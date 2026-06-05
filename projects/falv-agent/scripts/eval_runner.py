#!/usr/bin/env python3
"""
falv-agent 本地回归评测 harness。

当前版本只测试确定性环节，不调用 Anthropic API：
- pipeline.py detect 的合同类型、当事方、多方协议识别
- render_report.py 的固定 issue list 输出

用法：
  python3 scripts/eval_runner.py
  python3 scripts/eval_runner.py --case barley_sha_founder_j
"""

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parents[1]
CASES_DIR = ROOT / "evals" / "cases"
FIXTURES_DIR = ROOT / "evals" / "fixtures"
PIPELINE = ROOT / "scripts" / "pipeline.py"
RENDER_REPORT = ROOT / "scripts" / "render_report.py"
SECURITY_PREFLIGHT = ROOT / "scripts" / "security_preflight.py"


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str = ""


@dataclass
class CaseResult:
    name: str
    passed: bool
    checks: list[CheckResult] = field(default_factory=list)


def run_json(cmd: list[str]) -> dict:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"命令失败：{' '.join(cmd)}\nSTDERR:\n{proc.stderr}\nSTDOUT:\n{proc.stdout}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"输出不是 JSON：{' '.join(cmd)}\n{proc.stdout}") from exc


def run_json_with_status(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(cmd, text=True, capture_output=True)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": proc.stdout, "stderr": proc.stderr}
    return proc.returncode, payload


def contains_all(haystack_values, needles: list[str]) -> tuple[bool, str]:
    haystack = "\n".join(str(v) for v in haystack_values)
    missing = [needle for needle in needles if needle not in haystack]
    return not missing, "缺少：" + "、".join(missing) if missing else ""


def add_check(checks: list[CheckResult], name: str, passed: bool, details: str = ""):
    checks.append(CheckResult(name=name, passed=passed, details=details))


def eval_detect_case(case_dir: Path) -> CaseResult:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    contract_path = case_dir / case["contract_path"]
    checks: list[CheckResult] = []

    detected = run_json([sys.executable, str(PIPELINE), "detect", "--contract", str(contract_path)])

    add_check(
        checks,
        "contract_type",
        detected.get("contract_type") == case.get("expected_contract_type"),
        f"got={detected.get('contract_type')} expected={case.get('expected_contract_type')}",
    )
    add_check(
        checks,
        "context_file",
        detected.get("context_file") == case.get("expected_context_file"),
        f"got={detected.get('context_file')} expected={case.get('expected_context_file')}",
    )
    add_check(
        checks,
        "confidence",
        detected.get("confidence") == case.get("expected_confidence"),
        f"got={detected.get('confidence')} expected={case.get('expected_confidence')}",
    )
    add_check(
        checks,
        "multipartite",
        detected.get("is_multipartite") == case.get("expected_multipartite"),
        f"got={detected.get('is_multipartite')} expected={case.get('expected_multipartite')}",
    )

    ok, details = contains_all(detected.get("identified_parties", []), case.get("must_identify_parties", []))
    add_check(checks, "identified_parties", ok, details)

    ok, details = contains_all(detected.get("available_parties", []), case.get("must_offer_party_options", []))
    add_check(checks, "available_parties", ok, details)

    ok, details = contains_all(detected.get("matched_keywords", []), case.get("must_match_keywords", []))
    add_check(checks, "matched_keywords", ok, details)

    for party in case.get("valid_party_examples", []):
        code, payload = run_json_with_status([
            sys.executable, str(PIPELINE), "validate-party",
            "--contract", str(contract_path),
            "--party", party,
        ])
        add_check(checks, f"valid_party:{party}", code == 0 and payload.get("valid") is True, str(payload))

    for party in case.get("invalid_party_examples", []):
        code, payload = run_json_with_status([
            sys.executable, str(PIPELINE), "validate-party",
            "--contract", str(contract_path),
            "--party", party,
        ])
        add_check(checks, f"invalid_party:{party}", code != 0 and payload.get("valid") is False, str(payload))

    if case.get("expected_preflight_level"):
        preflight = run_json([sys.executable, str(SECURITY_PREFLIGHT), "--contract", str(contract_path)])
        add_check(
            checks,
            "preflight_level",
            preflight.get("confidentiality_level") == case.get("expected_preflight_level"),
            f"got={preflight.get('confidentiality_level')} expected={case.get('expected_preflight_level')}",
        )
        ok, details = contains_all(
            [item.get("type") for item in preflight.get("sensitive_items", [])],
            case.get("must_detect_sensitive_types", []),
        )
        add_check(checks, "preflight_sensitive_types", ok, details)
        ok, details = contains_all(
            [item.get("category") for item in preflight.get("keyword_hits", [])],
            case.get("must_detect_keyword_categories", []),
        )
        add_check(checks, "preflight_keyword_categories", ok, details)

    return CaseResult(
        name=case.get("name", case_dir.name),
        passed=all(c.passed for c in checks),
        checks=checks,
    )


def eval_render_fixture() -> CaseResult:
    expectations = json.loads((FIXTURES_DIR / "render_expectations.json").read_text(encoding="utf-8"))
    input_path = FIXTURES_DIR / expectations["input"]
    checks: list[CheckResult] = []

    with tempfile.TemporaryDirectory(prefix="falv-eval-") as tmpdir:
        output_path = Path(tmpdir) / "report.md"
        run_json([sys.executable, str(RENDER_REPORT), "--input", str(input_path), "--output", str(output_path)])
        text = output_path.read_text(encoding="utf-8")

    missing = [item for item in expectations.get("must_include", []) if item not in text]
    add_check(
        checks,
        "render_must_include",
        not missing,
        "缺少：" + "、".join(missing) if missing else "",
    )

    unexpected = [item for item in expectations.get("must_not_include", []) if item in text]
    add_check(
        checks,
        "render_must_not_include",
        not unexpected,
        "不应出现：" + "、".join(unexpected) if unexpected else "",
    )

    return CaseResult(name="render_report fixture", passed=all(c.passed for c in checks), checks=checks)


def discover_cases(case_filter: Optional[str]) -> list[Path]:
    case_dirs = sorted(path for path in CASES_DIR.iterdir() if (path / "case.json").exists())
    if case_filter:
        case_dirs = [path for path in case_dirs if path.name == case_filter or case_filter in path.name]
    return case_dirs


def print_result(result: CaseResult):
    status = "PASS" if result.passed else "FAIL"
    print(f"[{status}] {result.name}")
    for check in result.checks:
        check_status = "ok" if check.passed else "bad"
        detail = f" - {check.details}" if check.details and not check.passed else ""
        print(f"  {check_status} {check.name}{detail}")


def main():
    parser = argparse.ArgumentParser(description="运行 falv-agent 本地回归评测")
    parser.add_argument("--case", help="只运行名称匹配的 eval case")
    parser.add_argument("--json", action="store_true", help="输出 JSON 摘要")
    args = parser.parse_args()

    results: list[CaseResult] = []
    for case_dir in discover_cases(args.case):
        results.append(eval_detect_case(case_dir))
    if not args.case:
        results.append(eval_render_fixture())

    if args.json:
        payload = {
            "passed": all(r.passed for r in results),
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "checks": [check.__dict__ for check in r.checks],
                }
                for r in results
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print_result(result)

    if not all(r.passed for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
