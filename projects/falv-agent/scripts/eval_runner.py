#!/usr/bin/env python3
"""
falv-agent 本地回归评测 harness。

当前版本只测试确定性环节，不调用 Anthropic API：
- pipeline.py detect 的合同类型、当事方、多方协议识别
- legal_coverage_check.py 的合同类型法条覆盖矩阵
- usage_log.py 的去敏使用日志
- render_report.py 的固定 issue list 输出

用法：
  python3 scripts/eval_runner.py
  python3 scripts/eval_runner.py --case barley_sha_founder_j
"""

import argparse
import importlib.util
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
LEGAL_CITATION_CHECK = ROOT / "scripts" / "legal_citation_check.py"
LEGAL_COVERAGE_CHECK = ROOT / "scripts" / "legal_coverage_check.py"
USAGE_LOG = ROOT / "scripts" / "usage_log.py"
BUNDLE_REVIEW = ROOT / "scripts" / "bundle_review.py"


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


def load_pipeline_module():
    spec = importlib.util.spec_from_file_location("falv_pipeline_eval", PIPELINE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 pipeline.py：{PIPELINE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def eval_citation_fixture() -> CaseResult:
    expectations = json.loads((FIXTURES_DIR / "citation_expectations.json").read_text(encoding="utf-8"))
    input_path = FIXTURES_DIR / expectations["input"]
    checks: list[CheckResult] = []
    result = run_json([sys.executable, str(LEGAL_CITATION_CHECK), "--input", str(input_path)])
    statuses = [item.get("status") for item in result.get("findings", [])]
    citations = [item.get("citation") for item in result.get("findings", [])]

    ok, details = contains_all(statuses, expectations.get("must_have_status", []))
    add_check(checks, "citation_statuses", ok, details)
    ok, details = contains_all(citations, expectations.get("must_include", []))
    add_check(checks, "citation_mentions", ok, details)
    return CaseResult(name="legal citation fixture", passed=all(c.passed for c in checks), checks=checks)


def eval_coverage_fixture() -> CaseResult:
    expectations = json.loads((FIXTURES_DIR / "coverage_expectations.json").read_text(encoding="utf-8"))
    checks: list[CheckResult] = []
    result = run_json([sys.executable, str(LEGAL_COVERAGE_CHECK)])
    results_by_type = {item.get("contract_type"): item for item in result.get("results", [])}
    pipeline = load_pipeline_module()
    investment_coverage = pipeline.load_legal_coverage("投资协议")
    investment_triggered = pipeline.load_legal_coverage(
        "投资协议",
        "本轮股权收购将导致控制权变更，投资人取得董事席位和一票否决权，并可能触发经营者集中申报。"
    )
    platform_triggered = pipeline.load_legal_coverage(
        "平台技术服务协议",
        "平台向商家提供API数据接口和技术服务，可能处理用户订单信息、手机号和地址；协议还包含排他合作、最低价和流量限制安排。"
    )

    add_check(
        checks,
        "coverage_matrix_ok",
        result.get("ok") is True,
        str(result),
    )
    add_check(
        checks,
        "coverage_contract_type_count",
        result.get("checked_contract_types", 0) >= expectations.get("min_contract_type_count", 0),
        f"got={result.get('checked_contract_types')} expected>={expectations.get('min_contract_type_count')}",
    )

    missing_types = [item for item in expectations.get("must_include_contract_types", []) if item not in results_by_type]
    add_check(
        checks,
        "coverage_must_include_types",
        not missing_types,
        "缺少：" + "、".join(missing_types) if missing_types else "",
    )

    incomplete = []
    for contract_type in expectations.get("must_have_full_required_coverage", []):
        item = results_by_type.get(contract_type, {})
        if item.get("coverage") != 1.0:
            incomplete.append(f"{contract_type}:{item.get('coverage')}")
    add_check(
        checks,
        "coverage_required_full",
        not incomplete,
        "未满覆盖：" + "、".join(incomplete) if incomplete else "",
    )
    add_check(
        checks,
        "pipeline_legal_coverage_context",
        investment_coverage.get("status") == "matched"
        and investment_coverage.get("contract_type") == "投资协议"
        and "company_law_84" in investment_coverage.get("required_citation_ids", []),
        str(investment_coverage),
    )
    investment_topic_ids = [item.get("id") for item in investment_triggered.get("active_review_topics", [])]
    platform_topic_ids = [item.get("id") for item in platform_triggered.get("active_review_topics", [])]
    add_check(
        checks,
        "coverage_investment_topic_activation",
        "investment_antitrust_concentration" in investment_topic_ids,
        str(investment_triggered.get("active_review_topics", [])),
    )
    add_check(
        checks,
        "coverage_platform_topic_activation",
        "platform_pipl_processing" in platform_topic_ids
        and "platform_antitrust_dominance" in platform_topic_ids,
        str(platform_triggered.get("active_review_topics", [])),
    )
    add_check(
        checks,
        "coverage_confirmation_questions",
        bool(investment_triggered.get("confirmation_questions"))
        and bool(platform_triggered.get("confirmation_questions")),
        str({
            "investment": investment_triggered.get("confirmation_questions"),
            "platform": platform_triggered.get("confirmation_questions"),
        }),
    )

    return CaseResult(name="legal coverage fixture", passed=all(c.passed for c in checks), checks=checks)


def eval_usage_log_fixture() -> CaseResult:
    checks: list[CheckResult] = []
    pipeline = load_pipeline_module()
    source = json.loads((FIXTURES_DIR / "sample_pipeline_result.json").read_text(encoding="utf-8"))
    source["legal_coverage"] = pipeline.load_legal_coverage(source.get("contract_type", "通用"))

    with tempfile.TemporaryDirectory(prefix="falv-usage-eval-") as tmpdir:
        tmpdir_path = Path(tmpdir)
        analysis_path = tmpdir_path / "analysis.json"
        contract_path = tmpdir_path / "contract.txt"
        log_path = tmpdir_path / "usage_events.jsonl"
        analysis_path.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")
        contract_path.write_text("本文件仅用于 eval hash，不应写入 usage log。", encoding="utf-8")

        run_json([
            sys.executable, str(USAGE_LOG), "record",
            "--analysis", str(analysis_path),
            "--contract", str(contract_path),
            "--log", str(log_path),
        ])
        report = run_json([sys.executable, str(USAGE_LOG), "report", "--log", str(log_path)])
        raw_log = log_path.read_text(encoding="utf-8")

    add_check(checks, "usage_event_count", report.get("event_count") == 1, str(report))
    add_check(
        checks,
        "usage_contract_type_count",
        report.get("contract_type_counts", {}).get("投资协议") == 1,
        str(report.get("contract_type_counts")),
    )
    add_check(
        checks,
        "usage_no_contract_text",
        "本文件仅用于 eval hash" not in raw_log,
        "usage log 不应包含合同正文",
    )
    add_check(
        checks,
        "usage_problematic_citation",
        report.get("problematic_status_counts", {}).get("deprecated", 0) >= 1,
        str(report.get("problematic_status_counts")),
    )

    return CaseResult(name="usage log fixture", passed=all(c.passed for c in checks), checks=checks)


def eval_bundle_fixture() -> CaseResult:
    checks: list[CheckResult] = []
    bundle_dir = CASES_DIR / "investment_bundle"
    result = run_json([sys.executable, str(BUNDLE_REVIEW), str(bundle_dir)])
    roles = [item.get("role") for item in result.get("documents", [])]
    triggered = [
        item.get("id")
        for item in result.get("cross_file_checks", [])
        if item.get("status") == "triggered"
    ]
    missing = [item.get("role") for item in result.get("missing_expected_documents", [])]

    add_check(
        checks,
        "bundle_transaction_type",
        result.get("transaction_type") == "投资交易包",
        str(result),
    )
    add_check(
        checks,
        "bundle_roles",
        "股东协议/SHA" in roles
        and "投资协议/认购协议" in roles
        and "公司章程" in roles,
        str(roles),
    )
    add_check(
        checks,
        "bundle_cross_file_checks",
        "governance_vs_articles" in triggered
        and "closing_conditions_vs_main_agreement" in triggered,
        str(triggered),
    )
    add_check(
        checks,
        "bundle_missing_expected_documents",
        "披露函/披露清单" in missing,
        str(missing),
    )
    return CaseResult(name="transaction bundle fixture", passed=all(c.passed for c in checks), checks=checks)


def eval_risk_calibration_fixture() -> CaseResult:
    checks: list[CheckResult] = []
    pipeline = load_pipeline_module()
    coverage = pipeline.load_legal_coverage(
        "投资协议",
        "本轮股权收购涉及取得控制权、决定性影响、经营者集中申报和交割条件。"
    )
    major = pipeline.calibrate_risk_level(55, coverage, [])
    ordinary = pipeline.calibrate_risk_level(55, {"active_review_topics": [], "confirmation_questions": []}, [])
    add_check(
        checks,
        "risk_major_factor_upgrade",
        major.get("final_level") == "重大风险" and major.get("major_factors"),
        str(major),
    )
    add_check(
        checks,
        "risk_no_major_factor_downgrade",
        ordinary.get("final_level") == "中等风险"
        and ordinary.get("adjustment") == "downgraded_no_major_factor",
        str(ordinary),
    )
    return CaseResult(name="risk calibration fixture", passed=all(c.passed for c in checks), checks=checks)


def eval_citation_policy_fixture() -> CaseResult:
    checks: list[CheckResult] = []
    text = "重大风险：《民法典》第五百八十五条可能涉及违约金调整。"
    code, result = run_json_with_status([
        sys.executable,
        str(LEGAL_CITATION_CHECK),
        "--input",
        str(FIXTURES_DIR / "citation_check_input.txt"),
        "--pkulaw-policy",
        "local",
    ])
    add_check(
        checks,
        "citation_policy_local",
        code == 0 and result.get("knowledge_base", {}).get("pkulaw_policy") == "local",
        str(result),
    )
    module_spec = importlib.util.spec_from_file_location("falv_citation_eval", LEGAL_CITATION_CHECK)
    if module_spec is None or module_spec.loader is None:
        add_check(checks, "citation_policy_major_context", False, "无法加载 legal_citation_check.py")
    else:
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        add_check(
            checks,
            "citation_policy_major_context",
            module.is_major_context(text) is True
            and module.should_use_pkulaw("on-demand", "current", True) is True
            and module.should_use_pkulaw("local", "unknown", True) is False,
            "policy helpers failed",
        )
    return CaseResult(name="citation policy fixture", passed=all(c.passed for c in checks), checks=checks)


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
        results.append(eval_citation_fixture())
    results.append(eval_coverage_fixture())
    results.append(eval_usage_log_fixture())
    results.append(eval_bundle_fixture())
    results.append(eval_risk_calibration_fixture())
    results.append(eval_citation_policy_fixture())

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
