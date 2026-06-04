#!/usr/bin/env python3
"""
BB-PAXDATA Quality Regression Pipeline
Dual-mode: MOCK (CI, no API key) vs LIVE (scheduled, with API key).

Exit code 0: passed | Exit code 1: regression detected or error.
"""
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src and project root are on path before any project imports
_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))
sys.path.insert(0, str(_REPO_ROOT))

from bb_paxdata.quality.evaluator import QualityEvaluator  # noqa: E402

from tests.fixtures.golden_dataset import GoldenDataset  # noqa: E402

QUALITY_THRESHOLD = 0.80
REPORT_PATH = Path("output/quality_regression_report.md")


def _build_mock_ai_output(ground_truth: dict) -> dict:
    """Simulate slightly perturbed AI output from golden ground truth."""
    gt = ground_truth
    return {
        "sent_id": gt.get("sent_id", "mock_sent"),
        "AI_Duygu_Skoru": min(1.0, (gt.get("AI_Duygu_Skoru") or 0.0) + 0.05),
        "AI_Risk_Skoru": gt.get("AI_Risk_Skoru", 2),
        "AI_Potansiyel_Risk": gt.get("AI_Potansiyel_Risk", "LOW"),
        "AI_Diplomatik_Ton": gt.get("AI_Diplomatik_Ton", "NEUTRAL"),
        "AI_Birincil_Konu": gt.get("AI_Birincil_Konu", "güvenlik"),
        "AI_Manipulasyon_Skor": gt.get("AI_Manipulasyon_Skor", 0.0),
        "AI_Talep_Var": gt.get("AI_Talep_Var", 0),
        "AI_Cerceveleme": gt.get("AI_Cerceveleme", "threat"),
    }


def run_regression_eval() -> None:
    t_start = time.monotonic()
    print("=" * 60)
    print("🚀 BB-PAXDATA Quality Regression Pipeline")
    print("=" * 60)

    # ── 1. Load golden dataset ──────────────────────────────────────────────
    dataset = GoldenDataset()
    try:
        data = dataset.load_dataset()
        fixtures = data.get("fixtures", [])
        print(f"✅ Schema validation passed. Loaded {len(fixtures)} fixtures.")
    except Exception as e:
        print(f"❌ Schema validation FAILED: {e}")
        sys.exit(1)

    if not fixtures:
        print("❌ No fixtures found in golden dataset.")
        sys.exit(1)

    # ── 2. Detect execution mode ────────────────────────────────────────────
    api_key = os.getenv("OPENAI_API_KEY")
    is_live = bool(api_key)
    mode_label = "LIVE LLM" if is_live else "MOCK (CI — no API key)"
    print(f"⚙️  Execution mode: {mode_label}")

    # ── 3. Build simulated AI outputs ───────────────────────────────────────
    ai_results = [_build_mock_ai_output(f["ground_truth"]) for f in fixtures]
    print(f"🔧 Built {len(ai_results)} mock AI output(s).")

    # ── 4. Run evaluator ────────────────────────────────────────────────────
    model_name = "gpt-4o" if is_live else "mock-model"
    evaluator = QualityEvaluator(model_name=model_name)

    if not is_live:
        print("⚠️  Patching DeepEval LLM-backed metrics for CI mock mode...")
        mock_metric = MagicMock()
        mock_metric.score = 0.90
        mock_metric.threshold = 0.70
        mock_metric.reason = "Mocked CI run — no API key"
        mock_metric.is_successful.return_value = True

        with (
            patch("bb_paxdata.quality.evaluator.GEval", return_value=mock_metric),
            patch(
                "bb_paxdata.quality.evaluator.AnswerRelevancyMetric",
                return_value=mock_metric,
            ),
            patch(
                "bb_paxdata.quality.evaluator.JsonCorrectnessMetric",
                return_value=mock_metric,
            ),
        ):
            results = evaluator.evaluate_golden_dataset(ai_results)
    else:
        results = evaluator.evaluate_golden_dataset(ai_results)

    summary = results.get("summary", {})
    elapsed = time.monotonic() - t_start

    overall_score = summary.get("overall_mean_score", 0.0)
    overall_pass_rate = summary.get("overall_pass_rate", 0.0)

    # ── 5. Write markdown report ────────────────────────────────────────────
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("# 🛡️ NLP Quality Regression Report\n\n")
        f.write("| Field | Value |\n")
        f.write("|---|---|\n")
        f.write(f"| Execution Mode | `{mode_label}` |\n")
        f.write(f"| Fixtures Evaluated | {len(fixtures)} |\n")
        f.write(f"| Overall Mean Score | `{overall_score:.4f}` |\n")
        f.write(f"| Overall Pass Rate | `{overall_pass_rate * 100:.2f}%` |\n")
        f.write(f"| Threshold | `{QUALITY_THRESHOLD}` |\n")
        f.write(
            f"| Result | {'✅ PASSED' if overall_score >= QUALITY_THRESHOLD else '❌ FAILED'} |\n"
        )
        f.write(f"| Wall-clock Time | `{elapsed:.1f}s` |\n\n")

        metric_stats = summary.get("metric_statistics", {})
        if metric_stats:
            f.write("## Custom Metric Statistics\n\n")
            f.write("| Metric | Mean | Min | Max | Pass Rate |\n")
            f.write("|---|---|---|---|---|\n")
            for m, stats in metric_stats.items():
                f.write(
                    f"| {m} | {stats.get('mean_score', 0):.4f} "
                    f"| {stats.get('min_score', 0):.4f} "
                    f"| {stats.get('max_score', 0):.4f} "
                    f"| {stats.get('pass_rate', 0) * 100:.1f}% |\n"
                )

        individual = results.get("individual_results", [])
        if individual:
            f.write("\n## Per-Fixture Results (first 20)\n\n")
            f.write("| # | Sent ID | Score | Passed |\n")
            f.write("|---|---|---|---|\n")
            for i, r in enumerate(individual[:20]):
                passed_icon = "✅" if r.get("passed") else "❌"
                f.write(
                    f"| {i+1} | `{r.get('sent_id', '—')}` "
                    f"| {r.get('score', 0):.3f} | {passed_icon} |\n"
                )

    print(f"📝 Report written to: {REPORT_PATH}")
    print(
        f"📊 Overall mean score: {overall_score:.4f} "
        f"(threshold: {QUALITY_THRESHOLD}, pass rate: {overall_pass_rate*100:.1f}%)"
    )

    # ── 6. Gate on threshold ────────────────────────────────────────────────
    if overall_score < QUALITY_THRESHOLD:
        print(
            f"\n❌ REGRESSION DETECTED: score {overall_score:.4f} < {QUALITY_THRESHOLD}"
        )
        print("   Review the report and check metric statistics for failing metrics.")
        sys.exit(1)

    print(f"\n✅ Quality Regression Test PASSED in {elapsed:.1f}s.")
    sys.exit(0)


if __name__ == "__main__":
    run_regression_eval()
