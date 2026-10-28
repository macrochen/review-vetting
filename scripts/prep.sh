#!/usr/bin/env bash
# 摸项目底：技术栈、能跑的命令、git 现状、目录、约定文件。
# 用法：bash scripts/prep.sh [项目目录]   （不给就用当前目录，自动往上找项目根）

set -uo pipefail

start="${1:-$PWD}"
[ -d "$start" ] || { echo "目录不存在：$start" >&2; exit 1; }
root="$(cd "$start" && pwd)"

is_root() {
  local d="$1"
  [ -d "$d/.git" ] && return 0
  for f in package.json pyproject.toml go.mod Cargo.toml pom.xml build.gradle build.gradle.kts composer.json Gemfile mix.exs; do
    [ -f "$d/$f" ] && return 0
  done
  return 1
}

# 往上找项目根
while [ "$root" != "/" ] && ! is_root "$root"; do
  root="$(dirname "$root")"
done
if ! is_root "$root"; then
  echo "没找到项目根（往上找到 / 都没有 .git 或 package.json 之类的标志文件）" >&2
  echo "直接把项目目录传进来试试。" >&2
  exit 1
fi

echo "项目根：$root"
echo

echo "== 技术栈 =="
[ -f "$root/package.json" ] && python3 - "$root/package.json" <<'PY'
import json, sys
try:
    p = json.load(open(sys.argv[1], encoding="utf-8"))
except Exception as e:
    print(f"  package.json 解析失败：{e}"); raise SystemExit
print(f"  名称：{p.get('name','?')}　版本：{p.get('version','?')}")
if p.get("packageManager"): print(f"  包管理器：{p['packageManager']}")
for k in ("dependencies", "devDependencies"):
    deps = p.get(k) or {}
    if deps:
        keys = [d for d in deps if not d.startswith("@types/")]
        print(f"  {k}（{len(keys)}）：" + ", ".join(f"{d}@{deps[d]}" for d in sorted(keys)[:12]) + (" …" if len(keys) > 12 else ""))
PY
[ -f "$root/pyproject.toml" ] && { echo "  Python：pyproject.toml"; grep -E '^(requires-python|name|version)\s*=' "$root/pyproject.toml" 2>/dev/null | head -3 | sed 's/^/    /'; }
[ -f "$root/go.mod" ] && { echo "  Go："; head -3 "$root/go.mod" | sed 's/^/    /'; }
[ -f "$root/Cargo.toml" ] && { echo "  Rust："; grep -E '^(name|version|edition)\s*=' "$root/Cargo.toml" | head -3 | sed 's/^/    /'; }
[ -f "$root/requirements.txt" ] && echo "  Python：requirements.txt（$(wc -l < "$root/requirements.txt" | tr -d ' ') 行）"
echo

echo "== 能跑的命令（照着用，别猜） =="
if [ -f "$root/package.json" ]; then
  python3 - "$root/package.json" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding="utf-8"))
for k, v in (p.get("scripts") or {}).items():
    print(f"  npm run {k:<12} → {v}")
PY
fi
for f in Makefile justfile Justfile; do
  [ -f "$root/$f" ] && { echo "  [$f 里的目标]"; grep -E '^[a-zA-Z0-9_-]+:' "$root/$f" 2>/dev/null | cut -d: -f1 | head -15 | sed 's/^/    /'; }
done
if [ -d "$root/.github/workflows" ]; then
  echo "  [CI：.github/workflows]"
  grep -h -E '^\s*(- )?run:' "$root/.github/workflows"/*.y*ml 2>/dev/null | sed 's/^\s*-\?\s*run:\s*//' | sort -u | head -10 | sed 's/^/    /'
fi
echo

echo "== 约定文件（先读这些再改代码） =="
for f in AGENTS.md CLAUDE.md CONTRIBUTING.md README.md .editorconfig .prettierrc .eslintrc .eslintrc.js eslint.config.js tsconfig.json ruff.toml .ruff.toml setup.cfg; do
  [ -f "$root/$f" ] && printf '  %-18s %s 行\n' "$f" "$(wc -l < "$root/$f" | tr -d ' ')"
done
echo

echo "== git 现状（改之前先看基线） =="
if git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
  echo "  分支：$(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null)"
  echo "  最近提交："
  git -C "$root" -c core.quotepath=false log --oneline -5 2>/dev/null | sed 's/^/    /'
  echo "  未提交改动："
  git -C "$root" -c core.quotepath=false status --short 2>/dev/null | head -30 | sed 's/^/    /'
  echo "    —— 共 $(git -C "$root" status --short 2>/dev/null | wc -l | tr -d ' ') 项"
else
  echo "  （不是 git 仓库：没有基线可比，改动前先自己备份）"
fi
echo

echo "== 目录（前两层，跳过 node_modules 等） =="
(cd "$root" && find . -maxdepth 2 -type d \
  -not -path '*/node_modules*' -not -path '*/.git*' -not -path '*/dist*' \
  -not -path '*/.next*' -not -path '*/__pycache__*' -not -path '*/.venv*' \
  -not -path '*/venv*' -not -path '*/target*' -not -path '*/build*' 2>/dev/null \
  | sed 's|^\./||' | grep -v '^\.$' | sort | head -30 | sed 's/^/  /')
echo

echo "== 有没有测试 =="
found=0
for d in test tests __tests__ spec src/test src/__tests__; do
  [ -d "$root/$d" ] && { echo "  有：$d/"; found=1; }
done
[ "$found" -eq 0 ] && echo "  没找到测试目录 —— 改代码前要先跟用户说清楚：没有测试兜底"
echo

echo "== 审查报告里常见的路径长什么样（抽一眼就知道它说的是不是这个项目） =="
(cd "$root" && find . -maxdepth 3 -type f \( -name '*.ts' -o -name '*.tsx' -o -name '*.js' -o -name '*.py' -o -name '*.go' -o -name '*.rs' -o -name '*.java' -o -name '*.vue' \) \
  -not -path '*/node_modules*' -not -path '*/.git*' -not -path '*/dist*' 2>/dev/null | head -8 | sed 's|^\./|  |')
echo
echo "下一步：读约定文件 → 拆报告（extract_items.py）→ 验引用（check_refs.py）→ 逐条过四关。"
