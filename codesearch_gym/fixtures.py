"""Fixture corpora materialization utilities.

Provides small multi-language corpora for testing adversarial cases.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(eq=True, frozen=True)
class FixtureCorpus:
    name: str
    description: str
    files: Dict[str, str]  # relative path -> content


def _react_hooks() -> FixtureCorpus:
    files = {
        "src/App.js": """
import React, { useEffect, useState } from 'react';
function App() {
  const [n, setN] = useState(0);
  useEffect(() => { console.log('mount'); }, []);
  return <div>{n}</div>;
}
export default App;
""".strip()
        ,
        "src/utils.js": """
// Utilities
// TODO: useEffect cleanup is needed
export function inc(x) { return x + 1; }
""".strip()
        ,
        "src/legacy.js": """
// Old-style class component
class Legacy { method() { return 1; } }
export { Legacy };
""".strip()
        ,
    }
    return FixtureCorpus(
        name="react_hooks",
        description="React project with useEffect and TODO in comments",
        files=files,
    )


def _typescript_async() -> FixtureCorpus:
    files = {
        "src/api.ts": """
export async function fetchUser(id: string) {
  const rows = await DB.query(`select * from users where id = ${id}`);
  return rows[0];
}
""".strip()
        ,
        "src/sync.ts": """
// this file mentions async but is not actually async
export function add(a: number, b: number) { return a + b; }
""".strip()
        ,
        "types/index.d.ts": """
declare const DB: { query(sql: string): Promise<any[]> };
export { DB };
""".strip()
        ,
    }
    return FixtureCorpus(
        name="typescript_async",
        description="TypeScript code with async function and DB.query",
        files=files,
    )


def _python_unicode() -> FixtureCorpus:
    files = {
        "app.py": """
# -*- coding: utf-8 -*-
def café():
    return 1

def cafe():
    return 2
""".strip()
        ,
        "utils.py": """
def deco(f):
    def w(*a, **k):
        return f(*a, **k)
    return w
""".strip()
        ,
        "test.py": """
def test_something():
    s = "TODO: nothing"
    assert True
""".strip()
        ,
    }
    return FixtureCorpus(
        name="python_unicode",
        description="Python with unicode identifier café and ascii cafe",
        files=files,
    )


def _go_printf() -> FixtureCorpus:
    files = {
        "main.go": """
package main

import "fmt"

func main() {
    fmt.Printf("hello %d", 1)
}
""".strip()
        ,
        "logger.go": """
package main

func Logf(s string) {}
""".strip()
        ,
        "utils.go": """
package main

func Add(a, b int) int { return a + b }
""".strip()
        ,
    }
    return FixtureCorpus(
        name="go_printf",
        description="Go code using fmt.Printf",
        files=files,
    )


def _c_printf() -> FixtureCorpus:
    files = {
        "main.c": """
#include <stdio.h>

int main() {
    printf("hello %d", 1);
    return 0;
}
""".strip()
        ,
        "utils.c": """
int add(int a, int b) { return a + b; }
""".strip()
        ,
        "logger.h": """
void logf(const char* s);
""".strip()
        ,
    }
    return FixtureCorpus(
        name="c_printf",
        description="C code using printf",
        files=files,
    )


def _rust_macros() -> FixtureCorpus:
    files = {
        "Cargo.toml": """
[package]
name = "sample"
version = "0.1.0"
edition = "2021"
""".strip()
        ,
        "src/main.rs": """
fn main() {
    println!("hello {}", 1);
}
""".strip()
        ,
        "src/lib.rs": """
#[allow(dead_code)]
pub fn add(a: i32, b: i32) -> i32 { a + b }
""".strip()
        ,
    }
    return FixtureCorpus(
        name="rust_macros",
        description="Rust project using println! macro",
        files=files,
    )


def _mixed_comments() -> FixtureCorpus:
    files = {
        "config.txt": "password=secret123\n",
        "text.txt": "This is the the sample.\n",
        "comments.js": """
// async should not be matched here
function real() { return 1 }
""".strip()
        ,
    }
    return FixtureCorpus(
        name="mixed_comments",
        description="Mixed files with passwords and duplicate words in text",
        files=files,
    )


FIXTURES: List[FixtureCorpus] = [
    _react_hooks(),
    _typescript_async(),
    _python_unicode(),
    _go_printf(),
    _c_printf(),
    _rust_macros(),
    _mixed_comments(),
]

DEFAULT_FIXTURES_DIR = "corpora_fixtures"


def materialize_corpus(corpus: FixtureCorpus, base_path: str | Path) -> Path:
    base = Path(base_path).absolute()
    root = base / corpus.name
    for rel, content in corpus.files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def materialize_all_fixtures(base_path: str | Path) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for c in FIXTURES:
        out[c.name] = materialize_corpus(c, base_path)
    return out


def cleanup_fixtures(base_path: str | Path) -> None:
    root = Path(base_path).absolute()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


def get_corpus_path(corpus_name: str, base_path: str | Path) -> Path:
    return (Path(base_path).absolute() / corpus_name).absolute()


__all__ = [
    "FixtureCorpus",
    "FIXTURES",
    "DEFAULT_FIXTURES_DIR",
    "materialize_corpus",
    "materialize_all_fixtures",
    "cleanup_fixtures",
    "get_corpus_path",
]
