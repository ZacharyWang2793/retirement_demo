"use client";

import { useEffect, useState } from "react";

export function AgentReplyStrip({ reply }: { reply: string | null }) {
  const [opacity, setOpacity] = useState(1);

  useEffect(() => {
    if (!reply) return;
    setOpacity(1);
    const fade = setTimeout(() => setOpacity(0.4), 8000);
    return () => clearTimeout(fade);
  }, [reply]);

  if (!reply) {
    return <div className="h-6" />; // placeholder so layout doesn't jump
  }

  return (
    <div
      className="px-4 py-2 mb-2 max-w-2xl mx-auto text-sm text-rs-ink-2 bg-white rounded-full shadow-card border border-rs-border transition-opacity duration-700 truncate"
      style={{ opacity }}
      title={reply}
    >
      {reply}
    </div>
  );
}
