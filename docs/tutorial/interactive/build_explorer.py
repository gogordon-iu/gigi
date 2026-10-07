"""Build the interactive Gigi codebase explorer (docs/tutorial/gigi_explorer.html).

The explorer is a single self-contained HTML file (no internet / server needed)
with two linked views:

  * Code Map        - zoomable map of every package, file, class and function in
                      src/gigi, generated from the source code with ``ast``.
  * Story Game Flow - drill-down walkthrough of the Story Game activity
                      (phases -> sequence diagram -> individual call + source).

Usage (from the repository root)::

    python docs/tutorial/interactive/build_explorer.py

Re-run it whenever the code or ``story_flow.json`` changes. Code references in
``story_flow.json`` ("core/robot.py:Character.run_character") are resolved to
line numbers at build time; unresolved references are reported as warnings.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SRC = REPO / "src" / "gigi"
TEMPLATE = HERE / "explorer_template.html"
FLOW = HERE / "story_flow.json"
OUT = HERE.parent / "gigi_explorer.html"

# One-line descriptions of each package (shown in the map and side panel).
PACKAGE_INFO = {
    "": "The gigi Python package (src/gigi).",
    "core": "The robot & its runtime: Character facade, config, daemon, LLM conversation, logging.",
    "interaction": "LLM-driven interaction: planner, strategies, runners, safety filter.",
    "interaction/llm": "LLM client back-ends (Ollama, OpenAI, Azure).",
    "interaction/web": "Small Flask web UI.",
    "expression": "How Gigi expresses itself: face display, speech/TTS, visemes, movement & gestures.",
    "perception": "How Gigi senses the world: hearing/STT, vision, speaker ID, pronunciation scoring.",
    "hardware": "Low-level drivers: motors (PCA9685), camera, NPU runner, calibration.",
    "activities": "Runnable demos, games and scripted interactions.",
    "activities/common": "Helpers shared by activities.",
    "activities/scripted": "Graph-based scripted interactions.",
    "activities/social": "Social demos: intro, make friends, receptionist, face recognition.",
    "verification": "Hardware & AI self-tests (the `gigi-verify` command).",
    "verification/ai": "Self-tests for AI models (STT, TTS, LLM, face, voice).",
    "verification/hardware": "Self-tests for hardware (motors, camera, mic, speaker, screen).",
}

# Colour family per top-level package (used by the template).
PACKAGE_COLOR = {
    "core": "#0277bd",
    "interaction": "#00897b",
    "expression": "#c2185b",
    "perception": "#558b2f",
    "hardware": "#5d4037",
    "activities": "#f9a825",
    "verification": "#7b1fa2",
    "": "#455a64",
}


def first_line(doc: str | None) -> str:
    if not doc:
        return ""
    for line in doc.strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def short_doc(doc: str | None, limit: int = 600) -> str:
    if not doc:
        return ""
    text = " ".join(l.strip() for l in doc.strip().splitlines() if l.strip())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args = ast.unparse(fn.args)
    except Exception:  # pragma: no cover - very old Python
        args = "..."
    prefix = "async " if isinstance(fn, ast.AsyncFunctionDef) else ""
    return f"{prefix}{fn.name}({args})"


def func_node(fn, kind: str, parent_qual: str = "") -> dict:
    qual = f"{parent_qual}.{fn.name}" if parent_qual else fn.name
    end = getattr(fn, "end_lineno", fn.lineno)
    return {
        "name": fn.name,
        "qual": qual,
        "kind": kind,
        "line": fn.lineno,
        "end": end,
        "loc": end - fn.lineno + 1,
        "sig": signature(fn),
        "doc": short_doc(ast.get_docstring(fn)),
    }


def module_name(rel: Path) -> str:
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(["gigi", *parts])


def resolve_import(mod: str, names: list[str], modmap: dict[str, str]) -> set[str]:
    """Map an imported dotted module (+ imported names) to files in src/gigi."""
    found: set[str] = set()
    for n in names:
        if f"{mod}.{n}" in modmap:  # `from gigi.core import config` -> config.py
            found.add(modmap[f"{mod}.{n}"])
    if mod in modmap and (not found or len(found) < len(names)):
        found.add(modmap[mod])
    return found


def parse_module(path: Path, modmap: dict[str, str]) -> dict:
    rel = path.relative_to(SRC)
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    tree = ast.parse(text)
    me = module_name(rel)
    pkg = me if rel.name == "__init__.py" else me.rsplit(".", 1)[0]

    children = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            end = getattr(node, "end_lineno", node.lineno)
            methods = [
                func_node(m, "method", node.name)
                for m in node.body
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            children.append({
                "name": node.name,
                "qual": node.name,
                "kind": "class",
                "line": node.lineno,
                "end": end,
                "loc": end - node.lineno + 1,
                "bases": [ast.unparse(b) for b in node.bases],
                "doc": short_doc(ast.get_docstring(node)),
                "children": methods,
            })
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            children.append(func_node(node, "func"))

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("gigi"):
                    imports |= resolve_import(a.name, [], modmap)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                mod = ".".join(base + ([node.module] if node.module else []))
            else:
                mod = node.module or ""
            if mod.startswith("gigi"):
                imports |= resolve_import(mod, [a.name for a in node.names], modmap)
    me_rel = rel.as_posix()
    imports.discard(me_rel)

    return {
        "name": rel.name,
        "path": me_rel,
        "kind": "module",
        "module": me,
        "loc": len(lines),
        "doc": short_doc(ast.get_docstring(tree)),
        "imports": sorted(imports),
        "children": children,
        "source": text,
    }


def build_tree() -> tuple[dict, dict[str, dict]]:
    files = sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)
    modmap = {module_name(p.relative_to(SRC)): p.relative_to(SRC).as_posix() for p in files}
    modules = {p.relative_to(SRC).as_posix(): parse_module(p, modmap) for p in files}

    # imported-by (reverse edges)
    for m in modules.values():
        m["importedBy"] = []
    for path, m in modules.items():
        for dep in m["imports"]:
            if dep in modules:
                modules[dep]["importedBy"].append(path)

    root = {"name": "src/gigi", "path": "", "kind": "pkg", "doc": PACKAGE_INFO[""], "children": []}
    pkgs = {"": root}

    def get_pkg(rel_dir: str) -> dict:
        if rel_dir in pkgs:
            return pkgs[rel_dir]
        parent_dir = rel_dir.rsplit("/", 1)[0] if "/" in rel_dir else ""
        parent = get_pkg(parent_dir)
        node = {
            "name": rel_dir.rsplit("/", 1)[-1] + "/",
            "path": rel_dir,
            "kind": "pkg",
            "doc": PACKAGE_INFO.get(rel_dir, ""),
            "children": [],
        }
        parent["children"].append(node)
        pkgs[rel_dir] = node
        return node

    for path, m in modules.items():
        rel_dir = path.rsplit("/", 1)[0] if "/" in path else ""
        get_pkg(rel_dir)["children"].append(m)

    # Non-Python assets of the web UI, so the map is complete.
    for asset in sorted((SRC / "interaction" / "web").rglob("*")):
        if asset.is_file() and asset.suffix in {".html", ".css", ".js"}:
            rel = asset.relative_to(SRC).as_posix()
            try:
                n = len(asset.read_text(encoding="utf-8", errors="replace").splitlines())
            except OSError:
                n = 1
            get_pkg("interaction/web")["children"].append(
                {"name": asset.relative_to(SRC / "interaction" / "web").as_posix(), "path": rel,
                 "kind": "asset", "loc": n, "doc": "Web UI asset."})
    return root, modules


def build_index(modules: dict[str, dict]) -> dict[str, dict]:
    """'core/robot.py:Character.run_character' -> {path, line, end}."""
    index = {}
    for path, m in modules.items():
        index[path] = {"path": path, "line": 1, "end": m["loc"]}
        for c in m["children"]:
            index[f"{path}:{c['qual']}"] = {"path": path, "line": c["line"], "end": c["end"]}
            for meth in c.get("children", []):
                index[f"{path}:{meth['qual']}"] = {"path": path, "line": meth["line"], "end": meth["end"]}
    return index


def main() -> int:
    root, modules = build_tree()
    index = build_index(modules)

    flow = json.loads(FLOW.read_text(encoding="utf-8"))
    missing = []
    for phase in flow["phases"]:
        for step in phase["steps"]:
            resolved = []
            for ref in step.get("refs", []):
                hit = index.get(ref)
                if hit is None:
                    missing.append(f"  phase {phase['id']}: {ref}")
                    continue
                resolved.append({"ref": ref, **hit})
            step["refs"] = resolved
            wf = step.pop("warnFind", None)
            if wf:
                src = modules.get(wf["path"], {}).get("source", "")
                hit = next((i + 1 for i, l in enumerate(src.splitlines()) if wf["text"] in l), None)
                if hit:
                    step["warnLine"] = {"path": wf["path"], "line": hit}
                else:  # text no longer present (e.g. the bug was fixed): drop the warning
                    print(f"note: '{wf['text']}' not found in {wf['path']}; dropping warning on phase {phase['id']}")
                    step.pop("warn", None)
    for lane in flow["lifelines"]:
        if lane.get("module") and lane["module"] not in modules:
            missing.append(f"  lifeline {lane['id']}: {lane['module']}")

    data = {
        "tree": root,
        "packageColor": PACKAGE_COLOR,
        "flow": flow,
    }
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("</", "<\\/")  # never close the <script> tag early
    html = TEMPLATE.read_text(encoding="utf-8-sig").replace("/*__DATA__*/null", payload)
    OUT.write_text(html, encoding="utf-8")

    n_cls = sum(1 for m in modules.values() for c in m["children"] if c["kind"] == "class")
    n_fn = sum(1 + len(c.get("children", [])) - (c["kind"] == "class") for m in modules.values() for c in m["children"])
    print(f"Wrote {OUT.relative_to(REPO)}  ({len(modules)} files, {n_cls} classes, {n_fn} functions/methods, "
          f"{OUT.stat().st_size / 1024:.0f} KB)")
    if missing:
        print("WARNING: unresolved references in story_flow.json:")
        print("\n".join(missing))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
