import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { modulosDeLaBuild } from './modulosDeRama'
import { CABECERAS_DE_SEGURIDAD } from './cabecerasDeSeguridad'

export default defineConfig(({ mode }) => {
  // Los módulos de esta build: `VITE_MODULOS` o la rama `modulo/<nombre>`.
  // Ver `src/lib/modulos.ts` y `docs/MODULOS.md`.
  const modulos = modulosDeLaBuild(loadEnv(mode, process.cwd(), 'VITE_').VITE_MODULOS)
  return {
    plugins: [react(), tailwindcss()],
    define: {
      'import.meta.env.VITE_MODULOS': JSON.stringify(modulos),
    },
    server: {
      port: 5173,
      proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
      },
    },
    // `vite preview` sirve la build con las cabeceras de producción: es como se
    // prueba que la CSP no rompe nada antes de desplegar (TODO-34), y es lo que
    // el piloto expone por un túnel (`piloto.ps1`, docs/PILOTO.md).
    preview: {
      port: 4173,
      // En la red local (piloto) cada dispositivo entra por aquí: la IP real va
      // al backend en X-Forwarded-For (xfwd), que la cree porque llega desde
      // 127.0.0.1 (PEAKSTROKE_PROXIES_DE_CONFIANZA). Sin ella todos compartirían
      // origen y el freno de login de uno frenaría a todos.
      headers: CABECERAS_DE_SEGURIDAD,
      // Vite rechaza los `Host` que no conoce (contra el DNS rebinding). Los
      // túneles del piloto llegan con su dominio: se admiten esos y nada más.
      // Uno propio, en PEAKSTROKE_HOSTS_DEL_PILOTO (por comas).
      allowedHosts: [
        '.trycloudflare.com', '.ts.net', '.ngrok-free.app', '.ngrok.app',
        ...(process.env.PEAKSTROKE_HOSTS_DEL_PILOTO ?? '').split(',').map((h) => h.trim()).filter(Boolean),
      ],
      proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true, xfwd: true },
      },
    },
  }
})
