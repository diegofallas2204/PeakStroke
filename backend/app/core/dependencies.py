"""
dependencies.py — FastAPI dependencies reutilizables en toda la app.

Expone:
  get_current_user  → retorna el User activo desde el JWT
  require_feature   → guarda de tier (lanza 403 si el tier no tiene el feature)
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.tier_limits import get_tier_limit

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Extrae y valida el JWT. Retorna el objeto User de la base de datos.
    Lanza 401 si el token es inválido o el usuario no existe.
    """
    # Importación tardía para evitar ciclos
    from app.modules.auth.service import get_user_by_id

    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )
    return user


def require_feature(feature: str):
    """
    Dependency factory que verifica si el tier del usuario tiene acceso al feature.

    Uso:
        @router.get("/export")
        async def export(user = Depends(require_feature("export"))):
            ...
    """
    async def checker(current_user=Depends(get_current_user)):
        tier = getattr(current_user, "tier", "free")
        if not get_tier_limit(tier, feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tu plan '{tier}' no incluye '{feature}'. Actualiza tu suscripción.",
            )
        return current_user
    return checker
