"use client";

import { CardWrapper } from "@/components/CardWrapper";
import type { BalanceViewCard as TBalanceViewCard } from "@/lib/types";

type Props = {
  card: TBalanceViewCard;
  onClose: () => void;
  onSubmit: (submission: Record<string, unknown>) => void;
};

const fmt = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function BalanceViewCard({ card, onClose, onSubmit }: Props) {
  return (
    <CardWrapper title={card.title} subtitle={card.subtitle ?? undefined} onClose={onClose}>
      <div className="rounded-card bg-rs-yellow-lt border-l-4 border-rs-yellow p-4 mb-3">
        <div className="text-xs text-rs-ink-3 uppercase tracking-wide">Total balance</div>
        <div className="text-3xl font-bold text-rs-ink mt-1">{fmt(card.total_balance)}</div>
        <div className="text-xs text-rs-ink-3 mt-1">
          {fmt(card.vested_balance)} vested · {card.accounts.length} account
          {card.accounts.length === 1 ? "" : "s"}
        </div>
      </div>
      <div className="space-y-2">
        {card.accounts.map((a, i) => (
          <div key={i} className="border border-rs-border rounded p-3">
            <div className="font-medium text-rs-ink text-sm">{a.plan_name}</div>
            <div className="text-xs text-rs-ink-3 uppercase mt-0.5">{a.type}</div>
            <div className="text-lg font-semibold text-rs-ink mt-2">{fmt(a.balance)}</div>
            <div className="text-xs text-rs-ink-3">{fmt(a.vested_balance)} vested</div>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => onSubmit({ _acknowledged: true })}
        className="mt-4 w-full bg-rs-primary hover:bg-rs-primary-dk text-white rounded-md py-2 text-sm font-medium"
      >
        Done
      </button>
    </CardWrapper>
  );
}
