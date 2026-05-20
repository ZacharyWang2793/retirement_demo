// Fetch wrappers for the FastAPI backend. The proxy in next.config.js forwards
// /api/* to localhost:8000/api/*, so these paths work in both dev and prod.

import type { SavedSessionState, SessionMeta } from "./types";

export async function fetchCustomer(): Promise<{
  customer: { id: string; first_name: string; last_name: string };
  balance: {
    total_balance: number;
    vested_balance: number;
    accounts: { plan_name: string; type: string; balance: number }[];
  } | null;
}> {
  const r = await fetch("/api/customer");
  if (!r.ok) throw new Error(`customer fetch failed: ${r.status}`);
  return r.json();
}

export async function listSessions(): Promise<SessionMeta[]> {
  const r = await fetch("/api/sessions");
  if (!r.ok) throw new Error(`list sessions failed: ${r.status}`);
  return r.json();
}

export async function createSession(): Promise<{ thread_id: string }> {
  const r = await fetch("/api/sessions", { method: "POST" });
  if (!r.ok) throw new Error(`create session failed: ${r.status}`);
  return r.json();
}

export async function getSessionState(threadId: string): Promise<SavedSessionState> {
  const r = await fetch(`/api/sessions/${threadId}/state`);
  if (!r.ok) throw new Error(`get session state failed: ${r.status}`);
  return r.json();
}

export async function saveSessionState(
  threadId: string,
  state: { title: string | null; cards: unknown[]; messages: unknown[] }
): Promise<void> {
  const r = await fetch(`/api/sessions/${threadId}/state`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(state),
  });
  if (!r.ok) throw new Error(`save session state failed: ${r.status}`);
}

export async function deleteSession(threadId: string): Promise<void> {
  const r = await fetch(`/api/sessions/${threadId}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`delete session failed: ${r.status}`);
}
