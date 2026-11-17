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
      <Link href="/" className="wordmark">
        중고마켓
      </Link>
      <div className="nav-links">
        {session && <Link href="/products/new">판매하기</Link>}
        {session && <Link href="/chats">채팅</Link>}
        {session && <Link href="/me">내 정보</Link>}
        {isAdmin(session) && <Link href="/admin">운영 관리</Link>}
      </div>
      {session ? (
        <div className="row">
          <span className="whoami">{session.member.nickname}</span>
          <button
            onClick={() => {
              setSession(null);
              router.push("/");
            }}
          >
            로그아웃
          </button>
        </div>
      ) : (
        <div className="row">
          <Link href="/signup" className="button">
            회원가입
          </Link>
          <Link href="/login" className="button primary">
            로그인
          </Link>
        </div>
      )}
    </nav>
  );
}
