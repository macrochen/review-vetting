#!/usr/bin/env python3
"""把审查报告里出现的文件路径、path:line 抽出来，逐个验：
文件在不在、行号越界没有、那一行现在写的是什么。

用法：
    python3 scripts/check_refs.py 审查报告.md
    python3 scripts/check_refs.py 审查报告.md --root /path/to/project
    python3 scripts/check_refs.py 审查报告.md --root . --max 60

为什么先跑这个：审查意见里最常见的问题是"引了仓库里不存在的东西"。
验一遍能筛掉一大半，剩下的才值得逐条看。
"""

import argparse
import os
import re
import sys

EXTS = (
    "ts tsx js jsx mjs cjs vue svelte astro "
    "py pyi go rs java kt kts swift rb php cs c h cpp hpp cc "
    "sql prisma graphql gql proto "
    "json jsonc yaml yml toml ini cfg conf env "
    "md mdx rst txt css scss sass less html htm "
    "sh bash zsh ps1 bat tf tfvars gradle properties xml plist"
).split()

PATH_RE = re.compile(
    r"(?<![\w/.\-])"
    r"((?:\.{1,2}/)?(?:[\w.\-]+/)*[\w.\-]+\.(?:" + "|".join(EXTS) + r"))"
    r"(?::(\d+)(?::(\d+))?)?"
)

SKIP_DIRS = {
    ".git", "node_modules", "dist", "build", "target", ".next", ".nuxt",
    "__pycache__", ".venv", "venv", "env", "vendor", ".idea", ".vscode",
    "coverage", ".pytest_cache", ".mypy_cache", "Pods", "DerivedData",
}


def collect(report_path):
    """返回 [(引用原文, 路径, 行号 or None)]，按出现顺序去重。"""
    refs, seen = [], set()
    with open(report_path, encoding="utf-8") as fh:
        for raw in fh:
            # 跳过整行 URL，避免把链接里的路径当引用
            for m in PATH_RE.finditer(raw):
                start = m.start(1)
                if raw[max(0, start - 8):start].lower().endswith(("http://", "https://", "://")):
                    continue
                path = m.group(1)
                lineno = int(m.group(2)) if m.group(2) else None
                key = (path, lineno)
                if key in seen:
                    continue
                seen.add(key)
                refs.append((m.group(0), path, lineno))
    return refs


def build_basename_index(root):
    index = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
        for name in filenames:
            index.setdefault(name, os.path.join(dirpath, name))
    return index


def resolve(root, path, basename_index):
    """返回 (真实路径 or None, 状态说明)。"""
    candidate = path if os.path.isabs(path) else os.path.join(root, path)
    if os.path.isfile(candidate):
        return candidate, ""
    # 报告里常省略前缀，用文件名兜一次
    base = os.path.basename(path)
    hit = basename_index.get(base)
    if hit:
        rel = os.path.relpath(hit, root)
        return hit, f"路径对不上，但同名文件在 {rel}"
    return None, ""


def read_line(path, lineno):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        return None, f"读不了：{exc}"
    if lineno > len(lines):
        return None, f"行号越界（文件只有 {len(lines)} 行）"
    return lines[lineno - 1].strip(), ""


def truncate(text, width=72):
    text = re.sub(r"\s+", " ", text)
    return text if len(text) <= width else text[: width - 1] + "…"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--root", default=".", help="项目根目录（默认当前目录）")
    ap.add_argument("--max", type=int, default=80, help="最多列多少条（默认 80）")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"项目目录不存在：{root}", file=sys.stderr)
        return 1
    try:
        refs = collect(args.report)
    except FileNotFoundError:
        print(f"报告文件不存在：{args.report}", file=sys.stderr)
        return 1

    if not refs:
        print("没从报告里抽出任何文件路径。")
        print("可能它没写具体文件（纯架构建议），也可能路径格式很特别——那就手工核。")
        return 0

    index = build_basename_index(root)

    rows, missing, mismatched = [], [], []
    for raw, path, lineno in refs:
        real, note = resolve(root, path, index)
        if real is None:
            status, content = "文件不存在", ""
            missing.append(raw)
        elif note:
            status, content = note, ""
            mismatched.append(raw)
        elif lineno is None:
            status, content = "存在", ""
        else:
            line, err = read_line(real, lineno)
            status, content = ("存在", truncate(line)) if not err else (err, "")
            if err:
                missing.append(raw)
        rows.append((raw, status, content))

    ok = sum(1 for _, s, _ in rows if s == "存在")
    print(f"共抽出 {len(rows)} 处引用：{ok} 处能直接对上，{len(rows) - ok} 处需要看。\n")
    print("| # | 报告里写的 | 结果 | 那一行现在是什么 |")
    print("| --- | --- | --- | --- |")
    for i, (raw, status, content) in enumerate(rows[: args.max], 1):
        print(f"| {i} | `{raw}` | {status} | {content} |")
    if len(rows) > args.max:
        print(f"\n（还有 {len(rows) - args.max} 条没列，加 --max 看全）")

    if missing:
        print("\n**对不上的**（先判断是幻觉还是意见过时）：")
        for m in missing:
            print(f"  - `{m}`")
        print("  幻觉 → 不采纳；改名／挪位置 → 按现在的写法改，理由里写清。")
    if mismatched:
        print("\n**路径变了但文件还在的**：按提示的相对路径去核，别直接判它错。")
    if ok == len(rows):
        print("\n引用全对上了。下一步：逐条过四关（问题真实性 → 依据 → 契合 → 代价）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
