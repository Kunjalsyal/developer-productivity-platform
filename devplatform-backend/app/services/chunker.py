"""AST-based chunking (tree-sitter) for Python / JavaScript / TypeScript, plus text chunking for docs."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import PurePosixPath

from tree_sitter import Language, Node, Parser

CODE_EXT = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
}
DOC_EXT = {".md", ".rst", ".txt"}
_LABEL = {"python": "python", "javascript": "javascript", "typescript": "typescript", "tsx": "typescript"}


def detect_language(path: str) -> str | None:
    return CODE_EXT.get(PurePosixPath(path).suffix.lower())


def language_label(lang: str) -> str:
    return _LABEL[lang]


@dataclass
class CodeChunk:
    file_path: str
    language: str
    name: str
    kind: str
    start_line: int  # 1-based, inclusive
    end_line: int
    content: str


@dataclass
class ImportRef:
    module: str
    level: int = 0  # python relative-import depth
    names: list[str] = field(default_factory=list)

    @property
    def raw(self) -> str:
        return "." * self.level + self.module


@dataclass
class ParsedFile:
    chunks: list[CodeChunk]
    imports: list[ImportRef]


@lru_cache(maxsize=None)
def _language(lang: str) -> Language:
    if lang == "python":
        import tree_sitter_python as m
        return Language(m.language())
    if lang == "javascript":
        import tree_sitter_javascript as m
        return Language(m.language())
    if lang == "typescript":
        import tree_sitter_typescript as m
        return Language(m.language_typescript())
    if lang == "tsx":
        import tree_sitter_typescript as m
        return Language(m.language_tsx())
    raise ValueError(f"unsupported language: {lang}")


def _t(src: bytes, node: Node | None) -> str:
    return src[node.start_byte:node.end_byte].decode("utf8", "replace") if node is not None else ""


def _mk(lines, path, lang, name, kind, start, end) -> CodeChunk:
    end = max(start, min(end, len(lines)))
    return CodeChunk(path, language_label(lang), name, kind, start, end, "\n".join(lines[start - 1:end]))


# ---------------------------------------------------------------- Python

def _py_def(n: Node) -> Node | None:
    if n.type == "decorated_definition":
        n = n.child_by_field_name("definition")
    return n if n is not None and n.type in ("function_definition", "class_definition") else None


def _python_chunks(root: Node, src: bytes, lines: list[str], path: str) -> list[CodeChunk]:
    out: list[CodeChunk] = []

    def handle(container: Node, scope: str, in_class: bool) -> None:
        for child in container.children:
            target = _py_def(child)
            if target is None:
                continue
            name = _t(src, target.child_by_field_name("name"))
            qual = f"{scope}.{name}" if scope else name
            start = child.start_point[0] + 1
            if target.type == "function_definition":
                kind = "method" if in_class else "function"
                out.append(_mk(lines, path, "python", qual, kind, start, child.end_point[0] + 1))
                continue
            body = target.child_by_field_name("body")
            first = next((m for m in body.children if _py_def(m)), None) if body is not None else None
            end = child.end_point[0] + 1 if first is None else max(start, first.start_point[0])
            out.append(_mk(lines, path, "python", qual, "class", start, end))
            if first is not None:
                handle(body, qual, True)

    handle(root, "", False)
    return out


def _python_imports(root: Node, src: bytes) -> list[ImportRef]:
    refs: list[ImportRef] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type == "import_statement":
            for c in n.children_by_field_name("name"):
                dn = c.child_by_field_name("name") if c.type == "aliased_import" else c
                refs.append(ImportRef(_t(src, dn)))
        elif n.type == "import_from_statement":
            text = _t(src, n.child_by_field_name("module_name"))
            module = text.lstrip(".")
            names = []
            for c in n.children_by_field_name("name"):
                dn = c.child_by_field_name("name") if c.type == "aliased_import" else c
                names.append(_t(src, dn))
            refs.append(ImportRef(module, len(text) - len(module), names))
        else:
            stack.extend(n.children)
    return refs


# ---------------------------------------------------------------- JS / TS

_JS_DEFS = {
    "function_declaration": "function", "generator_function_declaration": "function",
    "class_declaration": "class", "abstract_class_declaration": "class",
    "interface_declaration": "interface", "type_alias_declaration": "type", "enum_declaration": "enum",
}
_FN_VALUES = {"arrow_function", "function_expression", "function", "generator_function", "class"}


def _js_chunks(root: Node, src: bytes, lines: list[str], path: str, lang: str) -> list[CodeChunk]:
    out: list[CodeChunk] = []

    def emit(outer: Node, name: str, kind: str) -> None:
        out.append(_mk(lines, path, lang, name, kind, outer.start_point[0] + 1, outer.end_point[0] + 1))

    def emit_class(outer: Node, node: Node, name: str) -> None:
        body = node.child_by_field_name("body")
        methods = [m for m in (body.children if body is not None else []) if m.type == "method_definition"]
        start = outer.start_point[0] + 1
        if not methods:
            emit(outer, name, "class")
            return
        out.append(_mk(lines, path, lang, name, "class", start, max(start, methods[0].start_point[0])))
        for m in methods:
            mname = _t(src, m.child_by_field_name("name"))
            out.append(_mk(lines, path, lang, f"{name}.{mname}", "method",
                           m.start_point[0] + 1, m.end_point[0] + 1))

    for n in root.children:
        node = n
        if n.type == "export_statement":
            node = n.child_by_field_name("declaration")
            if node is None:
                val = n.child_by_field_name("value")
                if val is not None and val.type in _FN_VALUES:
                    emit(n, "default", "function")
                continue
        if node.type in _JS_DEFS:
            name = _t(src, node.child_by_field_name("name")) or "default"
            kind = _JS_DEFS[node.type]
            emit_class(n, node, name) if kind == "class" else emit(n, name, kind)
        elif node.type in ("lexical_declaration", "variable_declaration"):
            for d in node.named_children:
                if d.type != "variable_declarator":
                    continue
                val = d.child_by_field_name("value")
                if val is not None and val.type in _FN_VALUES:
                    emit(n, _t(src, d.child_by_field_name("name")), "function")
    return out


def _unquote(s: str) -> str:
    return s.strip().strip("'\"`")


def _js_imports(root: Node, src: bytes) -> list[ImportRef]:
    refs: list[ImportRef] = []
    stack = [root]
    while stack:
        n = stack.pop()
        if n.type in ("import_statement", "export_statement"):
            s = n.child_by_field_name("source")
            if s is not None:
                refs.append(ImportRef(_unquote(_t(src, s))))
            if n.type == "import_statement":
                continue
        elif n.type == "call_expression":
            fn, args = n.child_by_field_name("function"), n.child_by_field_name("arguments")
            if fn is not None and args is not None and (
                fn.type == "import" or (fn.type == "identifier" and _t(src, fn) == "require")
            ):
                first = next(iter(args.named_children), None)
                if first is not None and first.type == "string":
                    refs.append(ImportRef(_unquote(_t(src, first))))
        stack.extend(n.children)
    return refs


# ---------------------------------------------------------------- public API

def _windows(chunk: CodeChunk, max_chars: int) -> list[CodeChunk]:
    if len(chunk.content) <= max_chars:
        return [chunk]
    parts, buf, size, start = [], [], 0, chunk.start_line
    for i, line in enumerate(chunk.content.split("\n")):
        if buf and size + len(line) + 1 > max_chars:
            parts.append((start, buf))
            buf, size, start = [], 0, chunk.start_line + i
        buf.append(line)
        size += len(line) + 1
    parts.append((start, buf))
    return [
        CodeChunk(chunk.file_path, chunk.language, f"{chunk.name} (part {k})", chunk.kind,
                  s, s + len(b) - 1, "\n".join(b))
        for k, (s, b) in enumerate(parts, 1)
    ]


def parse_file(path: str, content: str, max_chars: int = 6000) -> ParsedFile:
    lang = detect_language(path)
    if lang is None:
        raise ValueError(f"unsupported file type: {path}")
    src = content.encode("utf8")
    root = Parser(_language(lang)).parse(src).root_node
    lines = content.split("\n")
    if lang == "python":
        chunks, imports = _python_chunks(root, src, lines, path), _python_imports(root, src)
    else:
        chunks, imports = _js_chunks(root, src, lines, path, lang), _js_imports(root, src)
    if not chunks and content.strip():  # scripts / config files with no definitions
        chunks = [_mk(lines, path, lang, PurePosixPath(path).name, "module", 1, len(lines))]
    return ParsedFile([w for c in chunks for w in _windows(c, max_chars)], imports)


def chunk_text(path: str, text: str, max_chars: int = 1200, title: str | None = None) -> list[CodeChunk]:
    """Split prose (Markdown / Notion text) on headings, then by size. Lines are 1-based."""
    lines = text.split("\n")
    heading = title or PurePosixPath(path).name
    chunks: list[CodeChunk] = []
    buf: list[str] = []
    start, size = 1, 0

    def flush(end: int) -> None:
        nonlocal buf, size
        if "\n".join(buf).strip():
            chunks.append(CodeChunk(path, "text", heading, "doc", start, max(start, end), "\n".join(buf)))
        buf, size = [], 0

    for i, line in enumerate(lines, 1):
        if line.startswith("#"):
            flush(i - 1)
            heading = line.lstrip("#").strip() or heading
        elif buf and size + len(line) + 1 > max_chars:
            flush(i - 1)
        if not buf:
            start = i
        buf.append(line)
        size += len(line) + 1
    flush(len(lines))
    return chunks
