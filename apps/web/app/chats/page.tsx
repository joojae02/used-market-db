"use client";

import Link from "next/link";
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
      <h2>채팅</h2>
      <table>
        <thead><tr><th>상품</th><th>상대</th><th>마지막 메시지</th><th>안 읽음</th></tr></thead>
        <tbody>
          {data?.map((r) => (
            <tr key={r.room_no}>
              <td>
                <Link href={`/chats/${r.room_no}`}>{r.title}</Link> <span className="muted">[{r.trade_status}]</span>
                {r.room_status === "비활성" && <span className="muted"> (비활성)</span>}
              </td>
              <td>{r.other_nickname}</td>
              <td>{r.last_message ?? "-"} <span className="muted">{dt(r.last_sent_at)}</span></td>
              <td>{r.unread || ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data?.length === 0 && <p className="muted">채팅방이 없습니다.</p>}
    </>
  );
}
