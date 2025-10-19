import re

from codesearch_gym.blueprints import validate_blueprint
from codesearch_gym.runner import Finding, validate_pcre2_requirement
from codesearch_gym.seeds_adversarial import ADVERSARIAL_SEEDS, get_seed_by_id


def test_adversarial_seeds_defined():
    assert len(ADVERSARIAL_SEEDS) >= 7


def test_seed_ids_unique_and_format():
    ids = [s.id for s in ADVERSARIAL_SEEDS]
    assert len(ids) == len(set(ids))
    for i in ids:
        assert re.match(r"seed_\d{3}_[a-z0-9_]+", i)


def test_all_seeds_validate_and_have_gt():
    for s in ADVERSARIAL_SEEDS:
        ok, err = validate_blueprint(s)
        assert ok, err
        assert s.ground_truth and all(isinstance(g, Finding) for g in s.ground_truth)


def test_specific_flags_and_tools():
    mp = {s.id: s for s in ADVERSARIAL_SEEDS}
    assert mp["seed_001_useeffect_ast"].tool == "ast_grep_search"
    assert mp["seed_002_todo_text"].tool == "ripgrep_search"
    assert mp["seed_003_pcre2_lookbehind"].arguments.get("pcre2") is True
    assert mp["seed_008_pcre2_backref"].arguments.get("pcre2") is True
    assert "file_types" in mp["seed_004_type_filter_c"].arguments


def test_pcre2_requirement_detection():
    mp = {s.id: s for s in ADVERSARIAL_SEEDS}
    req, _ = validate_pcre2_requirement(mp["seed_003_pcre2_lookbehind"].arguments["pattern"])
    assert req
    req2, _ = validate_pcre2_requirement(mp["seed_008_pcre2_backref"].arguments["pattern"])
    assert req2


def test_get_seed_by_id_found_and_missing():
    s = get_seed_by_id(ADVERSARIAL_SEEDS[0].id)
    assert s is not None and s.id == ADVERSARIAL_SEEDS[0].id
    assert get_seed_by_id("seed_000_missing") is None
