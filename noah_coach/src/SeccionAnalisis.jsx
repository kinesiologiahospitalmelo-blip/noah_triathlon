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
  Gauge, Scale, Waves, ShieldAlert,
} from 'lucide-react'
import { NOAH, FONT } from './noahTheme'
// Foto editorial servida desde public/assets (como el resto de imágenes del proyecto).
// Si todavía no está subida, el build NO se rompe: solo no se muestra la imagen.
const heroImg = `${process.env.PUBLIC_URL || ''}/assets/analisis_hero.jpg`

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
  const hSerie = (hanna?.puntos || []).filter(p => p.hanna_life != null).slice(-dias).map((p, i) => ({ i, hl: p.hanna_life }))
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
          <img src={heroImg} alt="Atleta NOAH" style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 32%' }} />
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
            {hSerie.length > 1 && (
              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid rgba(41,45,41,0.08)' }}>
                <div style={{ ...eyebrow, fontSize: 9.5, marginBottom: 2 }}>HANNA · últimos {hSerie.length} días</div>
                <ResponsiveContainer width="100%" height={46}>
                  <AreaChart data={hSerie} margin={{ top: 4, right: 2, left: 2, bottom: 0 }}>
                    <defs><linearGradient id="ghl" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor={NOAH.salvia} stopOpacity={0.34} /><stop offset="100%" stopColor={NOAH.salvia} stopOpacity={0} /></linearGradient></defs>
                    <Area type="monotone" dataKey="hl" stroke={NOAH.salvia} strokeWidth={2} fill="url(#ghl)" dot={false} isAnimationActive />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
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
