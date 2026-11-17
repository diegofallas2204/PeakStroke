// Las cabeceras de seguridad del frontend (TODO-34, 2026-11-16). Un solo sitio:
// las usa `vite preview` (para probarlas contra la build de verdad) y las copia
// `public/_headers`, que es lo que leen Netlify y Cloudflare Pages.
// `cabecerasDeSeguridad.test.ts` comprueba que las dos digan lo mismo, y
// `docs/DESPLIEGUE.md` las traduce a nginx y Caddy.
//
// La CSP es la de una SPA sin nada de terceros: todo sale del mismo origen. Dos
// concesiones, a sabiendas:
// - `style-src 'unsafe-inline'`: algunos componentes montan su `<style>` (las
//   animaciones de `Modal`). No abre scripts, que siguen siendo solo 'self'.
// - `img-src data: blob:` y `connect-src 'self'`: el PDF se arma en el cliente
//   y se descarga como blob. Si el API vive en otro dominio, va en `connect-src`.
export const CABECERAS_DE_SEGURIDAD: Record<string, string> = {
  'Content-Security-Policy': [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join('; '),
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'Referrer-Policy': 'no-referrer',
  'Cross-Origin-Opener-Policy': 'same-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
}
