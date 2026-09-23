// Fichas de atleta y su vinculación con una cuenta.

export interface Swimmer {
  id: number
  name: string
  birth_date: string | null
  gender: string | null
  specialty: string
  main_stroke: string
  weight_kg: number | null
  height_cm: number | null
  notes: string | null
  created_at: string
  age: number | null
  user_id: number | null
  /** Email de la cuenta ligada, si la ficha ya tiene una. */
  user_email: string | null
  /** Los atletas se dan de baja, no se borran. */
  is_active: boolean
}

/**
 * Código de vinculación vivo: emitido, sin canjear y sin caducar.
 *
 * No viaja dentro de `Swimmer` a propósito — el backend lo sirve aparte
 * (`GET /link-codes/`) para no tener la definición de "código vivo" en dos
 * módulos. Quien pinte el estado de una ficha cruza las dos listas por
 * `swimmer_id`.
 */
export interface LinkCode {
  id: number
  swimmer_id: number
  swimmer_name: string
  /** A quién va dirigido, si se emitió desde el correo. */
  invited_email: string | null
  /** Ya formateado con guion: `ABCD-2345`. */
  code: string
  expires_at: string
  created_at: string
}

/** Alta de un atleta al equipo por su correo: ficha + cuenta + código. */
export interface InviteResult {
  link_code: LinkCode
  account_created: boolean
  /** Solo si la cuenta se acaba de crear. No se puede volver a consultar. */
  temporary_password: string | null
}

/**
 * Una solicitud de ingreso, vista desde el lado del atleta.
 *
 * **Sin el código, a propósito**: teclearlo es la prueba de que quien acepta es
 * quien el entrenador invitó. Enseñarlo aquí lo dejaría en un botón.
 */
export interface JoinRequest {
  team_name: string
  swimmer_name: string
  invited_by: string | null
  expires_at: string
  created_at: string
}
