import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import api from "../api/axios";

export default function CreateReceiptForm() {
  const {
    control,
    formState: { errors, isSubmitting },
    handleSubmit,
    register,
    reset,
  } = useForm({
    defaultValues: {
      receipt_number: "",
      purchase_order_id: "",
      notes: "",
      items_received: [{ item: "", qty: 1 }],
    },
  });
  const { append, fields, remove } = useFieldArray({
    control,
    name: "items_received",
  });
  const [submissionMessage, setSubmissionMessage] = useState(null);

  async function submitReceipt(values) {
    const payload = {
      receipt_number: values.receipt_number.trim(),
      purchase_order_id:
        values.purchase_order_id === "" || values.purchase_order_id === null
          ? null
          : Number(values.purchase_order_id),
      notes: values.notes.trim() || null,
      items_received: values.items_received.map(({ item, qty }) => ({
        item: item.trim(),
        qty: Number(qty),
      })),
    };

    setSubmissionMessage(null);
    try {
      const response = await api.post("/api/v1/warehouse/receipts", payload);
      setSubmissionMessage({
        type: "success",
        text: `Goods receipt ${response.data.receipt_number} logged successfully.`,
      });
      reset({
        receipt_number: "",
        purchase_order_id: "",
        notes: "",
        items_received: [{ item: "", qty: 1 }],
      });
    } catch (error) {
      const status = error.response?.status;
      const message =
        status === 401
          ? "Your session has expired. Please sign in again."
          : status === 404
            ? error.response.data?.detail ||
              "The linked purchase order could not be found."
            : status === 400
              ? error.response.data?.detail ||
                "The receipt could not be saved. Check the receipt number and details."
              : "The goods receipt could not be logged. Please try again.";
      setSubmissionMessage({ type: "error", text: message });
    }
  }

  const inputClass =
    "mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-emerald-700 focus:ring-2 focus:ring-emerald-700/20";
  const labelClass = "block text-sm font-medium text-slate-700";

  return (
    <form
      className="mt-8 max-w-3xl space-y-6 rounded-xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
      onSubmit={handleSubmit(submitReceipt)}
    >
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-slate-900">
          Log goods receipt
        </h2>
        <p className="mt-1 text-sm text-slate-500">
          Record the shipment and note any condition or delivery issues.
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
          <label className={labelClass} htmlFor="receipt-number">
            Receipt number
          </label>
          <input
            className={inputClass}
            id="receipt-number"
            placeholder="GR-2026-001"
            {...register("receipt_number", {
              required: "Enter a receipt number.",
            })}
          />
          {errors.receipt_number && (
            <p className="mt-1 text-sm text-red-700" role="alert">
              {errors.receipt_number.message}
            </p>
          )}
        </div>

        <div>
          <label className={labelClass} htmlFor="purchase-order-id">
            Purchase order ID <span className="font-normal text-slate-500">(optional)</span>
          </label>
          <input
            className={inputClass}
            id="purchase-order-id"
            min="1"
            placeholder="e.g. 42"
            type="number"
            {...register("purchase_order_id", {
              setValueAs: (value) => (value === "" ? null : Number(value)),
              validate: (value) =>
                value === null ||
                (Number.isSafeInteger(value) && value > 0) ||
                "Enter a valid positive purchase order ID.",
            })}
          />
          {errors.purchase_order_id && (
            <p className="mt-1 text-sm text-red-700" role="alert">
              {errors.purchase_order_id.message}
            </p>
          )}
        </div>
      </div>

      <div>
        <label className={labelClass} htmlFor="receipt-notes">
          Condition notes <span className="font-normal text-slate-500">(optional)</span>
        </label>
        <textarea
          className={`${inputClass} min-h-24 resize-y`}
          id="receipt-notes"
          placeholder="Describe any damage, missing items, or other delivery issues."
          rows={3}
          {...register("notes")}
        />
      </div>

      <fieldset className="space-y-3">
        <legend className="text-sm font-semibold text-slate-800">
          Received items
        </legend>
        {fields.map((field, index) => (
          <div
            className="grid gap-3 rounded-lg border border-slate-200 p-3 sm:grid-cols-[minmax(0,1fr)_9rem_auto] sm:items-end"
            key={field.id}
          >
            <div>
              <label className={labelClass} htmlFor={`received-item-${field.id}`}>
                Item name
              </label>
              <input
                className={inputClass}
                id={`received-item-${field.id}`}
                placeholder="e.g. Laptop"
                {...register(`items_received.${index}.item`, {
                  required: "Enter an item name.",
                })}
              />
              {errors.items_received?.[index]?.item && (
                <p className="mt-1 text-sm text-red-700" role="alert">
                  {errors.items_received[index].item.message}
                </p>
              )}
            </div>
            <div>
              <label className={labelClass} htmlFor={`received-qty-${field.id}`}>
                Quantity
              </label>
              <input
                className={inputClass}
                id={`received-qty-${field.id}`}
                min="1"
                step="1"
                type="number"
                {...register(`items_received.${index}.qty`, {
                  required: "Enter a quantity.",
                  valueAsNumber: true,
                  min: { value: 1, message: "Quantity must be at least 1." },
                  validate: (value) =>
                    Number.isInteger(value) || "Enter a whole number.",
                })}
              />
              {errors.items_received?.[index]?.qty && (
                <p className="mt-1 text-sm text-red-700" role="alert">
                  {errors.items_received[index].qty.message}
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
          onClick={() => append({ item: "", qty: 1 })}
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
          {isSubmitting ? "Logging receipt…" : "Log receipt"}
        </button>
      </div>
    </form>
  );
}
