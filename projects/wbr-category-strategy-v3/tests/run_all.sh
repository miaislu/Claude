#!/usr/bin/env bash
# 一键跑全部 unit tests + e2e smoke tests
# 用法:
#   bash tests/run_all.sh           # 默认 verbose
#   bash tests/run_all.sh -v 2      # 自定义 verbosity
#   bash tests/run_all.sh -p test_lineage_*  # 只跑匹配文件
set -euo pipefail

# 切到 skill 根目录(脚本所在的父目录)
cd "$(dirname "$0")/.."

# 预检:必需依赖
python3 -c "import pandas, openpyxl, numpy" 2>/dev/null || {
  echo "❌ 缺少 Python 依赖。先跑:"
  echo "   pip3 install pandas openpyxl numpy"
  exit 1
}

# 默认 -v;允许覆盖
ARGS=("${@:-}")
if [[ ${#ARGS[@]} -eq 0 || -z "${ARGS[0]:-}" ]]; then
  ARGS=("-v")
fi

echo "=== Running tests ==="
python3 -m unittest discover -s tests "${ARGS[@]}"
