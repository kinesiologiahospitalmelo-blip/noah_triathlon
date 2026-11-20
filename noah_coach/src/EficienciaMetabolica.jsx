// src/EficienciaMetabolica.jsx — NOAH · VO2max y su correlación con biomarcadores
// Autocontenido: fetchea /vo2. Gráfico en "isla oscura" (científico) con dos
// series: VO2max (azul, eje izq) y biomarcador HANNA/cuerpo (salvia, eje der).
// La idea: el VO2 sube cuando los biomarcadores acompañan; si entrenás con ellos
// bajos, se estanca. Solo presentación; no toca ningún algoritmo.
import React, { useState, useEffect } from 'react'
import { Activity, TrendingUp, TrendingDown, Minus, Wind, Gauge } from 'lucide-react'
import { NOAH, FONT } from './noahTheme'

const F = FONT.base, M = FONT.mono

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { headers }).then(r => r.json().catch(() => ({})))
}

const TONO_COL = { ok: '#6FBF8E', warn: '#E8A24B', neutral: NOAH.azul }

// Isla oscura (gráficos científicos), según el lenguaje visual de NOAH.
const island = {
  background: 'linear-gradient(165deg,#1C211C,#13160F)',
  borderRadius: 22, border: '1px solid rgba(255,255,255,0.08)',
  boxShadow: '0 20px 44px -26px rgba(0,0,0,0.75)', padding: 16,
}
const card = (o = {}) => ({
  background: NOAH.surface, border: `1px solid ${NOAH.border}`, borderRadius: 20,
  boxShadow: '0 2px 4px rgba(41,45,41,0.04), 0 16px 36px -24px rgba(41,45,41,0.45)',
  padding: 16, ...o,
})
const eyebrow = { fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: NOAH.azul, textTransform: 'uppercase' }

function Tendencia({ v, label }) {
  const col = v == null ? 'rgba(243,240,232,0.45)' : v > 0.3 ? '#6FBF8E' : v < -0.3 ? '#E2726E' : 'rgba(243,240,232,0.6)'
  const Ic = v == null ? Minus : v > 0.3 ? TrendingUp : v < -0.3 ? TrendingDown : Minus
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <Ic size={13} color={col} strokeWidth={2.4} />
        <span style={{ fontFamily: M, fontSize: 14, fontWeight: 700, color: col }}>{v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(1)}`}</span>
      </div>
      <span style={{ fontFamily: F, fontSize: 9.5, color: 'rgba(243,240,232,0.5)' }}>{label}</span>
    </div>
  )
}

// Gráfico dual en isla oscura
function GraficoVO2({ serie }) {
  const pts = (serie || []).filter(s => s.vo2 != null)
  if (pts.length < 2) return <div style={{ fontFamily: F, fontSize: 12, color: 'rgba(243,240,232,0.6)', padding: '20px 0', textAlign: 'center' }}>Pocos datos de VO2 todavía.</div>

  const W = 720, H = 250, PL = 44, PR = 44, PT = 20, PB = 32
  const iW = W - PL - PR, iH = H - PT - PB
  const n = pts.length
  const xs = i => PL + (n <= 1 ? iW / 2 : (i / (n - 1)) * iW)

  const vo2v = pts.map(p => p.vo2)
  const vmin = Math.floor(Math.min(...vo2v) - 1), vmax = Math.ceil(Math.max(...vo2v) + 1)
  const ysV = v => PT + iH - ((v - vmin) / (vmax - vmin || 1)) * iH

  const bio = pts.map(p => (p.cuerpo != null ? p.cuerpo : p.hanna))
  const hayBio = bio.some(b => b != null)
  const ysB = v => PT + iH - ((v - 0) / 100) * iH

  const vo2D = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${xs(i).toFixed(1)},${ysV(p.vo2).toFixed(1)}`).join(' ')
  const areaD = `${vo2D} L${xs(n - 1).toFixed(1)},${(PT + iH).toFixed(1)} L${xs(0).toFixed(1)},${(PT + iH).toFixed(1)} Z`
  const bioD = hayBio
    ? pts.map((p, i) => {
        const b = p.cuerpo != null ? p.cuerpo : p.hanna
        return b == null ? null : `${xs(i).toFixed(1)},${ysB(b).toFixed(1)}`
      }).filter(Boolean).reduce((d, pt, i) => d + (i === 0 ? 'M' : 'L') + pt, '')
    : ''

  const idxLabels = [0, Math.floor((n - 1) / 2), n - 1]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="vo2Area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={NOAH.azul} stopOpacity="0.28" />
          <stop offset="100%" stopColor={NOAH.azul} stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* grid horizontal (eje VO2) */}
      {[0, 0.25, 0.5, 0.75, 1].map((t, k) => {
        const y = PT + t * iH
        const val = (vmax - t * (vmax - vmin)).toFixed(0)
        return (
          <g key={k}>
            <line x1={PL} y1={y} x2={W - PR} y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
            <text x={PL - 7} y={y + 3} textAnchor="end" fontFamily={M} fontSize="9" fill="rgba(79,140,201,0.75)">{val}</text>
            {hayBio && <text x={W - PR + 7} y={y + 3} textAnchor="start" fontFamily={M} fontSize="9" fill="rgba(120,134,107,0.85)">{Math.round(100 - t * 100)}</text>}
          </g>
        )
      })}

      {/* biomarcador (salvia, secundario) */}
      {hayBio && <path d={bioD} fill="none" stroke={NOAH.salvia} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" strokeDasharray="1 0" />}

      {/* VO2 (azul, principal) */}
      <path d={areaD} fill="url(#vo2Area)" />
      <path d={vo2D} fill="none" stroke={NOAH.azul} strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      {pts.map((p, i) => <circle key={i} cx={xs(i)} cy={ysV(p.vo2)} r={i === n - 1 ? 4.5 : 0} fill={NOAH.azul} stroke="#13160F" strokeWidth="2" />)}

      {/* etiquetas eje x */}
      {idxLabels.map((i, k) => (
        <text key={k} x={xs(i)} y={H - 10} textAnchor={k === 0 ? 'start' : k === 2 ? 'end' : 'middle'} fontFamily={F} fontSize="9" fill="rgba(243,240,232,0.45)">{(pts[i].fecha || '').slice(5)}</text>
      ))}
    </svg>
  )
}

export default function EficienciaMetabolica({ atletaId }) {
  const [d, setD] = useState(null)
  const [err, setErr] = useState(false)

  useEffect(() => {
    let vivo = true
    authFetch(`${API}/atletas/${atletaId}/vo2`).then(j => {
      if (!vivo) return
      if (j?.ok === false) { setErr(true); return }
      setD(j?.data || { disponible: false })
    }).catch(() => setErr(true))
    return () => { vivo = false }
  }, [atletaId])

  if (err) return null
  if (!d) return <div style={{ fontFamily: F, fontSize: 13, color: NOAH.ink45, padding: 20 }}>Cargando…</div>
  if (!d.disponible) return (
    <div style={card()}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}><Wind size={14} color={NOAH.azul} /><span style={{ ...eyebrow }}>Eficiencia metabólica</span></div>
      <div style={{ fontFamily: F, fontSize: 12.5, color: NOAH.ink45, lineHeight: 1.5 }}>Todavía no hay VO2max de Garmin para este atleta. Aparece cuando Garmin calcula el VO2 (suele necesitar actividades con GPS y FC).</div>
    </div>
  )

  const lectCol = TONO_COL[d.lectura?.tono] || NOAH.azul

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Cabecera: VO2 actual + estado Garmin + tendencias */}
      <div style={card()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
          <Wind size={14} color={NOAH.azul} strokeWidth={2.3} />
          <span style={{ ...eyebrow, color: NOAH.azul }}>Eficiencia metabólica · VO2max</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 14, flexWrap: 'wrap' }}>
          <div>
            <div style={{ fontFamily: M, fontSize: 44, fontWeight: 700, color: NOAH.ink, letterSpacing: -1.5, lineHeight: 0.95 }}>{d.vo2_actual?.toFixed(0)}</div>
            <div style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, marginTop: 3 }}>ml/kg/min · {(d.vo2_fecha || '').slice(5)}</div>
          </div>
          <div style={{ flex: 1 }} />
          {d.training_status && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '5px 11px', borderRadius: 999, background: `${NOAH.salvia}16`, border: `1px solid ${NOAH.salvia}33` }}>
              <Gauge size={12} color={NOAH.salvia} />
              <span style={{ fontFamily: F, fontSize: 11, fontWeight: 700, color: NOAH.salvia }}>{d.training_status}</span>
            </div>
          )}
        </div>
      </div>

      {/* Gráfico dual en isla oscura */}
      <div style={island}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ fontFamily: F, fontSize: 11, fontWeight: 700, letterSpacing: 0.8, color: 'rgba(243,240,232,0.85)' }}>VO2 vs biomarcadores</span>
          <div style={{ display: 'flex', gap: 12 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 9.5, color: 'rgba(243,240,232,0.6)' }}><span style={{ width: 12, height: 3, borderRadius: 3, background: NOAH.azul }} />VO2</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 9.5, color: 'rgba(243,240,232,0.6)' }}><span style={{ width: 12, height: 3, borderRadius: 3, background: NOAH.salvia }} />cuerpo</span>
          </div>
        </div>
        <GraficoVO2 serie={d.serie} />
        <div style={{ display: 'flex', gap: 22, marginTop: 6, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.07)' }}>
          <Tendencia v={d.tendencia_30d} label="últimos 30d" />
          <Tendencia v={d.tendencia_90d} label="últimos 90d" />
          {d.correlacion != null && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ fontFamily: M, fontSize: 14, fontWeight: 700, color: d.correlacion > 0.1 ? '#6FBF8E' : d.correlacion < -0.1 ? '#E2726E' : 'rgba(243,240,232,0.7)' }}>{d.correlacion > 0 ? '+' : ''}{d.correlacion.toFixed(2)}</span>
              <span style={{ fontFamily: F, fontSize: 9.5, color: 'rgba(243,240,232,0.5)' }}>corr. biomarcador→VO2</span>
            </div>
          )}
        </div>
      </div>

      {/* Lectura NOAH */}
      {d.lectura?.texto && (
        <div style={card({ borderColor: `${lectCol}40` })}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <Activity size={14} color={lectCol} strokeWidth={2.3} style={{ flex: '0 0 auto', marginTop: 1 }} />
            <div style={{ fontFamily: F, fontSize: 12.5, color: NOAH.ink70, lineHeight: 1.5 }}>{d.lectura.texto}</div>
          </div>
        </div>
      )}
    </div>
  )
}
