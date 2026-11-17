# Desplegar PeakStroke

> Escrita el 2026-11-16 (`transversal/infra`, TODO-34). Sirve para cualquier
> alojamiento: **dónde** se aloja sigue siendo una decisión tuya. Lo que el
> código ya hace por su cuenta está marcado con ✅; lo que tiene que hacer quien
> despliega, con ☐.

## Las piezas

```
navegador ──https──▶ proxy (Caddy, nginx o el del alojamiento)
                       ├── /        → frontend/dist (estático)
                       └── /api/    → uvicorn app.main:app  ──▶ PostgreSQL
```

- **Frontend**: `npm run build` deja `frontend/dist/`, archivos estáticos.
- **API**: FastAPI con uvicorn, detrás de un proxy con HTTPS.
- **Base**: PostgreSQL. El código es el mismo que en SQLite; solo cambia la URL.

Servir el frontend y el API desde **el mismo dominio** (el API en `/api/`) es lo
más sencillo: la cookie de sesión, la CSP (`connect-src 'self'`) y CORS no piden
nada más. Con dominios distintos, ver «Dominios separados» al final.

## 1. Variables de entorno

Obligatorias en producción. ✅ **La app se niega a arrancar** si falta alguna:

| Variable | Valor | Por qué |
|---|---|---|
| `PEAKSTROKE_ENVIRONMENT` | `production` | Activa las comprobaciones de esta tabla, HSTS y apaga `/docs` |
| `PEAKSTROKE_AUTH_ENABLED` | `true` | Sin login el API está abierto: toda petición entra como el dueño |
| `PEAKSTROKE_JWT_SECRET` | aleatorio, 64+ caracteres | El de desarrollo está en el repo. Genera uno con `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `PEAKSTROKE_REFRESH_COOKIE_SECURE` | `true` | Que la cookie de sesión no viaje por http |
| `PEAKSTROKE_DATABASE_URL` | `postgresql+asyncpg://usuario:clave@host:5432/peakstroke` | La base |

✅ Además, aunque falte `ENVIRONMENT`, **sin login no arranca contra una base
remota** (solo contra SQLite o un PostgreSQL en la misma máquina).

Según el caso:

| Variable | Cuándo |
|---|---|
| `PEAKSTROKE_PROXIES_DE_CONFIANZA` | **Siempre que haya proxy delante** (lo normal). Redes del proxy, por comas: `127.0.0.1/32` si es Caddy/nginx en la misma máquina; la red interna del balanceador si es del alojamiento. Ver §4 |
| `PEAKSTROKE_CORS_ORIGINS` | Solo con dominios separados: `["https://app.ejemplo.com"]` |
| `PEAKSTROKE_FRENO_FALLOS_POR_ORIGEN` | Si un club entero entra desde la misma wifi y el freno de login le salta (20 por defecto, de 5 a 500) |

## 2. La base

```bash
cd backend
pip install -r requirements.txt -c requirements.lock asyncpg
alembic upgrade head
```

☐ Copia de seguridad antes de cada `alembic upgrade head` en una base con datos.
✅ La CI sube, comprueba y baja todas las migraciones en PostgreSQL 17 en cada
push (`.github/workflows/ci.yml`, trabajo `postgres`).

El primer club no se puede crear desde la web (no hay registro público). Se crea
en el servidor, y la contraseña temporal se enseña una vez:

```bash
python tools/ops.py crear-equipo --nombre-equipo "Club" --correo dueno@club.com --nombre "Nombre"
```

El resto de comandos de operación (revocar, restablecer contraseña de un
entrenador, cortar sesiones…) están en `backend/tools/README.md`.

## 3. El API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --no-proxy-headers
```

- `--host 127.0.0.1`: solo el proxy habla con uvicorn.
- `--no-proxy-headers`: uvicorn, por defecto, ya cree el `X-Forwarded-For` que
  llegue desde `127.0.0.1`. Apagándolo, **la única** que decide qué IP es la del
  cliente es `PEAKSTROKE_PROXIES_DE_CONFIANZA` (`core/proxy.py`), con tests.
- Con varios workers hace falta `PEAKSTROKE_JWT_SECRET` (sin él, cada worker
  firmaría con el suyo y las sesiones fallarían al azar).

✅ Cada respuesta del API lleva sus cabeceras de seguridad (`core/cabeceras.py`):
CSP cerrada, `nosniff`, `X-Frame-Options: DENY`, `no-referrer`, `Cache-Control:
no-store` (son datos personales) y HSTS en producción.

## 4. El proxy y la IP real

Detrás de un proxy, todas las conexiones llegan desde él. Si no se declara, el
freno de login ve a todo el mundo como **una sola IP** y, con 20 fallos de
cualquiera, frena a todos. Con `PEAKSTROKE_PROXIES_DE_CONFIANZA` puesto, la app
lee `X-Forwarded-For` **solo** cuando la conexión viene de esas redes, y de
derecha a izquierda: lo que escribe el cliente no se cree nunca.

☐ Comprobar después de desplegar: un login fallido debe auditarse con la red
del cliente, no la del proxy (`v_admin_accesos`, columna `ip_network`).

## 5. El frontend y sus cabeceras

```bash
cd frontend
npm ci && npm run build      # → dist/
```

Las cabeceras de seguridad del frontend las pone quien sirva `dist/`. Están en
un solo sitio, `frontend/cabecerasDeSeguridad.ts`; un test comprueba que
`frontend/public/_headers` diga lo mismo.

- **Netlify o Cloudflare Pages**: `_headers` ya va dentro de `dist/`. Nada más.
- **Caddy**:

  ```
  ejemplo.com {
      encode zstd gzip
      handle /api/* {
          reverse_proxy 127.0.0.1:8000
      }
      handle {
          root * /srv/peakstroke/dist
          try_files {path} /index.html
          file_server
          header {
              Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
              X-Content-Type-Options nosniff
              X-Frame-Options DENY
              Referrer-Policy no-referrer
              Cross-Origin-Opener-Policy same-origin
              Permissions-Policy "camera=(), microphone=(), geolocation=()"
              Strict-Transport-Security "max-age=31536000; includeSubDomains"
          }
      }
  }
  ```

  Caddy saca y renueva el certificado HTTPS solo. Con él en la misma máquina:
  `PEAKSTROKE_PROXIES_DE_CONFIANZA=127.0.0.1/32`.

- **nginx**: las mismas cabeceras con `add_header … always;` en el `location /`,
  `try_files $uri /index.html;`, y `location /api/ { proxy_pass
  http://127.0.0.1:8000; proxy_set_header X-Forwarded-For
  $proxy_add_x_forwarded_for; }`.

✅ La CSP se probó contra la build real (`npm run build && npm run preview`, que
sirve con estas cabeceras): las vistas, los modales, los gráficos y el PDF
funcionan sin una sola violación.

## 6. Antes de abrir a usuarios reales

- ☐ Las cinco variables de §1 (la app no arranca sin ellas).
- ☐ `PEAKSTROKE_PROXIES_DE_CONFIANZA` y la comprobación de §4.
- ☐ HTTPS en el dominio, y http redirigiendo a https.
- ☐ Copias de seguridad automáticas de PostgreSQL, **y probar a restaurar una**.
- ☐ El primer club con `ops.py crear-equipo`.
- ✅ La CI en verde en la rama que se despliega.

## Dominios separados

Si el frontend y el API viven en dominios distintos (`app.ejemplo.com` y
`api.ejemplo.com`):

- `PEAKSTROKE_CORS_ORIGINS=["https://app.ejemplo.com"]`.
- En la CSP del frontend, `connect-src 'self' https://api.ejemplo.com`.
- La cookie de refresh es `SameSite=Lax`: entre subdominios del mismo sitio
  funciona; entre sitios distintos, no. Mejor el mismo dominio.
