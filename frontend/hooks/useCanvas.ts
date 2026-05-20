"use client";

// Central state for the canvas: cards + their grid positions, the rolling
// transcript, and the latest assistant reply shown above the chat bar.
// Persists to /api/sessions/:thread_id/state on every change (debounced).

import { useEffect, useMemo, useReducer, useRef } from "react";

import { saveSessionState } from "@/lib/api";
import { findNextFreeSlot, sizeFor } from "@/lib/layout";
import type { AnyCard, CanvasCard, CardLayout, SavedSessionState } from "@/lib/types";

type State = {
  threadId: string | null;
  title: string | null;
  cards: CanvasCard[];
  messages: { role: string; content: string }[];
  reply: string | null; // latest assistant message shown in strip
};

type Action =
  | { type: "init"; state: SavedSessionState }
  | { type: "reset"; threadId: string }
  | { type: "card_spawn"; card: AnyCard }
  | { type: "card_remove"; id: string }
  | { type: "card_move"; layouts: CardLayout[] }
  | { type: "message_user"; text: string }
  | { type: "message_assistant"; text: string }
  | { type: "set_reply"; text: string }
  | { type: "clear_reply" };

const initial: State = {
  threadId: null,
  title: null,
  cards: [],
  messages: [],
  reply: null,
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "init":
      return {
        threadId: action.state.thread_id,
        title: action.state.title,
        cards: action.state.cards ?? [],
        messages: action.state.messages ?? [],
        reply: null,
      };
    case "reset":
      return { ...initial, threadId: action.threadId };
    case "card_spawn": {
      const { w, h } = sizeFor(action.card.card_type);
      const slot = findNextFreeSlot(
        state.cards.map((c) => c.layout),
        w,
        h
      );
      const newCard: CanvasCard = {
        card: action.card,
        layout: { i: action.card.id, x: slot.x, y: slot.y, w, h },
      };
      return { ...state, cards: [...state.cards, newCard] };
    }
    case "card_remove":
      return { ...state, cards: state.cards.filter((c) => c.card.id !== action.id) };
    case "card_move": {
      const byId = new Map(action.layouts.map((l) => [l.i, l]));
      return {
        ...state,
        cards: state.cards.map((c) => {
          const next = byId.get(c.card.id);
          if (!next) return c;
          return { ...c, layout: { ...c.layout, x: next.x, y: next.y, w: next.w, h: next.h } };
        }),
      };
    }
    case "message_user":
      return { ...state, messages: [...state.messages, { role: "user", content: action.text }], reply: null };
    case "message_assistant":
      return {
        ...state,
        messages: [...state.messages, { role: "assistant", content: action.text }],
        reply: action.text,
      };
    case "set_reply":
      return { ...state, reply: action.text };
    case "clear_reply":
      return { ...state, reply: null };
  }
}

export function useCanvas() {
  const [state, dispatch] = useReducer(reducer, initial);
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced persistence — every state change schedules a save 400ms later.
  useEffect(() => {
    if (!state.threadId) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      saveSessionState(state.threadId!, {
        title: state.title,
        cards: state.cards,
        messages: state.messages,
      }).catch((err) => console.warn("save canvas state failed", err));
    }, 400);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [state.threadId, state.title, state.cards, state.messages]);

  const layouts = useMemo(() => state.cards.map((c) => c.layout), [state.cards]);

  return { state, dispatch, layouts };
}
