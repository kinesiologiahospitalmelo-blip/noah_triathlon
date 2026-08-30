// SeccionTecnica.jsx — Análisis biomecánico profesional
// Spider chart, sparklines, drift multidimensional, sensor detection, recomendaciones priorizadas
import { useState, useEffect } from 'react'
import { RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
         LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
         PieChart, Pie, Cell, CartesianGrid, ComposedChart,
         ScatterChart, Scatter, ZAxis, Legend, ReferenceLine } from 'recharts'

const API = window.location.hostname === 'localhost' ? 'http://localhost:5000/api' : '/api'

function authFetch(url, options = {}) {
  let token = null
  try { token = JSON.parse(localStorage.getItem('noah_sesion'))?.token } catch {}
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers })
}

const C = {
  purple: '#A78BFA', green: '#10B981', blue: '#3B82F6', cyan: '#06B6D4',
  red: '#EF4444', yellow: '#F59E0B', dim: 'rgba(255,255,255,0.4)',
  bg: 'rgba(255,255,255,0.03)', border: 'rgba(255,255,255,0.06)',
}

const PRIORIDAD_COLOR = { alta: C.red, media: C.yellow, baja: C.green }
const PRIORIDAD_LABEL = { alta: '● ALTA', media: '● MEDIA', baja: '● BAJA' }

// ═══════════════════════════════════════════════════════════════
// COMPONENTES
// ═══════════════════════════════════════════════════════════════

function MetricaOverlay({ label, valor, unidad, estado, x, y }) {
  const color = estado === 'óptima' || estado === 'bueno' || estado === 'equilibrado' || estado === 'elite' ? C.green
    : estado === 'mejorar' || estado === 'significativo' ? C.red
    : estado === 'baja' || estado === 'leve' || estado === 'alta' ? C.yellow : C.purple
  return (
    <div style={{
      position: 'absolute', left: `${x}%`, top: `${y}%`, transform: 'translate(-50%,-50%)',
      textAlign: 'center', zIndex: 2,
    }}>
      <div style={{
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(8px)',
        borderRadius: 12, padding: '8px 14px', border: `1px solid ${color}40`,
      }}>
        <div style={{ fontSize: 9, color: C.dim, fontWeight: 600, letterSpacing: 1 }}>{label}</div>
        <div style={{ fontSize: 22, fontWeight: 800, color }}>{valor}<span style={{ fontSize: 11, color: C.dim }}> {unidad}</span></div>
        <div style={{ fontSize: 8, color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>{estado}</div>
      </div>
    </div>
  )
}

function SpiderChart({ data }) {
  if (!data || Object.keys(data).length === 0) return null
  const labels = {
    cadencia: 'Cadencia', gct: 'GCT', oscilacion: 'Oscilación',
    economia: 'Economía', estabilidad: 'Estabilidad',
    balance: 'Balance', pedaleo: 'Pedaleo',
  }
  const chartData = Object.entries(data)
    .filter(([_, v]) => v !== null)
    .map(([key, val]) => ({ metric: labels[key] || key, value: val, fullMark: 100 }))

  if (chartData.length < 2) return null

  return (
    <div style={{ margin: '16px auto', textAlign: 'center' }}>
      <div style={{ fontSize: 10, color: C.cyan, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
        PERFIL BIOMECÁNICO
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius={80}>
          <PolarGrid stroke="rgba(255,255,255,0.08)" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: C.dim, fontSize: 9 }} />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          <Radar dataKey="value" stroke={C.cyan} fill={C.cyan} fillOpacity={0.15} strokeWidth={2} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

function DriftCard({ drift }) {
  if (!drift || Object.keys(drift).length === 0) return null
  const labels = {
    cadencia: 'Cadencia', gct: 'GCT', vertical_osc: 'Osc. Vert.', stride: 'Stride',
    torque_effectiveness: 'Torque Eff.',
  }
  const entries = Object.entries(drift).filter(([_, v]) => v !== undefined && v !== null)
  if (entries.length === 0) return null

  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 10, color: C.purple, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
        DRIFT POR FATIGA (inicio → final)
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {entries.map(([key, val]) => {
          const abs_val = Math.abs(val)
          const color = abs_val < 3 ? C.green : abs_val < 5 ? C.yellow : C.red
          const arrow = val > 0.5 ? '↑' : val < -0.5 ? '↓' : '→'
          return (
            <div key={key} style={{
              flex: '1 1 45%', padding: '10px 12px', borderRadius: 10,
              background: C.bg, border: `1px solid ${C.border}`,
            }}>
              <div style={{ fontSize: 9, color: C.dim, fontWeight: 600, marginBottom: 2 }}>
                {labels[key] || key}
              </div>
              <div style={{ fontSize: 18, fontWeight: 800, color }}>
                {arrow} {val > 0 ? '+' : ''}{val}%
              </div>
              <div style={{ fontSize: 8, color: C.dim }}>
                {abs_val < 3 ? 'Estable' : abs_val < 5 ? 'Leve fatiga' : 'Fatiga significativa'}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Sparklines({ data, cadUnidad = 'spm', linea2Key = 'gct', linea2Nombre = 'GCT (ms)' }) {
  if (!data || data.length < 1) return null
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 10, color: C.blue, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
        EVOLUCIÓN ÚLTIMAS SEMANAS
      </div>
      <ResponsiveContainer width="100%" height={100}>
        <LineChart data={data}>
          <XAxis dataKey="semana" tick={{ fill: C.dim, fontSize: 8 }}
                 tickFormatter={v => v ? v.slice(5) : ''} />
          <YAxis hide domain={['auto', 'auto']} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 10 }}
                   labelStyle={{ color: C.dim }} />
          <Line type="monotone" dataKey="cadencia" stroke={C.purple} strokeWidth={2}
                dot={false} name={`Cadencia (${cadUnidad})`} />
          {data.some(d => d[linea2Key]) && (
            <Line type="monotone" dataKey={linea2Key} stroke={C.cyan} strokeWidth={2}
                  dot={false} name={linea2Nombre} />
          )}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function SensorNotice({ sensores }) {
  if (!sensores || !sensores.faltantes || sensores.faltantes.length === 0) return null
  return (
    <div style={{
      padding: '12px 16px', borderRadius: 12, marginTop: 16,
      background: 'rgba(59,130,246,0.06)', border: `1px solid rgba(59,130,246,0.15)`,
    }}>
      <div style={{ fontSize: 10, color: C.blue, fontWeight: 700, marginBottom: 6, letterSpacing: 1 }}>
        ⓘ MÉTRICAS NO DISPONIBLES
      </div>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', lineHeight: 1.6 }}>
        <strong>{sensores.faltantes.join(', ')}</strong> requieren{' '}
        <span style={{ color: C.blue, fontWeight: 600 }}>{sensores.sensor_recomendado || 'sensor compatible'}</span>.
        Con estos datos se completa el perfil biomecánico, el índice de economía y el drift multidimensional.
      </div>
      {sensores.sensores.length > 0 && (
        <div style={{ fontSize: 9, color: C.dim, marginTop: 6 }}>
          Sensores activos: {sensores.sensores.join(', ')}
        </div>
      )}
    </div>
  )
}

function Comparacion({ data }) {
  if (!data || Object.keys(data).length === 0) return null
  const labels = { cadencia: 'Cadencia', gct: 'GCT', vo: 'Osc. Vert.', torque_effectiveness: 'Torque Eff.' }
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 10, color: C.green, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>
        VS PERÍODO ANTERIOR
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {Object.entries(data).map(([key, val]) => {
          const mejor = (key === 'cadencia' && val.direccion === 'up') || (key === 'gct' && val.direccion === 'down') ||
            (key === 'torque_effectiveness' && val.direccion === 'up')
          const color = mejor ? C.green : val.direccion === 'equal' ? C.dim : C.yellow
          const arrow = val.direccion === 'up' ? '↑' : val.direccion === 'down' ? '↓' : '→'
          return (
            <div key={key} style={{
              flex: 1, textAlign: 'center', padding: '8px 0', borderRadius: 10,
              background: C.bg, border: `1px solid ${C.border}`,
            }}>
              <div style={{ fontSize: 9, color: C.dim, fontWeight: 600 }}>{labels[key] || key}</div>
              <div style={{ fontSize: 16, fontWeight: 800, color }}>
                {arrow} {val.diff > 0 ? '+' : ''}{val.diff}
              </div>
              <div style={{ fontSize: 8, color: C.dim }}>{val.anterior} → {val.actual}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CadenciaZonas({ data, tipo }) {
  if (!data || Object.keys(data).length === 0) return null
  const label = tipo === 'cycling' ? 'CADENCIA POR ZONA DE POTENCIA' : 'CADENCIA POR ZONA DE INTENSIDAD'
  const sorted = Object.entries(data).sort((a, b) => a[0].localeCompare(b[0]))
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 10, color: C.dim, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>{label}</div>
      <div style={{ display: 'flex', gap: 6 }}>
        {sorted.map(([z, v]) => (
          <div key={z} style={{
            flex: 1, textAlign: 'center', padding: '10px 0', borderRadius: 10,
            background: C.bg, border: `1px solid ${C.border}`,
          }}>
            <div style={{ fontSize: 10, color: C.blue, fontWeight: 700 }}>{z}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: C.purple }}>{v}</div>
            <div style={{ fontSize: 8, color: C.dim }}>{tipo === 'cycling' ? 'rpm' : 'spm'}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Recomendaciones({ recs }) {
  if (!recs || recs.length === 0) return null
  // Ordenar por prioridad
  const orden = { alta: 0, media: 1, baja: 2 }
  const sorted = [...recs].sort((a, b) =>
    (typeof a === 'object' ? orden[a.prioridad] || 2 : 2) - (typeof b === 'object' ? orden[b.prioridad] || 2 : 2))

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 10, color: C.yellow, fontWeight: 700, letterSpacing: 1, marginBottom: 10 }}>
        NOAH DETECTÓ
      </div>
      {sorted.map((rec, i) => {
        if (typeof rec === 'string') {
          return (
            <p key={i} style={{
              fontSize: 12, color: 'rgba(255,255,255,0.7)', lineHeight: 1.8,
              margin: '0 0 10px 0',
            }}>{rec}</p>
          )
        }
        const pColor = PRIORIDAD_COLOR[rec.prioridad] || C.yellow
        return (
          <div key={i} style={{
            padding: '14px 16px', borderRadius: 12, marginBottom: 8,
            background: `${pColor}08`, border: `1px solid ${pColor}20`,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: 'rgba(255,255,255,0.85)' }}>{rec.texto}</span>
              <span style={{ fontSize: 8, fontWeight: 700, color: pColor, letterSpacing: 1 }}>
                {PRIORIDAD_LABEL[rec.prioridad]}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', lineHeight: 1.6 }}>
              <strong style={{ color: C.cyan }}>Ejercicio:</strong> {rec.ejercicio}
            </div>
            <div style={{ display: 'flex', gap: 16, marginTop: 6 }}>
              <span style={{ fontSize: 9, color: C.dim }}>
                <strong style={{ color: C.purple }}>Frecuencia:</strong> {rec.frecuencia}
              </span>
              <span style={{ fontSize: 9, color: C.dim }}>
                <strong style={{ color: C.green }}>Esperado:</strong> {rec.resultado_esperado}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function Interpretacion({ items }) {
  if (!items || items.length === 0) return null
  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700, letterSpacing: 1, marginBottom: 12 }}>
        LECTURA BIOMECÁNICA
      </div>
      {items.map((text, i) => (
        <p key={i} style={{
          fontSize: 12, color: 'rgba(255,255,255,0.7)', lineHeight: 1.8,
          margin: '0 0 10px 0',
        }}>{text}</p>
      ))}
    </div>
  )
}


// ── Score Donut SVG ──
function ScoreDonut({ score }) {
  if (!score) return null
  const color = score >= 80 ? C.green : score >= 60 ? C.yellow : C.red
  const label = score >= 80 ? 'Muy bueno' : score >= 60 ? 'Aceptable' : 'Mejorar'
  const circ = 2 * Math.PI * 38
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 9, color: C.dim, fontWeight: 700, letterSpacing: 1, marginBottom: 4 }}>SCORE TÉCNICO</div>
      <svg width="100" height="100" viewBox="0 0 100 100" style={{ display: 'block', margin: '0 auto' }}>
        <circle cx="50" cy="50" r="38" fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="5" />
        <circle cx="50" cy="50" r="38" fill="none" stroke={color} strokeWidth="5"
          strokeDasharray={circ} strokeDashoffset={circ - (score / 100) * circ}
          strokeLinecap="round" transform="rotate(-90 50 50)" />
        <text x="50" y="46" textAnchor="middle" fill="rgba(255,255,255,0.85)" fontSize="22" fontWeight="800">{score}</text>
        <text x="50" y="58" textAnchor="middle" fill={C.dim} fontSize="8">/100</text>
        <text x="50" y="74" textAnchor="middle" fill={color} fontSize="9" fontWeight="600">{label}</text>
      </svg>
    </div>
  )
}

// ── Donut Estado Sesiones ──
function DonutEstado({ estado }) {
  if (!estado || (!estado.eficiente && !estado.compensada && !estado.degradada)) return null
  const data = [
    { name: 'Eficiente', value: estado.eficiente || 0, color: C.green },
    { name: 'Compensada', value: estado.compensada || 0, color: C.yellow },
    { name: 'Degradada', value: estado.degradada || 0, color: C.red },
  ].filter(d => d.value > 0)
  return (
    <div style={{ marginTop: 20, textAlign: 'center' }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 8 }}>ESTADO DE SESIONES</div>
      <ResponsiveContainer width="100%" height={140}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%" innerRadius={35} outerRadius={55} dataKey="value" stroke="none">
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', justifyContent: 'center', gap: 16, marginTop: 4 }}>
        {data.map(d => (
          <span key={d.name} style={{ fontSize: 10, color: d.color, fontWeight: 600 }}>{d.value}% {d.name}</span>
        ))}
      </div>
    </div>
  )
}

// ── Gráfico Eficiencia Temporal ──
function GraficoEficiencia({ data }) {
  if (!data || data.length < 1) return null
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 10 }}>EFICIENCIA BIOMECÁNICA</div>
      <ResponsiveContainer width="100%" height={150}>
        <LineChart data={data}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="fecha" tick={{ fill: C.dim, fontSize: 8 }} tickFormatter={v => v ? v.slice(5) : ''} />
          <YAxis domain={[20, 100]} tick={{ fill: C.dim, fontSize: 8 }} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 8, fontSize: 10 }} />
          <Line type="monotone" dataKey="score" stroke={C.purple} strokeWidth={2} dot={{ r: 3, fill: C.purple }} name="Eficiencia" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// ANÁLISIS / PLAN DE MEJORA — 3 visualizaciones reales
// (reemplaza tarjetas de texto por gráficos sobre datos existentes)
// ═══════════════════════════════════════════════════════════════

function pearson(xs, ys) {
  const n = xs.length
  if (n < 3) return null
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  let cov = 0, vx = 0, vy = 0
  for (let i = 0; i < n; i++) {
    cov += (xs[i] - mx) * (ys[i] - my)
    vx += (xs[i] - mx) ** 2
    vy += (ys[i] - my) ** 2
  }
  if (vx === 0 || vy === 0) return 0
  return +(cov / Math.sqrt(vx * vy)).toFixed(2)
}

// ── 1) CURVA: Eficiencia vs Fatiga ──
function CurvaEficienciaFatiga({ serie, correlacion }) {
  if (!serie || serie.length === 0) return null
  const r = correlacion !== null && correlacion !== undefined
    ? correlacion
    : pearson(serie.map(s => s.fatiga), serie.map(s => s.eficiencia))

  const fuerza = r === null ? null
    : Math.abs(r) >= 0.6 ? 'FUERTE' : Math.abs(r) >= 0.3 ? 'MODERADA' : 'DÉBIL'
  const rColor = r === null ? C.dim : r <= -0.3 ? C.red : r >= 0.3 ? C.green : C.yellow

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 8 }}>
        EFICIENCIA VS FATIGA
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ComposedChart data={serie} margin={{ top: 4, right: 4, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" />
          <XAxis dataKey="fecha" tick={{ fill: C.dim, fontSize: 8 }} tickFormatter={v => v ? v.slice(5) : ''} />
          <YAxis yAxisId="left" domain={[0, 100]} tick={{ fill: C.purple, fontSize: 8 }} />
          <YAxis yAxisId="right" orientation="right" domain={['auto', 'auto']} tick={{ fill: C.red, fontSize: 8 }} />
          <ReferenceLine yAxisId="left" y={80} stroke={C.green} strokeDasharray="3 3" strokeOpacity={0.5}
                          label={{ value: 'ÓPTIMO', position: 'insideTopRight', fill: C.green, fontSize: 8 }} />
          <ReferenceLine yAxisId="left" y={60} stroke="#3B82F6" strokeDasharray="3 3" strokeOpacity={0.5}
                          label={{ value: 'ESTABLE', position: 'insideTopRight', fill: '#3B82F6', fontSize: 8 }} />
          <ReferenceLine yAxisId="left" y={40} stroke={C.yellow} strokeDasharray="3 3" strokeOpacity={0.5}
                          label={{ value: 'ALERTA', position: 'insideTopRight', fill: C.yellow, fontSize: 8 }} />
          <ReferenceLine yAxisId="left" y={20} stroke={C.red} strokeDasharray="3 3" strokeOpacity={0.5}
                          label={{ value: 'RIESGO', position: 'insideTopRight', fill: C.red, fontSize: 8 }} />
          <Tooltip contentStyle={{ background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 10 }} />
          <Line yAxisId="left" type="monotone" dataKey="eficiencia" name="Eficiencia" stroke={C.purple} strokeWidth={2} dot={{ r: 3 }} connectNulls />
          <Line yAxisId="right" type="monotone" dataKey="fatiga" name="Fatiga (ATL)" stroke={C.red} strokeWidth={2} dot={{ r: 3 }} connectNulls />
        </ComposedChart>
      </ResponsiveContainer>
      {r !== null && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 4 }}>
          <span style={{ fontSize: 9, color: C.dim, fontWeight: 700, letterSpacing: 1 }}>CORRELACIÓN DETECTADA</span>
          <span style={{ fontSize: 12, fontWeight: 800, color: rColor }}>r = {r}</span>
          {fuerza && <span style={{ fontSize: 8, color: rColor, fontWeight: 700 }}>({fuerza})</span>}
        </div>
      )}
    </div>
  )
}

// ── 2) HEATMAP: Estabilidad biomecánica por sesión vs baseline propio ──
const ESTADO_COLOR = {
  optimo: C.green, estable: '#3B82F6', alerta: C.yellow, degradado: C.red,
}
const ESTADO_LABEL = { optimo: 'Óptimo', estable: 'Estable', alerta: 'Alerta', degradado: 'Degradado' }

function HeatmapEstabilidad({ heatmap }) {
  if (!heatmap || !heatmap.metricas || heatmap.sesiones.length === 0) return null
  const filas = Object.entries(heatmap.metricas)
  const cols = heatmap.sesiones

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 8 }}>
        ESTABILIDAD BIOMECÁNICA
      </div>
      <div style={{ overflowX: 'auto' }}>
        <div style={{ display: 'grid', gridTemplateColumns: `90px repeat(${cols.length}, minmax(26px, 1fr))`, gap: 3 }}>
          <div />
          {cols.map((f, i) => (
            <div key={i} title={f} style={{ fontSize: 7, color: C.dim, textAlign: 'center' }}>
              S{i + 1}
            </div>
          ))}
          {filas.map(([key, row]) => (
            <FragmentRow key={key} label={row.label} celdas={row.celdas} cols={cols.length} />
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 10, flexWrap: 'wrap' }}>
        {Object.entries(ESTADO_LABEL).map(([k, label]) => (
          <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 9, height: 9, borderRadius: 2, background: ESTADO_COLOR[k] }} />
            <span style={{ fontSize: 8, color: C.dim }}>{label}</span>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <div style={{ width: 9, height: 9, borderRadius: 2, background: 'rgba(255,255,255,0.06)', border: `1px solid ${C.border}` }} />
          <span style={{ fontSize: 8, color: C.dim }}>N/D</span>
        </div>
      </div>
    </div>
  )
}

function FragmentRow({ label, celdas, cols }) {
  return (
    <>
      <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.75)', fontWeight: 600, display: 'flex', alignItems: 'center' }}>
        {label}
      </div>
      {Array.from({ length: cols }).map((_, i) => {
        const c = celdas[i]
        if (!c || c === 'N/D') {
          return (
            <div key={i} title="N/D" style={{
              height: 24, borderRadius: 4, background: 'rgba(255,255,255,0.04)',
              border: `1px dashed ${C.border}`,
            }} />
          )
        }
        const color = ESTADO_COLOR[c.estado] || C.dim
        return (
          <div key={i} title={`${c.valor} — ${ESTADO_LABEL[c.estado] || c.estado}`} style={{
            height: 24, borderRadius: 4, background: `${color}55`, border: `1px solid ${color}`,
          }} />
        )
      })}
    </>
  )
}

// ── 3) SCATTER: Fatiga × Degradación técnica + regresión + clusters ──
const CLUSTER_COLOR = [C.cyan, C.yellow, C.purple]

function ScatterFatigaDegradacion({ scatter, regresion }) {
  if (!scatter || scatter.length === 0) return null
  const grupos = {}
  scatter.forEach(p => {
    const c = p.cluster || 0
    if (!grupos[c]) grupos[c] = []
    grupos[c].push(p)
  })
  const clusterIds = Object.keys(grupos)
  const nClusters = clusterIds.length

  // Los clusters de k-means no tienen un orden ni significado propio (son
  // solo un índice 0/1) — acá les damos una etiqueta legible ordenándolos
  // por su degradación promedio real, en vez de mostrar "Grupo 1/Grupo 2"
  // sin contexto.
  let nombreCluster = {}
  if (nClusters > 1) {
    const promedios = clusterIds.map(c => ({
      c, avg: grupos[c].reduce((s, p) => s + p.degradacion, 0) / grupos[c].length,
    })).sort((a, b) => a.avg - b.avg)
    const etiquetas = ['Menor degradación técnica', 'Mayor degradación técnica']
    promedios.forEach((p, i) => { nombreCluster[p.c] = etiquetas[i] || `Grupo ${i + 1}` })
  }

  const xs = scatter.map(p => p.fatiga)
  const minX = Math.min(...xs), maxX = Math.max(...xs)
  const lineaRegresion = regresion ? [
    { fatiga: minX, degradacion: regresion.slope * minX + regresion.intercept },
    { fatiga: maxX, degradacion: regresion.slope * maxX + regresion.intercept },
  ] : null

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 8 }}>
        FATIGA × DEGRADACIÓN TÉCNICA
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 4, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" dataKey="fatiga" name="Fatiga (-TSB)" tick={{ fill: C.dim, fontSize: 8 }} />
          <YAxis type="number" dataKey="degradacion" name="Degradación" domain={[0, 'auto']} tick={{ fill: C.dim, fontSize: 8 }} />
          <ZAxis range={[40, 40]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 10 }} />
          {Object.entries(grupos).map(([c, pts]) => (
            <Scatter key={c} name={nombreCluster[c] || 'Sesiones'}
                      data={pts} fill={CLUSTER_COLOR[c % CLUSTER_COLOR.length]} />
          ))}
          {lineaRegresion && (
            <Line data={lineaRegresion} type="linear" dataKey="degradacion" xAxisId={0}
                  stroke={C.dim} strokeWidth={1.5} strokeDasharray="4 4" dot={false} legendType="none" />
          )}
          {nClusters > 1 && <Legend wrapperStyle={{ fontSize: 9 }} />}
        </ScatterChart>
      </ResponsiveContainer>
      {regresion && (
        <div style={{ textAlign: 'center', fontSize: 9, color: C.dim, marginTop: 2 }}>
          Tendencia: {regresion.slope >= 0 ? '+' : ''}{regresion.slope} pts degradación / pt fatiga
        </div>
      )}
    </div>
  )
}

// ── Clusters de Técnica: Cadencia vs Stride Length, coloreado por
//    el estado real de eficiencia de cada sesión ──
const ESTADO_EFICIENCIA_COLOR = { eficiente: C.green, compensada: C.yellow, degradada: C.red }
const ESTADO_EFICIENCIA_LABEL = { eficiente: 'Eficiente', compensada: 'Compensada', degradada: 'Degradada' }

function ClustersTecnica({ clusters, xNombre = 'Cadencia', xUnidad = ' spm', yNombre = 'Stride', yUnidad = ' m' }) {
  if (!clusters || clusters.length === 0) return null
  const grupos = {}
  clusters.forEach(p => {
    if (!grupos[p.estado]) grupos[p.estado] = []
    grupos[p.estado].push(p)
  })

  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 8 }}>
        CLUSTERS DE TÉCNICA
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <ScatterChart margin={{ top: 4, right: 12, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="rgba(255,255,255,0.04)" />
          <XAxis type="number" dataKey="cadencia" name={xNombre} unit={xUnidad} tick={{ fill: C.dim, fontSize: 8 }} />
          <YAxis type="number" dataKey="stride" name={yNombre} unit={yUnidad} tick={{ fill: C.dim, fontSize: 8 }} />
          <ZAxis range={[40, 40]} />
          <Tooltip cursor={{ strokeDasharray: '3 3' }} contentStyle={{ background: '#1a1a2e', border: `1px solid ${C.border}`, borderRadius: 8, fontSize: 10 }} />
          <Legend wrapperStyle={{ fontSize: 9 }} />
          {Object.entries(grupos).map(([estado, pts]) => (
            <Scatter key={estado} name={ESTADO_EFICIENCIA_LABEL[estado] || estado}
                      data={pts} fill={ESTADO_EFICIENCIA_COLOR[estado] || C.dim} />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Comparativa: sesión actual vs mejor sesión del período ──
function ComparativaTecnica({ comparativa }) {
  if (!comparativa || comparativa.length === 0) return null
  return (
    <div style={{ marginTop: 20 }}>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.85)', fontWeight: 700, marginBottom: 2 }}>
        COMPARATIVA vs MEJOR PERÍODO
      </div>
      <div style={{ fontSize: 9, color: C.dim, marginBottom: 8 }}>
        Sesión más reciente vs. tu sesión con mejor score técnico en este período
        (no es necesariamente la más rápida o exigente)
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {comparativa.map((row, i) => {
          const color = row.mejora === true ? C.green : row.mejora === false ? C.red : C.dim
          const arrow = row.diff_pct > 0 ? '↑' : row.diff_pct < 0 ? '↓' : '→'
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 10px', borderRadius: 8, background: C.bg, border: `1px solid ${C.border}`,
            }}>
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.75)', flex: '1 1 auto' }}>{row.metrica}</span>
              <span style={{ fontSize: 10, color: C.dim, marginRight: 10 }}>
                {row.mejor_periodo} → <strong style={{ color: '#fff' }}>{row.actual}</strong>
              </span>
              <span style={{ fontSize: 11, fontWeight: 800, color }}>
                {arrow} {row.diff_pct > 0 ? '+' : ''}{row.diff_pct}%
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Patrón detectado: conclusión automática MUY corta a partir de
//    valores reales (drift + regresión ya calculados) ──
function PatronDetectado({ patron }) {
  if (!patron || !patron.patron) return null
  return (
    <div style={{
      marginTop: 20, padding: '14px 16px', borderRadius: 12,
      background: `${C.purple}0c`, border: `1px solid ${C.purple}30`,
    }}>
      <div style={{ fontSize: 9, color: C.purple, fontWeight: 700, letterSpacing: 1, marginBottom: 6 }}>
        NOAH DETECTÓ
      </div>
      <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.9)', fontWeight: 600, marginBottom: 6 }}>
        {patron.patron}
      </div>
      {patron.accion && (
        <div style={{ fontSize: 10, color: C.dim }}>
          <span style={{ color: C.green, fontWeight: 700 }}>Acción: </span>{patron.accion}
        </div>
      )}
    </div>
  )
}

function AnalisisFatigaTecnica({ data, clusterEjes }) {
  if (!data) return null
  const hayDatos = (data.serie && data.serie.length > 0) ||
                    (data.scatter && data.scatter.length > 0) ||
                    (data.heatmap && data.heatmap.sesiones?.length > 0)
  if (!hayDatos) return null

  return (
    <div style={{ marginTop: 24 }}>
      <div style={{ fontSize: 10, color: C.cyan, fontWeight: 700, letterSpacing: 1, marginBottom: 4 }}>
        ANÁLISIS BIOMECÁNICO
      </div>
      <CurvaEficienciaFatiga serie={data.serie} correlacion={data.correlacion_eficiencia_fatiga} />
      <HeatmapEstabilidad heatmap={data.heatmap} />
      <ClustersTecnica clusters={data.clusters_tecnica} {...(clusterEjes || {})} />
      <ComparativaTecnica comparativa={data.comparativa} />
      <ScatterFatigaDegradacion scatter={data.scatter} regresion={data.regresion_fatiga_degradacion} />
      <PatronDetectado patron={data.patron_detectado} />
    </div>
  )
}

// ═══════════════════════════════════════════════════════════════
// PANELES POR DEPORTE
// ═══════════════════════════════════════════════════════════════

function PanelRunning({ data }) {
  const m = data.metricas || {}
  const cad = m.cadencia || {}
  return (
    <div>
      {/* Imagen con overlays */}
      <div style={{ position: 'relative', width: '100%', height: 350, borderRadius: 16, overflow: 'hidden', marginBottom: 4 }}>
        <img src="/img/tecnica_run.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.6 }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.9) 100%)' }} />

        {cad.promedio && <MetricaOverlay label="CADENCIA" valor={cad.promedio} unidad="spm" estado={cad.estado} x={50} y={22} />}
        {cad.q1 && <MetricaOverlay label="INICIO" valor={cad.q1} unidad="spm"
          estado={cad.q1 >= (cad.referencia?.min||170) ? 'óptima' : 'baja'} x={18} y={52} />}
        {cad.q4 && <MetricaOverlay label="FINAL" valor={cad.q4} unidad="spm"
          estado={Math.abs(cad.drift_pct||0) < 3 ? 'óptima' : 'mejorar'} x={82} y={52} />}
        {cad.drift_pct !== undefined && (
          <MetricaOverlay label="DRIFT" valor={`${cad.drift_pct > 0 ? '+' : ''}${cad.drift_pct}`}
            unidad="%" estado={Math.abs(cad.drift_pct) < 3 ? 'óptima' : (Math.abs(cad.drift_pct) < 5 ? 'leve' : 'mejorar')} x={50} y={75} />
        )}

        {m.gct && <MetricaOverlay label="GCT" valor={m.gct.promedio_ms} unidad="ms" estado={m.gct.estado} x={30} y={38} />}
        {m.vertical_osc && <MetricaOverlay label="OSC VERT" valor={m.vertical_osc.promedio_cm} unidad="cm" estado={m.vertical_osc.estado} x={70} y={38} />}
        {m.economia && <MetricaOverlay label="ECONOMÍA" valor={m.economia.vertical_ratio} unidad="%" estado={m.economia.estado} x={50} y={50} />}
      </div>

      {/* Nivel del atleta */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 10, color: C.dim }}>Nivel: </span>
        <span style={{ fontSize: 10, color: C.purple, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>
          {data.nivel}
        </span>
      </div>

      {/* Sensor notice */}
      <SensorNotice sensores={data.sensores} />

      {/* ANÁLISIS / PLAN DE MEJORA — 3 gráficos reales sobre datos existentes */}
      <AnalisisFatigaTecnica data={data.analisis_fatiga} />
    </div>
  )
}

function PanelCycling({ data }) {
  const m = data.metricas || {}
  const cad = m.cadencia || {}
  const lr = m.lr_balance || {}
  const te = m.torque_effectiveness || {}
  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 350, borderRadius: 16, overflow: 'hidden', marginBottom: 4 }}>
        <img src="/img/tecnica_bike.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.6 }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.9) 100%)' }} />

        {cad.promedio && <MetricaOverlay label="CADENCIA" valor={cad.promedio} unidad="rpm" estado={cad.estado} x={50} y={22} />}
        {cad.q1 && <MetricaOverlay label="INICIO" valor={cad.q1} unidad="rpm"
          estado={cad.q1 >= 80 ? 'óptima' : 'baja'} x={18} y={38} />}
        {cad.q4 && <MetricaOverlay label="FINAL" valor={cad.q4} unidad="rpm"
          estado={Math.abs(cad.drift_pct||0) < 3 ? 'óptima' : 'mejorar'} x={82} y={38} />}
        {lr.promedio_pct !== undefined && <MetricaOverlay label="L/R BALANCE" valor={`${lr.promedio_pct}/${(100-lr.promedio_pct).toFixed(1)}`} unidad="%" estado={lr.estado} x={22} y={62} />}
        {te.promedio_pct && <MetricaOverlay label="TORQUE EFF" valor={te.promedio_pct} unidad="%" estado={te.estado} x={78} y={62} />}
      </div>

      {/* Nivel del atleta */}
      <div style={{ textAlign: 'center', marginBottom: 12 }}>
        <span style={{ fontSize: 10, color: C.dim }}>Nivel: </span>
        <span style={{ fontSize: 10, color: C.purple, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 1 }}>
          {data.nivel}
        </span>
      </div>

      <SpiderChart data={data.spider} />
      <DriftCard drift={data.drift} />
      <Sparklines data={data.sparkline} cadUnidad="rpm" linea2Key="torque_effectiveness" linea2Nombre="Torque Eff. (%)" />
      <CadenciaZonas data={m.cadencia_por_zona} tipo="cycling" />
      <Comparacion data={data.comparacion} />
      <SensorNotice sensores={data.sensores} />
      <Interpretacion items={data.interpretacion} />
      <AnalisisFatigaTecnica data={data.analisis_fatiga}
        clusterEjes={{ xNombre: 'Cadencia', xUnidad: ' rpm', yNombre: 'Potencia', yUnidad: ' W' }} />
    </div>
  )
}

function PanelSwimming({ data }) {
  if (!data || data.error) return (
    <div style={{ position: 'relative', width: '100%', height: 300, borderRadius: 16, overflow: 'hidden' }}>
      <img src="/img/tecnica_swim.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.5 }} />
      <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.95) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <p style={{ fontSize: 13, color: C.dim }}>{data?.error || 'Sin datos de natación'}</p>
      </div>
    </div>
  )
  const m = data.metricas || {}
  const estilos = data.estilos || {}
  const dist = data.distribucion || {}
  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 300, borderRadius: 16, overflow: 'hidden', marginBottom: 4 }}>
        <img src="/img/tecnica_swim.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.5 }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.95) 100%)' }} />
        {m.swolf_avg && <MetricaOverlay label="SWOLF" valor={m.swolf_avg} unidad="" estado={m.swolf_avg < 40 ? 'óptima' : m.swolf_avg < 50 ? 'bueno' : 'mejorar'} x={25} y={30} />}
        {m.brazadas_avg && <MetricaOverlay label="BRAZADAS/25m" valor={m.brazadas_avg} unidad="" estado="bueno" x={75} y={30} />}
        {m.dps_avg && <MetricaOverlay label="DPS" valor={m.dps_avg} unidad="m" estado={m.dps_avg > 2.0 ? 'óptima' : 'bueno'} x={25} y={60} />}
        {m.pace_avg && <MetricaOverlay label="RITMO" valor={m.pace_avg} unidad="min/100m" estado="bueno" x={75} y={60} />}
      </div>
      <p style={{ textAlign: 'center', fontSize: 10, color: C.dim, marginBottom: 12 }}>
        Pileta {data.pool_length || 25}m · <strong style={{ color: C.cyan }}>{data.n_largos}</strong> largos analizados
      </p>
      {Object.keys(estilos).length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700, letterSpacing: 1, marginBottom: 10 }}>POR ESTILO</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {Object.entries(estilos).map(([nombre, d]) => (
              <div key={nombre} style={{ flex: '1 1 140px', padding: '12px', borderRadius: 12, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div style={{ fontSize: 11, color: C.cyan, fontWeight: 700, marginBottom: 6 }}>{nombre}</div>
                <div style={{ fontSize: 10, color: C.dim, lineHeight: 2 }}>
                  Brazadas: <strong style={{ color: 'rgba(255,255,255,0.8)' }}>{d.brazadas_25m}/25m</strong><br/>
                  DPS: <strong style={{ color: 'rgba(255,255,255,0.8)' }}>{d.dps}m</strong><br/>
                  SWOLF: <strong style={{ color: 'rgba(255,255,255,0.8)' }}>{d.swolf}</strong><br/>
                  Ritmo: <strong style={{ color: 'rgba(255,255,255,0.8)' }}>{d.pace_100m} min/100m</strong><br/>
                  FC: <strong style={{ color: 'rgba(255,255,255,0.8)' }}>{d.hr_avg || '--'} bpm</strong>
                  <div style={{ fontSize: 8, color: C.dim, marginTop: 2 }}>{d.n_largos} largos</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
      {Object.keys(dist).length > 1 && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 12, color: C.cyan, fontWeight: 700, letterSpacing: 1, marginBottom: 8 }}>DISTRIBUCIÓN DE ESTILOS</div>
          <div style={{ display: 'flex', height: 24, borderRadius: 6, overflow: 'hidden' }}>
            {Object.entries(dist).sort((a,b) => b[1]-a[1]).map(([nombre, pct], i) => {
              const colors = [C.cyan, C.purple, C.green, C.yellow]
              return <div key={nombre} style={{ width: pct+'%', background: colors[i%4], display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {pct > 10 && <span style={{ fontSize: 8, color: '#000', fontWeight: 700 }}>{nombre} {pct}%</span>}
              </div>
            })}
          </div>
        </div>
      )}
      <SpiderChart data={data.spider} />
      <DriftCard drift={data.drift} />
      <Sparklines data={data.sparkline} cadUnidad="" linea2Key="swolf" linea2Nombre="SWOLF" />
      <Comparacion data={data.comparacion} />
      <Interpretacion items={data.interpretacion} />
      <AnalisisFatigaTecnica data={data.analisis_fatiga}
        clusterEjes={{ xNombre: 'Brazadas', xUnidad: '/25m', yNombre: 'Ritmo', yUnidad: ' min/100m' }} />
    </div>
  )
}


// ═══════════════════════════════════════════════════════════════
// COMPONENTE PRINCIPAL
// ═══════════════════════════════════════════════════════════════

export default function SeccionTecnica({ atletaId }) {
  const [sport, setSport] = useState('running')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    authFetch(`${API}/atletas/${atletaId}/tecnica?sport=${sport}&semanas=8`)
      .then(r => r.json())
      .then(d => { setData(d.data || d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId, sport])

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      {/* Selector de deporte */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
        {[
          { id: 'running', icon: '🏃', label: 'Running' },
          { id: 'cycling', icon: '🚴', label: 'Cycling' },
          { id: 'swimming', icon: '🏊', label: 'Swimming' },
        ].map(s => (
          <button key={s.id} onClick={() => setSport(s.id)} style={{
            flex: 1, padding: '10px 0', borderRadius: 10, cursor: 'pointer',
            border: `1px solid ${sport === s.id ? C.purple : C.border}`,
            background: sport === s.id ? `${C.purple}15` : C.bg,
            color: sport === s.id ? C.purple : C.dim, fontSize: 12, fontWeight: 700,
            transition: 'all 0.2s',
          }}>
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {loading && <div style={{ textAlign: 'center', color: C.dim, padding: 40 }}>Analizando biomecánica...</div>}

      {!loading && data && !data.error && (
        <>
          {sport === 'running' && <PanelRunning data={data} />}
          {sport === 'cycling' && <PanelCycling data={data} />}
          {sport === 'swimming' && <PanelSwimming data={data} />}
        </>
      )}

      {!loading && data?.error && (
        <div style={{
          textAlign: 'center', padding: 40, borderRadius: 16,
          background: C.bg, border: `1px solid ${C.border}`,
        }}>
          <div style={{ fontSize: 13, color: C.dim, marginBottom: 8 }}>{data.error}</div>
          {data.sensores?.faltantes?.length > 0 && (
            <SensorNotice sensores={data.sensores} />
          )}
        </div>
      )}
    </div>
  )
}
