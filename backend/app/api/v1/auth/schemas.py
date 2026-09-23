"""Schemas Pydantic del módulo auth."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["coach", "athlete"]

# Mínimo deliberadamente laxo en longitud pero explícito: la fortaleza real la da
# Argon2id, no una política de caracteres que solo empuja a la gente a "P@ssw0rd!".
PASSWORD_MIN = 8


class UserCreate(BaseModel):
    """Alta de cuenta. Solo la ejecuta un entrenador — no hay registro público."""
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=PASSWORD_MIN, max_length=128)
    role: Role = "athlete"


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=PASSWORD_MIN, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    # `None` = la cuenta existe pero todavía no pertenece a ningún club. Es el
    # estado de partida de quien se registra por su cuenta y espera a que un
    # entrenador lo invite. Ser entrenador o atleta es algo que se es *en* un
    # club, así que fuera de uno no hay rol que dar.
    role: str | None
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthConfig(BaseModel):
    """Lo que el frontend necesita saber antes de decidir qué pintar.

    Es el único sitio donde se pregunta "¿en qué modo estoy?", para que la barra
    de desarrollo no tenga que deducirlo de tres respuestas distintas.
    """
    auth_enabled: bool
    # Si existe el conmutador de identidad. Cuando es False el frontend no debe
    # dibujar la barra de desarrollo: las cabeceras no las lee nadie.
    dev_identities_enabled: bool = False
    # Si ESTA petición viaja en modo desarrollador. Sale de la cabecera que la
    # propia petición mandó, así que la barra puede reflejar el estado real en
    # vez de recordar lo que creía haber puesto.
    dev_bypass_active: bool = False
    # Los nombres de las cabeceras, para que el cliente no los lleve a fuego.
    dev_user_header: str | None = None
    dev_bypass_header: str | None = None


class DevIdentity(BaseModel):
    """Una cuenta que se puede suplantar desde el conmutador de desarrollo.

    Deliberadamente más pobre que `MemberResponse`: es un selector, no una ficha.
    Lo justo para pintar la lista y mandar la cabecera.
    """
    email: str
    name: str
    # `None` = cuenta del pool, sin club todavía. Ver `MemberResponse.role`.
    role: str | None
    is_owner: bool = False
    swimmer_name: str | None = None


class MemberCreate(BaseModel):
    """Alta de un miembro del equipo desde la sección Perfil.

    Si se omite `password`, el backend genera una temporal y la devuelve una
    sola vez.

    **Ya no lleva `swimmer_id`.** Hasta el 2026-08-09 el entrenador elegía aquí
    a qué ficha quedaba ligada la cuenta, de un desplegable y sin que nadie del
    otro lado confirmara nada. Ese vínculo ahora se crea canjeando un código
    (`api/v1/codigos/`): lo emite el entrenador y lo canjea la persona, y
    hasta que no ocurren las dos cosas no hay relación.
    """
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    role: Role = "athlete"
    password: str | None = Field(default=None, min_length=PASSWORD_MIN, max_length=128)


class MemberResponse(UserResponse):
    """Un usuario con su rol en el equipo y el nadador al que está ligado.

    `team_id` y `role` van a `None` juntos: es la cuenta que todavía no está en
    ningún club. La interfaz lo lee como "solo puedes ver tu perfil, y ahí están
    tus solicitudes de ingreso".
    """
    team_id: int | None
    team_name: str | None = None
    # Entrenador en jefe = entrenador que además es dueño del equipo.
    is_owner: bool = False
    swimmer_id: int | None = None
    swimmer_name: str | None = None


class MemberCreated(BaseModel):
    member: MemberResponse
    # Solo viene rellena si la generó el backend. No se puede volver a consultar:
    # lo que se guarda es el hash.
    temporary_password: str | None = None


class SessionResponse(BaseModel):
    """Lo que devuelve /login y /refresh.

    El access token va en el cuerpo (el cliente lo guarda en memoria); el refresh
    NO aparece aquí a propósito — viaja en cookie httpOnly, fuera del alcance de
    cualquier script de la página.
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int          # segundos de vida del access token
    # MemberResponse y no UserResponse: el cliente necesita el rol y el equipo
    # para decidir qué enseñar nada más entrar.
    user: MemberResponse
