from fastapi import FastAPI


app = FastAPI(title="Ripple API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
