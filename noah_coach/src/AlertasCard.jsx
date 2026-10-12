// AlertasCard.jsx — Alertas de carga / intensidad / zonas de NOAH
// Componente autocontenido: <AlertasCard atletaId={id} />
// Pega al endpoint GET /api/atletas/:id/alertas (noah_alertas.py).
import { useState, useEffect } from 'react'
import { AlertTriangle, Activity, TrendingUp, Scale, Waves, ChevronDown } from 'lucide-react'

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'

function authFetch(url, options = {}) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers })
}

const C = {
  ink: 'rgba(255,255,255,0.92)', ink2: 'rgba(255,255,255,0.62)', ink3: 'rgba(255,255,255,0.38)',
  alta: '#F87171', media: '#F59E0B', ok: '#34D399',
}
const ICONO = { intensidad: Activity, zonas: Waves, volumen: TrendingUp, acwr: Scale, monotonia: Waves }

export default function AlertasCard({ atletaId, compact = false }) {
  const [data, setData] = useState(null)
  const [abierto, setAbierto] = useState(!compact)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/alertas?dias=7`)
      .then(r => r.json()).then(r => setData(r.data || r)).catch(() => {})
  }, [atletaId])

  if (!data?.disponible) return null
  const alertas = data.alertas || []
  const altas = data.resumen?.altas || 0
  const colorHeader = altas > 0 ? C.alta : alertas.length ? C.media : C.ok

  // Sin alertas: señal verde discreta (nunca "no hay datos")
  if (!alertas.length) return (
    <div style={glass(C.ok)}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 8, height: 8, borderRadius: '50%', background: C.ok, boxShadow: `0 0 8px ${C.ok}` }} />
        <span style={{ fontSize: 12.5, fontWeight: 700, color: C.ink }}>Carga bajo control</span>
        <span style={{ fontSize: 11, color: C.ink3, marginLeft: 'auto' }}>últimos 7 días</span>
      </div>
    </div>
  )

  return (
    <div style={glass(colorHeader)}>
      <div onClick={() => setAbierto(a => !a)} style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
        <AlertTriangle size={16} color={colorHeader} />
        <span style={{ fontSize: 12.5, fontWeight: 700, color: C.ink }}>
          {alertas.length} {alertas.length === 1 ? 'alerta' : 'alertas'} de carga
        </span>
        {altas > 0 && (
          <span style={{ fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 20, background: `${C.alta}22`, color: C.alta }}>
            {altas} alta{altas > 1 ? 's' : ''}
          </span>
        )}
        <ChevronDown size={15} color={C.ink3}
          style={{ marginLeft: 'auto', transform: abierto ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }} />
      </div>

      {abierto && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12 }}>
          {alertas.map((a, i) => {
            const col = a.severidad === 'alta' ? C.alta : C.media
            const Icon = ICONO[a.tipo] || AlertTriangle
            return (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start',
                padding: '9px 11px', borderRadius: 11, background: `${col}12`, border: `1px solid ${col}28` }}>
                <Icon size={15} color={col} style={{ flexShrink: 0, marginTop: 1 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span style={{ fontSize: 12, fontWeight: 700, color: C.ink }}>{a.titulo}</span>
                    {a.fecha && <span style={{ fontSize: 9.5, color: C.ink3 }}>{a.fecha.slice(5)}</span>}
                  </div>
                  <div style={{ fontSize: 11, color: C.ink2, marginTop: 2, lineHeight: 1.45 }}>{a.detalle}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function glass(accent) {
  return {
    background: 'linear-gradient(165deg, rgba(255,255,255,0.05), rgba(255,255,255,0.012))',
    border: `1px solid ${accent}2e`, borderRadius: 16, padding: '13px 15px',
    boxShadow: '0 10px 28px -12px rgba(0,0,0,0.5)',
  }
}
