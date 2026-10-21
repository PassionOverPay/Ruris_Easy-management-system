import { useState } from "react";
import api from "../api/axios";

export default function DownloadPdfButton({ endpoint, filename }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  async function downloadPdf() {
    if (downloading) return;
    setDownloading(true);
    setError("");
    try {
      const response = await api.get(endpoint, { responseType: "blob" });
      const objectUrl = URL.createObjectURL(
        new Blob([response.data], { type: "application/pdf" }),
      );
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
    } catch {
      setError("PDF could not be downloaded. Please try again.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        aria-busy={downloading}
        className="whitespace-nowrap rounded-lg border border-emerald-800 px-3 py-2 text-xs font-semibold text-emerald-900 transition hover:bg-emerald-50 disabled:cursor-wait disabled:opacity-60"
        disabled={downloading}
        onClick={() => void downloadPdf()}
        type="button"
      >
        {downloading ? "Preparing PDF…" : "Download PDF"}
      </button>
      {error && (
        <span className="max-w-40 text-xs text-red-700" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
