export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Session = { token: string; member: { member_no: number; nickname: string; role: string } };

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem("session");
  return raw ? (JSON.parse(raw) as Session) : null;
}

export function setSession(s: Session | null) {
  if (s) localStorage.setItem("session", JSON.stringify(s));
  else localStorage.removeItem("session");
  window.dispatchEvent(new Event("session"));
}

export const isAdmin = (s: Session | null) => !!s && ["moderator", "staff", "root"].includes(s.member.role);

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getSession()?.token;
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.body instanceof FormData) body = opts.body;
  else if (opts.body !== undefined) {
    body = JSON.stringify(opts.body);
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(API_URL + path, { method: opts.method ?? "GET", headers, body });
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    if (res.status === 401 && token) setSession(null);
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail ?? res.statusText));
  }
  return data as T;
}

export const imageUrl = (path: string) => API_URL + path;
export const won = (n: number) => n.toLocaleString("ko-KR") + "원";
export const dt = (s?: string | null) => (s ? s.replace("T", " ").slice(0, 16) : "-");
