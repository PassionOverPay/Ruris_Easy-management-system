import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import api from "../api/axios";

function todayAsDateInput() {
  const now = new Date();
  const localDate = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 10);
}

export default function CreatePOForm() {
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm({
    defaultValues: {
      supplier_name: "",
      order_date: todayAsDateInput(),
      expected_delivery_date: "",
      currency: "RON",
      items_summary: [{ item: "", qty: 1, unit_price: "" }],
    },
  });
  const { append, fields, remove } = useFieldArray({
    control,
    name: "items_summary",
  });
  const [submissionMessage, setSubmissionMessage] = useState(null);

  async function submitPurchaseOrder(values) {
    const payload = {
      supplier_name: values.supplier_name.trim(),
      order_date: values.order_date,
      expected_delivery_date: values.expected_delivery_date,
      currency: values.currency,
      items_summary: values.items_summary.map(({ item, qty, unit_price }) => ({
        item: item.trim(),
        qty: Number(qty),
        unit_price: Number(unit_price),
      })),
    };

    setSubmissionMessage(null);
    try {
      const response = await api.post("/api/v1/purchasing/orders", payload);
      setSubmissionMessage({
        type: "success",
        text: `Purchase Order created successfully as ${response.data.po_number}!`,
      });
      reset({
        supplier_name: "",
        order_date: todayAsDateInput(),
        expected_delivery_date: "",
        currency: "RON",
        items_summary: [{ item: "", qty: 1, unit_price: "" }],
      });
    } catch (error) {
      const status = error.response?.status;
      const message =
        status === 401
          ? "Your session has expired. Please sign in again."
          : status === 400
            ? error.response.data?.detail ||
              "The purchase order could not be saved. Check the PO number and details."
            : "The purchase order could not be created. Please try again.";
      setSubmissionMessage({ type: "error", text: message });
    }
  }

  const inputClass =
    "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-700 focus:ring-2 focus:ring-emerald-700/20";
  const labelClass = "block text-sm font-medium text-slate-700";

  return (
    <form
      className="mt-8 max-w-3xl space-y-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
      onSubmit={handleSubmit(submitPurchaseOrder)}
    >
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-slate-900">
          Create purchase order
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Add supplier and delivery details, then list the items to order.
        </p>
      </div>
      {submissionMessage && (
        <p
          className={
            submissionMessage.type === "success"
              ? "rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800"
              : "rounded-lg bg-red-50 px-3 py-2 text-sm text-red-800"
          }
          role={submissionMessage.type === "error" ? "alert" : "status"}
        >
          {submissionMessage.text}
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} htmlFor="supplier-name">
            Supplier name
          </label>
          <input
            className={inputClass}
            id="supplier-name"
            placeholder="Supplier company"
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
          <label className={labelClass} htmlFor="order-date">
            Order date
          </label>
          <input
            className={inputClass}
            id="order-date"
            type="date"
            {...register("order_date", { required: "Choose an order date." })}
          />
          {errors.order_date && (
            <p className="mt-1 text-sm text-red-700" role="alert">
              {errors.order_date.message}
            </p>
          )}
        </div>

        <div>
          <label className={labelClass} htmlFor="expected-delivery-date">
            Expected delivery date
          </label>
          <input
            className={inputClass}
            id="expected-delivery-date"
            type="date"
            {...register("expected_delivery_date", {
              required: "Choose an expected delivery date.",
            })}
          />
          {errors.expected_delivery_date && (
            <p className="mt-1 text-sm text-red-700" role="alert">
              {errors.expected_delivery_date.message}
            </p>
          )}
        </div>
        <div>
          <label className={labelClass} htmlFor="purchase-order-currency">
            Order currency
          </label>
          <select
            className={inputClass}
            id="purchase-order-currency"
            {...register("currency", { required: "Choose an order currency." })}
          >
            <option value="RON">RON</option>
            <option value="EUR">EUR</option>
          </select>
        </div>
      </div>

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold text-slate-800">
          Order items
        </legend>
        {fields.map((field, index) => (
          <div
            className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-[minmax(0,1fr)_7rem_9rem_auto] sm:items-end"
            key={field.id}
          >
            <div>
              <label className={labelClass} htmlFor={`item-name-${field.id}`}>
                Item name
              </label>
              <input
                className={inputClass}
                id={`item-name-${field.id}`}
                placeholder="e.g. Laptop"
                {...register(`items_summary.${index}.item`, {
                  required: "Enter an item name.",
                })}
              />
              {errors.items_summary?.[index]?.item && (
                <p className="mt-1 text-sm text-red-700" role="alert">
                  {errors.items_summary[index].item.message}
                </p>
              )}
            </div>
            <div>
              <label className={labelClass} htmlFor={`item-price-${field.id}`}>
                Unit price
              </label>
              <input
                className={inputClass}
                id={`item-price-${field.id}`}
                min="0.01"
                step="0.01"
                type="number"
                {...register(`items_summary.${index}.unit_price`, {
                  required: "Enter a unit price.",
                  valueAsNumber: true,
                  min: { value: 0.01, message: "Price must be greater than 0." },
                })}
              />
              {errors.items_summary?.[index]?.unit_price && (
                <p className="mt-1 text-sm text-red-700" role="alert">
                  {errors.items_summary[index].unit_price.message}
                </p>
              )}
            </div>
            <div>
              <label className={labelClass} htmlFor={`item-qty-${field.id}`}>
                Quantity
              </label>
              <input
                className={inputClass}
                id={`item-qty-${field.id}`}
                min="1"
                step="1"
                type="number"
                {...register(`items_summary.${index}.qty`, {
                  required: "Enter a quantity.",
                  valueAsNumber: true,
                  min: { value: 1, message: "Quantity must be at least 1." },
                  validate: (value) =>
                    Number.isInteger(value) || "Enter a whole number.",
                })}
              />
              {errors.items_summary?.[index]?.qty && (
                <p className="mt-1 text-sm text-red-700" role="alert">
                  {errors.items_summary[index].qty.message}
                </p>
              )}
            </div>
            <button
              className="min-h-10 rounded-lg border border-slate-300 px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={fields.length === 1}
              onClick={() => remove(index)}
              type="button"
            >
              Remove
            </button>
          </div>
        ))}
        <button
          className="rounded-lg border border-emerald-800 px-3 py-2 text-sm font-semibold text-emerald-900 transition hover:bg-emerald-50"
          onClick={() => append({ item: "", qty: 1, unit_price: "" })}
          type="button"
        >
          Add item
        </button>
      </fieldset>

      <div className="border-t border-slate-200 pt-5">
        <button
          className="rounded-lg bg-emerald-900 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-800 focus:outline-none focus:ring-2 focus:ring-emerald-700 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? "Creating purchase order…" : "Create purchase order"}
        </button>
      </div>
    </form>
  );
}
