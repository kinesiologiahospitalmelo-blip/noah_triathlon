// src/App.js — NOA NOAH Coach v5 — Estilo Garmin/TrainingPeaks
import { useState, useEffect, useRef } from 'react'
import { BrowserRouter, Routes, Route, useParams, Navigate, useNavigate } from 'react-router-dom'
import axios from 'axios'
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar,
  ScatterChart, Scatter, ReferenceLine, AreaChart, Area
} from 'recharts'
import AtletaDashboard from './AtletaDashboard'
import SeccionRace from './SeccionRace'
import SeccionTests from './SeccionTests'
import OnboardingAtleta from './OnboardingAtleta'
import GraficoActividadStreams from './GraficoActividadStreams'
import PantallaCarga from './PantallaCarga'

// API — en la PC/celular de casa (red local) sigue usando el puerto 5000,
// como ya funcionaba. En Vercel (1 sola dirección para front y backend)
// no hay puerto separado: todo entra por /api en el mismo dominio. El
// navegador ya sabe en qué dirección está parado — solo se le pregunta.
const esLocal = window.location.hostname === "localhost" || window.location.hostname.startsWith("192.168.")
const API = esLocal
  ? `http://${window.location.hostname}:5000/api`
  : "/api"

// authFetch — mismo helper que en AtletaDashboard.jsx, para los fetch()
// nativos del panel coach (axios ya está cubierto por el interceptor
// definido más abajo, junto a la sesión).
function authFetch(url, options = {}) {
  let token = null
  try {
    const raw = localStorage.getItem('noah_sesion')
    token = raw ? JSON.parse(raw)?.token : null
  } catch {}
  const headers = { ...(options.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...options, headers }).then(res => {
    if (res.status === 401) {
      try { localStorage.removeItem('noah_sesion') } catch {}
      if (!window.location.pathname.startsWith('/login')) window.location.href = '/login'
    }
    return res
  })
}

const C = {
  bg:      '#0D1117',
  bg2:     '#161B22',
  bg3:     '#21262D',
  bg4:     '#2D333B',
  border:  'rgba(240,246,252,0.10)',
  border2: 'rgba(240,246,252,0.18)',
  text:    '#E6EDF3',
  text2:   '#8B949E',
  text3:   '#58A6FF',
  run:     '#8B5CF6', runL: 'rgba(139,92,246,0.15)',
  bike:    '#38BDF8', bikeL: 'rgba(56,189,248,0.12)',
  swim:    '#34D399', swimL: 'rgba(52,211,153,0.12)',
  done:    '#3FB950', doneL: 'rgba(63,185,80,0.15)',
  miss:    '#F85149', missL: 'rgba(248,81,73,0.15)',
  partial: '#D29922', partialL: 'rgba(210,153,34,0.15)',
  planned: '#58A6FF', plannedL: 'rgba(88,166,255,0.12)',
  purple:  '#8B5CF6',
  blue:    '#1F6FEB',
  teal:    '#20B2AA',
  amber:   '#D29922',
  red:     '#F85149',
}

const IconRun = ({ size=16, color='currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="13" cy="4" r="2"/>
    <path d="M6 20l3.5-3.5L12 13l2 1 3-3.5"/>
    <path d="M8 9l1.5-4 3.5 2 2 4"/>
  </svg>
)
const IconBike = ({ size=16, color='currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="5.5" cy="17.5" r="3.5"/>
    <circle cx="18.5" cy="17.5" r="3.5"/>
    <path d="M15 6a1 1 0 0 0-1-1h-1l-5 8.5h6.5L13 6"/>
    <path d="M18.5 17.5L14 6"/>
  </svg>
)
const IconSwim = ({ size=16, color='currentColor' }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12c1.5-2 3-2 4.5 0S9 14 10.5 12 13 10 14.5 12 17 14 18.5 12 21 10 22 12"/>
    <path d="M2 17c1.5-2 3-2 4.5 0S9 19 10.5 17 13 15 14.5 17 17 19 18.5 17 21 15 22 17"/>
    <circle cx="16" cy="5" r="1.5"/>
    <path d="M14 6.5l-3 3.5h5"/>
  </svg>
)

const SPORT = {
  running:  { color: C.run,  light: C.runL,  Icon: IconRun,  label: 'Running',  short: 'RUN'  },
  cycling:  { color: C.bike, light: C.bikeL, Icon: IconBike, label: 'Ciclismo', short: 'BIKE' },
  swimming: { color: C.swim, light: C.swimL, Icon: IconSwim, label: 'Natación', short: 'SWIM' },
  triatlon: { color: C.run,  light: C.runL,  Icon: IconRun,  label: 'Triatlón', short: 'TRI'  },
}

const ESTADO = {
  done:    { color: C.done,    light: C.doneL,    label: '✓ Hecha',       dot: C.done    },
  miss:    { color: C.miss,    light: C.missL,    label: '✗ No realizada',dot: C.miss    },
  partial: { color: C.partial, light: C.partialL, label: '~ Modificada',  dot: C.partial },
  planned: { color: C.planned, light: C.plannedL, label: 'Planificada',   dot: C.planned },
}

const css = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${C.bg}; color: ${C.text}; font-family: 'Inter', system-ui, sans-serif; font-size: 14px; }
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: ${C.bg2}; }
  ::-webkit-scrollbar-thumb { background: ${C.bg4}; border-radius: 2px; }
  button { font-family: inherit; }
  input, select, textarea { font-family: inherit; background: ${C.bg3}; border: 1px solid ${C.border}; color: ${C.text}; border-radius: 6px; padding: 7px 11px; font-size: 13px; width: 100%; outline: none; }
  input:focus, select:focus { border-color: ${C.blue}; }
  label { font-size: 11px; color: ${C.text2}; margin-bottom: 4px; display: block; letter-spacing: 0.5px; }
`

function hoyKey() { return new Date().toISOString().slice(0, 10) }
function fmtPaceStr(pace) {
  if (!pace) return '--'
  const m=Math.floor(pace), s=Math.round((pace-m)*60)
  return `${m}:${String(s).padStart(2,'0')}/km`
}
function fmtDist(km) {
  if (!km) return '--'
  const real = km > 500 ? km/1000 : km
  return real >= 1 ? `${real.toFixed(2)} km` : `${Math.round(real*1000)} m`
}
function getDiaKey(f) { return f ? f.slice(0, 10) : null }
function fmtPace(p) { if(!p) return '--'; const m=Math.floor(p),s=Math.round((p-m)*60); return `${m}:${String(s).padStart(2,'0')}` }
function fmtDur(d) { if(!d) return '--'; const h=Math.floor(d/60),m=Math.round(d%60); return h>0?`${h}h ${m}min`:`${m} min` }
function getEstado(s) {
  if (!s) return 'planned'
  // 'completada' viene del backend como string: 'done' | 'partial' | 'miss' | null
  if (s.completada==='done'||s.completada===true||s.estado==='done') return 'done'
  if (s.completada==='partial'||s.estado==='partial') return 'partial'
  if (s.completada==='miss'||s.estado==='miss') return 'miss'
  const fk = getDiaKey(s.fecha)
  if (fk&&fk<hoyKey()&&!s.completada) return 'miss'
  return 'planned'
}

function SportBadge({ sport }) {
  const s = SPORT[sport]||SPORT.running
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'2px 8px', borderRadius:5, fontSize:10, fontWeight:700, color:s.color, background:s.light, border:`1px solid ${s.color}33` }}>
      <s.Icon size={11} color={s.color} />{s.short}
    </span>
  )
}

function EstadoBadge({ estado }) {
  const e = ESTADO[estado]||ESTADO.planned
  return (
    <span style={{ display:'inline-flex', alignItems:'center', gap:4, padding:'2px 8px', borderRadius:5, fontSize:10, fontWeight:600, color:e.color, background:e.light }}>
      {e.label}
    </span>
  )
}

function Pill({ flag }) {
  const cols = { verde:C.done, amarillo:C.amber, rojo:C.miss }
  const bgs  = { verde:C.doneL, amarillo:C.partialL, rojo:C.missL }
  if (!flag) return null
  return <span style={{ padding:'2px 8px', borderRadius:99, fontSize:10, fontWeight:700, color:cols[flag]||C.text2, background:bgs[flag]||C.bg3, letterSpacing:0.5, textTransform:'uppercase' }}>{flag}</span>
}

function MetricCard({ label, value, sub, color }) {
  return (
    <div style={{ background:C.bg3, border:`1px solid ${C.border}`, borderTop:`2px solid ${color||C.purple}`, borderRadius:8, padding:'11px 13px' }}>
      <div style={{ fontSize:10, color:C.text2, marginBottom:5, letterSpacing:0.8, textTransform:'uppercase' }}>{label}</div>
      <div style={{ fontSize:20, fontWeight:700, color:color||C.text }}>{value??'--'}</div>
      {sub&&<div style={{ fontSize:11, color:C.text2, marginTop:3 }}>{sub}</div>}
    </div>
  )
}

function MetricBadgeCircular({ label, value, sub, color }) {
  const c = color || C.purple
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:7, minWidth:78 }}>
      <div style={{
        width:78, height:78, borderRadius:'50%',
        background:'rgba(255,255,255,0.045)',
        backdropFilter:'blur(12px)', WebkitBackdropFilter:'blur(12px)',
        border:`2px solid ${c}`, boxShadow:`0 0 18px ${c}30, inset 0 0 12px ${c}12`,
        display:'flex', alignItems:'center', justifyContent:'center',
      }}>
        <span style={{ fontSize:18, fontWeight:800, color:c, lineHeight:1 }}>{value??'--'}</span>
      </div>
      <div style={{ textAlign:'center' }}>
        <div style={{ fontSize:9.5, fontWeight:700, color:C.text2, letterSpacing:0.7, textTransform:'uppercase' }}>{label}</div>
        {sub && <div style={{ fontSize:9, color:C.text3, marginTop:1 }}>{sub}</div>}
      </div>
    </div>
  )
}

function SectionTitle({ children }) {
  return <div style={{ fontSize:10, fontWeight:600, letterSpacing:1.5, textTransform:'uppercase', color:C.text2, marginBottom:10 }}>{children}</div>
}

function Card({ children, style }) {
  return <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:10, overflow:'hidden', ...style }}>{children}</div>
}

function CardRow({ label, value }) {
  return (
    <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'9px 14px', borderBottom:`1px solid ${C.border}` }}>
      <span style={{ fontSize:12, color:C.text2 }}>{label}</span>
      <span style={{ fontSize:13, fontWeight:500 }}>{value??'--'}</span>
    </div>
  )
}

function AtletaItem({ atleta, selected, onClick, colapsado }) {
  const dep = atleta.deporte_ppal||atleta.deporte||'running'
  const s = SPORT[dep]||SPORT.running
  const inicial = (atleta.nombre||'?').trim().charAt(0).toUpperCase()

  return (
    <div onClick={onClick} title={atleta.nombre} style={{
      padding: colapsado ? '10px 0' : '10px 14px',
      cursor:'pointer', display:'flex', alignItems:'center',
      justifyContent: colapsado ? 'center' : 'flex-start',
      gap:10, borderBottom:`1px solid ${C.border}`,
      background:selected?`${C.purple}18`:'transparent',
      borderLeft:selected?`3px solid ${C.purple}`:'3px solid transparent',
      transition:'all 0.15s',
    }}>
      <div style={{
        width:34, height:34, borderRadius:'50%', flexShrink:0,
        background:`${s.color}22`, border:`1.5px solid ${s.color}55`,
        display:'flex', alignItems:'center', justifyContent:'center',
        fontSize:14, fontWeight:800, color:s.color,
      }}>{inicial}</div>
      {!colapsado && (
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flex:1, minWidth:0 }}>
          <div style={{ fontWeight:600, fontSize:13, color:C.text, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>
            {atleta.nombre}
          </div>
          <Pill flag={atleta.hrv_flag} />
        </div>
      )}
    </div>
  )
}

function calcularTssBloques(bloques, lthr) {
  if (!bloques?.length || !lthr) return 0
  return bloques.reduce((total, b) => {
    const reps    = b.repeticiones || 1
    const dur     = b.duracion_min || 0
    const pausa   = b.pausa_min || 0
    const nPausas = Math.max(0, reps - 1)

    const hrMid = ((b.hr_min || lthr * 0.8) + (b.hr_max || lthr * 0.9)) / 2
    const IF = hrMid / lthr

    // TSS del trabajo principal
    const dur_trabajo = dur * reps
    let tss = IF * IF * (dur_trabajo / 60) * 100

    // TSS de las pausas — si son activas se asume ~Z1 (IF≈0.65), si son
    // pasivas el costo metabólico es despreciable (≈0)
    if (pausa > 0 && nPausas > 0) {
      const dur_pausa = pausa * nPausas
      const IF_pausa = b.pausa_activa !== false ? 0.65 : 0.0
      tss += IF_pausa * IF_pausa * (dur_pausa / 60) * 100
    }

    return total + tss
  }, 0)
}

function BloqueItem({ bloque, sport }) {
  const fmtD = d => d < 1 ? `${Math.round(d*60)}"` : `${Math.round(d)}'`
  const fmtP = p => { if(!p)return''; const m=Math.floor(p),s=Math.round((p-m)*60); return `${m}:${String(s).padStart(2,'0')}` }
  const dur = bloque.repeticiones>1?`${bloque.repeticiones}×${fmtD(bloque.duracion_min)}`:fmtD(bloque.duracion_min)
  const ref = sport==='cycling' && bloque.watts_min ? `${bloque.watts_min}–${bloque.watts_max}W`
    : sport==='swimming' && bloque.pace_ref ? `${fmtP(bloque.pace_ref)}/100m`
    : bloque.pace_ref ? `${fmtP(bloque.pace_ref)}/km`
    : ''
  const sc = SPORT[sport||'running']
  return (
    <div style={{ padding:'6px 10px', background:C.bg4, borderRadius:6, fontSize:12, color:C.text2, marginBottom:4, borderLeft:`3px solid ${sc.color}22` }}>
      <span style={{ fontWeight:700, color:C.text, marginRight:6 }}>{dur}</span>
      <span style={{ color:sc.color, marginRight:6, fontWeight:600 }}>{bloque.zona}</span>
      <span style={{ color:C.text2 }}>{ref}</span>
    </div>
  )
}

// Cache simple en memoria por sesión de navegador — evita refetchear zonas
// cada vez que se abre un editor distinto del mismo atleta.
const _zonasCache = {}

function useZonasAtleta(atletaId, sport) {
  const [zonas, setZonas] = useState(null)
  useEffect(() => {
    if (!atletaId || !sport) return
    const key = `${atletaId}-${sport}`
    if (_zonasCache[key]) { setZonas(_zonasCache[key]); return }
    axios.get(`${API}/atletas/${atletaId}/zonas/${sport}`)
      .then(r => { _zonasCache[key] = r.data.data; setZonas(r.data.data) })
      .catch(() => {})
  }, [atletaId, sport])
  return zonas
}

function BloqueEditor({ bloque, sport, atletaId, onChange, onEliminar }) {
  const s = SPORT[sport||'running']
  const zonas = useZonasAtleta(atletaId, sport)
  const durMin = bloque.duracion_min || 1
  const esBike = sport === 'cycling'
  const esSwim = sport === 'swimming'

  const fmtDur = (d) => {
    if (d < 1) return `${Math.round(d * 60)}"`
    return `${Math.round(d)}'`
  }
  const ajustarDur = (delta) => onChange({ ...bloque, duracion_min: Math.max(0.17, durMin + delta) })
  const ajustarReps = (delta) => onChange({ ...bloque, repeticiones: Math.max(1, Math.min(30, (bloque.repeticiones||1)+delta)) })
  const ajustarPausa = (delta) => onChange({ ...bloque, pausa_min: Math.max(0, (bloque.pausa_min||0)+delta) })

  // Lista de zonas disponibles para el selector — los bloques guardados usan
  // prefijo BZ para bike (ver datos reales en prescripcion_bloques), aunque
  // el endpoint /zonas/cycling devuelve las claves como Z1-Z7 (bici también
  // usa esa convención ahí). Mapeamos entre ambos formatos al buscar la referencia.
  const zonasDisponibles = esBike
    ? ['BZ1','BZ2','BZ3','BZ4','BZ5','BZ6','BZ7']
    : ['Z1','Z2','Z3','Z4','Z5','Z6']

  // El shape real de /zonas/:sport es un objeto plano: {Z1:{...}, Z2:{...}, ...}
  // con claves w_min/w_max (no watts_min/watts_max) y pace_ref no existe —
  // para run/swim el campo de referencia de pace viene como otra estructura
  // que no incluye pace directamente en este endpoint (solo HR/watts).
  const zonaKey = bloque.zona?.replace('BZ', 'Z')  // 'BZ3' -> 'Z3' para buscar en el objeto
  const zonaInfo = (zonas && typeof zonas === 'object' && !Array.isArray(zonas))
    ? zonas[zonaKey]
    : null

  return (
    <div style={{ padding:'10px 12px', background:C.bg4, borderRadius:8, marginBottom:6,
      border:`1px solid ${C.border2}` }}>

      {/* Fila 1: zona + nombre + eliminar */}
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:8 }}>
        <select value={bloque.zona} onChange={e=>onChange({...bloque, zona:e.target.value, zona_nombre:e.target.value})}
          style={{ fontSize:11, fontWeight:700, color:s.color, background:C.bg3,
            border:`1px solid ${s.color}44`, borderRadius:6, padding:'4px 6px', cursor:'pointer' }}>
          {zonasDisponibles.map(z => <option key={z} value={z}>{z}</option>)}
        </select>
        <input value={bloque.nombre||''} onChange={e=>onChange({...bloque, nombre:e.target.value})}
          placeholder="Nombre del bloque"
          style={{ flex:1, minWidth:80, fontSize:12, color:C.text, background:'transparent',
            border:'none', borderBottom:`1px solid ${C.border2}`, padding:'2px 0' }} />
        {onEliminar && (
          <button onClick={onEliminar} title="Eliminar bloque" style={{
            width:22, height:22, borderRadius:5, border:`1px solid ${C.miss}33`,
            background:'transparent', color:C.miss, cursor:'pointer', fontSize:13, flexShrink:0 }}>×</button>
        )}
      </div>

      {/* Fila 2: reps / duración / pausa */}
      <div style={{ display:'flex', alignItems:'center', gap:14, flexWrap:'wrap', marginBottom:8 }}>
        <div style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ fontSize:10, color:C.text2 }}>reps</span>
          <button onClick={()=>ajustarReps(-1)} style={miniBtnStyle}>−</button>
          <span style={{ fontSize:12, fontWeight:700, color:C.text, minWidth:18, textAlign:'center' }}>{bloque.repeticiones||1}</span>
          <button onClick={()=>ajustarReps(1)} style={miniBtnStyle}>+</button>
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ fontSize:10, color:C.text2 }}>dur</span>
          <button onClick={()=>ajustarDur(-(durMin<2?0.25:1))} style={miniBtnStyle}>−</button>
          <span style={{ fontSize:12, fontWeight:700, color:C.text, minWidth:30, textAlign:'center' }}>{fmtDur(durMin)}</span>
          <button onClick={()=>ajustarDur(durMin<2?0.25:1)} style={miniBtnStyle}>+</button>
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ fontSize:10, color:C.text2 }}>pausa</span>
          <button onClick={()=>ajustarPausa(-0.5)} style={miniBtnStyle}>−</button>
          <span style={{ fontSize:12, fontWeight:700, color:C.text, minWidth:26, textAlign:'center' }}>{fmtDur(bloque.pausa_min||0)}</span>
          <button onClick={()=>ajustarPausa(0.5)} style={miniBtnStyle}>+</button>
        </div>

        <label style={{ display:'flex', alignItems:'center', gap:4, fontSize:10, color:C.text2, cursor:'pointer' }}>
          <input type="checkbox" checked={bloque.pausa_activa!==false}
            onChange={e=>onChange({...bloque, pausa_activa:e.target.checked})} />
          activa
        </label>
      </div>

      {/* Fila 3: métrica editable — watts (bike) / pace (run, min:seg /km) / pace (swim, min:seg /100m) */}
      <div style={{ display:'flex', alignItems:'center', gap:10, flexWrap:'wrap' }}>
        {esBike ? (
          <>
            <span style={{ fontSize:10, color:C.text2 }}>watts</span>
            <input type="number" value={bloque.watts_min ?? ''} placeholder="min"
              onChange={e=>onChange({...bloque, watts_min: e.target.value===''?null:Number(e.target.value)})}
              style={inputMiniStyle} />
            <span style={{ fontSize:11, color:C.text2 }}>–</span>
            <input type="number" value={bloque.watts_max ?? ''} placeholder="max"
              onChange={e=>onChange({...bloque, watts_max: e.target.value===''?null:Number(e.target.value)})}
              style={inputMiniStyle} />
            <span style={{ fontSize:11, color:C.text2 }}>W</span>
          </>
        ) : (
          <>
            <span style={{ fontSize:10, color:C.text2 }}>pace</span>
            <input value={bloque.pace_ref ?? ''} placeholder={esSwim?'1:44':'5:04'}
              onChange={e=>onChange({...bloque, pace_ref_str: e.target.value})}
              style={{...inputMiniStyle, width:52}} />
            <span style={{ fontSize:11, color:C.text2 }}>/{esSwim?'100m':'km'}</span>
          </>
        )}

        {zonaInfo && (
          <span style={{ fontSize:10, color:C.text3, fontStyle:'italic', marginLeft:'auto' }}>
            ref {bloque.zona}: {esBike
              ? `${zonaInfo.w_min ?? '?'}–${zonaInfo.w_max ?? '?'}W`
              : `HR ${zonaInfo.hr_min ?? '?'}–${zonaInfo.hr_max ?? '?'}`}
          </span>
        )}
      </div>
    </div>
  )
}

const miniBtnStyle = {
  width:20, height:20, borderRadius:4, border:`1px solid ${C.border2}`,
  background:C.bg3, color:C.text, cursor:'pointer', fontSize:13, lineHeight:'18px', textAlign:'center'
}
const inputMiniStyle = {
  width:44, padding:'3px 6px', fontSize:11, color:C.text, background:C.bg3,
  border:`1px solid ${C.border2}`, borderRadius:5, textAlign:'center'
}

// ── Gráfico de actividad — PREMIUM ESMERILADO ─────────────────────────────────
// Eje Y izq: FC (bpm) — curva violeta bezier suavizada
// Eje Y der: pace / watts / swolf según deporte — curva blanca punteada
// Columnas de fondo coloreadas por zona HR, línea LTHR amber, hover tooltip
// ── GraficoActividad → GraficoActividadStreams (streams punto a punto) ────────
function GraficoActividad({ act, laps, sport, lthr = 162, sesionId, atletaId }) {
  return (
    <GraficoActividadStreams
      act={act}
      laps={laps || []}
      sport={sport}
      lthr={lthr}
      sesionId={sesionId || act?.sesion_id}
      atletaId={atletaId}
      height={240}
    />
  )
}


// ── MiniCalendario — selector de 7 días (dashboard coach) ────────────────────
function MiniCalendario({ fechaSeleccionada, onSelect, actividades7dias }) {
  const hoy  = hoyKey()
  const dias = []
  for (let i = 6; i >= 0; i--)
    dias.push(new Date(Date.now() - i * 86400000).toISOString().slice(0, 10))
  const DIAS_CORTO = ['D','L','M','M','J','V','S']
  const sportColors = { running:'#8B5CF6', cycling:'#38BDF8', swimming:'#34D399' }

  return (
    <div style={{ display:'flex', gap:5, marginBottom:14 }}>
      {dias.map(dia => {
        const actsDia = (actividades7dias || {})[dia] || []
        const esHoy   = dia === hoy
        const selec   = dia === fechaSeleccionada
        const dObj    = new Date(dia + 'T12:00:00')
        return (
          <div key={dia} onClick={() => onSelect(dia)} style={{
            flex:1, cursor:'pointer', borderRadius:10,
            padding:'7px 4px', textAlign:'center',
            background: selec
              ? 'linear-gradient(135deg,rgba(139,92,246,0.35),rgba(139,92,246,0.15))'
              : esHoy ? 'rgba(255,255,255,0.07)' : 'rgba(255,255,255,0.03)',
            border: selec ? '1px solid rgba(139,92,246,0.6)'
              : esHoy ? '1px solid rgba(255,255,255,0.12)' : '1px solid rgba(255,255,255,0.05)',
            transition: 'all 0.15s',
          }}>
            <div style={{ fontSize:9, color: selec ? '#C4B5FD' : 'rgba(255,255,255,0.35)',
              fontWeight:600, textTransform:'uppercase', letterSpacing:0.5, marginBottom:3 }}>
              {DIAS_CORTO[dObj.getDay()]}
            </div>
            <div style={{ fontSize:14, fontWeight:700,
              color: selec ? '#E9D5FF' : esHoy ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.5)' }}>
              {dObj.getDate()}
            </div>
            <div style={{ display:'flex', justifyContent:'center', gap:2, marginTop:4, minHeight:6 }}>
              {actsDia.map((a, i) => (
                <div key={i} style={{
                  width:5, height:5, borderRadius:'50%',
                  background: sportColors[a.sport] || '#94A3B8',
                  boxShadow: `0 0 4px ${sportColors[a.sport] || '#94A3B8'}80`,
                }}/>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}


// ── ActividadRecienteCoach — con mini calendario 7 días ─────────────────────
function ActividadRecienteCoach({ atletaId, lthr = 162, presc }) {
  const hoy = hoyKey()
  // Estado unificado: un objeto con todo lo que necesita el render
  const [estado, setEstado] = useState({ acts: null, acts7: {}, fechaSel: null })

  useEffect(() => {
    if (!atletaId) return
    // Reset inmediato — limpia cualquier dato del atleta anterior
    setEstado({ acts: null, acts7: {}, fechaSel: null })

    let cancelado = false
    const desde = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    const hasta  = new Date().toISOString().slice(0, 10)

    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desde}&hasta=${hasta}`)
      .then(r => r.json())
      .then(r => {
        if (cancelado) return
        const acts7 = r.data?.actividades || {}
        const results = Object.entries(acts7).map(([dia, acts]) => ({ dia, acts }))
      const conActs = results.filter(r => r.acts.length > 0).sort((a,b) => b.dia > a.dia ? 1 : -1)
      // Setear todo en un solo setState — cero renders intermedios
      setEstado({
        acts7,
        fechaSel: conActs.length > 0 ? conActs[0].dia : hoy,
        acts:     conActs.length > 0 ? conActs[0].acts : [],
      })
    })

    // Cleanup: si atletaId cambia antes de que termine el fetch, ignorar resultado
    return () => { cancelado = true }
  }, [atletaId])

  // Cuando el usuario toca el calendario — solo cambia fecha y acts, no recarga nada
  const onSelectFecha = (fecha) => {
    setEstado(prev => ({
      ...prev,
      fechaSel: fecha,
      acts: prev.acts7[fecha] || [],
    }))
  }

  const { acts, acts7, fechaSel } = estado
  const lista = acts || []
  const dObj = fechaSel ? new Date(fechaSel + 'T12:00:00') : null
  const labelFecha = !dObj ? '' : fechaSel === hoy
    ? '✓ Actividad de hoy'
    : `✓ ${dObj.toLocaleDateString('es-AR', { weekday:'long', day:'numeric', month:'short' })}`

  return (
    <div style={{background:C.bg3,borderRadius:10,padding:'14px 16px',
      border:`1px solid ${C.border}`,borderLeft:'4px solid #10B981',
      boxShadow:'0 8px 24px rgba(0,0,0,0.4)'}}>
      <MiniCalendario
        fechaSeleccionada={fechaSel}
        onSelect={onSelectFecha}
        actividades7dias={acts7}
      />
      {acts === null && <div style={{fontSize:11,color:C.text2,padding:'8px 0'}}>Cargando...</div>}
      {lista.length > 0 && <div style={{fontSize:10,fontWeight:700,color:'#10B981',textTransform:'uppercase',
        letterSpacing:1.2,marginBottom:14}}>{labelFecha}</div>}
      {acts !== null && lista.length === 0 && <div style={{fontSize:11,color:C.text2,padding:'8px 0',textAlign:'center'}}>Sin actividad este día</div>}
      <div style={{display:'flex',flexDirection:'column',gap:16}}>
        {lista.map((act, idx) => {
          const sp = SPORT[act.sport] || SPORT.running
          const distKm = act.distance_km > 500 ? act.distance_km/1000 : act.distance_km
          return (
            <div key={act.sesion_id || act.id || idx} style={{borderTop:idx>0?`1px solid ${C.border}`:'none',paddingTop:idx>0?16:0}}>
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                <div style={{width:36,height:36,borderRadius:7,background:sp.light,
                  display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:1}}>
                  <sp.Icon size={14} color={sp.color}/>
                  <span style={{fontSize:7,fontWeight:800,color:sp.color}}>{sp.short}</span>
                </div>
                <div style={{flex:1}}>
                  <div style={{fontSize:13,fontWeight:700,color:C.text}}>
                    {sp.label} · {distKm?.toFixed(2)} km · {Math.round(act.duration_min)} min
                  </div>
                  <div style={{fontSize:11,color:C.text2}}>
                    HR {act.hr_avg?Math.round(act.hr_avg):'--'} bpm avg
                    {act.hr_max?` · máx ${Math.round(act.hr_max)}`:''}
                    {act.tss_total?` · TSS ${act.tss_total.toFixed(0)}`:''}
                    {act.pace?` · ${Math.floor(act.pace)}:${String(Math.round((act.pace%1)*60)).padStart(2,'0')}/km`:''}
                    {act.np_watts?` · ${act.np_watts}W NP`:''}
                  </div>
                </div>
              </div>
              <GraficoActividad act={act} laps={act.laps||[]} sport={act.sport} lthr={lthr}
                sesionId={act.sesion_id || act.id} atletaId={atletaId}/>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── ActividadCoach — actividad inline dentro de CoachSesionCard ───────────────
function ActividadCoach({ atletaId, fecha, sport, tssPresc, lthr = 162 }) {
  const [acts, setActs] = useState(null)

  useEffect(() => {
    if (!atletaId || !fecha) return
    authFetch(`${API}/atletas/${atletaId}/actividades_dia?fecha=${fecha}&exacto=true`)
      .then(r=>r.json()).then(r=>setActs(r.data?.actividades||[])).catch(()=>setActs([]))
  }, [atletaId, fecha])

  if (!acts) return <div style={{fontSize:11,color:C.text2,padding:'8px 0'}}>Cargando actividad...</div>

  // Mapear sport de la sesión prescripta al sport real de Garmin
  const SPORT_MAP = { running:'running', run:'running', cycling:'cycling', bike:'cycling', swimming:'swimming', swim:'swimming' }
  const sportEsperado = SPORT_MAP[sport] || sport

  // Filtrar solo la(s) actividad(es) que coinciden con el deporte de ESTA sesión.
  // Evita mostrar una actividad de otro deporte (ej: bike) dentro de una sesión de running.
  const actsFiltradas = (acts||[]).filter(a => (SPORT_MAP[a.sport] || a.sport) === sportEsperado)

  if (!actsFiltradas.length) return (
    <div style={{fontSize:11,color:'rgba(255,255,255,0.3)',padding:'8px 0',display:'flex',alignItems:'center',gap:6}}>
      <span style={{fontSize:14}}>📡</span> Sin actividad Garmin este día
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:10,marginTop:10}}>
      {actsFiltradas.map((act,idx)=>(
        <div key={idx}>
          <GraficoActividad act={act} laps={act.laps||[]} sport={act.sport} lthr={lthr}
            sesionId={act.sesion_id || act.id} atletaId={atletaId}/>
          {act.sport === 'running' && <VelocidadCriticaBotonesCoach atletaId={atletaId} />}
        </div>
      ))}
    </div>
  )
}


// ══════════════════════════════════════════════════════════════════════════════
// CalendarioMensual — vista mensual estilo TrainingPeaks
// ══════════════════════════════════════════════════════════════════════════════
function CalendarioMensual({ atletaId, presc, dark = false }) {
  const hoy = hoyKey()
  const [mesOffset, setMesOffset] = useState(0)
  const [actsMes, setActsMes]     = useState({})
  const [cargando, setCargando]   = useState(false)
  const [diaDetalle, setDiaDetalle] = useState(null)

  const fechaRef  = new Date(); fechaRef.setDate(1); fechaRef.setMonth(fechaRef.getMonth() + mesOffset)
  const anio      = fechaRef.getFullYear()
  const mes       = fechaRef.getMonth()
  const primerDia = new Date(anio, mes, 1)
  const ultimoDia = new Date(anio, mes + 1, 0)
  const nombreMes = primerDia.toLocaleDateString('es-AR', { month:'long', year:'numeric' })

  useEffect(() => {
    if (!atletaId) return
    setCargando(true); setActsMes({})
    const desde = primerDia.toISOString().slice(0, 10)
    const hasta  = ultimoDia.toISOString().slice(0, 10)
    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desde}&hasta=${hasta}`)
      .then(r => r.json())
      .then(r => {
        const map = r.data?.actividades || {}
        setActsMes(map)
        setCargando(false)
      })
      .catch(() => { setActsMes({}); setCargando(false) })
  }, [atletaId, mesOffset])

  const sesiones  = presc?.prescripcion?.sesiones || []
  const getEstado = (fecha) => {
    const acts = actsMes[fecha]||[], pres = sesiones.filter(s=>getDiaKey(s.fecha)===fecha)
    const pass  = fecha <= hoy
    if (pres.length > 0) {
      const sp = pres.map(s=>s.sport)
      if (acts.some(a=>sp.includes(a.sport))) return 'done'
      if (acts.length > 0) return 'partial'
      if (pass) return 'miss'
      return 'planned'
    }
    return acts.length > 0 ? 'done' : 'none'
  }

  const T = dark ? {
    wrap:   'linear-gradient(160deg,rgba(10,10,28,0.98),rgba(16,16,40,0.96))',
    header: 'linear-gradient(90deg,rgba(99,102,241,0.15),transparent)',
    border: 'rgba(255,255,255,0.07)',
    text:   'rgba(255,255,255,0.88)', dim:'rgba(255,255,255,0.3)',
    week:   'rgba(255,255,255,0.38)', hoy:'rgba(99,102,241,0.2)',
    selBg:  'rgba(99,102,241,0.3)', selBorder:'rgba(99,102,241,0.7)',
    dayBg:  'transparent', tss:'rgba(99,102,241,0.12)', tssBorder:'rgba(99,102,241,0.25)',
    tssText:'#A5B4FC',
  } : {
    wrap:   '#FFFFFF',
    header: 'linear-gradient(90deg,#EEF2FF,#F9FAFB)',
    border: '#E5E7EB',
    text:   '#111827', dim:'#9CA3AF',
    week:   '#6B7280', hoy:'#EEF2FF',
    selBg:  '#E0E7FF', selBorder:'#6366F1',
    dayBg:  '#FFFFFF', tss:'#F5F3FF', tssBorder:'#DDD6FE',
    tssText:'#6366F1',
  }

  const E = {
    done:    {bg:dark?'rgba(34,197,94,0.15)':'#DCFCE7',   bd:dark?'rgba(34,197,94,0.35)':'#86EFAC',   dot:'#22C55E'},
    partial: {bg:dark?'rgba(245,158,11,0.15)':'#FEF9C3',  bd:dark?'rgba(245,158,11,0.35)':'#FDE047',  dot:'#F59E0B'},
    miss:    {bg:dark?'rgba(239,68,68,0.13)':'#FEE2E2',   bd:dark?'rgba(239,68,68,0.3)':'#FECACA',    dot:'#EF4444'},
    planned: {bg:dark?'rgba(99,102,241,0.1)':'#EEF2FF',   bd:dark?'rgba(99,102,241,0.25)':'#C7D2FE',  dot:'#6366F1'},
    none:    {bg:'transparent', bd:'transparent', dot:null},
  }
  const SC = {running:'#8B5CF6',cycling:'#38BDF8',swimming:'#34D399'}
  const DIAS = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']

  const dow = (f) => (new Date(f+'T12:00:00').getDay()+6)%7
  const offset = dow(`${anio}-${String(mes+1).padStart(2,'0')}-01`)
  const celdas = Math.ceil((offset + ultimoDia.getDate())/7)*7
  const grilla = Array.from({length:celdas}, (_,i)=>{
    const d = i-offset+1
    return (d<1||d>ultimoDia.getDate()) ? null :
      `${anio}-${String(mes+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`
  })
  const semanas = Array.from({length:grilla.length/7}, (_,i)=>grilla.slice(i*7,i*7+7))
  const tssSem  = (sem) => sem.filter(Boolean).reduce((t,f)=>
    t+(actsMes[f]||[]).reduce((tt,a)=>tt+(a.tss_total||0),0), 0)

  return (
    <div style={{
      borderRadius:14, overflow:'hidden',
      background:T.wrap,
      border:`1px solid ${T.border}`,
      boxShadow: dark?'0 20px 60px rgba(0,0,0,0.5)':'0 4px 16px rgba(0,0,0,0.06)',
    }}>

      {/* Header */}
      <div style={{padding:'12px 18px',background:T.header,borderBottom:`1px solid ${T.border}`,
        display:'flex',alignItems:'center',gap:10}}>
        {[['‹',()=>setMesOffset(m=>m-1)],['›',()=>setMesOffset(m=>m+1)]].map(([l,fn],i)=>(
          <button key={i} onClick={fn} style={{width:30,height:30,borderRadius:7,
            border:`1px solid ${T.border}`,background:'transparent',color:T.text,
            cursor:'pointer',fontSize:16,display:'flex',alignItems:'center',justifyContent:'center'}}>
            {l}
          </button>
        )).reduce((acc,el,i)=>i===0?[el]:[ ...acc,
          <div key="mid" style={{flex:1,textAlign:'center'}}>
            <span style={{fontSize:15,fontWeight:700,color:T.text,textTransform:'capitalize'}}>
              {nombreMes}
            </span>
          </div>, el
        ],[])}
        <button onClick={()=>setMesOffset(0)} style={{padding:'3px 10px',borderRadius:7,
          fontSize:10,fontWeight:600,border:`1px solid ${T.border}`,background:'transparent',
          color:T.dim,cursor:'pointer'}}>Hoy</button>
      </div>

      {/* Leyenda */}
      <div style={{padding:'6px 18px',display:'flex',gap:10,borderBottom:`1px solid ${T.border}`}}>
        {[['#22C55E','Completada'],['#F59E0B','Modificada'],['#EF4444','No realizada'],['#6366F1','Planificada']].map(([c,l])=>(
          <div key={l} style={{display:'flex',alignItems:'center',gap:3}}>
            <div style={{width:7,height:7,borderRadius:'50%',background:c}}/>
            <span style={{fontSize:9,color:T.dim}}>{l}</span>
          </div>
        ))}
      </div>

      {/* Cabecera días */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(7,1fr) 60px',
        padding:'0 6px',borderBottom:`1px solid ${T.border}`}}>
        {DIAS.map(d=>(
          <div key={d} style={{padding:'6px 4px',textAlign:'center',fontSize:9,
            fontWeight:600,color:T.week,textTransform:'uppercase',letterSpacing:0.5}}>{d}</div>
        ))}
        <div style={{padding:'6px 4px',textAlign:'center',fontSize:9,fontWeight:600,color:T.week}}>TSS</div>
      </div>

      {/* Cargando */}
      {cargando && <div style={{padding:20,textAlign:'center',color:T.dim,fontSize:12}}>Cargando...</div>}

      {/* Semanas */}
      {!cargando && semanas.map((sem,si)=>(
        <div key={si} style={{display:'grid',gridTemplateColumns:'repeat(7,1fr) 60px',
          padding:'2px 6px',gap:2,borderBottom:`1px solid ${T.border}`}}>
          {sem.map((fecha,di)=>{
            if(!fecha) return <div key={di}/>
            const est    = E[getEstado(fecha)]
            const acts   = actsMes[fecha]||[]
            const pres   = sesiones.filter(s=>getDiaKey(s.fecha)===fecha)
            const esHoy  = fecha===hoy
            const esFut  = fecha>hoy
            const selec  = diaDetalle===fecha
            const num    = new Date(fecha+'T12:00:00').getDate()
            const tss    = Math.round(acts.reduce((t,a)=>t+(a.tss_total||0),0))
            return (
              <div key={di} onClick={()=>setDiaDetalle(selec?null:fecha)} style={{
                minHeight:68,padding:'5px 6px',borderRadius:7,cursor:'pointer',
                transition:'all 0.12s',
                background:selec?T.selBg:esHoy?T.hoy:est.bg,
                border:`1px solid ${selec?T.selBorder:esHoy?T.selBorder:est.bd||T.border}`,
                opacity:esFut&&getEstado(fecha)==='none'?0.45:1,
              }}>
                <div style={{display:'flex',justifyContent:'space-between',marginBottom:3}}>
                  <span style={{fontSize:12,fontWeight:esHoy?800:500,
                    color:esHoy?(dark?'#A5B4FC':'#6366F1'):T.text}}>{num}</span>
                  {est.dot&&<div style={{width:6,height:6,borderRadius:'50%',
                    background:est.dot,boxShadow:`0 0 3px ${est.dot}`}}/>}
                </div>
                {acts.slice(0,2).map((a,ai)=>{
                  const c=SC[a.sport]||'#94A3B8'
                  const dk=(a.distance_km>500?a.distance_km/1000:a.distance_km)?.toFixed(1)
                  return <div key={ai} style={{fontSize:8,fontWeight:600,color:c,
                    background:`${c}18`,borderRadius:3,padding:'1px 4px',marginBottom:1,
                    overflow:'hidden',whiteSpace:'nowrap',textOverflow:'ellipsis'}}>
                    {a.sport==='running'?'🏃':a.sport==='cycling'?'🚴':'🏊'} {dk}km
                  </div>
                })}
                {acts.length===0&&pres.slice(0,1).map((s,pi)=>(
                  <div key={pi} style={{fontSize:8,color:T.dim,borderRadius:3,padding:'1px 0'}}>
                    {s.sport==='running'?'🏃':s.sport==='cycling'?'🚴':'🏊'} {s.nombre?.slice(0,10)}
                  </div>
                ))}
                {tss>0&&<div style={{fontSize:8,color:T.dim}}>{tss}</div>}
              </div>
            )
          })}
          {/* TSS semanal */}
          <div style={{display:'flex',flexDirection:'column',justifyContent:'center',
            alignItems:'center',padding:'4px',background:T.tss,borderRadius:7,
            border:`1px solid ${T.tssBorder}`}}>
            <div style={{fontSize:13,fontWeight:800,color:T.tssText}}>{Math.round(tssSem(sem))}</div>
            <div style={{fontSize:7,color:T.dim,textTransform:'uppercase',letterSpacing:0.5}}>TSS</div>
          </div>
        </div>
      ))}

      {/* Detalle día */}
      {diaDetalle&&(()=>{
        const acts=actsMes[diaDetalle]||[], pres=sesiones.filter(s=>getDiaKey(s.fecha)===diaDetalle)
        const label=new Date(diaDetalle+'T12:00:00').toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'long'})
        return (
          <div style={{margin:'4px 6px 6px',borderRadius:9,padding:'12px 14px',
            background:dark?'rgba(99,102,241,0.1)':'#F5F3FF',
            border:`1px solid ${dark?'rgba(99,102,241,0.25)':'#C7D2FE'}`}}>
            <div style={{fontSize:12,fontWeight:700,color:dark?'#A5B4FC':'#4F46E5',
              marginBottom:8,textTransform:'capitalize'}}>📅 {label}</div>
            {acts.length===0&&pres.length===0&&<div style={{fontSize:12,color:T.dim}}>Sin actividad</div>}
            {pres.map((s,i)=>(
              <div key={i} style={{padding:'7px 10px',borderRadius:7,marginBottom:5,
                background:dark?'rgba(255,255,255,0.04)':'#FFFFFF',
                border:`1px solid ${T.border}`,display:'flex',gap:8,alignItems:'center'}}>
                <span style={{fontSize:13}}>{s.sport==='running'?'🏃':s.sport==='cycling'?'🚴':'🏊'}</span>
                <div style={{flex:1}}>
                  <div style={{fontSize:11,fontWeight:600,color:T.text}}>{s.nombre}</div>
                  <div style={{fontSize:10,color:T.dim}}>{s.duracion_min}min · TSS {s.tss}</div>
                </div>
                <div style={{padding:'2px 7px',borderRadius:99,fontSize:9,fontWeight:600,
                  background:acts.some(a=>a.sport===s.sport)?(dark?'rgba(34,197,94,0.2)':'#DCFCE7'):(dark?'rgba(239,68,68,0.15)':'#FEE2E2'),
                  color:acts.some(a=>a.sport===s.sport)?'#22C55E':'#EF4444'}}>
                  {acts.some(a=>a.sport===s.sport)?'✓ Hecha':'✗ Pendiente'}
                </div>
              </div>
            ))}
            {acts.map((a,i)=>{
              const c=SC[a.sport]||'#94A3B8'
              const dk=(a.distance_km>500?a.distance_km/1000:a.distance_km)?.toFixed(2)
              return (
                <div key={i} style={{marginBottom:8}}>
                  <div style={{padding:'7px 10px',borderRadius:7,marginBottom:5,
                    background:dark?'rgba(255,255,255,0.04)':'#FFFFFF',
                    border:`1px solid ${c}30`,display:'flex',gap:8,alignItems:'center'}}>
                    <span style={{fontSize:13}}>{a.sport==='running'?'🏃':a.sport==='cycling'?'🚴':'🏊'}</span>
                    <div>
                      <div style={{fontSize:11,fontWeight:600,color:c}}>
                        {a.sport} · {dk}km · {Math.round(a.duration_min)}min
                      </div>
                      <div style={{fontSize:10,color:T.dim}}>
                        HR {a.hr_avg?Math.round(a.hr_avg):'--'} · TSS {a.tss_total?.toFixed(0)||'--'}
                        {a.pace?` · ${Math.floor(a.pace)}:${String(Math.round((a.pace%1)*60)).padStart(2,'0')}/km`:''}
                      </div>
                    </div>
                  </div>
                  <GraficoActividad act={a} laps={a.laps||[]} sport={a.sport} lthr={162}
                    sesionId={a.sesion_id || a.id} atletaId={atletaId}/>
                </div>
              )
            })}
          </div>
        )
      })()}
    </div>
  )
}


function CoachSesionCard({ ses, atletaId, onCambio, lthr = 162 }) {
  const [expanded, setExpanded] = useState(false)
  const [editando, setEditando] = useState(false)
  const [bloques, setBloques] = useState(ses.bloques || [])
  const [confirmDel, setConfirmDel] = useState(false)
  const [loading, setLoading] = useState(false)
  const [guardado, setGuardado] = useState(false)
  const [evalCarga, setEvalCarga] = useState(null)

  useEffect(() => {
    if (!atletaId || !ses.tss) return
    authFetch(`${API}/atletas/${atletaId}/evaluar_carga`, {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({
        tss: ses.tss,
        intensa: (ses.intensidad||'').toLowerCase().includes('umbral') ||
                 (ses.intensidad||'').toLowerCase().includes('vo2') ||
                 (ses.nombre||'').toLowerCase().includes('calidad'),
      })
    }).then(r=>r.json()).then(r=>{ if(r.data?.evaluado) setEvalCarga(r.data) }).catch(()=>{})
  }, [atletaId, ses.tss])

  const estado = getEstado(ses)
  const s = SPORT[ses.sport||'running']
  const fk = getDiaKey(ses.fecha)
  const esHoy = fk===hoyKey()
  const tssCalc = Math.round(calcularTssBloques(bloques, lthr))
  // Duración total = trabajo (dur × reps) + pausas entre repeticiones.
  // Si hay N reps, hay (N-1) pausas entre ellas (no después de la última rep).
  const durTotal = Math.round(bloques.reduce((t,b) => {
    const reps  = b.repeticiones || 1
    const dur   = b.duracion_min || 0
    const pausa = b.pausa_min || 0
    const nPausas = Math.max(0, reps - 1)
    return t + dur*reps + pausa*nPausas
  }, 0))
  const tssOrig = ses.tss || 0
  const tssDiff = tssCalc - tssOrig
  const borderLeft = estado==='done'?C.done:estado==='miss'?C.miss:estado==='partial'?C.partial:esHoy?s.color:C.border2

  const marcarEstado = async (e) => {
    setLoading(true)
    try { await axios.patch(`${API}/atletas/${atletaId}/sesiones/${ses.sesion_num||ses.id}`,{estado:e}); onCambio?.() }
    catch { alert('Error al actualizar') }
    setLoading(false)
  }
  const guardarEdicion = async () => {
    setLoading(true)
    try {
      // Convertir pace_ref_str ("5:04") a decimal (5.0667) antes de mandar al backend.
      // Si el coach no tocó el pace, se mantiene el valor decimal original.
      const bloquesAEnviar = bloques.map(b => {
        if (b.pace_ref_str !== undefined) {
          const m = b.pace_ref_str.match(/^(\d+):(\d{1,2})$/)
          const { pace_ref_str, ...resto } = b
          return { ...resto, pace_ref: m ? Number(m[1]) + Number(m[2])/60 : b.pace_ref }
        }
        return b
      })
      await axios.patch(`${API}/atletas/${atletaId}/sesiones/${ses.sesion_num||ses.id}`,
        { bloques: bloquesAEnviar, tss: tssCalc, duracion: durTotal })
      setGuardado(true); setTimeout(()=>setGuardado(false), 2000); onCambio?.()
    } catch { alert('Error al guardar') }
    setLoading(false)
  }
  const borrar = async () => {
    if (!confirmDel) { setConfirmDel(true); return }
    setLoading(true)
    try { await axios.delete(`${API}/atletas/${atletaId}/sesiones/${ses.sesion_num||ses.id}`); onCambio?.() }
    catch { alert('Error al borrar') }
    setLoading(false)
  }

  return (
    <div style={{ background:C.bg3, borderRadius:8,
      border:`1px solid ${esHoy?`${s.color}44`:C.border}`,
      borderLeft:`4px solid ${borderLeft}`, marginBottom:6, overflow:'hidden' }}>

      <div onClick={()=>{ setExpanded(e=>!e); if(editando)setEditando(false) }}
        style={{ padding:'10px 12px', cursor:'pointer', display:'flex', alignItems:'center', gap:10 }}>
        <div style={{ width:40, height:40, borderRadius:8, flexShrink:0, background:s.light,
          display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:2 }}>
          <s.Icon size={14} color={s.color} />
          <span style={{ fontSize:7, fontWeight:800, color:s.color, letterSpacing:0.8 }}>{s.short}</span>
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:13, fontWeight:600, color:C.text, lineHeight:1.2 }}>{ses.nombre}</div>
          <div style={{ fontSize:11, color:C.text2, marginTop:2, display:'flex', gap:8, flexWrap:'wrap' }}>
            <span>⏱ {durTotal} min</span>
            <span style={{ color: editando && tssDiff!==0 ? (tssDiff>0?C.miss:C.done) : C.text2 }}>
              TSS {editando ? tssCalc : tssOrig}
              {editando && tssDiff!==0 && ` (${tssDiff>0?'+':''}${tssDiff})`}
            </span>
            {fk && <span>{new Date(fk+'T12:00:00').toLocaleDateString('es-AR',{weekday:'short',day:'numeric',month:'short'})}</span>}
          </div>
        </div>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4 }}>
          {evalCarga && (
            <div title={evalCarga.mensaje} style={{
              fontSize:10, fontWeight:700, padding:'2px 8px', borderRadius:99,
              background: evalCarga.clasificacion==='adecuada'?'#10B98120':
                          evalCarga.clasificacion==='moderada'?'#F59E0B20':'#EF444420',
              color: evalCarga.clasificacion==='adecuada'?'#10B981':
                     evalCarga.clasificacion==='moderada'?'#F59E0B':'#EF4444',
              border: `1px solid ${evalCarga.clasificacion==='adecuada'?'#10B98140':
                       evalCarga.clasificacion==='moderada'?'#F59E0B40':'#EF444440'}`,
              cursor:'help',
            }}>
              {evalCarga.emoji} {evalCarga.clasificacion}
            </div>
          )}
          <SportBadge sport={ses.sport||'running'} />
          <EstadoBadge estado={estado} />
        </div>
        <span style={{ fontSize:12, color:C.text2, transform:expanded?'rotate(180deg)':'none', transition:'transform 0.2s', marginLeft:4 }}>▾</span>
      </div>

      {expanded && (
        <div style={{ borderTop:`1px solid ${C.border}`, padding:'12px 12px' }}>
          {evalCarga && (
            <div style={{
              marginBottom:12, padding:'10px 14px', borderRadius:8,
              background: evalCarga.clasificacion==='adecuada'?'#10B98110':
                          evalCarga.clasificacion==='moderada'?'#F59E0B10':'#EF444410',
              border:`1px solid ${evalCarga.clasificacion==='adecuada'?'#10B98130':
                     evalCarga.clasificacion==='moderada'?'#F59E0B30':'#EF444430'}`,
            }}>
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                <span style={{fontSize:18}}>{evalCarga.emoji}</span>
                <div>
                  <div style={{fontSize:12,fontWeight:700,color:
                    evalCarga.clasificacion==='adecuada'?'#10B981':
                    evalCarga.clasificacion==='moderada'?'#F59E0B':'#EF4444'}}>
                    NOAH — Carga {evalCarga.clasificacion}
                  </div>
                  <div style={{fontSize:11,color:C.text2}}>{evalCarga.mensaje}</div>
                </div>
              </div>
              <div style={{display:'flex',gap:16,fontSize:11,color:C.text2,marginBottom:4}}>
                <span>Absorción: <b style={{color:C.text}}>{Math.round((evalCarga.prob_absorcion||0)*100)}%</b></span>
                <span>Riesgo sobre.: <b style={{color:evalCarga.prob_riesgo>0.5?C.miss:C.text}}>{Math.round((evalCarga.prob_riesgo||0)*100)}%</b></span>
              </div>
              {evalCarga.factores?.length>0 && evalCarga.factores.map((f,i)=>(
                <div key={i} style={{fontSize:10,color:'#F59E0B'}}>⚠ {f}</div>
              ))}
            </div>
          )}
          {!editando
            ? bloques.map((b,i) => <BloqueItem key={i} bloque={b} sport={ses.sport} />)
            : bloques.map((b,i) => (
                <BloqueEditor key={i} bloque={b} sport={ses.sport} atletaId={atletaId}
                  onChange={nb => setBloques(prev => prev.map((x,j) => j===i ? nb : x))}
                  onEliminar={bloques.length>1 ? () => setBloques(prev => prev.filter((_,j)=>j!==i)) : null}
                />
              ))
          }
          {editando && (
            <button onClick={() => setBloques(prev => [...prev, {
                nombre:'Nuevo bloque', zona: ses.sport==='cycling'?'BZ2':'Z2', zona_nombre: ses.sport==='cycling'?'BZ2':'Z2',
                duracion_min:5, repeticiones:1, pausa_min:0, pausa_activa:true,
                hr_min:null, hr_max:null, watts_min:null, watts_max:null, pace_ref:null,
              }])}
              style={{ width:'100%', padding:'7px 0', marginBottom:8, borderRadius:7,
                border:`1px dashed ${C.border2}`, background:'transparent', color:C.text2,
                fontSize:11.5, fontWeight:600, cursor:'pointer' }}>
              + Agregar bloque
            </button>
          )}
          {editando && (
            <div style={{ margin:'8px 0', padding:'8px 12px', background:C.bg,
              borderRadius:6, display:'flex', gap:20, alignItems:'center', flexWrap:'wrap',
              border:`1px solid ${C.border}` }}>
              <span style={{ fontSize:12, color:C.text2 }}>Total: <b style={{ color:C.text }}>{durTotal} min</b></span>
              <span style={{ fontSize:12, color:C.text2 }}>TSS: <b style={{
                color: tssDiff>0?C.miss:tssDiff<0?C.done:C.text }}>{tssCalc}</b>
                {tssDiff!==0 && <span style={{ color:C.text2 }}> (era {tssOrig})</span>}
              </span>
              <span style={{ fontSize:11, color: tssDiff>5?C.miss:tssDiff<-5?C.done:C.text2 }}>
                {tssDiff>5?'⚠ Más carga':tssDiff<-5?'✓ Menos carga':'≈ Sin cambio'}
              </span>
            </div>
          )}
          {/* Nutrición — sesiones largas de bike */}
          {ses.descripcion && ses.descripcion.includes('Nutrición:') && (
            <div style={{ margin:'8px 0', padding:'8px 12px', background:'#F59E0B11',
              border:'1px solid #F59E0B33', borderRadius:6, fontSize:11.5, color:C.text }}>
              🍌 <b>Nutrición:</b> {ses.descripcion.split('Nutrición:')[1].trim()}
            </div>
          )}
          {/* Actividad realizada Garmin */}
          {getDiaKey(ses.fecha) <= hoyKey() && (
            <ActividadCoach
              atletaId={atletaId}
              fecha={getDiaKey(ses.fecha)}
              sport={ses.sport||'running'}
              tssPresc={ses.tss}
              lthr={lthr}
            />
          )}

          <div style={{ display:'flex', gap:6, marginTop:10, flexWrap:'wrap', alignItems:'center' }}>
            {!editando && ['done','partial','miss'].map(e=>(
              <button key={e} onClick={()=>marcarEstado(e)} disabled={loading}
                style={{ padding:'4px 11px', borderRadius:6, fontSize:11, fontWeight:600,
                  cursor:'pointer', border:`1px solid ${ESTADO[e].color}44`,
                  background:estado===e?ESTADO[e].light:'transparent', color:ESTADO[e].color }}>
                {ESTADO[e].label}
              </button>
            ))}
            <div style={{ flex:1 }} />
            {!editando
              ? <button onClick={e=>{e.stopPropagation();setEditando(true)}}
                  style={{ padding:'4px 11px', borderRadius:6, fontSize:11, fontWeight:600,
                    cursor:'pointer', border:`1px solid ${C.planned}44`, background:'transparent', color:C.planned }}>
                  ✏ Editar
                </button>
              : <>
                  <button onClick={()=>{setBloques(ses.bloques||[]);setEditando(false)}}
                    style={{ padding:'4px 11px', borderRadius:6, fontSize:11, cursor:'pointer',
                      border:`1px solid ${C.border2}`, background:'transparent', color:C.text2 }}>
                    Cancelar
                  </button>
                  <button onClick={guardarEdicion} disabled={loading}
                    style={{ padding:'4px 11px', borderRadius:6, fontSize:11, fontWeight:700,
                      cursor:'pointer', border:'none',
                      background:guardado?C.done:C.planned, color:'#fff' }}>
                    {guardado?'✓ Guardado':loading?'...':'Guardar'}
                  </button>
                </>
            }
            {!editando && (
              <button onClick={borrar} disabled={loading}
                style={{ padding:'4px 11px', borderRadius:6, fontSize:11, fontWeight:600,
                  cursor:'pointer', border:`1px solid ${C.miss}44`,
                  background:confirmDel?C.miss:'transparent', color:confirmDel?'#fff':C.miss }}>
                {confirmDel?'¿Confirmar?':'🗑'}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function AgregarSesionModal({ atletaId, onCerrar, onAgregada }) {
  const [sport,  setSport]  = useState('running')
  const [tipo,   setTipo]   = useState('aerobico')
  const [fecha,  setFecha]  = useState(new Date().toISOString().slice(0,10))
  const [dur,    setDur]    = useState(45)
  const [saving, setSaving] = useState(false)

  const TIPOS = [
    {id:'aerobico',    label:'Aeróbico Z1-Z2',   desc:'Base aeróbica, sin lactato'},
    {id:'long',        label:'Fondo largo Z1-Z2', desc:'Continuo largo, mitocondrias'},
    {id:'ftp',         label:'FTP / Umbral',      desc:'Trabajo al umbral de lactato'},
    {id:'vo2',         label:'VO2max',             desc:'Intervalos de alta intensidad'},
    {id:'neuro',       label:'Neuromuscular',      desc:'Sprints y aceleraciones'},
    {id:'recuperacion',label:'Recuperación',       desc:'Z1 suave, post-esfuerzo'},
  ]
  const DEPORTES = [{id:'running',label:'🏃 Run'},{id:'cycling',label:'🚴 Bike'},{id:'swimming',label:'🏊 Swim'}]

  const guardar = async () => {
    setSaving(true)
    try {
      await axios.post(`${API}/atletas/${atletaId}/prescripcion/sesion`,
        { sport, tipo, fecha, duracion_min: dur },
        { headers: {'Content-Type':'application/json'} }
      )
      onAgregada?.()
      onCerrar()
    } catch(e) {
      alert('Error: ' + (e?.response?.data?.error || e.message))
    }
    setSaving(false)
  }

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.6)', zIndex:1000,
      display:'flex', alignItems:'center', justifyContent:'center' }}
      onClick={e=>{ if(e.target===e.currentTarget) onCerrar() }}>
      <div style={{ background:C.bg2, borderRadius:14, padding:24, width:360, maxWidth:'90vw',
        border:`1px solid ${C.border}` }}>
        <div style={{ fontSize:15, fontWeight:700, color:C.text, marginBottom:16 }}>
          ➕ Agregar sesión manual
        </div>

        {/* Deporte */}
        <div style={{ marginBottom:14 }}>
          <div style={{ fontSize:11, color:C.text2, marginBottom:6, fontWeight:600 }}>DEPORTE</div>
          <div style={{ display:'flex', gap:6 }}>
            {DEPORTES.map(d=>(
              <button key={d.id} onClick={()=>setSport(d.id)} style={{
                flex:1, padding:'7px 4px', borderRadius:7, fontSize:12, fontWeight:600,
                cursor:'pointer', border:`1px solid ${sport===d.id?C.purple:C.border}`,
                background:sport===d.id?`${C.purple}22`:'transparent',
                color:sport===d.id?C.purple:C.text2
              }}>{d.label}</button>
            ))}
          </div>
        </div>

        {/* Tipo */}
        <div style={{ marginBottom:14 }}>
          <div style={{ fontSize:11, color:C.text2, marginBottom:6, fontWeight:600 }}>TIPO DE SESIÓN</div>
          <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
            {TIPOS.map(t=>(
              <button key={t.id} onClick={()=>setTipo(t.id)} style={{
                padding:'8px 12px', borderRadius:7, fontSize:12, fontWeight:600,
                cursor:'pointer', border:`1px solid ${tipo===t.id?C.purple:C.border}`,
                background:tipo===t.id?`${C.purple}22`:'transparent',
                color:tipo===t.id?C.purple:C.text2, textAlign:'left',
                display:'flex', justifyContent:'space-between', alignItems:'center'
              }}>
                <span>{t.label}</span>
                <span style={{ fontSize:10, color:C.text3, fontWeight:400 }}>{t.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Fecha y duración */}
        <div style={{ display:'flex', gap:10, marginBottom:18 }}>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:11, color:C.text2, marginBottom:6, fontWeight:600 }}>FECHA</div>
            <input type="date" value={fecha} onChange={e=>setFecha(e.target.value)}
              style={{ width:'100%', padding:'7px 10px', borderRadius:7, border:`1px solid ${C.border}`,
                background:C.bg3, color:C.text, fontSize:13, boxSizing:'border-box' }} />
          </div>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:11, color:C.text2, marginBottom:6, fontWeight:600 }}>DURACIÓN</div>
            <div style={{ display:'flex', alignItems:'center', gap:6 }}>
              <input type="number" value={dur} onChange={e=>setDur(Number(e.target.value))}
                min={15} max={360} step={5}
                style={{ width:'100%', padding:'7px 10px', borderRadius:7, border:`1px solid ${C.border}`,
                  background:C.bg3, color:C.text, fontSize:13 }} />
              <span style={{ fontSize:12, color:C.text2, whiteSpace:'nowrap' }}>min</span>
            </div>
          </div>
        </div>

        {/* Botones */}
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={onCerrar} style={{ flex:1, padding:'10px 0', borderRadius:8,
            border:`1px solid ${C.border}`, background:'transparent', color:C.text2,
            fontSize:13, cursor:'pointer' }}>Cancelar</button>
          <button onClick={guardar} disabled={saving} style={{ flex:2, padding:'10px 0', borderRadius:8,
            border:'none', background:C.purple, color:'#fff',
            fontSize:13, fontWeight:700, cursor:'pointer' }}>
            {saving ? 'Agregando...' : 'Agregar sesión'}
          </button>
        </div>
      </div>
    </div>
  )
}


function CoachSemana({ presc, atletaId, onCambio, atleta }) {
  const [aprobando,  setAprobando]  = useState(false)
  const [aprobado,   setAprobado]   = useState(false)
  const [modalAgregar, setModalAgregar] = useState(false)

  if (!presc?.prescripcion?.sesiones?.length) return (
    <div style={{padding:48,textAlign:'center',color:C.text2}}>
      <div style={{fontSize:32,marginBottom:12}}>📋</div>
      <div style={{fontSize:15,fontWeight:700,color:C.text,marginBottom:6}}>Sin prescripción activa</div>
      <div style={{fontSize:13,color:C.text2}}>Apretá "Nuevo ciclo" para que NOAH genere la semana.</div>
    </div>
  )

  const sesiones = presc.prescripcion.sesiones
  const yaAprobada = presc.prescripcion.estado === 'aprobada'

  const aprobarSemana = async () => {
    setAprobando(true)
    try {
      await axios.post(`${API}/atletas/${atletaId}/prescripcion/aprobar`,{},{
        headers:{'Content-Type':'application/json'}
      })
      setAprobado(true)
      setTimeout(()=>{ setAprobado(false); onCambio?.() }, 1500)
    } catch(e) {
      alert('Error al aprobar: ' + (e?.response?.data?.error || e.message))
    }
    setAprobando(false)
  }

  const porDia = {}
  sesiones.forEach(s=>{const fk=getDiaKey(s.fecha)||'sin-fecha';if(!porDia[fk])porDia[fk]=[];porDia[fk].push(s)})
  const dias = Object.keys(porDia).sort()

  const byDeporte = {running:0,cycling:0,swimming:0}
  sesiones.forEach(s=>{if(byDeporte[s.sport]!==undefined)byDeporte[s.sport]+=(s.tss||0)})

  return (
    <div>
      <div style={{display:'flex',gap:8,marginBottom:14,flexWrap:'wrap'}}>
        {Object.entries(byDeporte).filter(([,v])=>v>0).map(([dep,tss])=>{
          const s=SPORT[dep]||SPORT.running
          return (
            <div key={dep} style={{flex:1,minWidth:80,background:C.bg3,borderRadius:8,
              padding:'10px 13px',border:`1px solid ${C.border}`,borderTop:`2px solid ${s.color}`,
              display:'flex',alignItems:'center',gap:10}}>
              <div style={{width:32,height:32,borderRadius:7,background:s.light,
                display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:1}}>
                <s.Icon size={14} color={s.color}/>
                <span style={{fontSize:7,fontWeight:800,color:s.color}}>{s.short}</span>
              </div>
              <div>
                <div style={{fontSize:10,color:s.color,fontWeight:700,textTransform:'uppercase'}}>
                  {s.label}
                </div>
                <div style={{fontSize:16,fontWeight:700,color:C.text}}>TSS {tss}</div>
              </div>
            </div>
          )
        })}
        <div style={{flex:1,minWidth:80,background:C.bg3,borderRadius:8,
          padding:'10px 13px',border:`1px solid ${C.border}`,borderTop:`2px solid ${C.purple}`}}>
          <div style={{fontSize:10,color:C.purple,fontWeight:700,textTransform:'uppercase',marginBottom:4}}>TOTAL</div>
          <div style={{fontSize:16,fontWeight:700,color:C.text}}>TSS {presc.prescripcion.tss_total}</div>
        </div>
      </div>

      {dias.map(dia=>(
        <div key={dia} style={{marginBottom:10}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',
            letterSpacing:0.8,marginBottom:6,padding:'4px 0',
            borderBottom:`1px solid ${C.border}`,display:'flex',justifyContent:'space-between'}}>
            <span>{new Date(dia+'T12:00:00').toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'short'}).toUpperCase()}</span>
            <span style={{color:C.text2}}>TSS {porDia[dia].reduce((a,s)=>a+(s.tss||0),0)}</span>
          </div>
          {porDia[dia].map((ses,i)=>(
            <CoachSesionCard key={i} ses={ses} atletaId={atletaId} onCambio={onCambio} lthr={atleta?.lthr_run||162}/>
          ))}
        </div>
      ))}

      {/* Botón agregar sesión */}
      <div style={{marginTop:12,textAlign:'right'}}>
        <button onClick={()=>setModalAgregar(true)} style={{
          padding:'7px 16px', borderRadius:7, border:`1px solid ${C.purple}44`,
          background:'transparent', color:C.purple, fontSize:12,
          fontWeight:600, cursor:'pointer'
        }}>➕ Agregar sesión</button>
      </div>

      {/* Modal agregar */}
      {modalAgregar && (
        <AgregarSesionModal
          atletaId={atletaId}
          onCerrar={()=>setModalAgregar(false)}
          onAgregada={()=>{ onCambio?.(); setModalAgregar(false) }}
        />
      )}

      {/* Botón aprobar semana */}
      <div style={{marginTop:16,paddingTop:14,borderTop:`1px solid ${C.border}`}}>
        {yaAprobada
          ? <div style={{textAlign:'center',fontSize:13,color:C.done,fontWeight:600}}>
              ✓ Semana aprobada
            </div>
          : <button onClick={aprobarSemana} disabled={aprobando||aprobado} style={{
              width:'100%',padding:'11px 0',borderRadius:8,border:'none',
              background:aprobado?C.done:C.purple,color:'#fff',
              fontSize:14,fontWeight:700,cursor:'pointer'
            }}>
              {aprobado?'✓ Aprobada':aprobando?'Aprobando...':'✓ Aprobar semana'}
            </button>
        }
        <div style={{fontSize:11,color:C.text3,textAlign:'center',marginTop:6}}>
          Revisá y editá cada sesión antes de aprobar. El atleta verá la prescripción aprobada.
        </div>
      </div>
    </div>
  )
}


// ── HANNA LIFE — Gráfico de vitalidad autonómica ────────────────────────────
function HannaLifeGrafico({ atletaId, modo = 'dark' }) {
  const [data, setData]   = useState(null)
  const [hover, setHover] = useState(null)
  const [dias, setDias]   = useState(90)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/hanna_life?dias=${dias}`)
      .then(r=>r.json()).then(r=>setData(r.data)).catch(()=>{})
  }, [atletaId, dias])

  const isDark = modo === 'dark'
  const txt    = isDark ? C.text  : C.ink
  const txt2   = isDark ? C.text2 : C.ink3
  const bg     = isDark ? C.bg3   : '#F8FAFC'
  const brdr   = isDark ? C.border : '#E2E8F0'

  if (!data) return <div style={{padding:24,textAlign:'center',color:txt2}}>Cargando HANNA LIFE...</div>

  const pts = (data.puntos||[]).filter(p=>p.hanna_life!=null && p.hanna_life!==undefined)
  const hoy = data.hanna_hoy || (pts.length ? pts[pts.length-1] : {})

  const NIVEL_COLOR = {'Óptimo':'#10B981','Bueno':'#3B82F6','Moderado':'#F59E0B','Bajo':'#F97316','Crítico':'#EF4444'}
  const nColor = NIVEL_COLOR[hoy.hanna_nivel] || '#6B7280'
  const rColor = (hoy.riesgo_viral||0) >= 60 ? '#EF4444' : (hoy.riesgo_viral||0) >= 30 ? '#F59E0B' : '#10B981'

  // Semáforo de carga
  const puedeCargar = hoy.puede_cargar !== false && (hoy.hanna_life||0) >= 55
  const semaforo = puedeCargar ? {color:'#10B981',icon:'🟢',txt:'Puede cargar'} :
                   (hoy.hanna_life||0) >= 40 ? {color:'#F59E0B',icon:'🟡',txt:'Carga reducida'} :
                   {color:'#EF4444',icon:'🔴',txt:'Solo recuperación'}

  if (!pts.length) return (
    <div style={{padding:24,textAlign:'center',color:txt2,fontSize:12}}>
      Sin datos. Corré: <code>python noah_hanna_life.py --atleta {atletaId} --todo</code>
    </div>
  )

  // SVG
  const W=780, H=220, PT=32, PR=24, PB=36, PL=52
  const iW=W-PL-PR, iH=H-PT-PB
  const n = pts.length

  const hannaVals = pts.map(p=>p.hanna_life)
  const baseline  = hannaVals.length > 7
    ? hannaVals.slice(-Math.min(30,hannaVals.length)).reduce((a,b)=>a+b,0)/Math.min(30,hannaVals.length)
    : 65
  const refPob = 65

  const minY = Math.max(0,  Math.min(25, ...hannaVals) - 5)
  const maxY = Math.min(100, Math.max(85, ...hannaVals) + 5)
  const xs = i => PL + (i / Math.max(n-1,1)) * iW
  const ys = v => PT + iH - ((v-minY)/(maxY-minY||1)) * iH

  // Etiquetas eje X cada ~10 puntos
  const xLabels = []
  const step = Math.max(1, Math.floor(n/8))
  for (let i=0; i<n; i+=step) xLabels.push({i, label: pts[i].fecha.slice(5)})

  const handleMouse = e => {
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = (e.clientX-rect.left) * (W/rect.width)
    const idx = Math.max(0, Math.min(n-1, Math.round((mx-PL)/iW*(n-1))))
    setHover(idx)
  }

  // Zona crítica (bajo baseline personal -10%)
  const umbral = baseline * 0.90

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>

      {/* Cards resumen */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:10,flexWrap:'wrap'}}>

        {/* HANNA LIFE hoy */}
        <div style={{background:`${nColor}15`,borderRadius:12,padding:'16px 20px',
          border:`1px solid ${nColor}30`,borderLeft:`5px solid ${nColor}`}}>
          <div style={{fontSize:10,fontWeight:700,color:nColor,textTransform:'uppercase',letterSpacing:1,marginBottom:4}}>
            HANNA LIFE — hoy
          </div>
          <div style={{fontSize:40,fontWeight:900,color:nColor,lineHeight:1}}>
            {hoy.hanna_life?.toFixed(0)??'--'}
          </div>
          <div style={{fontSize:13,color:txt2,marginTop:4}}>{hoy.hanna_nivel||'Sin datos'}</div>
          {hoy.hanna_scores && (
            <div style={{display:'flex',gap:10,marginTop:12,flexWrap:'wrap'}}>
              {[['HRV',hoy.hanna_scores.hrv,'#8B5CF6'],
                ['FC',hoy.hanna_scores.fc,'#10B981'],
                ['Stress',hoy.hanna_scores.stress,'#F59E0B'],
                ['Sueño',hoy.hanna_scores.sueno_dur,'#3B82F6'],
                ['TSB',hoy.hanna_scores.tsb,'#6366F1']].map(([l,v,c])=>(
                <div key={l} style={{textAlign:'center',minWidth:32}}>
                  <div style={{fontSize:13,fontWeight:700,color:c}}>{v?.toFixed(0)??'--'}</div>
                  <div style={{fontSize:9,color:txt2}}>{l}</div>
                </div>
              ))}
            </div>
          )}
          {hoy.hrv_estimado && (
            <div style={{fontSize:9,color:txt2,marginTop:6,fontStyle:'italic'}}>* HRV estimado</div>
          )}
        </div>

        {/* Semáforo de carga */}
        <div style={{background:`${semaforo.color}12`,borderRadius:12,padding:'16px 20px',
          border:`1px solid ${semaforo.color}30`,
          display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:8}}>
          <div style={{fontSize:48}}>{semaforo.icon}</div>
          <div style={{fontSize:14,fontWeight:700,color:semaforo.color,textAlign:'center'}}>
            {semaforo.txt}
          </div>
          <div style={{fontSize:11,color:txt2,textAlign:'center'}}>
            {puedeCargar ? 'Sistema autónomo preparado' : 'Priorizar recuperación'}
          </div>
        </div>

        {/* Riesgo viral */}
        <div style={{background:`${rColor}12`,borderRadius:12,padding:'16px 20px',
          border:`1px solid ${rColor}30`,borderLeft:`5px solid ${rColor}`}}>
          <div style={{fontSize:10,fontWeight:700,color:rColor,textTransform:'uppercase',letterSpacing:1,marginBottom:4}}>
            Riesgo viral (RMSSD)
          </div>
          <div style={{fontSize:40,fontWeight:900,color:rColor,lineHeight:1}}>
            {hoy.riesgo_viral?.toFixed(0)??'0'}%
          </div>
          <div style={{fontSize:12,color:txt2,marginTop:4,textTransform:'capitalize'}}>
            {hoy.riesgo_viral_nivel||'bajo'}
          </div>
          <div style={{fontSize:11,color:txt2,marginTop:8}}>
            {(hoy.riesgo_viral||0) >= 60 ? '⚠ Descanso. Ver médico si hay síntomas.' :
             (hoy.riesgo_viral||0) >= 30 ? '⚡ Reducir carga. Monitorear.' :
             '✓ Sin señales de alerta.'}
          </div>
          {hoy.riesgo_viral_alertas?.length > 0 && (
            <div style={{marginTop:8,display:'flex',flexDirection:'column',gap:3}}>
              {hoy.riesgo_viral_alertas.map((a,i)=>(
                <div key={i} style={{fontSize:10,color:a.nivel==='alto'?'#EF4444':'#F59E0B'}}>
                  ▸ {a.msg}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Selector días */}
      <div style={{display:'flex',gap:6,alignItems:'center'}}>
        <span style={{fontSize:11,color:txt2}}>Período:</span>
        {[30,60,90,180].map(d=>(
          <button key={d} onClick={()=>setDias(d)} style={{
            padding:'3px 10px',borderRadius:5,cursor:'pointer',fontSize:11,
            border:`1px solid ${dias===d?'#8B5CF6':brdr}`,
            background:dias===d?'#8B5CF622':'transparent',
            color:dias===d?'#8B5CF6':txt2
          }}>{d}d</button>
        ))}
        <span style={{fontSize:10,color:txt2,marginLeft:8}}>{n} días con datos</span>
      </div>

      {/* Gráfico */}
      <div style={{background:bg,borderRadius:12,padding:'12px 8px',
        border:`1px solid ${brdr}`,overflowX:'auto'}}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          style={{display:'block',maxWidth:'100%',cursor:'crosshair'}}
          onMouseMove={handleMouse} onMouseLeave={()=>setHover(null)}>

          {/* Zonas de fondo */}
          <rect x={PL} y={PT} width={iW} height={ys(80)-PT} fill="#10B98106"/>
          <rect x={PL} y={ys(80)} width={iW} height={ys(65)-ys(80)} fill="#3B82F606"/>
          <rect x={PL} y={ys(65)} width={iW} height={ys(50)-ys(65)} fill="#F59E0B06"/>
          <rect x={PL} y={ys(50)} width={iW} height={ys(35)-ys(50)} fill="#F9731606"/>
          <rect x={PL} y={ys(35)} width={iW} height={PT+iH-ys(35)} fill="#EF444408"/>

          {/* Zona de riesgo bajo baseline */}
          {pts.map((p,i)=>{
            if (i===0||!pts[i-1]) return null
            const prev=pts[i-1]
            if (p.hanna_life < umbral || prev.hanna_life < umbral) {
              return <rect key={i} x={xs(i-1)} y={ys(umbral)}
                width={xs(i)-xs(i-1)} height={Math.max(0,PT+iH-ys(umbral))}
                fill="#EF444412"/>
            }
            return null
          })}

          {/* Línea umbral crítico */}
          <line x1={PL} y1={ys(umbral)} x2={W-PR} y2={ys(umbral)}
            stroke="#EF4444" strokeWidth="1" strokeDasharray="3,3" opacity={0.4}/>

          {/* Línea baseline personal */}
          <line x1={PL} y1={ys(baseline)} x2={W-PR} y2={ys(baseline)}
            stroke="#F59E0B" strokeWidth="1.5" strokeDasharray="8,4" opacity={0.7}/>
          <text x={W-PR-4} y={ys(baseline)-5} textAnchor="end" fontSize="10"
            fill="#F59E0B" opacity={0.9}>👤 {baseline.toFixed(0)}</text>

          {/* Línea referencia poblacional */}
          <line x1={PL} y1={ys(refPob)} x2={W-PR} y2={ys(refPob)}
            stroke="#3B82F6" strokeWidth="1.5" strokeDasharray="5,4" opacity={0.6}/>
          <text x={W-PR-4} y={ys(refPob)-5} textAnchor="end" fontSize="10"
            fill="#3B82F6" opacity={0.8}>⚡ {refPob}</text>

          {/* Íconos eje Y grandes */}
          <text x={PL-8} y={ys(88)} textAnchor="middle" fontSize="20" dominantBaseline="middle">🔋</text>
          <text x={PL-8} y={ys(50)} textAnchor="middle" fontSize="16" dominantBaseline="middle">⚡</text>
          <text x={PL-8} y={ys(20)} textAnchor="middle" fontSize="20" dominantBaseline="middle">🪫</text>

          {/* Curva — segmentos coloreados */}
          {pts.slice(1).map((p,i)=>{
            const prev=pts[i]
            const c=NIVEL_COLOR[p.hanna_nivel]||'#6B7280'
            const isPuntual = pts[i].hanna_life!=null && p.hanna_life!=null
            return isPuntual ? <line key={i}
              x1={xs(i).toFixed(1)} y1={ys(prev.hanna_life).toFixed(1)}
              x2={xs(i+1).toFixed(1)} y2={ys(p.hanna_life).toFixed(1)}
              stroke={c} strokeWidth="2.5" strokeLinecap="round" opacity={0.9}/> : null
          })}

          {/* Puntos — sólidos si son reales, huecos si estimados */}
          {pts.map((p,i)=>{
            const c=NIVEL_COLOR[p.hanna_nivel]||'#6B7280'
            const isHover = hover===i
            return p.hrv ? (
              <circle key={i} cx={xs(i)} cy={ys(p.hanna_life)} r={isHover?6:3}
                fill={c} stroke={isDark?'rgba(255,255,255,0.3)':'white'} strokeWidth="1.5"/>
            ) : (
              <circle key={i} cx={xs(i)} cy={ys(p.hanna_life)} r={isHover?5:2.5}
                fill="none" stroke={c} strokeWidth="1.5"/>
            )
          })}

          {/* Punto hover con tooltip */}
          {hover !== null && hover < pts.length && (
            <>
              <line x1={xs(hover)} y1={PT} x2={xs(hover)} y2={PT+iH}
                stroke={isDark?'rgba(255,255,255,0.15)':'rgba(0,0,0,0.08)'} strokeWidth="1"/>
              <rect x={Math.min(xs(hover)+10,W-PR-145)} y={PT+2}
                width={140} height={pts[hover].hrv?100:85} rx={8}
                fill={isDark?'rgba(10,10,20,0.97)':'rgba(255,255,255,0.97)'}
                stroke={NIVEL_COLOR[pts[hover].hanna_nivel]||'#6B7280'} strokeWidth="1.5"/>
              <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+16}
                fontSize="9" fill={txt2}>{pts[hover].fecha}</text>
              <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+30}
                fontSize="13" fontWeight="800"
                fill={NIVEL_COLOR[pts[hover].hanna_nivel]||'#6B7280'}>
                {pts[hover].hanna_life?.toFixed(0)} — {pts[hover].hanna_nivel}
              </text>
              {pts[hover].hrv && <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+44}
                fontSize="10" fill="#8B5CF6" fontWeight="600">
                HRV: {pts[hover].hrv?.toFixed(1)}ms
              </text>}
              {pts[hover].bb && <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+57}
                fontSize="10" fill={txt2}>BB: {Math.round(pts[hover].bb)}</text>}
              {pts[hover].sleep && <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+70}
                fontSize="10" fill={txt2}>Sueño: {pts[hover].sleep?.toFixed(1)}h</text>}
              {pts[hover].stress && <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+83}
                fontSize="10" fill={txt2}>Stress: {pts[hover].stress?.toFixed(0)}</text>}
              <text x={Math.min(xs(hover)+16,W-PR-139)} y={PT+(pts[hover].hrv?97:83)}
                fontSize="9" fill={pts[hover].riesgo_viral>30?'#EF4444':'#10B981'}>
                Riesgo viral: {pts[hover].riesgo_viral?.toFixed(0)||'0'}%
              </text>
            </>
          )}

          {/* Eje Y */}
          {[20,35,50,65,80,100].map(v=>(v>=minY&&v<=maxY)&&(
            <text key={v} x={PL-24} y={ys(v)+4} textAnchor="end" fontSize="8"
              fill={isDark?'rgba(255,255,255,0.25)':C.ink4}>{v}</text>
          ))}

          {/* Eje X */}
          {xLabels.map(({i,label})=>(
            <text key={i} x={xs(i)} y={H-PB+16} textAnchor="middle" fontSize="8"
              fill={isDark?'rgba(255,255,255,0.3)':C.ink4}>{label}</text>
          ))}
        </svg>
      </div>

      {/* Leyenda */}
      <div style={{display:'flex',gap:12,flexWrap:'wrap',alignItems:'center'}}>
        {Object.entries(NIVEL_COLOR).map(([nivel,color])=>(
          <div key={nivel} style={{display:'flex',alignItems:'center',gap:4}}>
            <div style={{width:12,height:3,background:color,borderRadius:2}}/>
            <span style={{fontSize:10,color:txt2}}>{nivel}</span>
          </div>
        ))}
        <span style={{fontSize:10,color:txt2,marginLeft:4,opacity:0.7}}>
          ● HRV real · ○ estimado · 👤 Tu baseline · ⚡ Ref. población
        </span>
      </div>

      {/* Nota */}
      <div style={{fontSize:10,color:txt2,opacity:0.55,fontStyle:'italic'}}>
        HANNA LIFE = HRV×25% + FC×15% + Stress×10% + Sueño dur×15% + Sueño cal×15% + TSB×15% + Monotonía×5%
        · Riesgo viral basado en RMSSD (Buchheit 2014, Tedesco 2023)
      </div>
    </div>
  )
}


function HannaLife3D({ atletaId, modo = 'light' }) {
  const [data, setData]   = useState(null)
  const [rotY, setRotY]   = useState(30)   // rotación Y (mouse drag)
  const [drag, setDrag]   = useState(null)
  const [hover, setHover] = useState(null)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/hanna_life?dias=60`)
      .then(r=>r.json()).then(r=>setData(r.data)).catch(()=>{})
  }, [atletaId])

  const isDark = modo === 'dark'
  const bg   = isDark ? '#0f0f1a' : '#F8FAFC'
  const txt  = isDark ? 'rgba(255,255,255,0.85)' : '#1E293B'
  const txt2 = isDark ? 'rgba(255,255,255,0.4)'  : '#64748B'
  const grid = isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)'

  // ── Proyección 3D isométrica ───────────────────────────────────────────────
  const W=720, H=340
  const CX=360, CY=200  // centro de proyección
  const SCALE = { x:6, y:1.6, z:0.7 }

  const toScreen = (xi, yi, zi) => {
    // Rotación Y paramétrica
    const rad = rotY * Math.PI / 180
    const rx = xi * Math.cos(rad) - zi * Math.sin(rad)
    const rz = xi * Math.sin(rad) + zi * Math.cos(rad)
    return {
      sx: CX + rx * SCALE.x,
      sy: CY - yi * SCALE.y - rz * SCALE.z
    }
  }

  // ── Drag para rotar ────────────────────────────────────────────────────────
  const onMouseDown = (e) => setDrag(e.clientX)
  const onMouseMove = (e) => {
    if (drag === null) return
    setRotY(r => Math.max(-60, Math.min(60, r + (e.clientX - drag) * 0.3)))
    setDrag(e.clientX)
  }
  const onMouseUp = () => setDrag(null)

  if (!data) return (
    <div style={{padding:40,textAlign:'center',color:txt2,fontSize:13}}>
      Cargando HANNA LIFE 3D...
    </div>
  )

  const pts = (data.puntos||[]).filter(p=>p.hanna_life!=null)
  if (pts.length < 3) return (
    <div style={{padding:40,textAlign:'center',color:txt2,fontSize:13}}>
      Sin suficientes datos para el gráfico 3D.<br/>
      Corré: <code>python noah_hanna_life.py --atleta {atletaId} --todo</code>
    </div>
  )

  const n = pts.length
  const NIVEL_COLOR = {
    'Óptimo':'#10B981','Bueno':'#3B82F6',
    'Moderado':'#F59E0B','Bajo':'#F97316','Crítico':'#EF4444'
  }

  // Normalizar datos
  const hannaVals  = pts.map(p=>p.hanna_life||0)
  const stressVals = pts.map(p=>p.stress||50)
  const maxStress  = Math.max(...stressVals, 1)

  // Baseline poblacional por edad/sexo (ya viene en el endpoint como referencia)
  const baselinePob  = 65  // HANNA LIFE referencia población activa
  // Baseline personal: media móvil 30d del atleta
  const baselinePerso = hannaVals.length > 5
    ? hannaVals.slice(0, Math.min(30, hannaVals.length)).reduce((a,b)=>a+b,0) / Math.min(30,hannaVals.length)
    : baselinePob

  // Puntos de la curva 3D
  // xi = índice de tiempo (0..n-1)
  // yi = HANNA LIFE (0..100)
  // zi = stress normalizado (0..10)
  const screenPts = pts.map((p,i) => ({
    ...toScreen(i, p.hanna_life||0, (p.stress||50)/maxStress*10),
    hanna: p.hanna_life,
    stress: p.stress,
    nivel: p.hanna_nivel,
    fecha: p.fecha,
    i,
  }))

  // Baseline poblacional line
  const basePobPts = [0, n-1].map(i => toScreen(i, baselinePob, 0))
  // Baseline personal line
  const basePersoPts = [0, n-1].map(i => toScreen(i, baselinePerso, 0))

  // Grid del piso (eje Y=0)
  const gridLines = []
  for (let xi=0; xi<=n-1; xi+=Math.max(1,Math.floor(n/8))) {
    const p0 = toScreen(xi, 0, 0)
    const p1 = toScreen(xi, 0, 10)
    gridLines.push(<line key={`gx${xi}`} x1={p0.sx} y1={p0.sy} x2={p1.sx} y2={p1.sy} stroke={grid} strokeWidth="1"/>)
  }
  for (let zi=0; zi<=10; zi+=2) {
    const p0 = toScreen(0, 0, zi)
    const p1 = toScreen(n-1, 0, zi)
    gridLines.push(<line key={`gz${zi}`} x1={p0.sx} y1={p0.sy} x2={p1.sx} y2={p1.sy} stroke={grid} strokeWidth="1"/>)
  }

  // Líneas verticales desde la curva al piso (sombra)
  const shadows = screenPts.map((sp,i) => {
    const floor = toScreen(i, 0, (pts[i].stress||50)/maxStress*10)
    return <line key={`s${i}`} x1={sp.sx} y1={sp.sy} x2={floor.sx} y2={floor.sy}
      stroke={NIVEL_COLOR[sp.nivel]||'#6B7280'} strokeWidth="0.5" opacity={0.2}/>
  })

  // Path principal de la curva
  const pathMain = screenPts.map((sp,i)=>`${i===0?'M':'L'}${sp.sx.toFixed(1)},${sp.sy.toFixed(1)}`).join(' ')

  // Path baseline poblacional
  const pathPob = basePobPts.map((p,i)=>`${i===0?'M':'L'}${p.sx.toFixed(1)},${p.sy.toFixed(1)}`).join(' ')
  // Path baseline personal
  const pathPerso = basePersoPts.map((p,i)=>`${i===0?'M':'L'}${p.sx.toFixed(1)},${p.sy.toFixed(1)}`).join(' ')

  // Eje Y — iconos de salud
  const yAxisPts = [
    { yi: 85, icon: '🔋', label: 'Óptimo',   color: '#10B981' },
    { yi: baselinePob, icon: '⚡', label: 'Referencia', color: '#3B82F6' },
    { yi: baselinePerso, icon: '👤', label: 'Tu baseline', color: '#F59E0B' },
    { yi: 25, icon: '🪫', label: 'Alerta',   color: '#EF4444' },
  ]

  // Punto hover
  const hoverPt = hover !== null ? screenPts[hover] : null

  return (
    <div style={{display:'flex',flexDirection:'column',gap:12}}>

      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:8}}>
        <div>
          <div style={{fontSize:13,fontWeight:700,color:txt}}>HANNA LIFE — Vista 3D</div>
          <div style={{fontSize:11,color:txt2}}>
            Eje X: tiempo · Eje Y: vitalidad · Eje Z: estrés fisiológico · Arrastrá para rotar
          </div>
        </div>
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          {[
            {label:'── Curva real', color: isDark?'white':'#1E293B'},
            {label:'╌╌ Ref. poblacional', color:'#3B82F6'},
            {label:'╌╌ Tu baseline', color:'#F59E0B'},
          ].map(({label,color})=>(
            <div key={label} style={{fontSize:10,color,display:'flex',alignItems:'center',gap:4}}>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* SVG 3D */}
      <div style={{background:bg,borderRadius:12,border:`1px solid ${isDark?'rgba(255,255,255,0.08)':'#E2E8F0'}`,
        overflow:'hidden',cursor:drag!==null?'grabbing':'grab',userSelect:'none'}}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          style={{display:'block',maxWidth:'100%'}}
          onMouseDown={onMouseDown} onMouseMove={onMouseMove}
          onMouseUp={onMouseUp} onMouseLeave={onMouseUp}>

          {/* Grid piso */}
          {gridLines}

          {/* Sombras */}
          {shadows}

          {/* Zona de riesgo — debajo del baseline personal */}
          <defs>
            <linearGradient id="riesgoGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#EF4444" stopOpacity="0.0"/>
              <stop offset="100%" stopColor="#EF4444" stopOpacity="0.15"/>
            </linearGradient>
          </defs>

          {/* Baseline poblacional */}
          <path d={pathPob} fill="none" stroke="#3B82F6" strokeWidth="1.5"
            strokeDasharray="8,4" opacity={0.7}/>
          {/* Label baseline pob */}
          {basePobPts[1] && (
            <text x={basePobPts[1].sx+4} y={basePobPts[1].sy+4}
              fontSize="10" fill="#3B82F6" opacity={0.8}>⚡ {baselinePob.toFixed(0)}</text>
          )}

          {/* Baseline personal */}
          <path d={pathPerso} fill="none" stroke="#F59E0B" strokeWidth="1.5"
            strokeDasharray="5,3" opacity={0.8}/>
          {basePersoPts[1] && (
            <text x={basePersoPts[1].sx+4} y={basePersoPts[1].sy+4}
              fontSize="10" fill="#F59E0B" opacity={0.9}>👤 {baselinePerso.toFixed(0)}</text>
          )}

          {/* Curva principal — segmentos coloreados por nivel */}
          {screenPts.slice(1).map((sp,i)=>{
            const prev = screenPts[i]
            const color = NIVEL_COLOR[sp.nivel] || '#6B7280'
            return <line key={i}
              x1={prev.sx} y1={prev.sy} x2={sp.sx} y2={sp.sy}
              stroke={color} strokeWidth="2.5" opacity={0.9}
              strokeLinecap="round"/>
          })}

          {/* Puntos en la curva */}
          {screenPts.map((sp,i)=>(
            <circle key={i} cx={sp.sx} cy={sp.sy}
              r={hover===i?6:2.5}
              fill={NIVEL_COLOR[sp.nivel]||'#6B7280'}
              stroke={hover===i?(isDark?'white':'#1E293B'):'none'}
              strokeWidth="1.5"
              style={{cursor:'pointer'}}
              onMouseEnter={()=>setHover(i)}
              onMouseLeave={()=>setHover(null)}
            />
          ))}

          {/* Iconos eje Y */}
          {yAxisPts.map(({yi,icon,label,color})=>{
            const p = toScreen(-2, yi, 0)
            return (
              <g key={label}>
                <text x={p.sx-8} y={p.sy+5} textAnchor="middle" fontSize="14">{icon}</text>
                <text x={p.sx+2} y={p.sy+5} fontSize="9" fill={color} opacity={0.7}>{yi.toFixed(0)}</text>
              </g>
            )
          })}

          {/* Tooltip hover */}
          {hoverPt && hover !== null && (
            <g>
              <rect x={Math.min(hoverPt.sx+10,W-140)} y={hoverPt.sy-60}
                width={130} height={70} rx={8}
                fill={isDark?'rgba(15,15,26,0.95)':'rgba(255,255,255,0.97)'}
                stroke={NIVEL_COLOR[hoverPt.nivel]||'#6B7280'} strokeWidth="1.5"/>
              <text x={Math.min(hoverPt.sx+16,W-134)} y={hoverPt.sy-44}
                fontSize="9" fill={txt2}>{hoverPt.fecha}</text>
              <text x={Math.min(hoverPt.sx+16,W-134)} y={hoverPt.sy-30}
                fontSize="12" fontWeight="700" fill={NIVEL_COLOR[hoverPt.nivel]}>
                HANNA {hoverPt.hanna?.toFixed(0)} — {hoverPt.nivel}
              </text>
              <text x={Math.min(hoverPt.sx+16,W-134)} y={hoverPt.sy-16}
                fontSize="10" fill={txt2}>
                Stress: {hoverPt.stress?.toFixed(0)||'--'}
              </text>
              {/* Indicador zona */}
              <text x={Math.min(hoverPt.sx+16,W-134)} y={hoverPt.sy-3}
                fontSize="10" fill={
                  (hoverPt.hanna||0) >= baselinePob ? '#10B981' :
                  (hoverPt.hanna||0) >= baselinePerso ? '#F59E0B' : '#EF4444'
                } fontWeight="600">
                {(hoverPt.hanna||0) >= baselinePob ? '▲ Sobre referencia' :
                 (hoverPt.hanna||0) >= baselinePerso ? '◆ En tu baseline' : '▼ Bajo tu baseline'}
              </text>
            </g>
          )}

          {/* Eje tiempo — etiquetas */}
          {pts.filter((_,i)=>i===0||i===Math.floor(n/2)||i===n-1).map((p,i)=>{
            const idx = i===0?0:i===1?Math.floor(n/2):n-1
            const sp = toScreen(idx, 0, 0)
            return (
              <text key={i} x={sp.sx} y={sp.sy+14} textAnchor="middle"
                fontSize="9" fill={txt2}>{pts[idx]?.fecha?.slice(5)||''}</text>
            )
          })}

          {/* Label rotación */}
          <text x={W-8} y={16} textAnchor="end" fontSize="9" fill={txt2} opacity={0.5}>
            ↔ {rotY.toFixed(0)}°
          </text>
        </svg>
      </div>

      {/* Leyenda niveles */}
      <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
        {Object.entries(NIVEL_COLOR).map(([nivel,color])=>(
          <div key={nivel} style={{display:'flex',alignItems:'center',gap:5}}>
            <div style={{width:10,height:10,borderRadius:'50%',background:color}}/>
            <span style={{fontSize:10,color:txt2}}>{nivel}</span>
          </div>
        ))}
        <div style={{fontSize:10,color:txt2,marginLeft:8,opacity:0.6}}>
          · Eje Z (profundidad) = estrés fisiológico
        </div>
      </div>

      {/* Interpretación */}
      <div style={{display:'flex',gap:12,flexWrap:'wrap'}}>
        {[
          {icon:'🔋',label:'Sobre referencia poblacional',desc:'Vitalidad óptima',color:'#10B981'},
          {icon:'⚡',label:'En línea con referencia',desc:'Nivel saludable normal',color:'#3B82F6'},
          {icon:'👤',label:'En tu baseline personal',desc:'Tu estado típico',color:'#F59E0B'},
          {icon:'🪫',label:'Bajo tu baseline',desc:'Riesgo de enfermedad o sobrecarga',color:'#EF4444'},
        ].map(({icon,label,desc,color})=>(
          <div key={label} style={{display:'flex',gap:8,alignItems:'flex-start',
            padding:'8px 12px',borderRadius:8,background:`${color}10`,
            border:`1px solid ${color}25`,flex:'1 1 180px'}}>
            <span style={{fontSize:18,flexShrink:0}}>{icon}</span>
            <div>
              <div style={{fontSize:11,fontWeight:600,color}}>{label}</div>
              <div style={{fontSize:10,color:txt2}}>{desc}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


function TabDiagnostico({ diag }) {
  if (!diag) return <div style={{ padding:24, color:C.text2, textAlign:'center', fontSize:13 }}>Cargando...</div>
  if (diag.error) return <div style={{ padding:24, color:C.text2 }}>{diag.resumen_coach||'Sin datos.'}</div>
  const colMap = { verde:C.done, amarillo:C.amber, rojo:C.miss }
  const sc = colMap[diag.color]||C.text2
  const dist = diag.distribucion||{}
  const real = dist.distribucion_real||{}
  const ideal = dist.distribucion_ideal||{}
  const gaps = dist.gaps||{}
  const proy = diag.proyeccion||{}
  const barData = [{zona:'Z1-Z2',real:real.z1z2_pct||0,ideal:ideal.z1z2_pct||0},{zona:'Z3-Z4',real:real.z3z4_pct||0,ideal:ideal.z3z4_pct||0},{zona:'Z5-Z6',real:real.z5z6_pct||0,ideal:ideal.z5z6_pct||0}]
  const proyData = (proy.con_patron_actual?.proyeccion||[]).map((v,i)=>({semana:`S${i+1}`,actual:v,correcto:proy.con_correccion?.proyeccion?.[i]}))

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
      <Card>
        <div style={{ padding:'14px 18px', display:'flex', alignItems:'center', gap:14 }}>
          <div style={{ width:52,height:52,borderRadius:'50%',background:`${sc}18`,border:`2px solid ${sc}`,display:'flex',alignItems:'center',justifyContent:'center',fontSize:17,fontWeight:800,color:sc }}>{diag.score_general}</div>
          <div>
            <div style={{ fontSize:14, fontWeight:600, marginBottom:4 }}>{diag.resumen_coach}</div>
            <div style={{ fontSize:12, color:C.text2 }}>{dist.total_horas}h · {dist.sesiones_n} sesiones · fase {dist.fase}</div>
          </div>
        </div>
      </Card>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
        <div>
          <SectionTitle>Distribución real vs ideal</SectionTitle>
          <Card style={{ padding:14 }}>
            <ResponsiveContainer width="100%" height={170}>
              <BarChart data={barData} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="zona" tick={{ fill:C.text2, fontSize:11 }} />
                <YAxis tick={{ fill:C.text2, fontSize:10 }} unit="%" />
                <Tooltip contentStyle={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:8, fontFamily:'Inter', fontSize:12 }} formatter={v=>`${v}%`} />
                <Bar dataKey="real" name="Real" fill={C.purple} radius={[3,3,0,0]} />
                <Bar dataKey="ideal" name="Ideal" fill={C.teal} radius={[3,3,0,0]} opacity={0.5} />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ marginTop:10 }}>
              {[['Z1-Z2',real.z1z2_pct,ideal.z1z2_pct,gaps.z1z2],['Z3-Z4',real.z3z4_pct,ideal.z3z4_pct,gaps.z3z4]].map(([z,r,id,g])=>(
                <div key={z} style={{ display:'flex', justifyContent:'space-between', fontSize:11, padding:'4px 0', borderBottom:`1px solid ${C.border}`, color:C.text2 }}>
                  <span>{z}</span><span>Real <b style={{ color:C.text }}>{r}%</b></span><span>Ideal <b style={{ color:C.teal }}>{id}%</b></span><span style={{ color:g>0?C.miss:C.done }}>{g>0?'+':''}{g}%</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
        <div>
          <SectionTitle>Proyección CTL — 16 semanas</SectionTitle>
          <Card style={{ padding:14 }}>
            <ResponsiveContainer width="100%" height={170}>
              <LineChart data={proyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="semana" tick={{ fill:C.text2, fontSize:9 }} interval={3} />
                <YAxis tick={{ fill:C.text2, fontSize:10 }} />
                <Tooltip contentStyle={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:8, fontFamily:'Inter', fontSize:12 }} />
                <Line type="monotone" dataKey="actual" name="Sin cambio" stroke={C.amber} dot={false} strokeWidth={2} strokeDasharray="4 3" />
                <Line type="monotone" dataKey="correcto" name="Con corrección" stroke={C.teal} dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <div style={{ marginTop:8, fontSize:12, color:C.text2 }}>CTL actual: <b style={{ color:C.text }}>{proy.ctl_actual}</b>{proy.con_correccion?.ganancia>0&&<span style={{ color:C.done, marginLeft:8 }}>+{proy.con_correccion.ganancia} con corrección</span>}</div>
          </Card>
        </div>
      </div>
      {diag.alertas?.length>0&&(
        <div>
          <SectionTitle>Alertas NOA</SectionTitle>
          <Card>
            {diag.alertas.map((a,i)=>(
              <div key={i} style={{ padding:'11px 14px', borderBottom:`1px solid ${C.border}`, display:'flex', gap:10 }}>
                <div style={{ width:3, borderRadius:2, background:{alto:C.miss,moderado:C.amber,info:C.blue}[a.nivel]||C.text2, flexShrink:0 }} />
                <div>
                  <div style={{ fontSize:10, fontWeight:700, color:{alto:C.miss,moderado:C.amber,info:C.blue}[a.nivel]||C.text2, marginBottom:3, textTransform:'uppercase', letterSpacing:0.8 }}>{a.nivel}</div>
                  <div style={{ fontSize:13, color:C.text2 }}>{a.texto_coach}</div>
                </div>
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  )
}

// ── Modal nuevo atleta ────────────────────────────────────────────────────────
function ModalNuevoAtleta({ onClose, onCreado }) {
  const [form, setForm] = useState({ nombre:'', email:'', lthr_run:155, hr_max:185, edad:'', deporte_ppal:'running' })
  const [loading, setLoading] = useState(false)
  const handleSubmit = async () => {
    if (!form.nombre||!form.email) return alert('Nombre y email requeridos')
    setLoading(true)
    try { await axios.post(`${API}/atletas`,form); onCreado(); onClose() }
    catch { alert('Error creando atleta') }
    setLoading(false)
  }
  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.7)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:100 }}>
      <div style={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:14, padding:26, width:400, maxWidth:'90vw' }}>
        <div style={{ fontSize:15, fontWeight:700, marginBottom:18 }}>Nuevo atleta</div>
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          {[['nombre','Nombre completo','text'],['email','Email','email'],['lthr_run','LTHR Running','number'],['hr_max','FC Máxima','number'],['edad','Edad','number']].map(([key,label,type])=>(
            <div key={key}><label>{label}</label><input type={type} value={form[key]} onChange={e=>setForm(f=>({...f,[key]:e.target.value}))} /></div>
          ))}
          <div><label>Deporte principal</label>
            <select value={form.deporte_ppal} onChange={e=>setForm(f=>({...f,deporte_ppal:e.target.value}))}>
              <option value="running">Running</option>
              <option value="triatlon">Triatlón</option>
              <option value="cycling">Ciclismo</option>
              <option value="swimming">Natación</option>
            </select>
          </div>
        </div>
        <div style={{ display:'flex', gap:8, marginTop:20, justifyContent:'flex-end' }}>
          <button onClick={onClose} style={{ padding:'8px 16px', borderRadius:7, border:`1px solid ${C.border}`, background:C.bg3, color:C.text, cursor:'pointer', fontSize:13, fontWeight:500 }}>Cancelar</button>
          <button onClick={handleSubmit} disabled={loading} style={{ padding:'8px 16px', borderRadius:7, border:'none', background:C.purple, color:'#fff', cursor:'pointer', fontSize:13, fontWeight:600 }}>{loading?'Creando...':'Crear atleta'}</button>
        </div>
      </div>
    </div>
  )
}



// ── Curva de Periodización A/T/R/Taper ───────────────────────────────────────

// ── Modelo Banister por deporte — Tab Fases ───────────────────────────────────
function ModeloBanisterFases({ atletaId }) {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [deporte, setDeporte] = useState('todos')   // 'todos' | 'running' | 'cycling' | 'swimming'
  const [hover, setHover]   = useState(null)
  const svgRef = useRef(null)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/fases`)
      .then(r => r.json())
      .then(r => { setData(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId])

  if (loading) return <div style={{padding:32,textAlign:'center',color:C.text2}}>Calculando PMC...</div>
  if (!data)   return <div style={{padding:32,textAlign:'center',color:C.text2}}>Sin datos</div>

  // ── Colores ───────────────────────────────────────────────────────────────
  const SPORT_C = { running:'#8B5CF6', cycling:'#38BDF8', swimming:'#34D399', todos:'#F59E0B' }
  const FASE_C  = { A:'#6366F1', T:'#F59E0B', R:'#EF4444', Taper:'#10B981' }

  // ── Datos según deporte seleccionado ─────────────────────────────────────
  const getSeriesData = () => {
    if (deporte === 'todos') {
      // Usar datos globales del atleta (suma de deportes)
      const d = data.deportes?.running || data.deportes?.[Object.keys(data.deportes||{})[0]]
      return d ? { hist: d.hist || [], proy: d.proy || [] } : { hist:[], proy:[] }
    }
    const d = data.deportes?.[deporte]
    return d ? { hist: d.hist || [], proy: d.proy || [] } : { hist:[], proy:[] }
  }

  const { hist, proy } = getSeriesData()
  const todos_pts = [...hist, ...proy]
  if (!todos_pts.length) return <div style={{padding:32,textAlign:'center',color:C.text2}}>Sin datos para este deporte</div>

  // ── Dimensiones ───────────────────────────────────────────────────────────
  const W=720, H=300, PT=32, PB=48, PL=52, PR=60
  const iW=W-PL-PR, iH=H-PT-PB

  // Escalas Y
  const ctlVals = todos_pts.map(p=>p.ctl||0)
  const atlVals = todos_pts.map(p=>p.atl||0)
  const tsbVals = todos_pts.map(p=>p.tsb||0)
  const maxY    = Math.max(...ctlVals, ...atlVals) + 10
  const minY    = Math.min(...tsbVals) - 8
  const rangeY  = maxY - minY || 1

  const xs = i  => PL + (i / Math.max(todos_pts.length-1, 1)) * iW
  const ys = v  => PT + iH - ((v - minY) / rangeY) * iH
  const y0  = ys(0)

  // ── Paths ─────────────────────────────────────────────────────────────────
  const mkPath = (arr, key, offset=0) =>
    arr.map((p,i) => `${i===0?'M':'L'}${xs(i+offset).toFixed(1)},${ys(p[key]||0).toFixed(1)}`).join(' ')

  const mkArea = (arr, key, offset=0) => {
    const pts = arr.map((p,i) => `${xs(i+offset).toFixed(1)},${ys(p[key]||0).toFixed(1)}`).join(' L')
    const n = arr.length - 1
    return `M${xs(offset).toFixed(1)},${ys(arr[0]?.[key]||0).toFixed(1)} L${pts} L${xs(n+offset).toFixed(1)},${y0.toFixed(1)} L${xs(offset).toFixed(1)},${y0.toFixed(1)} Z`
  }

  // CTL área bajo la curva
  const ctlHistArea = hist.length > 1 ? mkArea(hist, 'ctl') : ''
  const tsbHistArea = hist.filter(p=>(p.tsb||0)>0).length > 1 ? '' : ''

  // ── Bandas de fases proyectadas ────────────────────────────────────────────
  const bandas = []
  let cur = null
  proy.forEach((p,i) => {
    const xi = hist.length + i
    if (!cur || cur.fase !== p.fase) {
      if (cur) bandas.push(cur)
      cur = { fase:p.fase, xS:xi, xE:xi }
    } else { cur.xE = xi }
  })
  if (cur) bandas.push(cur)

  // ── Líneas de referencia Y ────────────────────────────────────────────────
  const yTicks = []
  const step = rangeY > 80 ? 20 : rangeY > 40 ? 10 : 5
  for (let v = Math.ceil(minY/step)*step; v <= maxY; v += step) yTicks.push(v)

  // ── X labels — mostrar cada N semanas ─────────────────────────────────────
  const xLabels = todos_pts.reduce((acc, p, i) => {
    if (i % Math.max(1, Math.floor(todos_pts.length/10)) === 0)
      acc.push({ i, label: (p.f||'').slice(5) }) // MM-DD
    return acc
  }, [])

  // ── Hover handler ─────────────────────────────────────────────────────────
  const handleMouse = e => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx = (e.clientX - rect.left) * (W / rect.width)
    const idx = Math.max(0, Math.min(todos_pts.length-1,
      Math.round((mx - PL) / iW * (todos_pts.length-1))))
    setHover({ i:idx, x:xs(idx), p:todos_pts[idx] })
  }

  // ── Punto actual (último histórico) ───────────────────────────────────────
  const actual = hist[hist.length-1] || {}
  const xHoy   = xs(hist.length-1)
  const tsbColor = (actual.tsb||0) > 5 ? '#10B981' : (actual.tsb||0) < -15 ? '#EF4444' : '#F59E0B'

  const deportes = Object.keys(data.deportes || {})

  return (
    <div style={{ background:C.bg2, borderRadius:12, overflow:'hidden',
      border:`1px solid ${C.border}` }}>

      {/* ── Header ───────────────────────────────────────────────────────── */}
      <div style={{ padding:'14px 20px', borderBottom:`1px solid ${C.border}`,
        display:'flex', alignItems:'center', gap:12, flexWrap:'wrap',
        background:'linear-gradient(90deg,rgba(99,102,241,0.1),transparent)' }}>
        <div style={{ fontSize:13, fontWeight:700, color:C.text }}>
          📈 Performance Management Chart
        </div>

        {/* Selector de deporte */}
        <div style={{ display:'flex', gap:4, marginLeft:'auto' }}>
          {['todos', ...deportes].map(d => {
            const s = SPORT[d] || { color: '#F59E0B', short: 'ALL' }
            return (
              <button key={d} onClick={() => setDeporte(d)} style={{
                padding:'3px 10px', borderRadius:6, fontSize:10, fontWeight:700,
                cursor:'pointer', border:`1px solid ${deporte===d ? (SPORT_C[d]||'#F59E0B')+'80' : C.border}`,
                background: deporte===d ? `${SPORT_C[d]||'#F59E0B'}22` : 'transparent',
                color: deporte===d ? (SPORT_C[d]||'#F59E0B') : C.text2,
              }}>
                {d === 'todos' ? 'TODO' : d.toUpperCase().slice(0,4)}
              </button>
            )
          })}
        </div>
      </div>

      {/* ── Métricas actuales ────────────────────────────────────────────── */}
      <div style={{ padding:'12px 20px', display:'flex', gap:8,
        borderBottom:`1px solid ${C.border}`, flexWrap:'wrap' }}>
        {[
          { label:'CTL', val:actual.ctl?.toFixed(1), color:'#6366F1', desc:'Fitness' },
          { label:'ATL', val:actual.atl?.toFixed(1), color:'#EF4444', desc:'Fatiga' },
          { label:'TSB', val:actual.tsb?.toFixed(1), color:tsbColor, desc:'Forma' },
          actual.fase && { label:'FASE', val:actual.fase, color:FASE_C[actual.fase]||C.text2, desc:'' },
        ].filter(Boolean).map((m,i) => (
          <div key={i} style={{ flex:1, minWidth:70,
            background:C.bg3, borderRadius:8, padding:'8px 12px',
            borderTop:`2px solid ${m.color}`, border:`1px solid ${C.border}`,
            borderTopColor: m.color }}>
            <div style={{ fontSize:9, color:C.text2, textTransform:'uppercase',
              letterSpacing:0.8, marginBottom:4 }}>{m.label} · {m.desc}</div>
            <div style={{ fontSize:20, fontWeight:800, color:m.color }}>{m.val??'--'}</div>
          </div>
        ))}

        {/* Tooltip inline cuando hay hover */}
        {hover?.p && (
          <div style={{ marginLeft:'auto', display:'flex', gap:10, alignItems:'center',
            padding:'6px 14px', borderRadius:8, fontSize:11,
            background:C.bg3, border:`1px solid ${C.border}` }}>
            <span style={{ color:C.text2, fontSize:10 }}>{hover.p.f}</span>
            <span style={{ color:'#6366F1', fontWeight:700 }}>CTL {hover.p.ctl}</span>
            <span style={{ color:'#EF4444', fontWeight:700 }}>ATL {hover.p.atl}</span>
            <span style={{ color: (hover.p.tsb||0)>0?'#10B981':'#F59E0B', fontWeight:700 }}>
              TSB {hover.p.tsb}
            </span>
            {hover.p.fase && (
              <span style={{ color:FASE_C[hover.p.fase]||C.text2, fontWeight:600, fontSize:10 }}>
                {hover.p.fase}
              </span>
            )}
          </div>
        )}
      </div>

      {/* ── SVG Principal ────────────────────────────────────────────────── */}
      <div style={{ padding:'8px 0 0' }}>
        <svg ref={svgRef} width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          style={{ display:'block', maxWidth:'100%', cursor:'crosshair' }}
          onMouseMove={handleMouse} onMouseLeave={() => setHover(null)}>

          <defs>
            {/* Gradiente CTL */}
            <linearGradient id={`gCTL_${atletaId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#6366F1" stopOpacity="0.35"/>
              <stop offset="100%" stopColor="#6366F1" stopOpacity="0.03"/>
            </linearGradient>
            {/* Gradiente TSB positivo */}
            <linearGradient id={`gTSBpos_${atletaId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#10B981" stopOpacity="0.25"/>
              <stop offset="100%" stopColor="#10B981" stopOpacity="0.02"/>
            </linearGradient>
            {/* Gradiente TSB negativo */}
            <linearGradient id={`gTSBneg_${atletaId}`} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%"   stopColor="#EF4444" stopOpacity="0.20"/>
              <stop offset="100%" stopColor="#EF4444" stopOpacity="0.02"/>
            </linearGradient>
          </defs>

          {/* Bandas de fase proyectadas */}
          {bandas.map((b,i) => (
            <g key={i}>
              <rect x={xs(b.xS)} y={PT} width={Math.max(2,xs(b.xE)-xs(b.xS)+iW/Math.max(todos_pts.length-1,1))}
                height={iH} fill={FASE_C[b.fase]||'#888'} opacity={0.08}/>
              <text x={(xs(b.xS)+xs(b.xE))/2} y={PT+14}
                textAnchor="middle" fontSize="10" fill={FASE_C[b.fase]||C.text2}
                fontWeight="800" opacity="0.9">{b.fase}</text>
            </g>
          ))}

          {/* Grid horizontal */}
          {yTicks.map(v => (
            <line key={v} x1={PL} y1={ys(v)} x2={W-PR} y2={ys(v)}
              stroke={v===0 ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.05)'}
              strokeWidth={v===0 ? 1.5 : 1}/>
          ))}

          {/* Área CTL histórico */}
          {ctlHistArea && (
            <path d={ctlHistArea} fill={`url(#gCTL_${atletaId})`}/>
          )}

          {/* Área TSB positivo */}
          {hist.length > 1 && (
            <path
              d={hist.map((p,i) => {
                const v = Math.max(0, p.tsb||0)
                return `${i===0?'M':'L'}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`
              }).join(' ') + ` L${xs(hist.length-1)},${y0} L${xs(0)},${y0} Z`}
              fill={`url(#gTSBpos_${atletaId})`}
            />
          )}

          {/* Área TSB negativo (rojo) */}
          {hist.length > 1 && (
            <path
              d={hist.map((p,i) => {
                const v = Math.min(0, p.tsb||0)
                return `${i===0?'M':'L'}${xs(i).toFixed(1)},${ys(v).toFixed(1)}`
              }).join(' ') + ` L${xs(hist.length-1)},${y0} L${xs(0)},${y0} Z`}
              fill={`url(#gTSBneg_${atletaId})`}
            />
          )}

          {/* Curva ATL histórico */}
          {hist.length > 1 && (
            <path d={mkPath(hist,'atl')} fill="none"
              stroke="#EF4444" strokeWidth="1.5" opacity="0.7" strokeDasharray="4,2"/>
          )}

          {/* Curva ATL proyectado */}
          {proy.length > 1 && (
            <path d={mkPath(proy,'atl',hist.length)} fill="none"
              stroke="#EF4444" strokeWidth="1" opacity="0.4" strokeDasharray="4,3"/>
          )}

          {/* Curva CTL histórico */}
          {hist.length > 1 && (
            <path d={mkPath(hist,'ctl')} fill="none"
              stroke="#6366F1" strokeWidth="2.5" opacity="0.9"/>
          )}

          {/* Curva CTL proyectado */}
          {proy.length > 1 && (
            <path d={mkPath(proy,'ctl',hist.length)} fill="none"
              stroke="#6366F1" strokeWidth="2" opacity="0.5" strokeDasharray="6,3"/>
          )}

          {/* Curva TSB histórico */}
          {hist.length > 1 && (
            <path d={mkPath(hist,'tsb')} fill="none"
              stroke="#10B981" strokeWidth="2.5" opacity="0.95"/>
          )}

          {/* Curva TSB proyectado */}
          {proy.length > 1 && (
            <path d={mkPath(proy,'tsb',hist.length)} fill="none"
              stroke="#10B981" strokeWidth="2" opacity="0.55" strokeDasharray="6,3"/>
          )}

          {/* Línea "hoy" */}
          <line x1={xHoy} y1={PT} x2={xHoy} y2={PT+iH}
            stroke="rgba(255,255,255,0.35)" strokeWidth="1.5" strokeDasharray="4,3"/>
          <text x={xHoy+4} y={PT+11} fontSize="9" fill="rgba(255,255,255,0.5)">HOY</text>

          {/* Punto actual CTL */}
          <circle cx={xHoy} cy={ys(actual.ctl||0)} r={5}
            fill="#6366F1" stroke="white" strokeWidth="2"/>
          {/* Punto actual TSB */}
          <circle cx={xHoy} cy={ys(actual.tsb||0)} r={5}
            fill={tsbColor} stroke="white" strokeWidth="2"/>

          {/* Zona óptima TSB (5 a 25) — franja verde suave */}
          <rect x={PL} y={ys(25)} width={iW} height={Math.max(0,ys(5)-ys(25))}
            fill="rgba(16,185,129,0.06)" rx="0"/>

          {/* Línea hover */}
          {hover && (
            <>
              <line x1={hover.x} y1={PT} x2={hover.x} y2={PT+iH}
                stroke="rgba(255,255,255,0.25)" strokeWidth="1"/>
              <circle cx={hover.x} cy={ys(hover.p?.ctl||0)} r={4}
                fill="#6366F1" stroke="white" strokeWidth="1.5"/>
              <circle cx={hover.x} cy={ys(hover.p?.atl||0)} r={3}
                fill="#EF4444" stroke="white" strokeWidth="1.5"/>
              <circle cx={hover.x} cy={ys(hover.p?.tsb||0)} r={4}
                fill={tsbColor} stroke="white" strokeWidth="1.5"/>
            </>
          )}

          {/* Eje Y izquierdo */}
          {yTicks.map(v => (
            <text key={v} x={PL-5} y={ys(v)+4} textAnchor="end"
              fontSize="9" fill={v===0?'rgba(255,255,255,0.4)':'rgba(255,255,255,0.25)'}>
              {v}
            </text>
          ))}
          <text x={14} y={H/2} textAnchor="middle" fontSize="9"
            fill="rgba(99,102,241,0.6)"
            transform={`rotate(-90,14,${H/2})`}>CTL / ATL / TSB</text>

          {/* Eje X — fechas */}
          {xLabels.map(({ i, label }) => (
            <text key={i} x={xs(i)} y={H-PB+16} textAnchor="middle"
              fontSize="8" fill="rgba(255,255,255,0.25)">{label}</text>
          ))}
        </svg>
      </div>

      {/* ── Leyenda + Zona óptima ─────────────────────────────────────────── */}
      <div style={{ padding:'8px 20px 14px', display:'flex', gap:16,
        alignItems:'center', flexWrap:'wrap', borderTop:`1px solid ${C.border}` }}>
        {[
          { color:'#6366F1', label:'CTL (Fitness)',    dash:false },
          { color:'#EF4444', label:'ATL (Fatiga)',     dash:true  },
          { color:'#10B981', label:'TSB (Forma)',      dash:false },
        ].map((l,i) => (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:5 }}>
            <div style={{
              width:18, height:l.dash?0:3,
              borderTop: l.dash?`2px dashed ${l.color}`:'none',
              background: l.dash?'transparent':l.color,
              borderRadius:2
            }}/>
            <span style={{ fontSize:10, color:C.text2 }}>{l.label}</span>
          </div>
        ))}
        <div style={{ display:'flex', alignItems:'center', gap:5 }}>
          <div style={{ width:16, height:8, borderRadius:2,
            background:'rgba(16,185,129,0.15)',
            border:'1px solid rgba(16,185,129,0.3)' }}/>
          <span style={{ fontSize:10, color:C.text2 }}>Zona óptima TSB (5-25)</span>
        </div>
        <span style={{ fontSize:9, color:C.text3, marginLeft:'auto' }}>
          {hist.length} días histórico · {proy.length} proyectado
        </span>
      </div>

      {/* ── Cards por deporte ─────────────────────────────────────────────── */}
      <div style={{ padding:'0 20px 16px', display:'flex', gap:8, flexWrap:'wrap' }}>
        {deportes.map(dep => {
          const dd = data.deportes?.[dep]
          const act = dd?.hist?.[dd.hist.length-1] || {}
          const sc = SPORT[dep] || { color:'#888', short:dep.slice(0,3).toUpperCase() }
          const tsbC = (act.tsb||0)>5?'#10B981':(act.tsb||0)<-15?'#EF4444':'#F59E0B'
          return (
            <div key={dep} onClick={() => setDeporte(dep)} style={{
              flex:1, minWidth:100, borderRadius:8, padding:'10px 12px',
              background: deporte===dep ? `${sc.color}18` : C.bg3,
              border:`1px solid ${deporte===dep ? sc.color+'60' : C.border}`,
              cursor:'pointer', transition:'all 0.15s',
            }}>
              <div style={{ fontSize:10, fontWeight:700, color:sc.color,
                textTransform:'uppercase', marginBottom:6 }}>
                {dep}
              </div>
              <div style={{ display:'flex', gap:8, fontSize:11 }}>
                <span style={{ color:'#6366F1', fontWeight:700 }}>CTL {act.ctl?.toFixed(0)||'--'}</span>
                <span style={{ color:tsbC, fontWeight:700 }}>TSB {act.tsb?.toFixed(0)||'--'}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function CurvaPeriodizacion({ atletaId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/periodizacion`)
      .then(r => r.json())
      .then(r => { setData(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId])

  if (loading) return <div style={{ padding:24, color:C.text2, fontSize:13 }}>Cargando curva...</div>
  if (!data)   return <div style={{ padding:24, color:C.text2, fontSize:13 }}>Sin datos de periodización</div>

  const FASE_COLOR = { A:'#6366f1', T:'#f59e0b', R:'#ef4444', Taper:'#22c55e' }
  const FASE_LABEL = { A:'Acumulación', T:'Transformación', R:'Realización', Taper:'Taper' }
  const FASE_DESC  = {
    A:     'Construir la base aeróbica. Volumen alto, intensidad baja.',
    T:     'Convertir la base en rendimiento. Trabajo de umbral.',
    R:     'Pico de rendimiento. Velocidad específica de carrera.',
    Taper: 'Reducción de carga. Llegar fresco y activado a la carrera.',
  }

  // Combinar histórico + proyectado para el gráfico
  const todos = [
    ...data.historico.map(p => ({ ...p, real: p.ctl, proy: null })),
    ...data.proyectado.map(p => ({ ...p, real: null, proy: p.ctl })),
  ]

  // Calcular dimensiones del gráfico SVG
  const W = 900, H = 260, PL = 48, PR = 20, PT = 20, PB = 40
  const GW = W - PL - PR, GH = H - PT - PB

  const todas_fechas = todos.map(p => p.fecha).sort()
  const min_fecha = todas_fechas[0]
  const max_fecha = data.carrera.fecha

  const ctls = todos.map(p => p.real || p.proy || 0)
  const max_ctl = Math.max(...ctls, data.ctl_objetivo || 80) * 1.1
  const min_ctl = 0

  const xScale = (fecha) => {
    const total = new Date(max_fecha) - new Date(min_fecha)
    const pos   = new Date(fecha)    - new Date(min_fecha)
    return PL + (pos / total) * GW
  }
  const yScale = (ctl) => PT + GH - ((ctl - min_ctl) / (max_ctl - min_ctl)) * GH

  // Paths SVG
  const pathReal = todos.filter(p => p.real !== null)
    .map((p, i) => `${i===0?'M':'L'}${xScale(p.fecha)},${yScale(p.real)}`).join(' ')

  const pathProy = todos.filter(p => p.proy !== null)
    .map((p, i) => `${i===0?'M':'L'}${xScale(p.fecha)},${yScale(p.proy)}`).join(' ')

  // Línea CTL objetivo
  const yObj = yScale(data.ctl_objetivo)

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>

      {/* Leyenda de fases */}
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        {data.fases.map((f, i) => (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:6,
            padding:'4px 12px', borderRadius:99,
            background:`${FASE_COLOR[f.fase]}22`,
            border:`1px solid ${FASE_COLOR[f.fase]}44` }}>
            <div style={{ width:8, height:8, borderRadius:2,
              background:FASE_COLOR[f.fase] }} />
            <span style={{ fontSize:12, fontWeight:700, color:FASE_COLOR[f.fase] }}>
              {f.fase}
            </span>
            <span style={{ fontSize:11, color:C.text2 }}>{FASE_LABEL[f.fase]}</span>
          </div>
        ))}
        <div style={{ display:'flex', alignItems:'center', gap:6,
          padding:'4px 12px', borderRadius:99,
          background:'#ffffff11', border:`1px solid ${C.border}` }}>
          <div style={{ width:16, height:2, background:C.text, opacity:0.5 }} />
          <span style={{ fontSize:11, color:C.text2 }}>Real</span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:6,
          padding:'4px 12px', borderRadius:99,
          background:'#ffffff11', border:`1px solid ${C.border}` }}>
          <div style={{ width:16, height:2, background:C.purple,
            borderTop:'2px dashed' }} />
          <span style={{ fontSize:11, color:C.text2 }}>Proyectado</span>
        </div>
      </div>

      {/* Gráfico SVG */}
      <div style={{ background:C.bg3, borderRadius:12, padding:'16px 8px',
        border:`1px solid ${C.border}`, overflowX:'auto' }}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          style={{ minWidth:W }}>

          {/* Fondo de fases coloreado */}
          {data.fases.map((f, i) => {
            const x1 = xScale(f.desde)
            const x2 = xScale(f.hasta)
            return (
              <rect key={i} x={x1} y={PT} width={Math.max(1,x2-x1)} height={GH}
                fill={FASE_COLOR[f.fase]} opacity={0.08} />
            )
          })}

          {/* Líneas de grilla horizontal */}
          {[0, 25, 50, 75, 100].filter(v => v <= max_ctl).map(v => (
            <g key={v}>
              <line x1={PL} x2={W-PR} y1={yScale(v)} y2={yScale(v)}
                stroke={C.border} strokeWidth={0.5} opacity={0.5} />
              <text x={PL-4} y={yScale(v)+4} textAnchor="end"
                style={{ fontSize:10, fill:C.text2 }}>{v}</text>
            </g>
          ))}

          {/* Línea CTL objetivo */}
          <line x1={PL} x2={W-PR} y1={yObj} y2={yObj}
            stroke={C.purple} strokeWidth={1} strokeDasharray="4,4" opacity={0.5} />
          <text x={W-PR-2} y={yObj-4} textAnchor="end"
            style={{ fontSize:9, fill:C.purple }}>obj {data.ctl_objetivo}</text>

          {/* Labels de fases en el gráfico */}
          {data.fases.map((f, i) => {
            const xMid = (xScale(f.desde) + xScale(f.hasta)) / 2
            return (
              <text key={i} x={xMid} y={PT+14} textAnchor="middle"
                style={{ fontSize:10, fontWeight:'bold',
                  fill:FASE_COLOR[f.fase], opacity:0.8 }}>
                {f.fase}
              </text>
            )
          })}

          {/* Curva CTL real */}
          {pathReal && (
            <path d={pathReal} fill="none"
              stroke={C.text} strokeWidth={2} opacity={0.7} />
          )}

          {/* Curva CTL proyectado */}
          {pathProy && (
            <path d={pathProy} fill="none"
              stroke={C.purple} strokeWidth={2}
              strokeDasharray="6,3" opacity={0.9} />
          )}

          {/* Marcador de hoy */}
          {(() => {
            const xHoy = xScale(new Date().toISOString().slice(0,10))
            return (
              <g>
                <line x1={xHoy} x2={xHoy} y1={PT} y2={PT+GH}
                  stroke="#fff" strokeWidth={1} opacity={0.3} />
                <text x={xHoy+3} y={PT+10}
                  style={{ fontSize:9, fill:'#fff', opacity:0.5 }}>hoy</text>
              </g>
            )
          })()}

          {/* Marcador de la carrera */}
          {(() => {
            const xCar = xScale(data.carrera.fecha)
            return (
              <g>
                <line x1={xCar} x2={xCar} y1={PT} y2={PT+GH}
                  stroke={C.done} strokeWidth={2} opacity={0.8} />
                <text x={xCar-3} y={PT+10} textAnchor="end"
                  style={{ fontSize:9, fill:C.done, fontWeight:'bold' }}>
                  🏁 {data.carrera.nombre}
                </text>
              </g>
            )
          })()}

          {/* Eje X — fechas */}
          {[...data.historico, ...data.proyectado]
            .filter((_, i) => i % 30 === 0)
            .map((p, i) => (
              <text key={i} x={xScale(p.fecha)} y={H-8} textAnchor="middle"
                style={{ fontSize:9, fill:C.text2 }}>
                {p.fecha.slice(5)}
              </text>
            ))
          }
        </svg>
      </div>

      {/* Cards de fases */}
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        {data.fases.map((f, i) => (
          <div key={i} style={{ flex:1, minWidth:140,
            background:C.bg3, borderRadius:10, padding:'12px 14px',
            border:`1px solid ${C.border}`,
            borderTop:`3px solid ${FASE_COLOR[f.fase]}` }}>
            <div style={{ fontSize:13, fontWeight:700,
              color:FASE_COLOR[f.fase], marginBottom:4 }}>
              {f.fase} — {FASE_LABEL[f.fase]}
            </div>
            <div style={{ fontSize:11, color:C.text2, marginBottom:6 }}>
              {FASE_DESC[f.fase]}
            </div>
            <div style={{ fontSize:10, color:C.text2 }}>
              {f.desde.slice(5)} → {f.hasta.slice(5)}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}


// ── Plan Coach Chart — usa el mismo endpoint que el atleta ───────────────────
function PlanCoachChart({ atletaId }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/periodizacion`)
      .then(r=>r.json()).then(r=>setData(r.data)).catch(()=>{})
  }, [atletaId])
  if (!data) return <div style={{padding:32,textAlign:'center',color:C.text2}}>Cargando...</div>
  const COLORES = {'A':'#6366F1','T':'#F59E0B','R':'#EF4444','TAPER':'#10B981'}
  const LABELS = {'A':'Acumulación','T':'Transformación','R':'Realización','TAPER':'Taper'}
  const hist = data?.historico || []
  const proy = data?.proyectado || []
  const todos = [...hist,...proy]
  if (!todos.length) return <div style={{padding:20,color:C.text2}}>Sin datos de planificación</div>
  const ctls = todos.map(p=>p.ctl)
  const minC=Math.max(0,Math.min(...ctls)-5),maxC=Math.max(...ctls)+10
  const W=620,H=200,PT=24,PR=20,PB=30,PL=44
  const iW=W-PL-PR,iH=H-PT-PB
  const xs=i=>PL+(i/Math.max(todos.length-1,1))*iW
  const ys=v=>PT+iH-((v-minC)/(maxC-minC||1))*iH
  // Usar fases del endpoint si están disponibles
  const fasesData = data?.fases || []
  const bandas = fasesData.length > 0
    ? fasesData.map(f => {
        const iS = todos.findIndex(p => p.fecha >= f.desde)
        const iE = todos.reduce((last, p, i) => p.fecha <= f.hasta ? i : last, iS)
        return { fase: f.fase, xS: Math.max(0,iS), xE: Math.max(0,iE), color: f.color }
      }).filter(b => b.xS >= 0)
    : (() => {
        const bs=[];let cur=null
        proy.forEach((p,i)=>{const xi=hist.length+i;if(!cur||cur.fase!==p.fase){if(cur)bs.push(cur);cur={fase:p.fase,xS:xi,xE:xi}}else{cur.xE=xi}});if(cur)bs.push(cur)
        return bs
      })()
  const pP=proy.map((p,i)=>{const xi=hist.length+i;return `${i===0?'M':'L'}${xs(xi).toFixed(1)},${ys(p.ctl).toFixed(1)}`}).join(' ')
  const pH=hist.map((p,i)=>`${i===0?'M':'L'}${xs(i).toFixed(1)},${ys(p.ctl).toFixed(1)}`).join(' ')
  const xU=hist.length>0?xs(hist.length-1):PL
  const yO=ys(data.ctl_objetivo)
  return (
    <div style={{display:'flex',flexDirection:'column',gap:10}}>
      <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
        {['A','T','R','TAPER'].map(f=>(
          <div key={f} style={{display:'flex',alignItems:'center',gap:4}}>
            <div style={{width:10,height:10,borderRadius:2,background:COLORES[f]}}/>
            <span style={{fontSize:10,color:C.text2}}>{LABELS[f]}</span>
          </div>
        ))}
      </div>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{display:'block',maxWidth:'100%'}}>
        {bandas.map((b,i)=>(
          <rect key={i} x={xs(b.xS)} y={PT} width={Math.max(2,xs(b.xE)-xs(b.xS))} height={iH} fill={b.color||COLORES[b.fase]||'#888'} opacity={0.12}/>
        ))}
        {bandas.map((b,i)=>(
          <text key={i} x={(xs(b.xS)+xs(b.xE))/2} y={PT+12} textAnchor="middle" fontSize="10" fill={b.color||COLORES[b.fase]||'#888'} fontWeight="800">{b.fase}</text>
        ))}
        <line x1={PL} y1={yO} x2={W-PR} y2={yO} stroke={C.border2} strokeWidth="1" strokeDasharray="4,3"/>
        <text x={W-PR-2} y={yO-3} textAnchor="end" fontSize="8" fill={C.text2}>obj {data.ctl_objetivo}</text>
        <line x1={xU} y1={PT} x2={xU} y2={PT+iH} stroke={C.border2} strokeWidth="1" strokeDasharray="2,2"/>
        <text x={xU+2} y={PT+9} fontSize="8" fill={C.text2}>hoy</text>
        <line x1={xs(todos.length-1)} y1={PT} x2={xs(todos.length-1)} y2={PT+iH} stroke="#10B981" strokeWidth="1.5"/>
        <text x={xs(todos.length-1)-2} y={PT+10} textAnchor="end" fontSize="9" fill="#10B981" fontWeight="700">🏁</text>
        {hist.length>1&&<path d={pH} fill="none" stroke={C.border2} strokeWidth="1.5"/>}
        {proy.length>1&&<path d={pP} fill="none" stroke={C.text} strokeWidth="2" opacity={0.85}/>}
        {hist.length>0&&<circle cx={xs(hist.length-1)} cy={ys(hist[hist.length-1]?.ctl||0)} r={4} fill={C.run} stroke={C.bg} strokeWidth="2"/>}
        {[minC,Math.round((minC+maxC)/2),maxC].map(v=>(
          <text key={v} x={PL-4} y={ys(v)+3} textAnchor="end" fontSize="8" fill={C.text2}>{Math.round(v)}</text>
        ))}
      </svg>
      <div style={{display:'flex',gap:14,flexWrap:'wrap',fontSize:11,color:C.text2}}>
        <span>🏁 <b style={{color:C.text}}>{data.carrera_nombre}</b> {data.carrera_fecha}</span>
        <span>CTL {data.ctl_actual} → obj {data.ctl_objetivo}</span>
        <span style={{color:'#10B981'}}>Taper -{data.taper_reduccion_pct}%</span>
      </div>
    </div>
  )
}

// ── NOAH Intelligence Panel ───────────────────────────────────────────────────
function NOAHIntelPanel({ atletaId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [entrenado, setEntrenado] = useState(false)
  const [sinModelo, setSinModelo] = useState(false)
  const [errorMsg, setErrorMsg] = useState(null)

  const cargar = async () => {
    setLoading(true)
    setSinModelo(false)
    setErrorMsg(null)
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/noah_intel`)
      const json = await r.json()
      if (json.data?.error) {
        const msg = json.data.error || ''
        if (msg.toLowerCase().includes('no entrenado') || msg.toLowerCase().includes('entrenar')) {
          setSinModelo(true)
        } else {
          setErrorMsg(msg)
        }
      } else {
        setData(json.data)
        setEntrenado(true)
      }
    } catch (e) {
      setErrorMsg('No se pudo conectar con el servidor: ' + e.message)
    }
    setLoading(false)
  }

  const reentrenar = async () => {
    if (!window.confirm('Re-entrenar tarda ~30 segundos. ¿Continuar?')) return
    setLoading(true)
    setSinModelo(false)
    setErrorMsg(null)
    try {
      await authFetch(`${API}/atletas/${atletaId}/noah_intel/entrenar`, {method:'POST'})
      await cargar()
    } catch (e) {
      setErrorMsg('Error al re-entrenar: ' + e.message)
    }
    setLoading(false)
  }

  const adaptIcon = (t) => t==='mejorando'?'📈':t==='empeorando'?'📉':'➡'
  const adaptColor = (t) => t==='mejorando'?C.done:t==='empeorando'?C.miss:C.text2

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:14 }}>

      {/* Header */}
      <div style={{ background:`linear-gradient(135deg, ${C.purple}22, ${C.purple}08)`,
        borderRadius:10, padding:'14px 18px',
        border:`1px solid ${C.purple}44`,
        display:'flex', justifyContent:'space-between', alignItems:'center' }}>
        <div>
          <div style={{ fontSize:15, fontWeight:700, color:C.text }}>🧠 NOAH Intelligence</div>
          <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>
            ML entrenado con el historial completo del atleta
          </div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={cargar} disabled={loading} style={{
            padding:'7px 16px', borderRadius:7, border:'none',
            background:C.purple, color:'#fff', cursor:'pointer',
            fontSize:12, fontWeight:600 }}>
            {loading ? '⏳ Cargando...' : entrenado ? '🔄 Actualizar' : '▶ Analizar'}
          </button>
          {entrenado && (
            <button onClick={reentrenar} disabled={loading} style={{
              padding:'7px 12px', borderRadius:7,
              border:`1px solid ${C.border}`, background:'transparent',
              color:C.text2, cursor:'pointer', fontSize:11 }}>
              ⚙ Re-entrenar
            </button>
          )}
        </div>
      </div>

      {/* Estado: sin modelo ML entrenado */}
      {sinModelo && !loading && (
        <div style={{ textAlign:'center', padding:32, background:`${C.amber}11`,
          border:`1px solid ${C.amber}44`, borderRadius:10 }}>
          <div style={{ fontSize:24, marginBottom:8 }}>🧠</div>
          <div style={{ fontSize:14, fontWeight:700, color:C.amber, marginBottom:6 }}>
            Modelo ML no entrenado todavía
          </div>
          <div style={{ fontSize:12, color:C.text2, marginBottom:16 }}>
            NOAH Intel necesita datos históricos para entrenar su modelo.
            El análisis de ML es opcional — el ciclo semanal funciona sin él.
          </div>
          <button onClick={reentrenar} disabled={loading} style={{
            padding:'8px 20px', borderRadius:7, border:'none',
            background:C.amber, color:'#000', cursor:'pointer',
            fontSize:12, fontWeight:700 }}>
            ⚙ Entrenar modelo ahora
          </button>
        </div>
      )}

      {/* Estado: error general */}
      {errorMsg && !loading && (
        <div style={{ textAlign:'center', padding:24, background:`${C.miss}11`,
          border:`1px solid ${C.miss}44`, borderRadius:10 }}>
          <div style={{ fontSize:13, color:C.miss, fontWeight:600, marginBottom:4 }}>
            ⚠ Error al cargar Intel
          </div>
          <div style={{ fontSize:12, color:C.text2 }}>{errorMsg}</div>
        </div>
      )}

      {/* Estado: sin datos aún, esperando primer análisis */}
      {!data && !loading && !sinModelo && !errorMsg && (
        <div style={{ textAlign:'center', padding:32, color:C.text2, fontSize:13 }}>
          Hacé click en "Analizar" para ver el análisis de ML
        </div>
      )}

      {data && (
        <>
          {/* TSS recomendado */}
          {data.tss_recomendado && (
            <Card>
              <div style={{ padding:'14px 18px' }}>
                <SectionTitle>TSS semanal recomendado por ML</SectionTitle>
                <div style={{ display:'flex', gap:16, alignItems:'center', flexWrap:'wrap' }}>
                  <div style={{ fontSize:36, fontWeight:800, color:C.purple }}>
                    {data.tss_recomendado.tss_recomendado}
                  </div>
                  <div style={{ flex:1 }}>
                    <div style={{ fontSize:12, color:C.text2, marginBottom:4 }}>
                      {data.tss_recomendado.explicacion}
                    </div>
                    <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
                      {[
                        ['TSB', data.tss_recomendado.factor_tsb],
                        ['HRV', data.tss_recomendado.factor_hrv],
                        ['Sobre', data.tss_recomendado.factor_sobre],
                      ].map(([label, factor]) => (
                        <span key={label} style={{
                          fontSize:11, padding:'2px 8px', borderRadius:99,
                          background: factor >= 1 ? C.doneL : C.missL,
                          color: factor >= 1 ? C.done : C.miss,
                          fontWeight:600
                        }}>{label} ×{factor}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {/* Adaptación por deporte */}
          {data.adaptacion && (
            <div>
              <SectionTitle>Adaptación por deporte — últimas 8 semanas</SectionTitle>
              <Card>
                {Object.entries(data.adaptacion).map(([dep, d]) => {
                  if (d.tendencia === 'sin_datos') return null
                  const s = SPORT[dep] || SPORT.running
                  return (
                    <div key={dep} style={{ padding:'12px 16px',
                      borderBottom:`1px solid ${C.border}`,
                      display:'flex', alignItems:'center', gap:12 }}>
                      <div style={{ width:36, height:36, borderRadius:8,
                        background:s.light, display:'flex', flexDirection:'column',
                        alignItems:'center', justifyContent:'center', gap:1 }}>
                        <s.Icon size={14} color={s.color} />
                        <span style={{ fontSize:7, fontWeight:800, color:s.color }}>{s.short}</span>
                      </div>
                      <div style={{ flex:1 }}>
                        <div style={{ fontSize:13, fontWeight:600, color:C.text }}>{s.label}</div>
                        <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>
                          {d.metrica || 'pace/eficiencia'}
                          {d.css_actual && ` · CSS ${d.css_actual} min/100m`}
                          {d.ftp_ultimo && ` · FTP ~${d.ftp_ultimo}W`}
                          {d.pace_ultimo && ` · Pace Z2 ${d.pace_ultimo} min/km`}
                        </div>
                      </div>
                      <div style={{ textAlign:'right' }}>
                        <div style={{ fontSize:20 }}>{adaptIcon(d.tendencia)}</div>
                        <div style={{ fontSize:12, fontWeight:700,
                          color:adaptColor(d.tendencia) }}>
                          {d.tendencia} {d.mejora_pct > 0 ? '+' : ''}{d.mejora_pct}%
                        </div>
                      </div>
                    </div>
                  )
                })}
              </Card>
            </div>
          )}

          {/* Sobreentrenamiento */}
          {data.sobreentrenamiento && (
            <div>
              <SectionTitle>Riesgo de sobreentrenamiento</SectionTitle>
              <Card>
                <div style={{ padding:'14px 18px' }}>
                  <div style={{ display:'flex', alignItems:'center', gap:16, marginBottom:12 }}>
                    {/* Gauge */}
                    <div style={{ position:'relative', width:64, height:64, flexShrink:0 }}>
                      <svg width="64" height="64" viewBox="0 0 64 64">
                        <circle cx="32" cy="32" r="28" fill="none"
                          stroke={C.bg4} strokeWidth="8"/>
                        <circle cx="32" cy="32" r="28" fill="none"
                          stroke={data.sobreentrenamiento.nivel==='alto'?C.miss:
                                  data.sobreentrenamiento.nivel==='moderado'?C.amber:C.done}
                          strokeWidth="8"
                          strokeDasharray={`${(data.sobreentrenamiento.riesgo_pct/100)*175.9} 175.9`}
                          strokeLinecap="round"
                          transform="rotate(-90 32 32)"/>
                        <text x="32" y="37" textAnchor="middle"
                          style={{fontSize:'14px', fontWeight:'bold',
                            fill: data.sobreentrenamiento.nivel==='alto'?C.miss:
                                  data.sobreentrenamiento.nivel==='moderado'?C.amber:C.done}}>
                          {data.sobreentrenamiento.riesgo_pct}%
                        </text>
                      </svg>
                    </div>
                    <div>
                      <div style={{ fontSize:14, fontWeight:700, color:C.text, marginBottom:4 }}>
                        Riesgo {data.sobreentrenamiento.nivel}
                      </div>
                      <div style={{ fontSize:12, color:C.text2 }}>
                        {data.sobreentrenamiento.recomendacion}
                      </div>
                    </div>
                  </div>
                  {data.sobreentrenamiento.alertas?.map((a, i) => (
                    <div key={i} style={{ display:'flex', gap:8, padding:'6px 0',
                      borderTop:`1px solid ${C.border}` }}>
                      <span style={{ fontSize:11, fontWeight:700,
                        color:a.nivel==='alto'?C.miss:C.amber,
                        textTransform:'uppercase', minWidth:60 }}>{a.nivel}</span>
                      <span style={{ fontSize:12, color:C.text2 }}>{a.msg}</span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}

          {/* Cumplimiento */}
          {data.cumplimiento && data.cumplimiento.prob_cumplimiento && (
            <div>
              <SectionTitle>Probabilidad de cumplimiento esta semana</SectionTitle>
              <Card>
                <div style={{ padding:'14px 18px', display:'flex', gap:16, alignItems:'center' }}>
                  <div style={{ fontSize:32, fontWeight:800,
                    color: data.cumplimiento.prob_cumplimiento >= 0.75 ? C.done :
                           data.cumplimiento.prob_cumplimiento >= 0.5 ? C.amber : C.miss }}>
                    {Math.round(data.cumplimiento.prob_cumplimiento * 100)}%
                  </div>
                  <div style={{ fontSize:13, color:C.text2 }}>
                    {data.cumplimiento.interpretacion}
                  </div>
                </div>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Dashboard Coach de un atleta ──────────────────────────────────────────────
function DashboardAtleta({ atletaId, atleta }) {
  const [estado, setEstado]     = useState(null)
  const [presc, setPresc]       = useState(null)
  const [zonas, setZonas]       = useState(null)
  const [zonasBike, setZonasBike] = useState(null)
  const [zonasSwim, setZonasSwim] = useState(null)
  const [health, setHealth]     = useState(null)
  const [diag, setDiag]         = useState(null)
  const [loadingCiclo, setLoadingCiclo] = useState(false)
  const [syncLoading, setSyncLoading] = useState(false)
  const [tab, setTab]           = useState('semana')
  const [subTabZonas, setSubTabZonas] = useState('running')

  const cargarPresc = () => axios.get(`${API}/atletas/${atletaId}/prescripcion`).then(r=>setPresc(r.data.data)).catch(()=>{})

  useEffect(() => {
    if (!atletaId) return
    setEstado(null); setPresc(null); setZonas(null); setHealth(null); setDiag(null)
    axios.get(`${API}/atletas/${atletaId}/estado`).then(r=>setEstado(r.data.data)).catch(()=>{})
    cargarPresc()
    // Cargar zonas de todos los deportes del atleta
    axios.get(`${API}/atletas/${atletaId}/zonas/running`).then(r=>setZonas(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/zonas/cycling`).then(r=>setZonasBike(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/zonas/swimming`).then(r=>setZonasSwim(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/health`).then(r=>setHealth(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/diagnostico`).then(r=>setDiag(r.data.data)).catch(()=>{})
  }, [atletaId])

  const generarCiclo = async () => {
    setLoadingCiclo(true)
    try {
      const r = await axios.post(
        `${API}/atletas/${atletaId}/ciclo`,
        { forzar: false },
        { headers: { 'Content-Type': 'application/json' } }
      )
      setPresc(r.data.data)
    } catch (e) {
      const msg = e?.response?.data?.error || e?.message || 'Error generando ciclo'
      alert('Error: ' + msg)
    }
    setLoadingCiclo(false)
  }

  if (!atleta) return (
    <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', color:C.text2, gap:8 }}>
      <div style={{ fontSize:28 }}>👈</div>
      <div style={{ fontSize:13 }}>Seleccioná un atleta</div>
    </div>
  )

  const ctl = estado?.estado?.ctl
  const atl = estado?.estado?.atl
  const tsb = estado?.estado?.tsb
  const tsbColor = tsb>5?C.done:tsb<-15?C.miss:C.amber
  const chartData = (estado?.training||[]).slice(-60).map(d=>({fecha:d.d?.slice(5),CTL:d.ctl,ATL:d.atl,TSB:d.tsb}))
  const dep = atleta.deporte_ppal||atleta.deporte||'running'
  const s = SPORT[dep]||SPORT.running

  const tabs = [{id:'semana',label:'📅 Semana'},{id:'calendario',label:'🗓 Calendario'},{id:'estado',label:'📊 Estado'},{id:'diagnostico',label:'🔍 Diagnóstico'},{id:'zonas',label:'🎯 Zonas'},{id:'fases',label:'📈 Fases'},{id:'intel',label:'🧠 NOAH Intel'},{id:'race',label:'🏁 Race'},{id:'tests',label:'🔬 Tests'},{id:'clustering',label:'🧬 Clusters'},{id:'optimizer',label:'🎯 Optimizer'},{id:'perfil',label:'⚙ Perfil'},{id:'aprendizaje',label:'📈 Aprendizaje'},{id:'analisis_ciclismo',label:'⚡ Análisis Ciclismo'}]

  return (
    <div style={{ flex:1, overflow:'auto' }}>
      {/* Banner NOAH -- imagen de marca arriba de todo */}
      <div style={{ position:'relative', width:'100%', height:240, overflow:'hidden' }}>
        <img src="/assets/noah_banner_header.png" alt=""
          onError={e=>{e.target.parentElement.style.display='none'}}
          style={{ width:'100%', height:'100%', objectFit:'cover', objectPosition:'center 25%', display:'block' }} />
        <div style={{ position:'absolute', inset:0, background:`linear-gradient(to bottom, transparent 55%, ${C.bg} 100%)` }}/>
      </div>

      <div style={{ padding:'18px 26px 22px' }}>
      {/* Header atleta */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:18 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:5 }}>
            <h1 style={{ fontSize:22, fontWeight:800, color:C.text }}>{atleta.nombre}</h1>
            {/* Ícono deporte grande y claro */}
            <div style={{ display:'flex', alignItems:'center', gap:5, background:s.light, borderRadius:7, padding:'4px 10px', border:`1px solid ${s.color}33` }}>
              <s.Icon size={16} color={s.color} />
              <span style={{ fontSize:11, fontWeight:700, color:s.color, letterSpacing:0.8 }}>{s.label.toUpperCase()}</span>
            </div>
          </div>
          <div style={{ fontSize:12, color:C.text2 }}>{atleta.deporte} · LTHR {atleta.lthr_run} · {atleta.email}</div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <a href={`/atleta/${atleta.id}`} target="_blank" rel="noreferrer" style={{ textDecoration:'none' }}>
            <button style={{ padding:'7px 14px', borderRadius:7, border:`1px solid ${C.border}`, background:C.bg3, color:C.text2, cursor:'pointer', fontSize:12, fontWeight:500 }}>
              👤 Ver como atleta
            </button>
          </a>
          <button onClick={generarCiclo} disabled={loadingCiclo} style={{ padding:'7px 14px', borderRadius:7, border:'none', background:C.purple, color:'#fff', cursor:'pointer', fontSize:12, fontWeight:600 }}>
            {loadingCiclo?'Generando...':'⚡ Nuevo ciclo'}
          </button>
          <button onClick={async () => {
            if (!atletaId) return alert('Seleccioná un atleta primero')
            setSyncLoading(true)
            try {
              const r = await axios.post(`${API}/atletas/${atletaId}/sincronizar`, {modo:'todo'})
              const out = r.data.data?.output || ''
              const msg = out.includes('nueva') ? `✓ Actividad nueva sincronizada` : 'Sin actividades nuevas hoy'
              alert(msg)
              cargarPresc()
            } catch { alert('Error al sincronizar') }
            setSyncLoading(false)
          }} disabled={syncLoading} style={{ padding:'7px 14px', borderRadius:7, border:`1px solid ${C.border}`, background:C.bg3, color:C.text2, cursor:'pointer', fontSize:12, fontWeight:500 }}>
            {syncLoading ? '⏳ Sincronizando...' : '🔄 Sync'}
          </button>
        </div>
      </div>

      {/* Métricas -- badges circulares con vidrio esmerilado */}
      <div style={{
        display:'flex', justifyContent:'space-around', flexWrap:'wrap', gap:14,
        marginBottom:18, padding:'16px 18px', borderRadius:14,
        background:'rgba(255,255,255,0.02)', backdropFilter:'blur(8px)', WebkitBackdropFilter:'blur(8px)',
        border:`1px solid ${C.border}`,
      }}>
        <MetricBadgeCircular label="CTL" value={ctl?.toFixed(1)} sub="fitness" color={C.blue} />
        <MetricBadgeCircular label="ATL" value={atl?.toFixed(1)} sub="fatiga" color={C.miss} />
        <MetricBadgeCircular label="TSB" value={tsb?.toFixed(1)} sub="frescura" color={tsbColor} />
        <MetricBadgeCircular label="Hanna Life" value={estado?.estado?.hanna_life?.toFixed(0)||'--'} sub={estado?.estado?.hanna_nivel||'calculando'} color={{'Óptimo':C.done,'Bueno':'#3B82F6','Moderado':C.amber,'Bajo':'#F97316','Crítico':C.miss}[estado?.estado?.hanna_nivel]||C.text2} />
        <MetricBadgeCircular label="Diagnóstico" value={diag?.score_general?`${diag.score_general}`:'--'} sub={diag?.color||'calculando'} color={{verde:C.done,amarillo:C.amber,rojo:C.miss}[diag?.color]||C.text2} />
      </div>

      {/* Tabs -- ahora en columna vertical a la derecha (ver cierre mas abajo) */}
      <div style={{ display:'flex', gap:16, alignItems:'flex-start' }}>
        <div style={{ flex:1, minWidth:0 }}>

      {tab==='semana'&&(
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          {/* Actividad real de hoy/ayer — siempre visible */}
          <ActividadRecienteCoach atletaId={atletaId} />
          <CoachSemana presc={presc} atletaId={atletaId} onCambio={cargarPresc} atleta={atleta} />
        </div>
      )}

      {tab==='estado'&&(
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
          <div>
            <SectionTitle>Recuperación</SectionTitle>
            <Card>
              <CardRow label="HRV ratio" value={<>{estado?.estado?.hrv_ratio??'--'} <Pill flag={estado?.estado?.hrv_flag} /></>} />
              <CardRow label="HRV nocturno" value={`${estado?.estado?.hrv_ms??'--'} ms`} />
              <CardRow label="Sueño" value={`${estado?.estado?.sleep_h??'--'} h`} />
              <CardRow label="Deep / REM" value={`${estado?.estado?.deep_h??'--'} / ${estado?.estado?.rem_h??'--'} h`} />
              <CardRow label="Recovery" value={`${estado?.estado?.recovery??'--'} /100`} />
            </Card>
          </div>
          <div>
            <SectionTitle>CTL / ATL / TSB — 60 días</SectionTitle>
            <Card style={{ padding:14 }}>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="fecha" tick={{ fill:C.text2, fontSize:10 }} />
                  <YAxis tick={{ fill:C.text2, fontSize:10 }} />
                  <Tooltip contentStyle={{ background:C.bg2, border:`1px solid ${C.border}`, borderRadius:8, fontFamily:'Inter', fontSize:12 }} />
                  <Line type="monotone" dataKey="CTL" stroke={C.blue} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="ATL" stroke={C.miss} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="TSB" stroke={C.done} dot={false} strokeWidth={1.5} strokeDasharray="4 3" />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>
          <div style={{gridColumn:'1/-1'}}>
            <HannaLifeGrafico atletaId={atletaId} modo="dark" />
          </div>
          <div style={{gridColumn:'1/-1'}}>
            <ResumenCumplimientoCoach atletaId={atletaId} />
          </div>
        </div>
      )}

      {tab==='diagnostico'&&<TabDiagnostico diag={diag} />}

      {tab==='calendario' && atletaId && (
        <CalendarioMensual atletaId={atletaId} presc={presc} dark={true}/>
      )}
      {tab==='fases'&&(
        <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
          <ModeloBanisterFases atletaId={atletaId} />
          <ProyeccionMultideporteCoach atletaId={atletaId} />
        </div>
      )}

      {tab==='intel'&&<NOAHIntelPanel atletaId={atletaId} />}

      {tab==='race'&&<SeccionRace atletaId={atletaId} modoAtleta={false} />}

      {tab==='tests'&&<SeccionTests atletaId={atletaId} modoAtleta={false} />}

      {tab==='clustering'&&atletaId&&<ClusteringPanel atletaId={atletaId} atleta={atleta} />}
      {tab==='optimizer'&&atletaId&&<OptimizerPanel atletaId={atletaId} atleta={atleta} />}
      {tab==='perfil'&&atletaId&&(<><PerfilFisiologico atletaId={atletaId} atleta={atleta} /><PerfilDisponibilidad atletaId={atletaId} atleta={atleta} /></>)}
      {tab==='aprendizaje'&&atletaId&&<AprendizajePanel atletaId={atletaId} atleta={atleta} />}
      {tab==='analisis_ciclismo'&&atletaId&&<AnalisisCiclismoPanel atletaId={atletaId} atleta={atleta} ftp={atleta?.ftp_watts||200} cadenciaOptima={atleta?.cadencia_optima||85} />}
      {tab==='plan'&&atletaId&&(
        <div style={{display:'flex',flexDirection:'column',gap:16}}>
          <SectionTitle>Planificación — A/T/R/Taper</SectionTitle>
          <Card>
            <div style={{padding:20}}>
              <PlanCoachChart atletaId={atletaId} />
            </div>
          </Card>
        </div>
      )}

      {tab==='zonas'&&(
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          {/* Subtabs deportes */}
          <div style={{ display:'flex', gap:6 }}>
            {[
              {id:'running', label:'🏃 Running', show: true, color: C.run},
              {id:'cycling', label:'🚴 Ciclismo', show: !!zonasBike, color: C.bike},
              {id:'swimming',label:'🏊 Natación', show: !!zonasSwim, color: C.swim},
            ].filter(t=>t.show).map(t=>(
              <button key={t.id} onClick={()=>setSubTabZonas(t.id)} style={{
                padding:'6px 14px', fontSize:12, fontWeight:subTabZonas===t.id?700:400,
                color:subTabZonas===t.id?'#fff':C.text2,
                background:subTabZonas===t.id?t.color:'transparent',
                border:`1px solid ${subTabZonas===t.id?t.color:C.border}`,
                borderRadius:8, cursor:'pointer',
              }}>{t.label}</button>
            ))}
          </div>

          {/* Running */}
          {subTabZonas==='running'&&zonas&&(
            <div>
              <SectionTitle>Zonas Running — LTHR {atleta?.lthr_run} bpm</SectionTitle>
              <Card>
                {Object.entries(zonas.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{
                    padding:'13px 16px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderLeft: `4px solid ${z.color||C.run}`,
                    background: `${z.color||C.run}12`,
                  }}>
                    <div>
                      <span style={{ fontWeight:800, color:z.color||C.run, marginRight:8, fontSize:14 }}>{zona}</span>
                      <span style={{ fontWeight:600 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:14, fontWeight:700, color:z.color||C.run }}>
                        {z.pace_rango || (z.pace_min && z.pace_max ? `${z.pace_min} – ${z.pace_max} /km` : z.pace_ref ? fmtPaceStr(z.pace_ref)+' /km' : '--')}
                      </div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          )}

          {/* Ciclismo */}
          {subTabZonas==='cycling'&&zonasBike&&(
            <div>
              <SectionTitle>Zonas Ciclismo — FTP {zonasBike?.ftp}W · {zonasBike?.w_kg} W/kg</SectionTitle>
              <Card>
                {Object.entries(zonasBike.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{
                    padding:'13px 16px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderLeft: `4px solid ${z.color||C.bike}`,
                    background: `${z.color||C.bike}12`,
                  }}>
                    <div>
                      <span style={{ fontWeight:800, color:z.color||C.bike, marginRight:8, fontSize:14 }}>{zona}</span>
                      <span style={{ fontWeight:600 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>{z.pct_ftp}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:14, fontWeight:700, color:z.color||C.bike }}>{z.w_rango}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max||'--'} · {z.wkg_min||'--'} W/kg</div>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          )}

          {/* Natación */}
          {subTabZonas==='swimming'&&zonasSwim&&(
            <div>
              <SectionTitle>Zonas Natación — CSS {zonasSwim?.css} min/100m</SectionTitle>
              <Card>
                {Object.entries(zonasSwim.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{
                    padding:'13px 16px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderLeft: `4px solid ${C.swim}`,
                    background: `${C.swim}12`,
                  }}>
                    <div>
                      <span style={{ fontWeight:800, color:C.swim, marginRight:8, fontSize:14 }}>{zona}</span>
                      <span style={{ fontWeight:600 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>{z.descripcion}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:14, fontWeight:700, color:C.swim }}>{z.pace_rango}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          )}
        </div>
      )}
        </div>

        {/* Rail vertical de tabs -- a la derecha del contenido */}
        <div style={{
          width:132, flexShrink:0, display:'flex', flexDirection:'column', gap:5,
          position:'sticky', top:0,
        }}>
          {tabs.map(t=>{
            const partes = t.label.split(' ')
            const icono = partes[0]
            const texto = partes.slice(1).join(' ')
            return (
              <button key={t.id} onClick={()=>setTab(t.id)} style={{
                display:'flex', alignItems:'center', gap:8, padding:'9px 12px',
                borderRadius:10, border:`1px solid ${tab===t.id?C.purple:C.border}`,
                background: tab===t.id ? `${C.purple}18` : 'rgba(255,255,255,0.02)',
                backdropFilter:'blur(6px)', WebkitBackdropFilter:'blur(6px)',
                color: tab===t.id?C.purple:C.text2, cursor:'pointer',
                fontWeight: tab===t.id?700:500, fontSize:11.5, textAlign:'left',
                transition:'all 0.15s',
              }}>
                <span style={{ fontSize:15 }}>{icono}</span>
                <span>{texto}</span>
              </button>
            )
          })}
        </div>
      </div>
      </div>
    </div>
  )
}

// ── CoachApp ──────────────────────────────────────────────────────────────────
function CoachApp() {
  const [atletas, setAtletas] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const [colapsado, setColapsado] = useState(false)  // sidebar dinamico: abierto/cerrado
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)  // drawer mobile: abierto/cerrado (no afecta PC)

  const cargarAtletas = async () => {
    try { const r=await axios.get(`${API}/atletas`); setAtletas(r.data.data); if(!selectedId&&r.data.data.length>0)setSelectedId(r.data.data[0].id) }
    catch(e){console.error(e)}
    setLoading(false)
  }
  useEffect(()=>{cargarAtletas()},[])
  const selectedAtleta = atletas.find(a=>a.id===selectedId)||null

  return (
    <>
      <style>{css}</style>
      <style>{`
        .coach-mobile-toggle { display: none; }
        @media (max-width: 768px) {
          .coach-mobile-toggle {
            display: flex; position: fixed; top: 12px; left: 12px; z-index: 1001;
            width: 42px; height: 42px; border-radius: 11px;
            background: rgba(20,20,30,0.92); backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.15);
            align-items: center; justify-content: center; color: #fff; cursor: pointer;
            box-shadow: 0 4px 14px rgba(0,0,0,0.4);
          }
          .coach-sidebar {
            position: fixed !important; top:0; left:0; bottom:0; z-index: 1000;
            width: 78vw !important; max-width: 300px;
            transform: translateX(-100%);
            transition: transform 0.25s ease;
            box-shadow: 6px 0 30px rgba(0,0,0,0.6);
          }
          .coach-sidebar.mobile-open { transform: translateX(0); }
        }
      `}</style>
      {mobileMenuOpen && (
        <div onClick={()=>setMobileMenuOpen(false)} style={{
          position:'fixed', inset:0, background:'rgba(0,0,0,0.6)', zIndex:999,
        }}/>
      )}
      <button className="coach-mobile-toggle" onClick={()=>setMobileMenuOpen(o=>!o)}>
        {mobileMenuOpen ? '✕' : '☰'}
      </button>
      <div style={{ display:'flex', height:'100vh', overflow:'hidden' }}>
        {/* Sidebar -- ancho dinamico: 268px abierto, 64px colapsado (PC).
            En mobile se convierte en panel deslizable via CSS de arriba. */}
        <div className={`coach-sidebar${mobileMenuOpen ? ' mobile-open' : ''}`} style={{ width: colapsado ? 64 : 268, flexShrink:0, background:C.bg2, borderRight:`1px solid ${C.border}`, display:'flex', flexDirection:'column', transition:'width 0.2s' }}>
          <div style={{ padding: colapsado ? '18px 0 14px' : '18px 16px 14px', borderBottom:`1px solid ${C.border}`, display:'flex', flexDirection:'column', alignItems: colapsado ? 'center' : 'stretch' }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
              {!colapsado && (
                <div style={{ display:'flex', alignItems:'baseline' }}>
                  <span style={{ fontSize:22, fontWeight:800, letterSpacing:6, color:C.text }}>N</span>
                  <span style={{ fontSize:22, fontWeight:800, letterSpacing:6, color:C.run }}>O</span>
                  <span style={{ fontSize:22, fontWeight:800, letterSpacing:6, color:C.text }}>A</span>
                  <span style={{ fontSize:22, fontWeight:800, letterSpacing:6, color:C.run }}>H</span>
                </div>
              )}
              <button onClick={()=>setColapsado(c=>!c)} title={colapsado?'Expandir':'Colapsar'} style={{
                background:'transparent', border:`1px solid ${C.border}`, borderRadius:6,
                width:22, height:22, display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer', color:C.text2, fontSize:11, flexShrink:0,
              }}>{colapsado?'›':'‹'}</button>
            </div>
            {!colapsado && <div style={{ fontSize:9, color:C.text2, letterSpacing:2.5, marginTop:2, textTransform:'uppercase' }}>NOAH Coach</div>}
          </div>

          {/* Imagen de marca NOAH -- interactiva y liviana: reutiliza datos
              ya cargados (selectedAtleta), sin llamadas nuevas ni librerias. */}
          {/* Imagen de marca NOAH -- alterna al azar entre masculino/femenino en cada carga. */}
          {!colapsado && (
            <div style={{ position:'relative', width:'100%', height:280, overflow:'hidden' }}>
              <img src={Math.random() < 0.5 ? '/assets/noah_avatar_m.png' : '/assets/noah_avatar_f.png'}
                alt="" onError={e=>{e.target.parentElement.style.display='none'}}
                style={{ width:'100%', height:'100%', objectFit:'cover', objectPosition:'top center', display:'block' }} />
              <div style={{
                position:'absolute', left:0, right:0, bottom:0, height:'50%',
                background:`linear-gradient(to bottom, transparent, ${C.bg2}CC 60%, ${C.bg2} 100%)`,
                pointerEvents:'none',
              }}/>
            </div>
          )}

          <div style={{ flex:1, overflow:'auto' }}>
            {loading?(!colapsado && <div style={{ padding:14, color:C.text2, fontSize:13 }}>Cargando...</div>)
              :atletas.map(a=><AtletaItem key={a.id} atleta={a} selected={selectedId===a.id} onClick={()=>{setSelectedId(a.id); setMobileMenuOpen(false)}} colapsado={colapsado} />)}
          </div>
          <div style={{ padding:10, borderTop:`1px solid ${C.border}`, display:'flex', flexDirection:'column', gap:6 }}>
            <button onClick={()=>setShowModal(true)} title="Agregar atleta" style={{ width:'100%', padding:'9px', borderRadius:8, border:'none', background:C.purple, color:'#fff', cursor:'pointer', fontSize:13, fontWeight:600 }}>
              {colapsado ? '+' : '+ Agregar atleta'}
            </button>
            <button onClick={()=>{
              const navigate = window.location
              const s = getSesion()
              if (s?.token) axios.post(`${API}/logout`, {}).catch(()=>{})
              limpiarSesion()
              window.location.href = '/login'
            }} title="Cerrar sesión" style={{ width:'100%', padding:'8px', borderRadius:8, border:`1px solid ${C.border}`, background:'transparent', color:C.text2, cursor:'pointer', fontSize:12, fontWeight:600 }}>
              {colapsado ? '⏻' : 'Cerrar sesión'}
            </button>
          </div>
        </div>
        <DashboardAtleta key={selectedId} atletaId={selectedId} atleta={selectedAtleta} />
      </div>
      {showModal&&<OnboardingAtleta onClose={()=>setShowModal(false)} onCreado={cargarAtletas} />}
    </>
  )
}

function AtletaPage() {
  const { id } = useParams()
  return <AtletaDashboard atletaId={parseInt(id)} />
}

// ── Sesión — guardada en localStorage, mismo patrón simple para todo el front ──
const SESION_KEY = 'noah_sesion'

function getSesion() {
  try {
    const raw = localStorage.getItem(SESION_KEY)
    return raw ? JSON.parse(raw) : null
  } catch { return null }
}
function setSesion(sesion) {
  localStorage.setItem(SESION_KEY, JSON.stringify(sesion))
}
function limpiarSesion() {
  localStorage.removeItem(SESION_KEY)
}
// authFetch — helper para que cualquier fetch mande el token automáticamente.
// axios usa un interceptor (más abajo) así que no todos los call-sites
// necesitan tocarse a mano.
function authHeaders() {
  const s = getSesion()
  return s?.token ? { Authorization: `Bearer ${s.token}` } : {}
}

// Interceptor global de axios — agrega el token a TODAS las peticiones axios
// existentes en la app sin tener que tocar cada uno de los cientos de
// llamados ya escritos en App.js / AtletaDashboard.jsx.
axios.interceptors.request.use((config) => {
  const s = getSesion()
  if (s?.token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${s.token}`
  }
  return config
})
// Si el backend responde 401 (sesión vencida/inválida), limpiar y mandar a /login
axios.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      limpiarSesion()
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

function Login() {
  const navigate = useNavigate()
  const [usuario, setUsuario] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  // Si ya hay una sesión guardada (por ejemplo al abrir la app instalada en
  // el celular), saltar la pantalla de login y entrar directo al dashboard.
  useEffect(() => {
    const s = getSesion()
    if (s?.token) {
      if (s.rol === 'coach') navigate('/coach', { replace: true })
      else navigate(`/atleta/${s.atletaId}`, { replace: true })
    }
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (!usuario.trim() || !password) {
      setError('Completá usuario y contraseña')
      return
    }
    setCargando(true)
    try {
      const r = await axios.post(`${API}/login`, { usuario: usuario.trim(), password })
      const { token, atleta_id, nombre, rol } = r.data.data
      setSesion({ token, atletaId: atleta_id, nombre, rol })
      if (rol === 'coach') navigate('/coach')
      else navigate(`/atleta/${atleta_id}`)
    } catch (err) {
      setError(err?.response?.data?.error || 'Usuario o contraseña incorrectos')
    }
    setCargando(false)
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'radial-gradient(circle at 30% 20%, #1a0533, #0A0F1E 60%)',
      fontFamily: 'Inter, system-ui, sans-serif', padding: 20,
    }}>
      <form onSubmit={submit} style={{
        width: '100%', maxWidth: 360, background: 'rgba(255,255,255,0.04)',
        backdropFilter: 'blur(20px)', borderRadius: 20, padding: '36px 28px',
        border: '1px solid rgba(255,255,255,0.08)',
        boxShadow: '0 24px 60px -10px rgba(0,0,0,0.6)',
      }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display:'flex', justifyContent:'center', gap:1, marginBottom:6 }}>
            {['N','O','A','H'].map((l,i)=>(
              <span key={i} style={{ fontSize:28, fontWeight:900, letterSpacing:5,
                color: i%2===1 ? '#A78BFA' : '#fff' }}>{l}</span>
            ))}
          </div>
          <div style={{ fontSize:9, color:'rgba(255,255,255,0.35)', letterSpacing:2, textTransform:'uppercase' }}>
            Never Over, Always Higher
          </div>
        </div>

        <label style={{ fontSize:12, color:'rgba(255,255,255,0.6)', fontWeight:600 }}>Usuario</label>
        <input
          value={usuario} onChange={e=>setUsuario(e.target.value)}
          autoFocus autoComplete="username"
          style={{
            width:'100%', marginTop:6, marginBottom:16, padding:'11px 14px',
            borderRadius:10, border:'1px solid rgba(255,255,255,0.15)',
            background:'rgba(255,255,255,0.05)', color:'#fff', fontSize:14,
            boxSizing:'border-box',
          }}
        />

        <label style={{ fontSize:12, color:'rgba(255,255,255,0.6)', fontWeight:600 }}>Contraseña</label>
        <input
          type="password" value={password} onChange={e=>setPassword(e.target.value)}
          autoComplete="current-password"
          style={{
            width:'100%', marginTop:6, marginBottom:20, padding:'11px 14px',
            borderRadius:10, border:'1px solid rgba(255,255,255,0.15)',
            background:'rgba(255,255,255,0.05)', color:'#fff', fontSize:14,
            boxSizing:'border-box',
          }}
        />

        {error && (
          <div style={{ fontSize:12, color:'#F87171', background:'rgba(248,113,113,0.1)',
            border:'1px solid rgba(248,113,113,0.25)', borderRadius:8, padding:'8px 12px', marginBottom:16 }}>
            {error}
          </div>
        )}

        <button type="submit" disabled={cargando} style={{
          width:'100%', padding:'12px', borderRadius:10, border:'none',
          background: cargando ? 'rgba(139,92,246,0.5)' : 'linear-gradient(135deg,#8B5CF6,#6D28D9)',
          color:'#fff', fontSize:14, fontWeight:700, cursor: cargando?'default':'pointer',
        }}>
          {cargando ? 'Ingresando...' : 'Ingresar'}
        </button>
      </form>
    </div>
  )
}

// ── Protección de rutas ──────────────────────────────────────────────────────
function RequireCoach({ children }) {
  const s = getSesion()
  if (!s?.token || s.rol !== 'coach') return <Navigate to="/login" replace />
  return children
}
function RequireAtleta({ children }) {
  const { id } = useParams()
  const s = getSesion()
  if (!s?.token) return <Navigate to="/login" replace />
  // Un atleta solo puede ver SU PROPIO id — si la URL pide otro, se lo manda
  // a su propio dashboard en vez de dejarlo pasar. El coach puede ver cualquiera.
  if (s.rol === 'atleta' && String(s.atletaId) !== String(id)) {
    return <Navigate to={`/atleta/${s.atletaId}`} replace />
  }
  return children
}

// ── Análisis Ciclismo — Torque y W'bal ──────────────────────────────────────
function AnalisisCiclismoPanel({ atletaId, atleta, ftp = 200, cadenciaOptima = 85 }) {
  const [fecha,      setFecha]     = useState(new Date().toISOString().slice(0,10))
  const [sesiones,   setSesiones]  = useState([])
  const [sesionId,   setSesionId]  = useState(null)
  const [data,       setData]      = useState(null)
  const [cargando,   setCargando]  = useState(false)
  const [vista,      setVista]     = useState(null) // 'torque' | 'wbal'
  const [loadingAnal,setLoadingAnal] = useState(false)

  // Cargar sesiones de ciclismo del atleta al cambiar fecha
  useEffect(() => {
    if (!atletaId) return
    setSesiones([]); setSesionId(null); setData(null); setVista(null)
    authFetch(`${API}/atletas/${atletaId}/sesiones?limit=30`)
      .then(r => r.json())
      .then(r => {
        const ses = (r.data || r || []).filter(s =>
          s.sport === 'cycling' && s.fecha?.slice(0,10) === fecha
        )
        setSesiones(ses)
        if (ses.length === 1) setSesionId(ses[0].id)
      })
      .catch(() => {})
  }, [atletaId, fecha])

  // Buscar sesiones de ciclismo en un rango si no hay en fecha exacta
  useEffect(() => {
    if (!atletaId) return
    setSesiones([]); setSesionId(null); setData(null); setVista(null)
    // Buscar en los últimos 90 días para el selector
    authFetch(`${API}/atletas/${atletaId}/sesiones?limit=100`)
      .then(r => r.json())
      .then(r => {
        const ses = (r.data || r || []).filter(s => s.sport === 'cycling')
        setSesiones(ses)
      })
      .catch(() => {})
  }, [atletaId])

  const analizar = async () => {
    if (!sesionId) return
    setLoadingAnal(true); setData(null)
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/sesiones/${sesionId}/torque_wbal`)
      const d = await r.json()
      setData(d.data || d)
    } catch {}
    setLoadingAnal(false)
  }

  const Q_COLOR = { Q1:'#F97316', Q2:'#EF4444', Q3:'#22C55E', Q4:'#3B82F6' }
  const Q_DESC  = {
    Q1:'Explosivo (fuerza alta + cadencia alta)',
    Q2:'⚠ Veneno triatlón (fuerza alta + cadencia baja)',
    Q3:'Recuperación aeróbica',
    Q4:'Eficiencia cardiovascular',
  }

  const torque_umbral = ftp > 0 && cadenciaOptima > 0
    ? Math.round((9.549 * ftp) / cadenciaOptima) : 30

  const { samples=[], cuadrantes={}, metricas={} } = data || {}

  // Datos para scatter (max 1500 pts)
  const step1 = Math.max(1, Math.floor(samples.length / 1500))
  const scatterData = samples
    .filter((_,i) => i % step1 === 0 && samples[i].cadence > 0)
    .map(s => ({ x: s.cadence, y: s.torque, w: s.wbal_pct }))

  // Datos para W'bal temporal (max 400 pts)
  const step2 = Math.max(1, Math.floor(samples.length / 400))
  const lineData = samples
    .filter((_,i) => i % step2 === 0)
    .map(s => ({ t: Math.round(s.ts_s / 60), wbal: s.wbal_pct, torque: s.torque }))

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16, padding:'4px 0' }}>
      <SectionTitle>Análisis de Ciclismo — Torque & W'bal</SectionTitle>

      {/* Selector */}
      <Card>
        <div style={{ display:'flex', gap:10, alignItems:'flex-end', flexWrap:'wrap' }}>
          <div style={{ flex:1, minWidth:160 }}>
            <div style={{ fontSize:11, color:C.text2, marginBottom:4 }}>Sesión de ciclismo</div>
            <select value={sesionId||''} onChange={e => { setSesionId(Number(e.target.value)); setData(null); setVista(null) }}
              style={{ width:'100%', padding:'8px 10px', borderRadius:8, fontSize:13,
                background:C.bg, color:C.text, border:`1px solid ${C.border}` }}>
              <option value="">— Elegí una sesión —</option>
              {sesiones.map(s => (
                <option key={s.id} value={s.id}>
                  {s.fecha?.slice(0,10)} · {Math.round(s.duration||0)}min · {s.tss ? `TSS ${Math.round(s.tss)}` : ''}
                </option>
              ))}
            </select>
          </div>
          <button onClick={analizar} disabled={!sesionId || loadingAnal} style={{
            padding:'9px 20px', borderRadius:9, fontSize:13, fontWeight:700,
            background: sesionId ? '#007AFF' : C.bg2,
            color: sesionId ? '#fff' : C.text2,
            border:'none', cursor: sesionId ? 'pointer' : 'default',
            boxShadow: sesionId ? '0 4px 12px rgba(0,122,255,0.35)' : 'none',
            display:'flex', alignItems:'center', gap:6,
          }}>
            {loadingAnal ? '⏳ Calculando...' : '⚡ Analizar'}
          </button>
        </div>
        {sesiones.length === 0 && (
          <div style={{ fontSize:12, color:C.text2, marginTop:8 }}>
            Sin sesiones de ciclismo encontradas para este atleta.
          </div>
        )}
      </Card>

      {/* Resultado */}
      {data && (
        <>
          {/* Tarjetas métricas */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:8 }}>
            {[
              { label:'% tiempo Q2', value:`${cuadrantes?.Q2??'--'}%`, color:'#EF4444', icon:'⚠', desc:'Veneno triatlón' },
              { label:"W'bal final",  value:`${metricas?.wbal_final_pct??'--'}%`, color:'#22C55E', icon:'🔋', desc:'Batería anaeróbica restante' },
              { label:'Vaciados críticos', value:metricas?.vaciados_criticos??'--', color:'#F97316', icon:'⚡', desc:"Veces bajo 30% W'" },
              { label:'NME', value:metricas?.nme?metricas.nme.toFixed(1):'--', color:'#3B82F6', icon:'⚙', desc:'Eficiencia neuromuscular' },
            ].map(({ label, value, color, icon, desc }) => (
              <div key={label} style={{
                background:`${color}12`, borderRadius:10, padding:'12px 14px',
                border:`1px solid ${color}30`,
              }}>
                <div style={{ fontSize:11, color:C.text2, marginBottom:4 }}>{icon} {label}</div>
                <div style={{ fontSize:22, fontWeight:800, color }}>{value}</div>
                <div style={{ fontSize:10, color:C.text2, marginTop:2 }}>{desc}</div>
              </div>
            ))}
          </div>

          {/* Botones torque / wbal */}
          <div style={{ display:'flex', gap:10 }}>
            {[['torque','⚙ Torque vs Cadencia'],['wbal',"🔋 W'bal Temporal"]].map(([v, label]) => (
              <button key={v} onClick={() => setVista(vista===v ? null : v)} style={{
                flex:1, padding:'11px 16px', borderRadius:10, fontSize:13, fontWeight:700,
                background: vista===v ? '#007AFF' : C.bg,
                color: vista===v ? '#fff' : C.text2,
                border:`1px solid ${vista===v ? '#007AFF' : C.border}`,
                cursor:'pointer',
                boxShadow: vista===v ? '0 4px 12px rgba(0,122,255,0.35)' : 'none',
              }}>{label}</button>
            ))}
          </div>

          {/* Gráfico de cuadrantes */}
          {vista === 'torque' && scatterData.length > 0 && (
            <Card>
              <div style={{ fontSize:12, color:C.text2, marginBottom:8 }}>
                Cada punto = 1 seg · Eje X = Cadencia (RPM) · Eje Y = Torque (N·m)
                · Líneas = FTP ({metricas.ftp_usado}W) / Cadencia óptima ({metricas.cadencia_optima}rpm)
                <br/>· CP {metricas.cp_usado}W · W' {metricas.w_prime_usado ? Math.round(metricas.w_prime_usado/1000) : '--'}kJ ({metricas.w_prime_usado}J)
              </div>
              <ScatterChart width={Math.min(window.innerWidth - 80, 600)} height={260}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="x" type="number" domain={[40,130]} name="Cadencia"
                  tick={{ fill:C.text2, fontSize:10 }}
                  label={{ value:'RPM', position:'insideBottom', offset:-2, fill:C.text2, fontSize:10 }}/>
                <YAxis dataKey="y" type="number" name="Torque"
                  tick={{ fill:C.text2, fontSize:10 }}
                  label={{ value:'N·m', angle:-90, position:'insideLeft', fill:C.text2, fontSize:10 }}/>
                <Tooltip contentStyle={{ background:'#1C1C1E', border:`1px solid ${C.border}`, borderRadius:8, fontSize:11 }}
                  formatter={(v,n) => [v, n==='x'?'Cadencia (RPM)':'Torque (N·m)']} />
                <ReferenceLine x={cadenciaOptima} stroke="rgba(255,255,255,0.2)" strokeDasharray="4 4"
                  label={{ value:`${cadenciaOptima}rpm`, fill:'rgba(255,255,255,0.3)', fontSize:9 }}/>
                <ReferenceLine y={torque_umbral} stroke="rgba(255,255,255,0.2)" strokeDasharray="4 4"
                  label={{ value:`${torque_umbral}N·m`, fill:'rgba(255,255,255,0.3)', fontSize:9 }}/>
                <Scatter data={scatterData} shape={(p) => {
                  const { cx, cy, payload } = p
                  const q = payload.y > torque_umbral && payload.x >= cadenciaOptima ? 'Q1'
                          : payload.y > torque_umbral && payload.x < cadenciaOptima  ? 'Q2'
                          : payload.y <= torque_umbral && payload.x < cadenciaOptima  ? 'Q3' : 'Q4'
                  return <circle cx={cx} cy={cy} r={2.5} fill={Q_COLOR[q]} fillOpacity={0.65}/>
                }}/>
              </ScatterChart>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:6, marginTop:8 }}>
                {Object.entries(Q_DESC).map(([q,desc]) => (
                  <div key={q} style={{ display:'flex', alignItems:'center', gap:6, fontSize:10, color:C.text2 }}>
                    <div style={{ width:8,height:8,borderRadius:'50%',background:Q_COLOR[q],flexShrink:0 }}/>
                    <span><b style={{color:Q_COLOR[q]}}>{q} {cuadrantes?.[q]}%</b> — {desc}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {vista === 'torque' && scatterData.length === 0 && (
            <div style={{ padding:'16px', borderRadius:10,
              background:'rgba(248,81,73,0.08)', border:'1px solid rgba(248,81,73,0.25)',
              fontSize:13, color:'#FCA5A5', textAlign:'center', lineHeight:1.6 }}>
              ⚠ Sin datos de cadencia para esta actividad.<br/>
              El medidor de potencia no transmite RPM a Garmin — sin cadencia no se puede calcular Torque (N·m = P / RPM).<br/>
              <span style={{ fontSize:11, color:'rgba(252,165,165,0.6)' }}>
                Verificá en Garmin Connect si la actividad tiene cadencia de ciclismo.
              </span>
            </div>
          )}

          {/* Gráfico W'bal */}
          {vista === 'wbal' && lineData.length > 0 && (
            <Card>
              <div style={{ fontSize:12, color:C.text2, marginBottom:8 }}>
                Verde = W'bal (batería anaeróbica) · Rojo = Torque · Línea punteada = límite crítico 30%
              </div>
              <AreaChart width={Math.min(window.innerWidth - 80, 600)} height={240} data={lineData}>
                <defs>
                  <linearGradient id="wG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#22C55E" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#22C55E" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="tG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#EF4444" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.06)"/>
                <XAxis dataKey="t" tick={{ fill:C.text2, fontSize:10 }}
                  label={{ value:'min', position:'insideBottom', offset:-2, fill:C.text2, fontSize:10 }}/>
                <YAxis yAxisId="w" domain={[0,100]} tick={{ fill:'#22C55E', fontSize:10 }}/>
                <YAxis yAxisId="t" orientation="right" tick={{ fill:'#EF4444', fontSize:10 }}/>
                <Tooltip contentStyle={{ background:'#1C1C1E', border:`1px solid ${C.border}`, borderRadius:8, fontSize:11 }}
                  formatter={(v,n) => [n==='wbal' ? `${v?.toFixed(0)}%` : `${v?.toFixed(0)} N·m`, n==='wbal'?"W'bal":'Torque']}/>
                <ReferenceLine yAxisId="w" y={30} stroke="#EF4444" strokeOpacity={0.5} strokeDasharray="4 4"
                  label={{ value:'Crítico 30%', fill:'#EF4444', fontSize:9 }}/>
                <Area yAxisId="w" type="monotone" dataKey="wbal" stroke="#22C55E" strokeWidth={2} fill="url(#wG)" dot={false}/>
                <Area yAxisId="t" type="monotone" dataKey="torque" stroke="#EF4444" strokeWidth={1.5} fill="url(#tG)" dot={false} opacity={0.8}/>
              </AreaChart>
              {metricas?.vaciados_criticos > 0 && (
                <div style={{ marginTop:8, padding:'10px 14px', borderRadius:8,
                  background:'rgba(239,68,68,0.1)', border:'1px solid rgba(239,68,68,0.25)',
                  fontSize:12, color:'#FCA5A5' }}>
                  ⚡ {metricas.vaciados_criticos} vaciado{metricas.vaciados_criticos>1?'s':''} crítico{metricas.vaciados_criticos>1?'s':''} — 
                  W' bajó del 30% en {metricas.vaciados_criticos} ocasión{metricas.vaciados_criticos>1?'es':''}.
                  {cuadrantes?.Q2 > 15 && ` Pasó ${cuadrantes.Q2}% en Q2 — recomendar elevar cadencia.`}
                </div>
              )}
              {metricas?.vaciados_criticos === 0 && (
                <div style={{ marginTop:8, padding:'10px 14px', borderRadius:8,
                  background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)',
                  fontSize:12, color:'#86EFAC' }}>
                  ✓ Excelente gestión energética — W' siempre sobre el límite crítico.
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  )
}


export default function App() {
  const [cargando, setCargando] = useState(true)

  if (cargando) {
    return <PantallaCarga duracionMs={2000} onTerminar={() => setCargando(false)} />
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireCoach><CoachApp /></RequireCoach>} />
        <Route path="/coach" element={<RequireCoach><CoachApp /></RequireCoach>} />
        <Route path="/atleta/:id" element={<RequireAtleta><AtletaPage /></RequireAtleta>} />
      </Routes>
    </BrowserRouter>
  )
}

// ── ClusteringPanel — Análisis de clusters para el coach ──────────────────────
function AprendizajePanel({ atletaId, atleta }) {
  const [data,    setData]    = useState(null)
  const [loading, setLoading] = useState(true)
  const [dias,    setDias]    = useState(60)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    axios.get(`${API}/atletas/${atletaId}/feedback?dias=${dias}`)
      .then(r => { setData(r.data.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId, dias])

  if (loading) return <div style={{padding:32,textAlign:'center',color:C.text2}}>Cargando...</div>

  if (!data || data.sin_datos) return (
    <div style={{padding:48,textAlign:'center',color:C.text2}}>
      <div style={{fontSize:32,marginBottom:12}}>🧠</div>
      <div style={{fontSize:14,fontWeight:700,color:C.text,marginBottom:6}}>Sin datos de aprendizaje todavía</div>
      <div style={{fontSize:12,color:C.text2}}>
        NOAH aprende después de cada ciclo completado.<br/>
        Generá ciclos, el atleta entrena, y acá aparecerá qué funciona.
      </div>
    </div>
  )

  const RESULTADO_COLOR = {
    optima    : '#10B981',
    buena     : '#3B82F6',
    incompleta: '#F59E0B',
    sobrecarga: '#EF4444',
    sin_datos : '#6B7280',
  }
  const RESULTADO_ICON = {
    optima:'✓', buena:'~', incompleta:'↓', sobrecarga:'↑', sin_datos:'?'
  }

  return (
    <div style={{maxWidth:620,margin:'0 auto',padding:'8px 0'}}>

      {/* Header */}
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:16}}>
        <div>
          <div style={{fontSize:16,fontWeight:700,color:C.text}}>📈 Lo que NOAH aprendió</div>
          <div style={{fontSize:12,color:C.text2,marginTop:2}}>
            Basado en sesiones completadas y biomarcadores
          </div>
        </div>
        <select value={dias} onChange={e=>setDias(Number(e.target.value))}
          style={{padding:'5px 10px',borderRadius:7,border:`1px solid ${C.border}`,
            background:C.bg3,color:C.text,fontSize:12}}>
          <option value={30}>30 días</option>
          <option value={60}>60 días</option>
          <option value={90}>90 días</option>
        </select>
      </div>

      {/* Alertas */}
      {data.alertas?.length > 0 && (
        <div style={{marginBottom:16}}>
          {data.alertas.map((a,i) => (
            <div key={i} style={{
              padding:'10px 14px', borderRadius:8, marginBottom:6,
              background: a.tipo==='alerta'?'#EF444411':'#F59E0B11',
              border:`1px solid ${a.tipo==='alerta'?'#EF444433':'#F59E0B33'}`,
              fontSize:12, color: a.tipo==='alerta'?'#EF4444':'#F59E0B',
            }}>
              {a.tipo==='alerta'?'⚠':'💡'} {a.msg}
            </div>
          ))}
        </div>
      )}

      {/* Absorción general */}
      {data.absorcion_pct != null && (
        <div style={{background:C.card,borderRadius:12,padding:'16px 20px',marginBottom:12,
          display:'flex',alignItems:'center',gap:16}}>
          <div style={{
            width:64,height:64,borderRadius:32,
            background:`conic-gradient(${data.absorcion_pct>=75?'#10B981':data.absorcion_pct>=50?'#3B82F6':'#F59E0B'} ${data.absorcion_pct}%, #ffffff11 0)`,
            display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0
          }}>
            <div style={{width:48,height:48,borderRadius:24,background:C.card,
              display:'flex',alignItems:'center',justifyContent:'center',
              fontSize:14,fontWeight:800,
              color:data.absorcion_pct>=75?'#10B981':data.absorcion_pct>=50?'#3B82F6':'#F59E0B'}}>
              {data.absorcion_pct}%
            </div>
          </div>
          <div>
            <div style={{fontSize:13,fontWeight:700,color:C.text}}>Tasa de absorción</div>
            <div style={{fontSize:12,color:C.text2,marginTop:2}}>
              {data.absorcion_pct>=75
                ? 'El atleta absorbe bien la carga prescripta'
                : data.absorcion_pct>=50
                ? 'Absorción moderada — revisar volumen o intensidad'
                : 'Absorción baja — la carga puede ser excesiva'}
            </div>
          </div>
        </div>
      )}

      {/* Resumen por resultado */}
      {data.resumen?.length > 0 && (
        <div style={{background:C.card,borderRadius:12,padding:'16px 20px',marginBottom:12}}>
          <div style={{fontSize:13,fontWeight:700,color:C.text,marginBottom:12}}>Resultados</div>
          {data.resumen.map((r,i) => {
            const col = RESULTADO_COLOR[r.resultado] || '#6B7280'
            const icon = RESULTADO_ICON[r.resultado] || '?'
            return (
              <div key={i} style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                <div style={{width:28,height:28,borderRadius:14,background:`${col}22`,
                  display:'flex',alignItems:'center',justifyContent:'center',
                  fontSize:12,fontWeight:800,color:col,flexShrink:0}}>
                  {icon}
                </div>
                <div style={{flex:1}}>
                  <div style={{display:'flex',justifyContent:'space-between',marginBottom:3}}>
                    <span style={{fontSize:12,fontWeight:600,color:C.text,textTransform:'capitalize'}}>
                      {r.resultado}
                    </span>
                    <span style={{fontSize:12,color:C.text2}}>{r.n} sesiones</span>
                  </div>
                  <div style={{height:5,background:C.bg,borderRadius:3}}>
                    <div style={{height:5,borderRadius:3,background:col,
                      width:`${Math.min(100,(r.n/Math.max(...data.resumen.map(x=>x.n)))*100)}%`}}/>
                  </div>
                </div>
                <div style={{fontSize:11,color:C.text3,minWidth:80,textAlign:'right'}}>
                  {r.cumpl_avg != null && `TSS ${Math.round(r.cumpl_avg*100)}%`}
                  {r.hrv_avg != null && ` HRV ${r.hrv_avg>0?'+':''}${r.hrv_avg}`}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Últimas sesiones */}
      {data.ultimas?.length > 0 && (
        <div style={{background:C.card,borderRadius:12,padding:'16px 20px'}}>
          <div style={{fontSize:13,fontWeight:700,color:C.text,marginBottom:12}}>
            Últimas sesiones evaluadas
          </div>
          {data.ultimas.map((u,i) => {
            const col = RESULTADO_COLOR[u.resultado] || '#6B7280'
            const s   = SPORT[u.sport] || SPORT.running
            return (
              <div key={i} style={{display:'flex',alignItems:'center',gap:10,
                padding:'8px 0',borderBottom:i<data.ultimas.length-1?`1px solid ${C.border}`:'none'}}>
                <s.Icon size={14} color={s.color} style={{flexShrink:0}}/>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{fontSize:12,color:C.text,fontWeight:500,
                    overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                    {u.nombre}
                  </div>
                  <div style={{fontSize:11,color:C.text2}}>
                    {u.fecha} · TSS {u.tss_plan}→{Math.round(u.tss_real||0)}
                    {u.impacto_hrv!=null && ` · HRV ${u.impacto_hrv>0?'+':''}${u.impacto_hrv}`}
                  </div>
                </div>
                <div style={{fontSize:11,fontWeight:700,color:col,
                  padding:'2px 8px',borderRadius:99,background:`${col}18`,flexShrink:0}}>
                  {RESULTADO_ICON[u.resultado]} {u.resultado}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}


function PerfilFisiologico({ atletaId, atleta }) {
  const [lthrRun,  setLthrRun]  = useState(atleta?.lthr_run  || '')
  const [lthrBike, setLthrBike] = useState(atleta?.lthr_bike || '')
  const [lthrSwim, setLthrSwim] = useState(atleta?.lthr_swim || '')
  const [ftp,      setFtp]      = useState(atleta?.ftp_watts || '')
  const [css,      setCss]      = useState(atleta?.css_100m  || '')
  const [hrMax,    setHrMax]    = useState(atleta?.hr_max    || '')
  const [pesoKg,   setPesoKg]   = useState(atleta?.peso_kg   || '')
  const [saving,   setSaving]   = useState(false)
  const [saved,    setSaved]    = useState(false)

  // Si cambia el atleta seleccionado, recargar los valores mostrados
  useEffect(() => {
    setLthrRun(atleta?.lthr_run  || '')
    setLthrBike(atleta?.lthr_bike || '')
    setLthrSwim(atleta?.lthr_swim || '')
    setFtp(atleta?.ftp_watts || '')
    setCss(atleta?.css_100m  || '')
    setHrMax(atleta?.hr_max    || '')
    setPesoKg(atleta?.peso_kg   || '')
  }, [atletaId])

  const guardar = async () => {
    setSaving(true)
    try {
      const body = {
        lthr_run:  lthrRun  ? Number(lthrRun)  : null,
        lthr_bike: lthrBike ? Number(lthrBike) : null,
        lthr_swim: lthrSwim ? Number(lthrSwim) : null,
        ftp_watts: ftp      ? Number(ftp)      : null,
        css_100m:  css      ? Number(css)      : null,
        hr_max:    hrMax    ? Number(hrMax)    : null,
        peso_kg:   pesoKg   ? Number(pesoKg)   : null,
      }
      await axios.put(`${API}/atletas/${atletaId}`, body, { headers: { 'Content-Type': 'application/json' } })
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch (e) {
      alert('Error guardando: ' + (e?.response?.data?.error || e.message))
    }
    setSaving(false)
  }

  const Campo = ({ label, value, setValue, unit, placeholder }) => (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, color: C.text2, marginBottom: 4 }}>{label}</div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <input type="number" value={value} placeholder={placeholder}
          onChange={e => setValue(e.target.value)}
          style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${C.border}`,
            background: C.bg2, color: C.text, fontSize: 14 }} />
        <span style={{ fontSize: 12, color: C.text2, minWidth: 50 }}>{unit}</span>
      </div>
    </div>
  )

  return (
    <div style={{ marginBottom: 28, paddingBottom: 24, borderBottom: `1px solid ${C.border}` }}>
      <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Perfil fisiologico</div>
      <div style={{ fontSize: 12, color: C.text2, marginBottom: 16 }}>
        Estos valores son la base real de las zonas de entrenamiento de este atleta.
        Si quedan vacios, NOAH usa un valor generico de referencia (no personalizado).
      </div>
      <Campo label="LTHR Running"  value={lthrRun}  setValue={setLthrRun}  unit="bpm" placeholder="ej: 165" />
      <Campo label="LTHR Ciclismo" value={lthrBike} setValue={setLthrBike} unit="bpm" placeholder="ej: 158" />
      <Campo label="LTHR Natacion" value={lthrSwim} setValue={setLthrSwim} unit="bpm" placeholder="ej: 150" />
      <Campo label="FTP (potencia umbral)" value={ftp} setValue={setFtp} unit="W" placeholder="ej: 220" />
      <div style={{ marginBottom: 14 }}>
        <div style={{ fontSize: 12, color: C.text2, marginBottom: 4 }}>CSS (ritmo critico natacion)</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <input type="number" value={css} placeholder="ej: 1.75"
            onChange={e => setCss(e.target.value)}
            style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${C.border}`,
              background: C.bg2, color: C.text, fontSize: 14 }} />
          <span style={{ fontSize: 12, color: C.text2, minWidth: 50 }}>min/100m</span>
          {css && (
            <span style={{ fontSize: 12, color: C.text3, minWidth: 55 }}>
              ≈ {Math.floor(Number(css))}:{String(Math.round((Number(css)%1)*60)).padStart(2,'0')}/100m
            </span>
          )}
        </div>
      </div>
      <Campo label="FC Maxima" value={hrMax} setValue={setHrMax} unit="bpm" placeholder="ej: 190" />
      <Campo label="Peso" value={pesoKg} setValue={setPesoKg} unit="kg" placeholder="ej: 72" />
      <button onClick={guardar} disabled={saving}
        style={{ padding: '10px 20px', borderRadius: 8, border: 'none',
          background: saved ? C.success : C.purple, color: '#fff', fontWeight: 700,
          cursor: saving ? 'wait' : 'pointer', fontSize: 13 }}>
        {saving ? 'Guardando...' : saved ? '✓ Guardado' : 'Guardar perfil fisiologico'}
      </button>
    </div>
  )
}

function PerfilDisponibilidad({ atletaId, atleta }) {
  const dep = atleta?.deporte_ppal || atleta?.deporte || 'running'

  // Defaults por deporte
  const DEFAULTS = {
    running:  { sesMin:3, sesMax:5, durSem:60,  durFin:120 },
    triatlon: { sesMin:6, sesMax:9, durSem:90,  durFin:300 },
    cycling:  { sesMin:3, sesMax:5, durSem:90,  durFin:300 },
    swimming: { sesMin:3, sesMax:5, durSem:60,  durFin:90  },
  }
  const def = DEFAULTS[dep] || DEFAULTS.running

  const [sesMin,  setSesMin]  = useState(def.sesMin)
  const [sesMax,  setSesMax]  = useState(def.sesMax)
  const [durSem,  setDurSem]  = useState(def.durSem)
  const [durFin,  setDurFin]  = useState(def.durFin)
  const [saving,  setSaving]  = useState(false)
  const [saved,   setSaved]   = useState(false)
  const [loaded,  setLoaded]  = useState(false)

  // Cargar perfil existente
  useEffect(() => {
    axios.get(`${API}/atletas/${atletaId}/perfil_macro`)
      .then(r => {
        const d = r.data?.data?.disponibilidad
        if (d) {
          setSesMin(d.sesiones_semana_min ?? def.sesMin)
          setSesMax(d.sesiones_semana_max ?? def.sesMax)
          setDurSem(d.dur_max_semana_min  ?? def.durSem)
          setDurFin(d.dur_max_finde_min   ?? def.durFin)
        }
        setLoaded(true)
      }).catch(() => setLoaded(true))
  }, [atletaId])

  const guardar = async () => {
    setSaving(true)
    try {
      await axios.post(
        `${API}/atletas/${atletaId}/disponibilidad`,
        { sesiones_semana_min: sesMin, sesiones_semana_max: sesMax,
          dur_max_semana_min: durSem, dur_max_finde_min: durFin },
        { headers: { 'Content-Type': 'application/json' } }
      )
      setSaved(true)
      setTimeout(() => setSaved(false), 2500)
    } catch(e) {
      alert('Error guardando: ' + (e?.response?.data?.error || e.message))
    }
    setSaving(false)
  }

  const Row = ({ label, value, setValue, min, max, step=1, unit='' }) => (
    <div style={{ marginBottom:20 }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
        <span style={{ fontSize:13, color:C.text2 }}>{label}</span>
        <span style={{ fontSize:14, fontWeight:700, color:C.purple }}>
          {value}{unit}
        </span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => setValue(Number(e.target.value))}
        style={{ width:'100%', accentColor:C.purple }} />
      <div style={{ display:'flex', justifyContent:'space-between', fontSize:11, color:C.text3, marginTop:3 }}>
        <span>{min}{unit}</span><span>{max}{unit}</span>
      </div>
    </div>
  )

  if (!loaded) return <div style={{padding:32,color:C.text2,textAlign:'center'}}>Cargando...</div>

  return (
    <div style={{ maxWidth:520, margin:'0 auto', padding:'8px 0' }}>
      <div style={{ fontSize:16, fontWeight:700, color:C.text, marginBottom:4 }}>⚙ Disponibilidad del atleta</div>
      <div style={{ fontSize:12, color:C.text2, marginBottom:24 }}>
        NOAH usa estos límites para escalar la duración y cantidad de sesiones de cada semana.
      </div>

      {/* Sesiones por semana */}
      <div style={{ background:C.card, borderRadius:12, padding:'20px 22px', marginBottom:16 }}>
        <div style={{ fontSize:13, fontWeight:700, color:C.text, marginBottom:16 }}>
          🗓 Sesiones por semana
        </div>
        <Row label="Mínimo de sesiones" value={sesMin} setValue={v => setSesMin(Math.min(v, sesMax))} min={1} max={7} />
        <Row label="Máximo de sesiones" value={sesMax} setValue={v => setSesMax(Math.max(v, sesMin))} min={1} max={14} />
        <div style={{ fontSize:11, color:C.text3, marginTop:4 }}>
          NOAH generará entre {sesMin} y {sesMax} sesiones según el estado del atleta esa semana.
        </div>
      </div>

      {/* Duración máxima */}
      <div style={{ background:C.card, borderRadius:12, padding:'20px 22px', marginBottom:16 }}>
        <div style={{ fontSize:13, fontWeight:700, color:C.text, marginBottom:16 }}>
          ⏱ Duración máxima por sesión
        </div>
        <Row label="Días de semana (lun-vie)" value={durSem} setValue={setDurSem} min={30} max={180} step={15} unit=" min" />
        <Row label="Fin de semana (sáb-dom)" value={durFin} setValue={setDurFin} min={45} max={360} step={15} unit=" min" />
        <div style={{ fontSize:11, color:C.text3, marginTop:4 }}>
          {dep === 'triatlon'
            ? 'Para IM: finde puede llegar a 5-6hs en pico de volumen.'
            : dep === 'cycling'
            ? 'Ciclistas de fondo: finde hasta 5hs en pico.'
            : 'Runner ultra: finde hasta 3-4hs en semanas de volumen máximo.'}
        </div>
      </div>

      {/* Botón guardar */}
      <button onClick={guardar} disabled={saving || saved} style={{
        width:'100%', padding:'12px 0', borderRadius:9, border:'none',
        background: saved ? C.done : C.purple,
        color:'#fff', fontSize:14, fontWeight:700, cursor:'pointer',
        transition:'background 0.3s'
      }}>
        {saving ? 'Guardando...' : saved ? '✓ Guardado' : 'Guardar disponibilidad'}
      </button>

      <div style={{ fontSize:11, color:C.text3, textAlign:'center', marginTop:10 }}>
        Los cambios aplican en el próximo ciclo semanal.
      </div>
    </div>
  )
}


function ClusteringPanel({ atletaId, atleta }) {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [hover, setHover]   = useState(null)
  const [dias, setDias]     = useState(180)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true); setData(null)
    authFetch(`${API}/atletas/${atletaId}/clustering?dias=${dias}&clusters=5`)
      .then(r => r.json())
      .then(r => { setData(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId, dias])

  if (loading) return (
    <div style={{padding:40,textAlign:'center',color:C.text2}}>
      Calculando clusters...
    </div>
  )
  if (!data || data.error) return (
    <div style={{padding:40,textAlign:'center',color:C.text2}}>
      {data?.error || 'Sin datos suficientes'}
    </div>
  )

  const clusters = data.clusters || []
  const historia = data.historia || []
  const hoy      = data.estado_hoy

  const W=460, H=300, PAD=36
  const xs_pca = historia.map(p=>p.pca_x)
  const ys_pca = historia.map(p=>p.pca_y)
  const xMin = Math.min(...xs_pca)-0.5, xMax = Math.max(...xs_pca)+0.5
  const yMin = Math.min(...ys_pca)-0.5, yMax = Math.max(...ys_pca)+0.5
  const sx = x => PAD + (x-xMin)/(xMax-xMin)*(W-PAD*2)
  const sy = y => H-PAD - (y-yMin)/(yMax-yMin)*(H-PAD*2)
  const colorC = id => clusters.find(c=>c.id===id)?.color||'#6B7280'

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:10}}>
        <div>
          <div style={{fontSize:16,fontWeight:800,color:C.text}}>🧬 Clustering de Estados — {atleta?.nombre}</div>
          <div style={{fontSize:11,color:C.text2,marginTop:2}}>
            {data.n_dias_analizados}d · {data.n_clusters} clusters · PCA {data.varianza_explicada}% varianza
          </div>
        </div>
        <div style={{display:'flex',gap:6}}>
          {[90,180,365].map(d=>(
            <button key={d} onClick={()=>setDias(d)} style={{
              padding:'4px 12px',borderRadius:7,fontSize:11,fontWeight:600,cursor:'pointer',
              border:'1px solid rgba(255,255,255,0.1)',
              background:dias===d?'rgba(139,92,246,0.2)':'transparent',
              color:dias===d?'#8B5CF6':'rgba(255,255,255,0.4)',
            }}>{d}d</button>
          ))}
        </div>
      </div>

      {hoy && (
        <div style={{borderRadius:14,padding:'16px 20px',background:`${hoy.color}15`,
          border:`1px solid ${hoy.color}40`,borderLeft:`5px solid ${hoy.color}`,
          display:'flex',alignItems:'center',gap:16,flexWrap:'wrap'}}>
          <div style={{fontSize:36}}>{hoy.icono}</div>
          <div style={{flex:1}}>
            <div style={{fontSize:10,fontWeight:700,color:hoy.color,textTransform:'uppercase',
              letterSpacing:1.5,marginBottom:4}}>ESTADO HOY</div>
            <div style={{fontSize:18,fontWeight:800,color:C.text,marginBottom:4}}>{hoy.nombre}</div>
            <div style={{fontSize:12,color:C.text2}}>{hoy.desc}</div>
          </div>
          <div style={{padding:'10px 16px',borderRadius:10,background:`${hoy.color}20`,
            border:`1px solid ${hoy.color}30`,fontSize:12,color:hoy.color,fontWeight:700,
            maxWidth:220,textAlign:'center'}}>
            💡 {hoy.accion}
          </div>
        </div>
      )}

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>
        {/* Cards clusters */}
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',
            letterSpacing:1,marginBottom:4}}>Distribución de estados</div>
          {clusters.map(c=>(
            <div key={c.id} style={{borderRadius:10,padding:'12px 14px',
              background:hoy?.id===c.id?`${c.color}18`:C.bg3,
              border:`1px solid ${hoy?.id===c.id?c.color+'50':C.border}`}}>
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                <div style={{fontSize:20,flexShrink:0}}>{c.icono}</div>
                <div style={{flex:1}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                    <span style={{fontSize:12,fontWeight:700,color:c.color}}>{c.nombre}</span>
                    <span style={{fontSize:11,color:C.text2,fontWeight:600}}>{c.pct_dias}% · {c.n_dias}d</span>
                  </div>
                  <div style={{height:3,borderRadius:99,background:'rgba(255,255,255,0.06)',marginTop:4,overflow:'hidden'}}>
                    <div style={{height:'100%',borderRadius:99,background:c.color,width:`${c.pct_dias}%`}}/>
                  </div>
                </div>
              </div>
              <div style={{display:'flex',gap:6,flexWrap:'wrap'}}>
                {[
                  ['HL',c.hl_media,c.color],
                  ['HRV',c.hrv_media?c.hrv_media+'ms':null,'#A78BFA'],
                  ['FC',c.fc_media?c.fc_media+'bpm':null,'#34D399'],
                  ['Sueño',c.sleep_media?c.sleep_media+'h':null,'#60A5FA'],
                  ['Stress',c.stress_media,'#FBBF24'],
                  ['TSB',c.tsb_media,c.tsb_media<-10?'#F87171':c.tsb_media>5?'#34D399':'#94A3B8'],
                ].filter(([,v])=>v!=null).map(([l,v,col])=>(
                  <div key={l} style={{padding:'2px 8px',borderRadius:6,
                    background:'rgba(255,255,255,0.05)',border:'1px solid rgba(255,255,255,0.08)',fontSize:10}}>
                    <span style={{color:'rgba(255,255,255,0.4)'}}>{l}: </span>
                    <span style={{color:col,fontWeight:700}}>{v}</span>
                  </div>
                ))}
                {c.score_auto!=null&&(
                  <div style={{padding:'2px 8px',borderRadius:6,marginLeft:'auto',
                    background:`${c.color}15`,border:`1px solid ${c.color}30`,
                    fontSize:9,color:c.color,fontWeight:700}}>
                    Auto {c.score_auto}/10 · Carga {c.score_carga}/10
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Scatter PCA */}
        <div style={{display:'flex',flexDirection:'column',gap:8}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',
            letterSpacing:1,marginBottom:4}}>Mapa de estados (PCA 2D)</div>
          <div style={{background:C.bg3,borderRadius:12,border:`1px solid ${C.border}`,
            overflow:'hidden',position:'relative'}}>
            <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}
              style={{display:'block',maxWidth:'100%',cursor:'crosshair'}}
              onMouseLeave={()=>setHover(null)}>
              {historia.map((p,i)=>{
                const col=colorC(p.cluster_id), isH=hover===i
                return <circle key={i} cx={sx(p.pca_x)} cy={sy(p.pca_y)}
                  r={isH?6:3} fill={col} opacity={isH?1:0.5}
                  stroke={isH?'#fff':'none'} strokeWidth="1.5"
                  style={{cursor:'pointer'}} onMouseEnter={()=>setHover(i)}/>
              })}
              {clusters.map(c=>(
                <g key={c.id}>
                  <circle cx={sx(c.pca_x)} cy={sy(c.pca_y)} r={10}
                    fill={c.color} opacity={0.2} stroke={c.color} strokeWidth="2"/>
                  <text x={sx(c.pca_x)} y={sy(c.pca_y)+4}
                    textAnchor="middle" fontSize="12">{c.icono}</text>
                </g>
              ))}
              {hoy?.pca_x_hoy!=null&&(
                <g>
                  <circle cx={sx(hoy.pca_x_hoy)} cy={sy(hoy.pca_y_hoy)}
                    r={9} fill="none" stroke="#fff" strokeWidth="2.5"/>
                  <circle cx={sx(hoy.pca_x_hoy)} cy={sy(hoy.pca_y_hoy)}
                    r={5} fill={hoy.color} stroke="#fff" strokeWidth="1.5"/>
                  <text x={sx(hoy.pca_x_hoy)+12} y={sy(hoy.pca_y_hoy)-8}
                    fontSize="9" fill="#fff" fontWeight="700">HOY</text>
                </g>
              )}
              {hover!=null&&historia[hover]&&(
                <g>
                  <rect x={Math.min(sx(historia[hover].pca_x)+10,W-120)}
                    y={sy(historia[hover].pca_y)-52} width={112} height={46} rx={6}
                    fill="rgba(10,10,20,0.95)" stroke={colorC(historia[hover].cluster_id)} strokeWidth="1"/>
                  <text x={Math.min(sx(historia[hover].pca_x)+16,W-114)}
                    y={sy(historia[hover].pca_y)-36} fontSize="9" fill="rgba(255,255,255,0.5)">
                    {historia[hover].fecha}</text>
                  <text x={Math.min(sx(historia[hover].pca_x)+16,W-114)}
                    y={sy(historia[hover].pca_y)-22} fontSize="11" fontWeight="700"
                    fill={colorC(historia[hover].cluster_id)}>
                    {clusters.find(c=>c.id===historia[hover].cluster_id)?.nombre||''}</text>
                  {historia[hover].hanna_life&&(
                    <text x={Math.min(sx(historia[hover].pca_x)+16,W-114)}
                      y={sy(historia[hover].pca_y)-9} fontSize="10" fill="rgba(255,255,255,0.6)">
                      HL: {historia[hover].hanna_life?.toFixed(0)}</text>
                  )}
                </g>
              )}
            </svg>
            <div style={{position:'absolute',bottom:6,left:8,display:'flex',gap:8,flexWrap:'wrap'}}>
              {clusters.map(c=>(
                <div key={c.id} style={{display:'flex',alignItems:'center',gap:3}}>
                  <div style={{width:7,height:7,borderRadius:'50%',background:c.color}}/>
                  <span style={{fontSize:8,color:C.text2}}>{c.nombre}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Serie temporal */}
      <div>
        <div style={{fontSize:11,fontWeight:700,color:C.text2,textTransform:'uppercase',
          letterSpacing:1,marginBottom:8}}>Evolución — últimos 60 días</div>
        <div style={{background:C.bg3,borderRadius:10,border:`1px solid ${C.border}`,
          padding:'10px 14px',display:'flex',gap:2,flexWrap:'wrap',alignItems:'center'}}>
          {historia.slice(-60).map((p,i)=>{
            const col=colorC(p.cluster_id)
            const cl=clusters.find(c=>c.id===p.cluster_id)
            return <div key={i} title={`${p.fecha} — ${cl?.nombre||''}`}
              style={{width:10,height:10,borderRadius:3,background:col,opacity:0.8,
                cursor:'pointer',transition:'transform 0.1s',flexShrink:0}}
              onMouseEnter={e=>e.currentTarget.style.transform='scale(1.8)'}
              onMouseLeave={e=>e.currentTarget.style.transform='scale(1)'}/>
          })}
        </div>
        <div style={{fontSize:10,color:C.text2,marginTop:6}}>
          Cada cuadrado = 1 día · hover para detalle
        </div>
      </div>
    </div>
  )
}

// ── OptimizerPanel ────────────────────────────────────────────────────────────
function OptimizerPanel({ atletaId, atleta }) {
  const [data, setData]           = useState(null)
  const [intelData, setIntelData] = useState(null)
  const [loading, setLoading]     = useState(true)
  const [aplicando, setApl]       = useState(false)
  const [msg, setMsg]             = useState(null)
  const [escSel, setEscSel]       = useState(null) // escenario seleccionado por el coach

  const cargar = (forzar=false) => {
    setLoading(true)
    authFetch(`${API}/atletas/${atletaId}/optimizer${forzar?'?forzar=true':''}`)
      .then(r=>r.json())
      .then(opt => {
        setData(opt.data)
        if (opt.data?.escenarios_coach?.escenarios?.length > 0) {
          setIntelData(opt.data.escenarios_coach)
          setEscSel(2) // default: Mantenimiento (index 2)
        }
        setLoading(false)
      }).catch(()=>setLoading(false))
  }

  useEffect(()=>{ if(atletaId) cargar() }, [atletaId])

  const aplicar = (receta, tss_override=null, escenario_nombre=null) => {
    setApl(true)
    authFetch(`${API}/atletas/${atletaId}/optimizer/aplicar`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({receta, tss_override, escenario_nombre})
    }).then(r=>r.json()).then(r=>{
      setMsg(r.data?.msg || 'Receta aplicada')
      setApl(false)
      setTimeout(()=>setMsg(null), 5000)
    }).catch(()=>setApl(false))
  }

  const aplicarEscenario = () => {
    if (escSel === null || !intelData?.escenarios) return
    const esc = intelData.escenarios[escSel]
    aplicar('coach_escenario', esc.tss_semana, esc.nombre)
  }

  if (loading) return (
    <div style={{padding:40,textAlign:'center',color:C.text2}}>
      Calculando optimizador...
    </div>
  )
  if (!data || data.error) return (
    <div style={{padding:32,display:'flex',flexDirection:'column',gap:12}}>
      <div style={{color:C.text2}}>{data?.error || 'Sin datos del optimizador'}</div>
      <button onClick={()=>cargar(true)} style={{
        padding:'8px 16px',borderRadius:8,border:`1px solid ${C.purple}`,
        background:'transparent',color:C.purple,cursor:'pointer',alignSelf:'flex-start',
      }}>Recalcular</button>
    </div>
  )

  const clust    = data.clustering || {}
  const clusters = clust.clusters || []
  const historia = clust.historia || []
  const receta   = data.receta || {}
  const kp       = data.k_params || {}
  const rec      = receta.receta_recomendada
  const sim      = receta.receta_seleccionada || {}
  const est      = data.estado_actual || {}

  const RECETA_COL = {
    volumen:'#3B82F6', calidad:'#F59E0B', mixta:'#8B5CF6',
    recuperacion:'#EF4444', recuperacion_activa:'#F97316',
    aumentar_carga:'#10B981', reducir_carga:'#94A3B8', mantener:'#6B7280',
  }
  const recCol = RECETA_COL[rec] || C.purple

  // PCA scatter
  const PCA_W=320, PCA_H=220
  const allX = [...clusters.map(c=>c.pca_x), ...historia.map(h=>h.pca_x)]
  const allY = [...clusters.map(c=>c.pca_y), ...historia.map(h=>h.pca_y)]
  const xMin=Math.min(...allX)-0.5, xMax=Math.max(...allX)+0.5
  const yMin=Math.min(...allY)-0.5, yMax=Math.max(...allY)+0.5
  const toSvgX = v => 20+(v-xMin)/(xMax-xMin)*(PCA_W-40)
  const toSvgY = v => 20+(1-(v-yMin)/(yMax-yMin))*(PCA_H-40)

  const trayectoria = sim.trayectoria || []

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:8}}>
        <div>
          <div style={{fontSize:15,fontWeight:800,color:C.text,marginBottom:2}}>🎯 NOAH Optimizer</div>
          <div style={{fontSize:11,color:C.text2}}>
            {data.n_semanas_analizadas} semanas · {clusters.length} clusters ·
            PCA {clust.var_explicada_pca}% varianza ·
            τCTL={kp.tau_ctl}d τATL={kp.tau_atl}d
          </div>
        </div>
        <button onClick={()=>cargar(true)} style={{
          padding:'6px 12px',borderRadius:7,border:`1px solid ${C.border}`,
          background:'transparent',color:C.text2,cursor:'pointer',fontSize:11,
        }}>🔄 Recalcular</button>
      </div>

      {msg && (
        <div style={{padding:'10px 16px',borderRadius:8,background:'rgba(16,185,129,0.1)',
          border:'1px solid rgba(16,185,129,0.3)',color:'#10B981',fontSize:12}}>
          ✓ {msg}
        </div>
      )}

      {/* ── 5 Escenarios del Coach (PMC + Banister + ML) ── */}
      {intelData && intelData.escenarios && (
        <div style={{background:C.bg3, borderRadius:12, padding:'16px 18px',
          border:`1px solid ${C.purple}33`}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,
            textTransform:'uppercase',letterSpacing:1,marginBottom:4}}>
            Escenarios de Carga — Elegí el que vas a aplicar
          </div>
          {intelData.rango && (
            <div style={{fontSize:10,color:C.text3,marginBottom:12}}>
              Micro 4sem: <b style={{color:C.text}}>{intelData.rango.micro_4sem}</b> TSS ·
              Macro 12sem: <b style={{color:C.text}}>{intelData.rango.macro_12sem}</b> TSS ·
              Contexto: <b style={{color:C.purple}}>{intelData.rango.contexto?.replace(/_/g,' ')}</b>
              {intelData.rango.n_semanas_atipicas > 0 && (
                <span style={{color:C.amber}}> · ⚠ {intelData.rango.n_semanas_atipicas} sem atípica/s</span>
              )}
            </div>
          )}
          <div style={{display:'flex',gap:8,flexWrap:'wrap',marginBottom:14}}>
            {intelData.escenarios.map((esc, i) => {
              const sel = escSel === i
              const sem = esc.semaforo || 'amarillo'
              const semCol = sem==='verde'?'#10B981':sem==='rojo'?'#EF4444':'#F59E0B'
              const recML = esc.recomendado_ml
              const recBase = esc.recomendado_base
              return (
                <div key={i} onClick={()=>setEscSel(i)} style={{
                  flex:1, minWidth:120, padding:'10px 12px', borderRadius:10,
                  cursor:'pointer', transition:'all 0.15s',
                  background: sel ? `${C.purple}18` : C.bg2,
                  border: sel ? `2px solid ${C.purple}` : `1px solid ${C.border}`,
                  position:'relative',
                }}>
                  {(recML || recBase) && (
                    <div style={{position:'absolute',top:-8,right:6,
                      fontSize:8,fontWeight:800,padding:'2px 6px',borderRadius:99,
                      background: recML ? '#10B981' : C.purple,
                      color:'white'}}>
                      {recML ? 'ML ★' : 'BASE'}
                    </div>
                  )}
                  <div style={{fontSize:10,fontWeight:700,color:sel?C.purple:C.text2,
                    marginBottom:6}}>{esc.nombre}</div>
                  <div style={{fontSize:18,fontWeight:800,color:C.text,marginBottom:2}}>
                    {esc.tss_semana} <span style={{fontSize:10,color:C.text3}}>TSS</span>
                  </div>
                  <div style={{fontSize:11,color:esc.delta_ctl>=0?'#2DE3A7':'#FF5C7A',
                    fontWeight:700,marginBottom:4}}>
                    CTL {esc.delta_ctl>=0?'+':''}{esc.delta_ctl?.toFixed(1)} en 4 sem
                  </div>
                  <div style={{display:'flex',alignItems:'center',gap:4}}>
                    <div style={{width:8,height:8,borderRadius:'50%',
                      background:semCol}}/>
                    <span style={{fontSize:10,color:C.text3}}>
                      {esc.prob_absorcion != null
                        ? `Abs ${(esc.prob_absorcion*100).toFixed(0)}%`
                        : sem}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <button onClick={aplicarEscenario} disabled={aplicando||escSel===null} style={{
              padding:'9px 22px',borderRadius:8,border:'none',cursor:'pointer',
              background:C.purple,color:'white',fontWeight:700,fontSize:13,
              opacity:aplicando?0.6:1,
            }}>
              {aplicando ? 'Aplicando...' : `✓ Aplicar: ${intelData.escenarios[escSel]?.nombre||''}`}
            </button>
            {escSel !== null && (
              <span style={{fontSize:11,color:C.text3}}>
                {intelData.escenarios[escSel]?.tss_semana} TSS/sem · 
                CTL {intelData.escenarios[escSel]?.delta_ctl>=0?'+':''}
                {intelData.escenarios[escSel]?.delta_ctl?.toFixed(1)} en 4 sem
              </span>
            )}
          </div>
        </div>
      )}

      {/* Estado + Receta */}
      <div style={{display:'flex',gap:12,flexWrap:'wrap'}}>

        {/* Estado actual */}
        <div style={{flex:1,minWidth:180,padding:'14px 16px',borderRadius:12,
          background:C.bg3,border:`1px solid ${C.border}`}}>
          <div style={{fontSize:10,fontWeight:700,color:C.text2,
            textTransform:'uppercase',letterSpacing:1,marginBottom:10}}>Estado Actual</div>
          {[
            {l:'CTL',v:est.ctl?.toFixed(1),c:'#7C6CFF'},
            {l:'ATL',v:est.atl?.toFixed(1),c:'#FF5C7A'},
            {l:'TSB',v:est.tsb?.toFixed(1),c:'#2DE3A7'},
            {l:'HANNA',v:est.hanna_life?.toFixed(0),c:'#F59E0B'},
          ].map(m=>(
            <div key={m.l} style={{display:'flex',justifyContent:'space-between',
              alignItems:'center',marginBottom:5}}>
              <span style={{fontSize:11,color:C.text2}}>{m.l}</span>
              <span style={{fontSize:14,fontWeight:700,color:m.c}}>{m.v||'--'}</span>
            </div>
          ))}
          <div style={{fontSize:10,color:C.text3,marginTop:8,
            borderTop:`1px solid ${C.border}`,paddingTop:8}}>
            Fase: <b style={{color:C.purple}}>{data.fase_actual}</b>
            {data.sem_hasta_carrera!=null && (
              <span> · Carrera en <b style={{color:'#EF4444'}}>{data.sem_hasta_carrera} sem</b></span>
            )}
          </div>
        </div>

        {/* Receta */}
        <div style={{flex:2,minWidth:240,padding:'14px 16px',borderRadius:12,
          background:C.bg3,border:`1px solid ${recCol}40`}}>
          <div style={{fontSize:10,fontWeight:700,color:C.text2,
            textTransform:'uppercase',letterSpacing:1,marginBottom:8}}>Receta Recomendada</div>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
            <div style={{padding:'5px 14px',borderRadius:99,fontSize:12,fontWeight:800,
              background:`${recCol}22`,color:recCol,border:`1px solid ${recCol}50`}}>
              {rec?.replace(/_/g,' ').toUpperCase() || '--'}
            </div>
          </div>
          <div style={{fontSize:11,color:C.text2,marginBottom:10,lineHeight:1.5}}>
            {receta.razon}
          </div>
          {sim.ctl_final_pred && (
            <div style={{display:'flex',gap:14,flexWrap:'wrap',marginBottom:10}}>
              {[
                {l:'CTL en 4 sem',v:sim.ctl_final_pred?.toFixed(1),c:'#7C6CFF'},
                {l:'ΔCTL',v:(sim.delta_ctl_pred>0?'+':'')+sim.delta_ctl_pred?.toFixed(1),c:'#2DE3A7'},
                {l:'Prob. completar',v:`${(sim.prob_completar*100)?.toFixed(0)}%`,c:'#84CC16'},
              ].map(m=>(
                <div key={m.l}>
                  <div style={{fontSize:9,color:C.text2,textTransform:'uppercase',letterSpacing:0.5}}>{m.l}</div>
                  <div style={{fontSize:16,fontWeight:800,color:m.c}}>{m.v}</div>
                </div>
              ))}
            </div>
          )}
          <button onClick={()=>aplicar(rec)} disabled={aplicando||!rec} style={{
            padding:'7px 18px',borderRadius:7,border:'none',cursor:'pointer',
            background:recCol,color:'white',fontWeight:700,fontSize:12,
            opacity:aplicando?0.6:1,
          }}>
            {aplicando ? 'Aplicando...' : '✓ Aplicar esta receta'}
          </button>
        </div>
      </div>

{/* Comparativa vieja eliminada — reemplazada por Escenarios PMC+ML arriba */}

      {/* PCA + Clusters */}
      <div style={{display:'flex',gap:12,flexWrap:'wrap'}}>

        {/* Scatter PCA */}
        <div style={{flex:1,minWidth:280,background:C.bg3,borderRadius:12,
          padding:'14px 16px',border:`1px solid ${C.border}`}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,
            textTransform:'uppercase',letterSpacing:1,marginBottom:8}}>
            Mapa PCA — {data.n_semanas_analizadas} semanas
          </div>
          <svg width="100%" viewBox={`0 0 ${PCA_W} ${PCA_H}`}>
            {historia.map((h,i)=>{
              const c = clusters.find(cl=>cl.id===h.cluster_id)
              return <circle key={i} cx={toSvgX(h.pca_x)} cy={toSvgY(h.pca_y)}
                r={3} fill={c?.color||'#6B7280'} opacity={0.4}/>
            })}
            {clusters.map((c,i)=>(
              <g key={i}>
                <circle cx={toSvgX(c.pca_x)} cy={toSvgY(c.pca_y)}
                  r={10} fill={c.color} opacity={0.2}/>
                <circle cx={toSvgX(c.pca_x)} cy={toSvgY(c.pca_y)}
                  r={5} fill={c.color} opacity={0.9}/>
                <text x={toSvgX(c.pca_x)} y={toSvgY(c.pca_y)-9}
                  textAnchor="middle" fontSize="8" fill={c.color} fontWeight="700">
                  {c.nombre?.split(' ')[0]}
                </text>
              </g>
            ))}
            {data.cluster_actual && (
              <g>
                <circle cx={toSvgX(data.cluster_actual.pca_x_hoy||data.cluster_actual.pca_x)}
                  cy={toSvgY(data.cluster_actual.pca_y_hoy||data.cluster_actual.pca_y)}
                  r={7} fill="white" stroke={recCol} strokeWidth="2.5"/>
                <text x={toSvgX(data.cluster_actual.pca_x_hoy||data.cluster_actual.pca_x)}
                  y={toSvgY(data.cluster_actual.pca_y_hoy||data.cluster_actual.pca_y)+16}
                  textAnchor="middle" fontSize="8" fill="white" fontWeight="700">HOY</text>
              </g>
            )}
          </svg>
        </div>

        {/* Lista clusters */}
        <div style={{flex:1,minWidth:240,display:'flex',flexDirection:'column',gap:6}}>
          <div style={{fontSize:11,fontWeight:700,color:C.text2,
            textTransform:'uppercase',letterSpacing:1}}>Clusters identificados</div>
          {clusters.map((c,i)=>(
            <div key={i} style={{padding:'10px 12px',borderRadius:10,
              background:C.bg3,border:`1px solid ${c.color}25`}}>
              <div style={{display:'flex',justifyContent:'space-between',
                alignItems:'center',marginBottom:4}}>
                <span style={{fontSize:12,fontWeight:700,color:c.color}}>{c.nombre}</span>
                <span style={{fontSize:10,color:C.text2}}>{c.pct_semanas}%</span>
              </div>
              <div style={{display:'flex',gap:10}}>
                <span style={{fontSize:10,color:C.text2}}>
                  Auto: <b style={{color:'#2DE3A7'}}>{c.score_auto?.toFixed(1)}</b>
                </span>
                <span style={{fontSize:10,color:C.text2}}>
                  Carga: <b style={{color:'#7C6CFF'}}>{c.score_carga?.toFixed(1)}</b>
                </span>
                <span style={{fontSize:10,color:C.text2}}>
                  ΔCTLnxt: <b style={{color:c.delta_ctl_sig>0?'#2DE3A7':'#FF5C7A'}}>
                    {c.delta_ctl_sig>0?'+':''}{c.delta_ctl_sig?.toFixed(1)||'--'}
                  </b>
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

    </div>
  )
}


function ResumenCumplimientoCoach({ atletaId }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [dias, setDias]       = useState(30)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    authFetch(`${API}/atletas/${atletaId}/resumen_cumplimiento?dias=${dias}`)
      .then(r => r.json())
      .then(r => { setData(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId, dias])

  if (loading) return (
    <Card style={{textAlign:'center',color:C.text2,fontSize:12}}>Cargando resumen...</Card>
  )
  if (!data) return null

  const pct = data.pct_horas
  const pctColor = pct == null ? C.text2 : pct >= 90 ? C.done : pct >= 70 ? C.amber : C.miss

  return (
    <Card>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14}}>
        <SectionTitle>Cumplimiento — {data.periodo_dias} días</SectionTitle>
        <select value={dias} onChange={e=>setDias(Number(e.target.value))} style={{
          padding:'4px 8px', borderRadius:6, border:`1px solid ${C.border}`,
          background:C.bg3, color:C.text, fontSize:11,
        }}>
          <option value={7}>7 días</option>
          <option value={30}>30 días</option>
          <option value={90}>90 días</option>
        </select>
      </div>

      <div style={{display:'flex',alignItems:'baseline',gap:8,marginBottom:4}}>
        <span style={{fontSize:28,fontWeight:800,color:pctColor}}>{pct != null ? `${pct}%` : '--'}</span>
        <span style={{fontSize:12,color:C.text2}}>de las horas prescriptas</span>
      </div>
      <div style={{fontSize:11,color:C.text3,marginBottom:16}}>
        {data.horas_realizadas}h realizadas de {data.horas_prescriptas}h planificadas
      </div>

      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10}}>
        {[
          {label:'Completadas', value:data.sesiones_completadas, color:C.done},
          {label:'No realizadas', value:data.sesiones_no_realizadas, color:C.miss},
          {label:'Extra (no planificadas)', value:data.sesiones_extra, color:C.amber},
        ].map(({label,value,color}) => (
          <div key={label} style={{background:C.bg3,borderRadius:8,padding:'10px 12px',
            border:`1px solid ${C.border}`,textAlign:'center'}}>
            <div style={{fontSize:20,fontWeight:800,color}}>{value}</div>
            <div style={{fontSize:9,color:C.text3,marginTop:2,lineHeight:1.3}}>{label}</div>
          </div>
        ))}
      </div>
    </Card>
  )
}


function ProyeccionMultideporteCoach({ atletaId }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    authFetch(`${API}/atletas/${atletaId}/proyeccion_multideporte`)
      .then(r => r.json())
      .then(r => { setData(r.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId])

  if (loading) return <div style={{textAlign:'center',color:C.text2,fontSize:12,padding:'12px 0'}}>Calculando proyección...</div>
  if (!data || data.msg) return (
    <div style={{textAlign:'center',color:C.text2,fontSize:12,padding:'12px 0'}}>
      {data?.msg || 'Sin datos de proyección todavía'}
    </div>
  )

  const DEPORTES = [
    {key:'running',  label:'🏃 Running',  color:C.purple},
    {key:'cycling',  label:'🚴 Ciclismo', color:C.blue},
    {key:'swimming', label:'🏊 Natación', color:'#34D399'},
  ]
  const conDatos = DEPORTES.filter(d => data[d.key])
  if (conDatos.length === 0) return null

  return (
    <div>
      <SectionTitle>Proyección hacia la carrera — por disciplina</SectionTitle>
      <div style={{ fontSize:11, color:C.text3, marginBottom:16 }}>
        Fecha límite de carga = último día para seguir sumando antes de tener que empezar a bajar (taper)
      </div>
      <div style={{display:'flex',flexDirection:'column',gap:20}}>
        {conDatos.map(({key,label,color}) => {
          const d = data[key]
          return (
            <div key={key} style={{borderTop:`2px solid ${color}`,paddingTop:12}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6}}>
                <span style={{fontSize:12,fontWeight:700,color}}>{label}</span>
                {!d.invariantes_ok && (
                  <span style={{fontSize:9,fontWeight:700,color:C.miss,background:`${C.miss}18`,padding:'2px 7px',borderRadius:99}}>⚠ revisar</span>
                )}
              </div>
              <div style={{display:'flex',gap:16,flexWrap:'wrap',fontSize:11,color:C.text2,marginBottom:6}}>
                <span>CTL actual <b style={{color:C.text}}>{d.ctl_actual ?? '--'}</b></span>
                <span>CTL pico <b style={{color:C.text}}>{d.ctl_pico ?? '--'}</b></span>
                <span>TSB en carrera <b style={{color:C.text}}>{d.tsb_carrera_A ?? '--'}</b></span>
              </div>
              <div style={{fontSize:12,fontWeight:700,color:C.amber}}>
                📅 Fecha límite de carga: {d.fecha_inicio_taper || '--'}
              </div>
              {d.notas?.length > 0 && (
                <div style={{marginTop:6,display:'flex',flexDirection:'column',gap:2}}>
                  {d.notas.map((n,i) => (
                    <div key={i} style={{fontSize:10,color:n.startsWith('⚠')?C.miss:C.text3}}>{n}</div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}


function VelocidadCriticaBotonesCoach({ atletaId }) {
  const [data, setData]       = useState(null)
  const [abierto, setAbierto] = useState(false)
  const [cargando, setCargando] = useState(false)

  const cargar = async () => {
    if (data) return
    setCargando(true)
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/velocidad_critica`)
      const d = await r.json()
      setData(d.data || d)
    } catch {}
    setCargando(false)
  }

  const toggle = () => {
    setAbierto(o => !o)
    if (!data) cargar()
  }

  return (
    <div style={{ marginTop:8 }}>
      <button onClick={toggle} style={{
        width:'100%', padding:'10px 0', borderRadius:10, fontSize:13, fontWeight:700,
        background: abierto ? C.purple : `${C.purple}18`,
        color: abierto ? '#fff' : C.purple,
        border:`1.5px solid ${abierto ? C.purple : C.purple+'40'}`,
        cursor:'pointer',
      }}>{cargando && !data ? '⏳' : '🏃 Velocidad Crítica'}</button>

      {abierto && (
        <div style={{ marginTop:10 }}>
          {!data && cargando && (
            <div style={{ textAlign:'center', padding:20, color:C.text2, fontSize:12 }}>Calculando...</div>
          )}
          {data && !data.disponible && (
            <div style={{ textAlign:'center', padding:16, color:C.text2, fontSize:12 }}>📡 {data.msg}</div>
          )}
          {data && data.disponible && (
            <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
              <div style={{ flex:1, minWidth:120, background:'#F9731612', borderRadius:8, padding:'8px 12px', border:'1px solid #F9731625' }}>
                <div style={{ fontSize:10, color:C.text2 }}>CS (Velocidad Crítica)</div>
                <div style={{ fontSize:18, fontWeight:800, color:'#F97316' }}>
                  {data.cs_pace_min_km ? `${Math.floor(data.cs_pace_min_km)}:${String(Math.round((data.cs_pace_min_km%1)*60)).padStart(2,'0')}/km` : '--'}
                </div>
              </div>
              <div style={{ flex:1, minWidth:120, background:'#A855F712', borderRadius:8, padding:'8px 12px', border:'1px solid #A855F725' }}>
                <div style={{ fontSize:10, color:C.text2 }}>D' (capacidad anaeróbica)</div>
                <div style={{ fontSize:18, fontWeight:800, color:'#A855F7' }}>
                  {data.d_prime_m ? `${Math.round(data.d_prime_m)}m` : '--'}
                </div>
              </div>
            </div>
          )}
          {data && data.disponible && <ExplicacionCSCoach data={data} />}
        </div>
      )}
    </div>
  )
}




function ExplicacionCSCoach({ data }) {
  const puntos = [
    data.fastest_1k  && { label:'1k',  km:1,  seg:data.fastest_1k  },
    data.fastest_5k  && { label:'5k',  km:5,  seg:data.fastest_5k  },
    data.fastest_10k && { label:'10k', km:10, seg:data.fastest_10k },
  ].filter(Boolean).map(p => ({ ...p, pace: (p.seg/p.km)/60 }))

  if (!data.cs_pace_min_km || puntos.length === 0) return null

  const csPace = data.cs_pace_min_km
  const todos = [...puntos, { label:'CS', pace:csPace, esCS:true }]
  const paceMin = Math.min(...todos.map(p=>p.pace)) - 0.06
  const paceMax = Math.max(...todos.map(p=>p.pace)) + 0.06

  const CX=140, CY=128, R=104
  const anguloDe = (pace) => 180 - ((pace-paceMin)/(paceMax-paceMin))*180
  const puntoArco = (pace, r=R) => {
    const a = anguloDe(pace) * Math.PI/180
    return { x: CX + r*Math.cos(a), y: CY - r*Math.sin(a) }
  }
  const fmtP = (p) => `${Math.floor(p)}:${String(Math.round((p%1)*60)).padStart(2,'0')}`

  const inicio = puntoArco(paceMin)
  const fin    = puntoArco(paceMax)
  const csPos  = puntoArco(csPace)
  const csIn   = puntoArco(csPace, R-13)
  const csOut  = puntoArco(csPace, R+13)

  return (
    <div style={{ marginTop:14, padding:'14px 14px 10px', background:C.bg3, borderRadius:10, border:`1px solid ${C.border}` }}>
      <div style={{ fontSize:10.5, color:C.text2, marginBottom:4, lineHeight:1.5, textAlign:'center' }}>
        Cuanto más lejos del rojo (esfuerzo corto/anaeróbico), más cerca del límite sostenible
      </div>
      <svg viewBox="0 0 280 145" style={{ width:'100%', maxWidth:320, display:'block', margin:'0 auto' }}>
        <defs>
          <linearGradient id="gaugeCSCoach" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%"  stopColor="#EF4444"/>
            <stop offset="35%" stopColor="#F97316"/>
            <stop offset="65%" stopColor="#FACC15"/>
            <stop offset="100%" stopColor="#38BDF8"/>
          </linearGradient>
        </defs>

        <path d={`M ${inicio.x} ${inicio.y} A ${R} ${R} 0 0 1 ${fin.x} ${fin.y}`}
          stroke="url(#gaugeCSCoach)" strokeWidth="13" fill="none" strokeLinecap="round" opacity="0.9"/>

        <line x1={csIn.x} y1={csIn.y} x2={csOut.x} y2={csOut.y}
          stroke="#fff" strokeWidth="3.5" strokeLinecap="round"/>
        <circle cx={csPos.x} cy={csPos.y} r="5" fill="#38BDF8" stroke="#fff" strokeWidth="1.5"/>

        {puntos.map((p,i) => {
          const pos = puntoArco(p.pace)
          const arriba = pos.y < CY - 20
          return (
            <g key={i}>
              <circle cx={pos.x} cy={pos.y} r="5" fill={C.bg3} stroke="#EF4444" strokeWidth="2.5"/>
              <text x={pos.x} y={arriba ? pos.y-12 : pos.y+20} textAnchor="middle"
                fontSize="9" fontWeight="700" fill={C.text2}>{p.label}</text>
              <text x={pos.x} y={arriba ? pos.y-2 : pos.y+30} textAnchor="middle"
                fontSize="8.5" fill={C.text3}>{fmtP(p.pace)}</text>
            </g>
          )
        })}

        <text x={CX} y={CY+2} textAnchor="middle" fontSize="22" fontWeight="800" fill="#38BDF8">
          {fmtP(csPace)}
        </text>
        <text x={CX} y={CY+18} textAnchor="middle" fontSize="9" fontWeight="700" fill={C.text2} letterSpacing="1">
          CS · min/km
        </text>
      </svg>
    </div>
  )
}
