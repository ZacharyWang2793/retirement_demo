// SSE client wrapping @microsoft/fetch-event-source so we can POST a body
// (the standard EventSource constructor is GET-only).

import { fetchEventSource } from "@microsoft/fetch-event-source";

import type { AnyCard } from "./types";

export type ChatStreamEvent =
  | { type: "announcement"; text: string }
  | { type: "card"; card: AnyCard }
  | { type: "message"; text: string }
  | { type: "card_close"; card_id: string }
  | { type: "done" }
  | { type: "error"; message: string };

export type StreamHandler = (ev: ChatStreamEvent) => void;

export async function streamChat(
  threadId: string,
  text: string,
  customerId: string | null,
  onEvent: StreamHandler,
  signal?: AbortSignal
): Promise<void> {
  await fetchEventSource(`/api/chat/${threadId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, customer_id: customerId }),
    signal,
    onmessage(ev) {
      try {
        const data = ev.data ? JSON.parse(ev.data) : {};
        onEvent({ type: ev.event as ChatStreamEvent["type"], ...data } as ChatStreamEvent);
      } catch (e) {
        onEvent({ type: "error", message: `bad SSE payload: ${String(e)}` });
      }
    },
    onerror(err) {
      onEvent({ type: "error", message: String(err) });
      throw err; // stop retrying
    },
    openWhenHidden: true,
  });
}

export async function streamCardSubmit(
  threadId: string,
  submission: Record<string, unknown>,
  onEvent: StreamHandler,
  signal?: AbortSignal
): Promise<void> {
  await fetchEventSource(`/api/cards/${threadId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ submission }),
    signal,
    onmessage(ev) {
      try {
        const data = ev.data ? JSON.parse(ev.data) : {};
        onEvent({ type: ev.event as ChatStreamEvent["type"], ...data } as ChatStreamEvent);
      } catch (e) {
        onEvent({ type: "error", message: `bad SSE payload: ${String(e)}` });
      }
    },
    onerror(err) {
      onEvent({ type: "error", message: String(err) });
      throw err;
    },
    openWhenHidden: true,
  });
}
