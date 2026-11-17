"use client";

import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { act } from "@/lib/hooks";

export default function SignupPage() {
  const router = useRouter();
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const body = Object.fromEntries(
          [...new FormData(e.currentTarget)].filter(([, v]) => v !== ""),
        );
        act(
          () => api<{ rejoined: boolean }>("/auth/signup", { method: "POST", body }),
          () => {
            alert("가입이 완료되었습니다. 로그인하세요.");
            router.push("/login");
          },
        );
      }}
    >
      <h2>회원가입</h2>
      <input name="name" placeholder="성명 *" required />
      <input name="nickname" placeholder="닉네임 * (로그인 ID)" required />
      <input name="phone" placeholder="전화번호 * 010-0000-0000" required />
      <input name="email" type="email" placeholder="이메일 *" required />
      <input name="password" type="password" placeholder="패스워드 *" required />
      <label>
        생년월일 <input name="birth_date" type="date" />
      </label>
      <input name="address" placeholder="집주소" />
      <button>가입</button>
      <p className="muted">탈퇴한 이메일로 가입하면 기존 계정이 재활성화됩니다.</p>
    </form>
  );
}
