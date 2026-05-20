"use client";

import { useCallback, useEffect, useState } from "react";

import { createSession, deleteSession, listSessions } from "@/lib/api";
import type { SessionMeta } from "@/lib/types";

export function useSessions(activeThreadId: string | null) {
  const [sessions, setSessions] = useState<SessionMeta[]>([]);

  const refresh = useCallback(async () => {
    try {
      setSessions(await listSessions());
    } catch (e) {
      console.warn("listSessions failed", e);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, activeThreadId]);

  const newSession = useCallback(async () => {
    const s = await createSession();
    await refresh();
    return s.thread_id;
  }, [refresh]);

  const removeSession = useCallback(
    async (threadId: string) => {
      await deleteSession(threadId);
      await refresh();
    },
    [refresh]
  );

  return { sessions, newSession, removeSession, refresh };
}
