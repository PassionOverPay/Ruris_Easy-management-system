import { useCallback, useEffect, useState } from "react";
import api from "../api/axios";

const decisionStyles = {
  pending: "bg-amber-50 text-amber-800",
  matched: "bg-emerald-50 text-emerald-800",
  disputed: "bg-red-50 text-red-700",
  paid: "bg-blue-50 text-blue-700",
};

export default function InvoicesHistoryTable() {
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadInvoices = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/api/v1/accounting/invoices");
      setInvoices(response.data);
    } catch {
      setError("Invoice history could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInvoices();
  }, [loadInvoices]);

  return (
    <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-7">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Invoice history
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Previously logged supplier invoices and decisions.
          </p>
        </div>
        <button
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          disabled={loading}
          onClick={() => void loadInvoices()}
          type="button"
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500" role="status">
          Loading invoices…
        </p>
      ) : error ? (
        <p className="px-5 py-6 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : invoices.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500">
          No invoices yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-5 py-3 font-semibold sm:px-7" scope="col">
                  Invoice
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  PO reference
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Supplier
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Invoice date
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Original
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Converted
                </th>
                <th className="px-5 py-3 font-semibold sm:pr-7" scope="col">
                  Match decision
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {invoices.map((invoice) => (
                <tr key={invoice.id}>
                  <th
                    className="whitespace-nowrap px-5 py-4 font-semibold text-slate-900 sm:px-7"
                    scope="row"
                  >
                    {invoice.invoice_number}
                  </th>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {invoice.purchase_order_id ?? "—"}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-700">
                    {invoice.supplier_name}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {invoice.invoice_date}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-700">
                    {invoice.amount_original} {invoice.currency}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 font-medium text-slate-800">
                    {invoice.amount_ron} RON
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 sm:pr-7">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
                        decisionStyles[invoice.status] || "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {invoice.status}
                    </span>
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
