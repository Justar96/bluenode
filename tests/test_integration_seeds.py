import shutil
from pathlib import Path

import pytest

from codesearch_gym.fixtures import cleanup_fixtures, materialize_all_fixtures
from codesearch_gym.seeds_adversarial import ADVERSARIAL_SEEDS
from codesearch_gym.verify_seeds import verify_all_seeds

has_rg = shutil.which("rg") is not None
has_ast = shutil.which("ast-grep") is not None


@pytest.mark.integration
@pytest.mark.skipif(not (has_rg and has_ast), reason="requires ripgrep and ast-grep installed")
def test_integration_verify_all_seeds(tmp_path: Path):
    materialize_all_fixtures(tmp_path)
    min_f1 = 0.95
    report = verify_all_seeds(ADVERSARIAL_SEEDS, str(tmp_path), min_f1=min_f1)
    # Verify report structure is present
    assert "results" in report and isinstance(report["results"], list)
    # Verify all seeds pass with the configured threshold
    assert (
        report["passed"] == report["total"]
    ), f"Expected all seeds to pass, but {report['failed']} failed"
    # Verify each seed meets the F1 threshold
    for res in report["results"]:  # type: ignore[union-attr]
        assert res["ok"], f"Seed {res['seed_id']} execution failed"
        assert res["span_f1"] >= min_f1, f"Seed {res['seed_id']} F1={res['span_f1']:.3f} < {min_f1}"
        assert res["file_iou"] >= 0.0, f"Seed {res['seed_id']} has invalid file_iou"
    cleanup_fixtures(tmp_path)
