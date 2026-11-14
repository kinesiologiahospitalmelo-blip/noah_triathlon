// src/SeccionAnalisis.jsx — Análisis y Biomarcadores (Opción 1 · editorial premium)
// Pantalla autocontenida. Fetchea /estado, /riesgo_lesion y /hanna_life.
// Solo presentación; NO inventa datos — cada gráfico usa datos reales recibidos.
import React, { useState, useEffect } from 'react'
import {
  AreaChart, Area, LineChart, Line, ResponsiveContainer, CartesianGrid,
  XAxis, YAxis, Tooltip, ReferenceLine, ReferenceArea,
} from 'recharts'
import {
  HeartPulse, Activity, Moon, Brain, Battery, TrendingUp, TrendingDown,
  Gauge, Scale, Waves, ShieldAlert, BatteryFull, BatteryLow, Thermometer,
} from 'lucide-react'
import { NOAH, FONT } from './noahTheme'
// Foto editorial — importada desde src/assets (donde ya está subida en el repo).
import heroImg from './assets/analisis_hero.jpg'
function FotoHero() {
  return (
    <img src={heroImg} alt="Atleta NOAH"
      onError={e => { e.currentTarget.style.display = 'none' }}
      style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 32%' }} />
  )
}

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url, options = {}) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) { try { localStorage.removeItem('noah_sesion') } catch {}; window.location.href = '/login' }
    return res
  })
}

const F = FONT.base, M = FONT.mono
const SEMA = { ok: '#35C07A', warn: '#E8A24B', bad: '#E2726E' }
const NIVEL = { 'Óptimo': SEMA.ok, 'Bueno': NOAH.azul, 'Moderado': SEMA.warn, 'Bajo': NOAH.coral, 'Crítico': SEMA.bad }
const RIESGO = { bajo: SEMA.ok, moderado: SEMA.warn, alto: NOAH.coral, critico: SEMA.bad }

const surface = (extra = {}) => ({
  position: 'relative', background: NOAH.surface, border: `1px solid ${NOAH.border}`,
  borderRadius: 20, boxShadow: '0 1px 2px rgba(41,45,41,0.04), 0 14px 34px -22px rgba(41,45,41,0.45)', ...extra,
})
const glass = (extra = {}) => ({
  position: 'relative', overflow: 'hidden', borderRadius: 22,
  background: 'linear-gradient(158deg, rgba(255,255,255,0.82) 0%, rgba(243,240,232,0.55) 100%)',
  backdropFilter: 'blur(18px)', WebkitBackdropFilter: 'blur(18px)',
  border: '1px solid rgba(255,255,255,0.8)',
  boxShadow: '0 14px 40px -16px rgba(41,45,41,0.34), 0 2px 8px -4px rgba(41,45,41,0.12)', ...extra,
})
const eyebrow = { fontFamily: F, fontSize: 10.5, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: NOAH.ink45 }

function Anillo({ valor, nivel, size = 116 }) {
  const v = Math.max(0, Math.min(100, Number(valor) || 0))
  const R = (size - 16) / 2, CX = size / 2, CY = size / 2, C = 2 * Math.PI * R
  const color = NIVEL[nivel] || NOAH.salvia
  return (
    <div style={{ position: 'relative', width: size, height: size, flex: '0 0 auto' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(41,45,41,0.09)" strokeWidth={9} />
        <circle cx={CX} cy={CY} r={R} fill="none" stroke={color} strokeWidth={9} strokeLinecap="round"
          strokeDasharray={`${(v / 100) * C} ${C}`} transform={`rotate(-90 ${CX} ${CY})`}
          style={{ transition: 'stroke-dasharray .9s cubic-bezier(.4,0,.2,1)' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: M, fontSize: 32, fontWeight: 700, color: NOAH.ink, letterSpacing: -1, lineHeight: 1 }}>{valor != null ? Math.round(valor) : '—'}</span>
        {nivel && <span style={{ fontFamily: F, fontSize: 10.5, fontWeight: 700, color, marginTop: 3 }}>{nivel}</span>}
      </div>
    </div>
  )
}

// Mini anillo (biomarcador circular)
function MiniRing({ Icon, label, value, max, unit, color, delay }) {
  const v = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100))
  const R = 22, CX = 28, CY = 28, C = 2 * Math.PI * R
  return (
    <div style={{ ...surface({ padding: '13px 12px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 7, animation: `aRise .5s both`, animationDelay: `${delay}ms` }) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5, alignSelf: 'flex-start' }}>
        <Icon size={12} color={color} strokeWidth={2.2} />
        <span style={{ ...eyebrow, fontSize: 9.5 }}>{label}</span>
      </div>
      <div style={{ position: 'relative', width: 56, height: 56 }}>
        <svg width={56} height={56} viewBox="0 0 56 56">
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(41,45,41,0.09)" strokeWidth={6} />
          <circle cx={CX} cy={CY} r={R} fill="none" stroke={color} strokeWidth={6} strokeLinecap="round"
            strokeDasharray={`${(v / 100) * C} ${C}`} transform={`rotate(-90 ${CX} ${CY})`} style={{ transition: 'stroke-dasharray .8s ease' }} />
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: M, fontSize: 15, fontWeight: 700, color: NOAH.ink }}>{value != null ? value : '—'}</span>
        </div>
      </div>
      {unit && <span style={{ fontFamily: M, fontSize: 9, color: NOAH.ink45 }}>{unit}</span>}
    </div>
  )
}

const RANGOS = [['Semana', 7], ['Mes', 30], ['Trimestre', 90]]

// ─────────────────────────────────────────────────────────────────────────────
// HANNA · Proyección de vitalidad y riesgo de enfermedad.
// NO es una curva simple: dibuja la LÍNEA BASE personal (media 30 días reales),
// la zona de riesgo por DEBAJO (la curva cambia de color), la zona óptima por
// arriba, íconos de batería llena (óptimo) / batería baja (alerta) / termómetro
// (riesgo de enfermedad bajo la base) y la PREDICCIÓN a 7 días en línea punteada.
// La proyección usa el MISMO modelo de la app (tendencia real 7d + factor TSB);
// no inventa valores: parte del último HANNA real y de la pendiente observada.
// ─────────────────────────────────────────────────────────────────────────────
function HannaPrediccion({ puntos, hoy, dias }) {
  const [hover, setHover] = useState(null)
  const pts = (puntos || []).filter(p => p.hanna_life != null).slice(-dias)
  if (pts.length < 2)
    return <div style={{ padding: '26px 8px', textAlign: 'center', fontFamily: F, fontSize: 11.5, color: NOAH.ink45 }}>Historial insuficiente para la proyección.</div>

  const hl = hoy?.hanna_life ?? pts[pts.length - 1].hanna_life
  const tsb = hoy?.hanna_scores?.tsb ?? 0
  const rvHoy = hoy?.riesgo_viral ?? 0

  // Línea base personal (media real de los últimos 30 días) y umbral de riesgo.
  const vals = pts.map(p => p.hanna_life)
  const baseline = vals.length > 7 ? vals.slice(-30).reduce((a, b) => a + b, 0) / Math.min(30, vals.length) : 65
  const umbral = baseline * 0.88

  // ── Proyección 7 días — misma base del proyecto (tendencia reciente + factor
  //    según TSB), con dos mejoras pedidas: SIN azar (determinista) y la
  //    tendencia por ajuste lineal de mínimos cuadrados — el MISMO método que ya
  //    usa el backend para la tendencia de HRV (np.polyfit grado 1). No inventa
  //    datos: parte del último HANNA real y de la pendiente observada.
  const pendiente = (ys) => {
    const k = ys.length
    if (k < 2) return 0
    const mx = (k - 1) / 2
    const my = ys.reduce((a, b) => a + b, 0) / k
    let num = 0, den = 0
    for (let i = 0; i < k; i++) { num += (i - mx) * (ys[i] - my); den += (i - mx) * (i - mx) }
    return den ? num / den : 0
  }
  const genProy = () => {
    if (pts.length < 5) return []
    const vs = pts.slice(-7).map(p => p.hanna_life)
    const trend = pendiente(vs)
    const factor = tsb < -15 ? -0.8 : tsb > 5 ? 0.3 : 0
    const out = []
    let cur = hl
    for (let i = 1; i <= 7; i++) {
      cur = Math.max(10, Math.min(100, cur + (trend * 0.3) + factor))
      out.push({ hl: Math.round(cur * 10) / 10 })
    }
    return out
  }
  const proy = genProy()

  const serie = [
    ...pts.map(p => ({ hl: p.hanna_life, rv: p.riesgo_viral, fecha: p.fecha, real: true })),
    ...proy.map(p => ({ hl: p.hl, real: false })),
  ]
  const n = serie.length

  const W = 720, H = 240, PT = 24, PB = 28, PL = 40, PR = 30
  const iW = W - PL - PR, iH = H - PT - PB
  const minY = Math.max(0, Math.min(25, Math.min(...vals)) - 6)
  const maxY = Math.min(100, Math.max(85, Math.max(...vals)) + 4)
  const xs = i => PL + (i / Math.max(n - 1, 1)) * iW
  const ys = v => PT + iH - ((v - minY) / (maxY - minY || 1)) * iH
  const xHoy = xs(pts.length - 1)

  // Color del tramo según posición respecto de la línea base del atleta.
  const segColor = v => (v >= baseline ? SEMA.ok : v >= umbral ? SEMA.warn : NOAH.coral)

  const real = serie.filter(s => s.real)
  const areaD =
    real.map((s, i) => `${i === 0 ? 'M' : 'L'}${xs(i).toFixed(1)},${ys(s.hl).toFixed(1)}`).join(' ') +
    ` L${xs(real.length - 1).toFixed(1)},${(PT + iH).toFixed(1)} L${xs(0).toFixed(1)},${(PT + iH).toFixed(1)} Z`
  const proyD = proy.length
    ? `M${xHoy.toFixed(1)},${ys(hl).toFixed(1)} ` + proy.map((p, i) => `L${xs(pts.length + i).toFixed(1)},${ys(p.hl).toFixed(1)}`).join(' ')
    : ''

  const step = Math.max(1, Math.floor(n / 7))
  const xLabels = serie.reduce((acc, s, i) => { if (i % step === 0 && s.real) acc.push({ i, label: s.fecha?.slice(5) }); return acc }, [])

  const pFinal = proy.length ? proy[proy.length - 1].hl : null
  const tendProy = pFinal == null ? null : pFinal < hl - 3 ? 'baja' : pFinal > hl + 3 ? 'sube' : 'estable'

  const onMove = e => {
    const r = e.currentTarget.getBoundingClientRect()
    const mx = (e.clientX - r.left) * (W / r.width)
    setHover(Math.max(0, Math.min(n - 1, Math.round((mx - PL) / iW * (n - 1)))))
  }

  const nivelHoy = hl >= 75 ? 'Óptimo' : hl >= 55 ? 'Bueno' : hl >= 40 ? 'Moderado' : hl >= 25 ? 'Bajo' : 'Crítico'

  return (
    <div>
      {/* Cabecera del módulo */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '0 2px', marginBottom: 10 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Activity size={13} color={NOAH.salvia} strokeWidth={2.3} />
            <span style={eyebrow}>HANNA · proyección 7 días</span>
          </div>
          <div style={{ fontFamily: F, fontSize: 11, color: NOAH.ink45, marginTop: 4 }}>
            Línea base {Math.round(baseline)} · por debajo = riesgo de enfermedad
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: M, fontSize: 30, fontWeight: 700, color: NIVEL[nivelHoy] || NOAH.ink, letterSpacing: -1, lineHeight: 1 }}>{hl != null ? Math.round(hl) : '—'}</div>
          {tendProy && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontFamily: M, fontSize: 11, fontWeight: 700, marginTop: 3, color: tendProy === 'baja' ? NOAH.coral : tendProy === 'sube' ? SEMA.ok : NOAH.ink45 }}>
              {tendProy === 'baja' ? <TrendingDown size={12} /> : tendProy === 'sube' ? <TrendingUp size={12} /> : <Activity size={11} />}
              {pFinal != null ? `→ ${Math.round(pFinal)}` : ''}
            </div>
          )}
        </div>
      </div>

      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`}
        style={{ display: 'block', width: '100%', height: 'auto', cursor: 'crosshair' }}
        onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <defs>
          <linearGradient id="hpArea" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={NOAH.salvia} stopOpacity="0.22" />
            <stop offset="100%" stopColor={NOAH.salvia} stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Zona óptima (sobre la base) y zona de riesgo (bajo la base) */}
        <rect x={PL} y={ys(maxY)} width={iW} height={Math.max(0, ys(baseline) - ys(maxY))} fill={SEMA.ok} opacity="0.05" />
        <rect x={PL} y={ys(umbral)} width={iW} height={Math.max(0, ys(minY) - ys(umbral))} fill={NOAH.coral} opacity="0.07" />

        {/* Grid horizontal suave */}
        {[25, 40, 55, 70, 85].filter(v => v >= minY && v <= maxY).map(v => (
          <line key={v} x1={PL} y1={ys(v)} x2={W - PR} y2={ys(v)} stroke="rgba(41,45,41,0.06)" strokeWidth="1" />
        ))}

        {/* Línea base personal (salvia) + umbral de riesgo (coral) */}
        <line x1={PL} y1={ys(baseline)} x2={W - PR} y2={ys(baseline)} stroke={NOAH.salvia} strokeWidth="1.5" strokeDasharray="7,4" opacity="0.8" />
        <text x={W - PR - 2} y={ys(baseline) - 5} textAnchor="end" fontSize="9" fontFamily={M} fill={NOAH.salvia} opacity="0.9">base {Math.round(baseline)}</text>
        <line x1={PL} y1={ys(umbral)} x2={W - PR} y2={ys(umbral)} stroke={NOAH.coral} strokeWidth="1" strokeDasharray="3,3" opacity="0.45" />

        {/* Área bajo la curva real */}
        <path d={areaD} fill="url(#hpArea)" />

        {/* Curva histórica — tramos coloreados según posición vs. base */}
        {real.slice(1).map((s, i) => (
          <line key={i} x1={xs(i).toFixed(1)} y1={ys(real[i].hl).toFixed(1)} x2={xs(i + 1).toFixed(1)} y2={ys(s.hl).toFixed(1)}
            stroke={segColor((real[i].hl + s.hl) / 2)} strokeWidth="3" strokeLinecap="round" opacity="0.95" />
        ))}

        {/* Divisor HOY / proyección */}
        {proy.length > 0 && (
          <>
            <line x1={xHoy} y1={PT} x2={xHoy} y2={PT + iH} stroke="rgba(41,45,41,0.2)" strokeWidth="1.3" strokeDasharray="4,3" />
            <text x={xHoy + 4} y={PT + 9} fontSize="8" fontFamily={F} fill={NOAH.ink45}>HOY</text>
            <text x={xHoy + 4} y={PT + 19} fontSize="8" fontFamily={F} fill={NOAH.coral}>→ predicción</text>
          </>
        )}

        {/* Predicción — línea punteada */}
        {proyD && (
          <path d={proyD} fill="none" stroke={NOAH.coral} strokeWidth="2.2" strokeDasharray="6,4" strokeLinecap="round" opacity="0.9" />
        )}
        {proy.map((p, i) => (
          <circle key={`p${i}`} cx={xs(pts.length + i)} cy={ys(p.hl)} r="2.4" fill={NOAH.marfil} stroke={NOAH.coral} strokeWidth="1.5" />
        ))}

        {/* Punto de HOY */}
        <circle cx={xHoy} cy={ys(hl)} r="4.5" fill={NIVEL[nivelHoy] || NOAH.salvia} stroke="#fff" strokeWidth="2" />

        {/* Íconos del eje Y: batería llena (óptimo) / termómetro (riesgo) / batería baja */}
        <foreignObject x={PL - 15} y={ys(Math.min(maxY, 92)) - 7} width="15" height="15"><BatteryFull size={13} color={SEMA.ok} /></foreignObject>
        <foreignObject x={PL - 15} y={ys(Math.max(minY + 10, umbral - 6)) - 7} width="15" height="15"><Thermometer size={12} color={NOAH.coral} /></foreignObject>
        <foreignObject x={PL - 15} y={ys(minY + 6) - 7} width="15" height="15"><BatteryLow size={13} color={SEMA.bad} /></foreignObject>

        {/* Tooltip */}
        {hover != null && hover < n && (() => {
          const s = serie[hover]
          const col = s.real ? segColor(s.hl) : NOAH.coral
          const tx = Math.min(xs(hover) + 10, W - PR - 128)
          const ty = PT + 2
          const boxH = s.real ? 60 : 42
          return (
            <g>
              <line x1={xs(hover)} y1={PT} x2={xs(hover)} y2={PT + iH} stroke="rgba(41,45,41,0.12)" strokeWidth="1" />
              <rect x={tx} y={ty} width="124" height={boxH} rx="8" fill="#FBFAF6" stroke={col} strokeWidth="1.3" />
              <text x={tx + 9} y={ty + 14} fontSize="9" fontFamily={F} fill={NOAH.ink45}>{s.real ? s.fecha : 'predicción'}</text>
              <text x={tx + 9} y={ty + 30} fontSize="14" fontFamily={M} fontWeight="700" fill={col}>{Math.round(s.hl)}</text>
              {s.real && s.rv != null && (
                <text x={tx + 9} y={ty + 48} fontSize="9.5" fontFamily={F} fill={s.rv >= 30 ? NOAH.coral : SEMA.ok}>Riesgo viral {Math.round(s.rv)}%</text>
              )}
            </g>
          )
        })()}

        {/* Eje X */}
        {xLabels.map(({ i, label }) => (
          <text key={i} x={xs(i)} y={H - 8} textAnchor="middle" fontSize="9" fontFamily={M} fill={NOAH.ink45}>{label}</text>
        ))}
      </svg>

      {/* Leyenda */}
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', alignItems: 'center', marginTop: 8, padding: '0 2px' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 12, height: 3, borderRadius: 3, background: SEMA.ok }} />sobre la base</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 12, height: 3, borderRadius: 3, background: NOAH.coral }} />bajo la base</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 14, height: 0, borderTop: `2px dashed ${NOAH.coral}` }} />predicción 7d</span>
      </div>

      {/* Referencia de los íconos del eje */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginTop: 6, padding: '0 2px' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: F, fontSize: 9.5, color: NOAH.ink45 }}><BatteryFull size={12} color={SEMA.ok} />óptimo</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: F, fontSize: 9.5, color: NOAH.ink45 }}><Thermometer size={11} color={NOAH.coral} />riesgo de enfermedad</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: F, fontSize: 9.5, color: NOAH.ink45 }}><BatteryLow size={12} color={SEMA.bad} />alerta</span>
      </div>

      {/* Lectura NOAH — MISMA narrativa que ya tiene el proyecto (genNarrativa). */}
      {(() => {
        const frases = []
        if (hl >= 75) frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — sistema autónomo en condiciones óptimas.`)
        else if (hl >= 55) frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — estado aceptable, podés entrenar con carga moderada.`)
        else if (hl >= 40) frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — hay señales de fatiga acumulada. Reducí la carga.`)
        else frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — sistema autónomo comprometido. Priorizar recuperación.`)
        const hrv = hoy?.hrv || 0
        if (hrv > 0) {
          if (hrv < 25) frases.push(`HRV de ${hrv.toFixed(0)}ms es bajo — posible sobrecarga autonómica o mala calidad de sueño.`)
          else if (hrv < 40) frases.push(`HRV de ${hrv.toFixed(0)}ms es moderado — el sistema nervioso autónomo está respondiendo.`)
          else frases.push(`HRV de ${hrv.toFixed(0)}ms es bueno — parasimpático activo, buena recuperación.`)
        }
        if (tsb < -20) frases.push(`TSB ${tsb.toFixed(0)}: carga muy alta. Riesgo de lesión si continuás en zonas 5-6.`)
        else if (tsb < -10) frases.push(`TSB ${tsb.toFixed(0)}: en carga. Tolerás Z3-Z4 pero moderá volumen en zonas altas.`)
        else if (tsb > 10) frases.push(`TSB ${tsb.toFixed(0)}: buena frescura. Podés atacar entrenamientos de calidad.`)
        const sleep = hoy?.hanna_scores?.sueno || 50
        if (sleep < 40) frases.push(`Calidad de sueño baja (${sleep.toFixed(0)}/100). Intentá llegar a 7-8h de sueño reparador.`)
        if (rvHoy >= 50) frases.push(`Riesgo viral ${rvHoy.toFixed(0)}% — RMSSD bajo. Si hay síntomas, no entrenar.`)
        else if (rvHoy >= 30) frases.push(`Riesgo viral moderado (${rvHoy.toFixed(0)}%). Monitoreá síntomas en las próximas 48h.`)
        const pF = proy.length ? proy[proy.length - 1].hl : null
        if (pF != null) {
          if (pF < hl - 5) frases.push(`Proyección a 7 días: tendencia a la baja (${pF.toFixed(0)}). Revisá la carga semanal.`)
          else if (pF > hl + 3) frases.push(`Proyección a 7 días: tendencia favorable (${pF.toFixed(0)}) si mantenés buena recuperación.`)
        }
        if (!frases.length) return null
        return (
          <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 14, background: 'rgba(120,134,107,0.08)', border: `1px solid ${NOAH.border}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <Brain size={14} color={NOAH.salvia} strokeWidth={2.3} />
              <span style={{ ...eyebrow, color: NOAH.salvia }}>Lectura NOAH</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {frases.map((f, i) => (
                <div key={i} style={{ fontFamily: F, fontSize: 12, lineHeight: 1.5, color: NOAH.ink70, paddingLeft: 10, borderLeft: '2px solid rgba(120,134,107,0.4)' }}>{f}</div>
              ))}
            </div>
          </div>
        )
      })()}
    </div>
  )
}

export default function SeccionAnalisis({ atletaId }) {
  const [estado, setEstado] = useState(null)
  const [riesgo, setRiesgo] = useState(null)
  const [hanna, setHanna] = useState(null)
  const [loading, setLoading] = useState(true)
  const [rango, setRango] = useState(1)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    Promise.all([
      authFetch(`${API}/atletas/${atletaId}/estado`).then(r => r.json()).then(r => r.data || r).catch(() => null),
      authFetch(`${API}/atletas/${atletaId}/riesgo_lesion?dias=90`).then(r => r.json()).then(r => r.data).catch(() => null),
      authFetch(`${API}/atletas/${atletaId}/hanna_life?dias=90`).then(r => r.json()).then(r => r.data).catch(() => null),
    ]).then(([e, ri, h]) => { setEstado(e); setRiesgo(ri); setHanna(h); setLoading(false) })
  }, [atletaId])

  if (loading) return <div style={{ padding: 60, textAlign: 'center', fontFamily: F, fontSize: 12.5, color: NOAH.ink45 }}>Cargando análisis…</div>
  const e = estado?.estado || {}
  const training = estado?.training || []
  if (!training.length && e.hanna_life == null) return <div style={{ padding: 28, fontFamily: F, fontSize: 12.5, color: NOAH.ink45 }}>Sin datos de análisis todavía.</div>

  const dias = RANGOS[rango][1]
  const serie = training.slice(-dias).map(d => ({ f: d.d?.slice(5), CTL: d.ctl, ATL: d.atl, TSB: d.tsb }))
  const ctl0 = serie[0]?.CTL, ctl1 = serie[serie.length - 1]?.CTL
  const trend = (ctl0 != null && ctl1 != null && ctl0 !== 0) ? Math.round(((ctl1 - ctl0) / ctl0) * 100) : null

  const hoy = hanna?.hanna_hoy || {}
  const hLife = e.hanna_life ?? hoy.hanna_life
  const hNivel = e.hanna_nivel ?? hoy.hanna_nivel
  const hrvSerie = (hanna?.puntos || []).filter(p => p.hrv != null).slice(-dias).map((p, i) => ({ i, hrv: p.hrv }))
  const rv = hoy.riesgo_viral

  const tsb = e.tsb
  const tsbColor = tsb > 5 ? NOAH.azul : tsb < -15 ? NOAH.coral : NOAH.salvia
  const { body_battery: bb, stress: st, sleep_h: sl, recovery: rc, hrv_ms: hrv } = e
  const colBB = bb > 70 ? SEMA.ok : bb > 40 ? SEMA.warn : SEMA.bad
  const colST = st < 25 ? SEMA.ok : st < 50 ? SEMA.warn : SEMA.bad
  const colSL = sl >= 7 ? SEMA.ok : sl >= 6 ? SEMA.warn : SEMA.bad
  const colRC = rc >= 70 ? SEMA.ok : rc >= 50 ? SEMA.warn : SEMA.bad

  const acwr = riesgo?.acwr
  const acwrHist = (riesgo?.historico_acwr || []).map((h, i) => ({ i, acwr: h.acwr })).filter(p => p.acwr != null)
  const mono = riesgo?.monotonia_strain

  const tipTxt = { background: '#FBFAF6', border: `1px solid ${NOAH.border}`, borderRadius: 10, fontSize: 12, fontFamily: F, color: NOAH.ink, boxShadow: NOAH.shadow }

  return (
    <div style={{ color: NOAH.ink, fontFamily: F, margin: '-14px -12px 0' }}>
      <style>{`@keyframes aRise{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:none}}
        @media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}`}</style>

      {/* ───── A. ENCABEZADO EDITORIAL + HANNA LIFE ───── */}
      <section style={{ position: 'relative' }}>
        <div style={{ position: 'relative', height: 208, overflow: 'hidden' }}>
          <FotoHero />
          <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(90deg, rgba(20,24,20,0.42) 0%, rgba(20,24,20,0.08) 42%, transparent 66%)' }} />
          <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 90, background: `linear-gradient(180deg, transparent, ${NOAH.marfil} 96%)` }} />
          <div style={{ position: 'absolute', top: 18, left: 18 }}>
            <div style={{ fontFamily: F, fontSize: 10.5, fontWeight: 700, letterSpacing: 2, color: 'rgba(255,255,255,0.9)', textTransform: 'uppercase' }}>NOAH · Rendimiento</div>
            <div style={{ fontFamily: F, fontSize: 38, fontWeight: 800, color: '#fff', letterSpacing: -1, lineHeight: 1, marginTop: 4, textShadow: '0 2px 12px rgba(0,0,0,0.4)' }}>Análisis</div>
          </div>
        </div>

        {/* HANNA LIFE — módulo principal, superpuesto a la foto */}
        <div style={{ padding: '0 12px' }}>
          <div style={{ ...glass({ marginTop: -46, padding: '16px', animation: 'aRise .5s both' }) }}>
            <span style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.95), transparent)' }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
              <Anillo valor={hLife} nivel={hNivel} size={116} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <HeartPulse size={13} color={NOAH.salvia} strokeWidth={2.4} />
                  <span style={{ ...eyebrow, color: NOAH.salvia }}>HANNA Life</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px', marginTop: 10 }}>
                  {[['Fitness · CTL', e.ctl != null ? Math.round(e.ctl) : '—'], ['Fatiga · ATL', e.atl != null ? Math.round(e.atl) : '—'], ['HRV', hrv != null ? `${Math.round(hrv)} ms` : '—'], ['Recovery', rc != null ? `${Math.round(rc)}/100` : '—']].map(([l, v]) => (
                    <div key={l}>
                      <div style={{ ...eyebrow, fontSize: 9.5 }}>{l}</div>
                      <div style={{ fontFamily: M, fontSize: 15, fontWeight: 600, color: NOAH.ink }}>{v}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div style={{ padding: '14px 12px 0' }}>
        {/* ───── B. CARGA Y FORMA ───── */}
        <div style={{ display: 'flex', gap: 4, padding: 4, borderRadius: 999, background: 'rgba(41,45,41,0.05)', border: `1px solid ${NOAH.border}`, marginBottom: 12 }}>
          {RANGOS.map(([lbl], i) => (
            <button key={lbl} onClick={() => setRango(i)} style={{ flex: 1, padding: '8px 0', borderRadius: 999, border: 'none', cursor: 'pointer', background: i === rango ? NOAH.grafito : 'transparent', color: i === rango ? '#F3F0E8' : NOAH.ink70, fontFamily: F, fontSize: 12, fontWeight: 700, transition: 'all .2s ease' }}>{lbl}</button>
          ))}
        </div>

        {/* ───── HANNA · PROYECCIÓN Y RIESGO DE ENFERMEDAD ───── */}
        <div style={{ ...surface({ padding: '16px 12px 12px', marginBottom: 14 }) }}>
          <HannaPrediccion puntos={hanna?.puntos} hoy={hoy} dias={dias} />
        </div>

        <div style={{ ...surface({ padding: '16px 12px 10px', marginBottom: 14 }) }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8, padding: '0 4px' }}>
            <span style={eyebrow}>Carga y forma</span>
            {trend != null && (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3, fontFamily: M, fontSize: 12, fontWeight: 700, color: trend >= 0 ? SEMA.ok : NOAH.coral }}>
                {trend >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}{trend > 0 ? '+' : ''}{trend}% CTL
              </span>
            )}
          </div>
          {serie.length > 1 ? (
            <ResponsiveContainer width="100%" height={196}>
              <AreaChart data={serie} margin={{ top: 6, right: 6, left: -18, bottom: 0 }}>
                <defs><linearGradient id="gctl" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={NOAH.coral} stopOpacity={0.26} /><stop offset="100%" stopColor={NOAH.coral} stopOpacity={0} /></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(41,45,41,0.07)" vertical={false} />
                <XAxis dataKey="f" tick={{ fill: NOAH.ink45, fontSize: 9, fontFamily: M }} interval="preserveStartEnd" minTickGap={28} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: NOAH.ink45, fontSize: 9, fontFamily: M }} axisLine={false} tickLine={false} width={34} />
                <Tooltip contentStyle={tipTxt} labelStyle={{ color: NOAH.ink45 }} />
                <ReferenceLine y={0} stroke="rgba(41,45,41,0.18)" />
                <Area type="monotone" dataKey="CTL" stroke={NOAH.coral} strokeWidth={2.5} fill="url(#gctl)" dot={false} name="Fitness" />
                <Line type="monotone" dataKey="ATL" stroke={NOAH.azul} strokeWidth={2} dot={false} name="Fatiga" />
                <Line type="monotone" dataKey="TSB" stroke={NOAH.salvia} strokeWidth={1.6} strokeDasharray="4 3" dot={false} name="Forma" />
              </AreaChart>
            </ResponsiveContainer>
          ) : <div style={{ padding: '24px 8px', textAlign: 'center', fontFamily: F, fontSize: 12, color: NOAH.ink45 }}>Serie insuficiente en este rango.</div>}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 8 }}>
            {[['Fitness', NOAH.coral], ['Fatiga', NOAH.azul], ['Forma', NOAH.salvia]].map(([l, c]) => (
              <span key={l} style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10.5, color: NOAH.ink45 }}>
                <span style={{ width: 10, height: 3, borderRadius: 3, background: c }} />{l}</span>
            ))}
          </div>
        </div>

        {/* ───── C. PREVENCIÓN DE LESIONES ───── */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '0 4px', marginBottom: 10 }}>
          <ShieldAlert size={15} color={NOAH.coral} strokeWidth={2.2} />
          <span style={{ fontFamily: F, fontSize: 14, fontWeight: 800, letterSpacing: -0.2, color: NOAH.ink }}>Prevención de lesiones</span>
        </div>

        {/* ACWR con curva + zonas Gabbett */}
        <div style={{ ...surface({ padding: '14px 12px 10px', marginBottom: 12 }) }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', padding: '0 2px', marginBottom: 6 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Scale size={13} color={NOAH.azul} strokeWidth={2.2} /><span style={eyebrow}>ACWR · carga aguda vs crónica</span></div>
              {acwr?.disponible && <div style={{ fontFamily: F, fontSize: 11, color: NOAH.ink45, marginTop: 4, textTransform: 'capitalize' }}>{acwr.zona?.replace('_', ' ')}</div>}
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontFamily: M, fontSize: 30, fontWeight: 700, color: RIESGO[acwr?.nivel_riesgo] || NOAH.ink, letterSpacing: -1, lineHeight: 1 }}>{acwr?.disponible ? acwr.acwr?.toFixed(2) : '—'}</div>
            </div>
          </div>
          {acwrHist.length > 1 ? (
            <ResponsiveContainer width="100%" height={150}>
              <LineChart data={acwrHist} margin={{ top: 6, right: 8, left: -22, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(41,45,41,0.06)" vertical={false} />
                <ReferenceArea y1={0.8} y2={1.3} fill={NOAH.salvia} fillOpacity={0.12} />
                <ReferenceLine y={1.5} stroke={NOAH.coral} strokeDasharray="4 3" strokeWidth={1} label={{ value: '1.5 riesgo', position: 'insideTopRight', fill: NOAH.coral, fontSize: 9, fontFamily: M }} />
                <ReferenceLine y={0.8} stroke={NOAH.salvia} strokeDasharray="4 3" strokeWidth={1} label={{ value: '0.8', position: 'insideBottomRight', fill: NOAH.salvia, fontSize: 9, fontFamily: M }} />
                <XAxis dataKey="i" hide />
                <YAxis domain={[0.5, 1.8]} tick={{ fill: NOAH.ink45, fontSize: 9, fontFamily: M }} axisLine={false} tickLine={false} width={34} />
                <Tooltip contentStyle={tipTxt} formatter={v => [Number(v).toFixed(2), 'ACWR']} labelFormatter={() => ''} />
                <Line type="monotone" dataKey="acwr" stroke={NOAH.grafito} strokeWidth={2.2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          ) : <div style={{ padding: '16px 8px', textAlign: 'center', fontFamily: F, fontSize: 11.5, color: NOAH.ink45 }}>Historial insuficiente para la curva.</div>}
          {acwr?.mensaje && <div style={{ fontFamily: F, fontSize: 11, color: NOAH.ink70, lineHeight: 1.4, marginTop: 6, padding: '0 2px' }}>{acwr.mensaje}</div>}
        </div>

        {/* Monotonía / Strain + Riesgo viral */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 14 }}>
          <div style={{ ...surface({ padding: '14px' }) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 8 }}><Waves size={13} color={RIESGO[mono?.nivel_riesgo] || NOAH.salvia} strokeWidth={2.2} /><span style={eyebrow}>Monotonía</span></div>
            <div style={{ fontFamily: M, fontSize: 28, fontWeight: 700, color: RIESGO[mono?.nivel_riesgo] || NOAH.ink, letterSpacing: -1, lineHeight: 1 }}>{mono?.disponible ? (mono.monotonia_maxima ? '>2.0' : mono.monotonia?.toFixed(1)) : '—'}</div>
            {mono?.strain != null && <div style={{ fontFamily: M, fontSize: 11, color: NOAH.ink45, marginTop: 5 }}>Strain {Math.round(mono.strain)}</div>}
          </div>
          <div style={{ ...surface({ padding: '14px' }) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 8 }}><ShieldAlert size={13} color={rv >= 60 ? SEMA.bad : rv >= 30 ? SEMA.warn : SEMA.ok} strokeWidth={2.2} /><span style={eyebrow}>Riesgo viral</span></div>
            <div style={{ fontFamily: M, fontSize: 28, fontWeight: 700, color: rv >= 60 ? SEMA.bad : rv >= 30 ? SEMA.warn : SEMA.ok, letterSpacing: -1, lineHeight: 1 }}>{rv != null ? `${Math.round(rv)}` : '—'}<span style={{ fontSize: 12, color: NOAH.ink45 }}>%</span></div>
            <div style={{ fontFamily: F, fontSize: 10.5, color: NOAH.ink45, marginTop: 5 }}>probabilidad</div>
          </div>
        </div>

        {/* ───── D. BIOMARCADORES (visualizaciones diferenciadas) ───── */}
        <div style={{ fontFamily: F, fontSize: 14, fontWeight: 800, letterSpacing: -0.2, color: NOAH.ink, padding: '0 4px', marginBottom: 10 }}>Biomarcadores</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 10 }}>
          <MiniRing Icon={Battery} label="Body Batt." value={bb != null ? Math.round(bb) : null} max={100} unit="/100" color={colBB} delay={0} />
          <MiniRing Icon={Activity} label="Recovery" value={rc != null ? Math.round(rc) : null} max={100} unit="/100" color={colRC} delay={60} />
          <MiniRing Icon={Brain} label="Estrés" value={st != null ? Math.round(st) : null} max={100} unit="/100" color={colST} delay={120} />
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {/* Sueño — barra */}
          <div style={{ ...surface({ padding: '13px 14px' }) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 8 }}><Moon size={12} color={colSL} strokeWidth={2.2} /><span style={{ ...eyebrow, fontSize: 9.5 }}>Sueño</span></div>
            <div style={{ fontFamily: M, fontSize: 24, fontWeight: 700, color: NOAH.ink, letterSpacing: -0.5 }}>{sl != null ? sl.toFixed(1) : '—'}<span style={{ fontSize: 11, color: NOAH.ink45 }}> h</span></div>
            <div style={{ height: 6, borderRadius: 6, background: 'rgba(41,45,41,0.08)', marginTop: 9, overflow: 'hidden' }}>
              <div style={{ height: '100%', width: `${Math.min(100, ((sl || 0) / 9) * 100)}%`, borderRadius: 6, background: colSL, transition: 'width .8s ease' }} />
            </div>
          </div>
          {/* HRV — sparkline */}
          <div style={{ ...surface({ padding: '13px 14px' }) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}><HeartPulse size={12} color={NOAH.salvia} strokeWidth={2.2} /><span style={{ ...eyebrow, fontSize: 9.5 }}>HRV</span></div>
            <div style={{ fontFamily: M, fontSize: 24, fontWeight: 700, color: NOAH.ink, letterSpacing: -0.5 }}>{hrv != null ? Math.round(hrv) : '—'}<span style={{ fontSize: 11, color: NOAH.ink45 }}> ms</span></div>
            {hrvSerie.length > 1 && (
              <ResponsiveContainer width="100%" height={30}>
                <LineChart data={hrvSerie} margin={{ top: 6, right: 0, left: 0, bottom: 0 }}>
                  <Line type="monotone" dataKey="hrv" stroke={NOAH.salvia} strokeWidth={1.8} dot={false} isAnimationActive />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
          {/* TSB — divergente */}
          <div style={{ ...surface({ padding: '13px 14px', gridColumn: '1 / -1' }) }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 9 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Gauge size={12} color={tsbColor} strokeWidth={2.2} /><span style={{ ...eyebrow, fontSize: 9.5 }}>TSB · frescura</span></div>
              <span style={{ fontFamily: M, fontSize: 20, fontWeight: 700, color: tsbColor, letterSpacing: -0.5 }}>{tsb != null ? (tsb > 0 ? `+${Math.round(tsb)}` : Math.round(tsb)) : '—'}</span>
            </div>
            <div style={{ position: 'relative', height: 8, borderRadius: 6, background: 'rgba(41,45,41,0.08)' }}>
              <div style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 1, background: 'rgba(41,45,41,0.22)' }} />
              {tsb != null && (() => {
                const pct = Math.max(-1, Math.min(1, tsb / 30))
                const w = Math.abs(pct) * 50
                return <div style={{ position: 'absolute', top: 0, bottom: 0, left: pct >= 0 ? '50%' : `${50 - w}%`, width: `${w}%`, borderRadius: 6, background: tsbColor, transition: 'all .8s ease' }} />
              })()}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5, fontFamily: F, fontSize: 9, color: NOAH.ink45 }}><span>fatiga</span><span>frescura</span></div>
          </div>
        </div>
      </div>
    </div>
  )
}
