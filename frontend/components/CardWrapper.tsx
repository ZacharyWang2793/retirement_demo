"use client";

import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string | null;
  onClose?: () => void;
  children: ReactNode;
};

/**
 * Standard chrome for every card: title bar (acts as the drag handle via the
 * .drag-handle class react-grid-layout looks for) + close button + scrollable body.
 */
export function CardWrapper({ title, subtitle, onClose, children }: Props) {
  return (
    <div className="h-full w-full bg-white rounded-card shadow-card border border-rs-border flex flex-col overflow-hidden">
      <div className="drag-handle cursor-grab active:cursor-grabbing flex items-start justify-between px-4 py-3 border-b border-rs-border bg-rs-surface-2">
        <div className="min-w-0">
          <div className="font-semibold text-rs-ink truncate">{title}</div>
          {subtitle ? (
            <div className="text-xs text-rs-ink-3 truncate mt-0.5">{subtitle}</div>
          ) : null}
        </div>
        {onClose ? (
          <button
            type="button"
            onPointerDown={(e) => e.stopPropagation()}
            onClick={onClose}
            className="ml-2 text-rs-ink-3 hover:text-red-600 hover:bg-red-50 rounded-full w-7 h-7 flex items-center justify-center flex-shrink-0"
            aria-label="Close card"
          >
            ✕
          </button>
        ) : null}
      </div>
      <div className="flex-1 overflow-auto p-4">{children}</div>
    </div>
  );
}
