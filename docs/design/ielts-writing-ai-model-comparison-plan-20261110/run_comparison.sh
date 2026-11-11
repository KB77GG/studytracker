#!/usr/bin/env bash
# 换模型对照：deepseek-flash 对 deepseek-v4-pro。提示词以运行时代码为准（iwa-2026-11-10.12），
# 思考 high、输出上限 32000、超时 300 秒、只做评价（evaluate）。说明见同目录 codex-run.md。
#
# 在仓库根目录运行：
#   DRY=1 bash docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
#       彩排：演示模型，不调用付费服务，不需要 Key，结果写到 ~/iwa-compare-dry
#   CONFIRM_CAP=<授权上限> PRICE_FLASH_IN=… PRICE_FLASH_CACHED=… PRICE_FLASH_OUT=… \
#   PRICE_PRO_IN=… PRICE_PRO_CACHED=… PRICE_PRO_OUT=… \
#     bash docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
#       真实运行第一阶段（除 Task 1 带题图两篇以外的全部组）
#   STAGE=vision CONFIRM_CAP=<授权上限> PRICE_…=… bash …/run_comparison.sh
#       识图配好后的第二阶段：Task 1 带题图两篇
#
# 已完成的步骤（结果目录里有 .done）会跳过；中途停下后重跑同一条命令即可继续。
# 每次运行前检查：本阶段已用调用数 + 剩余步骤的最坏调用数 <= CONFIRM_CAP，否则不开始。
# 兼容 macOS 自带的 bash 3.2。

set -eo pipefail

REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
PY=${PY:-$REPO/.venv/bin/python}
D=${IWA_CALIBRATION:-$HOME/iwa-calibration}
STAGE=${STAGE:-main}
DRY=${DRY:-0}

if [ "$DRY" = 1 ]; then
  OUT=${IWA_COMPARE_OUT:-$HOME/iwa-compare-dry}
  export IWA_ENV_FILE=/nonexistent/iwa-dry.env IWA_DATA_DIR="$OUT/data"
  export IWA_LLM_PROVIDER=fake IWA_VISION_PROVIDER=fake
  FLASH=fake-flash
  PRO=fake-pro
else
  OUT=${IWA_COMPARE_OUT:-$HOME/iwa-compare}
  export IWA_LLM_PROVIDER=deepseek
  FLASH=deepseek-flash
  PRO=deepseek-v4-pro
  for v in PRICE_FLASH_IN PRICE_FLASH_CACHED PRICE_FLASH_OUT PRICE_PRO_IN PRICE_PRO_CACHED PRICE_PRO_OUT CONFIRM_CAP; do
    if [ -z "${!v}" ]; then
      echo "缺少 $v（单价为每百万 token 的元数；CONFIRM_CAP 为用户授权的本阶段调用上限）" >&2
      exit 2
    fi
  done
fi
export IWA_EVALUATE_THINKING=high IWA_EVALUATE_THINKING_MAX_TOKENS=32000 IWA_EVALUATE_THINKING_TIMEOUT=300
mkdir -p "$OUT"
LEDGER="$OUT/ledger.txt"

# 组名|样本|每篇次数|先跑的模型|Flash 上限|Pro 上限|Flash 额外参数|Pro 额外参数
# 上限 = 评价次数 × 2（首轮 + 一次校验重试），Task 1 带图组的 Flash 另加 2 次识图。
if [ "$STAGE" = vision ]; then
  STEPS="rated_t1|$D/holdout_rated_t1.jsonl|2|flash|10|8|--with-vision|--image-descriptions $OUT/rated_t1-flash/image_descriptions.json"
  if [ "$DRY" != 1 ]; then
    "$PY" -c 'import sys
from tools.ielts_writing_ai import load_settings
sys.exit(0 if load_settings().vision_enabled else 1)' || {
      echo "识图没有配置（IWA_VISION_PROVIDER / IWA_VISION_API_KEY），第二阶段不开始" >&2
      exit 2
    }
  fi
else
  STEPS="dev|builtin|2|flash|28|28||
teacher|$D/teacher.jsonl|2|pro|4|4||
rated_t2|$D/holdout_rated_t2.jsonl|2|flash|16|16||
ordering|$D/holdout_ordering.jsonl|1|pro|20|20||
lowband|$D/holdout_lowband.jsonl|2|flash|24|24||
official|$D/official.jsonl|2|pro|20|20||"
fi

calls_of() { # 某个结果目录的实际调用数（没有报告时为 0）
  if [ -f "$1/report.json" ]; then
    "$PY" -c 'import json, sys; print(json.load(open(sys.argv[1]))["calls"])' "$1/report.json"
  else
    echo 0
  fi
}

skip_group() { # 官方样卷没有转录完时整组跳过
  [ "$1" = official ] && [ ! -f "$D/official.jsonl" ]
}

# ---- 预算检查 ----
used=0
remaining=0
for d in "$OUT"/*-flash "$OUT"/*-pro "$OUT"/*-flash.incomplete-* "$OUT"/*-pro.incomplete-*; do
  [ -d "$d" ] || continue
  case "$STAGE:$(basename "$d")" in
    vision:rated_t1-*|main:dev-*|main:teacher-*|main:rated_t2-*|main:ordering-*|main:lowband-*|main:official-*)
      used=$((used + $(calls_of "$d"))) ;;
  esac
done
while IFS='|' read -r group samples repeat first capf capp xf xp; do
  [ -n "$group" ] || continue
  skip_group "$group" && continue
  [ -f "$OUT/$group-flash/.done" ] || remaining=$((remaining + capf))
  [ -f "$OUT/$group-pro/.done" ] || remaining=$((remaining + capp))
done <<EOF
$STEPS
EOF
echo "阶段 $STAGE：已用 $used 次，剩余步骤最坏 $remaining 次，授权上限 ${CONFIRM_CAP:-（彩排不限）}"
if [ "$DRY" != 1 ] && [ $((used + remaining)) -gt "$CONFIRM_CAP" ]; then
  echo "超出授权上限，不开始。请用户确认新的上限后再运行。" >&2
  exit 2
fi
if [ ! -f "$D/official.jsonl" ] && [ "$STAGE" = main ]; then
  echo "注意：$D/official.jsonl 不存在（官方样卷尚未转录），official 组跳过"
fi

run_one() { # 组名 样本 每篇次数 模型键 上限 额外参数
  local group=$1 samples=$2 repeat=$3 key=$4 cap=$5 extra=$6
  local dir="$OUT/$group-$key" model pin pc po rc
  if [ -f "$dir/.done" ]; then
    echo "跳过 $group / $key（已完成）"
    return 0
  fi
  if [ -d "$dir" ]; then
    mv "$dir" "$dir.incomplete-$(date +%Y%m%d%H%M%S)"
  fi
  if [ "$key" = flash ]; then
    model=$FLASH; pin=$PRICE_FLASH_IN; pc=$PRICE_FLASH_CACHED; po=$PRICE_FLASH_OUT
  else
    model=$PRO; pin=$PRICE_PRO_IN; pc=$PRICE_PRO_CACHED; po=$PRICE_PRO_OUT
  fi
  set -- realcheck --samples "$samples" --kinds evaluate --evaluate-thinking high \
    --repeat "$repeat" --max-calls "$cap" --out "$dir"
  if [ "$DRY" != 1 ]; then
    set -- "$@" --confirm-paid --price-in "$pin" --price-cached-in "$pc" --price-out "$po"
  fi
  # shellcheck disable=SC2086  # extra 是空或“选项 路径”，路径里没有空格
  set -- "$@" $extra
  echo "$(date '+%F %T') 开始 $group / $model（上限 $cap 次）" | tee -a "$LEDGER"
  set +e
  IWA_LLM_MODEL=$model "$PY" -m tools.ielts_writing_ai "$@" </dev/null
  rc=$?
  set -e
  echo "$(date '+%F %T') 结束 $group / $model：退出码 $rc，实际调用 $(calls_of "$dir") 次" | tee -a "$LEDGER"
  if [ $rc -ne 0 ]; then
    echo "停止：$group / $model 退出码 $rc（2 = 参数或数据有误；3 = 首次调用就遇到 Key 或网络错误）" >&2
    exit $rc
  fi
  touch "$dir/.done"
}

seed=1
while IFS='|' read -r group samples repeat first capf capp xf xp; do
  [ -n "$group" ] || continue
  seed=$((seed + 1))
  skip_group "$group" && continue
  # 两个模型交替先跑，避免一个模型总在同一时段
  if [ "$first" = flash ]; then
    run_one "$group" "$samples" "$repeat" flash "$capf" "$xf"
    run_one "$group" "$samples" "$repeat" pro "$capp" "$xp"
  else
    run_one "$group" "$samples" "$repeat" pro "$capp" "$xp"
    run_one "$group" "$samples" "$repeat" flash "$capf" "$xf"
  fi
  # A = Flash，B = Pro；盲评表里两边以甲 / 乙随机出现
  "$PY" -m tools.ielts_writing_ai realcheck-compare "$OUT/$group-flash" "$OUT/$group-pro" \
    --allow-model-change --blind "$seed" --out "$OUT/compare-$group" </dev/null
done <<EOF
$STEPS
EOF

"$PY" "$REPO/docs/design/ielts-writing-ai-model-comparison-plan-20261110/summarize_comparison.py" "$OUT"
echo "完成。汇总：$OUT/summary.md（只有数字，可以共享）；每组的盲评表：$OUT/compare-<组>/blind_review.md"
