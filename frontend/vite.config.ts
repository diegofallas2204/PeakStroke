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
    // prueba que la CSP no rompe nada antes de desplegar (TODO-34).
    preview: {
      port: 4173,
      headers: CABECERAS_DE_SEGURIDAD,
      proxy: {
        '/api': { target: 'http://localhost:8000', changeOrigin: true },
      },
    },
  }
})
