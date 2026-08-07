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
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class AuthConfig(BaseModel):
    """Lo que el frontend necesita saber antes de decidir si pide login."""
    auth_enabled: bool


class DevIdentity(BaseModel):
    """Una cuenta que se puede suplantar desde el conmutador de desarrollo.

    Deliberadamente más pobre que `MemberResponse`: es un selector, no una ficha.
    Lo justo para pintar la lista y mandar la cabecera.
    """
    email: str
    name: str
    role: str
    is_owner: bool = False
    swimmer_name: str | None = None


class MemberCreate(BaseModel):
    """Alta de un miembro del equipo desde la sección Perfil.

    `swimmer_id` liga la cuenta a un perfil deportivo ya existente. Si se omite
    `password`, el backend genera una temporal y la devuelve una sola vez.
    """
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    role: Role = "athlete"
    password: str | None = Field(default=None, min_length=PASSWORD_MIN, max_length=128)
    swimmer_id: int | None = None


class MemberResponse(UserResponse):
    """Un usuario con su rol en el equipo y el nadador al que está ligado."""
    team_id: int
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
