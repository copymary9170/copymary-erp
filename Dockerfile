# Imagen de producción de CopyMary ERP.
# Incluye requirements-postgres.txt porque el despliegue self-hosted
# (docker-compose.yml) usa PostgreSQL, no SQLite.

FROM python:3.12-slim

WORKDIR /app

# Dependencias del sistema mínimas para compilar/instalar psycopg[binary]
# (la variante "binary" trae su propio libpq, pero curl se usa para el
# healthcheck de Streamlit).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt

COPY . .

# Usuario sin privilegios (no correr como root en producción).
RUN useradd --create-home --uid 1000 copymary \
    && chown -R copymary:copymary /app
USER copymary

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

ENTRYPOINT ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
