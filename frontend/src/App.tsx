import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { RutaPorRol } from './components/layout/RutaPorRol'
import { SECTION_ACCENT } from './lib/constants'
import { Spinner } from './components/ui/primitives'
import { useSimpleMode } from './hooks/useSimpleMode'

// Code-splitting: el fondo WebGL (Three.js) y cada página viven en su propio chunk
// para no inflar el bundle inicial. Las páginas con Recharts/GSAP arrastran esas
// libs solo a su chunk, no al arranque.
const WaveBackground = lazy(() =>
  import('./components/three/WaveBackground').then((m) => ({ default: m.WaveBackground })))
const DashboardPage = lazy(() =>
  import('./features/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const PlansPage = lazy(() =>
  import('./features/plans/PlansPage').then((m) => ({ default: m.PlansPage })))
const SwimmersPage = lazy(() =>
  import('./features/swimmers/SwimmersPage').then((m) => ({ default: m.SwimmersPage })))
const AerobicPage = lazy(() =>
  import('./features/aerobic/AerobicPage').then((m) => ({ default: m.AerobicPage })))
const WeeklyPage = lazy(() =>
  import('./features/weekly/WeeklyPage').then((m) => ({ default: m.WeeklyPage })))
const TeamPage = lazy(() =>
  import('./features/team/TeamPage').then((m) => ({ default: m.TeamPage })))
const SimulatorPage = lazy(() =>
  import('./features/simulator/SimulatorPage').then((m) => ({ default: m.SimulatorPage })))
const ProfilePage = lazy(() =>
  import('./features/profile/ProfilePage').then((m) => ({ default: m.ProfilePage })))

export default function App() {
  const { pathname } = useLocation()
  const [simple] = useSimpleMode()
  // Color de la sección activa → disponible a toda la página como var CSS para
  // que las tarjetas tiñan su glow de hover con el acento de la sección.
  const accent = SECTION_ACCENT[pathname] ?? 'var(--color-accent)'

  return (
    // < lg la navegación es una barra superior → el layout apila en columna.
    <div className="relative flex h-full flex-col lg:flex-row">
      {!simple && (
        <Suspense fallback={null}>
          <WaveBackground />
        </Suspense>
      )}
      <Sidebar />
      <main
        className="relative z-10 min-h-0 flex-1 overflow-y-auto"
        style={{ '--page-accent': accent } as React.CSSProperties}
      >
        <div className="mx-auto max-w-[1280px] px-4 py-5 sm:px-6 lg:px-7 lg:py-6">
          <Suspense fallback={<Spinner />}>
            {/* `RutaPorRol` envuelve TODO el switch, no cada ruta: la regla es
                una sola y vive en `navConfig`, así que registrar la guarda una
                vez evita que a alguien se le olvide ponerla en la ruta nueva. */}
            <RutaPorRol>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/macrociclos" element={<PlansPage />} />
                <Route path="/atletas" element={<SwimmersPage />} />
                <Route path="/pruebas" element={<AerobicPage />} />
                <Route path="/plan-semanal" element={<WeeklyPage />} />
                <Route path="/equipo" element={<TeamPage />} />
                {/* Comparación se fusionó dentro de Plan semanal como la vista
                    Progresión. La ruta sobrevive solo para no romper los
                    marcadores de quien la tuviera guardada. */}
                <Route
                  path="/comparacion"
                  element={<Navigate to="/plan-semanal?vista=progresion" replace />}
                />
                <Route path="/simulador" element={<SimulatorPage />} />
                <Route path="/perfil" element={<ProfilePage />} />
              </Routes>
            </RutaPorRol>
          </Suspense>
        </div>
      </main>
    </div>
  )
}
