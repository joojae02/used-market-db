"""Apply only the sanction-success feedback requested for the frontend.
Run from the repository root. Does not change document-related headings.
"""
from pathlib import Path

file = Path("apps/web/components/SanctionForm.tsx")
if not file.is_file():
    raise SystemExit("Repository root에서 실행하세요: apps/web/components/SanctionForm.tsx 없음")
s = file.read_text(encoding="utf-8")
old = "          onDone,\n"
new = """          () => {
            alert(`${type} 제재가 적용되었습니다.`);
            onDone();
          },
"""
if new in s:
    print("이미 적용된 수정입니다.")
elif s.count(old) == 1:
    file.write_text(s.replace(old, new), encoding="utf-8")
    print(f"수정 완료: {file}")
else:
    raise SystemExit("예상했던 SanctionForm.tsx와 코드가 달라 자동 수정하지 않았습니다.")
