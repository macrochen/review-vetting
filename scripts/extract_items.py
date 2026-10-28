#!/usr/bin/env python3
"""把一份审查报告粗拆成条目，输出一张表，方便逐条核。

用法：
    python3 scripts/extract_items.py 审查报告.md
    python3 scripts/extract_items.py 审查报告.md --level 3    # 只按三级标题切
    python3 scripts/extract_items.py 审查报告.md --csv        # 输出 csv

只做"切"，不做"判断"。切得太碎是正常的——合并靠人。
"""

import argparse
import csv
import re
import sys

HEADING = re.compile(r"^(#{2,4})\s+(.*\S)\s*$")
NUMBERED = re.compile(r"^\s{0,3}(?:\d{1,2}[.、)）]|（\d{1,2}）|\(\d{1,2}\))\s*(\S.*)$")
BULLET_BOLD = re.compile(r"^\s{0,3}[-*+]\s+\*\*(.+?)\*\*")
FENCE = re.compile(r"^\s*(```|~~~)")


def truncate(text: str, width: int = 70) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def extract(path: str, max_level: int):
    items = []
    in_fence = False
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue

            m = HEADING.match(line)
            if m:
                level = len(m.group(1))
                if level <= max_level:
                    items.append(("标题", lineno, m.group(2)))
                continue

            m = NUMBERED.match(line)
            if m:
                items.append(("编号", lineno, m.group(1)))
                continue

            m = BULLET_BOLD.match(line)
            if m:
                items.append(("要点", lineno, m.group(1)))
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("report")
    ap.add_argument("--level", type=int, default=4, help="按几级标题切（2-4，默认 4）")
    ap.add_argument("--csv", action="store_true", help="输出 csv 而不是 markdown 表")
    args = ap.parse_args()

    try:
        items = extract(args.report, args.level)
    except FileNotFoundError:
        print(f"文件不存在：{args.report}", file=sys.stderr)
        return 1

    if not items:
        print("没切出条目。这份报告可能不是 markdown，或者结构很散——手工拆。")
        return 0

    if args.csv:
        writer = csv.writer(sys.stdout)
        writer.writerow(["#", "行号", "类型", "内容"])
        for i, (kind, lineno, text) in enumerate(items, 1):
            writer.writerow([i, lineno, kind, truncate(text, 200)])
    else:
        print("| # | 行号 | 类型 | 内容 |")
        print("| --- | --- | --- | --- |")
        for i, (kind, lineno, text) in enumerate(items, 1):
            print(f"| {i} | {lineno} | {kind} | {truncate(text)} |")
        print()
        print(f"共 {len(items)} 条。")
        print("下一步：合并同一件事被切开的几条，补上「它要的动作」和「指向哪里」两列；")
        print("        报告自己说「共 N 处」的，跟这个数对一对，对不上说明有漏读。")

    return 0


if __name__ == "__main__":
    sys.exit(main())
