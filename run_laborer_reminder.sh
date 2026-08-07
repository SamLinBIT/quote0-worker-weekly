#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 打工人周历 — cron 入口（uv 版 wrapper）
#
# Secrets are read from .env in the script directory.
# 依赖: uv（curl -LsSf https://astral.sh/uv/install.sh | sh）
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# --- Load secrets --------------------------------------------------
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
    set -a            # auto-export all variables
    source "${SCRIPT_DIR}/.env"
    set +a
else
    echo "[ERROR] .env file not found at ${SCRIPT_DIR}/.env"
    exit 1
fi

# --- Timezone (all Python time calls use this) ----------------------
export TZ='Asia/Shanghai'

# --- PATH (cron runs with minimal PATH) ----------------------------
export PATH="${HOME}/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# --- Run -----------------------------------------------------------
mkdir -p logs

# flock 防重入：手动 + cron 重叠时后到者直接退出，避免重复推送
exec 9>"${SCRIPT_DIR}/logs/laborer.lock"
flock -n 9 || { echo "[$(date '+%F %T %Z')] 已有实例在运行，本次跳过" >&2; exit 1; }

# 日志按日轮转
LOG_FILE="${SCRIPT_DIR}/logs/laborer_$(date +%F).log"
echo "[$(date '+%F %T %Z')] run_laborer_reminder.sh $*" \
    | tee -a "${LOG_FILE}"
# --frozen：锁文件已在仓库内，不联网拉取/解析，离线 cron 也稳
uv run --frozen python -m laborer_reminder.main "$@" 2>&1 \
    | tee -a "${LOG_FILE}"
