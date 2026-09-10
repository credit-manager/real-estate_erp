#!/bin/sh
# DynamicPro ERP — verified periodic PostgreSQL backup worker.
set -eu

BACKUP_DIR="/backups"
BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION="${BACKUP_RETENTION:-30}"

mkdir -p "${BACKUP_DIR}"

while :; do
    DATE=$(date +%Y-%m-%d_%H%M%S)
    BACKUP_FILE="${BACKUP_DIR}/dp_${DB_NAME}_${DATE}.sql.gz"
    TMP_FILE="${BACKUP_FILE}.tmp"

    echo "[BACKUP] Starting backup: ${DATE}"
    rm -f "${TMP_FILE}"

    if pg_dump -h "${DB_HOST}" -U "${DB_USER}" -d "${DB_NAME}" \
        --no-owner --no-privileges --clean --if-exists \
        | gzip > "${TMP_FILE}"; then
        :
    else
        echo "[BACKUP] pg_dump failed" >&2
        rm -f "${TMP_FILE}"
        sleep "${BACKUP_INTERVAL_SECONDS}"
        continue
    fi

    FILESIZE=$(stat -c%s "${TMP_FILE}" 2>/dev/null || stat -f%z "${TMP_FILE}")
    if [ "${FILESIZE}" -lt 128 ]; then
        echo "[BACKUP] Refusing suspiciously small backup (${FILESIZE} bytes)" >&2
        rm -f "${TMP_FILE}"
        sleep "${BACKUP_INTERVAL_SECONDS}"
        continue
    fi

    if ! gzip -t "${TMP_FILE}"; then
        echo "[BACKUP] gzip integrity verification failed" >&2
        rm -f "${TMP_FILE}"
        sleep "${BACKUP_INTERVAL_SECONDS}"
        continue
    fi

    mv -f "${TMP_FILE}" "${BACKUP_FILE}"
    echo "[BACKUP] Created and verified: ${BACKUP_FILE} (${FILESIZE} bytes)"

    find "${BACKUP_DIR}" -name "dp_*.sql.gz" -mtime "+${BACKUP_RETENTION}" -delete 2>/dev/null || true
    REMAINING=$(find "${BACKUP_DIR}" -maxdepth 1 -type f -name "dp_*.sql.gz" | wc -l)
    echo "[BACKUP] ${REMAINING} backups remaining"
    echo "[BACKUP] Sleeping ${BACKUP_INTERVAL_SECONDS}s before next run."
    sleep "${BACKUP_INTERVAL_SECONDS}"
done
