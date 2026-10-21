import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import api from "../api/axios";

function todayAsDateInput() {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 10);
}

export default function InvoiceProcessing() {
  const [purchaseOrders, setPurchaseOrders] = useState([]);
  const [purchaseOrdersError, setPurchaseOrdersError] = useState("");
  const [purchaseOrderId, setPurchaseOrderId] = useState("");
  const [match, setMatch] = useState(null);
  const [lookupMessage, setLookupMessage] = useState(null);
  const [invoiceMessage, setInvoiceMessage] = useState(null);
  const {
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm({
    defaultValues: {
      invoice_number: "",
      supplier_name: "",
      invoice_date: todayAsDateInput(),
      currency: "RON",
      amount_original: "",
    },
  });

  useEffect(() => {
    async function loadPurchaseOrders() {
      try {
        const response = await api.get("/api/v1/purchasing/orders");
        setPurchaseOrders(response.data);
      } catch {
        setPurchaseOrdersError("Purchase orders could not be loaded.");
      }
    }
    void loadPurchaseOrders();
  }, []);

  async function fetchMatch(event) {
    event.preventDefault();
    const id = Number(purchaseOrderId);
    if (!Number.isSafeInteger(id) || id <= 0) {
      setMatch(null);
      setLookupMessage({
        type: "error",
        text: "Enter a valid positive purchase order ID.",
      });
      return;
    }

    setMatch(null);
    setLookupMessage({ type: "loading", text: "Fetching match details…" });
    setInvoiceMessage(null);
    try {
      const response = await api.get(`/api/v1/purchasing/${id}/match`);
      setMatch(response.data);
      setLookupMessage(null);
    } catch (error) {
      const status = error.response?.status;
      const text =
        status === 401
          ? "Your session has expired. Please sign in again."
          : status === 403
            ? "You do not have permission to review this purchase order."
            : status === 404
              ? "Purchase order not found."
              : "Could not fetch match details. Please try again.";
      setLookupMessage({ type: "error", text });
    }
  }

  async function submitInvoice(values) {
    setInvoiceMessage(null);
    try {
      const response = await api.post("/api/v1/accounting/invoices", {
        ...values,
        purchase_order_id: match.purchase_order_id,
        amount_original: Number(values.amount_original),
      });
      setInvoiceMessage({
        type: "success",
        text: `Invoice logged. Rate: ${response.data.exchange_rate} RON/${response.data.currency}. Converted amount: RON ${response.data.amount_ron}.`,
      });
      reset({
        invoice_number: "",
        supplier_name: "",
        invoice_date: todayAsDateInput(),
        currency: "RON",
        amount_original: "",
      });
    } catch (error) {
      const status = error.response?.status;
      const text =
        status === 401
          ? "Your session has expired. Please sign in again."
          : status === 400
            ? error.response.data?.detail ||
              "Invoice could not be saved. Check the invoice number and details."
            : status === 503
              ? error.response.data?.detail ||
                "The exchange rate is unavailable for this invoice date."
              : "Could not log the invoice. Please try again.";
      setInvoiceMessage({ type: "error", text });
    }
  }

  const inputClass =
    "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-700 focus:ring-2 focus:ring-emerald-700/20";
  const labelClass = "block text-sm font-medium text-slate-700";

  return (
    <section className="mt-8 max-w-4xl space-y-6">
      <form
        className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
        onSubmit={fetchMatch}
      >
        <div>
          <h2 className="text-xl font-semibold tracking-tight text-slate-900">
            Review purchase order match
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Fetch ordered and received quantities before entering the invoice.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="w-full sm:max-w-md">
            <label className={labelClass} htmlFor="match-purchase-order-id">
              Purchase order
            </label>
            <select
              className={inputClass}
              id="match-purchase-order-id"
              onChange={(event) => {
                setPurchaseOrderId(event.target.value);
                setMatch(null);
                setLookupMessage(null);
                setInvoiceMessage(null);
              }}
              required
              value={purchaseOrderId}
            >
              <option value="">-- Select Purchase Order --</option>
              {purchaseOrders.map((po) => (
                <option key={po.id} value={po.id}>
                  {po.po_number} - {po.supplier_name} ({po.order_date})
                </option>
              ))}
            </select>
          </div>
          <button
            className="min-h-11 rounded-lg bg-emerald-900 px-5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 disabled:cursor-wait disabled:opacity-60"
            disabled={lookupMessage?.type === "loading"}
            type="submit"
          >
            {lookupMessage?.type === "loading" ? "Fetching…" : "Fetch match"}
          </button>
        </div>
        {purchaseOrdersError && (
          <p className="text-sm text-red-700" role="alert">
            {purchaseOrdersError}
          </p>
        )}
        {lookupMessage && (
          <p
            className={
              lookupMessage.type === "error"
                ? "text-sm text-red-700"
                : "text-sm text-slate-600"
            }
            role={lookupMessage.type === "error" ? "alert" : "status"}
          >
            {lookupMessage.text}
          </p>
        )}
      </form>

      {match && (
        <>
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-200 px-5 py-4 sm:px-7">
              <h2 className="text-lg font-semibold text-slate-900">
                Ordered vs. received
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                Purchase order #{match.purchase_order_id}
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-600">
                  <tr>
                    <th className="px-5 py-3 font-semibold sm:px-7" scope="col">
                      Item
                    </th>
                    <th className="px-5 py-3 font-semibold" scope="col">
                      Ordered
                    </th>
                    <th className="px-5 py-3 font-semibold" scope="col">
                      Received
                    </th>
                    <th className="px-5 py-3 font-semibold" scope="col">
                      Difference
                    </th>
                    <th className="px-5 py-3 font-semibold sm:pr-7" scope="col">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {match.items.map((line, index) => (
                    <tr key={`${line.item}-${index}`}>
                      <th
                        className="whitespace-nowrap px-5 py-3 font-medium text-slate-900 sm:px-7"
                        scope="row"
                      >
                        {line.item}
                      </th>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-700">
                        {line.ordered_quantity}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-700">
                        {line.received_quantity}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 text-slate-700">
                        {line.missing_quantity > 0
                          ? `−${line.missing_quantity}`
                          : line.unexpected_quantity > 0
                            ? `+${line.unexpected_quantity}`
                            : "0"}
                      </td>
                      <td className="whitespace-nowrap px-5 py-3 sm:pr-7">
                        <span
                          className={
                            line.status === "matched"
                              ? "rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold capitalize text-emerald-800"
                              : "rounded-full bg-amber-50 px-2.5 py-1 text-xs font-semibold capitalize text-amber-800"
                          }
                        >
                          {line.status.replaceAll("_", " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {match.items.length === 0 && (
                    <tr>
                      <td
                        className="px-5 py-5 text-slate-500 sm:px-7"
                        colSpan={5}
                      >
                        No line items were returned for this purchase order.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <form
            className="space-y-5 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
            onSubmit={handleSubmit(submitInvoice)}
          >
            <div>
              <h2 className="text-xl font-semibold tracking-tight text-slate-900">
                Log invoice
              </h2>
              <p className="mt-1 text-sm text-slate-500">
                This invoice will be linked to purchase order #
                {match.purchase_order_id}.
              </p>
              <p className="mt-1 text-xs text-slate-500">
                EUR amounts are converted for informational RON reporting using
                the reference rate available on or before the invoice date. The
                selected rate does not determine VAT or accounting recognition.
              </p>
            </div>

            {invoiceMessage && (
              <p
                className={
                  invoiceMessage.type === "success"
                    ? "rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
                    : "rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"
                }
                role={invoiceMessage.type === "error" ? "alert" : "status"}
              >
                {invoiceMessage.text}
              </p>
            )}

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className={labelClass} htmlFor="invoice-number">
                  Invoice number
                </label>
                <input
                  className={inputClass}
                  id="invoice-number"
                  {...register("invoice_number", {
                    required: "Enter an invoice number.",
                  })}
                />
                {errors.invoice_number && (
                  <p className="mt-1 text-sm text-red-700" role="alert">
                    {errors.invoice_number.message}
                  </p>
                )}
              </div>
              <div>
                <label className={labelClass} htmlFor="invoice-supplier">
                  Supplier name
                </label>
                <input
                  className={inputClass}
                  id="invoice-supplier"
                  {...register("supplier_name", {
                    required: "Enter a supplier name.",
                  })}
                />
                {errors.supplier_name && (
                  <p className="mt-1 text-sm text-red-700" role="alert">
                    {errors.supplier_name.message}
                  </p>
                )}
              </div>
              <div>
                <label className={labelClass} htmlFor="invoice-date">
                  Invoice date
                </label>
                <input
                  className={inputClass}
                  id="invoice-date"
                  type="date"
                  {...register("invoice_date", {
                    required: "Choose an invoice date.",
                  })}
                />
                {errors.invoice_date && (
                  <p className="mt-1 text-sm text-red-700" role="alert">
                    {errors.invoice_date.message}
                  </p>
                )}
              </div>
              <div>
                <label className={labelClass} htmlFor="invoice-currency">
                  Currency
                </label>
                <select
                  className={inputClass}
                  id="invoice-currency"
                  {...register("currency", { required: true })}
                >
                  <option value="RON">RON</option>
                  <option value="EUR">EUR</option>
                </select>
              </div>
              <div>
                <label className={labelClass} htmlFor="invoice-amount">
                  Original amount
                </label>
                <input
                  className={inputClass}
                  id="invoice-amount"
                  min="0.01"
                  step="0.01"
                  type="number"
                  {...register("amount_original", {
                    required: "Enter the invoice amount.",
                    valueAsNumber: true,
                    min: { value: 0.01, message: "Amount must be greater than 0." },
                    validate: (value) =>
                      Number.isFinite(value) || "Enter a valid amount.",
                  })}
                />
                {errors.amount_original && (
                  <p className="mt-1 text-sm text-red-700" role="alert">
                    {errors.amount_original.message}
                  </p>
                )}
              </div>
            </div>

            <div className="border-t border-slate-200 pt-5">
              <button
                className="rounded-lg bg-emerald-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? "Logging invoice…" : "Log invoice"}
              </button>
            </div>
          </form>
        </>
      )}
    </section>
  );
}
