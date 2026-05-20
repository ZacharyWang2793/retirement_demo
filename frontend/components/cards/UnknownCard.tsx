"use client";

import { CardWrapper } from "@/components/CardWrapper";
import type { UnknownCard as TUnknownCard } from "@/lib/types";

type Props = {
  card: TUnknownCard;
  onClose: () => void;
};

export function UnknownCard({ card, onClose }: Props) {
  return (
    <CardWrapper title={card.title || card.card_type} subtitle={card.subtitle ?? undefined} onClose={onClose}>
      <div className="text-sm text-rs-ink-3">
        <p className="mb-3">
          This card type (<code className="text-rs-ink-2">{card.card_type}</code>) isn't yet
          ported to React. It'll work in the Streamlit app while we finish Phase 2.
        </p>
        <pre className="bg-rs-surface-2 border border-rs-border rounded p-2 overflow-auto text-[11px] text-rs-ink-2">
          {JSON.stringify(card, null, 2)}
        </pre>
      </div>
    </CardWrapper>
  );
}
