"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { api, dt } from "@/lib/api";
import { act, useLoad, useSession } from "@/lib/hooks";

type Room = {
  room_no: number;
  product_no: number;
  title: string;
  trade_status: string;
  room_status: string;
  seller_nickname: string;
  buyer_nickname: string;
  can_send: boolean;
  messages: { message_no: number; sender_no: number; sender_nickname: string; content: string; sent_at: string; read_at: string | null }[];
};

export default function ChatRoomPage() {
  const { id } = useParams<{ id: string }>();
  const session = useSession();
  const { data: room, error, reload } = useLoad<Room>(`/chats/${id}`);
  const bottom = useRef<HTMLDivElement>(null);

  // 데모라 웹소켓 대신 3초 폴링
  useEffect(() => {
    const t = setInterval(reload, 3000);
    return () => clearInterval(t);
  }, [reload]);
  useEffect(() => bottom.current?.scrollIntoView(), [room?.messages.length]);

  if (error) return <p className="error">{error}</p>;
  if (!room) return null;
  const me = session?.member.member_no;

  return (
    <>
      <h3>
        <Link href={`/products/${room.product_no}`}>{room.title}</Link> <span className="muted">[{room.trade_status}]</span>
      </h3>
      <p className="muted">
        판매자 {room.seller_nickname} · 구매자 {room.buyer_nickname} · 방 상태 {room.room_status}
      </p>
      <div className="chat">
        {room.messages.map((m) => (
          <div key={m.message_no} className={`msg ${m.sender_no === me ? "mine" : ""}`}>
            <div className="muted">{m.sender_nickname} · {dt(m.sent_at)} {m.sender_no === me && (m.read_at ? "읽음" : "안읽음")}</div>
            {m.content}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      {room.can_send ? (
        <form
          className="row"
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
          <input name="content" placeholder="메시지" required style={{ flex: 1 }} autoComplete="off" />
          <button>전송</button>
        </form>
      ) : (
        <p className="muted">메시지를 보낼 수 없는 채팅방입니다.</p>
      )}
    </>
  );
}
