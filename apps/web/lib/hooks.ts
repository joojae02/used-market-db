"use client";

import { useCallback, useEffect, useState, useSyncExternalStore } from "react";
import { api, getSession, Session } from "./api";

let cached: { raw: string | null; value: Session | null } = { raw: null, value: null };

function readSession(): Session | null {
  const raw = localStorage.getItem("session");
  if (raw !== cached.raw) cached = { raw, value: getSession() };
  return cached.value;
}

function subscribe(cb: () => void) {
  window.addEventListener("session", cb);
  window.addEventListener("storage", cb);
  return () => {
    window.removeEventListener("session", cb);
    window.removeEventListener("storage", cb);
  };
}

export function useSession() {
  return useSyncExternalStore(subscribe, readSession, () => null);
}

/** GET 요청 결과 + 에러 + 다시 불러오기 */
export function useLoad<T>(path: string | null) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const reload = useCallback(() => {
    if (!path) return;
    api<T>(path).then(
      (d) => {
        setData(d);
        setError(null);
      },
      (e: Error) => setError(e.message),
    );
  }, [path]);
  useEffect(reload, [reload]);
  return { data, error, reload };
}

/** 버튼 액션 실행 → 실패하면 alert, 성공하면 onDone */
export async function act(fn: () => Promise<unknown>, onDone?: () => void) {
  try {
    await fn();
    onDone?.();
  } catch (e) {
    alert((e as Error).message);
  }
}
