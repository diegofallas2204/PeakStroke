// Qué módulos trae la build, decidido al arrancar Vite (lo usa `vite.config.ts`).
//
// En orden: la variable `VITE_MODULOS` si está puesta (en el entorno o en un
// `.env`); si no, el nombre de la rama: `modulo/<nombre>` trae solo ese módulo.
// En cualquier otra rama, todos.
//
// Por la rama y no por un archivo a propósito: si `modulo/inicio` llevara un
// `.env` propio, fusionar su trabajo de vuelta a `Preliminar` se traería
// también el interruptor, y la app de todos quedaría con un solo módulo.
import { execSync } from 'node:child_process'

/** `modulo/inicio` → `inicio`. Cualquier otra rama → `''` (todos). */
export function moduloDeRama(rama: string): string {
  const m = /(?:^|\/)modulo\/([a-z0-9-]+)$/.exec(rama.trim())
  return m ? m[1] : ''
}

/** La rama actual: la de GitHub Actions si corre allí, o la de git. */
function ramaActual(): string {
  const deCi = process.env.GITHUB_HEAD_REF || process.env.GITHUB_REF_NAME
  if (deCi) return deCi
  try {
    return execSync('git rev-parse --abbrev-ref HEAD', { stdio: ['ignore', 'pipe', 'ignore'] })
      .toString().trim()
  } catch {
    return ''      // sin git (una copia suelta): todos los módulos
  }
}

export function modulosDeLaBuild(desdeEnv: string | undefined): string {
  if (desdeEnv !== undefined && desdeEnv.trim() !== '') return desdeEnv.trim()
  return moduloDeRama(ramaActual())
}
