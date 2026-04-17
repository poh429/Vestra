import shutil
from pathlib import Path
from uuid import uuid4

from widget.agent.coverage_workspace import CoverageWorkspace
from widget.agent.models import NumericFact, TargetSpec


def _local_tmp_dir() -> Path:
    path = Path("tests/.tmp") / f"coverage_workspace_{uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_coverage_workspace_roundtrip_target_narrative_and_report():
    tmp_dir = _local_tmp_dir()
    workspace = CoverageWorkspace(tmp_dir / "coverage")
    target_spec = TargetSpec(
        symbol="2330.TW",
        thesis_type="industry_recovery",
        top_question="景氣修復是否已進入可驗證階段？",
        key_numeric_facts=[
            NumericFact(
                name="inventory",
                value=119.9,
                unit="B USD",
                as_of="2026-04-17",
                source_label="SEC",
                source_field="InventoryNet",
            )
        ],
    )

    try:
        workspace.save_target_spec(target_spec)
        workspace.save_narrative("2330.TW", {"market_consensus": ["市場仍偏保守。"]})
        workspace.save_tree("2330.TW", {"root_question": "景氣修復是否已進入可驗證階段？"})
        workspace.save_report("2330.TW", "# Coverage memo")

        restored_target = workspace.load_target_spec("2330.TW")
        restored_narrative = workspace.load_narrative("2330.TW")
        restored_tree = workspace.load_tree("2330.TW")
        restored_report = workspace.load_report("2330.TW")

        assert restored_target is not None
        assert restored_target.key_numeric_facts[0].source_field == "InventoryNet"
        assert restored_narrative == {"market_consensus": ["市場仍偏保守。"]}
        assert restored_tree == {"root_question": "景氣修復是否已進入可驗證階段？"}
        assert restored_report == "# Coverage memo"
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

