#!/bin/sh
# ─────────────────────────────────────────────────────────────
# DynamicPro ERP — Database Backup Script
# Runs as a cron container. Backs up daily, keeps last N days.
# ─────────────────────────────────────────────────────────────
set -e

BACKUP_DIR="/backups"
DATE=$(date +%Y-%m-%d_%H%M)
BACKUP_FILE="${BACKUP_DIR}/dp_${DB_NAME}_${DATE}.sql.gz"

echo "[BACKUP] Starting backup: ${DATE}"

mkdir -p "${BACKUP_DIR}"

# Dump and compress
pg_dump -h "${DB_HOST}" -U "${DB_USER}" -d "${DB_NAME}" \
    --no-owner --no-privileges --clean --if-exists \
    | gzip > "${BACKUP_FILE}"

FILESIZE=$(stat -c%s "${BACKUP_FILE}" 2>/dev/null || stat -f%z "${BACKUP_FILE}")
echo "[BACKUP] Created: ${BACKUP_FILE} (${FILESIZE} bytes)"

# Delete backups older than RETENTION days
echo "[BACKUP] Cleaning backups older than ${BACKUP_RETENTION} days..."
find "${BACKUP_DIR}" -name "dp_*.sql.gz" -mtime "+${BACKUP_RETENTION}" -delete 2>/dev/null || true

# List remaining backups
REMAINING=$(ls -1 "${BACKUP_DIR}"/dp_*.sql.gz 2>/dev/null | wc -l)
echo "[BACKUP] ${REMAINING} backups remaining"

echo "[BACKUP] Done."
