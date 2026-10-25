"""POST /api/predictions: no login, correct compounding, and Gemini's explanation with a safe fallback."""

import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from google.genai import errors, types

from app.main import app
from backend.services import gemini_service


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def gemini_response(contents, reply=None, finish=types.FinishReason.STOP):
    """Gemini's reply shape; by default a sentence restating the amount from the prompt."""
    if reply is None:
        reply = f"Skipping these could grow to about {re.search(r'\$[\d,]+\.\d\d', contents).group()} over time."
    return SimpleNamespace(text=reply, candidates=[SimpleNamespace(finish_reason=finish)])


@pytest.fixture
def gemini(monkeypatch):
    """A fake Gemini that records each request and answers with `reply`/`finish` (or raises `error`)."""
    fake = SimpleNamespace(calls=[], reply=None, finish=types.FinishReason.STOP, error=None)

    def generate_content(model, contents, config):
        fake.calls.append(SimpleNamespace(model=model, contents=contents, config=config))
        if fake.error:
            raise fake.error
        return gemini_response(contents, fake.reply, fake.finish)

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-never-real")
    monkeypatch.setattr(gemini_service.genai, "Client", lambda api_key: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    return fake


def monthly_simulation(monthly, years, annual_return):
    """Independent check: deposit at each month end, grow monthly at the rate that compounds to annual_return."""
    rate = (1 + annual_return) ** (1 / 12) - 1
    balance = 0.0
    for _ in range(years * 12):
        balance = balance * (1 + rate) + monthly
    return balance


def test_recurring_projection_needs_no_login_and_grows_every_monthly_saving(client, gemini):
    response = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10})
    assert response.status_code == 200, response.text
    recurring = response.json()["recurring"]
    assert recurring["monthly_savings"] == 72 and recurring["total_saved"] == 8640
    assert recurring["future_savings"] == pytest.approx(monthly_simulation(72, 10, 0.07), abs=0.01)
    assert recurring["future_savings"] > recurring["total_saved"]
    assert recurring["future_value_if_saved"] == recurring["future_savings"]  # nothing replaces it when skipping
    amount = f"${recurring['future_savings']:,.2f}"
    assert response.json()["explanation"] == f"Skipping these could grow to about {amount} over time."
    assert response.json()["explanation_source"] == "gemini"
    assert f"{amount} in 10 years" in gemini.calls[0].contents


def test_lower_price_alternative_saves_the_monthly_difference(client, gemini):
    body = client.post("/api/predictions", json={"amount": 50, "alternative_amount": 35, "times_per_month": 2, "years": 30}).json()
    assert body["recurring"]["monthly_savings"] == 30 and body["recurring"]["total_saved"] == 10800
    assert body["recurring"]["future_savings"] == pytest.approx(monthly_simulation(30, 30, 0.07), abs=0.01)
    assert body["recurring"]["future_value_if_saved"] == pytest.approx(monthly_simulation(100, 30, 0.07), abs=0.01)
    assert "lower-cost recurring option" in gemini.calls[0].contents


def test_zero_return_is_plain_addition(client, gemini):
    body = client.post("/api/predictions", json={"amount": 10, "times_per_month": 3, "years": 5, "annual_return": 0}).json()
    assert body["recurring"]["future_savings"] == body["recurring"]["total_saved"] == 1800


def test_one_time_purchase_compounds_once_a_year(client, gemini):
    body = client.post("/api/predictions", json={"amount": 100, "years": 10}).json()
    assert body["future_savings"] == round(100 * 1.07 ** 10, 2) and "recurring" not in body


def test_no_saving_skips_gemini(client, gemini):
    body = client.post("/api/predictions", json={"amount": 20, "alternative_amount": 25, "times_per_month": 4, "years": 10}).json()
    assert body["recurring"]["future_savings"] == 0 and body["explanation_source"] == "fallback"
    assert "doesn't save" in body["explanation"] and gemini.calls == []


def test_gemini_failure_falls_back_and_is_retried_later(client, gemini):
    gemini.error = TimeoutError("slow")
    body = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()
    assert body["explanation_source"] == "fallback" and "you could have about $" in body["explanation"]
    gemini.error = None
    body = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()
    assert body["explanation_source"] == "gemini" and len(gemini.calls) == 2


def test_quota_error_pauses_gemini_for_the_suggested_delay(client, gemini, monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(gemini_service.time, "monotonic", lambda: clock.now)
    gemini.error = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED", "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "30s"}]}})
    for times in (4, 5, 6):
        body = client.post("/api/predictions", json={"amount": 18, "times_per_month": times, "years": 10}).json()
        assert body["explanation_source"] == "fallback" and body["recurring"]["future_savings"] > 0
    assert len(gemini.calls) == 1
    gemini.error = None
    clock.now += 29
    assert client.post("/api/predictions", json={"amount": 18, "times_per_month": 7, "years": 10}).json()["explanation_source"] == "fallback"
    clock.now += 2
    assert client.post("/api/predictions", json={"amount": 18, "times_per_month": 7, "years": 10}).json()["explanation_source"] == "gemini"


def test_quota_pause_defaults_and_bounds():
    error = lambda details: errors.ClientError(429, {"error": {"code": 429, "details": details}})
    assert gemini_service._quota_pause_seconds(error([])) == gemini_service.QUOTA_PAUSE_SECONDS
    assert gemini_service._quota_pause_seconds(error([{"retryDelay": "1499s"}])) == 1499
    assert gemini_service._quota_pause_seconds(error([{"retryDelay": "0.2s"}])) == 5
    assert gemini_service._quota_pause_seconds(error([{"retryDelay": "90000s"}])) == 3600


@pytest.mark.parametrize("reply, finish", [
    ("Skipping these recurring purchases could grow to about $12,", types.FinishReason.MAX_TOKENS),  # cut off
    ("Target", types.FinishReason.STOP),  # no amount
    ("You could have about $99,999.00 someday.", types.FinishReason.STOP),  # wrong amount
    ("", types.FinishReason.STOP),
])
def test_unusable_gemini_replies_fall_back(client, gemini, reply, finish):
    gemini.reply, gemini.finish = reply, finish
    body = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()
    assert body["explanation_source"] == "fallback"
    assert body["explanation"] == f"By skipping these recurring purchases, you could have about ${body['recurring']['future_savings']:,.2f} after 10 years."


@pytest.mark.parametrize("model, expected", [
    ("gemini-3.8-flash", {"thinking_level": types.ThinkingLevel.MINIMAL}),
    ("gemini-3.5-pro", {"thinking_level": types.ThinkingLevel.LOW}),
    ("gemini-2.5-flash", {"thinking_budget": 0}),
    ("gemini-2.0-flash", None),
])
def test_explanations_skip_thinking_so_the_sentence_fits(client, gemini, monkeypatch, model, expected):
    monkeypatch.setenv("GEMINI_EXPLANATION_MODEL", model)
    assert client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()["explanation_source"] == "gemini"
    config = gemini.calls[0].config
    assert config.max_output_tokens == 256
    if expected is None:
        assert config.thinking_config is None
    else:
        assert all(getattr(config.thinking_config, key) == value for key, value in expected.items())


def test_explanations_use_their_own_fast_model(client, gemini, monkeypatch):
    monkeypatch.delenv("GEMINI_EXPLANATION_MODEL", raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10})
    assert gemini.calls[0].model == "gemini-3.5-flash"


def test_model_rejecting_minimal_thinking_is_retried_with_low(client, monkeypatch):
    calls = []

    def generate_content(model, contents, config):
        calls.append(config.thinking_config.thinking_level)
        if config.thinking_config.thinking_level == types.ThinkingLevel.MINIMAL:
            raise errors.ClientError(400, {"error": {"code": 400, "status": "INVALID_ARGUMENT",
                "message": "Thinking level MINIMAL is not supported for this model. Please retry with other thinking level."}})
        return gemini_response(contents)

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-never-real")
    monkeypatch.setenv("GEMINI_EXPLANATION_MODEL", "gemini-3.8-flash")
    monkeypatch.setattr(gemini_service.genai, "Client", lambda api_key: SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    body = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()
    assert body["explanation_source"] == "gemini"
    assert calls == [types.ThinkingLevel.MINIMAL, types.ThinkingLevel.LOW]


def test_repeated_inputs_reuse_gemini_sentence_and_requests_time_out(client, gemini):
    for _ in range(3):
        assert client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()["explanation_source"] == "gemini"
    assert len(gemini.calls) == 1
    options = gemini.calls[0].config.http_options
    assert options.timeout == gemini_service.EXPLANATION_TIMEOUT_MS >= 10_000 and options.retry_options.attempts == 1
    client.post("/api/predictions", json={"amount": 18, "times_per_month": 5, "years": 10})
    assert len(gemini.calls) == 2


def test_gemini_client_stays_open_for_the_request(client, monkeypatch):
    class ClosingClient:
        """Like google-genai 2.x: the HTTP connection closes when the Client is garbage collected."""
        def __init__(self, api_key):
            self.state = state = {"closed": False}

            def generate_content(model, contents, config):
                if state["closed"]:
                    raise RuntimeError("Cannot send a request, as the client has been closed.")
                return gemini_response(contents)
            self.models = SimpleNamespace(generate_content=generate_content)

        def __del__(self):
            self.state["closed"] = True

    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key-never-real")
    monkeypatch.setattr(gemini_service.genai, "Client", ClosingClient)
    body = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()
    assert body["explanation_source"] == "gemini" and body["explanation"].startswith("Skipping these could grow")


def test_missing_gemini_key_still_returns_the_projection(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    body = client.post("/api/predictions", json={"amount": 18, "times_per_month": 4, "years": 10}).json()
    assert body["explanation_source"] == "fallback" and body["recurring"]["future_savings"] > 0


@pytest.mark.parametrize("payload", [
    {"amount": 0, "years": 10}, {"amount": 5, "years": 0}, {"amount": 5, "years": 101},
    {"amount": 5, "times_per_month": 0}, {"amount": 5, "annual_return": 1.5}, {"amount": 5, "alternative_amount": -1},
])
def test_invalid_inputs_are_422(client, payload):
    assert client.post("/api/predictions", json=payload).status_code == 422
