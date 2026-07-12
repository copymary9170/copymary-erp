#!/bin/sh
# Restaura un respaldo en la base de datos.
#
# Uso (desde el servidor, en la carpeta del proyecto, fuera de los
# contenedores):
#   ./scripts/restore.sh backups/copymary_erp_20260101-000000.sql.gz
#
# ADVERTENCIA: esto reemplaza los datos actuales de la base con los del
# respaldo. Confirma que es lo que quieres antes de correrlo.
set -eu

if [ "$#" -ne 1 ]; then
    echo "Uso: $0 <archivo-de-respaldo.sql.gz>" >&2
    exit 1
fi

BACKUP_FILE="$1"
if [ ! -f "$BACKUP_FILE" ]; then
    echo "No se encontró el archivo: $BACKUP_FILE" >&2
    exit 1
fi

# shellcheck disable=SC1091
. ./.env

echo "Vas a restaurar '$BACKUP_FILE' sobre la base '${POSTGRES_DB}'."
echo "Esto reemplaza los datos actuales. Escribe 'si' para continuar:"
read -r confirmacion
if [ "$confirmacion" != "si" ]; then
    echo "Cancelado."
    exit 1
fi

gunzip -c "$BACKUP_FILE" | docker compose exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"

echo "Restauración completada."
