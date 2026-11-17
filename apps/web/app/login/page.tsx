"use client";

import { useRouter } from "next/navigation";
import { api, Session, setSession } from "@/lib/api";
import { act } from "@/lib/hooks";

export default function LoginPage() {
  const router = useRouter();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        act(
          () => api<Session>("/auth/login", { method: "POST", body: Object.fromEntries(f) }).then(setSession),
          () => router.push("/"),
        );
      }}
    >
      <h2>로그인</h2>
      <input name="nickname" placeholder="닉네임" required />
      <input name="password" type="password" placeholder="패스워드" required />
      <button>로그인</button>
      <p className="muted">데모 계정: root / mod / seller / buyer / buyer2 (비밀번호 1234)</p>
    </form>
  );
}
