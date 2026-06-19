import { lazy, Suspense } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { SECTION_ACCENT } from './lib/constants'
import { Spinner } from './components/ui/primitives'

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
const WeeklyPlanPage = lazy(() =>
  import('./features/weekly/WeeklyPlanPage').then((m) => ({ default: m.WeeklyPlanPage })))
const TeamPage = lazy(() =>
  import('./features/team/TeamPage').then((m) => ({ default: m.TeamPage })))
const ComparisonPage = lazy(() =>
  import('./features/comparison/ComparisonPage').then((m) => ({ default: m.ComparisonPage })))
const SimulatorPage = lazy(() =>
  import('./features/simulator/SimulatorPage').then((m) => ({ default: m.SimulatorPage })))

export default function App() {
  const { pathname } = useLocation()
  // Color de la sección activa → disponible a toda la página como var CSS para
  // que las tarjetas tiñan su glow de hover con el acento de la sección.
  const accent = SECTION_ACCENT[pathname] ?? 'var(--color-accent)'

  return (
    <div className="relative flex h-full">
      <Suspense fallback={null}>
        <WaveBackground />
      </Suspense>
      <Sidebar />
      <main className="relative z-10 flex-1 overflow-y-auto" style={{ '--page-accent': accent } as React.CSSProperties}>
        <div className="mx-auto max-w-[1280px] px-7 py-6">
          <Suspense fallback={<Spinner />}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/macrociclos" element={<PlansPage />} />
              <Route path="/atletas" element={<SwimmersPage />} />
              <Route path="/pruebas" element={<AerobicPage />} />
              <Route path="/plan-semanal" element={<WeeklyPlanPage />} />
              <Route path="/equipo" element={<TeamPage />} />
              <Route path="/comparacion" element={<ComparisonPage />} />
              <Route path="/simulador" element={<SimulatorPage />} />
            </Routes>
          </Suspense>
        </div>
      </main>
    </div>
  )
}
