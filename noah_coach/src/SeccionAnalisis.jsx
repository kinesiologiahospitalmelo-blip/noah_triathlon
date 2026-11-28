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
import AlertasCard from './AlertasCard'
import CalibracionHanna from './CalibracionHanna'
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
const AZUL_CLARO = '#7FC0F2'   // línea CUERPO (biomarcadores) — azul clara
const VEREDICTO = {
  cargar:  { label: 'Cargá normal', col: '#35C07A' },
  reducir: { label: 'Reducí / ajustá', col: '#E8A24B' },
  revisar: { label: 'Revisá / recuperá', col: '#E2726E' },
}
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
    ...pts.map(p => ({ hl: p.hanna_life, cuerpo: p.cuerpo, rv: p.riesgo_viral, fecha: p.fecha, real: true })),
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

  // ── Curva CUERPO (estado autónomico: SOLO biomarcadores, sin carga). Es la
  //    lectura "pura" del riesgo viral/enfermedad. La integrada (hanna_life) es
  //    cuerpo × modificador de carga. La DISTANCIA entre ambas = efecto de la
  //    carga de entrenamiento. No agrega lógica: ambos ya vienen del backend.
  const tieneCuerpo = real.filter(s => s.cuerpo != null).length > 1
  const cuerpoD = tieneCuerpo
    ? real.map((s, i) => `${i === 0 ? 'M' : 'L'}${xs(i).toFixed(1)},${ys(s.cuerpo ?? s.hl).toFixed(1)}`).join(' ')
    : ''
  const cuerpoHoy = hoy?.cuerpo ?? pts[pts.length - 1]?.cuerpo
  const gap = (hl != null && cuerpoHoy != null) ? hl - cuerpoHoy : null
  // Área de IMPACTO entre cuerpo (azul) e integrada (HANNA): el relleno = cuánto
  // la carga/estado mueve al cuerpo. Se pinta claro para que se lea el área.
  const impactoD = tieneCuerpo
    ? real.map((s, i) => `${i === 0 ? 'M' : 'L'}${xs(i).toFixed(1)},${ys(s.hl).toFixed(1)}`).join(' ') +
      ' ' + real.slice().reverse().map((s, k) => { const i = real.length - 1 - k; return `L${xs(i).toFixed(1)},${ys(s.cuerpo ?? s.hl).toFixed(1)}` }).join(' ') + ' Z'
    : ''
  const impactoNum = gap != null ? Math.round(gap) : null
  // El TEXTO sale del estado de carga del backend (separa sobrecarga de
  // desentrenamiento) — ya no se adivina por el signo del gap.
  const cEstado = hoy?.carga_estado
  const impactoCol = gap == null ? NOAH.ink45
    : gap > 4 ? SEMA.ok : gap < -4 ? SEMA.warn : NOAH.salvia
  let divTxt = null, divCol = NOAH.ink45
  if (gap != null) {
    if (cuerpoHoy < umbral && gap >= -3) { divTxt = 'Tu cuerpo está bajo y la carga no lo explica — cuidá la recuperación o revisá si quedó carga sin registrar.'; divCol = NOAH.coral }
    else if (cEstado === 'sobrecarga') { divTxt = 'La carga te está pesando: fatiga acumulada, la integrada cae por debajo de tu cuerpo.'; divCol = SEMA.warn }
    else if (cEstado === 'desentrenamiento') { divTxt = 'Venís frenado: la falta de carga —no la carga— explica el bajón de la integrada.'; divCol = SEMA.warn }
    else if (cEstado === 'fresco' || gap > 6) { divTxt = 'Fresco de carga: tu cuerpo rinde mejor que lo que marca la carga — hay margen para cargar.'; divCol = SEMA.ok }
    else { divTxt = 'Cuerpo y carga alineados: la lectura es estable.'; divCol = NOAH.salvia }
  }

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
            Línea base {Math.round(baseline)} · por debajo = señales de alerta
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontFamily: M, fontSize: 30, fontWeight: 700, color: NIVEL[nivelHoy] || NOAH.ink, letterSpacing: -1, lineHeight: 1 }}>{hl != null ? Math.round(hl) : '—'}</div>
          {hoy?.veredicto && VEREDICTO[hoy.veredicto] && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 5, padding: '3px 9px', borderRadius: 20, background: `${VEREDICTO[hoy.veredicto].col}18`, border: `1px solid ${VEREDICTO[hoy.veredicto].col}40` }}>
              <span style={{ width: 6, height: 6, borderRadius: 3, background: VEREDICTO[hoy.veredicto].col }} />
              <span style={{ fontFamily: F, fontSize: 10.5, fontWeight: 700, color: VEREDICTO[hoy.veredicto].col }}>{VEREDICTO[hoy.veredicto].label}</span>
            </div>
          )}
          {tendProy && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 3, fontFamily: M, fontSize: 11, fontWeight: 700, marginTop: 4, color: tendProy === 'baja' ? NOAH.coral : tendProy === 'sube' ? SEMA.ok : NOAH.ink45 }}>
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

        {/* ÁREA DE IMPACTO entre cuerpo e integrada — relleno claro */}
        {impactoD && (
          <path d={impactoD} fill={AZUL_CLARO} opacity="0.14" />
        )}

        {/* Curva CUERPO (estado autónomico, solo biomarcadores) — AZUL CLARA */}
        {cuerpoD && (
          <path d={cuerpoD} fill="none" stroke={AZUL_CLARO} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" opacity="0.95" />
        )}

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

        {/* Punto de HOY — cuerpo (azul clara) e integrada */}
        {cuerpoHoy != null && (
          <circle cx={xHoy} cy={ys(cuerpoHoy)} r="3.2" fill={AZUL_CLARO} stroke="#fff" strokeWidth="1.5" opacity="0.95" />
        )}
        <circle cx={xHoy} cy={ys(hl)} r="4.5" fill={NIVEL[nivelHoy] || NOAH.salvia} stroke="#fff" strokeWidth="2" />

        {/* Íconos del eje Y: batería llena (óptimo) / termómetro (riesgo) / batería baja */}
        <foreignObject x={PL - 15} y={ys(Math.min(maxY, 92)) - 7} width="15" height="15"><BatteryFull size={13} color={SEMA.ok} /></foreignObject>
        <foreignObject x={PL - 15} y={ys(Math.max(minY + 10, umbral - 6)) - 7} width="15" height="15"><Thermometer size={12} color={NOAH.coral} /></foreignObject>
        <foreignObject x={PL - 15} y={ys(minY + 6) - 7} width="15" height="15"><BatteryLow size={13} color={SEMA.bad} /></foreignObject>

        {/* Tooltip */}
        {hover != null && hover < n && (() => {
          const s = serie[hover]
          const col = s.real ? segColor(s.hl) : NOAH.coral
          const tieneC = s.real && s.cuerpo != null
          const tx = Math.min(xs(hover) + 10, W - PR - 132)
          const ty = PT + 2
          const boxH = s.real ? (tieneC ? 76 : 60) : 42
          return (
            <g>
              <line x1={xs(hover)} y1={PT} x2={xs(hover)} y2={PT + iH} stroke="rgba(41,45,41,0.12)" strokeWidth="1" />
              <rect x={tx} y={ty} width="128" height={boxH} rx="8" fill="#FBFAF6" stroke={col} strokeWidth="1.3" />
              <text x={tx + 9} y={ty + 14} fontSize="9" fontFamily={F} fill={NOAH.ink45}>{s.real ? s.fecha : 'predicción'}</text>
              <text x={tx + 9} y={ty + 30} fontSize="14" fontFamily={M} fontWeight="700" fill={col}>{Math.round(s.hl)}<tspan fontSize="8.5" fontFamily={F} fontWeight="400" fill={NOAH.ink45}> integrada</tspan></text>
              {tieneC && (
                <text x={tx + 9} y={ty + 46} fontSize="12" fontFamily={M} fontWeight="700" fill={AZUL_CLARO}>{Math.round(s.cuerpo)}<tspan fontSize="8.5" fontFamily={F} fontWeight="400" fill={NOAH.ink45}> cuerpo</tspan></text>
              )}
              {s.real && s.rv != null && (
                <text x={tx + 9} y={ty + (tieneC ? 64 : 48)} fontSize="9.5" fontFamily={F} fill={s.rv >= 30 ? NOAH.coral : SEMA.ok}>Riesgo viral {Math.round(s.rv)}%</text>
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
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 12, height: 3, borderRadius: 3, background: SEMA.ok }} />integrada · sobre la base</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 12, height: 3, borderRadius: 3, background: NOAH.coral }} />integrada · bajo la base</span>
        {tieneCuerpo && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 12, height: 3, borderRadius: 3, background: AZUL_CLARO }} />cuerpo · solo biomarcadores</span>
        )}
        {impactoNum != null && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 12, height: 10, borderRadius: 2, background: AZUL_CLARO, opacity: 0.25 }} />área = impacto de carga</span>
        )}
        <span style={{ display: 'flex', alignItems: 'center', gap: 5, fontFamily: F, fontSize: 10, color: NOAH.ink45 }}><span style={{ width: 14, height: 0, borderTop: `2px dashed ${NOAH.coral}` }} />predicción 7d</span>
      </div>

      {/* Referencia de los íconos del eje */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', marginTop: 6, padding: '0 2px' }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: F, fontSize: 9.5, color: NOAH.ink45 }}><BatteryFull size={12} color={SEMA.ok} />óptimo</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: F, fontSize: 9.5, color: NOAH.ink45 }}><Thermometer size={11} color={NOAH.coral} />señales de alerta</span>
        <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontFamily: F, fontSize: 9.5, color: NOAH.ink45 }}><BatteryLow size={12} color={SEMA.bad} />alerta</span>
      </div>

      {/* Lectura de divergencia cuerpo ↔ carga + número de impacto */}
      {divTxt && (
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 9, marginTop: 10, padding: '10px 12px', borderRadius: 12, background: `${divCol}12`, border: `1px solid ${divCol}30` }}>
          {impactoNum != null && (
            <div style={{ flex: '0 0 auto', textAlign: 'center', minWidth: 52, paddingRight: 9, borderRight: `1px solid ${divCol}33` }}>
              <div style={{ fontFamily: M, fontSize: 20, fontWeight: 700, color: impactoCol, lineHeight: 1 }}>{impactoNum > 0 ? '+' : ''}{impactoNum}</div>
              <div style={{ fontFamily: F, fontSize: 8, color: NOAH.ink45, letterSpacing: 0.4, textTransform: 'uppercase', marginTop: 3 }}>impacto carga</div>
            </div>
          )}
          <div style={{ fontFamily: F, fontSize: 11.5, color: NOAH.ink, lineHeight: 1.45 }}>
            <span style={{ fontWeight: 700, color: divCol }}>Cuerpo {cuerpoHoy != null ? Math.round(cuerpoHoy) : '—'} · integrada {hl != null ? Math.round(hl) : '—'}</span> — {divTxt}
          </div>
        </div>
      )}

      {/* Lectura NOAH — alineada con el cálculo del backend (sin contradicciones). */}
      {(() => {
        const frases = []
        // 1) Titular: el MISMO mensaje que el semáforo del backend (nunca contradice).
        const band = hl >= 75 ? 'sistema en condiciones óptimas'
          : hl >= 55 ? 'estado aceptable, carga moderada'
          : hl >= 40 ? 'hay fatiga acumulada, reducí la carga'
          : 'sistema comprometido, priorizá recuperación'
        frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — ${hoy?.semaforo_msg || band}.`)
        const hrv = hoy?.hrv || 0
        if (hrv > 0) {
          if (hrv < 25) frases.push(`HRV de ${hrv.toFixed(0)}ms es bajo — posible sobrecarga autonómica o mala calidad de sueño.`)
          else if (hrv < 40) frases.push(`HRV de ${hrv.toFixed(0)}ms es moderado — el sistema nervioso autónomo está respondiendo.`)
          else frases.push(`HRV de ${hrv.toFixed(0)}ms es bueno — parasimpático activo, buena recuperación.`)
        }
        // 2) Carga: separa frescura real de desentrenamiento y de sobrecarga
        //    (usa el estado de carga del backend, no el signo del gap).
        if (cEstado === 'desentrenamiento') frases.push(`Venís de poca carga — es desentrenamiento, no frescura real. Reactivá progresivo.`)
        else if (cEstado === 'sobrecarga') frases.push(`La carga está alta y la fatiga pesa — bajá volumen e intensidad.`)
        else if (cEstado === 'fresco') frases.push(`Fresco por descanso planificado — hay margen para entrenamientos de calidad.`)
        else if (cEstado === 'carga') frases.push(`En carga de entrenamiento — tolerás calidad, moderá el volumen en zonas altas.`)
        const sleep = hoy?.hanna_scores?.sueno_dur || hoy?.hanna_scores?.sueno
        if (sleep != null && sleep < 40) frases.push(`Sueño por debajo de lo recomendado (${sleep.toFixed(0)}/100). Apuntá a 7-8h de calidad.`)
        // 3) Enfermedad unificada, con fuente etiquetada (medido / estimado).
        const enfPct = hoy?.riesgo_enf_pct, enfFuente = hoy?.riesgo_enf_fuente
        const nota = enfFuente === 'estimado' ? ' (HRV estimado — orientativo)' : ''
        if (enfPct != null && enfPct >= 50) frases.push(`Varias señales de alerta en tu recuperación${nota}. Aflojá la carga; si no te sentís bien, consultá a un profesional. No es un diagnóstico.`)
        else if (enfPct != null && enfPct >= 30) frases.push(`Algunas señales de alerta en tu recuperación${nota}. Cuidá la carga y observá cómo evolucionás estos días.`)
        else if (enfFuente === 'no_evaluable') frases.push(`Recuperación: sin datos suficientes para evaluar señales de alerta.`)
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
  const [recalc, setRecalc] = useState('idle')

  const recalcularHanna = () => {
    if (!atletaId || recalc === 'run') return
    setRecalc('run')
    authFetch(`${API}/atletas/${atletaId}/recalcular_hanna`, { method: 'POST' })
      .then(r => r.json())
      .then(() => { setRecalc('done'); setTimeout(() => window.location.reload(), 500) })
      .catch(() => setRecalc('idle'))
  }

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
  // Fecha del dato de biomarcadores más reciente (el backend completa cada
  // métrica con su último valor disponible + '_fecha'): así avisamos si es de
  // hoy o de un día anterior, en vez de mostrar un dato stale como actual.
  const _hoyISO = new Date().toISOString().slice(0, 10)
  const _fechasBio = ['bb_fecha', 'sleep_fecha', 'stress_fecha', 'hrv_fecha', 'hr_reposo_fecha']
    .map(k => hoy?.[k]).filter(Boolean).sort()
  const bioFecha = _fechasBio.length ? _fechasBio[_fechasBio.length - 1] : null
  const bioFechaLabel = bioFecha
    ? (bioFecha === _hoyISO ? 'actualizado hoy' : `último dato: ${bioFecha.slice(8, 10)}/${bioFecha.slice(5, 7)}`)
    : null
  const hLife = e.hanna_life ?? hoy.hanna_life
  const hNivel = e.hanna_nivel ?? hoy.hanna_nivel
  const hrvSerie = (hanna?.puntos || []).filter(p => p.hrv != null).slice(-dias).map((p, i) => ({ i, hrv: p.hrv }))
  // Riesgo de enfermedad UNIFICADO (viral + centinela) con fuente etiquetada.
  const enf = hoy.riesgo_enf_pct
  const enfFuente = hoy.riesgo_enf_fuente     // medido / estimado / no_evaluable
  const enfColor = enf == null ? NOAH.ink45 : enf >= 60 ? SEMA.bad : enf >= 30 ? SEMA.warn : SEMA.ok
  const fuenteLabel = { medido: 'medido', estimado: 'estimativo', no_evaluable: 'no evaluable' }[enfFuente] || null

  // ── Arquitectura del sueño (REM / profundo / liviano) — hoy + 7 días ──────
  // Norma de arquitectura adulta (Ohayon 2004): REM ~20-25%, profundo ~13-23%.
  const slH = hoy?.sleep_h ?? e.sleep_h
  const pctDe = h => (h != null && slH) ? Math.round((h / slH) * 100) : null
  const remPct = pctDe(hoy?.rem_h), deepPct = pctDe(hoy?.deep_h), lightPct = pctDe(hoy?.light_h)
  const sueCal = hoy?.hanna_scores?.sueno_cal
  const stageCol = (p, lo) => p == null ? NOAH.ink45 : p >= lo ? SEMA.ok : p >= lo * 0.72 ? SEMA.warn : NOAH.coral
  const remCol = stageCol(remPct, 18), deepCol = stageCol(deepPct, 12)
  const sleep7 = (hanna?.puntos || []).filter(p => p.sleep && (p.rem_h != null || p.deep_h != null)).slice(-7)
  const prom7 = key => { const vs = sleep7.map(p => (p.sleep ? (p[key] / p.sleep) * 100 : null)).filter(v => v != null && isFinite(v)); return vs.length ? Math.round(vs.reduce((a, b) => a + b, 0) / vs.length) : null }
  const rem7 = prom7('rem_h'), deep7 = prom7('deep_h')
  const lecturaSueno = (() => {
    if (remPct == null && deepPct == null) return null
    const partes = []
    if (remPct != null) partes.push(remPct >= 18 ? `REM ${remPct}% (bien)` : `REM ${remPct}% bajo (ideal 20-25%)`)
    if (deepPct != null) partes.push(deepPct >= 12 ? `profundo ${deepPct}% (bien)` : `profundo ${deepPct}% bajo (ideal 13-23%)`)
    let txt = `Dormiste ${slH != null ? slH.toFixed(1) : '—'}h — ${partes.join(' · ')}.`
    if (rem7 != null || deep7 != null) txt += ` Promedio 7 días: ${rem7 != null ? `REM ${rem7}%` : ''}${rem7 != null && deep7 != null ? ' · ' : ''}${deep7 != null ? `profundo ${deep7}%` : ''}.`
    return txt
  })()

  // Centinela de aviso temprano (complementa al riesgo viral, no lo reemplaza):
  // FC reposo en alza + variabilidad (CV) de HRV subiendo. Datos del backend.
  const cent = { nivel: hoy.centinela_nivel, msg: hoy.centinela_msg, dFC: hoy.fc_reposo_delta, cv: hoy.hrv_cv }
  const centCol = { ok: NOAH.salvia, leve: NOAH.azul, alerta: SEMA.warn, alto: NOAH.coral }[cent.nivel] || NOAH.ink45
  const centLabel = { ok: 'estable', leve: 'señal leve', alerta: 'en alerta', alto: 'señal marcada' }[cent.nivel] || '—'

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

      {/* Recalcular HANNA sobre todo el historial (ver el efecto de la lógica nueva) */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', padding: '0 4px 8px' }}>
        <button onClick={recalcularHanna} disabled={recalc === 'run'} style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 999,
          border: `1px solid ${NOAH.border}`, background: NOAH.surface, cursor: recalc === 'run' ? 'default' : 'pointer',
          fontFamily: F, fontSize: 11, fontWeight: 600, color: NOAH.ink70,
        }}>
          <Activity size={12} color={NOAH.salvia} strokeWidth={2.3} />
          {recalc === 'run' ? 'Recalculando…' : recalc === 'done' ? 'Listo ✓' : 'Recalcular HANNA'}
        </button>
      </div>

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
        <AlertasCard atletaId={atletaId} />
      </div>

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

        {/* Aprendizaje: percepción del atleta vs HANNA */}
        <CalibracionHanna atletaId={atletaId} />

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
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}><ShieldAlert size={13} color={enfColor} strokeWidth={2.2} /><span style={eyebrow}>Alerta de recuperación</span></div>
              {fuenteLabel && (
                <span style={{ fontFamily: F, fontSize: 8.5, fontWeight: 700, color: enfFuente === 'medido' ? NOAH.salvia : NOAH.ink45, textTransform: 'uppercase', letterSpacing: 0.4, padding: '2px 6px', borderRadius: 999, background: enfFuente === 'medido' ? 'rgba(120,134,107,0.12)' : 'rgba(41,45,41,0.05)', border: `1px solid ${NOAH.border}` }}>{fuenteLabel}</span>
              )}
            </div>
            {enf != null ? (
              <>
                <div style={{ fontFamily: M, fontSize: 28, fontWeight: 700, color: enfColor, letterSpacing: -1, lineHeight: 1 }}>{Math.round(enf)}<span style={{ fontSize: 12, color: NOAH.ink45 }}>%</span></div>
                <div style={{ fontFamily: F, fontSize: 10.5, color: NOAH.ink45, marginTop: 5 }}>{enfFuente === 'estimado' ? 'señales · HRV estimado' : 'señales de alerta (no es diagnóstico)'}</div>
              </>
            ) : (
              <>
                <div style={{ fontFamily: M, fontSize: 20, fontWeight: 700, color: NOAH.ink45, letterSpacing: -0.5, lineHeight: 1.1 }}>no evaluable</div>
                <div style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, marginTop: 5, lineHeight: 1.35 }}>sin HRV de reloj ni señales tempranas</div>
              </>
            )}
          </div>
        </div>

        {/* Centinela de aviso temprano — FC reposo + variabilidad HRV */}
        {cent.nivel && (
          <div style={{ ...surface({ padding: '14px', marginBottom: 14 }), borderColor: `${centCol}40` }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldAlert size={13} color={centCol} strokeWidth={2.3} />
                <span style={eyebrow}>Aviso temprano</span>
              </div>
              <span style={{ fontFamily: F, fontSize: 10.5, fontWeight: 700, color: centCol, padding: '3px 9px', borderRadius: 999, background: `${centCol}16`, border: `1px solid ${centCol}33`, textTransform: 'capitalize' }}>{centLabel}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              <div style={{ padding: '10px 12px', borderRadius: 12, background: 'rgba(41,45,41,0.035)', border: `1px solid ${NOAH.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}><HeartPulse size={12} color={cent.dFC >= 3 ? NOAH.coral : NOAH.salvia} strokeWidth={2.3} /><span style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, letterSpacing: 0.3 }}>Pulso en reposo vs tu base</span></div>
                <div style={{ fontFamily: M, fontSize: 24, fontWeight: 700, color: cent.dFC >= 3 ? NOAH.coral : NOAH.ink, letterSpacing: -0.6, lineHeight: 1 }}>
                  {cent.dFC != null ? `${cent.dFC > 0 ? '+' : ''}${cent.dFC.toFixed(0)}` : '—'}<span style={{ fontSize: 11, color: NOAH.ink45, fontWeight: 400 }}> lpm</span>
                </div>
                <div style={{ fontFamily: F, fontSize: 9, color: NOAH.ink45, marginTop: 5, lineHeight: 1.35 }}>
                  {cent.dFC == null ? 'latidos por minuto respecto de tu promedio'
                    : cent.dFC <= 0 ? 'por debajo de tu base = buena señal'
                    : 'por encima de tu base = posible aviso de infección'}
                </div>
              </div>
              <div style={{ padding: '10px 12px', borderRadius: 12, background: 'rgba(41,45,41,0.035)', border: `1px solid ${NOAH.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 6 }}><Activity size={12} color={AZUL_CLARO} strokeWidth={2.3} /><span style={{ fontFamily: F, fontSize: 10, color: NOAH.ink45, letterSpacing: 0.3 }}>Estabilidad del HRV</span></div>
                <div style={{ fontFamily: M, fontSize: 24, fontWeight: 700, color: NOAH.ink, letterSpacing: -0.6, lineHeight: 1 }}>
                  {cent.cv != null ? `${cent.cv.toFixed(0)}` : '—'}<span style={{ fontSize: 11, color: NOAH.ink45, fontWeight: 400 }}>%</span>
                </div>
                <div style={{ fontFamily: F, fontSize: 9, color: NOAH.ink45, marginTop: 5, lineHeight: 1.35 }}>
                  cuánto varía tu HRV día a día — sube = sistema inestable
                </div>
              </div>
            </div>
            {cent.msg && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, marginTop: 10, padding: '9px 11px', borderRadius: 10, background: `${centCol}10`, border: `1px solid ${centCol}26` }}>
                <Activity size={12} color={centCol} strokeWidth={2.3} style={{ flex: '0 0 auto', marginTop: 1 }} />
                <span style={{ fontFamily: F, fontSize: 11, color: NOAH.ink70, lineHeight: 1.45 }}>{cent.msg}</span>
              </div>
            )}
            <div style={{ fontFamily: F, fontSize: 9.5, color: NOAH.ink45, marginTop: 8, lineHeight: 1.4 }}>
              Complementa al riesgo viral: adelanta señales que la caída de HRV todavía no muestra (Flatt &amp; Esco).
            </div>
          </div>
        )}

        {/* ───── D. BIOMARCADORES (visualizaciones diferenciadas) ───── */}
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '0 4px', marginBottom: 10 }}>
          <span style={{ fontFamily: F, fontSize: 14, fontWeight: 800, letterSpacing: -0.2, color: NOAH.ink }}>Biomarcadores</span>
          {bioFechaLabel && <span style={{ fontFamily: F, fontSize: 10.5, color: NOAH.ink45 }}>{bioFechaLabel}</span>}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 10 }}>
          <MiniRing Icon={Battery} label="Body Batt." value={bb != null ? Math.round(bb) : null} max={100} unit="/100" color={colBB} delay={0} />
          <MiniRing Icon={Activity} label="Recovery" value={rc != null ? Math.round(rc) : null} max={100} unit="/100" color={colRC} delay={60} />
          <MiniRing Icon={Brain} label="Estrés" value={st != null ? Math.round(st) : null} max={100} unit="/100" color={colST} delay={120} />
        </div>

        {/* Arquitectura del sueño — REM / profundo / liviano en anillos + lectura 7d */}
        {(remPct != null || deepPct != null) && (
          <div style={{ ...surface({ padding: '14px 14px 12px', marginBottom: 10 }) }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, padding: '0 2px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <Moon size={13} color={NOAH.salvia} strokeWidth={2.3} />
                <span style={eyebrow}>Arquitectura del sueño</span>
              </div>
              {sueCal != null && (
                <span style={{ fontFamily: M, fontSize: 12, fontWeight: 700, color: sueCal >= 62 ? SEMA.ok : sueCal >= 40 ? SEMA.warn : NOAH.coral }}>
                  calidad {Math.round(sueCal)}<span style={{ fontSize: 9, color: NOAH.ink45, fontWeight: 400 }}>/100</span>
                </span>
              )}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
              <MiniRing Icon={Moon} label="REM" value={remPct} max={35} unit={hoy?.rem_h != null ? `${hoy.rem_h.toFixed(1)}h · ideal 20-25%` : '%'} color={remCol} delay={0} />
              <MiniRing Icon={Moon} label="Profundo" value={deepPct} max={30} unit={hoy?.deep_h != null ? `${hoy.deep_h.toFixed(1)}h · ideal 13-23%` : '%'} color={deepCol} delay={60} />
              <MiniRing Icon={Moon} label="Liviano" value={lightPct} max={70} unit={hoy?.light_h != null ? `${hoy.light_h.toFixed(1)}h` : '%'} color={NOAH.salvia} delay={120} />
            </div>
            {lecturaSueno && (
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, marginTop: 11, padding: '9px 11px', borderRadius: 10, background: 'rgba(120,134,107,0.08)', border: `1px solid ${NOAH.border}` }}>
                <Brain size={12} color={NOAH.salvia} strokeWidth={2.3} style={{ flex: '0 0 auto', marginTop: 1 }} />
                <span style={{ fontFamily: F, fontSize: 11, color: NOAH.ink70, lineHeight: 1.45 }}>{lecturaSueno}</span>
              </div>
            )}
          </div>
        )}
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
