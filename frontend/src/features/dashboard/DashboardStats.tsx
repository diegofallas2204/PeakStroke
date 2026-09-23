// Las cuatro tarjetas de cabecera del dashboard.
//
// Extraídas de `DashboardPage` cuando llegó la vista de atleta: lo que cambia
// entre roles son las etiquetas y a dónde llevan, y meterlo por dentro de la
// página la habría empujado sobre el límite de ~300 líneas del CLAUDE.md a
// cambio de un `if` por tarjeta.
import { CalendarRange, TrendingUp, Trophy, Users } from 'lucide-react'
import type { DashboardSummary } from '../../lib/types'
import { StatCard } from '../../components/ui/StatCard'
import type { Vista } from './vistaPorRol'

export function DashboardStats({
  data, vista, simple,
}: { data: DashboardSummary; vista: Vista; simple: boolean }) {
  // Para el entrenador, cuánta gente lleva; para el atleta, cuántas pruebas
  // tiene. "Atletas en plan: 1" es un dato que a un atleta no le dice nada.
  const primerValor = vista.muestraColumnaAtleta ? data.athletes_total : data.events_total

  return (
    <div className="grid grid-cols-4 gap-4">
      <StatCard
        label={vista.primeraTarjeta.etiqueta} value={primerValor} accent="#3b82f6"
        icon={<Users size={15} />}
        sub={simple ? undefined : vista.primeraTarjeta.sub(data.events_total, data.athletes_total)}
        to={vista.primeraTarjeta.a}
      />
      <StatCard
        label="Semana actual" value={data.current_week ?? 0} suffix={`/ ${data.total_weeks}`}
        accent="#22d3ee" icon={<CalendarRange size={15} />}
        sub={simple ? undefined : (data.current_phase ? `Fase ${data.current_phase}` : 'Fuera de calendario')}
        to={vista.semana.a}
      />
      <StatCard
        label={vista.estado.etiqueta} value={data.ahead} suffix="adelantados"
        accent="#34d399" icon={<TrendingUp size={15} />}
        sub={simple ? undefined : (
          <span>
            <span className="text-cyan">{data.on_track} en plan</span>
            {' · '}
            <span className="text-coral">{data.behind} atrasados</span>
          </span>
        )}
        to={vista.estado.a}
      />
      <StatCard
        label="Desviación media" value={data.avg_deviation_percent ?? 0} suffix="%" decimals={2}
        accent={data.avg_deviation_percent != null && data.avg_deviation_percent > 0 ? '#fb7185' : '#34d399'}
        icon={<Trophy size={15} />}
        sub={simple ? undefined : 'Real vs. plan (negativo = más rápido)'}
        to={vista.desviacion.a}
      />
    </div>
  )
}
