from pathlib import Path

import pytest

from codesearch_gym.fixtures import (
    FIXTURES,
    FixtureCorpus,
    materialize_corpus,
    materialize_all_fixtures,
    cleanup_fixtures,
    get_corpus_path,
)


def test_all_fixtures_defined():
    assert FIXTURES and all(isinstance(c, FixtureCorpus) for c in FIXTURES)


def test_corpus_names_unique():
    names = [c.name for c in FIXTURES]
    assert len(names) == len(set(names))


def test_corpus_files_nonempty():
    for c in FIXTURES:
        assert c.files
        for k, v in c.files.items():
            assert isinstance(k, str) and isinstance(v, str) and v.strip() != ""


def test_materialize_corpus_creates_files(tmp_path: Path):
    corpus = FIXTURES[0]
    root = materialize_corpus(corpus, tmp_path)
    for rel in corpus.files.keys():
        assert (root / rel).exists()


def test_materialize_all_and_cleanup(tmp_path: Path):
    roots = materialize_all_fixtures(tmp_path)
    assert roots and all(Path(p).exists() for p in roots.values())
    cleanup_fixtures(tmp_path)
    assert not Path(tmp_path).exists()


def test_get_corpus_path_returns_absolute(tmp_path: Path):
    p = get_corpus_path("react_hooks", tmp_path)
    assert p.is_absolute() and str(p).endswith("react_hooks")


def test_specific_patterns_present():
    react = next(c for c in FIXTURES if c.name == "react_hooks")
    assert "useEffect" in "\n".join(react.files.values())
    pyu = next(c for c in FIXTURES if c.name == "python_unicode")
    assert "café" in "\n".join(pyu.files.values())
    cc = next(c for c in FIXTURES if c.name == "c_printf")
    assert "printf(" in "\n".join(cc.files.values())
    ts = next(c for c in FIXTURES if c.name == "typescript_async")
    assert "async function" in ts.files["src/api.ts"]
