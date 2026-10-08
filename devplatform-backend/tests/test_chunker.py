from app.services.chunker import chunk_text, parse_file

PY = '''import os
from .utils import helper
from pkg.sub import thing as t


@decorator
def top(a, b):
    """Add."""
    return a + b


class Service:
    """Does things."""

    def __init__(self):
        self.x = 1

    @staticmethod
    def run(y):
        return y * 2
'''

TS = '''import { a } from "./a";
import React from "react";
const lazy = () => import("./lazy");

export function greet(name: string): string {
  return `hi ${name}`;
}

export const add = (x: number, y: number) => {
  return x + y;
};

interface User { id: number }

export class Repo {
  find(id: number) {
    return id;
  }
  save() {}
}
'''


def by_name(chunks):
    return {c.name: c for c in chunks}


def test_python_chunks_and_exact_lines():
    pf = parse_file("pkg/mod.py", PY)
    c = by_name(pf.chunks)
    assert set(c) == {"top", "Service", "Service.__init__", "Service.run"}
    assert c["top"].kind == "function" and c["Service.run"].kind == "method"
    assert c["top"].start_line == 6  # decorator line is included
    lines = PY.split("\n")
    for ch in pf.chunks:  # citations must map back to the exact source lines
        assert ch.content == "\n".join(lines[ch.start_line - 1:ch.end_line])
    assert "def __init__" not in c["Service"].content  # class chunk is header only


def test_python_imports():
    refs = {(r.module, r.level, tuple(r.names)) for r in parse_file("pkg/mod.py", PY).imports}
    assert ("os", 0, ()) in refs
    assert ("utils", 1, ("helper",)) in refs
    assert ("pkg.sub", 0, ("thing",)) in refs


def test_typescript_chunks_and_imports():
    pf = parse_file("src/x.ts", TS)
    c = by_name(pf.chunks)
    assert {"greet", "add", "User", "Repo", "Repo.find", "Repo.save"} <= set(c)
    assert c["add"].kind == "function" and c["User"].kind == "interface"
    assert c["greet"].start_line == 5
    mods = {r.module for r in pf.imports}
    assert mods == {"./a", "react", "./lazy"}


def test_script_without_definitions_becomes_module_chunk():
    pf = parse_file("scripts/run.py", "print('hi')\nx = 1\n")
    assert [c.kind for c in pf.chunks] == ["module"]


def test_long_function_is_split_with_correct_lines():
    body = "\n".join(f"    x{i} = {i}" for i in range(400))
    src = f"def big():\n{body}\n"
    pf = parse_file("a.py", src, max_chars=800)
    assert len(pf.chunks) > 1
    lines = src.split("\n")
    for ch in pf.chunks:
        assert ch.content == "\n".join(lines[ch.start_line - 1:ch.end_line])


def test_chunk_text_splits_on_headings():
    md = "# Title\nintro\n\n## Auth\nuses JWT\n\n## Payments\nretries"
    cs = chunk_text("README.md", md)
    assert [c.name for c in cs] == ["Title", "Auth", "Payments"]
    assert cs[1].start_line == 4
