"use client";

import { CardWrapper } from "@/components/CardWrapper";
import type { SuccessCard as TSuccessCard } from "@/lib/types";

type Props = {
  card: TSuccessCard;
  onClose: () => void;
  onSubmit: (submission: Record<string, unknown>) => void;
};

export function SuccessCard({ card, onClose, onSubmit }: Props) {
  return (
    <CardWrapper title={card.title} subtitle={card.subtitle ?? undefined} onClose={onClose}>
      <div className="flex items-start gap-3 mb-3">
        <span className="text-2xl">✓</span>
        <div className="text-sm text-rs-ink-2 space-y-1">
          {card.summary_lines?.map((line, i) => (
            <div key={i}>{line}</div>
          )) ?? <div>Request submitted.</div>}
          {card.request_id ? (
            <div className="text-xs text-rs-ink-3 mt-1">Request ID: {card.request_id}</div>
          ) : null}
        </div>
      </div>
      <button
        type="button"
        onClick={() => onSubmit({ _acknowledged: true })}
        className="mt-2 w-full bg-rs-primary hover:bg-rs-primary-dk text-white rounded-md py-2 text-sm font-medium"
      >
        {card.submit_label || "Done"}
      </button>
    </CardWrapper>
  );
}
