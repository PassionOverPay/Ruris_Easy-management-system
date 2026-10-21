import { useCallback, useEffect, useState } from "react";
import api from "../api/axios";

const decisionStyles = {
  pending: "bg-amber-50 text-amber-800",
  matched: "bg-emerald-50 text-emerald-800",
  disputed: "bg-red-50 text-red-700",
  paid: "bg-blue-50 text-blue-700",
};

function amountToCents(amount) {
  const [whole, fraction = ""] = String(amount).split(".");
  return Number(whole) * 100 + Number(`${fraction}00`.slice(0, 2));
}

function formatCents(cents) {
  return (cents / 100).toFixed(2);
}

function InvoiceRows({ invoices }) {
  if (invoices.length === 0) {
    return <p className="py-4 text-sm text-slate-500">No invoices linked to this PO.</p>;
  }

  return (
    <div className="mt-3 overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
          <tr>
            <th className="px-3 py-2 font-semibold" scope="col">Invoice</th>
            <th className="px-3 py-2 font-semibold" scope="col">Date</th>
            <th className="px-3 py-2 font-semibold" scope="col">Conversion</th>
            <th className="px-3 py-2 font-semibold" scope="col">Status</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {invoices.map((invoice) => (
            <tr key={invoice.id}>
              <th className="whitespace-nowrap px-3 py-3 font-medium text-slate-900" scope="row">
                {invoice.invoice_number}
              </th>
              <td className="whitespace-nowrap px-3 py-3 text-slate-600">
                {invoice.invoice_date}
              </td>
              <td className="whitespace-nowrap px-3 py-3 text-slate-700">
                <p>{invoice.amount_original} {invoice.currency}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Rate: {invoice.exchange_rate} RON/{invoice.currency}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Converted: {invoice.amount_ron} RON
                </p>
                <p className="mt-1 max-w-xs whitespace-normal text-xs text-slate-400">
                  {invoice.exchange_rate_purpose}
                </p>
              </td>
              <td className="whitespace-nowrap px-3 py-3">
                <span
                  title={invoice.match_notes || undefined}
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${
                    decisionStyles[invoice.status] || "bg-slate-100 text-slate-700"
                  }`}
                >
                  {invoice.status}
                </span>
                {invoice.match_notes && (
                  <p className="mt-1 max-w-xs whitespace-normal text-xs text-slate-500">
                    {invoice.match_notes}
                  </p>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function InvoicesHistoryTable() {
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [ordersResponse, invoicesResponse] = await Promise.all([
        api.get("/api/v1/purchasing/orders"),
        api.get("/api/v1/accounting/invoices"),
      ]);
      setPurchaseOrders(ordersResponse.data);
      setInvoices(invoicesResponse.data);
    } catch {
      setError("Invoice history could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  const unlinkedInvoices = invoices.filter(
    (invoice) => invoice.purchase_order_id === null,
  );

  return (
    <section className="mt-8 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 sm:px-7">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">
            Invoice history by purchase order
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Review cumulative billing and the invoices linked to each order.
          </p>
        </div>
        <button
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          disabled={loading}
          onClick={() => void loadHistory()}
          type="button"
        >
          Refresh
        </button>
      </div>
      {loading ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500" role="status">
          Loading invoice history…
        </p>
      ) : error ? (
        <p className="px-5 py-6 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : purchaseOrders.length === 0 && unlinkedInvoices.length === 0 ? (
        <p className="px-5 py-8 text-center text-sm text-slate-500">
          No purchase orders or invoices yet.
        </p>
      ) : (
        <div className="space-y-3 p-4 sm:p-6">
          {purchaseOrders.map((order) => {
            const orderInvoices = invoices.filter(
              (invoice) => invoice.purchase_order_id === order.id,
            );
            const billed = orderInvoices.reduce(
              (total, invoice) => total + Number(invoice.amount_original),
              0,
            );
            const comparableInvoices = orderInvoices.filter(
              (invoice) =>
                invoice.currency === order.currency &&
                invoice.supplier_name.trim().toLowerCase() ===
                  order.supplier_name.trim().toLowerCase(),
            );
            const actualInvoiceCostRonCents = comparableInvoices.reduce(
              (total, invoice) => total + amountToCents(invoice.amount_ron),
              0,
            );
            const budgetVarianceRon =
              order.estimated_total_ron === null || comparableInvoices.length === 0
                ? null
                : actualInvoiceCostRonCents -
                  amountToCents(order.estimated_total_ron);

            return (
              <details
                className="rounded-lg border border-slate-200 px-4 py-3"
                key={order.id}
              >
                <summary className="cursor-pointer list-none">
                  <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
                    <div>
                      <p className="font-semibold text-slate-900">
                        PO #{order.id} · {order.po_number}
                      </p>
                      <p className="mt-1 text-sm text-slate-600">{order.supplier_name}</p>
                    </div>
                    <div className="text-sm text-slate-700 sm:text-right">
                      <p>
                        Expected:{" "}
                        {order.expected_total_original === null
                          ? "Not available"
                          : `${order.expected_total_original} ${order.currency}`}
                      </p>
                      <p className="mt-1">
                        Budget estimate:{" "}
                        {order.estimated_total_ron === null
                          ? "Not available (historical rate not recorded)"
                          : `${order.estimated_total_ron} RON`}
                        {order.budget_exchange_rate &&
                          ` at ${order.budget_exchange_rate} RON/${order.currency}`}
                      </p>
                      <p className="mt-1">
                        Billed: {billed.toFixed(2)} /{" "}
                        {order.expected_total_original === null
                          ? "—"
                          : Number(order.expected_total_original).toFixed(2)}{" "}
                        {order.currency}
                      </p>
                      {comparableInvoices.length > 0 && (
                        <p className="mt-1">
                          Converted comparable invoice total:{" "}
                          {formatCents(actualInvoiceCostRonCents)} RON
                        </p>
                      )}
                      {orderInvoices.length > 0 && (
                        <p className="mt-1">
                          Budget variance:{" "}
                          {budgetVarianceRon === null
                            ? comparableInvoices.length === 0
                              ? "Not available (no comparable invoices)"
                              : "Not available (historical budget rate missing)"
                            : `${formatCents(budgetVarianceRon)} RON`}
                        </p>
                      )}
                      {orderInvoices.length > 0 && (
                        <p className="mt-1 max-w-lg whitespace-normal text-xs text-slate-500">
                          Variance compares same-supplier, same-currency invoice
                          totals converted at each invoice&apos;s stored rate with
                          the PO estimate using its stored budget rate. It is not
                          an accounting FX gain or loss.
                        </p>
                      )}
                    </div>
                  </div>
                </summary>
                <InvoiceRows invoices={orderInvoices} />
              </details>
            );
          })}
          {unlinkedInvoices.length > 0 && (
            <details className="rounded-lg border border-slate-200 px-4 py-3">
              <summary className="cursor-pointer font-semibold text-slate-900">
                Invoices without a purchase order ({unlinkedInvoices.length})
              </summary>
              <InvoiceRows invoices={unlinkedInvoices} />
            </details>
          )}
        </div>
      )}
    </section>
  );
}
