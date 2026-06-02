/**
 * api.ts — Instancia axios configurada con base URL y auth headers.
 * Todos los features importan desde aquí, nunca crean sus propios axios.
 */
import axios from 'axios'
import { useAuthStore } from '../hooks/useAuthStore'

export const api = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

// Interceptor: inyecta Bearer token en cada request
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Interceptor: redirige a /login si el token expiró
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
