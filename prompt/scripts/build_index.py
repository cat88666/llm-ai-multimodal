#!/usr/bin/env python3
"""Build and validate wiki/index.md.

The source of truth is wiki/index.meta.toml plus the Markdown files under wiki/.
The generated index is intentionally deterministic so it can be checked in CI or
before commits with:

    python3 scripts/build_index.py --check
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = ROOT / "wiki"
META_PATH = WIKI_DIR / "index.meta.toml"
INDEX_PATH = WIKI_DIR / "index.md"


def load_meta() -> dict:
    with META_PATH.open("rb") as f:
        return tomllib.load(f)


def wiki_pages() -> list[Path]:
    return sorted(
        p.relative_to(WIKI_DIR)
        for p in WIKI_DIR.rglob("*.md")
        if p.name != "index.md"
    )


def link_text(path: str | Path) -> str:
    stem = Path(path).stem
    for prefix in ("概念-", "机制-", "主题-", "设计-", "系统设计-"):
        if stem.startswith(prefix):
            return stem.removeprefix(prefix)
    return stem


def md_link(path: str | Path, text: str | None = None) -> str:
    path_str = str(path)
    return f"[{text or link_text(path_str)}]({path_str})"


def join_links(paths: list[str | Path]) -> str:
    return "<br>".join(md_link(p) for p in paths)


def join_keywords(keywords: list[dict]) -> str:
    if not keywords:
        return "无"
    return " · ".join(md_link(item["path"], item["text"]) for item in keywords)


def keyword_map(keywords: list[dict]) -> dict[str, dict]:
    return {item["text"]: item for item in keywords}


def split_keywords(layer: dict) -> tuple[list[dict], list[dict]]:
    keywords = layer.get("keywords", [])
    core_texts = layer.get("core_keywords")
    if core_texts is None:
        core = keywords[: min(8, len(keywords))]
    else:
        by_text = keyword_map(keywords)
        core = [by_text[text] for text in core_texts if text in by_text]
    core_set = {item["text"] for item in core}
    supplemental = [item for item in keywords if item["text"] not in core_set]
    return core, supplemental


def concepts_for(layer: dict, pages: set[Path], kind: str) -> list[Path]:
    result: list[Path] = []
    expected_prefix = f"{kind}-"
    for concept_dir in layer.get("concept_dirs", []):
        base = Path(concept_dir)
        result.extend(
            p
            for p in pages
            if p.parent == base and p.name.startswith(expected_prefix)
        )
    return sorted(result)


def maintenance_pages(pages: set[Path]) -> list[Path]:
    return sorted(
        p
        for p in pages
        if p.parts[0] not in {"concepts", "summaries", "synthesis"}
    )


def render_concept_table(meta: dict, pages: set[Path]) -> list[str]:
    lines = [
        "## 机制和概念索引",
        "",
        "| 层级 | 知识域 | 概念 | 机制 | 核心入口 | 补充关键词 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for layer in meta["layers"]:
        concepts = concepts_for(layer, pages, "概念")
        mechanisms = concepts_for(layer, pages, "机制")
        core_keywords, supplemental_keywords = split_keywords(layer)
        lines.append(
            "| {id} | {name} | {concepts} | {mechanisms} | {core_keywords} | {supplemental_keywords} |".format(
                id=layer["id"],
                name=layer["name"],
                concepts=join_links(concepts),
                mechanisms=join_links(mechanisms),
                core_keywords=join_keywords(core_keywords),
                supplemental_keywords=join_keywords(supplemental_keywords),
            )
        )
    return lines


def render_summaries(meta: dict) -> list[str]:
    settings = meta.get("settings", {})
    summaries = [Path(p) for p in settings.get("summaries", meta.get("summaries", []))]
    if not summaries:
        return []
    lines = [
        "",
        "## 主题总结",
        "",
        "| 主题 | 路径 |",
        "| --- | --- |",
    ]
    for p in summaries:
        lines.append(f"| {md_link(p)} | `{p}` |")
    return lines


def render_synthesis(meta: dict) -> list[str]:
    settings = meta.get("settings", {})
    synthesis = [Path(p) for p in settings.get("synthesis", meta.get("synthesis", []))]
    if not synthesis:
        return []
    lines = [
        "",
        "## 综合分析",
        "",
        "| 专题 | 路径 |",
        "| --- | --- |",
    ]
    for p in synthesis:
        lines.append(f"| {md_link(p)} | `{p}` |")
    return lines


def render_index(meta: dict, pages: list[Path]) -> str:
    page_set = set(pages)
    title = meta.get("settings", {}).get("title", "Java 知识库索引")
    description = meta.get("settings", {}).get("description", "")
    lines = [
        f"# {title}",
        "",
        "> 自动生成文件，请不要直接手改本文件。",
        f"> 手动维护入口：`wiki/index.meta.toml`；重新生成：`python3 scripts/build_index.py`。",
    ]
    if description:
        lines.append(f"> {description}")
    lines.append("")
    lines.extend(render_concept_table(meta, page_set))
    lines.extend(render_summaries(meta))
    lines.extend(render_synthesis(meta))

    maintenance = maintenance_pages(page_set)
    if maintenance:
        lines.append("")
        lines.append("## 维护")
        lines.append("")
        for p in maintenance:
            lines.append(f"- {md_link(p)}")

    return "\n".join(lines).rstrip() + "\n"


def markdown_links(markdown: str) -> set[Path]:
    links: set[Path] = set()
    for match in re.finditer(r"\]\(([^)#?]+)(?:[#?][^)]*)?\)", markdown):
        target = match.group(1)
        if target.endswith(".md"):
            links.add(Path(target))
    return links


def validate(meta: dict, rendered: str, pages: list[Path]) -> list[str]:
    errors: list[str] = []
    page_set = set(pages)

    configured_paths: list[Path] = []
    for layer in meta["layers"]:
        configured_paths.extend(Path(item["path"]) for item in layer.get("keywords", []))
        known_keywords = set(keyword_map(layer.get("keywords", [])).keys())
        unknown_core_keywords = sorted(set(layer.get("core_keywords", [])) - known_keywords)
        if unknown_core_keywords:
            errors.append(
                f"{layer['id']} core_keywords not found in keywords: "
                + ", ".join(unknown_core_keywords)
            )
    settings = meta.get("settings", {})
    configured_paths.extend(Path(p) for p in settings.get("summaries", meta.get("summaries", [])))
    configured_paths.extend(Path(p) for p in settings.get("synthesis", meta.get("synthesis", [])))

    for path in sorted(set(configured_paths)):
        if path not in page_set:
            errors.append(f"configured path does not exist: {path}")

    linked = markdown_links(rendered)
    missing_from_index = sorted(page_set - linked)
    if missing_from_index:
        errors.append("pages missing from generated index: " + ", ".join(str(p) for p in missing_from_index))

    broken_links = sorted(linked - page_set)
    if broken_links:
        errors.append("generated index has broken links: " + ", ".join(str(p) for p in broken_links))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build wiki/index.md from wiki/index.meta.toml")
    parser.add_argument("--check", action="store_true", help="fail if wiki/index.md is not up to date")
    args = parser.parse_args()

    meta = load_meta()
    pages = wiki_pages()
    rendered = render_index(meta, pages)
    errors = validate(meta, rendered, pages)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.check:
        current = INDEX_PATH.read_text(encoding="utf-8") if INDEX_PATH.exists() else ""
        if current != rendered:
            diff = difflib.unified_diff(
                current.splitlines(keepends=True),
                rendered.splitlines(keepends=True),
                fromfile=str(INDEX_PATH),
                tofile="generated index",
            )
            sys.stdout.writelines(diff)
            return 1
        return 0

    INDEX_PATH.write_text(rendered, encoding="utf-8")
    print(f"generated {INDEX_PATH.relative_to(ROOT)} ({len(pages)} pages)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
