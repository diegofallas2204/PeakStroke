import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '@/shared/lib/api'
import { useAuthStore } from '@/shared/hooks/useAuthStore'

export function LoginPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const setAuth = useAuthStore(s => s.setAuth)
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const endpoint = mode === 'login' ? '/auth/login' : '/auth/register'
      const payload = mode === 'login' ? { email, password } : { email, name, password }
      const { data } = await api.post<{ access_token: string }>(endpoint, payload)

      // Obtener perfil del usuario
      const meRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` }
      })
      setAuth(data.access_token, meRes.data)
      navigate('/macrocycles')
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Error al iniciar sesión')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <div className="text-5xl mb-3">🏊</div>
          <h1 className="text-3xl font-bold text-white">PeakStroke</h1>
          <p className="text-gray-400 mt-1">Planificación de natación competitiva</p>
        </div>

        <div className="bg-slate-900 rounded-2xl border border-white/10 p-6">
          <div className="flex gap-2 mb-6">
            {(['login', 'register'] as const).map(m => (
              <button key={m} className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${mode === m ? 'bg-sky-500 text-white' : 'text-gray-400 hover:text-white'}`}
                onClick={() => setMode(m)}>
                {m === 'login' ? 'Ingresar' : 'Registrarse'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === 'register' && (
              <div>
                <label className="label">Nombre</label>
                <input className="input" placeholder="Tu nombre" value={name} onChange={e => setName(e.target.value)} required />
              </div>
            )}
            <div>
              <label className="label">Email</label>
              <input className="input" type="email" placeholder="tu@email.com" value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            <div>
              <label className="label">Contraseña</label>
              <input className="input" type="password" placeholder="••••••••" value={password} onChange={e => setPassword(e.target.value)} required />
            </div>
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button className="btn-primary w-full" type="submit" disabled={loading}>
              {loading ? 'Cargando...' : mode === 'login' ? 'Ingresar' : 'Crear cuenta (Trial 30 días)'}
            </button>
          </form>

          {mode === 'register' && (
            <p className="text-center text-xs text-gray-500 mt-4">
              30 días gratis con plan Coach completo. Sin tarjeta de crédito.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
