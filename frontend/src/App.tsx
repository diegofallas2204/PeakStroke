import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { useAuthStore } from './shared/hooks/useAuthStore'
import { lazy, Suspense } from 'react'

// Lazy load de páginas — code splitting automático por route
const MacrocyclesPage = lazy(() => import('./features/training-plans/pages/MacrocyclesPage').then(m => ({ default: m.MacrocyclesPage })))
const MacrocycleDetailPage = lazy(() => import('./features/training-plans/pages/MacrocycleDetailPage').then(m => ({ default: m.MacrocycleDetailPage })))
const LoginPage = lazy(() => import('./features/auth/pages/LoginPage').then(m => ({ default: m.LoginPage })))

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<div className="min-h-screen bg-slate-950 flex items-center justify-center text-gray-400">Cargando...</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/macrocycles" element={<PrivateRoute><MacrocyclesPage /></PrivateRoute>} />
          <Route path="/macrocycles/:id" element={<PrivateRoute><MacrocycleDetailPage /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/macrocycles" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  )
}
