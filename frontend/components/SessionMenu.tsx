"use client";

import { useState } from "react";

import type { SessionMeta } from "@/lib/types";

type Props = {
  sessions: SessionMeta[];
  activeId: string | null;
  onSelect: (threadId: string) => void;
  onNew: () => void;
};

export function SessionMenu({ sessions, activeId, onSelect, onNew }: Props) {
  const [open, setOpen] = useState(false);
  const active = sessions.find((s) => s.thread_id === activeId);

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="bg-white hover:bg-rs-surface-2 border border-rs-border rounded-full px-4 py-2 text-sm shadow-card text-rs-ink-2 hover:text-rs-ink"
      >
        {active?.title || "Untitled canvas"} ▾
      </button>
      {open ? (
        <div className="absolute right-0 mt-2 w-72 bg-white border border-rs-border rounded-card shadow-card overflow-hidden z-50">
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onNew();
            }}
            className="w-full text-left px-4 py-3 text-sm font-medium text-rs-ink hover:bg-rs-surface-2 border-b border-rs-border"
          >
            + New canvas
          </button>
          <div className="max-h-72 overflow-auto">
            {sessions.length === 0 ? (
              <div className="px-4 py-3 text-sm text-rs-ink-3">No saved canvases yet.</div>
            ) : (
              sessions.map((s) => (
                <button
                  key={s.thread_id}
                  type="button"
                  onClick={() => {
                    setOpen(false);
                    onSelect(s.thread_id);
                  }}
                  className={`w-full text-left px-4 py-2 text-sm truncate ${
                    s.thread_id === activeId
                      ? "bg-rs-yellow-lt text-rs-ink font-medium"
                      : "text-rs-ink-2 hover:bg-rs-surface-2"
                  }`}
                >
                  {s.title || "Untitled canvas"}
                </button>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
