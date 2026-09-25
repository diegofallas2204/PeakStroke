"""Borra los eventos de auditoría de más de 24 meses (R11, 2026-09-24).

Es la única escritura que borra de `auditoria`, y la base solo la deja pasar
sobre filas caducadas: si esto intentara llevarse algo más reciente, el trigger
de la migración `e3a9d0c41b7f` abortaría la purga entera. Retira además la
clave HMAC de periodos pasados, por si no hubo tráfico que la retirase. Se
registra a sí misma como `auditoria.purgada`, así que borrar también deja rastro.

Pensada para un cron mensual; correrla dos veces seguidas no hace nada.

    python tools/purgar_auditoria.py
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core import model_registry  # noqa: F401
from app.core.anonimizacion import periodo_de
from app.core.auditoria import TipoDeEvento, auditar, contexto_de_auditoria
from app.core.database import AsyncSessionLocal, engine
from app.persistencia.repositorios.auditoria import RepositorioDeAuditoria
from app.persistencia.tablas.auditoria import PERIODO_DE_CLAVE_DIAS, RETENCION_MESES


async def main() -> None:
    async with contexto_de_auditoria(user_agent="tools/purgar_auditoria.py"):
        async with AsyncSessionLocal() as db:
            repo = RepositorioDeAuditoria(db)
            borrados = await repo.purgar_caducados()
            await repo.retirar_claves_anteriores_a(
                periodo_de(datetime.now(UTC), PERIODO_DE_CLAVE_DIAS),
            )
            await db.commit()
        auditar(
            TipoDeEvento.AUDITORIA_PURGADA,
            detalle=f"{borrados} evento(s) de más de {RETENCION_MESES} meses",
        )
    print(f"auditoria: {borrados} evento(s) de más de {RETENCION_MESES} meses borrados")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
