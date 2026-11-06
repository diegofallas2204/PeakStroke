"""Credenciales y sesiones de una cuenta: comprobarlas, cambiarlas y revocarlas.

Salieron de `service.py` el 2026-10-14, cuando el paso de las sesiones a la
entidad `Usuario` (REDISENO §5.1) lo habría dejado por encima de 300 líneas. Lo
que cambia de la cuenta lo decide `Usuario` (`revocar_sesiones`,
`cambiar_password`, `registrar_login`); aquí se hashea —el dominio no importa
Argon2— y se guarda por `RepositorioDeUsuarios`.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, needs_rehash, verify_password
from app.persistencia.repositorios import RepositorioDeUsuarios
from app.persistencia.repositorios.usuarios import CredencialesCambiadas
from app.persistencia.tablas.usuarios import User


async def revoke_sessions(db: AsyncSession, user: User) -> None:
    """Invalida todos los tokens ya emitidos para esa cuenta (`Usuario.revocar_sesiones`).

    Cualquier access o refresh de la generación anterior deja de validar en la
    siguiente petición — no en 15 minutos ni en 30 días —, y `guardar` borra sus
    sesiones abiertas en la misma transacción (TODO-30). Lo usa `/logout-all`;
    `/logout` y el reuso ya no: cerrar **un** dispositivo es borrar su sesión.
    """
    usuarios = RepositorioDeUsuarios(db)
    usuario = usuarios.entidad(user)
    usuario.revocar_sesiones()
    await usuarios.guardar(usuario)


async def change_password(db: AsyncSession, user: User, new_password: str) -> User:
    """Cambia la contraseña y revoca todas las sesiones, en un solo `commit`.

    Hasta el 2026-10-14 eran dos llamadas desde el router —fijar el hash y luego
    revocar— con un `commit` cada una: si la segunda fallaba, la contraseña
    quedaba cambiada y las sesiones del atacante, vivas. `Usuario.cambiar_password`
    no deja hacer una cosa sin la otra.
    """
    usuarios = RepositorioDeUsuarios(db)
    usuario = usuarios.entidad(user)
    usuario.cambiar_password(hash_password(new_password))
    # Condicional (vuelta 2 del revisor de TODO-30): si otra petición cambió la
    # contraseña desde que se verificó, `CredencialesCambiadas` sube al router.
    return await usuarios.cambiar_password(usuario)


async def comprobar_credenciales(
    db: AsyncSession, email: str, password: str,
) -> tuple[User | None, str]:
    """La cuenta si las credenciales son válidas, o `None`, y **por qué** no.

    Un único `None` para "no existe", "contraseña incorrecta", "cuenta
    desactivada" y "cambió mientras se verificaba": distinguirlos en la
    respuesta permitiría enumerar qué emails están registrados. El motivo es
    para la auditoría, NUNCA para la respuesta, que sigue siendo el mismo 401.
    Cincuenta `cuenta_inexistente` son un barrido; cincuenta
    `password_incorrecta` sobre una cuenta, un ataque a esa cuenta.

    `authenticate`, que solo devolvía la cuenta, se retiró con TODO-30:
    `/me/password` necesita el motivo para auditar la carrera.
    """
    usuarios = RepositorioDeUsuarios(db)
    user = await usuarios.por_correo(email)
    if user is None:
        # Hash de descarte para que la respuesta tarde lo mismo exista o no el
        # usuario. Sin esto, el tiempo de respuesta delata qué emails son reales.
        hash_password(password)
        return None, "cuenta_inexistente"
    if not verify_password(password, user.password_hash):
        return None, "password_incorrecta"
    if not user.is_active:
        return None, "cuenta_desactivada"

    usuario = usuarios.entidad(user)
    usuario.registrar_login(
        datetime.now(UTC),
        nuevo_hash=hash_password(password) if needs_rehash(user.password_hash) else None,
    )
    try:
        return await usuarios.registrar_acceso(usuario), ""
    except CredencialesCambiadas:
        # La contraseña cambió mientras se verificaba (Argon2 tarda ~200 ms):
        # la que se tecleó ya no es la de la cuenta.
        return None, "credenciales_cambiadas"
