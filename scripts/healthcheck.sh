#!/bin/bash
# =============================================================================
# tgbotstory2 — healthcheck script
# Usage:   ./scripts/healthcheck.sh
# Exit:    0 = OK, 1 = WARNING, 2 = CRITICAL
# =============================================================================

set -euo pipefail

SERVICE_NAME="tgbotstory2"
PROJECT_DIR="/home/user/tgbotstory2"
DB_PATH="${PROJECT_DIR}/data/bot.db"
TEMP_DIR="/tmp/tgbotstory2_media"
LOG_FILE="${PROJECT_DIR}/logs/bot.log"
DISK_THRESHOLD=80
LOG_STALE_SECONDS=600

WARNINGS=0
CRITICALS=0

check_service() {
    if systemctl is-active --quiet "${SERVICE_NAME}"; then
        echo "[OK]    Service '${SERVICE_NAME}' is running"
    else
        echo "[CRIT]  Service '${SERVICE_NAME}' is NOT running"
        CRITICALS=$((CRITICALS + 1))
    fi
}

check_watchdog() {
    local watchdog_usec
    watchdog_usec=$(systemctl show -p WatchdogUSec "${SERVICE_NAME}" 2>/dev/null | cut -d= -f2)
    if [[ -z "${watchdog_usec}" || "${watchdog_usec}" == "0" ]]; then
        echo "[OK]    Watchdog: not configured (skipped)"
        return
    fi

    local watchdog_ts
    watchdog_ts=$(systemctl show -p WatchdogTimestamp "${SERVICE_NAME}" 2>/dev/null | cut -d= -f2)
    if [[ -z "${watchdog_ts}" ]]; then
        echo "[WARN]  Watchdog: no ping timestamp found"
        WARNINGS=$((WARNINGS + 1))
        return
    fi

    local watchdog_epoch
    watchdog_epoch=$(date -d "${watchdog_ts}" +%s 2>/dev/null || echo 0)
    local now
    now=$(date +%s)
    local diff=$((now - watchdog_epoch))

    if [[ "${diff}" -gt 120 ]]; then
        echo "[WARN]  Watchdog: last ping ${diff}s ago (threshold: 120s)"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "[OK]    Watchdog: last ping ${diff}s ago"
    fi
}

check_disk() {
    local disk_usage
    disk_usage=$(df -h / 2>/dev/null | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ -z "${disk_usage}" ]]; then
        echo "[WARN]  Disk: cannot determine usage"
        WARNINGS=$((WARNINGS + 1))
    elif [[ "${disk_usage}" -gt "${DISK_THRESHOLD}" ]]; then
        echo "[CRIT]  Disk: usage at ${disk_usage}% (threshold: ${DISK_THRESHOLD}%)"
        CRITICALS=$((CRITICALS + 1))
    else
        echo "[OK]    Disk: usage at ${disk_usage}%"
    fi
}

check_database() {
    if [[ -f "${DB_PATH}" ]]; then
        echo "[OK]    Database: file exists at ${DB_PATH}"
    else
        echo "[CRIT]  Database: file NOT found at ${DB_PATH}"
        CRITICALS=$((CRITICALS + 1))
        return
    fi

    if sqlite3 "${DB_PATH}" "SELECT 1;" >/dev/null 2>&1; then
        echo "[OK]    Database: readable and queryable"
    else
        echo "[CRIT]  Database: cannot query (locked or corrupted)"
        CRITICALS=$((CRITICALS + 1))
    fi
}

check_temp_dir() {
    if mkdir -p "${TEMP_DIR}" 2>/dev/null; then
        echo "[OK]    Temp dir: ${TEMP_DIR} exists and writable"
    else
        echo "[CRIT]  Temp dir: cannot create ${TEMP_DIR}"
        CRITICALS=$((CRITICALS + 1))
    fi
}

check_log_freshness() {
    if [[ ! -f "${LOG_FILE}" ]]; then
        echo "[WARN]  Log file: not found at ${LOG_FILE}"
        WARNINGS=$((WARNINGS + 1))
        return
    fi

    local last_modified
    last_modified=$(stat -c %Y "${LOG_FILE}" 2>/dev/null || echo 0)
    local now
    now=$(date +%s)
    local diff=$((now - last_modified))

    if [[ "${diff}" -gt "${LOG_STALE_SECONDS}" ]]; then
        echo "[WARN]  Log file: last modified ${diff}s ago (threshold: ${LOG_STALE_SECONDS}s)"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "[OK]    Log file: last modified ${diff}s ago"
    fi
}

check_memory() {
    local mem_kb
    mem_kb=$(ps -o rss= -C python 2>/dev/null | awk '{sum+=$1} END {print sum+0}')
    if [[ -z "${mem_kb}" || "${mem_kb}" -eq 0 ]]; then
        echo "[WARN]  Memory: cannot determine process RSS"
        WARNINGS=$((WARNINGS + 1))
        return
    fi

    local mem_mb=$((mem_kb / 1024))
    if [[ "${mem_mb}" -gt 900 ]]; then
        echo "[WARN]  Memory: using ${mem_mb} MB (threshold: 900 MB)"
        WARNINGS=$((WARNINGS + 1))
    else
        echo "[OK]    Memory: using ${mem_mb} MB"
    fi
}

echo "=== tgbotstory2 Healthcheck ==="
echo ""

check_service
check_watchdog
check_disk
check_database
check_temp_dir
check_log_freshness
check_memory

echo ""
echo "=== Summary: ${WARNINGS} warning(s), ${CRITICALS} critical(s) ==="

if [[ "${CRITICALS}" -gt 0 ]]; then
    exit 2
elif [[ "${WARNINGS}" -gt 0 ]]; then
    exit 1
else
    exit 0
fi
