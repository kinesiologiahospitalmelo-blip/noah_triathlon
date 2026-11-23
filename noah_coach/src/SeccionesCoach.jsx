// SeccionesCoach.jsx — Botonera de secciones del coach (va debajo del panorama
// de atletas). Botones grandes, 3 por fila, icono centrado, violetas y flotando
// sobre el fondo navy; el icono en el color navy del fondo. Tocar -> onSelect(id).
import React from 'react'
import {
  CalendarDays, CalendarRange, Activity, Stethoscope, Gauge, Layers, Brain,
  Flag, FlaskConical, Boxes, SlidersHorizontal, User, Users, GraduationCap,
  Footprints, Bike,
} from 'lucide-react'

const NAVY = '#0B1020'
const VIOLET = '#8057D8'
const VIOLET_D = '#6449B9'

export const SECCIONES_COACH = [
  { id: 'semana',            label: 'Semana',            Icon: CalendarDays },
  { id: 'calendario',        label: 'Calendario',        Icon: CalendarRange },
  { id: 'estado',            label: 'Estado',            Icon: Activity },
  { id: 'diagnostico',       label: 'Diagnóstico',       Icon: Stethoscope },
  { id: 'zonas',             label: 'Zonas',             Icon: Gauge },
  { id: 'fases',             label: 'Fases',             Icon: Layers },
  { id: 'intel',             label: 'NOAH Intel',        Icon: Brain },
  { id: 'race',              label: 'Race',              Icon: Flag },
  { id: 'tests',             label: 'Tests',             Icon: FlaskConical },
  { id: 'clustering',        label: 'Clusters',          Icon: Boxes },
  { id: 'optimizer',         label: 'Optimizer',         Icon: SlidersHorizontal },
  { id: 'perfil',            label: 'Perfil',            Icon: User },
  { id: 'twin',              label: 'Twin',              Icon: Users },
  { id: 'aprendizaje',       label: 'Aprendizaje',       Icon: GraduationCap },
  { id: 'tecnica',           label: 'Técnica',           Icon: Footprints },
  { id: 'analisis_ciclismo', label: 'Análisis Ciclismo', Icon: Bike },
]

export default function SeccionesCoach({ onSelect, activo = null }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, width: '100%',
    }}>
      {SECCIONES_COACH.map(s => {
        const on = activo === s.id
        return (
          <button key={s.id} onClick={() => onSelect && onSelect(s.id)}
            style={{
              cursor: 'pointer', border: 'none', borderRadius: 18,
              padding: '18px 10px',
              background: on ? `linear-gradient(145deg, #9A7BE6, ${VIOLET})` : `linear-gradient(145deg, ${VIOLET}, ${VIOLET_D})`,
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 9,
              boxShadow: on
                ? `0 0 0 2px rgba(255,255,255,0.35), 0 16px 34px -16px rgba(128,87,216,0.8)`
                : `0 14px 30px -16px rgba(128,87,216,0.75)`,
              transition: 'transform .14s, box-shadow .14s',
            }}
            onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-3px)' }}
            onMouseLeave={e => { e.currentTarget.style.transform = 'none' }}>
            <s.Icon size={26} color={NAVY} strokeWidth={2.2} />
            <span style={{ fontFamily: "'Archivo', system-ui, sans-serif", fontSize: 13, fontWeight: 700, color: '#fff', textAlign: 'center', lineHeight: 1.15 }}>{s.label}</span>
          </button>
        )
      })}
    </div>
  )
}
