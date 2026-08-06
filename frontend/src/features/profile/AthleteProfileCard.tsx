// Ficha deportiva del atleta, en solo lectura: la edita el entrenador desde
// la sección Atletas.
import { useQuery } from '@tanstack/react-query'
import { IdCard } from 'lucide-react'
import { api } from '../../lib/api'
import { SPECIALTY_LABEL, STROKE_LABEL } from '../../lib/constants'
import { Card, Chip, EmptyState, Spinner } from '../../components/ui/primitives'

export function AthleteProfileCard({ swimmerId }: { swimmerId: number | null }) {
  const { data: swimmer, isLoading } = useQuery({
    queryKey: ['swimmer', swimmerId],
    queryFn: () => api.swimmers.getOne(swimmerId as number),
    enabled: swimmerId != null,
  })

  if (swimmerId == null) {
    return (
      <Card>
        <EmptyState
          icon={<IdCard size={24} />}
          title="Sin ficha deportiva"
          hint="Tu cuenta todavía no está ligada a un nadador. Pídeselo a tu entrenador."
        />
      </Card>
    )
  }
  if (isLoading || !swimmer) return <Card><Spinner /></Card>

  return (
    <Card title="Mi ficha deportiva">
      <div className="flex flex-wrap items-center gap-2">
        <Chip color="#3b82f6">{SPECIALTY_LABEL[swimmer.specialty] ?? swimmer.specialty}</Chip>
        <Chip color="#8b93b8">{STROKE_LABEL[swimmer.main_stroke] ?? swimmer.main_stroke}</Chip>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 border-t border-line pt-4 sm:grid-cols-4">
        <Stat label="Edad" value={swimmer.age != null ? `${swimmer.age} años` : '—'} />
        <Stat label="Género" value={swimmer.gender ?? '—'} />
        <Stat label="Peso" value={swimmer.weight_kg ? `${swimmer.weight_kg} kg` : '—'} />
        <Stat label="Talla" value={swimmer.height_cm ? `${swimmer.height_cm} cm` : '—'} />
      </dl>

      {swimmer.notes && (
        <p className="mt-4 border-t border-line pt-3.5 text-[12px] leading-relaxed text-text-dim">
          {swimmer.notes}
        </p>
      )}

      <p className="mt-4 text-[10.5px] text-text-faint">
        Estos datos los mantiene tu entrenador.
      </p>
    </Card>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label !mb-1">{label}</dt>
      <dd className="mono text-[15px] font-semibold">{value}</dd>
    </div>
  )
}
