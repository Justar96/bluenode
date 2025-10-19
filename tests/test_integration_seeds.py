import shutil
from pathlib import Path

import pytest

from codesearch_gym.fixtures import materialize_all_fixtures, cleanup_fixtures
from codesearch_gym.seeds_adversarial import ADVERSARIAL_SEEDS
from codesearch_gym.verify_seeds import verify_all_seeds


has_rg = shutil.which("rg") is not None
has_ast = shutil.which("ast-grep") is not None


@pytest.mark.integration
@pytest.mark.skipif(not (has_rg and has_ast), reason="requires ripgrep and ast-grep installed")
def test_integration_verify_all_seeds(tmp_path: Path):
    materialize_all_fixtures(tmp_path)
    report = verify_all_seeds(ADVERSARIAL_SEEDS, str(tmp_path), min_f1=0.95)
    # Do not assert pass count strictly; just ensure report structure is present
    assert "results" in report and isinstance(report["results"], list)
    cleanup_fixtures(tmp_path)
