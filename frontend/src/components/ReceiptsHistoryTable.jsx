import { useCallback, useEffect, useState } from "react";
import api from "../api/axios";
import DownloadPdfButton from "./DownloadPdfButton";

export default function ReceiptsHistoryTable() {
  const [receipts, setReceipts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReceipts = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/api/v1/warehouse/receipts");
      setReceipts(response.data);
    } catch {
      setError("Goods receipt history could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReceipts();
  }, [loadReceipts]);

  return (
    <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-7">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Goods receipt history
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Previously logged shipments and condition notes.
          </p>
        </div>
        <button
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          disabled={loading}
          onClick={() => void loadReceipts()}
          type="button"
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500" role="status">
          Loading goods receipts…
        </p>
      ) : error ? (
        <p className="px-5 py-6 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : receipts.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500">
          No goods receipts yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-5 py-3 font-semibold sm:px-7" scope="col">
                  Receipt
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  PO reference
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Received
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Items
                </th>
                <th className="px-5 py-3 font-semibold sm:pr-7" scope="col">
                  Notes
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {receipts.map((receipt) => (
                <tr key={receipt.id}>
                  <th
                    className="whitespace-nowrap px-5 py-4 font-semibold text-slate-900 sm:px-7"
                    scope="row"
                  >
                    <div className="flex flex-col items-start gap-3">
                      <span>{receipt.receipt_number}</span>
                      <DownloadPdfButton
                        endpoint={`/api/v1/warehouse/receipts/${receipt.id}/pdf`}
                        filename={`goods-receipt-${receipt.receipt_number}.pdf`}
                      />
                    </div>
                  </th>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {receipt.purchase_order_id ?? "Unsolicited"}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {new Date(receipt.received_at).toLocaleString()}
                  </td>
                  <td className="min-w-48 px-5 py-4 text-slate-700">
                    <ul className="space-y-1">
                      {receipt.items_received.map((item, index) => (
                        <li key={`${item.item}-${index}`}>
                          {item.item}: {item.qty}
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="min-w-48 px-5 py-4 text-slate-600 sm:pr-7">
                    {receipt.notes || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
