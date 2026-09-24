"""Registrar lo que pasa, sin que registrarlo pueda tumbar nada (D0, 2026-09-24).

Quien produce un evento llama a `auditar(...)`, que es **síncrona y no toca la
base de datos**: solo lo apunta en el contexto de la petición en curso. El
middleware (`MiddlewareDeAuditoria`) vuelca lo apuntado **cuando la petición
ya terminó**, en una sesión propia. De ahí salen las tres propiedades que D0
exige:

1. **Un fallo de la auditoría no afecta a la petición.** Cuando se escribe, la
   respuesta ya se envió; y si la escritura falla, se registra en el log del
   servidor con un `ERROR` que lleva los eventos perdidos —el último rastro— y
   se sigue.
2. **El coste en la petición es una lista y un `append`.** Una petición que no
   produce eventos (casi todas) no toca la base de datos por la auditoría.
3. **No compite por el bloqueo de SQLite.** La sesión de la petición ya cerró
   su transacción cuando la de la auditoría abre la suya.

El precio de (1): si el proceso muere entre enviar la respuesta y escribir, esos
eventos se pierden. Es una ventana de milisegundos, y es el mismo precio que
paga cualquier log que no quiere estar en el camino crítico.

**Se llama a `auditar` DESPUÉS de que la operación se confirme**, no antes: un
evento `ok` de algo que luego falló al confirmar sería mentira.

Fuera de una petición (un script, un test que llama al servicio directamente)
no hay contexto, y el evento se descarta con un aviso. Un script que quiera
registrar abre el suyo con `contexto_de_auditoria()` — lo usa la purga.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.anonimizacion import familia_de, huella_de, periodo_de, red_de
from app.core.database import AsyncSessionLocal
from app.core.principal import Principal
from app.persistencia.repositorios.auditoria import RepositorioDeAuditoria
from app.persistencia.tablas.auditoria import (
    FALLO,
    OK,
    PERIODO_DE_CLAVE_DIAS,
    EventoDeAuditoria,
)
from app.persistencia.tablas.usuarios import User

logger = logging.getLogger(__name__)


class TipoDeEvento(StrEnum):
    # Acceso y sesión — lo que enseña `v_admin_accesos`.
    LOGIN = "sesion.login"
    REFRESH_REUSADO = "sesion.refresh_reusado"
    LOGOUT = "sesion.logout"
    PASSWORD_CAMBIADA = "cuenta.password_cambiada"
    DEV_BYPASS = "dev.bypass"
    # Actividad sobre cuentas, equipos y registros.
    CUENTA_CREADA = "cuenta.creada"
    ROL_CAMBIADO = "miembro.rol_cambiado"
    MIEMBRO_REVOCADO = "miembro.revocado"
    MIEMBRO_RESTAURADO = "miembro.restaurado"
    PROPIEDAD_TRANSFERIDA = "equipo.propiedad_transferida"
    CODIGO_EMITIDO = "codigo.emitido"
    CODIGO_CANJEADO = "codigo.canjeado"
    CODIGO_REVOCADO = "codigo.revocado"
    NADADOR_BAJA = "nadador.baja"
    NADADOR_RESTAURADO = "nadador.restaurado"
    TEST_BAJA = "test_aerobico.baja"
    TEST_RESTAURADO = "test_aerobico.restaurado"
    INSCRIPCION_BAJA = "inscripcion.baja"
    INSCRIPCION_RESTAURADA = "inscripcion.restaurada"
    MACROCICLO_BORRADO = "macrociclo.borrado"
    AUDITORIA_PURGADA = "auditoria.purgada"


# Los que forman `v_admin_accesos`. La vista los filtra en SQL; un test comprueba
# que los dos conjuntos son el mismo.
TIPOS_DE_ACCESO = frozenset({
    TipoDeEvento.LOGIN, TipoDeEvento.REFRESH_REUSADO, TipoDeEvento.LOGOUT,
    TipoDeEvento.PASSWORD_CAMBIADA, TipoDeEvento.DEV_BYPASS,
})


@dataclass(slots=True)
class _Apunte:
    momento: datetime
    tipo: TipoDeEvento
    resultado: str
    actor_id: int | None
    actor_email: str | None
    team_id: int | None
    objetivo: tuple[str, int] | None
    detalle: str


@dataclass(slots=True)
class ContextoDeAuditoria:
    """Lo que la auditoría sabe de la petición en curso: origen y apuntes."""

    ip: str | None = None
    user_agent: str | None = None
    apuntes: list[_Apunte] = field(default_factory=list)


_contexto: ContextVar[ContextoDeAuditoria | None] = ContextVar("auditoria", default=None)
# Una clave por periodo y por proceso: pedirla a la base en cada volcado
# costaría una consulta por petición auditada.
_claves: dict[int, bytes] = {}


def auditar(
    tipo: TipoDeEvento, quien: Principal | User | None = None, *,
    correo: str | None = None, equipo: int | None = None,
    objetivo: tuple[str, int] | None = None, fallo: bool = False, detalle: str = "",
) -> None:
    """Apunta un evento en la petición en curso. **Nunca lanza.**

    `quien` rellena el actor (y el equipo, si es un `Principal`). `correo` es
    para cuando no hay cuenta —un login con un correo que no existe—.
    """
    ctx = _contexto.get()
    if ctx is None:
        logger.warning("AUDITORÍA: %s fuera de una petición; no se guarda", tipo)
        return
    user = quien.user if isinstance(quien, Principal) else quien
    if equipo is None and isinstance(quien, Principal):
        equipo = quien.team_id
    ctx.apuntes.append(_Apunte(
        momento=datetime.now(UTC), tipo=tipo, resultado=FALLO if fallo else OK,
        actor_id=user.id if user is not None else None,
        actor_email=(user.email if user is not None else correo),
        team_id=equipo, objetivo=objetivo, detalle=detalle,
    ))


def _fila(apunte: _Apunte, ctx: ContextoDeAuditoria, clave: bytes) -> EventoDeAuditoria:
    tipo_objetivo, id_objetivo = apunte.objetivo or (None, None)
    return EventoDeAuditoria(
        occurred_at=apunte.momento, event_type=str(apunte.tipo), outcome=apunte.resultado,
        actor_user_id=apunte.actor_id,
        actor_email=apunte.actor_email[:255] if apunte.actor_email else None,
        team_id=apunte.team_id, target_type=tipo_objetivo, target_id=id_objetivo,
        ip_network=red_de(ctx.ip), ip_hash=huella_de(ctx.ip, clave),
        user_agent=(familia_de(ctx.user_agent) or "")[:60] or None,
        detail=apunte.detalle[:200],
    )


async def volcar(ctx: ContextoDeAuditoria) -> None:
    """Escribe los apuntes en su propia sesión. Si falla, lo dice y sigue."""
    if not ctx.apuntes:
        return
    apuntes, ctx.apuntes = ctx.apuntes, []
    try:
        async with AsyncSessionLocal() as db:
            repo = RepositorioDeAuditoria(db)
            periodo = periodo_de(apuntes[0].momento, PERIODO_DE_CLAVE_DIAS)
            if periodo not in _claves:
                _claves.clear()  # la del periodo anterior ya no debe usarse
                _claves[periodo] = await repo.clave_del_periodo(periodo)
            repo.anotar([_fila(a, ctx, _claves[periodo]) for a in apuntes])
            await db.commit()
    except Exception:
        # El último rastro: si la tabla no los guarda, que al menos el log diga
        # qué se perdió. Sin la IP, que en el log no pasa por la anonimización.
        logger.exception(
            "AUDITORÍA: no se pudieron guardar %d evento(s); la petición siguió "
            "adelante. Perdidos: %s", len(apuntes),
            "; ".join(
                f"{a.momento.isoformat()} {a.tipo} {a.resultado} {a.actor_email or '-'}"
                for a in apuntes
            ),
        )


@asynccontextmanager
async def contexto_de_auditoria(
    ip: str | None = None, user_agent: str | None = None,
) -> AsyncIterator[ContextoDeAuditoria]:
    """Abre un contexto, y al cerrarlo vuelca lo apuntado dentro."""
    ctx = ContextoDeAuditoria(ip=ip, user_agent=user_agent)
    token = _contexto.set(ctx)
    try:
        yield ctx
    finally:
        _contexto.reset(token)
        await volcar(ctx)


class MiddlewareDeAuditoria:
    """ASGI puro: sin `BaseHTTPMiddleware`, que añade una tarea por petición.

    Todo lo que corre dentro de la petición ve el mismo `ContextoDeAuditoria`,
    y cuando la aplicación termina —respuesta enviada, sesión de la petición
    cerrada— se vuelca. También si la petición acabó en excepción: el `finally`
    de `contexto_de_auditoria` lo garantiza.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        cliente = scope.get("client")
        user_agent = next(
            (v.decode("latin-1") for k, v in scope.get("headers", ()) if k == b"user-agent"),
            None,
        )
        async with contexto_de_auditoria(
            ip=cliente[0] if cliente else None, user_agent=user_agent,
        ):
            await self.app(scope, receive, send)
