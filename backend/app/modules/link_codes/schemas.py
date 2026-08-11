"""Schemas Pydantic del módulo link_codes."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.modules.swimmers.schemas import Gender, MainStroke, Specialty


class LinkCodeCreate(BaseModel):
    swimmer_id: int


class InviteRequest(BaseModel):
    """Alta de un atleta al equipo, por el correo con el que se registra.

    Un solo gesto donde antes había tres (crear cuenta → crear ficha → emitir
    código). Los campos deportivos son los mismos de `SwimmerCreate`: se repiten
    aquí en vez de anidar el schema porque esto es un formulario, no una
    composición de recursos, y anidarlo obligaría al cliente a mandar
    `{"email": ..., "swimmer": {...}}` para dar de alta a una persona.
    """

    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    birth_date: date | None = None
    gender: Gender | None = None
    specialty: Specialty = "medio_fondo"
    main_stroke: MainStroke = "libre"
    notes: str | None = None

    @field_validator("birth_date")
    @classmethod
    def _not_future(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("La fecha de nacimiento no puede ser futura")
        return value


class LinkCodeResponse(BaseModel):
    id: int
    swimmer_id: int
    swimmer_name: str
    # A quién va dirigido, si se emitió desde el correo. `None` en los emitidos
    # sobre una ficha suelta.
    invited_email: str | None = None
    # Con el guion puesto: es lo que se dicta por teléfono y lo que se copia.
    code: str
    expires_at: datetime
    created_at: datetime


class InviteResponse(BaseModel):
    """Lo que el entrenador tiene que entregarle a la persona.

    `temporary_password` solo viene cuando la cuenta se acaba de crear aquí, y
    solo esta vez: lo que se guarda es el hash. Si la persona ya tenía cuenta,
    entra con la suya y este campo va vacío.
    """

    link_code: LinkCodeResponse
    account_created: bool
    temporary_password: str | None = None


class JoinRequestResponse(BaseModel):
    """Una solicitud de ingreso vista **desde el lado del atleta**.

    Deliberadamente sin el código: quien lo tiene que teclear es la persona, y
    dárselo hecho anularía la comprobación de identidad que el código existe
    para hacer. Aquí solo va lo que necesita para reconocer la invitación —de
    qué club es y hasta cuándo vale.
    """

    team_name: str
    swimmer_name: str
    invited_by: str | None = None
    expires_at: datetime
    created_at: datetime


class RedeemRequest(BaseModel):
    # 20 caracteres de holgura para aceptar el guion, los espacios y las
    # minúsculas: `service.normalize_code` se encarga, y rechazar por formato lo
    # que solo está mal escrito produce un 422 que no ayuda a nadie.
    code: str = Field(min_length=4, max_length=20)


class RedeemResponse(BaseModel):
    swimmer_id: int
    swimmer_name: str
    team_id: int
    team_name: str
