// HistoriaNoah.jsx — "Tu historia NOAH": el hero narrativo del Perfil.
// Convierte los análisis dispersos del perfil en capítulos visuales: cada uno
// es UN gráfico animado (curva con estela tipo cometa, que se dispara al entrar
// en pantalla) + UNA frase. El detalle largo queda plegado en "ver más".
// Toma el `perfil` ya fetcheado por SeccionPerfil (no vuelve a pedir datos).
import React, { useRef, useEffect, useState, useMemo } from 'react'
import { Sparkles, TrendingUp, HeartPulse, Gauge, ChevronDown, Activity, Calendar } from 'lucide-react'

const GE = {
  bg: '#13160F', glass: '#1C211C',
  green: '#9DB089', cyan: '#4F8CC9', glow: '#B8C7A8',
  text: '#F3F0E8', text2: 'rgba(243,240,232,0.60)', text3: 'rgba(243,240,232,0.40)',
  danger: '#E65B45', warn: '#E0A43C', purple: '#9A7BE0', border: 'rgba(255,255,255,0.09)',
}
const F = "'Archivo', system-ui, sans-serif"
const M = "'IBM Plex Mono', monospace"

const MESES_ES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
const fmtMes = (s) => { if (!s) return ''; const [y, m] = s.split('-'); return `${MESES_ES[(+m) - 1] || ''} ${y}` }

// ── hooks / utils ─────────────────────────────────────────────────────────
function useInView(margin = '-12% 0px') {
  const ref = useRef(null)
  const [seen, setSeen] = useState(0)   // contador: cada entrada re-dispara
  useEffect(() => {
    const el = ref.current; if (!el) return
    const io = new IntersectionObserver((es) => { es.forEach(e => { if (e.isIntersecting) setSeen(s => s + 1) }) }, { rootMargin: margin, threshold: 0.35 })
    io.observe(el); return () => io.disconnect()
  }, [margin])
  return [ref, seen]
}
const EASE = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
function _smooth(arr, k = 2) {
  return arr.map((v, i) => {
    if (v == null) return null
    let s = 0, n = 0
    for (let j = i - k; j <= i + k; j++) { const x = arr[j]; if (x != null && isFinite(x)) { s += x; n++ } }
    return n ? s / n : v
  })
}
// Catmull-Rom suave, cortando en nulls
function segCurve(ctx, pts, from, to) {
  let started = false; ctx.beginPath()
  for (let i = from; i < to; i++) {
    const p1 = pts[i], p2 = pts[i + 1]
    if (!p1 || p1.y == null) { started = false; continue }
    if (!started) { ctx.moveTo(p1.x, p1.y); started = true }
    if (!p2 || p2.y == null) continue
    const p0 = (pts[i - 1] && pts[i - 1].y != null) ? pts[i - 1] : p1
    const p3 = (pts[i + 2] && pts[i + 2].y != null) ? pts[i + 2] : p2
    ctx.bezierCurveTo(p1.x + (p2.x - p0.x) / 6, p1.y + (p2.y - p0.y) / 6,
      p2.x - (p3.x - p1.x) / 6, p2.y - (p3.y - p1.y) / 6, p2.x, p2.y)
  }
  ctx.stroke()
}

// ── Curva con estela cometa (canvas) ──────────────────────────────────────
function CurvaComet({ valores, color = GE.green, height = 150, run = 0, dur = 2200, fill = true }) {
  const ref = useRef(null), raf = useRef(0)
  useEffect(() => {
    const cv = ref.current; if (!cv) return
    const ctx = cv.getContext('2d')
    const dpr = Math.min(window.devicePixelRatio || 1, 2)
    const cssW = cv.clientWidth, cssH = cv.clientHeight
    if (!cssW) return
    cv.width = cssW * dpr; cv.height = cssH * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    const P = 14, W = cssW - P * 2, H = cssH - P * 2
    const vals = _smooth(valores, 2)
    const vv = vals.filter(x => x != null && isFinite(x))
    if (vv.length < 2) return
    const mn = Math.min(...vv), mx = Math.max(...vv), rg = (mx - mn) || 1
    const Mn = vals.length
    const pts = vals.map((v, i) => ({ x: P + (i / (Mn - 1)) * W, y: v == null ? null : P + H - ((v - mn) / rg) * H }))
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const draw = (idx) => {
      ctx.clearRect(0, 0, cssW, cssH)
      // grid sutil
      ctx.strokeStyle = 'rgba(255,255,255,0.05)'; ctx.lineWidth = 1
      for (let g = 1; g < 4; g++) { const y = P + H * g / 4; ctx.beginPath(); ctx.moveTo(P, y); ctx.lineTo(P + W, y); ctx.stroke() }
      // relleno bajo la curva dibujada
      if (fill && idx > 1) {
        ctx.save(); ctx.beginPath()
        segCurve(ctx, pts, 0, idx)
        const headX = pts[Math.min(idx, Mn - 1)].x
        ctx.lineTo(headX, P + H); ctx.lineTo(pts[0].x, P + H); ctx.closePath()
        const grd = ctx.createLinearGradient(0, P, 0, P + H)
        grd.addColorStop(0, color + '40'); grd.addColorStop(1, color + '00')
        ctx.fillStyle = grd; ctx.fill(); ctx.restore()
      }
      ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.strokeStyle = color
      // estela
      ctx.globalAlpha = 0.9; ctx.lineWidth = 2.4; ctx.shadowColor = color; ctx.shadowBlur = 6
      segCurve(ctx, pts, 0, idx)
      // cometa (tramo reciente)
      ctx.globalAlpha = 1; ctx.lineWidth = 3.2; ctx.shadowBlur = 14
      segCurve(ctx, pts, Math.max(0, idx - 14), idx)
      ctx.shadowBlur = 0; ctx.globalAlpha = 1
      const head = pts[Math.min(idx, Mn - 1)]
      if (head && head.y != null) {
        ctx.fillStyle = color; ctx.shadowColor = color; ctx.shadowBlur = 16
        ctx.beginPath(); ctx.arc(head.x, head.y, 4, 0, Math.PI * 2); ctx.fill(); ctx.shadowBlur = 0
      }
    }
    if (reduce) { draw(Mn - 1); return }
    let start = null
    const tick = (t) => { if (start == null) start = t; const p = Math.min(1, (t - start) / dur); draw(Math.max(1, Math.floor(EASE(p) * (Mn - 1)))); if (p < 1) raf.current = requestAnimationFrame(tick) }
    cancelAnimationFrame(raf.current); start = null; raf.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf.current)
  }, [valores, color, dur, fill, run])
  return <canvas ref={ref} style={{ width: '100%', height, display: 'block' }} />
}

// ── Barra de zonas animada ─────────────────────────────────────────────────
function ZonaBar({ baja, media, alta, run }) {
  const [w, setW] = useState(0)
  useEffect(() => { setW(0); const t = setTimeout(() => setW(1), 60); return () => clearTimeout(t) }, [run])
  const segs = [
    { pct: baja, c: GE.cyan, l: 'Suave' },
    { pct: media, c: GE.green, l: 'Medio' },
    { pct: alta, c: GE.danger, l: 'Intenso' },
  ]
  return (
    <div>
      <div style={{ display: 'flex', height: 22, borderRadius: 8, overflow: 'hidden', background: 'rgba(255,255,255,0.04)' }}>
        {segs.map((s, i) => (
          <div key={i} style={{ width: `${w ? (s.pct || 0) : 0}%`, background: s.c, transition: `width .9s cubic-bezier(.4,0,.2,1) ${i * 120}ms` }} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 14, marginTop: 10, flexWrap: 'wrap' }}>
        {segs.map((s, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 9, height: 9, borderRadius: 3, background: s.c }} />
            <span style={{ fontFamily: F, fontSize: 11, color: GE.text2 }}>{s.l}</span>
            <span style={{ fontFamily: M, fontSize: 12, fontWeight: 700, color: GE.text }}>{s.pct != null ? Math.round(s.pct) : '—'}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Número con count-up ────────────────────────────────────────────────────
function Contador({ to, run, dur = 1200, dec = 0 }) {
  const [v, setV] = useState(0)
  useEffect(() => {
    if (to == null) return
    const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) { setV(to); return }
    let start = null, raf = 0
    const tick = (t) => { if (start == null) start = t; const p = Math.min(1, (t - start) / dur); setV(EASE(p) * to); if (p < 1) raf = requestAnimationFrame(tick) }
    raf = requestAnimationFrame(tick); return () => cancelAnimationFrame(raf)
  }, [to, run, dur])
  return <>{to == null ? '—' : v.toFixed(dec)}</>
}

// ── Capítulo (panel isla oscura) ───────────────────────────────────────────
function Cap({ eyebrow, Icon, color, children, detalle }) {
  const [ref, seen] = useInView()
  const [abierto, setAbierto] = useState(false)
  return (
    <div ref={ref} style={{
      background: 'linear-gradient(165deg, #1C211C, #13160F)', border: `1px solid ${GE.border}`,
      borderRadius: 24, padding: '18px 18px 16px', boxShadow: '0 12px 34px -16px rgba(0,0,0,0.6)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 12 }}>
        <Icon size={13} color={color} strokeWidth={2.3} />
        <span style={{ fontFamily: F, fontSize: 10.5, fontWeight: 700, letterSpacing: '0.09em', textTransform: 'uppercase', color: GE.text2 }}>{eyebrow}</span>
      </div>
      {typeof children === 'function' ? children(seen) : children}
      {detalle && (
        <>
          <button onClick={() => setAbierto(a => !a)} style={{
            display: 'flex', alignItems: 'center', gap: 5, marginTop: 14, padding: 0, background: 'none', border: 'none',
            cursor: 'pointer', fontFamily: F, fontSize: 11, fontWeight: 700, color: GE.text2,
          }}>
            {abierto ? 'Ocultar' : 'Ver más'} <ChevronDown size={13} style={{ transform: abierto ? 'rotate(180deg)' : 'none', transition: 'transform .2s' }} />
          </button>
          {abierto && <div style={{ fontFamily: F, fontSize: 12, color: GE.text3, lineHeight: 1.6, marginTop: 10, paddingTop: 12, borderTop: `1px solid ${GE.border}` }}>{detalle}</div>}
        </>
      )}
    </div>
  )
}

const Headline = ({ children }) => <div style={{ fontFamily: F, fontSize: 17, fontWeight: 800, color: GE.text, lineHeight: 1.3, letterSpacing: '-0.01em' }}>{children}</div>
const Sub = ({ children }) => <div style={{ fontFamily: F, fontSize: 12.5, color: GE.text2, lineHeight: 1.5, marginTop: 6 }}>{children}</div>

// ── Componente principal ────────────────────────────────────────────────────
export default function HistoriaNoah({ perfil }) {
  const d = perfil || {}
  const vol = d.volumen_historico || {}
  const zonas = d.distribucion_zonas || {}
  const rec = d.dias_recuperacion || {}
  const firma = d.firma_recuperacion || {}
  const fase = d.fase_actual || {}
  const patron = d.patron_semanal || {}

  const hayVol = vol.disponible && Array.isArray(vol.km_por_mes) && vol.km_por_mes.length >= 2
  const hayZonas = zonas.z_baja_pct != null
  const hayRec = rec.disponible && rec.dias_promedio_recuperacion != null

  // Hook: total de sesiones + rango de fechas + fase
  const totalSes = patron.total_sesiones || null
  const rango = hayVol ? `${fmtMes(vol.meses[0])} — ${fmtMes(vol.meses[vol.meses.length - 1])}` : null
  const faseTxt = fase.disponible ? ({ mejora: 'en mejora', meseta: 'en meseta', declive: 'en descenso' }[fase.fase] || fase.fase) : null
  const faseCol = fase.fase === 'mejora' ? GE.green : fase.fase === 'declive' ? GE.danger : GE.warn

  // Temporadas: mes pico
  const mesPico = useMemo(() => {
    if (!hayVol) return null
    let mi = 0; vol.km_por_mes.forEach((k, i) => { if ((k || 0) > (vol.km_por_mes[mi] || 0)) mi = i })
    return { mes: fmtMes(vol.meses[mi]), km: Math.round(vol.km_por_mes[mi] || 0) }
  }, [hayVol, vol])

  // Recuperación: curva modelada desde el promedio real de días
  const recCurva = useMemo(() => {
    if (!hayRec) return null
    const dias = Math.max(2, rec.dias_promedio_recuperacion)
    const N = Math.round(dias) + 4, tau = dias / 1.4
    return Array.from({ length: N }, (_, i) => 100 - 45 * Math.exp(-i / tau))
  }, [hayRec, rec])

  if (!perfil || perfil.no_calculado) {
    return (
      <div style={{ background: 'linear-gradient(165deg, #1C211C, #13160F)', border: `1px solid ${GE.border}`, borderRadius: 24, padding: 20, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={15} color={GE.glow} />
          <span style={{ fontFamily: F, fontSize: 13, color: GE.text2 }}>NOAH está armando tu historia. Con unas sesiones más se desbloquea.</span>
        </div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 16 }}>
      {/* Título de la sección */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '2px 2px 0' }}>
        <Sparkles size={16} color={GE.glow} strokeWidth={2.2} />
        <span style={{ fontFamily: F, fontSize: 15, fontWeight: 800, color: GE.text, letterSpacing: '-0.01em' }}>Tu historia NOAH</span>
      </div>

      {/* 1 · EL GANCHO */}
      <Cap eyebrow="Esto aprendimos de vos" Icon={Sparkles} color={GE.glow}>
        {(seen) => (
          <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontFamily: M, fontSize: 46, fontWeight: 700, color: GE.text, letterSpacing: '-0.03em', lineHeight: 0.95 }}>
                <Contador to={totalSes} run={seen} />
              </div>
              <div style={{ fontFamily: F, fontSize: 11, color: GE.text2, marginTop: 4 }}>sesiones analizadas</div>
            </div>
            <div style={{ flex: 1, minWidth: 160 }}>
              {rango && <Sub><Calendar size={12} color={GE.text3} style={{ verticalAlign: -1, marginRight: 4 }} />Entrenaste de <b style={{ color: GE.text }}>{rango}</b></Sub>}
              {faseTxt && (
                <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 10, padding: '4px 11px', borderRadius: 999, background: `${faseCol}1C`, border: `1px solid ${faseCol}40` }}>
                  <span style={{ width: 7, height: 7, borderRadius: 999, background: faseCol }} />
                  <span style={{ fontFamily: F, fontSize: 11.5, fontWeight: 700, color: faseCol }}>Hoy estás {faseTxt}</span>
                </div>
              )}
            </div>
          </div>
        )}
      </Cap>

      {/* 2 · TUS TEMPORADAS */}
      {hayVol && (
        <Cap eyebrow="Tus temporadas" Icon={TrendingUp} color={GE.green}
          detalle={<>Este es tu volumen mensual (km) de los últimos dos años. Te sirve para ver si venís creciendo, sostenido o en baja, y ubicar tus bloques fuertes y tus cortes.</>}>
          {(seen) => (
            <>
              <Headline>Tu volumen, mes a mes</Headline>
              {mesPico && <Sub>Tu mes más fuerte fue <b style={{ color: GE.text }}>{mesPico.mes}</b> con <b style={{ color: GE.text }}>{mesPico.km} km</b>.</Sub>}
              <div style={{ marginTop: 12 }}><CurvaComet valores={vol.km_por_mes} color={GE.green} run={seen} dur={2400} /></div>
            </>
          )}
        </Cap>
      )}

      {/* 3 · CÓMO TE RECUPERÁS */}
      {hayRec && (
        <Cap eyebrow="Cómo te recuperás" Icon={HeartPulse} color={GE.cyan}
          detalle={firma.disponible
            ? <>Tu HRV nocturno pasa de <b style={{ color: GE.text }}>{firma.hrv_tras_carga_suave}</b> tras una carga suave a <b style={{ color: GE.text }}>{firma.hrv_tras_carga_fuerte}</b> tras una fuerte: esa es tu firma de recuperación. La curva de arriba está modelada a partir de tu promedio real de {rec.dias_promedio_recuperacion} días.</>
            : <>Promedio calculado sobre {rec.muestras} recuperaciones reales tras tus sesiones más duras.</>}>
          {(seen) => (
            <>
              <Headline>Te recuperás en ~{rec.dias_promedio_recuperacion} días</Headline>
              <Sub>Es lo que te toma volver a estar fresco después de una sesión fuerte.</Sub>
              <div style={{ marginTop: 12 }}><CurvaComet valores={recCurva} color={GE.cyan} run={seen} dur={2200} height={130} /></div>
            </>
          )}
        </Cap>
      )}

      {/* 4 · TUS ZONAS */}
      {hayZonas && (
        <Cap eyebrow="Tus zonas" Icon={Gauge} color={GE.warn}
          detalle={<>El reparto es por carga (TSS) en zonas bajas, medias y altas. Te muestra tu hábito: si acumulás volumen suave, si vivís en el umbral, o si cargás mucha intensidad para tu volumen.</>}>
          {(seen) => (
            <>
              <Headline>{zonas.patron ? zonas.patron.charAt(0).toUpperCase() + zonas.patron.slice(1) : 'Tu reparto de zonas'}</Headline>
              <div style={{ marginTop: 14 }}><ZonaBar baja={zonas.z_baja_pct} media={zonas.z_media_pct} alta={zonas.z_alta_pct} run={seen} /></div>
            </>
          )}
        </Cap>
      )}
    </div>
  )
}
