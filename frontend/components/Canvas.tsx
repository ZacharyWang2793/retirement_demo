"use client";

import GridLayout from "react-grid-layout";
import { useEffect, useRef, useState } from "react";

import { GRID_COLS } from "@/lib/layout";
import type { CanvasCard, CardLayout } from "@/lib/types";
import { renderCard } from "@/components/cards";

type Props = {
  cards: CanvasCard[];
  onLayoutChange: (layouts: CardLayout[]) => void;
  onCardClose: (id: string) => void;
  onCardSubmit: (id: string, submission: Record<string, unknown>) => void;
};

const ROW_HEIGHT = 28; // px per grid unit

export function Canvas({ cards, onLayoutChange, onCardClose, onCardSubmit }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(1200);

  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setWidth(entry.contentRect.width);
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);

  return (
    <div ref={ref} className="w-full h-full overflow-auto pb-44">
      {cards.length === 0 ? (
        <div className="h-full flex items-center justify-center text-rs-ink-3 text-sm">
          Type below to spawn your first card.
        </div>
      ) : (
        <GridLayout
          layout={cards.map((c) => c.layout)}
          cols={GRID_COLS}
          rowHeight={ROW_HEIGHT}
          width={width}
          margin={[12, 12]}
          containerPadding={[16, 16]}
          draggableHandle=".drag-handle"
          onLayoutChange={(layout) =>
            onLayoutChange(layout.map((l) => ({ i: l.i, x: l.x, y: l.y, w: l.w, h: l.h })))
          }
          isResizable={false}
        >
          {cards.map((c) => (
            <div key={c.card.id}>
              {renderCard(c.card, {
                onClose: () => onCardClose(c.card.id),
                onSubmit: (sub) => onCardSubmit(c.card.id, sub),
              })}
            </div>
          ))}
        </GridLayout>
      )}
    </div>
  );
}
