"""Offline packaging/safety smoke test; never opens any network connections."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
assert (root / "benchmark" / "run.py").is_file()
assert (root / "benchmark" / "deep_suite.py").is_file()
assert (root / "benchmark" / "compose.yml").is_file()
assert (root / "patch_sanction.py").is_file()

for script in ("benchmark/run.py", "benchmark/deep_suite.py", "patch_sanction.py"):
    ast.parse((root / script).read_text(encoding="utf-8"), filename=script)

compose = (root / "benchmark/compose.yml").read_text(encoding="utf-8")
runner = (root / "benchmark/run.py").read_text(encoding="utf-8")
assert 'DB_HOST: db' in compose
assert 'S3_BUCKET: ""' in compose
assert '127.0.0.1:18080:8000' in compose
assert 'MYSQL_ROOT_PASSWORD: "benchmark-local-only"' in compose
assert not re.search(r'(?m)^\s*[- ]*"?3306:3306', compose), "MySQL host port must stay private"
assert 'def assert_isolated_compose()' in runner
assert 'localhost port' in runner
assert 'BASE = "http://127.0.0.1:18080"' in runner
assert '5_000_000' not in runner

# Test the patch on a tiny fixture, without requiring any live code or Git checkout.
with tempfile.TemporaryDirectory() as td:
    work = Path(td)
    target = work / "apps/web/components/SanctionForm.tsx"
    target.parent.mkdir(parents=True)
    target.write_text('before\n          onDone,\nafter\n', encoding='utf-8')
    patch = root / 'patch_sanction.py'
    for run in range(2):
        result = subprocess.run([sys.executable, str(patch)], cwd=work, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr or result.stdout
    patched = target.read_text(encoding='utf-8')
    assert patched.count('alert(`${type} 제재가 적용되었습니다.`);') == 1
    assert 'onDone();' in patched

# Regression: a long prefix near the 30-character DB limit must still generate
# a valid nickname even after thousands of generated case identities.
sys.path.insert(0, str(root / "benchmark"))
from run import Bench  # noqa: E402
bench = Bench(260222, 5000, 12, True)
for prefix in ("racereporttarget", "racesanctiontarget", "timezoneprobe", "x" * 64):
    for serial in (10, 999, 1000, 6000, 12000):
        bench.serial = serial - 1
        nick = bench.identity(prefix)["nickname"]
        assert len(nick) <= 30, (prefix, serial, len(nick))

print('PASS: 파일 구성, Python 구문, 격리 설정, 패치 멱등성 정적 검사')
print('NOTICE: Docker 통합 테스트는 실행하지 않았습니다.')
