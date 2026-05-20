"use client";

import { useState } from "react";

type Props = {
  onSubmit: (text: string) => Promise<void> | void;
  disabled?: boolean;
};

export function ChatBar({ onSubmit, disabled }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || busy || disabled) return;
    setText("");
    setBusy(true);
    try {
      await onSubmit(trimmed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="max-w-2xl mx-auto flex items-center gap-2 bg-white border border-rs-border-strong rounded-full shadow-card px-3 py-2"
    >
      <input
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Ask about your retirement account…"
        disabled={disabled || busy}
        className="flex-1 outline-none bg-transparent px-3 py-2 text-sm text-rs-ink placeholder-rs-ink-3"
      />
      <button
        type="submit"
        disabled={disabled || busy || !text.trim()}
        className="bg-rs-primary hover:bg-rs-primary-dk disabled:bg-rs-border-strong text-white rounded-full px-4 py-2 text-sm font-medium transition-colors"
      >
        {busy ? "…" : "Send"}
      </button>
    </form>
  );
}
