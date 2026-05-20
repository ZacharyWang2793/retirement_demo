"use client";

import { useMemo, useState } from "react";

import { CardWrapper } from "@/components/CardWrapper";
import type { AllocationFormCard as TAllocationFormCard } from "@/lib/types";

type Props = {
  card: TAllocationFormCard;
  onClose: () => void;
  onSubmit: (submission: Record<string, unknown>) => void;
};

type Fund = { ticker: string; name: string; current_pct: number; target_pct: number };

export function AllocationFormCard({ card, onClose, onSubmit }: Props) {
  const [funds, setFunds] = useState<Fund[]>(() => card.funds.map((f) => ({ ...f })));
  const [newTicker, setNewTicker] = useState("");
  const [newPct, setNewPct] = useState(0);
  const [showAdd, setShowAdd] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const total = useMemo(() => funds.reduce((s, f) => s + f.target_pct, 0), [funds]);
  const remaining = 100 - total;
  const valid = Math.abs(remaining) < 0.05;

  function updateFundPct(ticker: string, pct: number) {
    setFunds((prev) => prev.map((f) => (f.ticker === ticker ? { ...f, target_pct: pct } : f)));
  }

  function removeFund(ticker: string) {
    setFunds((prev) => prev.filter((f) => f.ticker !== ticker));
  }

  function addFund() {
    const ticker = newTicker.trim().toUpperCase();
    setAddError(null);
    if (!ticker) {
      setAddError("Enter a ticker symbol.");
      return;
    }
    if (funds.some((f) => f.ticker === ticker)) {
      setAddError(`${ticker} is already in the list.`);
      return;
    }
    setFunds((prev) => [...prev, { ticker, name: ticker, current_pct: 0, target_pct: Number(newPct) || 0 }]);
    setNewTicker("");
    setNewPct(0);
    setShowAdd(false);
  }

  function handleSave() {
    if (!valid) return;
    onSubmit({
      account_id: card.account_id,
      allocations: funds.map((f) => ({ ticker: f.ticker, target_pct: f.target_pct })),
    });
  }

  let banner: { color: string; text: string };
  if (valid) {
    banner = { color: "bg-green-50 text-green-800 border-green-200", text: `Total: ${total.toFixed(1)}% ✓ — ready to save` };
  } else if (remaining > 0) {
    banner = { color: "bg-amber-50 text-amber-800 border-amber-200", text: `Total: ${total.toFixed(1)}% — ${remaining.toFixed(1)}% still unallocated` };
  } else {
    banner = { color: "bg-red-50 text-red-800 border-red-200", text: `Total: ${total.toFixed(1)}% — over by ${(-remaining).toFixed(1)}%` };
  }

  return (
    <CardWrapper title={card.title} subtitle={`${card.account_label} · Must sum to 100%.`} onClose={onClose}>
      <div className="space-y-3">
        {funds.length === 0 ? (
          <div className="text-sm text-rs-ink-3 italic">No funds. Add one below to get started.</div>
        ) : (
          funds.map((f) => (
            <div key={f.ticker} className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-baseline mb-1">
                  <span className="text-sm font-medium text-rs-ink truncate">
                    {f.name} ({f.ticker})
                  </span>
                  <span className="text-xs text-rs-ink-3 ml-2">
                    current {f.current_pct.toFixed(1)}% → <strong>{f.target_pct.toFixed(1)}%</strong>
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={0.5}
                  value={f.target_pct}
                  onChange={(e) => updateFundPct(f.ticker, Number(e.target.value))}
                  className="w-full"
                />
              </div>
              <button
                type="button"
                onClick={() => removeFund(f.ticker)}
                title={`Remove ${f.ticker}`}
                className="w-7 h-7 rounded-full border border-rs-border-strong text-rs-ink-3 hover:bg-red-50 hover:text-red-600 hover:border-red-300 flex items-center justify-center text-sm flex-shrink-0 mt-1"
              >
                ✕
              </button>
            </div>
          ))
        )}
      </div>

      <div className={`mt-3 px-3 py-2 text-sm border rounded ${banner.color}`}>{banner.text}</div>

      <div className="mt-3 border-t border-rs-border pt-3">
        {!showAdd ? (
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="text-sm text-rs-primary hover:text-rs-primary-dk font-medium"
          >
            ➕ Add a fund
          </button>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Ticker (e.g. VTSAX)"
                value={newTicker}
                onChange={(e) => setNewTicker(e.target.value)}
                className="flex-1 border border-rs-border rounded px-2 py-1 text-sm"
              />
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={newPct}
                onChange={(e) => setNewPct(Number(e.target.value))}
                className="w-20 border border-rs-border rounded px-2 py-1 text-sm"
              />
              <button
                type="button"
                onClick={addFund}
                className="bg-rs-yellow-lt border border-rs-yellow rounded px-3 py-1 text-sm font-medium hover:bg-rs-yellow"
              >
                Add
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowAdd(false);
                  setAddError(null);
                }}
                className="text-rs-ink-3 hover:text-rs-ink px-2"
              >
                ✕
              </button>
            </div>
            {addError ? <div className="text-xs text-red-600">{addError}</div> : null}
          </div>
        )}
      </div>

      <div className="grid grid-cols-[2fr_1fr] gap-2 mt-4">
        <button
          type="button"
          onClick={handleSave}
          disabled={!valid}
          className="bg-rs-primary hover:bg-rs-primary-dk disabled:bg-rs-border-strong disabled:cursor-not-allowed text-white rounded-md py-2 text-sm font-medium"
        >
          {card.submit_label || "Save allocation"}
        </button>
        <button
          type="button"
          onClick={() => onSubmit({ _cancelled: true })}
          className="border border-rs-border-strong hover:bg-rs-surface-2 text-rs-ink-2 rounded-md py-2 text-sm font-medium"
        >
          Cancel
        </button>
      </div>
    </CardWrapper>
  );
}
