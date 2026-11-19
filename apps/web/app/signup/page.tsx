"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { api } from "@/lib/api";
import { act } from "@/lib/hooks";

const LABELS = { nickname: "닉네임", email: "이메일", phone: "전화번호" } as const;
type Field = keyof typeof LABELS;

export default function SignupPage() {
  const router = useRouter();
  const form = useRef<HTMLFormElement>(null);
  const [checked, setChecked] = useState<Partial<Record<Field, boolean>>>({});

  // MEM-01 중복 확인: 닉네임·이메일·전화번호
  const check = () => {
    const f = new FormData(form.current!);
    const params = new URLSearchParams();
    for (const k of Object.keys(LABELS) as Field[]) if (f.get(k)) params.set(k, String(f.get(k)));
    if (![...params].length) return alert("닉네임, 이메일, 전화번호 중 하나 이상 입력하세요.");
    act(() => api<Partial<Record<Field, boolean>>>(`/auth/check?${params}`).then(setChecked));
  };

  const hint = (k: Field) =>
    checked[k] === undefined ? null : (
      <small className={checked[k] ? undefined : "error"}>{checked[k] ? "사용할 수 있어요" : `이미 사용 중인 ${LABELS[k]}${k === "phone" ? "예요" : "이에요"}`}</small>
    );

  return (
    <div className="panel narrow">
      <h1>
        회원가입
      </h1>
      <form
        ref={form}
        onChange={(e) => {
          // 값을 바꾸면 그 칸의 확인 결과는 무효
          const target: EventTarget = e.target;
          if (target instanceof HTMLInputElement && target.name in LABELS)
            setChecked((c) => ({ ...c, [target.name]: undefined }));
        }}
        onSubmit={(e) => {
          e.preventDefault();
          const body = Object.fromEntries([...new FormData(e.currentTarget)].filter(([, v]) => v !== ""));
          act(
            () => api("/auth/signup", { method: "POST", body }),
            () => {
              alert("가입했어요. 로그인하세요.");
              router.push("/login");
            },
          );
        }}
      >
        <label className="field">
          성명
          <input name="name" autoComplete="name" required />
        </label>
        <label className="field">
          닉네임 <small>로그인할 때 써요</small>
          <input name="nickname" autoComplete="username" required />
          {hint("nickname")}
        </label>
        <label className="field">
          전화번호
          <input
            name="phone"
            type="tel"
            placeholder="010-0000-0000"
            autoComplete="tel"
            pattern="01[0-9]-?[0-9]{3,4}-?[0-9]{4}"
            title="010-1234-5678 형식으로 입력하세요"
            onInvalid={(e) =>
              e.currentTarget.setCustomValidity(
                e.currentTarget.validity.patternMismatch ? "전화번호 형식이 올바르지 않아요. 예: 010-1234-5678" : "",
              )
            }
            onInput={(e) => e.currentTarget.setCustomValidity("")}
            required
          />
          {hint("phone")}
        </label>
        <label className="field">
          이메일 <small>탈퇴한 이메일로 가입하면 예전 계정이 다시 열려요</small>
          <input name="email" type="email" autoComplete="email" required />
          {hint("email")}
        </label>
        <div>
          <button type="button" onClick={check}>닉네임·이메일·전화번호 중복 확인</button>
        </div>
        <label className="field">
          패스워드
          <input name="password" type="password" autoComplete="new-password" required />
        </label>
        <label className="field">
          생년월일 <small>선택</small>
          <input name="birth_date" type="date" />
        </label>
        <label className="field">
          집주소 <small>선택</small>
          <input name="address" autoComplete="street-address" />
        </label>
        <button className="primary">가입하기</button>
      </form>
    </div>
  );
}
