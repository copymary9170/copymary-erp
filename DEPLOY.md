# Despliegue self-hosted de CopyMary ERP

Guía completa para poner el sistema en producción **por tu cuenta**, sin depender
de Streamlit Community Cloud ni de ningún proveedor específico. Todo corre con
Docker, así que sirve igual en un VPS de DigitalOcean, Hetzner, AWS Lightsail,
Vultr, un servidor propio, o incluso una PC con IP fija en tu local.

Al final vas a tener: la app + PostgreSQL + HTTPS automático y gratuito +
respaldos diarios automáticos, todo administrado con 2-3 comandos.

---

## 0. Qué necesitas antes de empezar

- Un servidor con **Ubuntu 22.04 o 24.04**, mínimo 1 GB de RAM (2 GB recomendado).
  Cualquier VPS económico de cualquier proveedor sirve — esta guía no depende
  de ninguno en particular.
- Acceso por SSH a ese servidor (usuario con permisos de `sudo`).
- (Opcional pero recomendado) Un dominio o subdominio propio, ej.
  `erp.tunegocio.com`, apuntando a la IP del servidor. Sin dominio también
  funciona, solo que sin HTTPS (ver Caddyfile).

No necesitas saber Docker de antemano — cada comando de abajo está completo,
cópialo y pégalo tal cual.

---

## 1. Preparar el servidor

Conéctate por SSH:

```bash
ssh tu-usuario@ip-de-tu-servidor
```

Instala Docker (el instalador oficial funciona igual en cualquier proveedor):

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
```

Cierra la sesión SSH y vuelve a entrar (para que el cambio de grupo tenga efecto):

```bash
exit
ssh tu-usuario@ip-de-tu-servidor
docker --version
```

Deberías ver algo como `Docker version 29.x.x`.

---

## 2. Configurar el firewall (importante)

Antes de exponer nada a internet, cierra todo excepto lo necesario:

```bash
sudo ufw allow 22/tcp    # SSH — no te quedes afuera de tu propio servidor
sudo ufw allow 80/tcp    # HTTP (Caddy lo redirige a HTTPS automáticamente)
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

Nota que **no** abrimos el puerto 8501 (Streamlit) ni el 5432 (PostgreSQL) al
exterior — solo son accesibles dentro de la red interna de Docker. El único
punto de entrada público es Caddy, en 80/443.

---

## 3. Descargar el proyecto

```bash
git clone https://github.com/copymary9170/copymary-erp.git
cd copymary-erp
```

---

## 4. Configurar las variables de entorno

```bash
cp .env.example .env
nano .env
```

Cambia `POSTGRES_PASSWORD` por una contraseña larga y única. Puedes generar
una segura con:

```bash
openssl rand -base64 24
```

Guarda el archivo (`Ctrl+O`, `Enter`, `Ctrl+X` en nano).

---

## 5. Configurar el dominio (o saltar este paso si no tienes uno)

**Si tienes un dominio:**

1. En el panel de DNS de tu dominio, crea un registro **A** apuntando al
   subdominio que quieras (ej. `erp`) hacia la IP de tu servidor.
2. Edita `Caddyfile` y reemplaza `tu-dominio.com` por tu dominio real:
   ```bash
   nano Caddyfile
   ```

**Si todavía no tienes dominio:** edita `Caddyfile`, comenta el primer bloque
y descomenta el bloque `:80` (instrucciones dentro del archivo). Podrás
acceder por `http://ip-de-tu-servidor` sin HTTPS hasta que consigas un
dominio — en ese momento vuelves a este paso.

---

## 6. Levantar todo

```bash
docker compose up -d --build
```

La primera vez tarda unos minutos (descarga las imágenes base y construye la
app). Verifica que todo esté corriendo:

```bash
docker compose ps
```

Deberías ver 4 servicios en estado `running`/`healthy`: `db`, `app`, `caddy`,
`backup`.

Si algo no arrancó, revisa los logs del servicio con problemas:

```bash
docker compose logs app
docker compose logs caddy
```

---

## 7. Entrar a la app

- Con dominio: `https://tu-dominio.com` (Caddy consigue el certificado HTTPS
  automáticamente la primera vez que alguien entra — puede tardar unos
  segundos la primerísima carga).
- Sin dominio: `http://ip-de-tu-servidor`

Como no existe ningún usuario todavía, la app te va a pedir crear el
administrador inicial. Hazlo con un correo y una contraseña reales — es la
única puerta de entrada al sistema.

---

## 8. Respaldos automáticos

Ya están funcionando sin que hagas nada: el servicio `backup` corre un
`pg_dump` completo cada 24 horas, comprimido, guardado en `./backups/` en el
propio servidor, y borra automáticamente los de más de 30 días.

Para ver los respaldos existentes:

```bash
ls -lh backups/
```

**Recomendación importante:** estos respaldos viven en el mismo servidor. Si
el servidor se pierde por completo (falla de disco, etc.), se pierden con él.
Copia periódicamente la carpeta `backups/` a otro lugar — por ejemplo, con
`rsync` o `scp` hacia tu computadora, o subiéndola a un bucket S3/Backblaze.
Ejemplo simple con `scp` desde tu propia PC (no desde el servidor):

```bash
scp -r tu-usuario@ip-de-tu-servidor:~/copymary-erp/backups ./respaldos-copymary
```

Puedes automatizar esto con un cron job en tu propia computadora o en otro
servidor si quieres que quede fuera del VPS por completo.

### Restaurar un respaldo

```bash
./scripts/restore.sh backups/copymary_erp_20260101-000000.sql.gz
```

Te va a pedir confirmación explícita antes de sobrescribir los datos actuales.

---

## 9. Actualizar la app cuando haya cambios nuevos

```bash
cd copymary-erp
git pull
docker compose up -d --build
```

Esto reconstruye solo lo que cambió y reinicia sin perder datos (la base de
datos vive en un volumen de Docker aparte, no se toca al reconstruir la app).

---

## 10. Comandos útiles del día a día

```bash
docker compose ps                  # ver qué está corriendo
docker compose logs -f app         # ver logs de la app en vivo
docker compose restart app         # reiniciar solo la app
docker compose down                # apagar todo (los datos se conservan)
docker compose up -d               # volver a encender
```

---

## Qué NO cubre esta guía (a propósito)

- **Balanceo de carga / múltiples servidores**: esta guía es para un solo
  servidor, que es más que suficiente para una empresa hasta un tamaño
  considerable. Si algún día necesitas escalar a varios servidores, es un
  paso posterior, no algo para resolver de entrada.
- **Monitoreo/alertas avanzadas**: `docker compose logs` y `docker compose ps`
  cubren lo básico. Herramientas como Uptime Kuma (auto-hospedable, gratis)
  son un buen siguiente paso si quieres que te avise si el sitio se cae.
- **CI/CD automático**: el proyecto decidió deliberadamente no usar GitHub
  Actions todavía (ver `docs/error-real-copymary-1.md`). Actualizar es un
  `git pull` + `docker compose up -d --build` manual, a propósito, mientras
  el equipo gana confianza en el proceso.

---

## Nota sobre lo que se probó y lo que no

El `Dockerfile` y `docker-compose.yml` de este repo se validaron con
`docker compose config` (estructura, variables de entorno, dependencias entre
servicios — todo correcto) y contra un PostgreSQL real (ver
`tests/test_erp_database_postgres.py`). La construcción completa de la imagen
Docker de la app (`docker compose up -d --build`) no se pudo probar de
extremo a extremo en el entorno donde se preparó este despliegue por no tener
salida a internet hacia Docker Hub — vas a ser tú, en tu propio servidor, con
salida a internet normal, quien la corra por primera vez. Si algo falla en
ese primer `docker compose up -d --build`, copia el error completo y
podemos resolverlo juntas.
