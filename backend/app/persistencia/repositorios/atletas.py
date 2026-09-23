"""El agregado Atleta: la ficha deportiva del nadador.

Era la mitad de lectura de `modules/swimmers/service.py`. Las dos fronteras del
sistema pasan por aquí y hay que pasar las dos, igual que en los macrociclos: el
equipo evita devolver la ficha de otro club, y `scope_to_own_swimmer` evita
devolverle al atleta la del compañero de calle.

Devuelve filas y no `Atleta`: la respuesta del API se valida sobre la fila, y la
entidad la construye quien necesita preguntarle algo —hoy solo la edad, en
`api/v1/atletas/service.to_response`—.

**`crear()` existe para que `codigos` no tenga que llamar a otra rebanada.** Dar
de alta a un atleta por su correo crea la ficha, la cuenta y el código en un
gesto (2026-08-10), y hasta el paso 5 eso se hacía importando
`swimmers.service.create_swimmer` desde `link_codes` — lógica cruzada de manual.
Ahora las dos puertas —el alta directa del entrenador y la invitación— pasan por
el mismo método, que es lo que garantiza que creen la misma ficha.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.persistencia.tablas.atletas import Swimmer


class RepositorioDeAtletas:
    """Las fichas que alcanza un `Principal`, y nada más."""

    __slots__ = ("db", "principal")

    def __init__(self, db: AsyncSession, principal: Principal) -> None:
        self.db = db
        self.principal = principal

    # ── El filtro ────────────────────────────────────────────────────────────

    def acotar(self, stmt):
        """Equipo + nadador propio. Las dos fronteras, en un sitio.

        `Swimmer.id` y no `Swimmer.user_id`: el nadador ligado a la cuenta lo
        resolvió ya el `Principal`, llevando el equipo en la condición del join.
        """
        stmt = stmt.where(Swimmer.team_id == self.principal.team_id)
        return self.principal.scope_to_own_swimmer(stmt, Swimmer.id)

    # ── Lecturas ─────────────────────────────────────────────────────────────

    async def filas(
        self, *, busqueda: str | None = None, incluir_de_baja: bool = False,
    ) -> list[Swimmer]:
        """El equipo entero para un entrenador; solo su propia ficha para un atleta."""
        stmt = self.acotar(select(Swimmer).order_by(Swimmer.name))
        if not incluir_de_baja:
            stmt = stmt.where(Swimmer.is_active.is_(True))
        if busqueda:
            stmt = stmt.where(Swimmer.name.ilike(f"%{busqueda}%"))
        return list((await self.db.execute(stmt)).scalars())

    async def fila_de(self, swimmer_id: int) -> Swimmer | None:
        """`None` si es de otro equipo o de otro atleta.

        El router traduce ese `None` a un 404: un 403 confirmaría que ese id
        existe en algún sitio, que es justo lo que no queremos filtrar.
        """
        stmt = self.acotar(select(Swimmer).where(Swimmer.id == swimmer_id))
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── Escrituras ───────────────────────────────────────────────────────────
    #
    # Todas están detrás de `require_coach`; un atleta no llega a ellas. El
    # equipo sale de la sesión, nunca del cuerpo de la petición.

    async def crear(
        self, *, team_id: int, nombre: str, nacimiento: date | None = None,
        genero: str | None = None, especialidad: str = "medio_fondo",
        estilo_principal: str = "libre", peso_kg: float | None = None,
        altura_cm: float | None = None, notas: str | None = None,
    ) -> Swimmer:
        fila = Swimmer(
            team_id=team_id, name=nombre, birth_date=nacimiento, gender=genero,
            specialty=especialidad, main_stroke=estilo_principal,
            weight_kg=peso_kg, height_cm=altura_cm, notes=notas,
        )
        self.db.add(fila)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

    async def actualizar(self, fila: Swimmer, cambios: dict[str, object]) -> Swimmer:
        for campo, valor in cambios.items():
            setattr(fila, campo, valor)
        await self.db.commit()
        await self.db.refresh(fila)
        return fila

    async def cambiar_alta(self, fila: Swimmer, activa: bool) -> Swimmer:
        """Da de baja (o reactiva) al nadador.

        Sustituye al borrado: su histórico de entrenamiento —semanas, tiempos
        reales, tests aeróbicos— es el activo más valioso de la aplicación y no
        debe evaporarse por un clic. Los macrociclos en los que participa siguen
        intactos.
        """
        fila.is_active = activa
        await self.db.commit()
        await self.db.refresh(fila)
        return fila
