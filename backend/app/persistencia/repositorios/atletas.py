"""El agregado Atleta: la ficha deportiva del nadador.

Era la mitad de lectura de `modules/swimmers/service.py`. Las dos fronteras del
sistema pasan por aquí y hay que pasar las dos, igual que en los macrociclos: el
equipo evita devolver la ficha de otro club, y `scope_to_own_swimmer` evita
devolverle al atleta la del compañero de calle.

Las lecturas de lista devuelven filas: la respuesta del API se valida sobre la
fila. Para cambiar una ficha se pide la entidad (`por_id`), se le pregunta o se
la cambia (`dar_de_baja()`, `restaurar()`) y se devuelve a `guardar`.

**`guardar()` es la puerta del alta para todos**: el entrenador, la invitación
por correo (`codigos`, que así no llama a otra rebanada) y el seed construyen
la ficha con `Atleta.nueva(...)` y la guardan aquí. Que las tres pasen por el
mismo sitio es lo que garantiza que creen la misma ficha.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.dominio.entidades import Atleta
from app.persistencia.mapeo import atleta_desde_fila
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

    async def por_id(self, swimmer_id: int) -> Atleta | None:
        """La entidad, para preguntarle o cambiarla. `None` si no es visible (404)."""
        fila = await self.fila_de(swimmer_id)
        return atleta_desde_fila(fila) if fila is not None else None

    # ── Escrituras ───────────────────────────────────────────────────────────
    #
    # Una sola puerta: `guardar(Atleta)`. Crear, editar, dar de baja y
    # restaurar pasan por la entidad y llegan aquí (C9, 2026-10-05). Hasta
    # entonces había tres métodos que tocaban la fila —`crear`, `actualizar`
    # con un diccionario de columnas y `cambiar_alta`— y la ficha se escribía
    # sin pasar nunca por el `Atleta`.

    async def guardar(self, atleta: Atleta) -> Swimmer | None:
        """Crea la ficha (sin `id`) o la sobrescribe (con `id`). Confirma.

        Devuelve la **fila**, porque la respuesta del API se valida sobre ella
        (lleva `created_at`, que la entidad no tiene). `None` si la ficha que se
        quiere sobrescribir no es visible para quien escribe: el router, 404.

        El equipo sale del `Principal`, nunca de la entidad ni de la petición.
        **`usuario_id` no se escribe aquí**: ligar ficha y cuenta es del canje
        del código (`codigos`), y editar una ficha no puede ser otra puerta para
        hacerlo. Estilo y género se escriben canónicos (`.value`) aunque la fila
        viniera con un alias.
        """
        if atleta.id is None:
            fila = Swimmer(team_id=self.principal.team_id)
            self.db.add(fila)
        else:
            fila = await self.fila_de(atleta.id)
            if fila is None:
                return None
        fila.name = atleta.nombre
        fila.birth_date = atleta.nacimiento
        fila.gender = atleta.genero.value if atleta.genero else None
        fila.specialty = atleta.especialidad.value
        fila.main_stroke = atleta.estilo_principal.value
        fila.weight_kg = atleta.peso_kg
        fila.height_cm = atleta.altura_cm
        fila.notes = atleta.notas
        fila.is_active = atleta.activo
        await self.db.commit()
        await self.db.refresh(fila)
        atleta.id = fila.id
        atleta.equipo_id = fila.team_id
        return fila
