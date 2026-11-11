// SeccionTecnica.jsx — Técnica / Biomecánica NOAH
// Rediseño premium (vidrio, violeta+cian) + análisis COMPLETO por deporte:
//  · Running : economía, apoyo, mapa, cambios, evolución (muestra-a-muestra).
//  · Ciclismo: entrega de potencia, simetría y pedaleo (L/R + torque), mapa,
//              cambios, evolución. (La "postura" no la mide el sensor; lo medible
//              es balance L/R, torque effectiveness y pedal smoothness.)
//  · Natación: datos por LARGO (no muestra-a-muestra): tarjetas por estilo,
//              evolución y consistencia. No se inventan curvas de segundo a segundo.
// Datos: /tecnica (tarjetas, índice, evolución, comparación) + /tecnica_lab (series).
// Base de conocimiento: tecnica_fuentes.json.
import { useState, useEffect, useMemo } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, ZAxis, ReferenceLine, ReferenceArea, BarChart, Bar, Cell,
} from 'recharts'
import fuentes from './tecnica_fuentes.json'

const esLocal = window.location.hostname === 'localhost' || window.location.hostname.startsWith('192.168.')
const API = esLocal ? `http://${window.location.hostname}:5000/api` : '/api'
function authFetch(url, o = {}) {
  let t = null
  try { t = JSON.parse(localStorage.getItem('noah_sesion'))?.token } catch {}
  return fetch(url, { ...o, headers: { ...(o.headers || {}), ...(t ? { Authorization: `Bearer ${t}` } : {}) } })
}

// ── Paleta oficial NOAH: verde salvia + azul eléctrico + blanco frío ──
// (violet/cian se conservan como nombres internos pero mapean a azul/verde salvia,
//  para no tocar cada uso; la identidad visible es solo estos 3 colores + gris.)
const C = {
  bg: '#090D18', ink: '#EFF3ED', dim: '#AAB5C6', aux: '#AAB5C6',
  border: 'rgba(255,255,255,0.08)',
  // identidad + paleta semántica de datos (cada color = un significado)
  sage: '#B9C995',   // PROTAGONISTA · favorable · eficiente · fresco
  blue: '#2454F4',   // secundario · variable del atleta · objetivo
  amber: '#E6B655',  // atención · fuerza/torque · fatiga
  slate: '#6E7689',  // neutral · recuperación · zona muerta
  ivory: '#EFF3ED',  // cards y textos
  green: '#35C07A',  // semáforo OK (dentro de gráficos)
  red: '#E2726E',    // semáforo alerta (dentro de gráficos)
  white: '#EFF3ED',
  violet: '#B9C995', cian: '#2454F4',           // protagonista=salvia · secundario=azul
  v: '#B9C995', vMut: '#9FB488', c: '#2454F4', cLit: '#5B79E8', blend: '#8FA0C0',
}
const glass = {
  background: 'linear-gradient(160deg, rgba(57,123,255,0.06), rgba(168,191,168,0.035) 58%, rgba(18,24,42,0) 100%), rgba(20,27,45,0.50)',
  backdropFilter: 'blur(20px) saturate(145%)', WebkitBackdropFilter: 'blur(20px) saturate(145%)',
  border: `1px solid ${C.border}`, borderRadius: 20,
  boxShadow: '0 20px 50px -22px rgba(0,0,0,0.65), inset 0 1px 0 rgba(255,255,255,0.05)',
}
const num = { fontVariantNumeric: 'tabular-nums' }
const tip = { background: 'rgba(16,22,38,0.94)', backdropFilter: 'blur(14px)', border: `1px solid ${C.border}`, borderRadius: 12, fontSize: 14, color: C.ink, boxShadow: '0 12px 30px -10px rgba(0,0,0,0.6)' }

const r1 = (x) => Math.round(x * 10) / 10
const median = (a) => { const s = [...a].filter(x => x != null && isFinite(x)).sort((x, y) => x - y); const n = s.length; return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0 }
const hexLerp = (a, b, t) => { const pa = [parseInt(a.slice(1, 3), 16), parseInt(a.slice(3, 5), 16), parseInt(a.slice(5, 7), 16)], pb = [parseInt(b.slice(1, 3), 16), parseInt(b.slice(3, 5), 16), parseInt(b.slice(5, 7), 16)]; const c = pa.map((v, i) => Math.round(v + (pb[i] - v) * t)); return `rgb(${c[0]},${c[1]},${c[2]})` }
const fmtPace = (p) => { if (p == null || !isFinite(p) || p <= 0) return '—'; const m = Math.floor(p); return `${m}:${String(Math.round((p - m) * 60)).padStart(2, '0')}` }
const paceDe = (ms) => (ms && ms > 0.3 ? (1000 / ms) / 60 : null)
function stat(rows, key) {
  const v = rows.map(r => r[key]).filter(x => x != null && isFinite(x))
  if (!v.length) return { n: 0 }
  const n = v.length, t = Math.max(1, Math.floor(n / 3))
  const mean = a => a.reduce((s, x) => s + x, 0) / a.length
  return { n, avg: r1(mean(v)), p1: r1(mean(v.slice(0, t))), p3: r1(mean(v.slice(-t))), min: r1(Math.min(...v)), max: r1(Math.max(...v)) }
}
function corr(rows, kx, ky) {
  const pts = rows.filter(r => r[kx] != null && r[ky] != null && isFinite(r[kx]) && isFinite(r[ky]))
  if (pts.length < 8) return null
  const n = pts.length, mx = pts.reduce((s, p) => s + p[kx], 0) / n, my = pts.reduce((s, p) => s + p[ky], 0) / n
  let sxy = 0, sxx = 0, syy = 0
  for (const p of pts) { const dx = p[kx] - mx, dy = p[ky] - my; sxy += dx * dy; sxx += dx * dx; syy += dy * dy }
  if (sxx === 0 || syy === 0) return null
  return Math.round((sxy / Math.sqrt(sxx * syy)) * 100) / 100
}
function thirds(rows, keys) {
  const n = rows.length, t1 = Math.floor(n / 3), t2 = Math.floor(2 * n / 3)
  const seg = (a) => { const o = {}; for (const k of keys) { const v = a.map(r => r[k]).filter(x => x != null && isFinite(x)); o[k] = v.length ? r1(v.reduce((s, x) => s + x, 0) / v.length) : null } return o }
  return { inicio: seg(rows.slice(0, t1)), mitad: seg(rows.slice(t1, t2)), final: seg(rows.slice(t2)) }
}
function etiquetaEstado(e) {
  const map = { elite: 'Nivel elite', bueno: 'Bien', avanzado: 'Avanzado', intermedio: 'Intermedio', promedio: 'Promedio', principiante: 'A mejorar', mejorar: 'A mejorar', optima: 'Óptima', 'óptima': 'Óptima', equilibrado: 'Equilibrado', leve: 'Leve', significativo: 'Marcado' }
  const k = (e || '').toLowerCase()
  return map[k] || (e ? e[0].toUpperCase() + e.slice(1) : '—')
}
function estadoInfo(e) {
  const k = (e || '').toLowerCase()
  if (['elite', 'bueno', 'óptima', 'optima', 'equilibrado', 'estable'].includes(k)) return { t: etiquetaEstado(e), c: C.sage }
  if (['mejorar', 'principiante', 'alerta', 'significativo'].includes(k)) return { t: etiquetaEstado(e), c: C.amber }
  return { t: etiquetaEstado(e), c: C.dim }
}

function construirFilas(series) {
  const ts = series.ts || []
  const out = []
  for (let i = 0; i < ts.length; i++) {
    const sp = series.speed_ms ? series.speed_ms[i] : null
    out.push({
      t: ts[i], hr: series.hr ? series.hr[i] : null, cadence: series.cadence ? series.cadence[i] : null,
      power: series.power ? series.power[i] : null, speed_ms: sp, pace: paceDe(sp),
      vo: series.vo && series.vo[i] != null ? r1(series.vo[i] / 10) : null,
      gct: series.gct ? series.gct[i] : null,
      stride: series.stride && series.stride[i] != null ? (series.stride[i] > 10 ? r1(series.stride[i] / 100) : r1(series.stride[i])) : null,
      vratio: series.vratio ? series.vratio[i] : null,
      lr: series.lr ? series.lr[i] : null,            // ya decodificado en el endpoint (% izq)
      torque: series.torque ? series.torque[i] : null,
      pedal: series.pedal ? series.pedal[i] : null,
      kmh: sp != null ? r1(sp * 3.6) : null,
    })
  }
  return out
}

// ── Base de conocimiento (JSON) ──
const SECCION_JSON = { running: 'running', cycling: 'ciclismo', swimming: 'natacion' }
const KEY_JSON = {
  running: { cadencia: 'cadencia', gct: 'gct', vertical_osc: 'oscilacion_vertical', economia: 'vertical_ratio', stride_length: 'zancada' },
  cycling: { cadencia: 'cadencia', lr_balance: 'balance_lr', torque_effectiveness: 'torque_effectiveness' },
  swimming: {},
}
function fuenteDe(sport, k) { try { return fuentes[SECCION_JSON[sport]][KEY_JSON[sport][k]] || null } catch { return null } }
function umbralTexto(u) {
  if (!u) return null
  const uni = u.unidad && typeof u.unidad === 'string' ? u.unidad : ''
  const orden = ['elite', 'bueno', 'avanzado', 'intermedio', 'promedio', 'principiante', 'mejorar']
  const parts = orden.filter(x => u[x] != null).map(x => `${x} ${u[x]}${typeof u[x] === 'number' ? uni : ''}`)
  return parts.length ? parts.join(' · ') : null
}

// ── Primitivos ──
function Glass({ children, style }) { return <div style={{ ...glass, padding: 18, ...style }}>{children}</div> }
function TituloSeccion({ children }) {
  return <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '6px 2px 2px' }}>
    <span style={{ width: 3, height: 15, borderRadius: 3, background: `linear-gradient(${C.violet}, ${C.cian})` }} />
    <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.8, color: C.dim, textTransform: 'uppercase' }}>{children}</span>
  </div>
}
function Expander({ label, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen)
  return <div>
    <button onClick={() => setOpen(o => !o)} className="noah-exp" style={{ width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'transparent', border: 'none', cursor: 'pointer', padding: '2px 0', color: open ? C.ink : C.dim }}>
      <span style={{ fontSize: 12, fontWeight: 700, letterSpacing: 0.4 }}>{label}</span>
      <span style={{ fontSize: 13, transform: open ? 'rotate(180deg)' : 'none', color: C.violet }}>⌄</span>
    </button>
    {open && <div style={{ marginTop: 10 }}>{children}</div>}
  </div>
}
function SensorFalta({ sensor }) {
  return <Glass style={{ border: `1px dashed ${C.border}`, background: 'rgba(22,29,46,0.30)' }}>
    <div style={{ fontSize: 13.5, color: C.dim, lineHeight: 1.55, textAlign: 'center' }}>Para este análisis necesitás <span style={{ color: C.ink }}>{sensor}</span>.<br />No lo mostramos con datos estimados.</div>
  </Glass>
}
function Interp({ x }) {
  if (!x) return null
  const Row = ({ k, v, c }) => v ? <div style={{ marginBottom: 11 }}>
    <div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: 0.6, color: c, marginBottom: 3, textTransform: 'uppercase' }}>{k}</div>
    <div style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.55, opacity: 0.94 }}>{v}</div>
  </div> : null
  return <div>
    <Row k="Qué observamos" v={x.observamos} c={C.violet} />
    <Row k="Los números" v={x.numeros} c={C.cian} />
    <Row k="Cuándo sucede" v={x.cuando} c={C.cian} />
    <Row k="Cómo se relacionan" v={x.relacion} c={C.violet} />
    <Row k="Qué significa · interpretación" v={x.significa} c={C.violet} />
    <Row k="Hipótesis a confirmar" v={x.hipotesis} c={C.dim} />
    <Row k="Impacto en el rendimiento" v={x.impacto} c={C.cian} />
    <Row k="Qué trabajar" v={x.trabajar} c={C.violet} />
  </div>
}
function Analisis({ eyebrow, titulo, subtitulo, children, interp }) {
  return <Glass style={{ position: 'relative', overflow: 'hidden' }}>
    <div style={{ position: 'absolute', top: -40, right: -40, width: 160, height: 160, borderRadius: '50%', background: `radial-gradient(circle, ${C.violet}18, transparent 70%)`, pointerEvents: 'none' }} />
    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.7, color: C.cian, textTransform: 'uppercase', marginBottom: 4 }}>{eyebrow}</div>
    <div style={{ fontSize: 18, fontWeight: 700, color: C.ink, lineHeight: 1.25 }}>{titulo}</div>
    {subtitulo && <div style={{ fontSize: 12.5, color: C.dim, margin: '4px 0 14px', lineHeight: 1.5 }}>{subtitulo}</div>}
    {children}
    {interp && interp.significa && <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start', marginTop: 14, background: `${C.sage}14`, border: `1px solid ${C.sage}3A`, borderRadius: 12, padding: '10px 13px' }}>
      <span style={{ color: C.sage, fontSize: 15, fontWeight: 800, lineHeight: 1.4 }}>✓</span>
      <span style={{ fontSize: 14, color: C.ink, lineHeight: 1.5 }}>{interp.significa}</span>
    </div>}
    {interp && <div style={{ marginTop: 10 }}>
      <Expander label="Ver análisis biomecánico completo"><Interp x={interp} /></Expander>
    </div>}
  </Glass>
}

// ── Serie temporal ──
function Serie({ filas, p, ultimo }) {
  return <div style={{ marginBottom: 8 }}>
    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, color: C.ink, marginBottom: 2, fontWeight: 600 }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: 7 }}><span style={{ width: 9, height: 9, borderRadius: 9, background: p.color }} />{p.label}</span>
      <span style={{ color: C.aux, fontSize: 11.5 }}>{p.unit}</span>
    </div>
    <ResponsiveContainer width="100%" height={108}>
      <LineChart data={filas} syncId="bio" margin={{ top: 4, right: 10, left: -6, bottom: ultimo ? 2 : 0 }}>
        <CartesianGrid stroke="rgba(255,255,255,0.035)" vertical={false} />
        <XAxis dataKey="t" tick={ultimo ? { fill: C.aux, fontSize: 11 } : false} tickFormatter={s => `${Math.floor(s / 60)}′`} height={ultimo ? 18 : 1} stroke="rgba(255,255,255,0.08)" />
        <YAxis domain={p.center50 ? [40, 60] : ['auto', 'auto']} reversed={!!p.pace} tick={{ fill: C.aux, fontSize: 11 }} width={40} tickFormatter={p.pace ? fmtPace : undefined} stroke="rgba(255,255,255,0.08)" />
        {p.center50 && <ReferenceLine y={50} stroke={C.aux} strokeDasharray="4 4" label={{ value: '50/50', fill: C.aux, fontSize: 10, position: 'right' }} />}
        <Tooltip contentStyle={tip} labelFormatter={s => `min ${Math.floor(s / 60)}`} formatter={v => [p.pace ? fmtPace(v) : v, p.label]} />
        <Line type="monotone" dataKey={p.key} name={p.label} stroke={p.color} strokeWidth={2.6} dot={false} connectNulls isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>
}
function MultiSerie({ filas, panels }) { return <div>{panels.map((p, i) => <Serie key={p.key} filas={filas} p={p} ultimo={i === panels.length - 1} />)}</div> }

// ── Cambios por tercio ──
function Cambios({ T, metricas }) {
  const cols = [C.sage, C.blend, C.amber]  // fresco → transición → fatiga
  return <div className="noah-grid">
    {metricas.map(m => {
      const data = [{ x: 'Inicio', v: T.inicio[m.key] }, { x: 'Mitad', v: T.mitad[m.key] }, { x: 'Final', v: T.final[m.key] }].filter(d => d.v != null)
      if (data.length < 2) return null
      return <div key={m.key}>
        <div style={{ fontSize: 12.5, color: C.ink, fontWeight: 600, marginBottom: 4 }}>{m.label} <span style={{ color: C.aux, fontSize: 11 }}>({m.unit})</span></div>
        <ResponsiveContainer width="100%" height={148}>
          <BarChart data={data} margin={{ top: 6, right: 6, left: -14, bottom: 0 }}>
            <CartesianGrid stroke="rgba(255,255,255,0.04)" vertical={false} />
            <XAxis dataKey="x" tick={{ fill: C.aux, fontSize: 11 }} stroke="rgba(255,255,255,0.08)" />
            <YAxis domain={['auto', 'auto']} tick={{ fill: C.aux, fontSize: 11 }} width={38} stroke="rgba(255,255,255,0.08)" />
            <Tooltip cursor={{ fill: 'rgba(255,255,255,0.04)' }} contentStyle={tip} />
            <Bar dataKey="v" name={m.label} radius={[5, 5, 0, 0]}>{data.map((d, i) => <Cell key={i} fill={cols[i]} />)}</Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    })}
  </div>
}

// ── Evolución semanal (claves por deporte) ──
const EVOL_METRICAS = {
  running: [{ key: 'cadencia', nombre: 'Cadencia', unidad: 'spm', mejorAlto: true }, { key: 'gct', nombre: 'Tiempo de contacto', unidad: 'ms', mejorAlto: false }, { key: 'vo', nombre: 'Oscilación', unidad: 'cm', mejorAlto: false }],
  cycling: [{ key: 'cadencia', nombre: 'Cadencia', unidad: 'rpm', mejorAlto: null }, { key: 'torque_effectiveness', nombre: 'Torque efectivo', unidad: '%', mejorAlto: true }],
  swimming: [{ key: 'swolf', nombre: 'SWOLF', unidad: '', mejorAlto: false }, { key: 'cadencia', nombre: 'Brazadas/largo', unidad: '', mejorAlto: false }],
}
// agrupa el sparkline (semanal) en puntos MENSUALES usando toda la historia
function aggMensual(spark, keys) {
  const buckets = {}
  for (const d of spark || []) { const m = String(d.semana || '').slice(0, 7); if (m.length < 7) continue; (buckets[m] = buckets[m] || []).push(d) }
  return Object.keys(buckets).sort().map(m => {
    const arr = buckets[m], o = { mes: m }
    for (const k of keys) { const v = arr.map(x => x[k]).filter(x => x != null && isFinite(x)); if (v.length) o[k] = r1(v.reduce((a, b) => a + b, 0) / v.length) }
    return o
  })
}
const mesLbl = (m) => { const M = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']; const p = String(m).split('-'); return p.length >= 2 ? `${M[(+p[1] || 1) - 1]} ${String(p[0]).slice(2)}` : m }
function Semanal({ spark, sport, sel, setSel }) {
  const metricas = (EVOL_METRICAS[sport] || []).filter(x => (spark || []).some(d => d[x.key] != null))
  if (!spark || !metricas.length) return { node: null, interp: null }
  const mensual = aggMensual(spark, metricas.map(m => m.key))
  const cfg = metricas[Math.min(sel, metricas.length - 1)]
  const serie = mensual.filter(d => d[cfg.key] != null).map(d => ({ semana: d.mes, v: d[cfg.key] }))
  if (serie.length < 2) return { node: null, interp: null, pocos: true }
  const prim = serie[0].v, ult = serie[serie.length - 1].v, dif = r1(ult - prim)
  const mejoro = cfg.mejorAlto == null ? null : cfg.mejorAlto ? dif > 0 : dif < 0
  const node = <div>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
      {metricas.map((x, i) => { const on = i === Math.min(sel, metricas.length - 1); return <button key={x.key} onClick={() => setSel(i)} style={{ padding: '8px 14px', borderRadius: 999, cursor: 'pointer', fontSize: 12.5, fontWeight: 700, border: `1px solid ${on ? C.cian : C.border}`, background: on ? `${C.cian}1F` : 'transparent', color: on ? C.cian : C.dim }}>{x.nombre}</button> })}
    </div>
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={serie} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
        <defs><linearGradient id="gEvo" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stopColor={C.violet} /><stop offset="100%" stopColor={C.cian} /></linearGradient></defs>
        <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
        <XAxis dataKey="semana" tick={{ fill: C.aux, fontSize: 12 }} tickMargin={8} stroke="rgba(255,255,255,0.08)" tickFormatter={mesLbl} />
        <YAxis domain={['auto', 'auto']} tick={{ fill: C.aux, fontSize: 12 }} width={38} stroke="rgba(255,255,255,0.08)" />
        <Tooltip contentStyle={tip} formatter={v => [`${v} ${cfg.unidad}`.trim(), cfg.nombre]} />
        <Line type="monotone" dataKey="v" name={cfg.nombre} stroke="url(#gEvo)" strokeWidth={3.2} dot={{ r: 4, fill: C.cian }} activeDot={{ r: 6 }} />
      </LineChart>
    </ResponsiveContainer>
  </div>
  const interp = {
    observamos: `Seguimiento de tu ${cfg.nombre.toLowerCase()} mes a mes (${serie.length} meses con datos).`,
    numeros: Math.abs(dif) < 0.1 ? `Se mantuvo en torno a ${ult} ${cfg.unidad}`.trim() + '.' : `Pasó de ${prim} a ${ult} ${cfg.unidad} (${dif > 0 ? '+' : ''}${dif})`.replace('  ', ' ') + '.',
    significa: mejoro == null ? 'Es una métrica de contexto: se lee junto a tu nivel y tus objetivos.' : Math.abs(dif) < 0.1 ? 'Tu técnica está estable entre sesiones.' : mejoro ? 'La tendencia va en la dirección correcta.' : 'La tendencia conviene vigilarla y reforzar el trabajo técnico.',
  }
  return { node, interp }
}

// ── Comparativa vs período anterior (unifica ambos formatos del backend) ──
function comparativaUnificada(d) {
  const lista = d.analisis_fatiga && d.analisis_fatiga.comparativa
  if (Array.isArray(lista) && lista.length) return lista.map(r => ({ metrica: r.metrica, de: r.mejor_periodo, a: r.actual, diff: r.diff_pct, mejor: r.mejora }))
  const obj = d.comparacion
  if (obj && typeof obj === 'object' && Object.keys(obj).length) {
    const labels = { cadencia: 'Cadencia', torque_effectiveness: 'Torque efectivo', swolf: 'SWOLF', paladas: 'Brazadas/largo', pace: 'Ritmo' }
    const bajarMejor = { swolf: true, paladas: true, pace: true }
    return Object.entries(obj).map(([k, v]) => ({
      metrica: labels[k] || k, de: v.anterior, a: v.actual, diff: v.diff,
      mejor: v.direccion ? (bajarMejor[k] ? v.direccion === 'down' : v.direccion === 'up') : null,
    }))
  }
  return []
}
function ComparativaBox({ d }) {
  const rows = comparativaUnificada(d)
  if (!rows.length) return null
  return <Glass style={{ marginTop: 12 }}>
    <div style={{ fontSize: 12, color: C.dim, fontWeight: 700, letterSpacing: 0.4, textTransform: 'uppercase', marginBottom: 8 }}>Comparado con tu período anterior</div>
    {rows.map((r, i) => { const c = r.mejor === true ? C.cian : r.mejor === false ? C.violet : C.dim; return <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '9px 0', borderTop: i ? `1px solid ${C.border}` : 'none' }}><span style={{ fontSize: 13.5, color: C.ink }}>{r.metrica}</span><span style={{ fontSize: 13, color: C.dim, ...num }}>{r.de} → <strong style={{ color: C.ink }}>{r.a}</strong>{r.diff != null && <span style={{ color: c, fontWeight: 700 }}> ({r.diff > 0 ? '+' : ''}{r.diff}{String(r.metrica).includes('%') ? '' : r.mejor != null ? '%' : ''})</span>}</span></div> })}
  </Glass>
}

// ── Tarjetas de métricas (running + cycling) ──
const META = {
  cadencia: { label: 'Cadencia', unit: 'spm', val: m => m.promedio, que: 'Pasos/pedaladas por minuto.', hacer: 'Ajustá la frecuencia con metrónomo.' },
  gct: { label: 'Tiempo de contacto', unit: 'ms', val: m => m.promedio_ms, que: 'Cuánto tiempo pasás apoyado en el suelo en cada paso.', hacer: 'Tobillo y gemelo reactivos: skipping y saltos cortos 2×/sem.' },
  vertical_osc: { label: 'Oscilación vertical', unit: 'cm', val: m => m.promedio_cm, que: 'Cuánto subís y bajás en cada paso.', hacer: 'Correr "hacia adelante", core y cadencia alta.' },
  stride_length: { label: 'Longitud de zancada', unit: 'm', val: m => m.promedio_m, que: 'El largo de cada paso; se lee junto a la cadencia.', hacer: 'Si se acorta al final, es fatiga: fuerza específica.' },
  economia: { label: 'Economía (vertical ratio)', unit: '%', val: m => m.vertical_ratio, que: 'Relación entre tu rebote y tu avance.', hacer: 'Mejora al bajar la oscilación y subir la cadencia.' },
  lr_balance: { label: 'Balance izq/der', unit: '%', val: m => m.promedio_pct, que: 'Reparto de potencia entre las dos piernas (ideal ~50/50).', hacer: 'Asimetría sostenida: fit de bici y fuerza de una pierna.' },
  torque_effectiveness: { label: 'Torque efectivo', unit: '%', val: m => m.promedio_pct, que: 'Qué parte de cada pedalada produce fuerza útil.', hacer: 'Drills de pedaleo redondo (una pierna, cadencia alta).' },
}
const METRICAS_SPORT = { running: ['cadencia', 'gct', 'vertical_osc', 'economia', 'stride_length'], cycling: ['cadencia', 'lr_balance', 'torque_effectiveness'], swimming: [] }
function TarjetaMetrica({ k, m, sport }) {
  const meta = META[k]; if (!meta) return null
  const v = meta.val(m); if (v == null) return null
  const f = fuenteDe(sport, k)
  const queMide = (f && f.que_mide) || meta.que
  const porQue = f && f.por_que_importa
  const umbral = umbralTexto(f && f.umbrales_noah)
  const est = estadoInfo(m.estado), drift = m.drift_pct, estable = drift == null || Math.abs(drift) < 4
  const extra = k === 'lr_balance' && m.pierna_dominante ? `Dominante: ${m.pierna_dominante} · desbalance ${m.desbalance}%` : null
  return <div style={{ ...glass, padding: 16 }}>
    <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 0.4, color: C.dim, textTransform: 'uppercase' }}>{meta.label}</div>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, margin: '6px 0 4px' }}>
      <span style={{ fontSize: 33, fontWeight: 800, color: C.ink, ...num, lineHeight: 1 }}>{v}</span>
      <span style={{ fontSize: 13, color: C.aux }}>{meta.unit}</span>
    </div>
    {m.estado && <div style={{ fontSize: 12, fontWeight: 700, color: est.c, letterSpacing: 0.2 }}>{est.t}</div>}
    {extra && <div style={{ fontSize: 11.5, color: C.dim, marginTop: 4 }}>{extra}</div>}
    <div style={{ fontSize: 12.5, color: C.dim, lineHeight: 1.5, marginTop: 8 }}>{queMide}</div>
    {drift != null && <div style={{ fontSize: 12, marginTop: 8, color: estable ? C.cian : C.violet }}>{estable ? 'Estable toda la sesión' : `Cambia ${drift > 0 ? '+' : ''}${drift}% hacia el final`}</div>}
    {(porQue || umbral || (m.estado || '').toLowerCase() === 'mejorar') && (
      <div style={{ marginTop: 10, paddingTop: 10, borderTop: `1px solid ${C.border}` }}>
        <Expander label="Detalle">
          {porQue && <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.5, marginBottom: 8, opacity: 0.9 }}><span style={{ color: C.cian, fontWeight: 700 }}>Por qué importa. </span>{porQue}</div>}
          {umbral && <div style={{ fontSize: 11.5, color: C.aux, ...num, marginBottom: 8 }}><span style={{ color: C.dim, fontWeight: 700 }}>Referencia NOAH: </span>{umbral}</div>}
          {(m.estado || '').toLowerCase() === 'mejorar' && <div style={{ fontSize: 12.5, color: C.ink, lineHeight: 1.5 }}><span style={{ color: C.violet, fontWeight: 700 }}>Qué hacer. </span>{meta.hacer}</div>}
        </Expander>
      </div>
    )}
  </div>
}

// ── Natación: tarjeta por estilo ──
function TarjetaEstilo({ nombre, e }) {
  const item = (lbl, v, u) => v == null ? null : <div><div style={{ fontSize: 10.5, color: C.aux, textTransform: 'uppercase', letterSpacing: 0.4 }}>{lbl}</div><div style={{ fontSize: 18, fontWeight: 800, color: C.ink, ...num }}>{v}<span style={{ fontSize: 11, color: C.aux, marginLeft: 2 }}>{u}</span></div></div>
  return <div style={{ ...glass, padding: 16 }}>
    <div style={{ fontSize: 13.5, fontWeight: 700, color: C.violet, marginBottom: 10 }}>{nombre} <span style={{ color: C.aux, fontSize: 11, fontWeight: 500 }}>· {e.n_largos} largos</span></div>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      {item('SWOLF', e.swolf, '')}
      {item('Dist/brazada', e.dps, 'm')}
      {item('Brazadas/25m', e.brazadas_25m, '')}
      {item('Ritmo/100m', e.pace_100m != null ? fmtPace(e.pace_100m) : null, '')}
    </div>
  </div>
}

// ── generadores de interpretación (texto real) ──
function genEconomia(filas) {
  const sV = stat(filas, 'vo'), sS = stat(filas, 'speed_ms'), sH = stat(filas, 'hr')
  if (!sV.n || !sS.n) return null
  const T = thirds(filas, ['vo', 'speed_ms', 'hr'])
  const cVS = corr(filas, 'vo', 'speed_ms')
  const paceAvg = paceDe(sS.avg)
  const sube = cVS != null && cVS > 0.25 && sV.avg >= 9
  return {
    observamos: `Tu oscilación vertical promedió ${sV.avg} cm, con un ritmo medio de ${fmtPace(paceAvg)}/km${sH.n ? ` y FC media de ${sH.avg} bpm` : ''}.`,
    numeros: `La relación entre velocidad y oscilación fue ${cVS == null ? 'poco concluyente' : cVS > 0.25 ? `positiva (r≈${cVS}): a más velocidad, más rebote` : cVS < -0.25 ? `negativa (r≈${cVS}): el rebote no crece al acelerar` : `baja (r≈${cVS}): el rebote es bastante independiente del ritmo`}.`,
    cuando: `Del primer al último tercio: oscilación ${T.inicio.vo}→${T.final.vo} cm` + (T.inicio.speed_ms && T.final.speed_ms ? `, ritmo ${fmtPace(paceDe(T.inicio.speed_ms))}→${fmtPace(paceDe(T.final.speed_ms))}/km` : '') + (sH.n ? `, FC ${T.inicio.hr}→${T.final.hr} bpm` : '') + '.',
    relacion: 'Que la FC suba con la intensidad es esperable; no alcanza para hablar de pérdida de economía. Miramos si la oscilación se dispara más de lo que justifica el cambio de ritmo.',
    significa: sube ? 'Al acelerar tendés a rebotar más: tu mecánica pierde algo de eficiencia a ritmos altos.' : 'Mantenés una oscilación contenida aunque cambie el ritmo: buena eficiencia mecánica.',
    impacto: sube ? 'Más rebote a ritmo de carrera significa más costo energético por kilómetro.' : 'Una mecánica estable te deja sostener el ritmo con menor costo.',
    trabajar: sube ? 'Cadencia alta, core y drills de técnica "hacia adelante".' : null,
  }
}
function genApoyo(filas) {
  const sG = stat(filas, 'gct'), sC = stat(filas, 'cadence'), sStr = stat(filas, 'stride')
  if (!sG.n || !sC.n) return null
  const T = thirds(filas, ['gct', 'cadence', 'stride'])
  const cGC = corr(filas, 'gct', 'cadence'), cSC = corr(filas, 'stride', 'cadence')
  const fatiga = T.final.gct != null && T.inicio.gct != null && T.final.gct > T.inicio.gct + 8 && T.final.cadence < T.inicio.cadence - 2
  const overstride = sStr.n && sStr.avg >= 1.3 && sC.avg <= 170
  return {
    observamos: `Contacto con el suelo ${sG.avg} ms y cadencia ${sC.avg} spm${sStr.n ? `, con zancada media de ${sStr.avg} m` : ''}.`,
    numeros: `GCT del inicio al final ${T.inicio.gct}→${T.final.gct} ms; cadencia ${T.inicio.cadence}→${T.final.cadence} spm${sStr.n && T.inicio.stride != null ? `; zancada ${T.inicio.stride}→${T.final.stride} m` : ''}.`,
    cuando: fatiga ? 'El cambio se concentra en el último tercio.' : 'Las variaciones entre tramos son chicas.',
    relacion: `GCT y cadencia suelen moverse en sentido opuesto${cGC != null ? ` (r≈${cGC})` : ''}. ${cSC != null && cSC < -0.2 ? 'Tu zancada se alarga cuando baja la cadencia' : 'Zancada y cadencia se mantienen acopladas'}.`,
    significa: fatiga ? 'Hacia el final el apoyo se hace más largo y la cadencia cae: patrón consistente con fatiga del tren inferior.' : 'Organizás el apoyo de forma estable durante toda la sesión.',
    hipotesis: overstride ? 'Zancada larga para tu cadencia: posible sobrepaso. A confirmar con el patrón de apoyo.' : null,
    impacto: fatiga ? 'Un apoyo más largo aumenta el frenado y el costo al final de la carrera.' : 'Un apoyo estable protege de lesión y sostiene el ritmo.',
    trabajar: fatiga || overstride ? 'Fuerza específica y recordatorios de cadencia en el tramo final.' : null,
  }
}
function genPotencia(filas) {
  const sP = stat(filas, 'power'), sC = stat(filas, 'cadence'), sH = stat(filas, 'hr')
  if (!sP.n) return null
  const T = thirds(filas, ['power', 'cadence', 'hr'])
  const cPC = sC.n ? corr(filas, 'power', 'cadence') : null
  const cPH = sH.n ? corr(filas, 'power', 'hr') : null
  const driftP = T.inicio.power ? r1((T.final.power - T.inicio.power) / T.inicio.power * 100) : 0
  const cae = driftP <= -8
  // desacople Pw:HR (eficiencia aeróbica): sube la FC manteniendo potencia = fatiga
  const driftHR = sH.n && T.inicio.hr ? r1((T.final.hr - T.inicio.hr) / T.inicio.hr * 100) : null
  const desacople = driftHR != null && driftP > -5 && driftHR >= 5
  return {
    observamos: `Potencia media ${sP.avg} W${sC.n ? `, cadencia ${sC.avg} rpm` : ' (sin sensor de cadencia)'}${sH.n ? `, FC media ${sH.avg} bpm` : ''}.`,
    numeros: `Potencia entre ${sP.min} y ${sP.max} W. Del inicio al final: potencia ${T.inicio.power}→${T.final.power} W (${driftP > 0 ? '+' : ''}${driftP}%)${sH.n ? `, FC ${T.inicio.hr}→${T.final.hr} bpm` : ''}.`,
    relacion: cPH != null ? `Relación potencia–FC: ${cPH > 0.3 ? 'alta' : 'moderada'} (r≈${cPH}); así se ve cuánto te cuesta cada vatio.` : (cPC != null ? `Potencia y cadencia: r≈${cPC}.` : 'Serie de potencia en el tiempo.'),
    significa: cae ? 'La potencia cae marcadamente hacia el final: fatiga o dosificación alta al inicio.' : desacople ? 'La potencia se sostiene pero la FC sube: aparece desacople (fatiga cardiovascular).' : 'Sostenés la entrega de potencia y la FC acompaña: buena eficiencia.',
    impacto: cae || desacople ? 'Perder potencia o que suba la FC a igual potencia penaliza el final de la prueba.' : 'Buena durabilidad: base para sostener el esfuerzo.',
    trabajar: cae || desacople ? 'Dosificación y resistencia específica (sweet spot / umbral) para sostener vatios con menos costo.' : null,
  }
}
function genPedaleo(filas) {
  const sLR = stat(filas, 'lr'), sT = stat(filas, 'torque')
  if (!sLR.n && !sT.n) return null
  const T = thirds(filas, ['lr', 'torque'])
  const out = {}
  if (sLR.n) {
    const desb = r1(Math.abs(sLR.avg - 50))
    const dom = sLR.avg > 50 ? 'izquierda' : 'derecha'
    const desbFinal = T.final.lr != null ? r1(Math.abs(T.final.lr - 50)) : null
    const crece = desbFinal != null && desbFinal > desb + 1.5
    out.observamos = `Balance izquierda/derecha ${sLR.avg}% / ${r1(100 - sLR.avg)}% (dominante: ${dom}).`
    out.numeros = `Desbalance medio ${desb}% respecto del 50/50.` + (desbFinal != null ? ` Al final: ${desbFinal}%.` : '')
    out.cuando = crece ? 'La asimetría se acentúa hacia el final de la sesión.' : 'La asimetría se mantiene pareja durante la sesión.'
    out.significa = desb >= 4 ? `Desbalance marcado hacia la pierna ${dom}: puede reflejar bike fitting, dominancia o fatiga de un lado.` : 'Balance dentro de lo normal (diferencias chicas son habituales).'
    out.trabajar = desb >= 4 ? 'Revisar el fit de la bici y sumar fuerza unilateral (sentadilla a una pierna, prensa unilateral).' : null
  }
  if (sT.n) {
    const driftT = T.inicio.torque ? r1((T.final.torque - T.inicio.torque) / T.inicio.torque * 100) : 0
    const caeT = driftT <= -5
    out.numeros = (out.numeros ? out.numeros + ' ' : '') + `Torque efectivo medio ${sT.avg}% (inicio→final ${T.inicio.torque}→${T.final.torque}%, ${driftT > 0 ? '+' : ''}${driftT}%).`
    if (!out.significa) out.significa = caeT ? 'La efectividad del pedaleo cae hacia el final: la técnica se desarma con la fatiga.' : 'Tu pedaleo mantiene la efectividad durante la sesión.'
    out.impacto = caeT ? 'Perder torque efectivo al final = más fuerza "desperdiciada" en la fase no propulsiva.' : 'Un pedaleo efectivo y estable ahorra energía.'
    if (!out.trabajar && caeT) out.trabajar = 'Drills de pedaleo redondo (una pierna, cadencia alta) y fuerza para sostener la técnica cansado.'
  }
  out.relacion = 'El balance L/R y el torque son métricas del medidor de potencia (Garmin Cycling Dynamics); se leen como tendencia, no como diagnóstico.'
  return out
}
function genCambios(filas, sport) {
  const keys = sport === 'cycling' ? ['power', 'cadence', 'torque'] : ['cadence', 'gct', 'vo']
  const presentes = keys.filter(k => stat(filas, k).n > 0)
  const T = thirds(filas, presentes)
  const etiquetas = { cadence: ['cadencia', 'spm'], gct: ['tiempo de contacto', 'ms'], vo: ['oscilación', 'cm'], power: ['potencia', 'W'], torque: ['torque efectivo', '%'] }
  let mayor = null
  for (const k of presentes) {
    const a = T.inicio[k], b = T.final[k]
    if (a == null || b == null || a === 0) continue
    const d = (b - a) / a * 100
    if (!mayor || Math.abs(d) > Math.abs(mayor.d)) mayor = { k, d: r1(d), a, b }
  }
  if (!mayor) return { T, interp: null, metricas: [] }
  const [nom, uni] = etiquetas[mayor.k]
  const relevante = Math.abs(mayor.d) >= 4
  const metricas = presentes.map(k => ({ key: k, label: etiquetas[k][0][0].toUpperCase() + etiquetas[k][0].slice(1), unit: etiquetas[k][1] }))
  return {
    T, metricas,
    interp: {
      observamos: `Comparamos inicio, mitad y final de la sesión en ${presentes.map(k => etiquetas[k][0]).join(', ')}.`,
      numeros: `El cambio más grande fue en ${nom}: ${mayor.a}→${mayor.b} ${uni} (${mayor.d > 0 ? '+' : ''}${mayor.d}%).`,
      cuando: 'La comparación es por tercios de la misma sesión, momentos compatibles entre sí.',
      relacion: relevante ? 'El cambio se sostiene a lo largo del tramo, no es un pico aislado.' : 'Las diferencias entre tercios son pequeñas.',
      significa: relevante ? `Hay un cambio técnico real hacia el final: tu ${nom} se desplaza de forma consistente.` : 'No hay deterioro técnico relevante: es variación normal dentro de la sesión.',
      impacto: relevante ? 'Un desplazamiento sostenido al final marca dónde empieza a pesar la fatiga.' : 'Buena durabilidad técnica dentro de la sesión.',
      trabajar: relevante ? 'Entrenar la técnica en estado de fatiga y fuerza para sostener el gesto.' : null,
    },
  }
}

// ════════ SEÑALES VISUALES (reemplazan el texto de "Qué vemos") ════════
function Mini({ serie, color }) {
  const data = (serie || []).map((v, i) => ({ i, v }))
  if (data.length < 2) return null
  return <ResponsiveContainer width="100%" height={42}><LineChart data={data} margin={{ top: 4, right: 2, left: 2, bottom: 0 }}>
    <Line dataKey="v" stroke={color} strokeWidth={2.2} dot={false} isAnimationActive={false} /></LineChart></ResponsiveContainer>
}
function driftTxt(dr, upLabel, downLabel) {
  if (dr == null) return null
  if (Math.abs(dr) < 3) return '■ estable toda la sesión'
  const up = dr > 0
  return `${up ? '▲' : '▼'} ${Math.abs(dr)}% ${up ? upLabel : downLabel} hacia el final`
}
function Chip({ label, value, unit, serie, good, drift }) {
  const col = good === false ? C.amber : good === true ? C.sage : C.dim
  return <div style={{ flex: '1 1 150px', minWidth: 150, ...glass, padding: 14 }}>
    <div style={{ fontSize: 11.5, color: C.dim, textTransform: 'uppercase', letterSpacing: 0.4 }}>{label}</div>
    <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, margin: '2px 0 4px' }}>
      <span style={{ fontSize: 28, fontWeight: 800, color: C.ink, ...num, lineHeight: 1 }}>{value}</span>
      <span style={{ fontSize: 12, color: C.dim }}>{unit}</span>
    </div>
    <Mini serie={serie} color={C.blue} />
    {drift && <div style={{ fontSize: 12, color: col, fontWeight: 700, marginTop: 2 }}>{drift}</div>}
  </div>
}
function SignalStrip({ sport, filas, d }) {
  const chips = []
  const mini = (key) => { const v = filas.map(r => r[key]).filter(x => x != null && isFinite(x)); const st = Math.max(1, Math.floor(v.length / 40)); return v.filter((_, i) => i % st === 0) }
  const drift = (key) => { const s = stat(filas, key); return s.n && s.p1 ? r1((s.p3 - s.p1) / s.p1 * 100) : null }
  if (sport === 'running') {
    const sc = stat(filas, 'cadence'); if (sc.n) { const dr = drift('cadence'); chips.push({ label: 'Cadencia', value: sc.avg, unit: 'spm', serie: mini('cadence'), good: dr == null || Math.abs(dr) < 4, drift: driftTxt(dr, 'sube', 'cae') }) }
    const sv = stat(filas, 'vo'); if (sv.n) { const dr = drift('vo'); chips.push({ label: 'Oscilación', value: sv.avg, unit: 'cm', serie: mini('vo'), good: dr == null || dr <= 4, drift: driftTxt(dr, 'más rebote', 'menos rebote') }) }
    else { const sh = stat(filas, 'hr'); if (sh.n) chips.push({ label: 'FC media', value: sh.avg, unit: 'bpm', serie: mini('hr'), good: null, drift: null }) }
  } else if (sport === 'cycling') {
    const sp = stat(filas, 'power'); if (sp.n) { const dr = drift('power'); chips.push({ label: 'Potencia', value: sp.avg, unit: 'W', serie: mini('power'), good: dr == null || dr >= -8, drift: driftTxt(dr, 'sube', 'cae') }) }
    const sc = stat(filas, 'cadence'); if (sc.n) { const dr = drift('cadence'); chips.push({ label: 'Cadencia', value: sc.avg, unit: 'rpm', serie: mini('cadence'), good: dr == null || Math.abs(dr) < 5, drift: driftTxt(dr, 'sube', 'cae') }) }
    const st = stat(filas, 'torque'); if (st.n) { const dr = drift('torque'); chips.push({ label: 'Torque efectivo', value: st.avg, unit: '%', serie: mini('torque'), good: dr == null || dr >= -5, drift: driftTxt(dr, 'sube', 'cae') }) }
  } else if (sport === 'swimming') {
    const largos = (d.curva_sesion && d.curva_sesion.largos) || []
    const brz = largos.map(l => l.paladas).filter(x => x != null)
    if (brz.length >= 3) { const dr = brz[0] ? r1((brz[brz.length - 1] - brz[0]) / brz[0] * 100) : null; const sub = Math.max(1, Math.floor(brz.length / 40)); chips.push({ label: 'Brazadas/largo', value: Math.round(brz.reduce((a, b) => a + b, 0) / brz.length), unit: '', serie: brz.filter((_, i) => i % sub === 0), good: dr == null || dr <= 5, drift: driftTxt(dr, 'sube (fatiga)', 'baja') }) }
    const met = d.metricas || {}
    if (met.swolf_avg != null) chips.push({ label: 'SWOLF', value: met.swolf_avg, unit: '', serie: largos.map(l => l.swolf).filter(x => x != null), good: null, drift: null })
    if (met.dps_avg != null) chips.push({ label: 'Dist/brazada', value: met.dps_avg, unit: 'm', serie: largos.map(l => l.dps).filter(x => x != null), good: null, drift: null })
  }
  if (!chips.length) return null
  return <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>{chips.map((c, i) => <Chip key={i} {...c} />)}</div>
}

// ════════ SEMÁFORO (estado de un vistazo) ════════
function semLevel(estado) {
  const k = (estado || '').toLowerCase()
  if (['elite', 'bueno', 'óptima', 'optima', 'equilibrado', 'estable'].includes(k)) return 'ok'
  if (['avanzado', 'promedio', 'intermedio', 'leve'].includes(k)) return 'warn'
  if (['mejorar', 'principiante', 'alerta', 'significativo'].includes(k)) return 'bad'
  return 'na'
}
function Semaforo({ label, value, unit, level }) {
  const colOf = { ok: C.green, warn: C.amber, bad: C.red, na: C.slate }
  const on = colOf[level] || C.slate
  const word = { ok: 'Óptimo', warn: 'Atención', bad: 'A mejorar', na: '—' }[level] || '—'
  const dot = (c, active) => <span style={{ width: 9, height: 9, borderRadius: 9, background: c, opacity: active ? 1 : 0.16, boxShadow: active ? `0 0 7px ${c}` : 'none' }} />
  return <div style={{ ...glass, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12, flex: '1 1 150px', minWidth: 150 }}>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, padding: '6px 5px', background: 'rgba(0,0,0,0.28)', borderRadius: 8 }}>
      {dot(C.red, level === 'bad')}{dot(C.amber, level === 'warn')}{dot(C.green, level === 'ok')}
    </div>
    <div>
      <div style={{ fontSize: 11.5, color: C.dim, textTransform: 'uppercase', letterSpacing: 0.3 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 800, color: C.ink, ...num, lineHeight: 1.1 }}>{value}<span style={{ fontSize: 11, color: C.dim, marginLeft: 2 }}>{unit}</span></div>
      <div style={{ fontSize: 12, fontWeight: 700, color: on }}>{word}</div>
    </div>
  </div>
}
function SemaforoRow({ sport, metricas, filas }) {
  const items = []
  const add = (k, label) => { const m = metricas[k]; if (!m || !META[k]) return; const v = META[k].val(m); if (v == null) return; items.push({ label, value: v, unit: META[k].unit, level: semLevel(m.estado) }) }
  if (sport === 'running') { add('cadencia', 'Cadencia'); add('gct', 'Contacto'); add('vertical_osc', 'Oscilación'); add('economia', 'Economía') }
  else if (sport === 'cycling') { add('cadencia', 'Cadencia'); add('torque_effectiveness', 'Torque'); const lr = metricas.lr_balance; if (lr && lr.promedio_pct != null) items.push({ label: 'Simetría L/D', value: lr.promedio_pct, unit: '%', level: lr.desbalance >= 8 ? 'bad' : lr.desbalance >= 4 ? 'warn' : 'ok' }) }
  // durabilidad bajo fatiga (de las muestras)
  if (filas && filas.length > 6) {
    const key = sport === 'cycling' ? 'power' : 'cadence'
    const s = stat(filas, key)
    if (s.n && s.p1) { const dr = Math.abs((s.p3 - s.p1) / s.p1 * 100); items.push({ label: 'Durabilidad', value: `${dr < 1 ? '' : (s.p3 - s.p1 > 0 ? '+' : '−')}${Math.round(Math.abs((s.p3 - s.p1) / s.p1 * 100))}`, unit: '%', level: dr < 4 ? 'ok' : dr < 8 ? 'warn' : 'bad' }) }
  }
  if (!items.length) return null
  return <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>{items.map((x, i) => <Semaforo key={i} {...x} />)}</div>
}

// ════════ CORRELACIONES (barras −1..+1) ════════
function CorrBars({ rels }) {
  if (!rels || !rels.length) return null
  const fuerza = (a) => a >= 0.3 ? 'fuerte' : a >= 0.15 ? 'moderada' : 'débil'
  return <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 6 }}>
    {rels.map((x, i) => {
      const a = Math.abs(x.r), col = a >= 0.3 ? C.blue : a >= 0.15 ? C.sage : C.slate, w = Math.min(50, a * 50)
      return <div key={i}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, fontSize: 13.5, color: C.ink, marginBottom: 5 }}>
          <span style={{ lineHeight: 1.4 }}>{x.lab}</span>
          <span style={{ color: col, fontWeight: 800, whiteSpace: 'nowrap', ...num }}>r={x.r}</span>
        </div>
        <div style={{ position: 'relative', height: 14, background: 'rgba(255,255,255,0.05)', borderRadius: 7 }}>
          <div style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 2, background: C.dim, opacity: 0.6 }} />
          <div style={{ position: 'absolute', top: 0, bottom: 0, borderRadius: 7, background: col, left: x.r >= 0 ? '50%' : `${50 - w}%`, width: `${w}%` }} />
        </div>
        <div style={{ fontSize: 12, color: C.dim, marginTop: 3 }}>relación {fuerza(a)}{x.n ? ` · ${x.n} muestras` : ''}</div>
      </div>
    })}
    <div style={{ fontSize: 12, color: C.dim }}>r va de −1 a +1. A la derecha suben juntas; a la izquierda una sube y la otra baja; cerca de 0 casi no se relacionan.</div>
  </div>
}
function corrN(filas, kx, ky) { const pts = filas.filter(r => r[kx] != null && r[ky] != null && isFinite(r[kx]) && isFinite(r[ky])); return { r: corr(filas, kx, ky), n: pts.length } }
function relsDe(filas, sport) {
  const out = []
  const push = (lab, kx, ky) => { const { r, n } = corrN(filas, kx, ky); if (r != null && n >= 10) out.push({ lab, r, n }) }
  if (sport === 'running') {
    push('Más velocidad ↔ más cadencia', 'speed_ms', 'cadence')
    push('Más velocidad ↔ más FC (cuánto te cuesta correr rápido)', 'speed_ms', 'hr')
    push('Más cadencia ↔ menos oscilación', 'cadence', 'vo')
    push('Más velocidad ↔ más oscilación', 'speed_ms', 'vo')
    push('Más velocidad ↔ menos tiempo de contacto', 'speed_ms', 'gct')
  } else if (sport === 'cycling') {
    push('Más potencia ↔ más cadencia', 'power', 'cadence')
    push('Más potencia ↔ más FC (desacople aeróbico)', 'power', 'hr')
    push('Más velocidad ↔ más cadencia', 'speed_ms', 'cadence')
    push('Más velocidad ↔ más FC', 'speed_ms', 'hr')
    push('Más cadencia ↔ más torque efectivo', 'cadence', 'torque')
  }
  return out
}

// ════════ GRÁFICOS INSIGNIA (uno por disciplina, calidad profesional) ════════
function HeadG({ eyebrow, titulo, subtitulo }) {
  return <>
    <div style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: 0.7, color: C.sage, textTransform: 'uppercase', marginBottom: 5 }}>{eyebrow}</div>
    <div style={{ fontSize: 20, fontWeight: 700, color: C.ink, lineHeight: 1.2 }}>{titulo}</div>
    {subtitulo && <div style={{ fontSize: 15, color: C.dim, margin: '5px 0 14px', lineHeight: 1.5 }}>{subtitulo}</div>}
  </>
}
function Conclusion({ que, relacion, mejorar }) {
  const Row = ({ k, v }) => <div style={{ marginBottom: 9 }}><div style={{ fontSize: 12.5, fontWeight: 700, color: C.blue, marginBottom: 2 }}>{k}</div><div style={{ fontSize: 14.5, color: C.ink, lineHeight: 1.55, opacity: 0.95 }}>{v}</div></div>
  return <div style={{ marginTop: 16, paddingTop: 14, borderTop: `1px solid ${C.border}` }}>
    <Row k="¿Qué está pasando?" v={que} /><Row k="¿Qué relación hay?" v={relacion} /><Row k="¿Qué mejorar y por qué?" v={mejorar} />
  </div>
}
function LeyendaCuad({ items }) {
  return <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 8, marginTop: 12 }}>
    {items.map((q, i) => <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
      <span style={{ width: 12, height: 12, borderRadius: 4, background: q.col, flex: '0 0 auto', marginTop: 3, border: `1px solid ${C.border}` }} />
      <div><div style={{ fontSize: 13.5, fontWeight: 700, color: C.ink }}>{q.nombre}</div><div style={{ fontSize: 12.5, color: C.dim, lineHeight: 1.4 }}>{q.desc}</div></div>
    </div>)}
  </div>
}

// Running — cadencia × zancada × velocidad
function FlagRunning({ filas }) {
  const base = filas.filter(r => r.cadence != null && r.stride != null && r.speed_ms != null)
  if (base.length < 12) return <SensorFalta sensor="un sensor de Running Dynamics (zancada) con datos muestra-a-muestra" />
  const cad = base.map(s => s.cadence), str = base.map(s => s.stride), spd = base.map(s => s.speed_ms)
  const mCad = Math.round(median(cad)), mStr = r1(median(str) * 100) / 100 || r1(median(str))
  const mStr2 = Math.round(median(str) * 100) / 100
  const sMin = Math.min(...spd), sMax = Math.max(...spd)
  const pts = base.map(s => ({ cadence: s.cadence, stride: s.stride, _c: hexLerp(C.sage, C.blue, sMax > sMin ? (s.speed_ms - sMin) / (sMax - sMin) : 0.5) }))
  const xMin = Math.min(...cad), xMax = Math.max(...cad), yMin = Math.min(...str), yMax = Math.max(...str)
  const pctAgil = Math.round(base.filter(r => r.cadence >= mCad && r.stride <= mStr2).length / base.length * 100)
  return <Glass>
    <HeadG eyebrow="Running · Mapa biomecánico" titulo="Cadencia × Zancada × Velocidad" subtitulo="Cada punto es un instante real tuyo. Color: verde = lento, azul = rápido. Las líneas son TU propia mediana, no un valor universal." />
    <ResponsiveContainer width="100%" height={372}>
      <ScatterChart margin={{ top: 16, right: 34, left: 22, bottom: 30 }}>
        <ReferenceArea x1={mCad} y1={mStr2} x2={xMax + 4} y2={yMax + 0.05} fill={C.blue} fillOpacity={0.10} label={{ value: 'Zancada potente', position: 'insideTopRight', fill: C.blue, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={mCad} y1={yMin - 0.05} x2={xMax + 4} y2={mStr2} fill={C.sage} fillOpacity={0.14} label={{ value: 'Paso corto y ágil', position: 'insideBottomRight', fill: C.sage, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={xMin - 3} y1={mStr2} x2={mCad} y2={yMax + 0.05} fill={C.amber} fillOpacity={0.10} label={{ value: 'Sobrepaso', position: 'insideTopLeft', fill: C.amber, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={xMin - 3} y1={yMin - 0.05} x2={mCad} y2={mStr2} fill={C.slate} fillOpacity={0.12} label={{ value: 'Lento y corto', position: 'insideBottomLeft', fill: C.dim, fontSize: 13.5, fontWeight: 700 }} />
        <CartesianGrid stroke="rgba(255,255,255,0.05)" />
        <XAxis type="number" dataKey="cadence" name="Cadencia" domain={[xMin - 3, xMax + 3]} tick={{ fill: C.dim, fontSize: 14 }} tickMargin={8} label={{ value: 'Cadencia (spm)', position: 'bottom', fill: C.ink, fontSize: 15, offset: 8 }} />
        <YAxis type="number" dataKey="stride" name="Zancada" domain={[yMin - 0.05, yMax + 0.05]} tick={{ fill: C.dim, fontSize: 14 }} width={46} tickFormatter={v => v.toFixed(2)} label={{ value: 'Zancada (m)', angle: -90, position: 'left', fill: C.ink, fontSize: 15, dx: 6 }} />
        <ZAxis range={[46, 46]} />
        <ReferenceLine x={mCad} stroke={C.dim} strokeDasharray="5 5" /><ReferenceLine y={mStr2} stroke={C.dim} strokeDasharray="5 5" />
        <Tooltip cursor={{ stroke: C.dim }} contentStyle={tip} />
        <Scatter data={pts} isAnimationActive={false}>{pts.map((p, i) => <Cell key={i} fill={p._c} fillOpacity={0.6} />)}</Scatter>
      </ScatterChart>
    </ResponsiveContainer>
    <div style={{ fontSize: 12.5, color: C.dim, marginTop: 4 }}>Líneas punteadas = tu mediana de cadencia ({mCad} spm) y de zancada ({mStr2} m).</div>
    <LeyendaCuad items={[
      { nombre: 'Paso corto y ágil', desc: 'Cadencia alta, zancada contenida: suele ser lo más económico.', col: C.sage },
      { nombre: 'Zancada potente', desc: 'Cadencia y zancada altas: tramos rápidos.', col: C.blue },
      { nombre: 'Sobrepaso / freno', desc: 'Zancada larga con cadencia baja: pisás por delante y frenás.', col: C.amber },
      { nombre: 'Lento y corto', desc: 'Cadencia y zancada bajas: rodaje suave o subida.', col: C.slate },
    ]} />
    <Conclusion
      que={`Pasaste el ${pctAgil}% del tiempo en "paso corto y ágil" (cadencia ≥ ${mCad} spm con zancada ≤ ${mStr2} m).`}
      relacion="A más velocidad (puntos azules) la zancada se alarga; lo clave es que no caiga la cadencia, porque ahí aparece el sobrepaso."
      mejorar={pctAgil >= 55 ? 'Tu patrón dominante ya es económico: mantené la cadencia en los tramos rápidos.' : 'Buscá subir la cadencia en los tramos rápidos para no irte al cuadrante de sobrepaso (freno y mayor impacto).'} />
  </Glass>
}

// Ciclismo — círculo de pedaleo (modelo) alimentado por datos reales
const _pol = (cx, cy, r, deg) => { const a = (deg - 90) * Math.PI / 180; return [cx + r * Math.cos(a), cy + r * Math.sin(a)] }
const _arc = (cx, cy, r, d0, d1) => { const [x0, y0] = _pol(cx, cy, r, d0), [x1, y1] = _pol(cx, cy, r, d1); const large = (((d1 - d0) % 360) + 360) % 360 > 180 ? 1 : 0; return `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}` }
function PedalClock({ filas }) {
  const sT = stat(filas, 'torque'), sP = stat(filas, 'pedal'), sLR = stat(filas, 'lr')
  if (!sT.n && !sLR.n) return <SensorFalta sensor="un medidor con Cycling Dynamics (torque y balance L/D)" />
  const te = sT.n ? Math.round(sT.avg) : null
  const ps = sP.n ? Math.round(sP.avg) : null
  const lrL = sLR.n ? r1(sLR.avg) : null, lrR = lrL != null ? r1(100 - lrL) : null
  const desb = lrL != null ? r1(Math.abs(lrL - 50)) : null
  const dom = lrL != null ? (lrL > 50 ? 'izquierda' : 'derecha') : null
  const teDeg = te != null ? te * 3.6 : 0
  return <Glass>
    <HeadG eyebrow="Ciclismo · Pedaleo" titulo="¿Cómo pedaleás?" subtitulo="Modelo del ciclo de pedalada. El relleno y el balance salen de datos REALES del medidor; la trayectoria del pie es un esquema, no una medición." />
    <div style={{ background: 'rgba(230,181,85,0.08)', border: `1px solid ${C.border}`, borderRadius: 12, padding: '9px 13px', fontSize: 12.5, color: C.dim, marginBottom: 14, lineHeight: 1.45 }}>
      ⓘ El sensor mide <b style={{ color: C.ink }}>efectividad</b> y <b style={{ color: C.ink }}>balance izq/der</b>, no la posición del pie en cada punto del giro.
    </div>
    <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', justifyContent: 'center' }}>
      {/* Gauge de efectividad (fuerza útil) */}
      {te != null && <div style={{ textAlign: 'center' }}>
        <svg viewBox="0 0 160 160" width="160" height="160">
          <circle cx="80" cy="80" r="62" fill="none" stroke={C.slate} strokeOpacity="0.35" strokeWidth="14" />
          <path d={_arc(80, 80, 62, 0.01, Math.max(1, teDeg))} fill="none" stroke={C.sage} strokeWidth="14" strokeLinecap="round" />
          <text x="80" y="74" fill={C.ink} fontSize="34" fontWeight="800" textAnchor="middle" fontFamily="Inter" style={num}>{te}<tspan fontSize="16" fill={C.dim}>%</tspan></text>
          <text x="80" y="98" fill={C.dim} fontSize="12.5" textAnchor="middle" fontFamily="Inter">fuerza útil</text>
        </svg>
        <div style={{ fontSize: 12.5, color: C.dim, maxWidth: 170 }}>Torque efectivo: parte de la pedalada que empuja.</div>
      </div>}
      {/* Reloj de pedaleo (modelo conceptual) */}
      <div style={{ textAlign: 'center' }}>
        <svg viewBox="0 0 160 160" width="160" height="160">
          <circle cx="80" cy="80" r="60" fill="none" stroke="rgba(255,255,255,0.10)" strokeWidth="2" />
          <path d={_arc(80, 80, 60, 25, 155)} fill="none" stroke={C.sage} strokeWidth="12" strokeLinecap="round" opacity="0.92" />
          <path d={_arc(80, 80, 60, 205, 335)} fill="none" stroke={C.slate} strokeWidth="7" strokeLinecap="round" opacity="0.8" />
          {[0, 180].map((d, i) => { const [x, y] = _pol(80, 80, 60, d); return <circle key={i} cx={x} cy={y} r="5" fill={C.amber} /> })}
          <text x="128" y="84" fill={C.sage} fontSize="12.5" fontWeight="700" textAnchor="middle" fontFamily="Inter">empuje</text>
          <text x="34" y="84" fill={C.dim} fontSize="12" textAnchor="middle" fontFamily="Inter">recobro</text>
          <text x="80" y="14" fill={C.amber} fontSize="11" textAnchor="middle" fontFamily="Inter">punto muerto</text>
          <text x="80" y="154" fill={C.amber} fontSize="11" textAnchor="middle" fontFamily="Inter">punto muerto</text>
        </svg>
        <div style={{ fontSize: 12.5, color: C.dim, maxWidth: 170 }}>Esquema del giro: dónde producís fuerza y dónde hay punto muerto.</div>
      </div>
    </div>
    {/* Balance izquierda / derecha */}
    {lrL != null && <div style={{ marginTop: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13, color: C.ink, marginBottom: 6 }}>
        <span><b style={{ color: C.sage }}>{lrL}%</b> izquierda</span>
        <span style={{ color: C.dim }}>balance</span>
        <span>derecha <b style={{ color: C.blue }}>{lrR}%</b></span>
      </div>
      <div style={{ position: 'relative', height: 16, borderRadius: 8, overflow: 'hidden', display: 'flex' }}>
        <div style={{ width: `${lrL}%`, background: C.sage }} /><div style={{ width: `${lrR}%`, background: C.blue }} />
        <div style={{ position: 'absolute', left: '50%', top: -3, bottom: -3, width: 2, background: C.ink, opacity: 0.8 }} />
      </div>
      <div style={{ fontSize: 12.5, color: desb >= 4 ? C.amber : C.dim, marginTop: 6 }}>
        {desb >= 4 ? `Desbalance ${desb}% hacia la pierna ${dom} — a vigilar (fit / fuerza unilateral).` : `Equilibrado (desbalance ${desb}%). La línea blanca es el 50/50 ideal.`}
      </div>
    </div>}
    {ps != null && <div style={{ fontSize: 12.5, color: C.dim, marginTop: 12 }}>Suavidad de pedaleo: <b style={{ color: C.ink }}>{ps}%</b> — qué tan parejo entregás la fuerza en el giro.</div>}
  </Glass>
}

// Ciclismo — cadencia × potencia, 4 cuadrantes
function FlagCycling({ filas }) {
  const base = filas.filter(r => r.cadence != null && r.power != null)
  if (base.length < 12) return <SensorFalta sensor="un medidor de potencia con datos muestra-a-muestra" />
  const cad = base.map(s => s.cadence), pw = base.map(s => s.power)
  const mCad = Math.round(median(cad)), mPw = Math.round(median(pw))
  const xMin = Math.min(...cad), xMax = Math.max(...cad), yMin = Math.min(...pw), yMax = Math.max(...pw)
  // color por cuadrante (cada color = un patrón)
  const QC = { fuerza: C.amber, potvel: C.sage, rodaje: C.blue, pesado: C.slate }
  const quad = (s) => s.power >= mPw ? (s.cadence < mCad ? 'fuerza' : 'potvel') : (s.cadence >= mCad ? 'rodaje' : 'pesado')
  const pts = base.map(s => ({ cadence: s.cadence, power: s.power, _c: QC[quad(s)] }))
  const pctFuerza = Math.round(base.filter(s => quad(s) === 'fuerza').length / base.length * 100)
  const pctPot = Math.round(base.filter(s => quad(s) === 'potvel').length / base.length * 100)
  return <Glass>
    <HeadG eyebrow="Ciclismo · Mapa de pedaleo" titulo="Cadencia × Potencia — 4 cuadrantes" subtitulo="Cada punto es una muestra real, pintado según su patrón. Los ejes se cruzan en TU mediana (referencia individual, no un valor fijo)." />
    <ResponsiveContainer width="100%" height={372}>
      <ScatterChart margin={{ top: 16, right: 34, left: 26, bottom: 30 }}>
        <ReferenceArea x1={xMin - 3} y1={mPw} x2={mCad} y2={yMax + 15} fill={C.amber} fillOpacity={0.09} label={{ value: 'Fuerza', position: 'insideTopLeft', fill: C.amber, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={mCad} y1={mPw} x2={xMax + 3} y2={yMax + 15} fill={C.sage} fillOpacity={0.12} label={{ value: 'Potencia-velocidad', position: 'insideTopRight', fill: C.sage, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={mCad} y1={yMin - 15} x2={xMax + 3} y2={mPw} fill={C.blue} fillOpacity={0.10} label={{ value: 'Rodaje suelto', position: 'insideBottomRight', fill: C.blue, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={xMin - 3} y1={yMin - 15} x2={mCad} y2={mPw} fill={C.slate} fillOpacity={0.12} label={{ value: 'Pesado', position: 'insideBottomLeft', fill: C.dim, fontSize: 13.5, fontWeight: 700 }} />
        <CartesianGrid stroke="rgba(255,255,255,0.05)" />
        <XAxis type="number" dataKey="cadence" name="Cadencia" domain={[xMin - 3, xMax + 3]} tick={{ fill: C.dim, fontSize: 14 }} tickMargin={8} label={{ value: 'Cadencia (rpm)', position: 'bottom', fill: C.ink, fontSize: 15, offset: 8 }} />
        <YAxis type="number" dataKey="power" name="Potencia" domain={[yMin - 15, yMax + 15]} tick={{ fill: C.dim, fontSize: 14 }} width={48} label={{ value: 'Potencia (W)', angle: -90, position: 'left', fill: C.ink, fontSize: 15, dx: 8 }} />
        <ZAxis range={[50, 50]} />
        <ReferenceLine x={mCad} stroke={C.dim} strokeDasharray="5 5" /><ReferenceLine y={mPw} stroke={C.dim} strokeDasharray="5 5" />
        <Tooltip cursor={{ stroke: C.dim }} contentStyle={tip} />
        <Scatter data={pts} isAnimationActive={false}>{pts.map((p, i) => <Cell key={i} fill={p._c} fillOpacity={0.55} />)}</Scatter>
      </ScatterChart>
    </ResponsiveContainer>
    <div style={{ fontSize: 12.5, color: C.dim, marginTop: 4 }}>Líneas punteadas = tu mediana de cadencia ({mCad} rpm) y de potencia ({mPw} W).</div>
    <LeyendaCuad items={[
      { nombre: 'Fuerza (torque)', desc: 'Cadencia baja + potencia alta: empujás grande. Cuida rodillas.', col: C.amber },
      { nombre: 'Potencia-velocidad', desc: 'Cadencia alta + potencia alta: tramos fuertes y ágiles.', col: C.sage },
      { nombre: 'Rodaje suelto', desc: 'Cadencia alta + potencia baja: piernas frescas, eficiente.', col: C.blue },
      { nombre: 'Pesado / recuperación', desc: 'Cadencia y potencia bajas: recuperás o vas trancado.', col: C.slate },
    ]} />
    <Conclusion
      que={`Pasás el ${pctFuerza}% del tiempo en "fuerza" (cadencia < ${mCad} rpm con potencia ≥ ${mPw} W).`}
      relacion="Cuanto más alta la potencia, podés mantenerla con más cadencia (ágil) o con más fuerza (torque). Tu nube muestra cuál elegís."
      mejorar={pctFuerza >= 35 ? 'Tendés a empujar grande: sumá cadencia en los esfuerzos para descargar las piernas de cara a la corrida.' : 'Buena cadencia bajo potencia. Mantené este patrón en los intervalos fuertes.'} />
  </Glass>
}

// Mapa UNIVERSAL cadencia × velocidad (sirve para todo atleta: solo pulso/cadencia/GPS)
function FlagMapaCV({ filas, sport }) {
  const yKey = sport === 'cycling' ? 'kmh' : 'pace'
  const base = filas.filter(r => r.cadence != null && r[yKey] != null && r.speed_ms != null)
  if (base.length < 12) return null
  const cad = base.map(s => s.cadence), ys = base.map(s => s[yKey]), spd = base.map(s => s.speed_ms)
  const mCad = Math.round(median(cad)), mY = sport === 'cycling' ? r1(median(ys)) : Math.round(median(ys) * 100) / 100
  const sMin = Math.min(...spd), sMax = Math.max(...spd)
  const pts = base.map(s => ({ cadence: s.cadence, [yKey]: s[yKey], _c: hexLerp(C.sage, C.blue, sMax > sMin ? (s.speed_ms - sMin) / (sMax - sMin) : 0.5) }))
  const xMin = Math.min(...cad), xMax = Math.max(...cad), yMin = Math.min(...ys), yMax = Math.max(...ys)
  const rev = sport !== 'cycling'
  const fy = rev ? [yMin, mY] : [mY, yMax], sy = rev ? [mY, yMax] : [yMin, mY]
  const nombres = sport === 'cycling'
    ? { fr: 'Ágil y rápido', fl: 'Fuerza / desarrollo', sr: 'Girar suave', sl: 'Suave' }
    : { fr: 'Ágil y rápido', fl: 'Zancada larga', sr: 'Cadencia alta, suave', sl: 'Suave' }
  const fast = (s) => sport === 'cycling' ? s[yKey] >= mY : s[yKey] <= mY
  const pctAgil = Math.round(base.filter(s => s.cadence >= mCad && fast(s)).length / base.length * 100)
  const yLbl = sport === 'cycling' ? 'Velocidad (km/h)' : 'Ritmo (/km)'
  return <Glass>
    <HeadG eyebrow={`${sport === 'cycling' ? 'Ciclismo' : 'Running'} · Mapa`} titulo={`Cadencia × ${sport === 'cycling' ? 'Velocidad' : 'Ritmo'}`} subtitulo="Cada punto es un instante real tuyo (color: verde = lento, azul = rápido). Las líneas son TU propia mediana." />
    <ResponsiveContainer width="100%" height={372}>
      <ScatterChart margin={{ top: 16, right: 34, left: 26, bottom: 30 }}>
        <ReferenceArea x1={mCad} y1={fy[0]} x2={xMax + 3} y2={fy[1]} fill={C.sage} fillOpacity={0.14} label={{ value: nombres.fr, position: 'insideTopRight', fill: C.sage, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={xMin - 3} y1={fy[0]} x2={mCad} y2={fy[1]} fill={C.blue} fillOpacity={0.10} label={{ value: nombres.fl, position: 'insideTopLeft', fill: C.blue, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={mCad} y1={sy[0]} x2={xMax + 3} y2={sy[1]} fill={C.slate} fillOpacity={0.10} label={{ value: nombres.sr, position: 'insideBottomRight', fill: C.dim, fontSize: 13, fontWeight: 700 }} />
        <ReferenceArea x1={xMin - 3} y1={sy[0]} x2={mCad} y2={sy[1]} fill={C.slate} fillOpacity={0.06} label={{ value: nombres.sl, position: 'insideBottomLeft', fill: C.dim, fontSize: 13, fontWeight: 700 }} />
        <CartesianGrid stroke="rgba(255,255,255,0.05)" />
        <XAxis type="number" dataKey="cadence" name="Cadencia" domain={[xMin - 3, xMax + 3]} tick={{ fill: C.dim, fontSize: 14 }} tickMargin={8} label={{ value: sport === 'cycling' ? 'Cadencia (rpm)' : 'Cadencia (spm)', position: 'bottom', fill: C.ink, fontSize: 15, offset: 8 }} />
        <YAxis type="number" dataKey={yKey} name={yLbl} domain={[yMin, yMax]} reversed={rev} tick={{ fill: C.dim, fontSize: 14 }} width={52} tickFormatter={rev ? fmtPace : undefined} label={{ value: yLbl, angle: -90, position: 'left', fill: C.ink, fontSize: 15, dx: 10 }} />
        <ZAxis range={[46, 46]} />
        <ReferenceLine x={mCad} stroke={C.dim} strokeDasharray="5 5" /><ReferenceLine y={mY} stroke={C.dim} strokeDasharray="5 5" />
        <Tooltip cursor={{ stroke: C.dim }} contentStyle={tip} formatter={(v, n) => [rev && n === yLbl ? fmtPace(v) : v, n]} />
        <Scatter data={pts} isAnimationActive={false}>{pts.map((p, i) => <Cell key={i} fill={p._c} fillOpacity={0.6} />)}</Scatter>
      </ScatterChart>
    </ResponsiveContainer>
    <div style={{ fontSize: 12.5, color: C.dim, marginTop: 4 }}>Mediana de cadencia {mCad}{sport === 'cycling' ? ' rpm' : ' spm'} y de {sport === 'cycling' ? `velocidad ${mY} km/h` : `ritmo ${fmtPace(mY)}/km`}.</div>
    <Conclusion
      que={`Pasaste el ${pctAgil}% del tiempo "ágil y rápido" (cadencia ≥ ${mCad} con buena velocidad).`}
      relacion="Sostener la velocidad con buena cadencia descarga las piernas; bajar la cadencia para ir rápido carga más el músculo."
      mejorar={pctAgil >= 55 ? 'Buen registro: mantené la cadencia cuando apretás el ritmo.' : 'Buscá subir la cadencia en los tramos rápidos en vez de alargar/pisar más fuerte.'} />
  </Glass>
}

// Ciclismo sin cadencia — Potencia × Velocidad (color por FC)
function FlagPotVel({ filas }) {
  const base = filas.filter(r => r.power != null && r.kmh != null)
  if (base.length < 12) return null
  const pw = base.map(s => s.power), vk = base.map(s => s.kmh), hrs = base.map(s => s.hr).filter(x => x != null)
  const mP = Math.round(median(pw)), mV = r1(median(vk))
  const hMin = hrs.length ? Math.min(...hrs) : 0, hMax = hrs.length ? Math.max(...hrs) : 1
  const pts = base.map(s => ({ power: s.power, kmh: s.kmh, _c: s.hr != null && hMax > hMin ? hexLerp(C.sage, C.amber, (s.hr - hMin) / (hMax - hMin)) : C.blue }))
  const xMin = Math.min(...pw), xMax = Math.max(...pw), yMin = Math.min(...vk), yMax = Math.max(...vk)
  const pctEf = Math.round(base.filter(s => s.power <= mP && s.kmh >= mV).length / base.length * 100)
  return <Glass>
    <HeadG eyebrow="Ciclismo · Mapa" titulo="Potencia × Velocidad" subtitulo="Cada punto es un instante real (color: verde = FC baja, ámbar = FC alta). Arriba-izquierda = más velocidad con menos vatios = más eficiente/aero." />
    <ResponsiveContainer width="100%" height={372}>
      <ScatterChart margin={{ top: 16, right: 34, left: 26, bottom: 30 }}>
        <ReferenceArea x1={xMin - 5} y1={mV} x2={mP} y2={yMax + 1} fill={C.sage} fillOpacity={0.14} label={{ value: 'Eficiente', position: 'insideTopLeft', fill: C.sage, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={mP} y1={yMin - 1} x2={xMax + 5} y2={mV} fill={C.amber} fillOpacity={0.10} label={{ value: 'Mucho vatio, poca velocidad', position: 'insideBottomRight', fill: C.amber, fontSize: 12.5, fontWeight: 700 }} />
        <CartesianGrid stroke="rgba(255,255,255,0.05)" />
        <XAxis type="number" dataKey="power" name="Potencia" domain={[xMin - 5, xMax + 5]} tick={{ fill: C.dim, fontSize: 14 }} tickMargin={8} label={{ value: 'Potencia (W)', position: 'bottom', fill: C.ink, fontSize: 15, offset: 8 }} />
        <YAxis type="number" dataKey="kmh" name="Velocidad" domain={[yMin - 1, yMax + 1]} tick={{ fill: C.dim, fontSize: 14 }} width={48} label={{ value: 'Velocidad (km/h)', angle: -90, position: 'left', fill: C.ink, fontSize: 15, dx: 6 }} />
        <ZAxis range={[46, 46]} />
        <ReferenceLine x={mP} stroke={C.dim} strokeDasharray="5 5" /><ReferenceLine y={mV} stroke={C.dim} strokeDasharray="5 5" />
        <Tooltip cursor={{ stroke: C.dim }} contentStyle={tip} />
        <Scatter data={pts} isAnimationActive={false}>{pts.map((p, i) => <Cell key={i} fill={p._c} fillOpacity={0.6} />)}</Scatter>
      </ScatterChart>
    </ResponsiveContainer>
    <div style={{ fontSize: 12.5, color: C.dim, marginTop: 4 }}>Mediana de potencia {mP} W y de velocidad {mV} km/h.</div>
    <Conclusion
      que={`El ${pctEf}% del tiempo lograste velocidad alta con potencia baja (zona eficiente).`}
      relacion="A igual potencia, ir más rápido = mejor posición/aero y rodada. El color muestra el costo cardíaco de cada punto."
      mejorar={pctEf >= 50 ? 'Buena eficiencia: sostené la posición aero en los tramos rápidos.' : 'Hay margen aero: posición más baja y constante para ganar velocidad sin más vatios.'} />
  </Glass>
}

// Natación — reparto de estilos: barra apilada COMPACTA (no una dona gigante)
function SwimDistribucion({ estilos }) {
  const items = estilos.map(([n, e]) => ({ name: n, value: e.n_largos || 0 })).filter(x => x.value > 0).sort((a, b) => b.value - a.value)
  const total = items.reduce((s, x) => s + x.value, 0)
  if (total < 3) return null
  const cols = [C.sage, C.blue, C.amber, C.slate, C.cLit]
  return <Glass style={{ padding: 16 }}>
    <div style={{ fontSize: 12.5, fontWeight: 700, letterSpacing: 0.6, color: C.sage, textTransform: 'uppercase', marginBottom: 10 }}>Reparto de estilos · {total} largos</div>
    <div style={{ display: 'flex', height: 18, borderRadius: 9, overflow: 'hidden' }}>
      {items.map((x, i) => <div key={i} title={x.name} style={{ width: `${x.value / total * 100}%`, background: cols[i % cols.length] }} />)}
    </div>
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 10 }}>
      {items.map((x, i) => <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13 }}>
        <span style={{ width: 11, height: 11, borderRadius: 3, background: cols[i % cols.length] }} />
        <span style={{ color: C.ink, fontWeight: 600 }}>{x.name}</span><span style={{ color: C.dim, ...num }}>{Math.round(x.value / total * 100)}%</span>
      </span>)}
    </div>
  </Glass>
}

// Natación — FATIGA de la sesión: barras divergentes (inicio→final)
function FatigaPanel({ largos }) {
  const L = (largos || []).filter(l => l != null)
  if (L.length < 6) return null
  const t = Math.max(1, Math.floor(L.length / 3))
  const seg = (arr, k) => { const v = arr.map(x => x[k]).filter(n => n != null && isFinite(n)); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null }
  const ini = L.slice(0, t), fin = L.slice(-t)
  const metricas = [
    { k: 'swolf', label: 'SWOLF', peor: 'up' },
    { k: 'dps', label: 'Distancia por brazada', peor: 'down' },
    { k: 'paladas', label: 'Brazadas por largo', peor: 'up' },
    { k: 'hr', label: 'Frecuencia cardíaca', peor: 'up' },
  ]
  const rows = metricas.map(m => {
    const a = seg(ini, m.k), b = seg(fin, m.k)
    if (a == null || b == null || a === 0) return null
    const d = r1((b - a) / a * 100)
    const malo = m.peor === 'up' ? d > 1.5 : d < -1.5
    return { ...m, a: r1(a), b: r1(b), d, malo }
  }).filter(Boolean)
  if (!rows.length) return null
  const maxAbs = Math.max(8, ...rows.map(r => Math.abs(r.d)))
  return <Glass>
    <HeadG eyebrow="Natación · Fatiga" titulo="¿Qué le pasa a tu brazada al final?" subtitulo="Cambio del primer al último tercio de la sesión. A la derecha empeora, a la izquierda mejora." />
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginTop: 6 }}>
      {rows.map((r, i) => {
        const col = r.malo ? C.amber : Math.abs(r.d) < 1.5 ? C.slate : C.sage
        const pos = r.peor === 'up' ? r.d > 0 : r.d < 0  // a la derecha = empeora
        const w = Math.min(50, Math.abs(r.d) / maxAbs * 50)
        return <div key={i}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13.5, color: C.ink, marginBottom: 5 }}>
            <span>{r.label}</span><span style={{ color: col, fontWeight: 800, ...num }}>{r.d > 0 ? '+' : ''}{r.d}%</span>
          </div>
          <div style={{ position: 'relative', height: 14, background: 'rgba(255,255,255,0.05)', borderRadius: 7 }}>
            <div style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 2, background: C.dim, opacity: 0.6 }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, borderRadius: 7, background: col, left: pos ? '50%' : `${50 - w}%`, width: `${w}%` }} />
          </div>
          <div style={{ fontSize: 12, color: C.dim, marginTop: 3, ...num }}>{r.a} → {r.b}</div>
        </div>
      })}
    </div>
    <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start', marginTop: 14, background: `${C.sage}14`, border: `1px solid ${C.sage}3A`, borderRadius: 12, padding: '10px 13px' }}>
      <span style={{ color: C.sage, fontSize: 15, fontWeight: 800 }}>✓</span>
      <span style={{ fontSize: 14, color: C.ink, lineHeight: 1.5 }}>{rows.some(r => r.malo) ? 'Tu técnica pierde algo de eficiencia con la fatiga: trabajá series largas manteniendo la distancia por brazada.' : 'Mantenés la técnica estable toda la sesión: buena resistencia del gesto.'}</span>
    </div>
  </Glass>
}

// Natación — RELACIONES técnicas: barras de correlación (reemplazan el texto)
function RelacionesPanel({ interp }) {
  const rels = []
  for (const t of interp || []) {
    const m = t.match(/\(r=(-?\d+(?:\.\d+)?),?\s*n=(\d+)/)
    if (!m) continue
    const r = parseFloat(m[1]), n = parseInt(m[2])
    let lab = t.split('(r=')[0].trim()
    const parts = lab.split('—'); lab = (parts[0] || lab).trim()
    if (lab.length > 90) lab = lab.slice(0, 88) + '…'
    rels.push({ lab, r, n })
  }
  if (!rels.length) return null
  return <Glass>
    <HeadG eyebrow="Natación · Relaciones" titulo="¿Cómo se relacionan tus variables?" subtitulo="Qué tan ligadas están tus métricas entre sí. Barra a la derecha = suben juntas; a la izquierda = una sube y la otra baja." />
    <CorrBars rels={rels} />
  </Glass>
}

// Natación — frecuencia × amplitud (mapa de eficiencia del nadador)
function SwimFreqAmplitud({ largos }) {
  const base = (largos || []).filter(l => l.paladas != null && l.dps != null && l.paladas > 0 && l.dps > 0)
  if (base.length < 6) return null
  const br = base.map(l => l.paladas), dp = base.map(l => l.dps), pc = base.map(l => l.pace).filter(x => x != null)
  const mBr = Math.round(median(br)), mDp = Math.round(median(dp) * 100) / 100
  const pcMin = pc.length ? Math.min(...pc) : 0, pcMax = pc.length ? Math.max(...pc) : 1
  const pts = base.map(l => ({ paladas: l.paladas, dps: l.dps, _c: l.pace != null && pcMax > pcMin ? hexLerp(C.sage, C.slate, (l.pace - pcMin) / (pcMax - pcMin)) : C.blue }))
  const xMin = Math.min(...br), xMax = Math.max(...br), yMin = Math.min(...dp), yMax = Math.max(...dp)
  const pctEfic = Math.round(base.filter(l => l.paladas <= mBr && l.dps >= mDp).length / base.length * 100)
  return <Glass>
    <HeadG eyebrow="Natación · Eficiencia" titulo="Frecuencia × Amplitud" subtitulo="Cada punto es un largo real (color: verde = más rápido). Ideal arriba-izquierda: pocas brazadas que avanzan mucho." />
    <ResponsiveContainer width="100%" height={340}>
      <ScatterChart margin={{ top: 16, right: 34, left: 26, bottom: 30 }}>
        <ReferenceArea x1={xMin - 1} y1={mDp} x2={mBr} y2={yMax + 0.1} fill={C.sage} fillOpacity={0.14} label={{ value: 'Eficiente', position: 'insideTopLeft', fill: C.sage, fontSize: 13.5, fontWeight: 700 }} />
        <ReferenceArea x1={mBr} y1={yMin - 0.1} x2={xMax + 1} y2={mDp} fill={C.amber} fillOpacity={0.10} label={{ value: 'Muchas brazadas, poco avance', position: 'insideBottomRight', fill: C.amber, fontSize: 12.5, fontWeight: 700 }} />
        <CartesianGrid stroke="rgba(255,255,255,0.05)" />
        <XAxis type="number" dataKey="paladas" name="Brazadas/largo" domain={[xMin - 1, xMax + 1]} tick={{ fill: C.dim, fontSize: 14 }} tickMargin={8} label={{ value: 'Brazadas por largo', position: 'bottom', fill: C.ink, fontSize: 15, offset: 8 }} />
        <YAxis type="number" dataKey="dps" name="Dist/brazada" domain={[yMin - 0.1, yMax + 0.1]} tick={{ fill: C.dim, fontSize: 14 }} width={46} tickFormatter={v => v.toFixed(2)} label={{ value: 'Dist/brazada (m)', angle: -90, position: 'left', fill: C.ink, fontSize: 15, dx: 6 }} />
        <ZAxis range={[60, 60]} />
        <ReferenceLine x={mBr} stroke={C.dim} strokeDasharray="5 5" /><ReferenceLine y={mDp} stroke={C.dim} strokeDasharray="5 5" />
        <Tooltip cursor={{ stroke: C.dim }} contentStyle={tip} />
        <Scatter data={pts} isAnimationActive={false}>{pts.map((p, i) => <Cell key={i} fill={p._c} fillOpacity={0.6} />)}</Scatter>
      </ScatterChart>
    </ResponsiveContainer>
    <div style={{ fontSize: 12.5, color: C.dim, marginTop: 4 }}>Líneas punteadas = tu mediana de brazadas ({mBr}) y de distancia por brazada ({mDp} m).</div>
    <Conclusion
      que={`El ${pctEfic}% de tus largos cae en la zona eficiente (≤ ${mBr} brazadas con ≥ ${mDp} m por brazada).`}
      relacion="Menos brazadas que avanzan más = mejor agarre y deslizamiento. Acelerar subiendo la frecuencia sin ganar distancia por brazada suele empeorar la eficiencia."
      mejorar={pctEfic >= 55 ? 'Buen deslizamiento: sostené la distancia por brazada cuando subís el ritmo.' : 'Trabajá agarre y empuje para ganar distancia por brazada sin acelerar la frecuencia.'} />
  </Glass>
}


export default function SeccionTecnica({ atletaId }) {
  const [sport, setSport] = useState('running')
  const [sesionId, setSesionId] = useState(null)
  const [agg, setAgg] = useState(null)
  const [lab, setLab] = useState(null)
  const [loading, setLoading] = useState(false)
  const [evolSel, setEvolSel] = useState(0)

  useEffect(() => { if (atletaId) { setSesionId(null); setEvolSel(0) } }, [atletaId, sport])
  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    const qs = sesionId ? `&sesion_id=${sesionId}` : ''
    Promise.all([
      authFetch(`${API}/atletas/${atletaId}/tecnica?sport=${sport}&semanas=1040${qs}`).then(r => r.json()).catch(() => null),
      authFetch(`${API}/atletas/${atletaId}/tecnica_lab?sport=${sport}${qs}`).then(r => r.json()).catch(() => null),
    ]).then(([a, l]) => { setAgg(a?.data || a); setLab(l?.data || l); setLoading(false) })
  }, [atletaId, sport, sesionId])

  const d = agg || {}
  const L = lab || {}
  const filas = useMemo(() => L.series ? construirFilas(L.series) : [], [L.series])
  const disp = L.disponibles || {}
  const hayLab = filas.length > 5

  const metricas = d.metricas || {}
  const interp = d.interpretacion || []
  const recs = (d.recomendaciones || []).filter(r => typeof r === 'string' && !/dentro del patrón|habitual|manten[ée] el patrón|sin cambios/i.test(r))
  const score = typeof d.score_tecnico === 'number' ? d.score_tecnico : null
  const colScore = score == null ? C.dim : score >= 60 ? C.cian : C.violet
  const lblScore = score == null ? '' : score >= 80 ? 'Técnica muy sólida' : score >= 60 ? 'Técnica estable' : score >= 45 ? 'Hay margen de mejora' : 'Prioridad de trabajo'
  const clavesMetricas = (METRICAS_SPORT[sport] || []).filter(k => metricas[k] && META[k])
  const estilos = d.estilos && typeof d.estilos === 'object' ? Object.entries(d.estilos) : []
  const esNado = sport === 'swimming'
  const hayDatos = clavesMetricas.length > 0 || interp.length > 0 || hayLab || estilos.length > 0

  const aEconomia = useMemo(() => (hayLab && sport === 'running') ? genEconomia(filas) : null, [filas, hayLab, sport])
  const aApoyo = useMemo(() => (hayLab && sport === 'running') ? genApoyo(filas) : null, [filas, hayLab, sport])
  const aPotencia = useMemo(() => (hayLab && sport === 'cycling') ? genPotencia(filas) : null, [filas, hayLab, sport])
  const aPedaleo = useMemo(() => (hayLab && sport === 'cycling') ? genPedaleo(filas) : null, [filas, hayLab, sport])
  const aCambios = useMemo(() => (hayLab && !esNado) ? genCambios(filas, sport) : null, [filas, hayLab, sport, esNado])
  const semanal = Semanal({ spark: d.sparkline, sport, sel: evolSel, setSel: setEvolSel })

  const panelsApoyo = [
    { key: 'gct', label: 'Tiempo de contacto', unit: 'ms', color: C.cian },
    { key: 'cadence', label: 'Cadencia', unit: 'spm', color: C.violet },
    { key: 'stride', label: 'Longitud de zancada', unit: 'm', color: C.cLit },
  ].filter(p => disp[p.key])
  const panelsPedaleo = [
    { key: 'lr', label: 'Balance izquierda/derecha', unit: '% izq', color: C.cian, center50: true },
    { key: 'torque', label: 'Torque efectivo', unit: '%', color: C.violet },
    { key: 'pedal', label: 'Suavidad de pedaleo', unit: '%', color: C.cLit },
  ].filter(p => disp[p.key])
  // paneles UNIVERSALES (funcionan con solo pulso/cadencia/GPS)
  const panelsRunTS = [
    disp.vo && { key: 'vo', label: 'Oscilación vertical', unit: 'cm', color: C.sage },
    disp.speed_ms && { key: 'pace', label: 'Ritmo', unit: '/km', color: C.blue, pace: true },
    disp.hr && { key: 'hr', label: 'Frecuencia cardíaca', unit: 'bpm', color: C.amber },
    disp.cadence && { key: 'cadence', label: 'Cadencia', unit: 'spm', color: C.sage },
  ].filter(Boolean)
  const panelsBikeTS = [
    disp.power && { key: 'power', label: 'Potencia', unit: 'W', color: C.blue },
    disp.speed_ms && { key: 'kmh', label: 'Velocidad', unit: 'km/h', color: C.sage },
    disp.hr && { key: 'hr', label: 'Frecuencia cardíaca', unit: 'bpm', color: C.amber },
    disp.cadence && { key: 'cadence', label: 'Cadencia', unit: 'rpm', color: C.sage },
  ].filter(Boolean)

  return (
    <div style={{ position: 'relative', maxWidth: 680, margin: '0 auto', width: '100%', overflowX: 'hidden', fontFamily: 'Inter, system-ui, sans-serif', color: C.ink }}>
      <style>{`
        .noah-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));gap:12px}
        .noah-exp:hover{opacity:.85}
        @media (prefers-reduced-motion: reduce){*{animation:none!important;transition:none!important}}
      `}</style>
      <div style={{ position: 'absolute', top: -30, left: -60, width: 260, height: 260, borderRadius: '50%', background: `radial-gradient(circle, ${C.violet}14, transparent 70%)`, filter: 'blur(10px)', pointerEvents: 'none', zIndex: 0 }} />
      <div style={{ position: 'absolute', top: 220, right: -80, width: 260, height: 260, borderRadius: '50%', background: `radial-gradient(circle, ${C.cian}12, transparent 70%)`, filter: 'blur(10px)', pointerEvents: 'none', zIndex: 0 }} />

      <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', gap: 18 }}>
        <div style={{ ...glass, padding: 5, display: 'flex', gap: 4, borderRadius: 16 }}>
          {[['running', 'Running'], ['cycling', 'Ciclismo'], ['swimming', 'Natación']].map(([id, lb]) => {
            const on = sport === id
            return <button key={id} onClick={() => setSport(id)} style={{ flex: 1, padding: '11px 0', borderRadius: 12, cursor: 'pointer', fontSize: 13, fontWeight: 700, border: 'none', background: on ? `linear-gradient(135deg, ${C.violet}2E, ${C.cian}24)` : 'transparent', color: on ? C.ink : C.dim, boxShadow: on ? `inset 0 0 0 1px ${C.border}` : 'none' }}>{lb}</button>
          })}
        </div>

        {!esNado && L.sesiones && L.sesiones.length > 1 && (
          <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 2 }}>
            {L.sesiones.map(s => { const on = s.id === L.sesion_id; return <button key={s.id} onClick={() => setSesionId(s.id)} style={{ flex: '0 0 auto', padding: '8px 13px', borderRadius: 10, cursor: 'pointer', fontSize: 12, fontWeight: 700, border: `1px solid ${on ? C.cian : C.border}`, background: on ? `${C.cian}1F` : 'rgba(22,29,46,0.4)', color: on ? C.cian : C.dim }}>{String(s.fecha).slice(5, 10)}</button> })}
          </div>
        )}

        {loading && <div style={{ textAlign: 'center', color: C.dim, padding: 56 }}>Cargando análisis…</div>}

        {!loading && !hayDatos && (
          <Glass style={{ textAlign: 'center', color: C.dim, padding: 30 }}>
            Todavía no hay datos de técnica para {esNado ? 'natación' : sport === 'cycling' ? 'ciclismo' : 'running'}.<br />Aparece cuando sincronices una actividad con los sensores correspondientes.
          </Glass>
        )}

        {!loading && hayDatos && <>
          {score != null && (
            <Glass style={{ position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', gap: 18 }}>
              <div style={{ position: 'absolute', inset: 0, background: `radial-gradient(120% 120% at 0% 0%, ${colScore}14, transparent 55%)`, pointerEvents: 'none' }} />
              <div style={{ position: 'relative', width: 72, height: 72, borderRadius: '50%', flex: '0 0 auto', background: `conic-gradient(${colScore} ${score * 3.6}deg, rgba(255,255,255,0.06) 0)`, display: 'grid', placeItems: 'center', boxShadow: `0 0 24px -6px ${colScore}66` }}>
                <div style={{ width: 56, height: 56, borderRadius: '50%', background: '#0D1324', display: 'grid', placeItems: 'center', fontSize: 22, fontWeight: 800, color: C.ink, ...num }}>{score}</div>
              </div>
              <div style={{ position: 'relative' }}>
                <div style={{ fontSize: 11, color: C.aux, fontWeight: 700, letterSpacing: 0.8, textTransform: 'uppercase' }}>Índice técnico</div>
                <div style={{ fontSize: 19, fontWeight: 700, color: C.ink, marginTop: 2 }}>{lblScore}</div>
              </div>
            </Glass>
          )}

          {(hayLab || (esNado && d.curva_sesion)) && (
            <div>
              <TituloSeccion>Qué vemos en tu técnica</TituloSeccion>
              <div style={{ marginTop: 10 }}>
                <SignalStrip sport={sport} filas={filas} d={d} />
                {interp.length > 0 && !esNado && <div style={{ marginTop: 12 }}><Glass style={{ padding: 14 }}><Expander label="Leer la lectura de NOAH">
                  {interp.map((t, i) => <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '6px 0', borderTop: i ? `1px solid ${C.border}` : 'none' }}><span style={{ width: 6, height: 6, borderRadius: 9, background: C.sage, marginTop: 8, flex: '0 0 auto' }} /><span style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.55 }}>{t}</span></div>)}
                </Expander></Glass></div>}
              </div>
            </div>
          )}

          {/* ───────── NATACIÓN (datos por largo) ───────── */}
          {esNado && <>
            {estilos.length > 0 && (
              <div>
                <TituloSeccion>Tus estilos</TituloSeccion>
                <div style={{ fontSize: 12, color: C.aux, margin: '2px 2px 10px', lineHeight: 1.5 }}>La natación se mide por largo (vuelta), no segundo a segundo. Estas son tus medias reales por estilo.</div>
                <div className="noah-grid">{estilos.filter(([, e]) => e && e.n_largos >= 3).map(([nombre, e]) => <TarjetaEstilo key={nombre} nombre={nombre} e={e} />)}</div>
              </div>
            )}
            {estilos.length > 1 && <SwimDistribucion estilos={estilos} />}
            {d.curva_sesion && Array.isArray(d.curva_sesion.largos) && d.curva_sesion.largos.length >= 6 && (
              <div>
                <TituloSeccion>Análisis · Frecuencia vs amplitud</TituloSeccion>
                <div style={{ marginTop: 10 }}><SwimFreqAmplitud largos={d.curva_sesion.largos} /></div>
              </div>
            )}
            {interp.length > 0 && (
              <div>
                <TituloSeccion>Análisis · Relaciones técnicas</TituloSeccion>
                <div style={{ marginTop: 10 }}><RelacionesPanel interp={interp} /></div>
              </div>
            )}
            {d.curva_sesion && Array.isArray(d.curva_sesion.largos) && d.curva_sesion.largos.length >= 6 && (
              <div>
                <TituloSeccion>Análisis · Fatiga en la sesión</TituloSeccion>
                <div style={{ marginTop: 10 }}><FatigaPanel largos={d.curva_sesion.largos} /></div>
              </div>
            )}
            <div>
              <TituloSeccion>Análisis · Evolución</TituloSeccion>
              <div style={{ marginTop: 10 }}>{semanal.node
                ? <Analisis eyebrow="Evolución histórica" titulo="¿Estás nadando más eficiente?" subtitulo="SWOLF y brazadas por largo, mes a mes (toda tu historia)." interp={semanal.interp}>{semanal.node}</Analisis>
                : <Glass style={{ textAlign: 'center', color: C.dim }}><div style={{ fontSize: 13.5, lineHeight: 1.5 }}>Necesitás registros en al menos 2 meses distintos para ver la tendencia.</div></Glass>}
                <ComparativaBox d={d} /></div>
            </div>
          </>}

          {/* ───────── RUNNING / CICLISMO ───────── */}
          {!esNado && <>
            {clavesMetricas.length > 0 && (
              <div>
                <TituloSeccion>Estado técnico · semáforo</TituloSeccion>
                <div style={{ marginTop: 10 }}><SemaforoRow sport={sport} metricas={metricas} filas={filas} /></div>
              </div>
            )}

            {clavesMetricas.length > 0 && (
              <div>
                <TituloSeccion>Tus métricas</TituloSeccion>
                <div className="noah-grid" style={{ marginTop: 10 }}>
                  {clavesMetricas.map(k => <TarjetaMetrica key={k} k={k} m={metricas[k]} sport={sport} />)}
                </div>
              </div>
            )}

            {hayLab && relsDe(filas, sport).length > 0 && (
              <div>
                <TituloSeccion>Relaciones entre tus variables</TituloSeccion>
                <div style={{ marginTop: 10 }}><Glass><HeadG eyebrow={`${sport === 'cycling' ? 'Ciclismo' : 'Running'} · Relaciones`} titulo="¿Qué se mueve junto con qué?" subtitulo="Calculado sobre las muestras reales de la sesión. A la derecha suben juntas; a la izquierda una sube y la otra baja." /><CorrBars rels={relsDe(filas, sport)} /></Glass></div>
              </div>
            )}

            {/* ANÁLISIS 1 — serie temporal (siempre, con lo que haya) */}
            {hayLab && (sport === 'running' ? panelsRunTS.length >= 2 : panelsBikeTS.length >= 2) && (
              <div>
                <TituloSeccion>{sport === 'cycling' ? (disp.power ? 'Análisis · Entrega de potencia' : 'Análisis · Velocidad, FC y cadencia') : (disp.vo ? 'Análisis · Economía del movimiento' : 'Análisis · Ritmo, FC y cadencia')}</TituloSeccion>
                <div style={{ marginTop: 10 }}>
                  {sport === 'running'
                    ? <Analisis eyebrow={disp.vo ? 'Economía del movimiento' : 'Cómo te movés'} titulo="¿Qué pasa cuando cambia el ritmo?" subtitulo="Ritmo, FC y cadencia en el tiempo (misma sesión)." interp={aEconomia}><MultiSerie filas={filas} panels={panelsRunTS} /></Analisis>
                    : <Analisis eyebrow={disp.power ? 'Entrega de potencia' : 'Cómo rodás'} titulo="¿Cómo sostenés el esfuerzo?" subtitulo="Velocidad/potencia, FC y cadencia en el tiempo." interp={aPotencia}><MultiSerie filas={filas} panels={panelsBikeTS} /></Analisis>}
                </div>
              </div>
            )}

            {/* ANÁLISIS 2 — mecánica/pedaleo: SOLO si hay sensores de dinámica (sin cartel) */}
            {sport === 'running' && panelsApoyo.length >= 2 && aApoyo && (
              <div>
                <TituloSeccion>Análisis · Mecánica del apoyo</TituloSeccion>
                <div style={{ marginTop: 10 }}><Analisis eyebrow="Mecánica del apoyo" titulo="¿Cómo organizás cada apoyo?" subtitulo="Contacto, cadencia y zancada en el tiempo." interp={aApoyo}><MultiSerie filas={filas} panels={panelsApoyo} /></Analisis></div>
              </div>
            )}
            {sport === 'cycling' && panelsPedaleo.length >= 1 && aPedaleo && (
              <div>
                <TituloSeccion>Análisis · Simetría y pedaleo</TituloSeccion>
                <div style={{ marginTop: 10 }}><Analisis eyebrow="Simetría y pedaleo" titulo="¿Cómo pedaleás y qué tan parejo?" subtitulo="Balance izquierda/derecha (50/50 ideal) y torque efectivo en el tiempo." interp={aPedaleo}><MultiSerie filas={filas} panels={panelsPedaleo} /></Analisis></div>
              </div>
            )}
            {sport === 'cycling' && hayLab && (disp.torque || disp.lr) && (
              <div>
                <TituloSeccion>Pedaleo · modelo</TituloSeccion>
                <div style={{ marginTop: 10 }}><PedalClock filas={filas} /></div>
              </div>
            )}

            {/* ANÁLISIS 3 — mapa: biomecánico si hay sensores, universal si no (siempre se ve) */}
            {hayLab && (
              <div>
                <TituloSeccion>Análisis · Mapa</TituloSeccion>
                <div style={{ marginTop: 10 }}>
                  {sport === 'running'
                    ? (disp.stride ? <FlagRunning filas={filas} /> : <FlagMapaCV filas={filas} sport="running" />)
                    : (disp.cadence && disp.power ? <FlagCycling filas={filas} />
                      : disp.power && disp.speed_ms ? <FlagPotVel filas={filas} />
                        : <FlagMapaCV filas={filas} sport="cycling" />)}
                </div>
              </div>
            )}

            {/* ANÁLISIS 4 */}
            <div>
              <TituloSeccion>Análisis 4 · Cambios durante la sesión</TituloSeccion>
              <div style={{ marginTop: 10 }}>{hayLab && aCambios && aCambios.metricas.length
                ? <Analisis eyebrow="Cambios durante la sesión" titulo="¿Tu técnica se mantiene o se deteriora?" subtitulo="Inicio, mitad y final de la misma sesión." interp={aCambios.interp}><Cambios T={aCambios.T} metricas={aCambios.metricas} /></Analisis>
                : <SensorFalta sensor="una sesión con suficientes datos muestra-a-muestra" />}</div>
            </div>

            {/* ANÁLISIS 5 */}
            <div>
              <TituloSeccion>Análisis 5 · Evolución histórica</TituloSeccion>
              <div style={{ marginTop: 10 }}>{semanal.node
                ? <Analisis eyebrow="Evolución histórica" titulo="¿Estás mejorando con el entrenamiento?" subtitulo="Promedio por mes, toda tu historia." interp={semanal.interp}>{semanal.node}</Analisis>
                : <Glass style={{ textAlign: 'center', color: C.dim }}><div style={{ fontSize: 13.5, lineHeight: 1.5 }}>Necesitás registros en al menos 2 meses distintos para ver la tendencia.</div></Glass>}
                <ComparativaBox d={d} /></div>
            </div>
          </>}

          {recs.length > 0 && (
            <div>
              <TituloSeccion>Qué trabajar ahora</TituloSeccion>
              <Glass style={{ marginTop: 10, background: `linear-gradient(160deg, ${C.violet}10, rgba(22,29,46,0.48))` }}>
                {recs.map((t, i) => <div key={i} style={{ display: 'flex', gap: 11, alignItems: 'flex-start', padding: '8px 0', borderTop: i ? `1px solid ${C.border}` : 'none' }}><span style={{ color: C.violet, fontWeight: 800, fontSize: 14, lineHeight: 1.5 }}>→</span><span style={{ fontSize: 13.5, color: C.ink, lineHeight: 1.55 }}>{t}</span></div>)}
              </Glass>
            </div>
          )}
        </>}
      </div>
    </div>
  )
}
