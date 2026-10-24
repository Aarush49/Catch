import { Camera, Check, X } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useState } from "react";
import { useAuth } from "./AuthProvider.jsx";
import { currency } from "../lib/impact.js";

const API = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

async function preparePhoto(file) {
  try {
    const image = await createImageBitmap(file);
    const longest = Math.max(image.width, image.height);
    const scale = longest < 2800 ? Math.min(3, 2800 / longest) : Math.min(1, 4096 / longest);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.width * scale));
    canvas.height = Math.max(1, Math.round(image.height * scale));
    const context = canvas.getContext("2d", { alpha: false });
    context.fillStyle = "white";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.filter = "contrast(1.18) brightness(1.02)";
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    image.close();
    const blob = await new Promise(resolve => canvas.toBlob(resolve, "image/jpeg", 0.94));
    return blob || file;
  } catch {
    return file;
  }
}

export default function ScanSheet({ open, onClose }) {
  const [status, setStatus] = useState("idle");
  const [receipt, setReceipt] = useState(null);
  const [error, setError] = useState("");
  const { user } = useAuth();
  const reduce = useReducedMotion();

  useEffect(() => {
    if (!open) {
      setStatus("idle");
      setReceipt(null);
      setError("");
    }
  }, [open]);

  async function file(event) {
    const selected = event.target.files?.[0];
    event.target.value = "";
    if (!selected) return;
    setStatus("parsing");
    setError("");
    setReceipt(null);
    try {
      const body = new FormData();
      const photo = await preparePhoto(selected);
      body.append("file", photo, photo === selected ? selected.name : "receipt.jpg");
      const response = await fetch(`${API}/api/receipts/scan`, {
        method: "POST",
        headers: { Authorization: `Bearer ${user?.token || ""}` },
        body,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Receipt scan failed.");
      setReceipt(result);
      setStatus("done");
      if (!result.items?.length) setError("I couldn't read any item lines. Try a closer, brighter photo with the full receipt in frame.");
    } catch (err) {
      setError(err.message || "Could not reach the receipt scanner. Check that the backend is running.");
      setStatus("error");
    }
  }

  if (!open) return null;
  return <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/45" role="dialog" aria-modal="true" aria-label="Scan a receipt" onMouseDown={e => e.target === e.currentTarget && onClose()}>
    <motion.section initial={reduce ? {} : { y: "100%" }} animate={{ y: 0 }} transition={{ type: "spring", damping: 28, stiffness: 280 }} className="max-h-[88vh] w-full max-w-3xl overflow-y-auto rounded-t-[20px] border border-ink/10 bg-raised p-5 pb-8 shadow-soft">
      <div className="mx-auto mb-5 h-1 w-10 rounded-full bg-ink/15" />
      <div className="flex items-center justify-between"><div><p className="eyebrow">Receipt import</p><h2 className="mt-1 text-2xl font-semibold">Scan a receipt</h2></div><button onClick={onClose} aria-label="Close scan" className="grid h-10 w-10 place-items-center rounded-control border border-ink/10"><X size={19} strokeWidth={1.75} /></button></div>
      {status === "idle" && <label className="mt-6 flex cursor-pointer flex-col rounded-card border border-dashed border-ink/20 bg-surface p-5"><div className="grid h-44 place-items-center rounded-control border border-ink/10 bg-raised"><div className="relative h-24 w-36"><span className="absolute left-0 top-0 h-5 w-5 border-l border-t border-regal" /><span className="absolute right-0 top-0 h-5 w-5 border-r border-t border-regal" /><span className="absolute bottom-0 left-0 h-5 w-5 border-b border-l border-regal" /><span className="absolute bottom-0 right-0 h-5 w-5 border-b border-r border-regal" /><Camera className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-regal" size={28} strokeWidth={1.75} /></div></div><span className="mt-5 font-semibold">Take a photo or choose a file</span><span className="mt-1 text-sm text-prussian/60">Use good lighting and keep the receipt flat and fully in frame.</span><input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={file} /></label>}
      {status === "parsing" && <div className="py-12"><p className="text-sm font-medium">Reading receipt lines</p><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-linen"><motion.div className="h-full rounded-full bg-regal" initial={{ width: "5%" }} animate={{ width: "94%" }} transition={{ duration: 12, ease: "easeOut" }} /></div><p className="mt-3 text-xs text-prussian/50">Enhancing the photo and checking the receipt in sections</p></div>}
      {error && <p role="alert" className="mt-4 rounded-control bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {status === "done" && receipt && <div className="mt-6"><div className="mb-4 flex items-center gap-2 text-jungle"><Check size={18} strokeWidth={1.75} /><span className="text-sm font-medium">{receipt.items?.length || 0} items found{receipt.store ? ` at ${receipt.store}` : ""}</span></div><div className="divide-y divide-ink/10">{(receipt.items || []).map((item, index) => <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .25, delay: Math.min(index * .05, .5) }} key={`${item.name}-${index}`} className="flex items-center justify-between gap-4 py-4"><span className="font-medium">{item.name}<small className="ml-2 text-prussian/50">{item.category}</small></span><span className="text-right"><strong className="tabular block font-medium">{currency(Number(item.price), 2)}</strong><small className="text-prussian/55">est. {Number(item.carbon_kg_co2e || 0).toFixed(2)} kg CO₂e</small></span></motion.div>)}</div>{receipt.total != null && <p className="mt-4 text-right font-semibold">Receipt total: {currency(Number(receipt.total), 2)}</p>}<button onClick={onClose} className="primary-button mt-5 w-full">Done</button></div>}
      {status === "error" && <button onClick={() => { setStatus("idle"); setError(""); }} className="primary-button mt-5 w-full">Try another photo</button>}
    </motion.section>
  </div>;
}
