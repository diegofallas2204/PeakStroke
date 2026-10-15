# `backend/tools/` — lo que se corre a mano en el servidor

Todo se ejecuta **desde `backend/`**, contra la base de `PEAKSTROKE_DATABASE_URL`
(sin ella, la de desarrollo, `backend/peakstroke.db`).

| Herramienta | Para qué | Cuándo |
|---|---|---|
| `ops.py` | El CLI de operaciones: clubes, cuentas, acceso, sesiones, contraseña, propiedad, salud | Cuando haga falta: son las operaciones que **no** tienen interfaz web |
| `purgar_auditoria.py` | Borra los eventos de auditoría de más de 24 meses (R11) | Cron mensual |
| `recalcular_carga.py` | Reconstruye `carga_diaria` desde cero | Tras la migración que la crea, o si se sospecha que se desincronizó |
| `grafo_de_imports.py` | Imprime el grafo de capas de `app/` y marca las flechas que suben | Al revisar la arquitectura; `test_dependencias_de_capas.py` ya lo comprueba |

---

## `ops.py` — el CLI de operaciones (D1)

```bash
.venv\Scripts\python tools/ops.py --help
.venv\Scripts\python tools/ops.py <comando> --help
```

Por qué es un CLI y no una web: se corre por SSH en el servidor, así que **no hay
puerto, ni endpoint, ni sesión que robar**. Se hace tres veces al año.

### Lo que vale para todos

- **Todo comando que escribe audita** en la tabla `auditoria`, con el usuario del
  sistema operativo como actor: `actor_email = os:<usuario>@<host>`, y en `detail`
  el comando que lo produjo. PSAdmin lo ve en `v_admin_accesos` o
  `v_admin_actividad`.
- **Los destructivos piden escribir el nombre del recurso**: el correo de la
  cuenta, o el nombre del club en `transferir`. Cualquier otra cosa cancela sin
  tocar nada. Para scripts, se puede pasar por la entrada estándar
  (`echo correo@club.com | python tools/ops.py revocar --correo correo@club.com`).
- **Todo comando que escribe tiene `--dry-run`**: hace todas las comprobaciones,
  dice lo que haría y no escribe **ni audita**.
- **Ninguna contraseña entra por argumento.** Quedaría en el historial del shell y
  en la lista de procesos. O se genera una temporal, que se enseña **una sola
  vez**, o se lee de la entrada estándar con `--password-stdin` (con terminal, sin
  eco y dos veces).
- **No escribe sobre una base sin migrar**: si la base no está en el head de
  Alembic, los comandos que escriben se niegan. `salud` dice en qué revisión está.
- Las reglas son las del API, no unas propias: el dueño no se queda sin acceso,
  solo un entrenador activo del club puede ser dueño, los correos se guardan en
  minúsculas y las validaciones de correo, nombre y contraseña son las de
  `UserCreate`.
- Sale con **0** si todo fue bien, **1** si se rechazó (el motivo va a stderr),
  **2** en `salud` si la base no está al día y **3** si la operación **se hizo
  pero su evento de auditoría no se pudo guardar**: el log de stderr dice cuál
  era, y hay que apuntarlo a mano. Nunca pasa en silencio.

### Los comandos

| Comando | Qué hace | Destructivo | Evento |
|---|---|---|---|
| `crear-equipo --nombre-equipo N --correo C --nombre M [--password-stdin]` | Crea un club y su dueño, un entrenador. Es el arranque en frío: sin él, no hay nadie que pueda crear nada desde la web | no | `equipo.creado` + `cuenta.creada` |
| `crear-cuenta --correo C --nombre M [--rol coach\|athlete] [--equipo ID] [--password-stdin]` | Da de alta una cuenta en un club. Con un solo club, se deduce. **A un atleta se le da de alta mejor por invitación** (`POST /link-codes/invite`), que crea ficha, cuenta y código juntos; esto crea solo la cuenta | no | `cuenta.creada` |
| `revocar --correo C` | Le quita el acceso al club **y corta todas sus sesiones** en el mismo commit. Sigue siendo del club: no puede entrar en otro (revocado ≠ sin equipo). Al dueño no se le revoca: primero `transferir` | sí | `miembro.revocado` |
| `restaurar --correo C` | Le devuelve el acceso al club. No toca sus sesiones | no | `miembro.restaurado` |
| `liberar --correo C` | Deja en el pool a un **atleta ya revocado**: borra su pertenencia, desliga su ficha (que se queda en el club con su histórico) y corta sus sesiones. Después puede canjear un código de otro club. **No se deshace**: para volver, hay que invitarlo de nuevo. No vale para entrenadores, que dejan historia en el club | sí | `miembro.liberado` |
| `cortar-sesiones --correo C` | Invalida todos sus tokens (access y refresh): tendrá que volver a entrar. Para una cuenta que se sospecha comprometida | sí | `sesion.cortadas` |
| `restablecer-password --correo C` | Le pone una contraseña temporal, que se enseña **una vez**, y corta sus sesiones. Para quien olvidó la suya: no hay recuperación por correo | sí | `cuenta.password_restablecida` |
| `transferir --a C [--equipo ID]` | Cede la propiedad del club a otro entrenador activo. Se confirma escribiendo **el nombre del club** | sí | `equipo.propiedad_transferida` |
| `salud` | Versión, entorno, base (sin contraseña), si las migraciones están al día y conteos de personas (nunca datos deportivos). **Solo lee y no audita**: funciona también sobre una base sin migrar | no | — |

### Liberar o revocar

Son dos gestos distintos a propósito (TODO-26, decidido el 2026-10-14):

- **Revocar** es echar: la persona sigue siendo del club y no entra en ningún
  sitio hasta que el club la restaure.
- **Liberar** es dejarla ir: sin club, puede entrar en otro. Solo se libera lo
  que ya está revocado, así que en la auditoría quedan los dos pasos.

### Lo que no está aquí

- **Las cuentas de PSAdmin**: son del bloque D2, con su tabla, su 2FA y su sesión
  propias.
- **Borrar una cuenta**: nada se borra, se da de baja. `liberar` es la única
  excepción, y borra la pertenencia, no la cuenta.

---

## Las otras tres

### `purgar_auditoria.py`

```bash
.venv\Scripts\python tools/purgar_auditoria.py
```

Es la única escritura que borra de `auditoria`, y la base solo se lo permite
sobre eventos de **más de 24 meses**: el trigger aborta la purga entera si
intentara llevarse algo más reciente. Retira además la clave HMAC de periodos
pasados. Se registra a sí misma (`auditoria.purgada`). Correrla dos veces
seguidas no hace nada.

### `recalcular_carga.py`

```bash
.venv\Scripts\python tools/recalcular_carga.py              # todos los atletas
.venv\Scripts\python tools/recalcular_carga.py --swimmer 7  # uno
```

`carga_diaria` (CTL/ATL de Banister) se mantiene sola: cada escritura de
sesiones y tests la recalcula. Esto es para lo que no pasa por esas escrituras.
Recalcular dos veces deja lo mismo.

### `grafo_de_imports.py`

```bash
.venv\Scripts\python tools/grafo_de_imports.py
```

Imprime qué capa de `app/` importa a cuál (`api → persistencia → dominio`) y
marca las flechas que suben. Hoy no hay ninguna, y
`tests/test_dependencias_de_capas.py` falla si aparece una.
