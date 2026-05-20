"use client";

import { CardWrapper } from "@/components/CardWrapper";
import type { ConfirmationCard as TConfirmationCard } from "@/lib/types";

type Props = {
  card: TConfirmationCard;
  onClose: () => void;
  onSubmit: (submission: Record<string, unknown>) => void;
};

export function ConfirmationCard({ card, onClose, onSubmit }: Props) {
  return (
    <CardWrapper title={card.title} subtitle={card.subtitle ?? undefined} onClose={onClose}>
      {card.summary_lines?.length ? (
        <div className="text-sm text-rs-ink-2 space-y-1 mb-3">
          {card.summary_lines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      ) : null}
      {card.diff?.length ? (
        <div className="border border-rs-border rounded mb-3 overflow-hidden">
          {card.diff.map((row, i) => (
            <div
              key={i}
              className="grid grid-cols-[1fr_auto_auto] gap-2 px-3 py-2 text-sm border-b border-rs-border last:border-b-0"
            >
              <span className="text-rs-ink-3">{row.field}</span>
              <span className="text-rs-ink-3 line-through">{row.before}</span>
              <span className="text-rs-ink font-medium">{row.after}</span>
            </div>
          ))}
        </div>
      ) : null}
      <div className="grid grid-cols-[2fr_1fr] gap-2 mt-3">
        <button
          type="button"
          onClick={() => onSubmit({ _confirmed: true })}
          className="bg-rs-primary hover:bg-rs-primary-dk text-white rounded-md py-2 text-sm font-medium"
        >
          {card.submit_label || "Confirm"}
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
