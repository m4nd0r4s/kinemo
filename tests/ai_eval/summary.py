"""Re-check every generated scene with `--strict` and summarize the AI eval."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def strict_ok(path: Path) -> tuple[bool, list[str]]:
    out = subprocess.run(
        [sys.executable, "-m", "kinemo.cli.main", "check", "--json", "--strict", str(path)],
        capture_output=True, text=True,
        encoding="utf-8",
    )
    try:
        report = json.loads(out.stdout)
    except json.JSONDecodeError:
        return False, ["load"]
    diags = report.get("diagnostics", []) + [d for sc in report.get("scenes", []) for d in sc["diagnostics"]]
    return out.returncode == 0, sorted({d["code"] for d in diags})


def main() -> int:
    prompts = [line.split("|")[0].strip() for line in (HERE / "prompts.txt").read_text(encoding="utf-8").splitlines() if line and not line.startswith("#")]
    recorded = {r["id"]: r for r in json.loads((HERE / "results.json").read_text(encoding="utf-8"))} if (HERE / "results.json").exists() else {}
    passed = 0
    for pid in prompts:
        path = HERE / "runs" / f"{pid}.py"
        ok, codes = strict_ok(path) if path.exists() else (False, ["missing"])
        iterations = recorded.get(pid, {}).get("iterations", "?")
        within = ok and (iterations == "?" or int(iterations) <= 2)
        passed += within
        print(f"{pid}  {'ok ' if within else 'FAIL'}  iterations={iterations}  {' '.join(codes)}")
    rate = passed / len(prompts)
    print(f"\n{passed}/{len(prompts)} = {rate:.0%} (target ≥ 90%)")
    return 0 if rate >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
