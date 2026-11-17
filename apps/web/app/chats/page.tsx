"use client";

import Link from "next/link";
import Status from "@/components/Status";
import { dt } from "@/lib/api";
import { useLoad } from "@/lib/hooks";

type Room = {
  room_no: number;
  title: string;
  trade_status: string;
  room_status: string;
  other_nickname: string;
  last_message: string | null;
  last_sent_at: string | null;
  unread: number;
};

export default function ChatsPage() {
  const { data, error } = useLoad<Room[]>("/chats");
  if (error) return <p className="error">{error}</p>;
  return (
    <>
      <div className="page-head">
        <h1>
          채팅
        </h1>
      </div>
      {data?.length === 0 ? (
        <div className="empty">
          <p>아직 대화가 없어요. 마음에 드는 물건의 상세 화면에서 판매자에게 말을 걸어보세요.</p>
          <Link href="/" className="button">물건 둘러보기</Link>
        </div>
      ) : (
        <ul className="room-list">
          {data?.map((r) => (
            <li key={r.room_no} className={r.room_status === "비활성" ? "inactive" : undefined}>
              <Link href={`/chats/${r.room_no}`}>
                <span className="room-title">
                  {r.other_nickname} <span className="muted">{r.title}</span>
                </span>
                <span className="room-last">{r.last_message ?? "아직 메시지가 없어요"}</span>
                <span className="room-side">
                  <span>{dt(r.last_sent_at)}</span>
                  {r.unread > 0 ? <span className="unread" aria-label={`안 읽은 메시지 ${r.unread}개`}>{r.unread}</span> : <Status value={r.trade_status} />}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
