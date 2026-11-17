"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, Session, setSession } from "@/lib/api";
import { act } from "@/lib/hooks";

export default function LoginPage() {
  const router = useRouter();
  return (
    <div className="panel narrow">
      <h1>
        로그인
      </h1>
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
        <label className="field">
          닉네임
          <input name="nickname" autoComplete="username" required />
        </label>
        <label className="field">
          패스워드
          <input name="password" type="password" autoComplete="current-password" required />
        </label>
        <button className="primary">로그인</button>
      </form>
      <p className="muted" style={{ marginTop: 16 }}>
        계정이 없으면 <Link href="/signup">회원가입</Link>하세요. 데모 계정은 판매왕, 구매왕, 운영자, 슈퍼루트이고 비밀번호는 모두 1234예요.
      </p>
    </div>
  );
}
