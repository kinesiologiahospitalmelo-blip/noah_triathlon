// CoachHome.jsx — Home del coach: resumen de TODOS los atletas de un pantallazo.
// Un gráfico por atleta: anillo HANNA + riesgo viral + carga (CTL/ATL/TSB) + km.
// Paleta NOAH original (navy / violeta / verde / blanco), vidrio esmerilado.
// Tocar un atleta -> onSelect(id). Autocontenido: fetchea /atletas.
import React, { useState, useEffect } from 'react'
import { Activity, ShieldAlert, Flame, ChevronRight, Waves, Bike, Footprints } from 'lucide-react'

// Paleta NOAH original
const P = {
  navy:   '#0B1020',
  navy2:  '#111735',
  violet: '#8057D8',
  violetD:'#6449B9',
  green:  '#35C29B',
  greenD: '#288264',
  white:  '#F5F7FA',
  ink:    'rgba(245,247,250,0.92)',
  ink2:   'rgba(245,247,250,0.60)',
  ink3:   'rgba(245,247,250,0.38)',
  amber:  '#E0A43C',
  red:    '#F0564B',
  glass:  'rgba(255,255,255,0.055)',
  glassBorder: 'rgba(255,255,255,0.10)',
}
const F = "'Archivo', system-ui, sans-serif"
const M = "'IBM Plex Mono', monospace"

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const h = { 'Content-Type': 'application/json' }; if (token) h['Authorization'] = `Bearer ${token}`
  return fetch(url, { headers: h }).then(r => r.json().catch(() => ({})))
}

const SPORT_ICON = { running: Footprints, cycling: Bike, swimming: Waves }
const colHanna = (v) => v == null ? P.ink3 : v >= 65 ? P.green : v >= 45 ? P.amber : P.red
const colRiesgo = (v) => v == null ? P.ink3 : v >= 60 ? P.red : v >= 30 ? P.amber : P.green

// Anillo HANNA
function AnilloHanna({ valor, cuerpo }) {
  const R = 34, C = 2 * Math.PI * R
  const v = valor == null ? 0 : Math.max(0, Math.min(100, valor))
  const col = colHanna(valor)
  return (
    <svg width="92" height="92" viewBox="0 0 92 92" style={{ flex: '0 0 auto' }}>
      <circle cx="46" cy="46" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
      {cuerpo != null && (
        <circle cx="46" cy="46" r={R - 9} fill="none" stroke={P.violet} strokeOpacity="0.5" strokeWidth="3"
          strokeDasharray={2 * Math.PI * (R - 9)} strokeDashoffset={2 * Math.PI * (R - 9) * (1 - Math.max(0, Math.min(100, cuerpo)) / 100)}
          strokeLinecap="round" transform="rotate(-90 46 46)" />
      )}
      <circle cx="46" cy="46" r={R} fill="none" stroke={col} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - v / 100)} transform="rotate(-90 46 46)"
        style={{ transition: 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)' }} />
      <text x="46" y="44" textAnchor="middle" fontFamily={M} fontSize="23" fontWeight="700" fill={P.white}>{valor == null ? '—' : Math.round(valor)}</text>
      <text x="46" y="60" textAnchor="middle" fontFamily={F} fontSize="8.5" fill={P.ink3} letterSpacing="1">HANNA</text>
    </svg>
  )
}

// Mini curva de CTL (sparkline) con relleno
function SparkCTL({ serie, col = P.violet }) {
  const vv = (serie || []).filter(v => v != null && isFinite(v))
  if (vv.length < 3) return (
    <div style={{ height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F, fontSize: 9.5, color: P.ink3 }}>sin historial de carga</div>
  )
  const W = 240, H = 44, PT = 6, PB = 6
  const mn = Math.min(...vv), mx = Math.max(...vv), rg = (mx - mn) || 1
  const n = vv.length
  const xs = i => (i / (n - 1)) * W
  const ys = v => PT + (H - PT - PB) - ((v - mn) / rg) * (H - PT - PB)
  const d = vv.map((v, i) => `${i === 0 ? 'M' : 'L'}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`).join(' ')
  const area = `${d} L${W},${H} L0,${H} Z`
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: 'block' }}>
      <defs><linearGradient id="spk" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={col} stopOpacity="0.35" /><stop offset="100%" stopColor={col} stopOpacity="0" /></linearGradient></defs>
      <path d={area} fill="url(#spk)" />
      <path d={d} fill="none" stroke={col} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={xs(n - 1)} cy={ys(vv[n - 1])} r="2.6" fill={col} />
    </svg>
  )
}

function Stat({ label, value, unit, col }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontFamily: M, fontSize: 16, fontWeight: 700, color: col || P.ink, lineHeight: 1 }}>{value ?? '—'}<span style={{ fontSize: 9, color: P.ink3, fontWeight: 400 }}>{unit}</span></div>
      <div style={{ fontFamily: F, fontSize: 8.5, color: P.ink3, letterSpacing: 0.6, textTransform: 'uppercase', marginTop: 4 }}>{label}</div>
    </div>
  )
}

function AtletaCard({ a, onSelect }) {
  const Ic = SPORT_ICON[a.deporte] || Footprints
  const tsb = a.tsb
  const tsbCol = tsb == null ? P.ink3 : tsb >= 5 ? P.green : tsb >= -15 ? P.amber : P.red
  const inicial = (a.nombre || '?').trim().charAt(0).toUpperCase()
  return (
    <button onClick={() => onSelect && onSelect(a.id)} style={{
      textAlign: 'left', cursor: 'pointer', width: '100%',
      background: P.glass, backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
      border: `1px solid ${P.glassBorder}`, borderRadius: 22, padding: 16,
      display: 'flex', flexDirection: 'column', gap: 12,
      boxShadow: '0 14px 40px -24px rgba(0,0,0,0.8)', transition: 'transform .15s, border-color .15s',
    }}
      onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.borderColor = 'rgba(128,87,216,0.5)' }}
      onMouseLeave={e => { e.currentTarget.style.transform = 'none'; e.currentTarget.style.borderColor = P.glassBorder }}>
      {/* Cabecera */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
        <div style={{ width: 40, height: 40, borderRadius: 12, flex: '0 0 auto', background: `linear-gradient(135deg, ${P.violet}, ${P.violetD})`, display: 'grid', placeItems: 'center', fontFamily: F, fontSize: 17, fontWeight: 800, color: P.white }}>{inicial}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: F, fontSize: 15, fontWeight: 700, color: P.white, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.nombre || 'Atleta'}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 11, color: P.ink2, marginTop: 2 }}><Ic size={12} color={P.green} />{a.deporte || '—'}</div>
        </div>
        <ChevronRight size={18} color={P.ink3} />
      </div>

      {/* Anillo HANNA + riesgo */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <AnilloHanna valor={a.hanna} cuerpo={a.cuerpo} />
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 11px', borderRadius: 12, background: `${colRiesgo(a.riesgo_viral)}1C`, border: `1px solid ${colRiesgo(a.riesgo_viral)}40` }}>
            <ShieldAlert size={14} color={colRiesgo(a.riesgo_viral)} strokeWidth={2.3} />
            <div style={{ flex: 1 }}>
              <div style={{ fontFamily: M, fontSize: 14, fontWeight: 700, color: colRiesgo(a.riesgo_viral), lineHeight: 1 }}>{a.riesgo_viral != null ? `${Math.round(a.riesgo_viral)}%` : '—'}</div>
              <div style={{ fontFamily: F, fontSize: 8.5, color: P.ink3, letterSpacing: 0.4, textTransform: 'uppercase', marginTop: 2 }}>Riesgo viral</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontFamily: F, fontSize: 11, color: P.ink2 }}>
            <Flame size={12} color={P.green} /> {a.km_semana != null ? `${Math.round(a.km_semana)} km` : '—'} esta semana
          </div>
        </div>
      </div>

      {/* Curva de carga (CTL) */}
      <div style={{ paddingTop: 10, borderTop: `1px solid rgba(255,255,255,0.07)` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
          <span style={{ fontFamily: F, fontSize: 8.5, color: P.ink3, letterSpacing: 0.8, textTransform: 'uppercase' }}>Carga · CTL 30d</span>
          <span style={{ fontFamily: F, fontSize: 9.5, color: P.ink2 }}>{a.ctl_serie?.length >= 2 ? (a.ctl_serie[a.ctl_serie.length - 1] - a.ctl_serie[0] >= 0 ? '↑ creciendo' : '↓ bajando') : ''}</span>
        </div>
        <SparkCTL serie={a.ctl_serie} />
      </div>

      {/* Carga actual */}
      <div style={{ display: 'flex', gap: 4, paddingTop: 8, borderTop: `1px solid rgba(255,255,255,0.07)` }}>
        <Stat label="CTL" value={a.ctl != null ? Math.round(a.ctl) : '—'} col={P.violet} />
        <Stat label="ATL" value={a.atl != null ? Math.round(a.atl) : '—'} col={P.ink} />
        <Stat label="TSB" value={tsb != null ? Math.round(tsb) : '—'} col={tsbCol} />
      </div>
    </button>
  )
}

export default function CoachHome({ onSelect }) {
  const [atletas, setAtletas] = useState(null)
  useEffect(() => {
    authFetch(`${API}/atletas`).then(j => setAtletas(Array.isArray(j?.data) ? j.data : []))
  }, [])

  const n = atletas?.length || 0
  const enRiesgo = (atletas || []).filter(a => (a.riesgo_viral || 0) >= 30 || (a.hanna != null && a.hanna < 45)).length

  return (
    <div>
      {/* Resumen */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>
        <div style={{ flex: 1, minWidth: 120, background: P.glass, backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)', border: `1px solid ${P.glassBorder}`, borderRadius: 18, padding: '13px 16px' }}>
          <div style={{ fontFamily: M, fontSize: 26, fontWeight: 700, color: P.white, lineHeight: 1 }}>{n}</div>
          <div style={{ fontFamily: F, fontSize: 10.5, color: P.ink2, marginTop: 4 }}>atletas activos</div>
        </div>
        <div style={{ flex: 1, minWidth: 120, background: P.glass, backdropFilter: 'blur(14px)', WebkitBackdropFilter: 'blur(14px)', border: `1px solid ${enRiesgo ? 'rgba(240,86,75,0.4)' : P.glassBorder}`, borderRadius: 18, padding: '13px 16px' }}>
          <div style={{ fontFamily: M, fontSize: 26, fontWeight: 700, color: enRiesgo ? P.red : P.green, lineHeight: 1 }}>{enRiesgo}</div>
          <div style={{ fontFamily: F, fontSize: 10.5, color: P.ink2, marginTop: 4 }}>requieren atención</div>
        </div>
      </div>

      {/* Grilla de atletas */}
      {atletas == null ? (
        <div style={{ fontFamily: F, fontSize: 13, color: P.ink3, padding: 30, textAlign: 'center' }}>Cargando atletas…</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
          {atletas.map(a => <AtletaCard key={a.id} a={a} onSelect={onSelect} />)}
        </div>
      )}
    </div>
  )
}
