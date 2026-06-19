import { Route, Routes, useLocation } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { WaveBackground } from './components/three/WaveBackground'
import { SECTION_ACCENT } from './lib/constants'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { PlansPage } from './features/plans/PlansPage'
import { SwimmersPage } from './features/swimmers/SwimmersPage'
import { AerobicPage } from './features/aerobic/AerobicPage'
import { WeeklyPlanPage } from './features/weekly/WeeklyPlanPage'
import { TeamPage } from './features/team/TeamPage'
import { ComparisonPage } from './features/comparison/ComparisonPage'
import { SimulatorPage } from './features/simulator/SimulatorPage'

export default function App() {
  const { pathname } = useLocation()
  // Color de la sección activa → disponible a toda la página como var CSS para
  // que las tarjetas tiñan su glow de hover con el acento de la sección.
  const accent = SECTION_ACCENT[pathname] ?? 'var(--color-accent)'

  return (
    <div className="relative flex h-full">
      <WaveBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 overflow-y-auto" style={{ '--page-accent': accent } as React.CSSProperties}>
        <div className="mx-auto max-w-[1280px] px-7 py-6">
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
        </div>
      </main>
    </div>
  )
}
