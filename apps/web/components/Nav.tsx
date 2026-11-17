"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { isAdmin, setSession } from "@/lib/api";
import { useSession } from "@/lib/hooks";

export default function Nav() {
  const session = useSession();
  const router = useRouter();
  return (
    <nav>
      <Link href="/">
        <b>중고마켓</b>
      </Link>
      {session ? (
        <>
          <Link href="/products/new">상품 등록</Link>
          <Link href="/chats">채팅</Link>
          <Link href="/me">내 정보</Link>
          {isAdmin(session) && <Link href="/admin">관리자</Link>}
          <span className="muted">
            {session.member.nickname} ({session.member.role})
          </span>
          <button
            onClick={() => {
              setSession(null);
              router.push("/");
            }}
          >
            로그아웃
          </button>
        </>
      ) : (
        <>
          <Link href="/login">로그인</Link>
          <Link href="/signup">회원가입</Link>
        </>
      )}
    </nav>
  );
}
