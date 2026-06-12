import { Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { WaveBackground } from './components/three/WaveBackground'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { PlansPage } from './features/plans/PlansPage'
import { SwimmersPage } from './features/swimmers/SwimmersPage'
import { AerobicPage } from './features/aerobic/AerobicPage'
import { WeeklyPlanPage } from './features/weekly/WeeklyPlanPage'
import { TeamPage } from './features/team/TeamPage'
import { ComparisonPage } from './features/comparison/ComparisonPage'
import { SimulatorPage } from './features/simulator/SimulatorPage'

export default function App() {
  return (
    <div className="relative flex h-full">
      <WaveBackground />
      <Sidebar />
      <main className="relative z-10 flex-1 overflow-y-auto">
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
