#!/bin/bash
# =============================================================================
# tgbotstory2 — deployment setup script
# Run as:  bash scripts/setup.sh
# =============================================================================

set -euo pipefail

# --- Configuration ---
PROJECT_DIR="/home/user/tgbotstory2"
VENV_DIR="${PROJECT_DIR}/venv"
SERVICE_FILE="${PROJECT_DIR}/tgbotstory2.service"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
ENV_FILE="${PROJECT_DIR}/.env"
ENV_EXAMPLE="${PROJECT_DIR}/.env.example"
DATA_DIR="${PROJECT_DIR}/data"
LOGS_DIR="${PROJECT_DIR}/logs"
TEMP_DIR="/tmp/tgbotstory2_media"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Step 1: Check Python version ---
log "Step 1/7: Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo "${PYTHON_VERSION}" | cut -d. -f1)
PYTHON_MINOR=$(echo "${PYTHON_VERSION}" | cut -d. -f2)

if [[ "${PYTHON_MAJOR}" -lt 3 ]] || [[ "${PYTHON_MAJOR}" -eq 3 && "${PYTHON_MINOR}" -lt 10 ]]; then
    err "Python 3.10+ required. Found: ${PYTHON_VERSION}"
    exit 1
fi
log "Python ${PYTHON_VERSION} — OK"

# --- Step 2: Create virtual environment ---
log "Step 2/7: Creating virtual environment..."
if [[ -d "${VENV_DIR}" ]]; then
    warn "Virtual environment already exists at ${VENV_DIR}"
    read -rp "Recreate? [y/N]: " RECREATE
    if [[ "${RECREATE,,}" == "y" ]]; then
        rm -rf "${VENV_DIR}"
        python3 -m venv "${VENV_DIR}"
        log "Virtual environment recreated"
    else
        log "Skipping venv creation"
    fi
else
    python3 -m venv "${VENV_DIR}"
    log "Virtual environment created at ${VENV_DIR}"
fi

# --- Step 3: Install dependencies ---
log "Step 3/7: Installing Python dependencies..."
source "${VENV_DIR}/bin/activate"
pip install --upgrade pip >/dev/null 2>&1
pip install -r "${PROJECT_DIR}/requirements.txt"
log "Dependencies installed"

# --- Step 4: Check/create .env ---
log "Step 4/7: Checking .env configuration..."
if [[ ! -f "${ENV_FILE}" ]]; then
    if [[ -f "${ENV_EXAMPLE}" ]]; then
        cp "${ENV_EXAMPLE}" "${ENV_FILE}"
        warn ".env created from .env.example"
        warn ">>> EDIT ${ENV_FILE} with your real values before starting the service!"
    else
        err ".env.example not found at ${ENV_EXAMPLE}"
        exit 1
    fi
else
    log ".env already exists"
fi

# --- Step 5: Generate FERNET_KEY if missing ---
log "Step 5/7: Generating encryption key..."
CURRENT_KEY=$(grep -E '^FERNET_KEY=' "${ENV_FILE}" 2>/dev/null | cut -d= -f2- || true)
if [[ -z "${CURRENT_KEY}" || "${CURRENT_KEY}" == "replace_me_with_generated_key" || "${CURRENT_KEY}" == "replace_me_with_fernet_key" ]]; then
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    if [[ "${CURRENT_KEY}" == "replace_me_with_generated_key" || "${CURRENT_KEY}" == "replace_me_with_fernet_key" ]]; then
        sed -i "s/^FERNET_KEY=.*/FERNET_KEY=${FERNET_KEY}/" "${ENV_FILE}"
    else
        echo "FERNET_KEY=${FERNET_KEY}" >> "${ENV_FILE}"
    fi
    log "Fernet key generated and saved to .env"
else
    log "Fernet key already set"
fi

# --- Step 6: Create directories and init DB ---
log "Step 6/7: Creating data/log directories..."
mkdir -p "${DATA_DIR}"
mkdir -p "${LOGS_DIR}"
mkdir -p "${TEMP_DIR}"
log "Directories: ${DATA_DIR}, ${LOGS_DIR}, ${TEMP_DIR}"

python3 -c "
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from bot.db.models import Base

async def init():
    engine = create_async_engine('sqlite+aiosqlite:///${DATA_DIR}/bot.db')
    async with engine.begin() as conn:
        await conn.exec_driver_sql('PRAGMA journal_mode=WAL')
        await conn.exec_driver_sql('PRAGMA foreign_keys=ON')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print('Database initialized')

asyncio.run(init())
"
log "Database initialized at ${DATA_DIR}/bot.db"

# --- Step 7: Install systemd unit ---
log "Step 7/7: Installing systemd service..."
mkdir -p "${SYSTEMD_DIR}"
cp "${SERVICE_FILE}" "${SYSTEMD_DIR}/tgbotstory2.service"
log "Unit file copied to ${SYSTEMD_DIR}/tgbotstory2.service"

systemctl --user daemon-reload
log "systemd user daemon reloaded"

if command -v loginctl &>/dev/null; then
    if loginctl enable-linger 2>/dev/null; then
        log "Linger enabled for user"
    else
        warn "Could not enable linger. Service may stop on logout."
        warn "Ask hosting support to run: loginctl enable-linger $(whoami)"
    fi
fi

systemctl --user enable tgbotstory2.service
systemctl --user start tgbotstory2.service

log ""
log "============================================"
log "  Deployment complete!"
log "============================================"
log ""
log "  Service:    systemctl --user status tgbotstory2"
log "  Logs:       journalctl --user -u tgbotstory2 -f"
log "  Health:     bash ${PROJECT_DIR}/scripts/healthcheck.sh"
log "  Config:     edit ${ENV_FILE}"
log ""
warn "Make sure you've edited ${ENV_FILE} with:"
warn "  - BOT_TOKEN (from @BotFather)"
warn "  - ADMIN_IDS (your Telegram user ID)"
warn "  - ENCRYPTION_KEY (auto-generated if missing)"
warn "  - Platform credentials (VK, IG, TT)"
log ""
log "Then restart: systemctl --user restart tgbotstory2"
