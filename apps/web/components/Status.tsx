/** 거래·게시글·계정 상태를 색 점과 함께 표시 (색은 globals.css 의 data-s 규칙) */
export default function Status({ value }: { value: string }) {
  return (
    <span className="status" data-s={value}>
      {value}
    </span>
  );
}
