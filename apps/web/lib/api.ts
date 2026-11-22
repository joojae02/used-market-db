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

/** 서버가 보낸 detail 을 사람이 읽을 문장으로. 객체·배열을 JSON 그대로 띄우지 않는다. */
function errorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (typeof d === "string" ? d : d?.msg)).filter(Boolean);
    if (msgs.length) return msgs.join("\n");
  }
  if (status === 422) return "입력값을 다시 확인하세요.";
  if (status >= 500) return "서버 오류가 발생했어요. 잠시 후 다시 시도하세요.";
  return `요청을 처리하지 못했어요. (${status})`;
}

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
    throw new Error(errorMessage(data?.detail, res.status));
  }
  return data as T;
}

/** 로컬 저장은 API 기준 상대경로(/uploads/..), S3 저장은 전체 URL */
export const imageUrl = (path: string) => (/^https?:\/\//.test(path) ? path : API_URL + path);
export const won = (n: number) => n.toLocaleString("ko-KR") + "원";
export const dt = (s?: string | null) => (s ? s.replace("T", " ").slice(0, 16) : "-");
