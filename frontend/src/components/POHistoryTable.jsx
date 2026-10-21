import { useCallback, useEffect, useState } from "react";
import api from "../api/axios";
import DownloadPdfButton from "./DownloadPdfButton";

const statusStyles = {
  ordered: "bg-blue-50 text-blue-700",
  partially_received: "bg-amber-50 text-amber-800",
  blocked: "bg-red-50 text-red-700",
  received: "bg-emerald-50 text-emerald-800",
  cancelled: "bg-slate-100 text-slate-600",
};

export default function POHistoryTable() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadOrders = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await api.get("/api/v1/purchasing/orders");
      setOrders(response.data);
    } catch {
      setError("Purchase order history could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadOrders();
  }, [loadOrders]);

  return (
    <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-7">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Purchase order history
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Select an order to view its line items.
          </p>
        </div>
        <button
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          disabled={loading}
          onClick={() => void loadOrders()}
          type="button"
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500" role="status">
          Loading purchase orders…
        </p>
      ) : error ? (
        <p className="px-5 py-6 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : orders.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500">
          No purchase orders yet.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
              <tr>
                <th className="px-5 py-3 font-semibold sm:px-7" scope="col">
                  PO number
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Supplier
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Order date
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Expected delivery
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Budget estimate
                </th>
                <th className="px-5 py-3 font-semibold" scope="col">
                  Rate used
                </th>
                <th className="px-5 py-3 font-semibold sm:pr-7" scope="col">
                  Status
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {orders.map((order) => (
                <tr key={order.id}>
                  <td className="px-5 py-4 sm:px-7">
                    <div className="space-y-3">
                      <details>
                        <summary className="cursor-pointer font-semibold text-emerald-900">
                          {order.po_number}
                        </summary>
                        <ul className="mt-2 space-y-1 pl-4 text-xs text-slate-600">
                          {order.items_summary.map((item, index) => (
                            <li key={`${item.item}-${index}`}>
                              {item.item}: {item.qty}
                            </li>
                          ))}
                          {order.items_summary.length === 0 && (
                            <li>No line items recorded.</li>
                          )}
                        </ul>
                      </details>
                      <DownloadPdfButton
                        endpoint={`/api/v1/purchasing/orders/${order.id}/pdf`}
                        filename={`purchase-order-${order.po_number}.pdf`}
                      />
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-800">
                    {order.supplier_name}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {order.order_date}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {order.expected_delivery_date}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-700">
                    {order.estimated_total_ron === null
                      ? "Not available"
                      : `${order.estimated_total_ron} RON`}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 text-slate-600">
                    {order.currency === "RON"
                      ? "1.000000 (RON)"
                      : order.budget_exchange_rate
                        ? `${order.budget_exchange_rate} RON/EUR`
                        : "Not recorded"}
                  </td>
                  <td className="whitespace-nowrap px-5 py-4 sm:pr-7">
                    <span
                      className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
                        statusStyles[order.status] || "bg-slate-100 text-slate-700"
                      }`}
                    >
                      {order.status.replaceAll("_", " ")}
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
