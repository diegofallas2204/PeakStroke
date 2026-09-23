// Cuentas, equipo y conmutador de identidad de desarrollo.

export type Role = 'coach' | 'athlete'

/** Un usuario junto con el nadador al que está ligado, si lo está. */
export interface Member {
  id: number
  email: string
  name: string
  /**
   * `null` = la cuenta existe pero no está en ningún club todavía.
   *
   * Es el estado de quien espera invitación, y no es lo mismo que `undefined`
   * («la sesión aún no cargó»): con `null` ya se sabe quién es, y lo que se
   * sabe es que solo puede ver su perfil.
   */
  role: Role | null
  is_active: boolean
  created_at: string
  last_login_at: string | null
  team_id: number | null
  team_name: string | null
  /** Entrenador en jefe = entrenador que además es dueño del equipo. */
  is_owner: boolean
  swimmer_id: number | null
  swimmer_name: string | null
}

export interface Team {
  id: number
  name: string
  owner_id: number | null
  owner_name: string | null
  is_owner: boolean
  coaches: number
  athletes: number
  swimmers: number
}

export interface MemberCreated {
  member: Member
  /** Solo si la generó el backend; no se puede volver a consultar. */
  temporary_password: string | null
}

export interface AuthConfig {
  auth_enabled: boolean
  /** Si existe el conmutador de desarrollo. False ⇒ no dibujar la barra. */
  dev_identities_enabled: boolean
  /** Si ESTA petición viajó en modo desarrollador (sale de la cabecera que se mandó). */
  dev_bypass_active: boolean
  /** Nombres de las cabeceras, para no llevarlos a fuego en el cliente. */
  dev_user_header: string | null
  dev_bypass_header: string | null
}

/** Una cuenta que el conmutador de desarrollo puede suplantar. */
export interface DevIdentity {
  email: string
  name: string
  /** `null` = cuenta del pool, sin club todavía. */
  role: string | null
  is_owner: boolean
  swimmer_name: string | null
}
