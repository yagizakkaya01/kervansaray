#!/usr/bin/env bash
# ============================================================
# Kervansaray - Günlük Otomatik PostgreSQL Yedekleme Scripti
# ============================================================
#
# Çalışma mantığı:
#   1. docker-compose içindeki Postgres veritabanını pg_dump ile döker.
#   2. gzip ile sıkıştırıp zaman damgasıyla kaydeder.
#   3. 7 günden eski yerel yedekleri otomatik temizler.
#
# Cron Kurulumu (her gece 03:00'te):
#   crontab -e
#   0 3 * * * /opt/kervansaray/scripts/backup.sh >> /var/log/kervansaray_backup.log 2>&1
#
# Host Dışı (Offsite) Senkronizasyon Örneği:
#   rclone sync /var/backups/kervansaray remote:kervansaray-backups
# ============================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/kervansaray}"
CONTAINER_NAME="${DB_CONTAINER:-kervansaray_db}"
DB_USER="${POSTGRES_USER:-kervansaray}"
DB_NAME="${POSTGRES_DB:-kervansaray}"
RETENTION_DAYS=7

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/kervansaray_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[$(date -Iseconds)] PostgreSQL yedekleme başlatılıyor: ${BACKUP_FILE}..."

# Docker içindeki Postgres'ten dump al ve gzip ile sıkıştır
docker exec "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip -9 > "${BACKUP_FILE}"

FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date -Iseconds)] Yedek başarıyla tamamlandı (${FILESIZE})."

# 7 günden eski yedekleri temizle
echo "[$(date -Iseconds)] ${RETENTION_DAYS} günden eski yedekler temizleniyor..."
find "${BACKUP_DIR}" -type f -name "kervansaray_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} +

echo "[$(date -Iseconds)] Yedekleme döngüsü tamamlandı."
