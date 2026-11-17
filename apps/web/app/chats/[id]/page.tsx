"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";
import Status from "@/components/Status";
import { api, dt } from "@/lib/api";
import { act, useLoad, useSession } from "@/lib/hooks";

type Room = {
  room_no: number;
  product_no: number;
  title: string;
  trade_status: string;
  room_status: string;
  seller_no: number;
  seller_nickname: string;
  buyer_nickname: string;
  can_send: boolean;
  messages: { message_no: number; sender_no: number; sender_nickname: string; content: string; sent_at: string; read_at: string | null }[];
};

export default function ChatRoomPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession();
  const { data: room, error, reload } = useLoad<Room>(`/chats/${id}`);
  const list = useRef<HTMLDivElement>(null);

  // 데모라 웹소켓 대신 3초 폴링
  useEffect(() => {
    const t = setInterval(reload, 3000);
    return () => clearInterval(t);
  }, [reload]);
  useEffect(() => {
    const el = list.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [room?.messages.length]);

  if (error) return <p className="error">{error}</p>;
  if (!room) return null;
  const me = session?.member.member_no;
  const other = me === room.seller_no ? room.buyer_nickname : room.seller_nickname;

  return (
    <>
      <div className="room-head">
        <div>
          <h1>
            {other}
          </h1>
          <Link href={`/products/${room.product_no}`}>{room.title}</Link>
        </div>
        <Status value={room.trade_status} />
      </div>
      <div className="chat" ref={list} aria-live="polite">
        {room.messages.length === 0 && <p className="muted">첫 메시지를 보내보세요.</p>}
        {room.messages.map((m) => {
          const mine = m.sender_no === me;
          return (
            <div key={m.message_no} className={`msg${mine ? " mine" : ""}`}>
              <div className="msg-body">{m.content}</div>
              <div className="msg-meta">
                {dt(m.sent_at).slice(11)}
                {mine && !m.read_at && " 안 읽음"}
              </div>
            </div>
          );
        })}
      </div>
      {room.can_send ? (
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            const form = e.currentTarget;
            const content = new FormData(form).get("content");
            act(() => api(`/chats/${id}/messages`, { method: "POST", body: { content } }), () => {
              form.reset();
              reload();
            });
          }}
        >
          <input name="content" placeholder="메시지 보내기" aria-label="메시지" required autoComplete="off" />
          <button className="primary">보내기</button>
        </form>
      ) : (
        <p className="closed-note">
          {room.room_status === "비활성" ? "다른 구매자와 거래가 끝나서 대화가 닫혔어요." : "거래 완료 후 30일이 지나 대화가 닫혔어요."} 이전 대화는 계속 볼 수 있어요.
        </p>
      )}
    </>
  );
}
