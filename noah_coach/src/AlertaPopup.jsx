// AlertaPopup.jsx — Aviso emergente de alertas de carga (una vez por día)
// Se muestra al abrir el atleta si hay alertas activas. Se cierra con la X.
// <AlertaPopup atletaId={id} />
import { useState, useEffect } from 'react'
import { AlertTriangle, X, Activity, Waves, TrendingUp, Scale } from 'lucide-react'

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'

function authFetch(url, options = {}) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers })
}

const ICONO = { intensidad: Activity, zonas: Waves, volumen: TrendingUp, acwr: Scale, monotonia: Waves }
const hoyStr = () => new Date().toISOString().slice(0, 10)

export default function AlertaPopup({ atletaId }) {
  const [alertas, setAlertas] = useState(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!atletaId) return
    let yaHoy = false
    try { yaHoy = localStorage.getItem(`noah_alerta_popup_${atletaId}`) === hoyStr() } catch {}
    if (yaHoy) return
    authFetch(`${API}/atletas/${atletaId}/alertas?dias=7`)
      .then(r => r.json())
      .then(r => {
        const d = r.data || r
        const list = (d && d.alertas) || []
        if (list.length) { setAlertas(list); setVisible(true) }
      })
      .catch(() => {})
  }, [atletaId])

  const cerrar = () => {
    try { localStorage.setItem(`noah_alerta_popup_${atletaId}`, hoyStr()) } catch {}
    setVisible(false)
  }

  if (!visible || !alertas?.length) return null
  const altas = alertas.filter(a => a.severidad === 'alta').length

  return (
    <div onClick={cerrar} style={{
      position: 'fixed', inset: 0, zIndex: 99999,
      background: 'rgba(5,6,12,0.72)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: '100%', maxWidth: 440, borderRadius: 20, overflow: 'hidden',
        background: 'linear-gradient(160deg, rgba(24,22,40,0.98), rgba(12,12,20,0.99))',
        border: '1px solid rgba(255,255,255,0.10)',
        boxShadow: '0 30px 80px -20px rgba(0,0,0,0.85)',
      }}>
        <div style={{
          padding: '18px 20px', display: 'flex', alignItems: 'center', gap: 12,
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          background: altas ? 'rgba(248,113,113,0.08)' : 'rgba(245,158,11,0.07)',
        }}>
          <div style={{
            width: 38, height: 38, borderRadius: 11, flexShrink: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: altas ? 'rgba(248,113,113,0.16)' : 'rgba(245,158,11,0.16)',
          }}>
            <AlertTriangle size={20} color={altas ? '#F87171' : '#F59E0B'} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14.5, fontWeight: 800, color: 'rgba(255,255,255,0.95)' }}>
              {alertas.length} {alertas.length === 1 ? 'alerta de carga' : 'alertas de carga'}
            </div>
            <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.5)', marginTop: 2 }}>
              últimos 7 días · revisá antes de la próxima sesión
            </div>
          </div>
          <button onClick={cerrar} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'rgba(255,255,255,0.5)', padding: 4, lineHeight: 0,
          }}><X size={20} /></button>
        </div>

        <div style={{
          padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 9,
          maxHeight: '58vh', overflowY: 'auto',
        }}>
          {alertas.map((a, i) => {
            const col = a.severidad === 'alta' ? '#F87171' : '#F59E0B'
            const Icon = ICONO[a.tipo] || AlertTriangle
            return (
              <div key={i} style={{
                display: 'flex', gap: 11, alignItems: 'flex-start',
                padding: '11px 13px', borderRadius: 13,
                background: `${col}12`, border: `1px solid ${col}2a`,
              }}>
                <Icon size={16} color={col} style={{ flexShrink: 0, marginTop: 1 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 700, color: 'rgba(255,255,255,0.92)' }}>{a.titulo}</div>
                  <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.6)', marginTop: 2, lineHeight: 1.45 }}>{a.detalle}</div>
                </div>
              </div>
            )
          })}
        </div>

        <div style={{ padding: '12px 16px 16px' }}>
          <button onClick={cerrar} style={{
            width: '100%', padding: '11px', borderRadius: 12, border: 'none', cursor: 'pointer',
            fontSize: 13, fontWeight: 800, color: '#0A0A0F',
            background: 'linear-gradient(90deg, #F59E0B, #F87171)',
          }}>
            Entendido
          </button>
        </div>
      </div>
    </div>
  )
}
