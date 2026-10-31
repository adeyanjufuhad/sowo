"use client";

import type { PaymentMode, VendorSettings } from "@sowo/shared";
import Link from "next/link";
import { useEffect, useId, useState, type FormEvent } from "react";
import { SHOP_RENAMED_EVENT } from "@/components/auth/account-bar";
import { api, ApiRequestError, USING_MOCK } from "@/lib/api";

const field =
  "h-11 w-full rounded-xl bg-paper px-3.5 text-base ring-1 ring-line outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent-strong";

interface Draft {
  businessName: string;
  ownerName: string;
  whatsappPhoneNumberId: string;
  alertPhone: string;
  paymentMode: PaymentMode;
  bankName: string;
  bankAccountName: string;
  bankAccountNumber: string;
}

function toDraft(settings: VendorSettings): Draft {
  return {
    businessName: settings.businessName,
    ownerName: settings.ownerName ?? "",
    whatsappPhoneNumberId: settings.whatsappPhoneNumberId ?? "",
    alertPhone: settings.alertPhone ?? "",
    paymentMode: settings.paymentMode,
    bankName: settings.bankName ?? "",
    bankAccountName: settings.bankAccountName ?? "",
    bankAccountNumber: settings.bankAccountNumber ?? "",
  };
}

function Field({
  label,
  hint,
  children,
  id,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
  id: string;
}) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      {children}
      {hint ? <p className="mt-1.5 text-xs text-muted">{hint}</p> : null}
    </div>
  );
}

/** Where a vendor connects their WhatsApp number and says how buyers pay. Saved per shop by the API. */
export function SettingsForm() {
  const ids = {
    business: useId(),
    owner: useId(),
    number: useId(),
    alert: useId(),
    bank: useId(),
    account: useId(),
    digits: useId(),
  };
  const [saved, setSaved] = useState<VendorSettings | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (USING_MOCK) return;
    api
      .getVendorSettings()
      .then((settings) => {
        setSaved(settings);
        setDraft(toDraft(settings));
      })
      .catch((err) => setError(err instanceof ApiRequestError ? err.message : "Couldn't load your settings."));
  }, []);

  if (USING_MOCK) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        <p role="status" className="rounded-xl bg-paper-deep px-3.5 py-3 text-sm text-ink-soft">
          Shop settings need the real backend, and this copy of Sowo runs in demo mode.{" "}
          <Link href="/dashboard" className="font-medium text-accent-strong underline-offset-4 hover:underline">
            Back to the demo dashboard
          </Link>
          .
        </p>
      </div>
    );
  }

  function change<K extends keyof Draft>(key: K, value: Draft[K]) {
    setDraft((current) => (current ? { ...current, [key]: value } : current));
    setDone(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !draft) return;
    setBusy(true);
    setError(null);
    setDone(false);
    try {
      const manual = draft.paymentMode === "manual";
      const next = await api.updateVendorSettings({
        businessName: draft.businessName,
        ownerName: draft.ownerName,
        whatsappPhoneNumberId: draft.whatsappPhoneNumberId,
        alertPhone: draft.alertPhone,
        paymentMode: draft.paymentMode,
        bankName: manual ? draft.bankName : undefined,
        bankAccountName: manual ? draft.bankAccountName : undefined,
        bankAccountNumber: manual ? draft.bankAccountNumber : undefined,
      });
      if (next.businessName !== saved?.businessName) {
        window.dispatchEvent(new CustomEvent(SHOP_RENAMED_EVENT, { detail: next.businessName }));
      }
      setSaved(next);
      setDraft(toDraft(next));
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "Couldn't save. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  if (!draft || !saved) {
    return (
      <div className="mx-auto max-w-xl px-4 py-10 sm:px-6">
        {error ? (
          <p role="alert" className="rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">
            {error}
          </p>
        ) : (
          <div className="h-96 animate-pulse rounded-3xl bg-paper-deep" aria-hidden />
        )}
      </div>
    );
  }

  const manual = draft.paymentMode === "manual";

  return (
    <div className="mx-auto max-w-xl px-4 py-8 sm:px-6">
      <h1 className="font-display text-2xl font-semibold tracking-[-0.03em]">Shop settings</h1>
      <p className="mt-1.5 text-sm text-muted">
        {saved.businessName}. These are only yours: other shops on Sowo have their own.
      </p>

      <form onSubmit={submit} className="mt-6 space-y-8">
        <section aria-labelledby={`${ids.business}-title`} className="space-y-4 rounded-3xl bg-card p-5 ring-1 ring-line sm:p-6">
          <h2 id={`${ids.business}-title`} className="text-base font-semibold">
            Your shop
          </h2>
          <Field
            id={ids.business}
            label="Business name"
            hint="Buyers see this in the chat, and it's the name on your dashboard."
          >
            <input
              id={ids.business}
              value={draft.businessName}
              onChange={(e) => change("businessName", e.target.value)}
              required
              maxLength={120}
              autoComplete="organization"
              className={field}
            />
          </Field>
          <Field id={ids.owner} label="Your name" hint="What Sowo calls you when it speaks to buyers. Leave blank to use your business name.">
            <input
              id={ids.owner}
              value={draft.ownerName}
              onChange={(e) => change("ownerName", e.target.value)}
              autoComplete="given-name"
              maxLength={80}
              className={field}
            />
          </Field>
        </section>

        <section aria-labelledby={`${ids.number}-title`} className="space-y-4 rounded-3xl bg-card p-5 ring-1 ring-line sm:p-6">
          <div>
            <h2 id={`${ids.number}-title`} className="text-base font-semibold">
              WhatsApp
            </h2>
            <p className="mt-1 text-sm text-muted">
              {saved.whatsappConnected
                ? "Connected: Sowo answers buyers who message this number."
                : "Not connected yet. Sowo only answers once your number's ID is saved here."}
            </p>
          </div>
          <Field
            id={ids.number}
            label="WhatsApp phone number ID"
            hint="In Meta for Developers, open your app → WhatsApp → API setup. It is the long number labelled Phone number ID, not your phone number."
          >
            <input
              id={ids.number}
              value={draft.whatsappPhoneNumberId}
              onChange={(e) => change("whatsappPhoneNumberId", e.target.value)}
              inputMode="numeric"
              autoComplete="off"
              className={field}
            />
          </Field>
          <Field
            id={ids.alert}
            label="Your phone, for alerts"
            hint="Sowo messages this number when an order is paid or a buyer needs you. Include the country code, like 234 801 234 5678."
          >
            <input
              id={ids.alert}
              value={draft.alertPhone}
              onChange={(e) => change("alertPhone", e.target.value)}
              inputMode="tel"
              autoComplete="tel"
              className={field}
            />
          </Field>
        </section>

        <fieldset className="space-y-4 rounded-3xl bg-card p-5 ring-1 ring-line sm:p-6">
          <legend className="px-0 text-base font-semibold">How buyers pay you</legend>
          {(
            [
              ["paystack", "Paystack link", "Buyers pay online and Sowo confirms it automatically."],
              ["manual", "Bank transfer", "Buyers pay into your own account and you tap Mark paid once you see the money."],
            ] as const
          ).map(([value, title, text]) => (
            <label
              key={value}
              className="flex cursor-pointer items-start gap-3 rounded-2xl p-3 ring-1 ring-line has-[:checked]:bg-accent-wash has-[:checked]:ring-accent-strong"
            >
              <input
                type="radio"
                name="paymentMode"
                value={value}
                checked={draft.paymentMode === value}
                onChange={() => change("paymentMode", value)}
                className="mt-1 size-4 accent-[var(--color-accent-strong,#c2410c)]"
              />
              <span>
                <span className="block text-sm font-medium">{title}</span>
                <span className="block text-sm text-muted">{text}</span>
              </span>
            </label>
          ))}

          {manual ? (
            <div className="space-y-4 pt-1">
              <Field id={ids.bank} label="Bank">
                <input
                  id={ids.bank}
                  value={draft.bankName}
                  onChange={(e) => change("bankName", e.target.value)}
                  autoComplete="off"
                  maxLength={80}
                  placeholder="GTBank"
                  className={field}
                />
              </Field>
              <Field id={ids.account} label="Account name">
                <input
                  id={ids.account}
                  value={draft.bankAccountName}
                  onChange={(e) => change("bankAccountName", e.target.value)}
                  autoComplete="off"
                  maxLength={120}
                  className={field}
                />
              </Field>
              <Field id={ids.digits} label="Account number" hint="Ten digits.">
                <input
                  id={ids.digits}
                  value={draft.bankAccountNumber}
                  onChange={(e) => change("bankAccountNumber", e.target.value)}
                  inputMode="numeric"
                  autoComplete="off"
                  className={field}
                />
              </Field>
            </div>
          ) : null}
        </fieldset>

        {error ? (
          <p role="alert" className="rounded-lg bg-accent-wash px-3 py-2 text-sm text-accent-strong">
            {error}
          </p>
        ) : null}
        {done ? (
          <p role="status" className="rounded-lg bg-paper-deep px-3 py-2 text-sm text-ink-soft">
            Saved.
          </p>
        ) : null}

        <button
          type="submit"
          disabled={busy}
          className="h-11 w-full rounded-full bg-accent-strong px-4 text-sm font-medium text-white transition-[transform,background-color] hover:bg-[#a33515] active:scale-[0.99] disabled:opacity-60 sm:w-auto sm:px-8"
        >
          {busy ? "Saving…" : "Save settings"}
        </button>
      </form>
    </div>
  );
}
