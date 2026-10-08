from app.services.chunker import ImportRef
from app.services.graph import resolve_js, resolve_python

KNOWN = {"api/payments/charge.py", "api/utils/retry.py", "api/utils/__init__.py", "src/lib/a.ts",
         "src/lib/b/index.ts", "src/app.tsx"}


def test_python_absolute_relative_and_package():
    assert resolve_python("api/x.py", ImportRef("api.utils.retry"), KNOWN) == ["api/utils/retry.py"]
    assert resolve_python("api/payments/charge.py", ImportRef("utils.retry", 2), KNOWN) == ["api/utils/retry.py"]
    assert resolve_python("api/payments/charge.py", ImportRef("", 2, ["utils"]), KNOWN) == ["api/utils/__init__.py"]
    assert resolve_python("a.py", ImportRef("os"), KNOWN) == []


def test_python_src_layout_suffix_match():
    assert resolve_python("tests/t.py", ImportRef("utils.retry"), {"api/utils/retry.py"}) == ["api/utils/retry.py"]


def test_js_relative_index_alias_and_packages():
    assert resolve_js("src/app.tsx", "./lib/a", KNOWN) == ["src/lib/a.ts"]
    assert resolve_js("src/app.tsx", "./lib/b", KNOWN) == ["src/lib/b/index.ts"]
    assert resolve_js("src/lib/a.ts", "@/app", KNOWN) == ["src/app.tsx"]
    assert resolve_js("src/app.tsx", "react", KNOWN) == []
