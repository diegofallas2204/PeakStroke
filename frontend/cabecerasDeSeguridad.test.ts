import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { CABECERAS_DE_SEGURIDAD } from './cabecerasDeSeguridad'

// `public/_headers` es una copia escrita a mano (Netlify y Cloudflare Pages la
// leen tal cual). Si alguien cambia una de las dos, esto lo dice.
describe('public/_headers', () => {
  const texto = readFileSync(new URL('./public/_headers', import.meta.url), 'utf8')
  const lineas = texto.split(/\r?\n/).map((l) => l.trim()).filter(Boolean)

  it('aplica a todas las rutas', () => {
    expect(lineas[0]).toBe('/*')
  })

  it('lleva exactamente las mismas cabeceras que la fuente', () => {
    const copia = Object.fromEntries(
      lineas.slice(1).map((l) => [l.slice(0, l.indexOf(':')), l.slice(l.indexOf(':') + 1).trim()]),
    )
    expect(copia).toEqual(CABECERAS_DE_SEGURIDAD)
  })

  it('no deja ejecutar scripts de fuera ni enmarcar la app', () => {
    const csp = CABECERAS_DE_SEGURIDAD['Content-Security-Policy']
    expect(csp).toContain("script-src 'self'")
    expect(csp).not.toContain('unsafe-eval')
    expect(csp).toContain("frame-ancestors 'none'")
  })
})
