"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { act, useLoad } from "@/lib/hooks";

export default function ReportButton({ targetType, targetNo }: { targetType: "상품게시글" | "회원"; targetNo: number }) {
  const [open, setOpen] = useState(false);
  const { data: reasons } = useLoad<string[]>(open ? "/reports/reasons" : null);
  if (!open) return <button onClick={() => setOpen(true)}>{targetType === "회원" ? "회원 신고" : "게시글 신고"}</button>;
  return (
    <form
      className="box"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        act(
          () =>
            api("/reports", {
              method: "POST",
              body: { target_type: targetType, target_no: targetNo, reason_code: f.get("reason"), content: f.get("content") },
            }),
          () => {
            alert("신고가 접수되었습니다.");
            setOpen(false);
          },
        );
      }}
    >
      <b>{targetType} 신고</b>
      <select name="reason" required>
        {reasons?.map((r) => <option key={r}>{r}</option>)}
      </select>
      <textarea name="content" placeholder="신고 내용" required />
      <div className="row">
        <button type="submit">신고</button>
        <button type="button" onClick={() => setOpen(false)}>취소</button>
      </div>
    </form>
  );
}
