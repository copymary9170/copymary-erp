#!/bin/sh
# Corre dentro del contenedor "backup" de docker-compose.yml.
# Hace un pg_dump completo cada 24 horas y borra respaldos de más de 30 días.
# No requiere cron: es un loop simple, suficiente para este caso de uso.
set -eu

mkdir -p /backups

while true; do
    timestamp="$(date -u +%Y%m%d-%H%M%S)"
    filename="/backups/copymary_erp_${timestamp}.sql.gz"

    echo "[$(date -u -Iseconds)] Iniciando respaldo -> ${filename}"
    if PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump -h db -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" | gzip > "${filename}"; then
        echo "[$(date -u -Iseconds)] Respaldo completado ($(du -h "${filename}" | cut -f1))"
    else
        echo "[$(date -u -Iseconds)] ERROR: el respaldo falló, se conserva el archivo parcial para diagnóstico" >&2
    fi

    # Borra respaldos de más de 30 días.
    find /backups -name "copymary_erp_*.sql.gz" -mtime +30 -delete

    sleep 86400
done
