"""Modelos del módulo teams: el equipo, la pertenencia y la asignación de atletas.

El equipo es la frontera de todo. Tres ideas que gobiernan el diseño:

1. **El rol vive en la pertenencia, no en la persona.** `TeamMember` liga usuario
   y equipo *con* un rol: ser entrenador es algo que se es *en* un club, no una
   propiedad intrínseca. Hoy `UNIQUE(user_id)` impone una persona = un equipo;
   el día que haga falta multi-equipo basta quitar esa restricción.
2. **El dueño es único y transferible** (`Team.owner_id`), y una FK compuesta
   garantiza que sea miembro de ese mismo equipo — no de otro.
3. **El aislamiento entre equipos lo impone la base de datos**, no el código. Las
   tablas de relación arrastran `team_id` y sus FKs son compuestas: asignar un
   atleta de otro club es imposible aunque el service se olvide de comprobarlo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer,
    String, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

Role = Literal["coach", "athlete"]

ROLE_COACH: Final = "coach"
ROLE_ATHLETE: Final = "athlete"
ROLES: Final[tuple[str, ...]] = (ROLE_COACH, ROLE_ATHLETE)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        # El dueño tiene que ser miembro DE ESTE equipo. Sin esta FK compuesta se
        # podría nombrar dueño a alguien de otro club con solo mandar su id.
        # use_alter: teams y team_members se referencian mutuamente, así que la
        # constraint se añade después de crear ambas tablas.
        ForeignKeyConstraint(
            ["id", "owner_id"], ["team_members.team_id", "team_members.user_id"],
            name="fk_teams_owner_is_member", use_alter=True,
        ),
    )

    # autoincrement explícito: al participar `id` en la FK compuesta de arriba,
    # SQLAlchemy asume que su valor viene del padre (como en herencia por tablas)
    # y deja de generarlo. Sin esto, insertar un equipo falla con "NULL identity key".
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120))
    # Único y transferible. Nullable por necesidad: al crear el equipo todavía no
    # existe ningún miembro al que apuntar. El service exige que sea entrenador
    # (eso no lo puede expresar una FK) y que nunca quede en NULL después.
    owner_id: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover - ayuda en consola/tests
        return f"<Team {self.id} {self.name}>"


class TeamMember(Base):
    """Pertenencia de una persona a un equipo, con su rol dentro de él."""
    __tablename__ = "team_members"
    __table_args__ = (
        # Regla de negocio: una persona pertenece a un solo equipo.
        UniqueConstraint("user_id", name="uq_team_members_user"),
        # Clave candidata a la que apuntan todas las FKs compuestas del esquema.
        # Es redundante con la anterior, pero una FK solo puede referenciar una
        # constraint que cubra exactamente sus columnas.
        UniqueConstraint("user_id", "team_id", name="uq_team_members_user_team"),
        CheckConstraint(f"role IN {ROLES!r}", name="ck_team_members_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True,
    )
    role: Mapped[str] = mapped_column(String(12), default=ROLE_ATHLETE, index=True)
    # Revocar el acceso desactiva la pertenencia; la cuenta y el histórico siguen.
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TeamMember u{self.user_id} t{self.team_id} ({self.role})>"


class CoachAthlete(Base):
    """Qué atletas lleva cada entrenador, dentro de un mismo equipo.

    Muchos a muchos en ambos sentidos: un entrenador lleva varios atletas y un
    atleta puede tener varios entrenadores (principal, de velocidad, físico…).
    """
    __tablename__ = "coach_athletes"
    __table_args__ = (
        UniqueConstraint("coach_id", "swimmer_id", name="uq_coach_athletes_pair"),
        # Entrenador y nadador tienen que ser del MISMO equipo, y ese equipo es el
        # de la fila. La base de datos lo impone; el service no puede saltárselo.
        ForeignKeyConstraint(
            ["coach_id", "team_id"], ["team_members.user_id", "team_members.team_id"],
            name="fk_coach_athletes_coach_in_team", ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["swimmer_id", "team_id"], ["swimmers.id", "swimmers.team_id"],
            name="fk_coach_athletes_swimmer_in_team", ondelete="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Redundante a propósito: es lo que permite la FK compuesta de arriba.
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    coach_id: Mapped[int] = mapped_column(Integer, index=True)
    swimmer_id: Mapped[int] = mapped_column(Integer, index=True)
    # 1 = entrenador principal del atleta. Solo ordena; no da permisos extra.
    priority: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
