"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { act, useLoad } from "@/lib/hooks";

export default function ReportButton({ targetType, targetNo }: { targetType: "상품게시글" | "회원"; targetNo: number }) {
  const [open, setOpen] = useState(false);
  const { data: reasons } = useLoad<string[]>(open ? "/reports/reasons" : null);
  const label = targetType === "회원" ? "판매자 신고" : "게시글 신고";
  if (!open)
    return (
      <button className="danger" onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  return (
    <form
      className="box"
      style={{ flexBasis: "100%" }}
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
            alert("신고를 접수했어요. 처리 상태는 내 정보에서 볼 수 있어요.");
            setOpen(false);
          },
        );
      }}
    >
      <b>{label}</b>
      <label className="field">
        사유
        <select name="reason" required>
          {reasons?.map((r) => <option key={r}>{r}</option>)}
        </select>
      </label>
      <label className="field">
        내용
        <textarea name="content" placeholder="어떤 문제가 있었는지 적어주세요" required />
      </label>
      <div className="row">
        <button className="primary">신고하기</button>
        <button type="button" onClick={() => setOpen(false)}>취소</button>
      </div>
    </form>
  );
}
