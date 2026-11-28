// CoachHome.jsx — Home del coach: vista rápida de TODOS los atletas.
// Por atleta: 3 anillos de disciplina (SWIM/BIKE/RUN como en el dashboard de
// atleta), distribución de actividades, biomarcadores (HANNA, sueño, FC),
// riesgo de enfermedad + lesión, curva de entrena/no-entrena, cuenta regresiva
// a la carrera y CTL/ATL/TSB. Cada tarjeta trae sus datos de endpoints que ya
// existen (/estado, /distribucion_entrenamiento, /riesgo_lesion) + /carreras.
// Paleta NOAH original (navy / violeta / verde / blanco), vidrio esmerilado.
import React, { useState, useEffect } from 'react'
import { Activity, ShieldAlert, Flame, ChevronRight, Waves, Bike, Footprints, Moon, HeartPulse, Bone, CalendarClock } from 'lucide-react'

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

// Colores por disciplina (coherentes con el dashboard de atleta)
const DEP = [
  { key: 'swimming', label: 'SWIM', Icon: Waves, color: '#4FA3E3' },
  { key: 'cycling',  label: 'BIKE', Icon: Bike, color: '#5FD0A0' },
  { key: 'running',  label: 'RUN',  Icon: Footprints, color: '#F0885A' },
]

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const h = { 'Content-Type': 'application/json' }; if (token) h['Authorization'] = `Bearer ${token}`
  return fetch(url, { headers: h }).then(r => r.json().catch(() => ({}))).catch(() => ({}))
}

const colHanna = (v) => v == null ? P.ink3 : v >= 65 ? P.green : v >= 45 ? P.amber : P.red
const colRiesgo = (v) => v == null ? P.ink3 : v >= 60 ? P.red : v >= 30 ? P.amber : P.green
const colLesion = (n) => n === 'alto' ? P.red : n === 'moderado' ? P.amber : n === 'bajo' ? P.green : P.ink3
const fmtHoras = h => { if (h == null) return '—'; const t = Math.round(Number(h) * 60); return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}` }
const _rgb = h => { const s = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(s.slice(i, i + 2), 16)) }
const _mix = (hex, tgt, a) => { const [r1, g1, b1] = _rgb(hex), [r2, g2, b2] = _rgb(tgt); const m = (x, y) => Math.round(x + (y - x) * a); return `#${[m(r1, r2), m(g1, g2), m(b1, b2)].map(v => v.toString(16).padStart(2, '0')).join('')}` }
const lighten = (h, a) => _mix(h, '#ffffff', a)
const darken = (h, a) => _mix(h, '#000000', a)

// ── Anillo de disciplina: horas + % al centro, distribución de zonas en el aro ──
function DiscRing({ dep, horas, pct, zonas }) {
  const R = 26, STROKE = 7, CX = 34, CY = 34, C = 2 * Math.PI * R
  const cEnd = lighten(dep.color, 0.45), cFtp = dep.color, cVo2 = darken(dep.color, 0.28)
  const segs = zonas ? [
    { k: 'E', v: zonas.endurance, c: cEnd },
    { k: 'U', v: zonas.threshold, c: cFtp },
    { k: 'V', v: zonas.vo2, c: cVo2 },
  ] : null
  const GAP = 0.016
  let off = 0
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, flex: 1, minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        <dep.Icon size={12} color={dep.color} strokeWidth={2.4} />
        <span style={{ fontFamily: F, fontSize: 9.5, fontWeight: 700, letterSpacing: 0.6, color: dep.color }}>{dep.label}</span>
      </div>
      <div style={{ position: 'relative', width: 68, height: 68 }}>
        <svg viewBox="0 0 68 68" style={{ width: 68, height: 68 }}>
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={STROKE} />
          {segs ? segs.map((g, i) => {
            const f = Math.max(0, (g.v || 0)) / 100
            const draw = Math.max(0, f - GAP)
            const el = (
              <circle key={i} cx={CX} cy={CY} r={R} fill="none" stroke={g.c} strokeWidth={STROKE} strokeLinecap="butt"
                strokeDasharray={`${draw * C} ${C}`} strokeDashoffset={-(off * C)} transform={`rotate(-90 ${CX} ${CY})`} />
            )
            off += f
            return el
          }) : <circle cx={CX} cy={CY} r={R} fill="none" stroke={`${dep.color}3a`} strokeWidth={STROKE} />}
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: M, fontSize: 12.5, fontWeight: 600, color: P.white, letterSpacing: -0.4, lineHeight: 1 }}>{fmtHoras(horas)}</span>
          {pct != null && <span style={{ fontFamily: M, fontSize: 8.5, color: P.ink3, marginTop: 1 }}>{pct}%</span>}
        </div>
      </div>
    </div>
  )
}

// ── Anillo HANNA + aro interno de cuerpo (autonómico) ──
function AnilloHanna({ valor, cuerpo }) {
  const R = 30, C = 2 * Math.PI * R
  const v = valor == null ? 0 : Math.max(0, Math.min(100, valor))
  const col = colHanna(valor)
  return (
    <svg width="82" height="82" viewBox="0 0 82 82" style={{ flex: '0 0 auto' }}>
      <circle cx="41" cy="41" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" />
      {cuerpo != null && (
        <circle cx="41" cy="41" r={R - 8} fill="none" stroke={P.violet} strokeOpacity="0.5" strokeWidth="3"
          strokeDasharray={2 * Math.PI * (R - 8)} strokeDashoffset={2 * Math.PI * (R - 8) * (1 - Math.max(0, Math.min(100, cuerpo)) / 100)}
          strokeLinecap="round" transform="rotate(-90 41 41)" />
      )}
      <circle cx="41" cy="41" r={R} fill="none" stroke={col} strokeWidth="7" strokeLinecap="round"
        strokeDasharray={C} strokeDashoffset={C * (1 - v / 100)} transform="rotate(-90 41 41)"
        style={{ transition: 'stroke-dashoffset 1s cubic-bezier(.4,0,.2,1)' }} />
      <text x="41" y="39" textAnchor="middle" fontFamily={M} fontSize="20" fontWeight="700" fill={P.white}>{valor == null ? '—' : Math.round(valor)}</text>
      <text x="41" y="54" textAnchor="middle" fontFamily={F} fontSize="8" fill={P.ink3} letterSpacing="1">HANNA</text>
    </svg>
  )
}

// ── Mini curva de CTL (sparkline) con relleno ──
function SparkCTL({ serie, col = P.violet }) {
  const vv = (serie || []).filter(v => v != null && isFinite(v))
  if (vv.length < 3) return (
    <div style={{ height: 40, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F, fontSize: 9.5, color: P.ink3 }}>sin historial de carga</div>
  )
  const W = 240, H = 40, PT = 5, PB = 5
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

// ── Strip 14 días: entrenó (barra por carga del día) o descansó ──
function TrainStrip({ dias }) {
  // dias: array de 14 (viejo→nuevo) de { trained:bool, tss, dow, sport }
  const mx = Math.max(1, ...dias.map(d => d.tss || 0))
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 34 }}>
      {dias.map((d, i) => {
        const h = d.trained ? Math.max(5, Math.round((d.tss / mx) * 30)) : 3
        const c = !d.trained ? 'rgba(255,255,255,0.10)' : (DEP.find(x => x.key === d.sport)?.color || P.green)
        return <div key={i} title={d.date} style={{ flex: 1, height: h, borderRadius: 3, background: c, minWidth: 0 }} />
      })}
    </div>
  )
}

function Stat({ label, value, unit, col }) {
  return (
    <div style={{ flex: 1, textAlign: 'center' }}>
      <div style={{ fontFamily: M, fontSize: 15, fontWeight: 700, color: col || P.ink, lineHeight: 1 }}>{value ?? '—'}<span style={{ fontSize: 9, color: P.ink3, fontWeight: 400 }}>{unit}</span></div>
      <div style={{ fontFamily: F, fontSize: 8, color: P.ink3, letterSpacing: 0.6, textTransform: 'uppercase', marginTop: 4 }}>{label}</div>
    </div>
  )
}

// ── Tile de biomarcador ──
function Bio({ Icon, label, value, unit, col }) {
  return (
    <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, padding: '8px 4px', borderRadius: 12, background: 'rgba(255,255,255,0.04)' }}>
      <Icon size={14} color={col || P.ink2} strokeWidth={2.2} />
      <div style={{ fontFamily: M, fontSize: 13, fontWeight: 700, color: col || P.white, lineHeight: 1 }}>{value ?? '—'}<span style={{ fontSize: 8, color: P.ink3, fontWeight: 400 }}>{unit}</span></div>
      <div style={{ fontFamily: F, fontSize: 8, color: P.ink3, letterSpacing: 0.4, textTransform: 'uppercase' }}>{label}</div>
    </div>
  )
}

function Chip({ Icon, label, value, col }) {
  return (
    <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 7, padding: '7px 10px', borderRadius: 11, background: `${col}1C`, border: `1px solid ${col}40`, minWidth: 0 }}>
      <Icon size={14} color={col} strokeWidth={2.3} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: M, fontSize: 13, fontWeight: 700, color: col, lineHeight: 1 }}>{value}</div>
        <div style={{ fontFamily: F, fontSize: 8, color: P.ink3, letterSpacing: 0.3, textTransform: 'uppercase', marginTop: 2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{label}</div>
      </div>
    </div>
  )
}

function AtletaCard({ a, carrera, onSelect }) {
  const [estado, setEstado] = useState(null)
  const [dist, setDist] = useState(null)
  const [lesion, setLesion] = useState(null)
  const [strip, setStrip] = useState(null)
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    let vivo = true
    setCargando(true)
    Promise.all([
      authFetch(`${API}/atletas/${a.id}/estado`),
      authFetch(`${API}/atletas/${a.id}/distribucion_entrenamiento?dias=7`),
      authFetch(`${API}/atletas/${a.id}/riesgo_lesion`),
      authFetch(`${API}/atletas/${a.id}/sesiones?limit=40`),
    ]).then(([e, d, l, s]) => {
      if (!vivo) return
      setEstado(e?.data || null)
      setDist(d?.data || null)
      setLesion(l?.data || null)
      // Strip de 14 días desde las sesiones reales
      const porDia = {}
      ;(Array.isArray(s?.data) ? s.data : []).forEach(ses => {
        const k = String(ses.fecha || '').slice(0, 10)
        if (!k) return
        const t = Number(ses.tss) || 0
        if (!porDia[k] || t > porDia[k].tss) porDia[k] = { tss: t, sport: ses.sport }
      })
      const out = []
      for (let i = 13; i >= 0; i--) {
        const dt = new Date(); dt.setDate(dt.getDate() - i)
        const k = dt.toISOString().slice(0, 10)
        const rec = porDia[k]
        out.push({ date: k, trained: !!rec, tss: rec?.tss || 0, sport: rec?.sport })
      }
      setStrip(out)
      setCargando(false)
    })
    return () => { vivo = false }
  }, [a.id])

  const est = estado?.estado || {}
  const hanna = est.hanna_life
  const cuerpo = a.cuerpo
  // Riesgo de enfermedad UNIFICADO (viral + centinela) con fuente; cae al viral
  // viejo solo si el backend todavía no recalculó.
  const riesgoEnf = est.riesgo_enf != null ? est.riesgo_enf : est.riesgo_viral
  const enfFuente = est.riesgo_enf_fuente   // medido / estimado / no_evaluable
  const enfTag = enfFuente === 'estimado' ? ' · estimativo' : enfFuente === 'no_evaluable' ? ' · no eval.' : ''
  const ctl = est.ctl, atl = est.atl, tsb = est.tsb
  const tsbCol = tsb == null ? P.ink3 : tsb >= 5 ? P.green : tsb >= -15 ? P.amber : P.red
  const km = est.km_semana
  const sueno = est.sleep_h
  const fc = est.hr_reposo
  const ctlSerie = (estado?.training || []).map(t => t.ctl).filter(v => v != null)
  const inicial = (a.nombre || '?').trim().charAt(0).toUpperCase()
  const sinDist = !dist || dist.sin_datos
  const acwr = lesion?.acwr
  const nivelLesion = acwr?.nivel_riesgo
  const diasCarrera = carrera ? Math.ceil((new Date(carrera.fecha + 'T00:00:00') - new Date(new Date().toISOString().slice(0, 10) + 'T00:00:00')) / 86400000) : null

  return (
    <div style={{
      background: P.glass, backdropFilter: 'blur(16px)', WebkitBackdropFilter: 'blur(16px)',
      border: `1px solid ${P.glassBorder}`, borderRadius: 22, padding: 16,
      display: 'flex', flexDirection: 'column', gap: 13,
      boxShadow: '0 14px 40px -24px rgba(0,0,0,0.8)',
    }}>
      {/* Cabecera */}
      <button onClick={() => onSelect && onSelect(a.id)} style={{
        textAlign: 'left', cursor: 'pointer', width: '100%', border: 'none', background: 'transparent', padding: 0,
        display: 'flex', alignItems: 'center', gap: 11,
      }}>
        <div style={{ width: 40, height: 40, borderRadius: 12, flex: '0 0 auto', background: `linear-gradient(135deg, ${P.violet}, ${P.violetD})`, display: 'grid', placeItems: 'center', fontFamily: F, fontSize: 17, fontWeight: 800, color: P.white }}>{inicial}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontFamily: F, fontSize: 15, fontWeight: 700, color: P.white, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.nombre || 'Atleta'}</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 11, color: P.ink2, marginTop: 2 }}>
            {diasCarrera != null && diasCarrera >= 0
              ? <><CalendarClock size={12} color={P.green} /> {carrera.nombre || 'Carrera'} · faltan {diasCarrera} d</>
              : <><Activity size={12} color={P.ink3} /> {a.deporte || '—'}</>}
          </div>
        </div>
        <ChevronRight size={18} color={P.ink3} />
      </button>

      {cargando ? (
        <div style={{ height: 150, display: 'flex', alignItems: 'center', justifyContent: 'center', fontFamily: F, fontSize: 12, color: P.ink3 }}>Cargando datos…</div>
      ) : (
      <>
      {/* 3 anillos de disciplina */}
      <div style={{ display: 'flex', gap: 6 }}>
        {DEP.map(dep => (
          <DiscRing key={dep.key} dep={dep}
            horas={dist?.deporte?.[dep.key]?.horas}
            pct={sinDist ? null : dist?.deporte?.[dep.key]?.pct}
            zonas={dist?.intensidad_por_deporte?.[dep.key]} />
        ))}
      </div>

      {/* Biomarcadores: HANNA + sueño + FC */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <AnilloHanna valor={hanna} cuerpo={cuerpo} />
        <div style={{ flex: 1, display: 'flex', gap: 6 }}>
          <Bio Icon={Moon} label="Sueño" value={sueno != null ? sueno.toFixed(1) : '—'} unit="h" col={sueno == null ? P.ink3 : sueno >= 7 ? P.green : sueno >= 6 ? P.amber : P.red} />
          <Bio Icon={HeartPulse} label="FC reposo" value={fc != null ? Math.round(fc) : '—'} unit="" col={P.ink2} />
          <Bio Icon={Flame} label="Km sem" value={km != null ? Math.round(km) : '—'} unit="" col={P.ink2} />
        </div>
      </div>

      {/* Riesgos: enfermedad + lesión */}
      <div style={{ display: 'flex', gap: 7 }}>
        <Chip Icon={ShieldAlert} label={`Alerta recuperación${enfTag}`} value={enfFuente === 'no_evaluable' ? 'no eval.' : riesgoEnf != null ? `${Math.round(riesgoEnf)}%` : '—'} col={enfFuente === 'no_evaluable' ? P.ink3 : colRiesgo(riesgoEnf)} />
        <Chip Icon={Bone} label={acwr?.disponible ? `Lesión · ACWR ${acwr.acwr ?? '—'}` : 'Riesgo lesión'} value={nivelLesion ? nivelLesion.charAt(0).toUpperCase() + nivelLesion.slice(1) : '—'} col={colLesion(nivelLesion)} />
      </div>

      {/* Entrena / descansa (14 días) */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 5 }}>
          <span style={{ fontFamily: F, fontSize: 8.5, color: P.ink3, letterSpacing: 0.8, textTransform: 'uppercase' }}>Entrenó · 14 días</span>
        </div>
        {strip ? <TrainStrip dias={strip} /> : null}
      </div>

      {/* Curva de carga (CTL) */}
      <div style={{ paddingTop: 10, borderTop: `1px solid rgba(255,255,255,0.07)` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
          <span style={{ fontFamily: F, fontSize: 8.5, color: P.ink3, letterSpacing: 0.8, textTransform: 'uppercase' }}>Carga · CTL</span>
          <span style={{ fontFamily: F, fontSize: 9.5, color: P.ink2 }}>{ctlSerie.length >= 2 ? (ctlSerie[ctlSerie.length - 1] - ctlSerie[0] >= 0 ? '↑ creciendo' : '↓ bajando') : ''}</span>
        </div>
        <SparkCTL serie={ctlSerie} />
      </div>

      {/* Carga actual */}
      <div style={{ display: 'flex', gap: 4, paddingTop: 8, borderTop: `1px solid rgba(255,255,255,0.07)` }}>
        <Stat label="CTL" value={ctl != null ? Math.round(ctl) : '—'} col={P.violet} />
        <Stat label="ATL" value={atl != null ? Math.round(atl) : '—'} col={P.ink} />
        <Stat label="TSB" value={tsb != null ? Math.round(tsb) : '—'} col={tsbCol} />
      </div>
      </>
      )}
    </div>
  )
}

export default function CoachHome({ onSelect }) {
  const [atletas, setAtletas] = useState(null)
  const [carreras, setCarreras] = useState({})   // atleta_id -> próxima carrera futura
  const [recalc, setRecalc] = useState('idle')

  const recalcularTodos = () => {
    if (recalc === 'run') return
    setRecalc('run')
    authFetch(`${API}/recalcular_hanna_todos`, { method: 'POST' })
      .then(r => r.json())
      .then(() => { setRecalc('done'); setTimeout(() => window.location.reload(), 600) })
      .catch(() => setRecalc('idle'))
  }

  useEffect(() => {
    authFetch(`${API}/atletas`).then(j => setAtletas(Array.isArray(j?.data) ? j.data : []))
    authFetch(`${API}/carreras`).then(j => {
      const list = Array.isArray(j?.data?.carreras) ? j.data.carreras : []
      const hoy = new Date().toISOString().slice(0, 10)
      const map = {}
      list.forEach(c => {
        const f = String(c.fecha || '').slice(0, 10)
        if (!f || f < hoy) return
        const aid = c.atleta_id
        if (!map[aid] || f < map[aid].fecha) map[aid] = { fecha: f, nombre: c.nombre }
      })
      setCarreras(map)
    })
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
        {/* Recalcular HANNA de TODOS los atletas (temporal) */}
        <button onClick={recalcularTodos} disabled={recalc === 'run'} title="Recalcular HANNA de todos los atletas" style={{
          flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4,
          minWidth: 110, borderRadius: 18, padding: '13px 16px', cursor: recalc === 'run' ? 'default' : 'pointer',
          background: 'rgba(255,255,255,0.05)', border: `1px solid ${P.glassBorder}`, color: P.ink,
        }}>
          <Activity size={18} color={P.green} strokeWidth={2.2} />
          <span style={{ fontFamily: F, fontSize: 10.5, fontWeight: 700, textAlign: 'center' }}>{recalc === 'run' ? 'Recalculando…' : recalc === 'done' ? 'Listo ✓' : 'Recalcular todos'}</span>
        </button>
      </div>

      {/* Grilla de atletas */}
      {atletas == null ? (
        <div style={{ fontFamily: F, fontSize: 13, color: P.ink3, padding: 30, textAlign: 'center' }}>Cargando atletas…</div>
      ) : atletas.length === 0 ? (
        <div style={{ fontFamily: F, fontSize: 13, color: P.ink3, padding: 30, textAlign: 'center' }}>No hay atletas todavía.</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 14 }}>
          {atletas.map(a => <AtletaCard key={a.id} a={a} carrera={carreras[a.id]} onSelect={onSelect} />)}
        </div>
      )}
    </div>
  )
}
