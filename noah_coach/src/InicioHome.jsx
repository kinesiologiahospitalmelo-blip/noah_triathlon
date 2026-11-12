// src/InicioHome.jsx — NOAH · Inicio (Opción 1 · editorial premium)
// SOLO presentación. Datos y acciones llegan por props reales del proyecto.
// No inventa datos ni imágenes. Usa exclusivamente lo recibido en props.
// Semana = 3 anillos (horas + distribución de zonas). HANNA LIFE = anillo + info.
// Movimiento con propósito y respeto de prefers-reduced-motion.
import { useState, useEffect, useMemo } from 'react'
import {
  Dumbbell, BarChart3, ClipboardCheck, Trophy, HeartPulse, Brain,
  Waves, Bike, Footprints, MessageCircle, Home, User, Camera,
  BatteryFull, BatteryLow, Zap, RefreshCw,
} from 'lucide-react'
import { NOAH, DEPORTE, SERIES, FONT } from './noahTheme'

// Semáforo (tonos del estilo nuevo)
const SEMA = { ok: '#35C07A', warn: '#E6B655', bad: '#E2726E' }
const AZUL = '#1C8FC4' // azul clásico v1.0.1 (#38BDF8), tono legible sobre marfil
const NIVEL_COLOR = { 'Óptimo': SEMA.ok, 'Bueno': NOAH.azul, 'Moderado': SEMA.warn, 'Bajo': NOAH.coral, 'Crítico': SEMA.bad }

// Identidad por disciplina + tintes de zona (endurance / umbral / vo2)
const DEP = [
  { key: 'swim', label: 'SWIM', Icon: Waves, color: DEPORTE.swim, tints: SERIES.azul },
  { key: 'bike', label: 'BIKE', Icon: Bike, color: DEPORTE.bike, tints: SERIES.salvia },
  { key: 'run', label: 'RUN', Icon: Footprints, color: DEPORTE.run, tints: SERIES.coral },
]

const ACCESOS_DEFAULT = [
  { id: 'entrenamiento', label: 'Entrenamiento', Icon: Dumbbell },
  { id: 'analisis', label: 'Análisis', Icon: BarChart3 },
  { id: 'evaluaciones', label: 'Evaluaciones', Icon: ClipboardCheck },
  { id: 'competicion', label: 'Competición', Icon: Trophy },
  { id: 'bienestar', label: 'Bienestar', Icon: HeartPulse },
  { id: 'twin', label: 'Mi Twin', Icon: Brain },
]
const NAV_DEFAULT = [
  { id: 'inicio', label: 'Inicio', Icon: Home },
  { id: 'entreno', label: 'Entreno', Icon: Dumbbell },
  { id: 'analisis', label: 'Análisis', Icon: BarChart3 },
  { id: 'perfil', label: 'Perfil', Icon: User },
]

function usePrefersReducedMotion() {
  const [reduce, setReduce] = useState(false)
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const m = window.matchMedia('(prefers-reduced-motion: reduce)')
    setReduce(m.matches)
    const h = e => setReduce(e.matches)
    m.addEventListener ? m.addEventListener('change', h) : m.addListener(h)
    return () => { m.removeEventListener ? m.removeEventListener('change', h) : m.removeListener(h) }
  }, [])
  return reduce
}

const fmtHoras = h => {
  if (h == null) return '—'
  const t = Math.round(Number(h) * 60)
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}

// Helpers de color: separar claramente las 3 zonas dentro de un mismo color
const _rgb = h => { const s = h.replace('#', ''); return [0, 2, 4].map(i => parseInt(s.slice(i, i + 2), 16)) }
const _mix = (hex, tgt, a) => { const [r1, g1, b1] = _rgb(hex), [r2, g2, b2] = _rgb(tgt); const m = (x, y) => Math.round(x + (y - x) * a); return `#${[m(r1, r2), m(g1, g2), m(b1, b2)].map(v => v.toString(16).padStart(2, '0')).join('')}` }
const lighten = (h, a) => _mix(h, '#ffffff', a)
const darken  = (h, a) => _mix(h, '#000000', a)

// ── Anillo de disciplina: horas + pct al centro; Endurance/FTP/VO₂ en aro y filas ──
function SportRing({ d, s, anim, delay = 0 }) {
  const R = 30, STROKE = 8.5, CX = 40, CY = 40, C = 2 * Math.PI * R
  const horas = s?.horas, pct = s?.pct, z = s?.zonas
  const cEnd = lighten(d.color, 0.50), cFtp = d.color, cVo2 = darken(d.color, 0.30)
  const zonas = z ? [
    { k: 'Endurance', v: z.endurance, c: cEnd, glow: false },
    { k: 'FTP',       v: z.threshold, c: cFtp, glow: false },
    { k: 'VO₂',       v: z.vo2,       c: cVo2, glow: true  },
  ] : null
  const GAP = 0.014 // separación visible entre segmentos
  let off = 0
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9, flex: 1, minWidth: 0, ...(anim ? { animation: 'noahRise .6s both', animationDelay: `${delay}ms` } : {}) }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        <d.Icon size={14} color={d.color} strokeWidth={2.4} />
        <span style={{ fontFamily: FONT.base, fontSize: 11, fontWeight: 700, letterSpacing: 0.8, color: d.color }}>{d.label}</span>
      </div>
      <div style={{ position: 'relative', width: 80, height: 80 }}>
        <svg viewBox="0 0 80 80" style={{ width: 80, height: 80 }}>
          <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(41,45,41,0.09)" strokeWidth={STROKE} />
          {zonas ? zonas.map((g, i) => {
            const f = Math.max(0, (g.v || 0)) / 100
            const draw = Math.max(0, f - GAP)
            const el = (
              <circle key={i} cx={CX} cy={CY} r={R} fill="none" stroke={g.c} strokeWidth={STROKE} strokeLinecap="butt"
                strokeDasharray={`${draw * C} ${C}`} strokeDashoffset={-(off * C)}
                transform={`rotate(-90 ${CX} ${CY})`}
                style={{ ...(g.glow ? { filter: `drop-shadow(0 0 3px ${g.c}bb)` } : {}), ...(anim ? { transition: 'stroke-dasharray .7s cubic-bezier(.4,0,.2,1)' } : {}) }} />
            )
            off += f
            return el
          }) : <circle cx={CX} cy={CY} r={R} fill="none" stroke={`${d.color}3a`} strokeWidth={STROKE} />}
        </svg>
        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontFamily: FONT.mono, fontSize: 16, fontWeight: 600, color: NOAH.ink, letterSpacing: -0.5, lineHeight: 1 }}>{fmtHoras(horas)}</span>
          {pct != null && <span style={{ fontFamily: FONT.mono, fontSize: 10, color: NOAH.ink45, marginTop: 1 }}>{pct}%</span>}
        </div>
      </div>
      {/* Distribución Endurance / FTP / VO₂ con su valor (fundamental) */}
      {zonas && (
        <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {zonas.map(g => (
            <div key={g.k} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 7, height: 7, borderRadius: 2, background: g.c, flex: '0 0 auto' }} />
              <span style={{ fontFamily: FONT.base, fontSize: 10, color: NOAH.ink70, flex: 1, whiteSpace: 'nowrap' }}>{g.k}</span>
              <span style={{ fontFamily: FONT.mono, fontSize: 11, fontWeight: 600, color: NOAH.ink }}>{g.v != null ? `${Math.round(g.v)}%` : '—'}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Anillo HANNA LIFE (valor 0–100) ──
function HannaRing({ valor, nivel, anim }) {
  const R = 40, STROKE = 8, CX = 52, CY = 52, C = 2 * Math.PI * R
  const v = Math.max(0, Math.min(100, Number(valor) || 0))
  const color = NIVEL_COLOR[nivel] || NOAH.salvia
  return (
    <div style={{ position: 'relative', width: 104, height: 104, flex: '0 0 auto' }}>
      <svg viewBox="0 0 104 104" style={{ width: 104, height: 104 }}>
        <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(41,45,41,0.08)" strokeWidth={STROKE} />
        <circle cx={CX} cy={CY} r={R} fill="none" stroke={color} strokeWidth={STROKE} strokeLinecap="round"
          strokeDasharray={`${(v / 100) * C} ${C}`} transform={`rotate(-90 ${CX} ${CY})`}
          style={anim ? { transition: 'stroke-dasharray .9s cubic-bezier(.4,0,.2,1)' } : undefined} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: FONT.mono, fontSize: 28, fontWeight: 600, color: NOAH.ink, letterSpacing: -1, lineHeight: 1 }}>{valor != null ? valor : '—'}</span>
        {nivel && <span style={{ fontFamily: FONT.base, fontSize: 10.5, fontWeight: 700, color, marginTop: 3 }}>{nivel}</span>}
      </div>
    </div>
  )
}

export default function InicioHome({
  atleta = {}, semana = {}, hanna = null, syncStatus = null, bioLoading, actLoading,
  onSyncBio = () => {}, onSyncAct = () => {}, onAcceso = () => {}, onAsistente = () => {},
  onSubirFoto = () => {}, navActivo = 'inicio', onNav = () => {}, hannaSlot = null, semanaSlot = null,
  accesos = ACCESOS_DEFAULT, nav = NAV_DEFAULT,
  logo = '/assets/noah_logo_icono_negro.png',
  fotoFallback = '/assets/noah_avatar_m.png',
}) {
  const [imgErr, setImgErr] = useState(false)
  const reduce = usePrefersReducedMotion()
  const anim = !reduce
  const nombre = atleta.nombre || 'Atleta'
  const propia = !!(atleta.foto && !imgErr)
  const foto = propia ? atleta.foto : fotoFallback

  const rise = (d = 0) => (anim ? { animation: `noahRise .62s cubic-bezier(.22,.61,.36,1) both`, animationDelay: `${d}ms` } : undefined)

  const totalHoras = useMemo(() => DEP.reduce((a, d) => a + (Number(semana[d.key]?.horas) || 0), 0), [semana])
  const conDatos = DEP.some(d => semana[d.key] && (semana[d.key].horas > 0 || semana[d.key].pct > 0))

  // HANNA: valores reales recibidos
  const hv = hanna?.valor
  const sema = hv == null ? null : hv >= 55 ? { c: SEMA.ok, Icon: BatteryFull, t: 'Puede cargar' }
    : hv >= 40 ? { c: SEMA.warn, Icon: Zap, t: 'Carga reducida' }
    : { c: SEMA.bad, Icon: BatteryLow, t: 'Solo recuperación' }
  const stats = hanna ? [
    { k: 'HRV', v: hanna.hrv != null ? `${Math.round(hanna.hrv)}` : null, u: 'ms' },
    { k: 'TSB', v: hanna.tsb != null ? `${hanna.tsb > 0 ? '+' : ''}${Math.round(hanna.tsb)}` : null, u: '' },
    { k: 'Sueño', v: hanna.sueno != null ? `${Math.round(hanna.sueno)}` : null, u: '/100' },
    { k: 'Riesgo viral', v: hanna.riesgo_viral != null ? `${Math.round(hanna.riesgo_viral)}` : null, u: '%' },
  ].filter(x => x.v != null) : []

  // Sync (LED de estado, dato real)
  const led = (esHoy, dias) => esHoy ? SEMA.ok : (dias != null && dias < 2) ? SEMA.warn : SEMA.bad
  const ledTxt = (esHoy, dias) => esHoy ? 'hoy' : (dias != null && dias < 999) ? `hace ${dias}d` : 'sin datos'

  return (
    <div style={{
      minHeight: '100vh', paddingBottom: 148, color: NOAH.ink, fontFamily: FONT.base,
      background: `radial-gradient(120% 60% at 85% -8%, rgba(230,91,69,0.08) 0%, transparent 46%),
        radial-gradient(90% 50% at 10% 108%, rgba(120,134,107,0.09) 0%, transparent 52%),
        ${NOAH.marfil}`,
    }}>
      <style>{`
        @keyframes noahRise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
        @keyframes noahFloat{0%,100%{transform:translateY(0)}50%{transform:translateY(-6px)}}
        @keyframes noahspin{to{transform:rotate(360deg)}}
        .noah-tile{transition:transform .22s cubic-bezier(.22,.61,.36,1),box-shadow .22s ease}
        .noah-tile:hover{transform:translateY(-3px)}
        .noah-press{transition:transform .12s ease}
        .noah-press:active{transform:scale(.97)}
        @media (prefers-reduced-motion: reduce){
          .noah-tile,.noah-press{transition:none}.noah-float{animation:none !important}
        }
      `}</style>

      <div style={{ maxWidth: 440, margin: '0 auto' }}>

        {/* ── 1 · HERO editorial: atleta protagonista + marca + saludo ── */}
        <section style={{ position: 'relative', height: 312, overflow: 'hidden', borderBottomLeftRadius: 30, borderBottomRightRadius: 30, ...rise(0) }}>
          <svg viewBox="0 0 440 312" preserveAspectRatio="xMidYMid slice" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
            <rect width="440" height="312" fill={NOAH.marfil} />
            <circle className="noah-float" cx="372" cy="60" r="150" fill={NOAH.coral} opacity="0.14"
              style={anim ? { animation: 'noahFloat 7s ease-in-out infinite' } : undefined} />
            <circle cx="60" cy="330" r="130" fill={NOAH.salvia} opacity="0.12" />
          </svg>

          <div style={{ position: 'absolute', right: 0, top: 0, bottom: 0, width: '60%' }}>
            <img src={foto} alt={nombre} onError={() => setImgErr(true)}
              style={{ width: '100%', height: '100%', objectFit: 'cover', objectPosition: '50% 20%' }} />
            <div style={{ position: 'absolute', inset: 0, background: `linear-gradient(90deg, ${NOAH.marfil} 2%, rgba(243,240,232,0.55) 30%, rgba(243,240,232,0.08) 56%, transparent 72%)` }} />
            <div style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 120, background: `linear-gradient(180deg, transparent, ${NOAH.marfil} 94%)` }} />
            <button onClick={onSubirFoto} aria-label="Cambiar foto" className="noah-press" style={{
              position: 'absolute', right: 14, top: 64, width: 34, height: 34, borderRadius: 999, cursor: 'pointer',
              background: 'rgba(41,45,41,0.42)', border: '1.5px solid rgba(255,255,255,0.8)', backdropFilter: 'blur(4px)',
              display: 'grid', placeItems: 'center',
            }}>
              <Camera size={15} color="#fff" strokeWidth={2.2} />
            </button>
          </div>

          <div style={{ position: 'absolute', top: 18, left: 20, display: 'flex', alignItems: 'center', gap: 9 }}>
            <img src={logo} alt="NOAH" style={{ width: 34, height: 34, borderRadius: 10, objectFit: 'cover', boxShadow: NOAH.shadow }} />
            <span style={{ fontFamily: FONT.base, fontWeight: 700, fontSize: 20, letterSpacing: -0.3, color: NOAH.grafito }}>noah<span style={{ color: NOAH.azul }}>°</span></span>
          </div>

          <div style={{ position: 'absolute', left: 20, bottom: 30, maxWidth: '68%' }}>
            <div style={{ fontFamily: FONT.base, fontSize: 12, fontWeight: 700, letterSpacing: 2, color: NOAH.salvia, textTransform: 'uppercase' }}>Hola</div>
            <div style={{ fontFamily: FONT.base, fontSize: 40, fontWeight: 700, color: NOAH.grafito, lineHeight: 1, letterSpacing: -1, marginTop: 2 }}>{nombre}</div>
            <div style={{ fontFamily: FONT.base, fontSize: 13.5, color: NOAH.ink70, marginTop: 10, lineHeight: 1.35 }}>Entrená más inteligente.<br />Rendí mejor.</div>
          </div>
        </section>

        <div style={{ padding: '0 16px' }}>

          {/* ── 2 · SEMANA: 3 anillos horizontales (horas + distribución) ── */}
          <section className="noah-tile" style={{
            position: 'relative', marginTop: -20, zIndex: 2,
            background: NOAH.surface, border: `1px solid ${NOAH.border}`, borderRadius: 20,
            boxShadow: '0 2px 4px rgba(41,45,41,0.04), 0 18px 40px -22px rgba(41,45,41,0.5)',
            padding: '14px 12px 14px', ...rise(90),
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12, padding: '0 2px' }}>
              <span style={{ fontFamily: FONT.base, fontSize: 11, fontWeight: 700, letterSpacing: 1.4, color: NOAH.ink45 }}>ESTA SEMANA</span>
              {totalHoras > 0 && <span style={{ fontFamily: FONT.mono, fontSize: 12, color: NOAH.ink45 }}>{fmtHoras(totalHoras)} h</span>}
            </div>
            {conDatos ? (
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-around', gap: 8 }}>
                {DEP.map((d, i) => <SportRing key={d.key} d={d} s={semana[d.key]} anim={anim} delay={150 + i * 90} />)}
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '14px 8px', fontFamily: FONT.base, fontSize: 12.5, color: NOAH.ink45 }}>
                Sin datos de entrenamiento esta semana.
              </div>
            )}
          </section>

          {/* ── 3 · HANNA LIFE: anillo a lo ancho + info real ── */}
          <section style={{ marginTop: 12, ...rise(300) }}>
            {hannaSlot || (
              <div className="noah-tile" style={{
                position: 'relative', overflow: 'hidden', borderRadius: 20, padding: '16px 16px',
                background: `linear-gradient(135deg, ${NOAH.surface} 0%, #F4F1E9 100%)`,
                border: `1px solid ${NOAH.border}`, boxShadow: '0 2px 4px rgba(41,45,41,0.04), 0 16px 36px -24px rgba(41,45,41,0.45)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                  <HeartPulse size={13} color={NOAH.salvia} strokeWidth={2.4} />
                  <span style={{ fontFamily: FONT.base, fontSize: 11, fontWeight: 700, letterSpacing: 1, color: NOAH.salvia }}>HANNA LIFE</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                  <HannaRing valor={hv} nivel={hanna?.nivel} anim={anim} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    {sema && (
                      <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 11px', borderRadius: 999, background: `${sema.c}1c`, marginBottom: 10 }}>
                        <sema.Icon size={14} color={sema.c} strokeWidth={2.2} />
                        <span style={{ fontFamily: FONT.base, fontSize: 12, fontWeight: 700, color: sema.c }}>{sema.t}</span>
                      </div>
                    )}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 12px' }}>
                      {stats.map(x => (
                        <div key={x.k} style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontFamily: FONT.base, fontSize: 10, fontWeight: 600, letterSpacing: 0.4, color: NOAH.ink45, textTransform: 'uppercase' }}>{x.k}</span>
                          <span style={{ fontFamily: FONT.mono, fontSize: 16, fontWeight: 600, color: NOAH.ink, letterSpacing: -0.5 }}>{x.v}<span style={{ fontSize: 9.5, color: NOAH.ink45 }}>{x.u}</span></span>
                        </div>
                      ))}
                      {!stats.length && <span style={{ fontFamily: FONT.base, fontSize: 12, color: NOAH.ink45 }}>Sin biomarcadores disponibles.</span>}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </section>

          {/* ── 4 · SINCRONIZACIÓN: LED de estado + acción (dato real) ── */}
          <section style={{ display: 'flex', gap: 8, marginTop: 12, ...rise(370) }}>
            {[
              { lbl: 'Bio', esHoy: syncStatus?.bio_es_hoy, dias: syncStatus?.bio_dias_atras, l: bioLoading, f: onSyncBio },
              { lbl: 'Actividad', esHoy: syncStatus?.act_es_hoy, dias: syncStatus?.act_dias_atras, l: actLoading, f: onSyncAct },
            ].map((b, i) => {
              const c = led(b.esHoy, b.dias)
              return (
                <button key={i} onClick={b.f} disabled={b.l} className="noah-press" style={{
                  flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                  padding: '9px 10px', borderRadius: 999, cursor: b.l ? 'default' : 'pointer',
                  background: 'rgba(56,189,248,0.10)', border: '1px solid rgba(56,189,248,0.40)',
                  fontFamily: FONT.base, fontSize: 11.5, fontWeight: 700, color: AZUL,
                }}>
                  <span style={{ width: 8, height: 8, borderRadius: 999, background: c, boxShadow: `0 0 6px ${c}99`, flex: '0 0 auto' }} />
                  <span>{b.lbl}</span>
                  <span style={{ fontFamily: FONT.mono, fontSize: 10.5, color: c, fontWeight: 700 }}>{b.l ? '…' : ledTxt(b.esHoy, b.dias)}</span>
                  <RefreshCw size={12} color={AZUL} style={b.l ? { animation: 'noahspin 1s linear infinite' } : undefined} />
                </button>
              )
            })}
          </section>

          {/* ── 5 · ACCESOS: grilla con profundidad ── */}
          <section style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 14 }}>
            {accesos.map((a, i) => (
              <button key={a.id} onClick={() => onAcceso(a.id)} className="noah-tile noah-press" style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 9, padding: '16px 6px',
                borderRadius: 18, cursor: 'pointer', position: 'relative', overflow: 'hidden',
                background: `linear-gradient(160deg, ${NOAH.surface} 0%, #F1EDE4 100%)`,
                border: `1px solid ${NOAH.border}`,
                boxShadow: '0 1px 2px rgba(41,45,41,0.04), 0 10px 24px -18px rgba(41,45,41,0.5)',
                ...rise(420 + i * 55),
              }}>
                <span style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 1, background: 'rgba(255,255,255,0.6)' }} />
                <span style={{ width: 44, height: 44, borderRadius: 13, display: 'grid', placeItems: 'center',
                  background: `linear-gradient(145deg, ${NOAH.salvia}26, ${NOAH.salvia}10)`, boxShadow: `inset 0 1px 1px rgba(255,255,255,0.5)` }}>
                  <a.Icon size={21} color={NOAH.salvia} strokeWidth={2} />
                </span>
                <span style={{ fontFamily: FONT.base, fontSize: 11.5, fontWeight: 600, color: NOAH.ink, textAlign: 'center', lineHeight: 1.15 }}>{a.label}</span>
              </button>
            ))}
          </section>
        </div>
      </div>

      {/* ── 6 · ASISTENTE: acceso discreto (chat) ── */}
      <button onClick={onAsistente} aria-label="Asistente NOAH" className="noah-press" style={{
        position: 'fixed', right: 18, bottom: 80, width: 54, height: 54, borderRadius: 999, zIndex: 60,
        background: `linear-gradient(145deg, #EF6B57, ${NOAH.coral})`, border: 'none', cursor: 'pointer',
        display: 'grid', placeItems: 'center', boxShadow: '0 10px 26px -8px rgba(230,91,69,0.65)',
      }}>
        <MessageCircle size={24} color="#fff" />
      </button>

      {/* ── 7 · NAV inferior ── */}
      <nav style={{ position: 'fixed', bottom: 0, left: 0, right: 0, height: 64, background: 'rgba(251,250,246,0.92)', borderTop: `1px solid ${NOAH.border}`, backdropFilter: 'blur(10px)', zIndex: 50 }}>
        <div style={{ maxWidth: 440, margin: '0 auto', height: '100%', display: 'flex' }}>
          {nav.map(n => {
            const on = navActivo === n.id
            return <button key={n.id} onClick={() => onNav(n.id)} className="noah-press" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 3, background: 'none', border: 'none', cursor: 'pointer' }}>
              <n.Icon size={20} color={on ? NOAH.coral : NOAH.ink45} strokeWidth={on ? 2.4 : 2} />
              <span style={{ fontFamily: FONT.base, fontSize: 10.5, fontWeight: on ? 700 : 500, color: on ? NOAH.coral : NOAH.ink45 }}>{n.label}</span>
            </button>
          })}
        </div>
      </nav>
    </div>
  )
}
