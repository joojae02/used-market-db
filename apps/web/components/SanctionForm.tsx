"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { act } from "@/lib/hooks";

export default function SanctionForm({ memberNo, reportNo, onDone }: { memberNo: number; reportNo?: number; onDone: () => void }) {
  const [type, setType] = useState("경고");
  return (
    <form
      className="box"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        act(
          () =>
            api(`/admin/members/${memberNo}/sanctions`, {
              method: "POST",
              body: { sanction_type: type, reason: f.get("reason"), end_at: f.get("end_at") || null, report_no: reportNo ?? null },
            }),
          onDone,
        );
      }}
    >
      <b>회원 #{memberNo} 제재</b>
      <select value={type} onChange={(e) => setType(e.target.value)}>
        <option>경고</option>
        <option>일시정지</option>
        <option>영구정지</option>
      </select>
      {type === "일시정지" && (
        <label>
          종료예정일시 <input name="end_at" type="datetime-local" required />
        </label>
      )}
      <textarea name="reason" placeholder="제재 사유" required />
      <button>제재 적용</button>
    </form>
  );
}
