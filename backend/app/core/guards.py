"""Lo que se le exige a quien llama para dejarle pasar.

`dependencies.py` resuelve **quién** hace la petición; aquí solo se decide si ese
quién alcanza. La separación importa porque son dos preguntas con dos respuestas
distintas: no saber quién eres es un 401, y no alcanzar es un 403.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.auditoria import TipoDeEvento, auditar
from app.core.dependencies import get_current_principal
from app.core.principal import Principal
from app.persistencia.tablas.equipos import ROLE_COACH

logger = logging.getLogger(__name__)


def require_role(*roles: str) -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Dependencia que exige uno de los roles indicados dentro del equipo.

    **Comprueba el rol siempre, también con el login apagado.** Hasta el
    2026-08-06 había aquí un atajo que devolvía el principal sin mirar nada si
    `auth_enabled=false`, justificado en que "el usuario de desarrollo es
    siempre el mismo, así que exigir un rol concreto solo estorbaría".

    Esa premisa murió el mismo día en que se añadió `X-PeakStroke-Dev-User`. Con
    el conmutador de identidad hay un rol real —el de la cuenta suplantada— y el
    atajo pasó a ser un agujero: un atleta llamaba
    `PATCH /auth/members/{su_id} {"role":"coach"}`, se ascendía, y con eso
    desactivaba TODO el filtro por nadador, que solo actúa sobre atletas.

    403 y no 404 a propósito: aquí el recurso no es ajeno, es el rol el que no
    alcanza. Decirlo claro no filtra nada que quien pregunta no sepa ya.

    La única excepción es el modo desarrollador (`X-PeakStroke-Dev-Bypass`), que
    no puede existir con el login encendido. Ver `dev_identity.bypass_pedido`.
    """
    async def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role not in roles:
            exigir_o_bypass(principal, f"rol {'/'.join(roles)}")
        return principal

    return checker


def require_owner() -> Callable[..., Coroutine[Any, Any, Principal]]:
    """Solo el dueño del equipo: renombrarlo, transferir la propiedad.

    Mismo motivo que `require_role` para comprobar siempre: con el conmutador de
    identidad, un entrenador asistente puede suplantarse y la diferencia entre
    dueño y asistente es justo lo que la Fase 4 del plan quiere poder ver.
    """
    async def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not principal.is_owner:
            exigir_o_bypass(principal, "dueño del equipo")
        return principal

    return checker


def exigir_o_bypass(principal: Principal, exigido: str) -> None:
    """Lanza 403, salvo que quien pregunta esté en modo desarrollador.

    El aviso en el log no es decorativo: el modo desarrollador existe para
    desatascarse mientras se depura, y una traza que diga qué guard se saltó y
    con qué identidad es la diferencia entre *usarlo* y *olvidar que está
    puesto*. Si aparece en un log que no sea tu portátil, algo va muy mal —
    `dev_identity_enabled` tendría que haberlo hecho imposible.
    """
    if principal.is_developer:
        logger.warning(
            "MODO DESARROLLADOR: %s (%s) se salta el guard de %s",
            principal.user.email, principal.role, exigido,
        )
        # Y queda en la auditoría, que sobrevive al scroll de la consola: un
        # `dev.bypass` en una base que no sea de desarrollo es una alarma.
        auditar(
            TipoDeEvento.DEV_BYPASS, principal,
            detalle=f"{principal.role} se salta el guard de {exigido}",
        )
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Tu rol no permite esta acción (se requiere: {exigido})",
    )


# Atajos para los guards más frecuentes.
require_coach = require_role(ROLE_COACH)
require_team_owner = require_owner()
