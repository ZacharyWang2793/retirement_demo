"use client";

import { useEffect, useState } from "react";

import { AgentReplyStrip } from "@/components/AgentReplyStrip";
import { Canvas } from "@/components/Canvas";
import { ChatBar } from "@/components/ChatBar";
import { SessionMenu } from "@/components/SessionMenu";
import { useCanvas } from "@/hooks/useCanvas";
import { useSessions } from "@/hooks/useSessions";
import { fetchCustomer, getSessionState, createSession } from "@/lib/api";
import { streamCardSubmit, streamChat } from "@/lib/sse";

export default function Page() {
  const { state, dispatch } = useCanvas();
  const { sessions, newSession } = useSessions(state.threadId);
  const [customerName, setCustomerName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Bootstrap: load customer + decide which session to open.
  useEffect(() => {
    (async () => {
      try {
        const c = await fetchCustomer();
        setCustomerName(c.customer.first_name);
      } catch (e) {
        console.warn("customer load failed", e);
      }

      // Open the most-recent session if any, else create one.
      try {
        const r = await fetch("/api/sessions");
        const list = (await r.json()) as { thread_id: string; updated_at: string }[];
        if (list.length > 0) {
          const stateLoaded = await getSessionState(list[0].thread_id);
          dispatch({ type: "init", state: stateLoaded });
        } else {
          const s = await createSession();
          dispatch({ type: "reset", threadId: s.thread_id });
        }
      } catch (e) {
        console.warn("session bootstrap failed", e);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUserMessage(text: string) {
    if (!state.threadId) return;
    dispatch({ type: "message_user", text });
    setBusy(true);
    try {
      await streamChat(state.threadId, text, null, (ev) => {
        if (ev.type === "card") dispatch({ type: "card_spawn", card: ev.card });
        else if (ev.type === "announcement") dispatch({ type: "message_assistant", text: ev.text });
        else if (ev.type === "message") dispatch({ type: "message_assistant", text: ev.text });
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleCardSubmit(cardId: string, submission: Record<string, unknown>) {
    if (!state.threadId) return;
    // Optimistically remove the card; the next graph step will spawn a new one if there is one.
    dispatch({ type: "card_remove", id: cardId });
    setBusy(true);
    try {
      await streamCardSubmit(state.threadId, submission, (ev) => {
        if (ev.type === "card") dispatch({ type: "card_spawn", card: ev.card });
        else if (ev.type === "message" || ev.type === "announcement")
          dispatch({ type: "message_assistant", text: ev.text });
      });
    } finally {
      setBusy(false);
    }
  }

  async function handleSelectSession(threadId: string) {
    const loaded = await getSessionState(threadId);
    dispatch({ type: "init", state: loaded });
  }

  async function handleNewSession() {
    const newId = await newSession();
    dispatch({ type: "reset", threadId: newId });
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Top bar */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-rs-border bg-white">
        <div>
          <div className="font-semibold text-rs-ink">Meridian Retirement</div>
          {customerName ? (
            <div className="text-xs text-rs-ink-3">Hello, {customerName}</div>
          ) : null}
        </div>
        <SessionMenu
          sessions={sessions}
          activeId={state.threadId}
          onSelect={handleSelectSession}
          onNew={handleNewSession}
        />
      </div>

      {/* Canvas */}
      <div className="flex-1 relative">
        <Canvas
          cards={state.cards}
          onLayoutChange={(layouts) => dispatch({ type: "card_move", layouts })}
          onCardClose={(id) => dispatch({ type: "card_remove", id })}
          onCardSubmit={handleCardSubmit}
        />

        {/* Floating reply strip + chat bar */}
        <div className="absolute bottom-0 left-0 right-0 px-6 pb-4 pointer-events-none">
          <div className="pointer-events-auto">
            <AgentReplyStrip reply={state.reply} />
            <ChatBar onSubmit={handleUserMessage} disabled={busy || !state.threadId} />
          </div>
        </div>
      </div>
    </div>
  );
}
