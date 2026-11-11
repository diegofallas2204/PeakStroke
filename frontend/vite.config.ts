import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { modulosDeLaBuild } from './modulosDeRama'

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
  }
})
