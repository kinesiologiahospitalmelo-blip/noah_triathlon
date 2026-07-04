// src/AtletaDashboard.jsx — NOA Athlete Dashboard v5 — Estilo Garmin/TrainingPeaks
import { useState, useEffect, useRef, memo, useCallback } from 'react'
import GraficoActividadStreams from './GraficoActividadStreams'
import SeccionRace from './SeccionRace'
import SeccionTests from './SeccionTests'
import axios from 'axios'
import {
  LineChart, Line, BarChart, Bar, AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid, ReferenceLine, Cell
} from 'recharts'
import {
  Footprints, Bike as BikeIcon, Waves, Calendar, CalendarDays, BarChart3, TrendingUp, TrendingDown,
  Target, Flag, FlaskConical, CheckCircle2, XCircle, AlertTriangle, Zap, Ruler,
  HeartPulse, Flame, Activity, RotateCw, Satellite, ClipboardList, User, BatteryFull,
  BatteryLow, Moon, GlassWater, Brain, ChevronLeft, ChevronRight, Banana, Minus, Check, Scale, LogOut
} from 'lucide-react'

// API — en la PC/celular de casa (red local) sigue usando el puerto 5000,
// como ya funcionaba. En Vercel (1 sola dirección para front y backend)
// no hay puerto separado: todo entra por /api en el mismo dominio. El
// navegador ya sabe en qué dirección está parado — solo se le pregunta.
const esLocal = window.location.hostname === "localhost" || window.location.hostname.startsWith("192.168.")
const API = esLocal
  ? `http://${window.location.hostname}:5000/api`
  : "/api"

// authFetch — wrapper de fetch que agrega el token de sesión guardado por
// el login (mismo localStorage que usa App.js) a cada petición. Reemplaza
// los usos de fetch() nativo en este archivo, que no pasan por el
// interceptor de axios definido en App.js. Si el backend responde 401
// (sesión vencida/inválida), limpia la sesión y manda a /login.
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

// ── PALETA NOAH v6 — armónica y reducida ───────────────────────────────────
// Un único acento (violeta) + 4 colores semánticos fijos (éxito/alerta/peligro/info).
// Las zonas de entrenamiento usan una escala secuencial del mismo acento en vez
// de colores arbitrarios sin relación entre sí. Todo color usado en el archivo
// debe salir de este objeto — no se permiten hex sueltos en los componentes.
const NOAH_C = {
  pageBg:  '#0A0F1E',
  cardBg:  'transparent',
  cardBg2: 'transparent',
  headerBg:'rgba(10,15,30,0.92)',
  border:  'rgba(255,255,255,0.08)',
  border2: 'rgba(255,255,255,0.13)',
  ink:     'rgba(255,255,255,0.92)',
  ink2:    'rgba(255,255,255,0.70)',
  ink3:    'rgba(255,255,255,0.45)',
  ink4:    'rgba(255,255,255,0.28)',

  // Acento único de marca (violeta) — todo lo "interactivo/destacado" usa esta familia
  accent:  '#8B5CF6', accentL: 'rgba(139,92,246,0.14)', accentDim: '#6D28D9',

  // Deportes — derivados del acento, no colores nuevos sin relación
  run:     '#A78BFA', runL: 'rgba(167,139,250,0.14)',
  bike:    '#38BDF8', bikeL: 'rgba(56,189,248,0.12)',
  swim:    '#34D399', swimL: 'rgba(52,211,153,0.12)',

  // Métricas de carga
  ctl:     '#8B5CF6', atl: '#F87171',
  tsbPos:  '#34D399', tsbNeg: '#F87171', tsbNeu: '#F59E0B',
  hrv:     '#A78BFA',

  // 4 colores semánticos — ÚNICOS en toda la app para estos significados
  success: '#34D399', successL: 'rgba(52,211,153,0.14)',
  warning: '#F59E0B', warningL: 'rgba(245,158,11,0.14)',
  danger:  '#F87171', dangerL:  'rgba(248,113,113,0.14)',
  info:    '#60A5FA', infoL:    'rgba(96,165,250,0.12)',
  amber:   '#F59E0B', // alias retro-compatible

  // Estados de sesión — mapeados a los 4 semánticos (no colores nuevos)
  done:    '#34D399', doneL: 'rgba(52,211,153,0.14)',
  miss:    '#F87171', missL: 'rgba(248,113,113,0.14)',
  partial: '#F59E0B', partialL: 'rgba(245,158,11,0.14)',
  planned: '#60A5FA', plannedL: 'rgba(96,165,250,0.12)',

  // Zonas — escala secuencial de un solo eje cromático (frío→cálido), no arcoíris suelto
  z1:'#94A3B8', z2:'#5EEAD4', z3:'#F59E0B', z4:'#FB923C', z5:'#F87171', z6:'#C084FC',
  bz1:'#BAE6FD', bz2:'#5EEAD4', bz3:'#38BDF8', bz4:'#8B5CF6', bz5:'#A78BFA', bz6:'#C084FC', bz7:'#F87171',
}

// ── SISTEMA DE DISEÑO PREMIUM v2 — glassmorphism, glow, profundidad ─────────
// Tokens reutilizables para que toda la app tenga la misma identidad visual:
// tarjetas que "flotan" del fondo, blur real, sombras con color del propio
// acento (no solo negro plano), y gradientes sutiles en vez de superficies lisas.
const DS = {
  // Vidrio esmerilado — para tarjetas, modales, headers flotantes
  glass: (tint = 'rgba(255,255,255,0.06)') => ({
    background: tint,
    backdropFilter: 'blur(18px) saturate(140%)',
    WebkitBackdropFilter: 'blur(18px) saturate(140%)',
    border: '1px solid rgba(255,255,255,0.10)',
  }),
  // Tarjeta elevada con sombra de profundidad + leve glow interior (borde superior luminoso)
  cardElevated: (glowColor = null) => ({
    background: 'linear-gradient(165deg, rgba(255,255,255,0.07) 0%, rgba(255,255,255,0.02) 100%)',
    border: '1px solid rgba(255,255,255,0.09)',
    borderRadius: 16,
    boxShadow: glowColor
      ? `0 12px 32px -8px rgba(0,0,0,0.45), 0 0 32px -12px ${glowColor}55, inset 0 1px 0 rgba(255,255,255,0.06)`
      : '0 12px 32px -8px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.06)',
  }),
  // Botón primario premium — gradiente + glow del color de acento + leve elevación al hover (vía clase)
  btnPrimary: (color) => ({
    background: `linear-gradient(135deg, ${color}, ${color}CC)`,
    border: 'none',
    borderRadius: 12,
    color: '#fff',
    fontWeight: 700,
    boxShadow: `0 6px 20px -4px ${color}77, inset 0 1px 0 rgba(255,255,255,0.25)`,
    transition: 'transform 0.15s ease, box-shadow 0.15s ease',
  }),
  btnGhost: () => ({
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.10)',
    borderRadius: 12,
    color: 'rgba(255,255,255,0.75)',
    fontWeight: 600,
  }),
  // Fondo de página con profundidad — gradiente radial sutil + textura de ruido implícita por capas
  pageBackground: {
    background: `
      radial-gradient(circle at 15% 0%, rgba(167,139,250,0.10) 0%, transparent 45%),
      radial-gradient(circle at 85% 15%, rgba(56,189,248,0.08) 0%, transparent 45%),
      radial-gradient(circle at 50% 100%, rgba(52,211,153,0.06) 0%, transparent 50%),
      #0A0F1E
    `,
    minHeight: '100vh',
  },
  // Glow de texto para títulos destacados (números grandes tipo CTL/TSS)
  textGlow: (color) => ({
    color,
    textShadow: `0 0 24px ${color}66, 0 0 4px ${color}33`,
  }),
  // Separador con gradiente (en vez de línea sólida plana)
  dividerGradient: {
    height: 1,
    background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.12), transparent)',
    border: 'none',
  },
}

const ZONA_COLORS = {
  Z1:NOAH_C.z1, Z2:NOAH_C.z2, Z3:NOAH_C.z3, Z4:NOAH_C.z4, Z5:NOAH_C.z5, Z6:NOAH_C.z6, 'Z1-Z2':NOAH_C.z2,
  BZ1:NOAH_C.bz1, BZ2:NOAH_C.bz2, BZ3:NOAH_C.bz3, BZ4:NOAH_C.bz4, BZ5:NOAH_C.bz5, BZ6:NOAH_C.bz6, BZ7:NOAH_C.bz7,
}
// Etiqueta del eje Y para run/swim, donde el valor numérico representa el
// nivel de zona (1=Z1 ... 6=Z6), no watts directos.
const ZONA_COLORS_LABEL = {0:'', 1:'Z1', 2:'Z2', 3:'Z3', 4:'Z4', 5:'Z5', 6:'Z6'}

// Iconos de deporte — wrappers de Lucide con la misma interfaz {size,color}
// que usaban los SVG caseros, para no romper los call-sites existentes.
const IconRun  = ({ size=18, color='currentColor' }) => <Footprints size={size} color={color} strokeWidth={2} />
const IconBike = ({ size=18, color='currentColor' }) => <BikeIcon   size={size} color={color} strokeWidth={2} />
const IconSwim = ({ size=18, color='currentColor' }) => <Waves      size={size} color={color} strokeWidth={2.2} />

const SPORT = {
  running:  { color: NOAH_C.run,  light: NOAH_C.runL,  Icon: IconRun,  label: 'Running',  short: 'RUN'  },
  cycling:  { color: NOAH_C.bike, light: NOAH_C.bikeL, Icon: IconBike, label: 'Ciclismo', short: 'BIKE' },
  swimming: { color: NOAH_C.swim, light: NOAH_C.swimL, Icon: IconSwim, label: 'Natación', short: 'SWIM' },
}

const ESTADO = {
  done:    { color: NOAH_C.success, light: NOAH_C.successL, label: 'Completada',   icon: CheckCircle2 },
  miss:    { color: NOAH_C.danger,  light: NOAH_C.dangerL,   label: 'No realizada', icon: XCircle },
  partial: { color: NOAH_C.warning, light: NOAH_C.warningL,  label: 'Modificada',   icon: AlertTriangle },
  planned: { color: NOAH_C.planned, light: NOAH_C.plannedL,  label: 'Planificada',  icon: Minus },
  rest:    { color: NOAH_C.ink4,    light: '#F3F4F6',   label: 'Descanso',     icon: Minus },
}

function hoyKey() { return new Date().toISOString().slice(0, 10) }
function fmtDist(km) {
  // Garmin CSV guarda en metros cuando distance_km tiene valores >500
  if (!km) return '--'
  const real = km > 500 ? km / 1000 : km
  return real >= 1 ? `${real.toFixed(2)} km` : `${Math.round(real*1000)} m`
}
function fmtPaceStr(pace) {
  if (!pace) return '--'
  const m = Math.floor(pace), s = Math.round((pace-m)*60)
  return `${m}:${String(s).padStart(2,'0')} /km`
}
function getDiaKey(f) { return f ? f.slice(0, 10) : null }
function fmtPace(p) {
  if (!p) return '--'
  const m = Math.floor(p), s = Math.round((p - m) * 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
function fmtDur(d) {
  if (!d) return '--'
  return d < 1 ? `${Math.round(d * 60)}"` : `${Math.round(d)}'`
}
function getEstado(s) {
  if (!s) return 'rest'
  if (s.completada === true || s.estado === 'done') return 'done'
  if (s.estado === 'partial' || s.completada === 'partial') return 'partial'
  const fk = getDiaKey(s.fecha)
  if (fk && fk < hoyKey() && !s.completada) return 'miss'
  return 'planned'
}

// ── Icono compacto de deporte — reemplaza el patrón emoji running/cycling/swim ──
function SportIcon({ sport, size = 13, color }) {
  const s = SPORT[sport] || SPORT.running
  const Icon = s.Icon
  return <Icon size={size} color={color || s.color} />
}

// ── Sport Tag — ícono SVG + texto "RUN / BIKE / SWIM" ─────────────────────────
function SportTag({ sport, size = 'sm' }) {
  const s = SPORT[sport] || SPORT.running
  const { Icon } = s
  const isSm = size === 'sm'
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: isSm ? '3px 9px' : '5px 12px',
      borderRadius: 6, fontSize: isSm ? 11 : 12, fontWeight: 700,
      color: s.color, background: s.light,
      border: `1px solid ${s.color}33`,
      whiteSpace: 'nowrap',
    }}>
      <Icon size={isSm ? 13 : 15} color={s.color} />
      {s.short}
    </span>
  )
}

function EstadoTag({ estado }) {
  const e = ESTADO[estado] || ESTADO.planned
  const Icon = e.icon
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      padding: '3px 9px', borderRadius: 6, fontSize: 11, fontWeight: 600,
      color: e.color, background: e.light, border: `1px solid ${e.color}33`,
    }}>
      <Icon size={12} color={e.color} /> {e.label}
    </span>
  )
}

function MetricPill({ label, value, unit, color }) {
  return (
    <div style={{
      position: 'relative',
      background: `linear-gradient(150deg, rgba(255,255,255,0.085) 0%, rgba(255,255,255,0.025) 65%)`,
      backdropFilter: 'blur(16px) saturate(150%)', WebkitBackdropFilter: 'blur(16px) saturate(150%)',
      border: `1px solid rgba(255,255,255,0.10)`,
      borderRadius: 13, padding: '12px 15px', minWidth: 75, flex: 1,
      boxShadow: `0 10px 28px -6px rgba(0,0,0,0.5), 0 0 22px -6px ${color}30, inset 0 1px 0 rgba(255,255,255,0.10), inset 0 -1px 0 rgba(0,0,0,0.15)`,
      overflow: 'hidden',
    }}>
      {/* Línea de acento superior con glow, en vez de borde sólido plano */}
      <div style={{ position:'absolute', top:0, left:'8%', right:'8%', height:2.5,
        background: `linear-gradient(90deg, transparent, ${color}, transparent)`,
        boxShadow: `0 0 8px ${color}` }} />
      <div style={{ fontSize: 9, fontWeight: 700, color: 'rgba(255,255,255,0.42)',
        letterSpacing: 0.8, textTransform: 'uppercase', marginBottom: 5 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 800, color: color,
        lineHeight: 1, textShadow: `0 0 16px ${color}70, 0 0 4px ${color}40` }}>{value ?? '--'}</div>
      {unit && <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 3 }}>{unit}</div>}
    </div>
  )
}

function ScoreBadge({ score, color, label }) {
  const col = color === 'verde' ? NOAH_C.done : color === 'rojo' ? NOAH_C.miss : color === 'naranja' ? NOAH_C.partial : NOAH_C.tsbNeu
  const pct = score != null ? Math.round(score * 100) : null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5 }}>
      <div style={{
        width: 72, height: 72, borderRadius: '50%', position: 'relative',
        background: `conic-gradient(${col} ${(pct||0)*3.6}deg, #E5E7EB 0deg)`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        boxShadow: `0 0 0 3px white, 0 3px 10px ${col}28`,
      }}>
        <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'white', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: 17, fontWeight: 800, color: col, lineHeight: 1 }}>{pct ?? '--'}</span>
          <span style={{ fontSize: 8, color: NOAH_C.ink4, fontWeight: 600, letterSpacing: 0.5 }}>SCORE</span>
        </div>
      </div>
      <span style={{ fontSize: 10, fontWeight: 700, color: col, textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</span>
    </div>
  )
}

function ProgressBar({ label, value, max, color, unit }) {
  const pct = Math.min(100, Math.round(((value||0)/max)*100))
  return (
    <div style={{ marginBottom: 13 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, color: NOAH_C.ink3, fontWeight: 500 }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color }}>{value?.toFixed?.(1) ?? value}{unit}</span>
      </div>
      <div style={{ height: 5, background: '#E5E7EB', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: `linear-gradient(90deg, ${color}88, ${color})`, borderRadius: 99 }} />
      </div>
    </div>
  )
}

// Cache simple de zonas por atleta+deporte — evita refetchear en cada render
const _zonasCacheAtleta = {}
function useZonasAtletaDash(atletaId, sport) {
  const [zonas, setZonas] = useState(null)
  useEffect(() => {
    if (!atletaId || !sport) return
    const key = `${atletaId}-${sport}`
    if (_zonasCacheAtleta[key]) { setZonas(_zonasCacheAtleta[key]); return }
    authFetch(`${API}/atletas/${atletaId}/zonas/${sport}`)
      .then(r => r.json())
      .then(r => { _zonasCacheAtleta[key] = r.data; setZonas(r.data) })
      .catch(() => {})
  }, [atletaId, sport])
  return zonas
}

// Texto resumen del plan, tal como lo armó/editó el coach:
// "30' Z1 + 4×5' Z3 (pausa 3' activa) + 10' Z1"
function resumenTextoPlan(bloques) {
  return bloques.map(b => {
    const dur = fmtDur(b.duracion_min)
    const base = b.repeticiones > 1 ? `${b.repeticiones}×${dur} ${b.zona}` : `${dur} ${b.zona}`
    if (b.pausa_min > 0 && b.repeticiones > 1) {
      const tipoPausa = b.pausa_activa === false ? 'pasiva' : 'activa'
      return `${base} (pausa ${fmtDur(b.pausa_min)} ${tipoPausa})`
    }
    return base
  }).join(' + ')
}

function WorkoutChart({ sesion, atletaId, mostrarGrafico = true }) {
  const sport = sesion?.sport || 'running'
  const zonas = useZonasAtletaDash(atletaId, sport)
  if (!sesion?.bloques?.length) return null
  const sc = SPORT[sport] || SPORT.running

  // Construir el perfil de la sesión en el tiempo: eje X = minuto acumulado,
  // eje Y = watts reales (bike) o nivel de zona (run/swim, ya que el pace
  // varía por bloque pero no tenemos pace punto-a-punto). Cada bloque genera
  // 2 puntos (inicio y fin a la misma altura) para que el área quede "escalonada"
  // y se vea como un perfil de potencia real, no una curva suavizada falsa.
  const ORDEN_ZONA = {Z1:1,Z2:2,Z3:3,Z4:4,Z5:5,Z6:6,BZ1:1,BZ2:2,BZ3:3,BZ4:4,BZ5:5,BZ6:6,BZ7:7}
  const esBike = sport === 'cycling'

  let tAcum = 0
  const perfil = []
  perfil.push({ t:0, valor:0, zona:sesion.bloques[0]?.zona, esPausa:false })

  sesion.bloques.forEach(b => {
    const reps = b.repeticiones || 1
    const durBloqueMin = b.duracion_min < 1 ? b.duracion_min : b.duracion_min
    const valorTrabajo = esBike ? (((b.watts_min||0)+(b.watts_max||0))/2 || ORDEN_ZONA[b.zona]*40)
                                  : ORDEN_ZONA[b.zona] || 1
    const valorPausa = esBike ? 0 : 0.5

    for (let r = 0; r < reps; r++) {
      perfil.push({ t:tAcum, valor:valorTrabajo, zona:b.zona, esPausa:false,
        watts_min:b.watts_min, watts_max:b.watts_max, pace:b.pace_ref })
      tAcum += durBloqueMin
      perfil.push({ t:tAcum, valor:valorTrabajo, zona:b.zona, esPausa:false,
        watts_min:b.watts_min, watts_max:b.watts_max, pace:b.pace_ref })

      if (b.pausa_min > 0 && r < reps - 1) {
        perfil.push({ t:tAcum, valor:valorPausa, zona:'pausa', esPausa:true, activa:b.pausa_activa!==false })
        tAcum += b.pausa_min
        perfil.push({ t:tAcum, valor:valorPausa, zona:'pausa', esPausa:true, activa:b.pausa_activa!==false })
      }
    }
  })

  // Referencia de zona del atleta — SIN HR, según deporte: watts (bike), pace (run/swim)
  // La zona de referencia es la de MAYOR INTENSIDAD (el trabajo real), no la
  // de mayor duración — el calentamiento Z1 suele durar más que el bloque de
  // trabajo, pero la referencia útil para el atleta es la zona que entrena.
  const zonaPrincipal = sesion.bloques.reduce((max,b) =>
    (ORDEN_ZONA[b.zona]||0) > (ORDEN_ZONA[max]||0) ? b.zona : max, sesion.bloques[0]?.zona)
  const zonaKey = zonaPrincipal?.replace('BZ','Z')
  const zInfo = zonas && typeof zonas==='object' && !Array.isArray(zonas) ? zonas.zonas?.[zonaKey] : null
  const tsbAtleta = zonas?.tsb
  const sugerenciaPisoTecho = tsbAtleta != null
    ? (tsbAtleta >= 0 ? 'Conviene trabajar al techo de la zona — buena frescura.'
       : tsbAtleta >= -15 ? 'Trabajar en el centro de la zona — fatiga moderada.'
       : 'Conviene trabajar al piso de la zona — fatiga acumulada.')
    : null

  const refZonaStr = zInfo
    ? (esBike ? `${zInfo.w_min ?? '?'}–${zInfo.w_max ?? '?'}W` : null)
    : null

  const yMax = esBike ? Math.max(...perfil.map(p=>p.valor), 50) * 1.15 : 7

  return (
    <div>
      {/* Resumen del plan — una línea legible */}
      <div style={{ fontSize:13, fontWeight:600, color:NOAH_C.ink, marginBottom:4, lineHeight:1.5 }}>
        {resumenTextoPlan(sesion.bloques)}
      </div>
      <div style={{ fontSize:11, color:NOAH_C.ink3, marginBottom:mostrarGrafico?14:10 }}>
        ⏱ {Math.round(sesion.duracion)} min total · TSS {sesion.tss}
      </div>

      {mostrarGrafico && (
        <div style={{
          background:'linear-gradient(160deg, #1A1F2E 0%, #11151F 100%)',
          borderRadius:14, padding:'16px 14px 8px', marginBottom:12,
          boxShadow:'0 8px 24px -8px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)',
        }}>
          <ResponsiveContainer width="100%" height={170}>
            <AreaChart data={perfil} margin={{top:4,right:4,left:-18,bottom:0}}>
              <defs>
                <linearGradient id={`grad-area-${sport}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={sc.color} stopOpacity={0.85}/>
                  <stop offset="100%" stopColor={sc.color} stopOpacity={0.08}/>
                </linearGradient>
                <filter id="areaGlow" x="-20%" y="-20%" width="140%" height="140%">
                  <feDropShadow dx="0" dy="0" stdDeviation="4" floodColor={sc.color} floodOpacity="0.5"/>
                </filter>
              </defs>
              <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.06)" vertical={false} />
              <XAxis dataKey="t" type="number" domain={[0, 'dataMax']}
                tick={{ fill:'rgba(255,255,255,0.45)', fontSize:10 }} axisLine={false} tickLine={false}
                tickFormatter={v=>`${Math.round(v)}'`} />
              <YAxis domain={[0, yMax]} tick={{ fill:'rgba(255,255,255,0.35)', fontSize:10 }}
                axisLine={false} tickLine={false}
                tickFormatter={v => esBike ? `${Math.round(v)}W` : (ZONA_COLORS_LABEL[Math.round(v)]||'')} />
              <Tooltip
                contentStyle={{ background:'#1A1F2E', border:'1px solid rgba(255,255,255,0.1)', borderRadius:10,
                  fontSize:12, boxShadow:'0 8px 24px rgba(0,0,0,0.4)', color:'#fff' }}
                itemStyle={{ color:'#fff' }}
                labelFormatter={v => `min ${Math.round(v)}`}
                formatter={(v,n,props) => {
                  const d = props.payload
                  if (d.esPausa) return [d.activa?'Pausa activa':'Pausa pasiva', '']
                  const ref = esBike && d.watts_min ? `${d.watts_min}–${d.watts_max}W`
                    : sport==='swimming'&&d.pace ? `${fmtPace(d.pace)}/100m`
                    : d.pace ? `${fmtPace(d.pace)}/km` : ''
                  return [ref || d.zona, d.zona]
                }}
              />
              <Area type="stepAfter" dataKey="valor" stroke={sc.color} strokeWidth={2.5}
                fill={`url(#grad-area-${sport})`} filter="url(#areaGlow)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Referencia de zona del atleta — SOLO watts/pace, nunca HR */}
      {(refZonaStr || sugerenciaPisoTecho) && (
        <div style={{ fontSize:11, color:'rgba(255,255,255,0.55)', marginBottom:10, padding:'8px 12px',
          background:'rgba(255,255,255,0.04)', borderRadius:8, border:`1px solid ${NOAH_C.border}` }}>
          {refZonaStr && <span>Referencia {zonaPrincipal}: <b style={{color:sc.color}}>{refZonaStr}</b></span>}
          {refZonaStr && sugerenciaPisoTecho && <span> · </span>}
          {sugerenciaPisoTecho && <span style={{fontStyle:'italic'}}>{sugerenciaPisoTecho}</span>}
        </div>
      )}

      {/* Nutrición */}
      {sesion.descripcion && sesion.descripcion.includes('Nutrición:') && (
        <div style={{ padding:'10px 14px', background:NOAH_C.warningL,
          border:`1px solid ${NOAH_C.warning}40`, borderRadius:8, fontSize:12, color:NOAH_C.warning, lineHeight:1.5,
          display:'flex', alignItems:'flex-start', gap:6 }}>
          <Banana size={14} style={{flexShrink:0, marginTop:1}}/>
          <span><b>Nutrición sugerida:</b> {sesion.descripcion.split('Nutrición:')[1].trim()}</span>
        </div>
      )}
    </div>
  )
}

function SesionCard({ sesion, expandida, onToggle, esHoy, atletaId }) {
  const estado = getEstado(sesion)
  const e = ESTADO[estado]
  const s = SPORT[sesion?.sport||'running']
  const borderLeft = estado==='done'?NOAH_C.done:estado==='miss'?NOAH_C.miss:estado==='partial'?NOAH_C.partial:esHoy?s.color:NOAH_C.border2
  return (
    <div style={{ background:NOAH_C.cardBg, borderRadius:10, border:`1px solid ${esHoy?s.color+'28':NOAH_C.border}`, borderLeft:`4px solid ${borderLeft}`, boxShadow:esHoy?`0 2px 8px ${s.color}10`:'0 1px 2px rgba(0,0,0,0.04)', overflow:'hidden' }}>
      <div onClick={onToggle} style={{ padding:'12px 16px', cursor:'pointer', display:'flex', alignItems:'center', gap:12 }}>
        {/* Ícono deporte con label */}
        <div style={{ width:44, height:44, borderRadius:8, flexShrink:0, background:s.light, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:2 }}>
          <s.Icon size={16} color={s.color} />
          <span style={{ fontSize:8, fontWeight:800, color:s.color, letterSpacing:0.8 }}>{s.short}</span>
        </div>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:14, fontWeight:600, color:NOAH_C.ink, marginBottom:3, lineHeight:1.2 }}>{sesion.nombre}</div>
          <div style={{ fontSize:11, color:NOAH_C.ink3, display:'flex', gap:10, flexWrap:'wrap' }}>
            {sesion.duracion && <span>⏱ {Math.round(sesion.duracion)} min</span>}
            {sesion.tss && <span>TSS {sesion.tss}</span>}
            {sesion.sport==='cycling' && sesion.watts_min ? <span>{sesion.watts_min}–{sesion.watts_max}W</span>
              : sesion.sport==='swimming' && sesion.pace_ref ? <span>{fmtPace(sesion.pace_ref)}/100m</span>
              : sesion.pace_ref ? <span>{fmtPace(sesion.pace_ref)}/km</span> : null}
          </div>
        </div>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:5, flexShrink:0 }}>
          <SportTag sport={sesion.sport||'running'} />
          <EstadoTag estado={estado} />
        </div>
        <span style={{ fontSize:12, color:NOAH_C.ink4, transform:expandida?'rotate(180deg)':'none', transition:'transform 0.2s', marginLeft:4 }}>▾</span>
      </div>
      {expandida && (
        <div style={{ borderTop:`1px solid ${NOAH_C.border}`, padding:'14px 16px', background:NOAH_C.cardBg2 }}>
          <WorkoutChart sesion={sesion} atletaId={atletaId} mostrarGrafico={false} />
          {/* Actividad realizada si la sesión ya pasó */}
          {getDiaKey(sesion.fecha) <= hoyKey() && atletaId && (
            <div style={{marginTop:14}}>
              <div style={{height:1,background:NOAH_C.border,marginBottom:14}}/>
              <div style={{fontSize:10,fontWeight:600,color:NOAH_C.ink4,letterSpacing:1,
                textTransform:'uppercase',marginBottom:10}}>Lo que hiciste</div>
              <ActividadRealizada sesionPresc={sesion} atletaId={atletaId} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function SemanaCompleta({ presc, atletaId, sesionExpandida, setSesionExpandida }) {
  const [actsSemana, setActsSemana] = useState({})

  // Calcular inicio de la semana actual (lunes)
  const hoy = hoyKey()
  const hoyDate = new Date(hoy+'T12:00:00')
  const diaSemana = hoyDate.getDay() || 7  // 1=lun, 7=dom
  const lunesActual = new Date(hoyDate)
  lunesActual.setDate(hoyDate.getDate() - diaSemana + 1)
  const domingoActual = new Date(lunesActual)
  domingoActual.setDate(lunesActual.getDate() + 6)
  const desdeStr = lunesActual.toISOString().slice(0,10)
  const hastaStr = domingoActual.toISOString().slice(0,10)

  // Cargar actividades reales de la semana actual
  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desdeStr}&hasta=${hastaStr}`)
      .then(r=>r.json()).then(r=>setActsSemana(r.data?.actividades||{})).catch(()=>{})
  }, [atletaId, desdeStr])

  const sesiones = presc?.prescripcion?.sesiones || []
  const porDia = {}
  sesiones.forEach(s => { const fk = getDiaKey(s.fecha)||'sin-fecha'; if(!porDia[fk])porDia[fk]=[]; porDia[fk].push(s) })

  // Agregar días de la semana actual que no están en la prescripción pero tienen actividad
  Object.keys(actsSemana).forEach(f => { if(!porDia[f]) porDia[f] = [] })

  // Si no hay nada esta semana, mostrar la prescripción activa
  const dias = Object.keys(porDia).length > 0
    ? Object.keys(porDia).sort()
    : []

  if (!dias.length) return (
    <div style={{ textAlign:'center', padding:48, color:NOAH_C.ink3, fontSize:14 }}>Sin planificación para esta semana</div>
  )

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
      {dias.map(fk => {
        const sesDia = porDia[fk]
        const esHoy = fk===hoy
        const esPasado = fk<hoy
        const sc0 = SPORT[sesDia[0]?.sport||'running']
        const fkDate = fk!=='sin-fecha' ? new Date(fk+'T12:00:00') : null
        const diaNombre = fkDate ? fkDate.toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'short'}) : 'Sin fecha'
        return (
          <div key={fk} style={{ borderRadius:12, border:`1px solid ${esHoy?sc0.color+'40':NOAH_C.border}`, boxShadow:esHoy?`0 4px 16px ${sc0.color}12`:'0 1px 3px rgba(0,0,0,0.04)', overflow:'hidden' }}>
            <div style={{ padding:'9px 16px', background:esHoy?`linear-gradient(90deg,${sc0.color}15,${sc0.color}06)`:NOAH_C.cardBg2, borderBottom:`1px solid ${esHoy?sc0.color+'20':NOAH_C.border}`, display:'flex', alignItems:'center', gap:10 }}>
              <span style={{ fontSize:11, fontWeight:700, letterSpacing:0.8, textTransform:'uppercase', color:esHoy?sc0.color:esPasado?NOAH_C.ink4:NOAH_C.ink3 }}>{diaNombre}</span>
              {esHoy && <span style={{ fontSize:9, fontWeight:700, color:sc0.color, background:sc0.light, borderRadius:99, padding:'2px 7px', border:`1px solid ${sc0.color}33` }}>HOY</span>}
              <div style={{ flex:1 }} />
              <span style={{ fontSize:11, color:NOAH_C.ink4 }}>TSS {sesDia.reduce((a,s)=>a+(s.tss||0),0)}</span>
            </div>
            <div style={{ padding:'10px 12px', background:NOAH_C.cardBg, display:'flex', flexDirection:'column', gap:8 }}>
              {sesDia.map((s,i) => (
                <SesionCard key={i} sesion={s} esHoy={esHoy}
                  atletaId={atletaId}
                  expandida={sesionExpandida===`${fk}-${i}`}
                  onToggle={() => setSesionExpandida(sesionExpandida===`${fk}-${i}`?null:`${fk}-${i}`)}
                />
              ))}
              {/* Actividades reales del día sin prescripción */}
              {sesDia.length===0 && (actsSemana[fk]||[]).map((act,i)=>(
                <div key={i} style={{background:NOAH_C.cardBg,borderRadius:10,
                  border:`1px solid ${NOAH_C.border}`,borderLeft:`4px solid ${NOAH_C.success}`,
                  padding:'12px 16px'}}>
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                    <SportTag sport={act.sport||'running'}/>
                    <div>
                      <div style={{fontSize:13,fontWeight:600,color:NOAH_C.ink}}>
                        {SPORT[act.sport]?.label||act.sport} — {act.distance_km?.toFixed(1)}km
                      </div>
                      <div style={{fontSize:11,color:NOAH_C.ink3}}>
                        {Math.round(act.duration_min)}min · TSS {act.tss?.toFixed(0)} · HR {act.hr_avg?Math.round(act.hr_avg):'--'}bpm
                      </div>
                    </div>
                    <div style={{marginLeft:'auto',fontSize:10,padding:'3px 8px',borderRadius:99,
                      background:NOAH_C.successL,color:NOAH_C.success,fontWeight:700,display:'flex',alignItems:'center',gap:3}}>
                      <CheckCircle2 size={11}/> Realizada
                    </div>
                  </div>
                  <ActividadRealizada sesionPresc={{fecha:fk,sport:act.sport}} atletaId={atletaId}/>
                </div>
              ))}
            </div>
          </div>
        )
      })}
      {presc.prescripcion && (
        <div style={{ background:`linear-gradient(135deg,${NOAH_C.headerBg},#1F2937)`, borderRadius:12, padding:'14px 20px', display:'flex', gap:28, alignItems:'center', flexWrap:'wrap', boxShadow:'0 4px 12px rgba(0,0,0,0.12)' }}>
          {[['TSS Semana',presc.prescripcion.tss_total,NOAH_C.run],['Fase',presc.prescripcion.fase,'#fff'],['Generado',presc.prescripcion.fecha_generada,'#6B7280']].map(([l,v,col]) => (
            <div key={l}><div style={{ fontSize:9, color:'#6B7280', fontWeight:600, textTransform:'uppercase', letterSpacing:1.5, marginBottom:4 }}>{l}</div><div style={{ fontSize:20, fontWeight:700, color:col }}>{v}</div></div>
          ))}
        </div>
      )}
    </div>
  )
}



// ── Curva de Periodización (vista atleta — simplificada) ──────────────────────
function CurvaPeriodizacionAtleta({ atletaId }) {
  const [data, setData] = useState(null)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/periodizacion`)
      .then(r => r.json())
      .then(r => setData(r.data))
      .catch(() => {})
  }, [atletaId])

  if (!data) return <div style={{ color:NOAH_C.ink3, fontSize:12 }}>Cargando...</div>

  const FASE_COLOR = { A:'#6366f1', T:'#f59e0b', R:'#ef4444', Taper:NOAH_C.success }
  const FASE_LABEL = { A:'Acumulación', T:'Transformación', R:'Realización', Taper:'Taper' }
  const FASE_DESC  = {
    A:     'Base aeróbica. Construís el motor.',
    T:     'Velocidad específica. El motor trabaja fuerte.',
    R:     'Pico de rendimiento. Llegás al máximo.',
    Taper: 'Descansás para llegar fresco a la carrera.',
  }

  const W=800, H=200, PL=40, PR=16, PT=16, PB=32
  const GW=W-PL-PR, GH=H-PT-PB
  const todos = [
    ...data.historico.map(p=>({...p,real:p.ctl,proy:null})),
    ...data.proyectado.map(p=>({...p,real:null,proy:p.ctl})),
  ]
  const max_ctl = Math.max(...todos.map(p=>p.real||p.proy||0), data.ctl_objetivo||80)*1.1
  const xScale = f => PL+((new Date(f)-new Date(data.historico[0].fecha))/(new Date(data.carrera.fecha)-new Date(data.historico[0].fecha)))*GW
  const yScale = c => PT+GH-((c)/(max_ctl))*GH
  const pathR = todos.filter(p=>p.real!==null).map((p,i)=>`${i===0?'M':'L'}${xScale(p.fecha)},${yScale(p.real)}`).join(' ')
  const pathP = todos.filter(p=>p.proy!==null).map((p,i)=>`${i===0?'M':'L'}${xScale(p.fecha)},${yScale(p.proy)}`).join(' ')

  return (
    <div>
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ borderRadius:8 }}>
        {data.fases.map((f,i) => (
          <rect key={i} x={xScale(f.desde)} y={PT}
            width={Math.max(1,xScale(f.hasta)-xScale(f.desde))} height={GH}
            fill={FASE_COLOR[f.fase]} opacity={0.1} />
        ))}
        {data.fases.map((f,i) => (
          <text key={i} x={(xScale(f.desde)+xScale(f.hasta))/2} y={PT+14}
            textAnchor="middle"
            style={{ fontSize:11, fontWeight:'bold', fill:FASE_COLOR[f.fase] }}>
            {f.fase}
          </text>
        ))}
        {pathR&&<path d={pathR} fill="none" stroke="#94a3b8" strokeWidth={2}/>}
        {pathP&&<path d={pathP} fill="none" stroke={FASE_COLOR[data.fases[0]?.fase]||'#6366f1'}
          strokeWidth={2.5} strokeDasharray="6,3"/>}
        <line x1={xScale(new Date().toISOString().slice(0,10))}
          x2={xScale(new Date().toISOString().slice(0,10))}
          y1={PT} y2={PT+GH} stroke="#ffffff" strokeWidth={1} opacity={0.3}/>
        <line x1={xScale(data.carrera.fecha)} x2={xScale(data.carrera.fecha)}
          y1={PT} y2={PT+GH} stroke={NOAH_C.success} strokeWidth={2}/>
        <g transform={`translate(${xScale(data.carrera.fecha)-15}, ${PT-2})`}>
          <Flag size={12} color={NOAH_C.success} strokeWidth={2.2}/>
        </g>
      </svg>
      <div style={{ display:'flex', gap:8, marginTop:12, flexWrap:'wrap' }}>
        {data.fases.map((f,i) => (
          <div key={i} style={{ flex:1, minWidth:120, padding:'10px 12px',
            borderRadius:8, background:`${FASE_COLOR[f.fase]}11`,
            border:`1px solid ${FASE_COLOR[f.fase]}33` }}>
            <div style={{ fontSize:12, fontWeight:700, color:FASE_COLOR[f.fase] }}>
              {f.fase} — {FASE_LABEL[f.fase]}
            </div>
            <div style={{ fontSize:11, color:NOAH_C.ink3, marginTop:3 }}>{FASE_DESC[f.fase]}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── Comparación prescripto vs realizado ──────────────────────────────────────
function ComparacionMetrica({ label, prescripto, realizado, unidad, invert=false }) {
  if (!prescripto || !realizado) return null
  const diff = realizado - prescripto
  const pct  = Math.round((diff / prescripto) * 100)
  const ok   = Math.abs(pct) <= 10  // dentro del 10% = cumplió
  const mas  = invert ? diff < 0 : diff > 0
  const color = ok ? NOAH_C.success : mas ? NOAH_C.warning : NOAH_C.danger
  const Icon  = ok ? Check : mas ? TrendingUp : TrendingDown

  return (
    <div style={{ flex:1, minWidth:80, background:NOAH_C.cardBg2, borderRadius:10,
      padding:'10px 12px', border:`1px solid ${ok?NOAH_C.success+'33':NOAH_C.border}`,
      borderTop:`3px solid ${color}` }}>
      <div style={{ fontSize:10, color:NOAH_C.ink4, fontWeight:600, textTransform:'uppercase',
        letterSpacing:0.8, marginBottom:6 }}>{label}</div>
      <div style={{ display:'flex', alignItems:'baseline', gap:6 }}>
        <span style={{ fontSize:22, fontWeight:800, color }}>{realizado?.toFixed?.(0)??realizado}</span>
        <span style={{ fontSize:11, color:NOAH_C.ink4 }}>{unidad}</span>
      </div>
      <div style={{ fontSize:11, color:NOAH_C.ink3, marginTop:4, display:'flex', gap:4, alignItems:'center' }}>
        <span>Prescripto: {prescripto?.toFixed?.(0)??prescripto} {unidad}</span>
        <span style={{ color, fontWeight:700, display:'flex', alignItems:'center', gap:2 }}><Icon size={12}/> {Math.abs(pct)}%</span>
      </div>
    </div>
  )
}

function SesionRealizada({ sesionReal, sesionPresc, sport }) {
  if (!sesionReal) return null
  const s = SPORT[sport||'running']

  const tssReal  = sesionReal.tss_total
  const tssPresc = sesionPresc?.tss
  const durReal  = sesionReal.duration_min
  const durPresc = sesionPresc?.duracion
  const hrReal   = sesionReal.hr_avg
  const hrPresc  = sesionPresc?.hr_max ? (sesionPresc.hr_min + sesionPresc.hr_max) / 2 : null

  // Evaluación global
  let eval_global, eval_color, eval_icon, eval_msg
  if (!tssReal) {
    eval_global = 'sin_datos'; eval_color = NOAH_C.ink4
    eval_icon = ClipboardList; eval_msg = 'Sin datos suficientes'
  } else if (!tssPresc) {
    eval_global = 'ok'; eval_color = NOAH_C.success
    eval_icon = Check; eval_msg = 'Sesión registrada'
  } else {
    const pct = (tssReal - tssPresc) / tssPresc * 100
    if (Math.abs(pct) <= 10) {
      eval_global = 'ok'; eval_color = NOAH_C.success
      eval_icon = Check; eval_msg = 'Cumpliste la prescripción'
    } else if (pct > 10) {
      eval_global = 'mas'; eval_color = NOAH_C.warning
      eval_icon = TrendingUp; eval_msg = `Hiciste ${Math.round(pct)}% más de lo prescripto`
    } else {
      eval_global = 'menos'; eval_color = NOAH_C.danger
      eval_icon = TrendingDown; eval_msg = `Hiciste ${Math.round(Math.abs(pct))}% menos de lo prescripto`
    }
  }

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
      {/* Header resultado */}
      <div style={{ background:`linear-gradient(135deg, ${eval_color}18, ${eval_color}08)`,
        borderRadius:12, padding:'16px 20px',
        border:`1px solid ${eval_color}33`, borderLeft:`4px solid ${eval_color}`,
        display:'flex', alignItems:'center', gap:16 }}>
        <div style={{ width:52, height:52, borderRadius:'50%',
          background:eval_color, display:'flex', alignItems:'center',
          justifyContent:'center', color:'#fff',
          flexShrink:0 }}>
          <eval_icon size={24} strokeWidth={2.2}/>
        </div>
        <div>
          <div style={{ fontSize:16, fontWeight:700, color:NOAH_C.ink }}>{eval_msg}</div>
          <div style={{ fontSize:12, color:NOAH_C.ink3, marginTop:4 }}>
            {sesionReal.fecha} · {s.label}
          </div>
        </div>
      </div>

      {/* Métricas comparación */}
      <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
        <ComparacionMetrica label="TSS" prescripto={tssPresc} realizado={tssReal} unidad="" />
        <ComparacionMetrica label="Duración" prescripto={durPresc} realizado={durReal} unidad="min" />
        {hrReal && <ComparacionMetrica label="HR promedio" prescripto={hrPresc} realizado={hrReal} unidad="bpm" invert={true} />}
        {sesionReal.pace && sesionPresc?.bloques?.[1]?.pace_ref && (
          <ComparacionMetrica label="Pace" prescripto={sesionPresc.bloques[1].pace_ref * 60}
            realizado={sesionReal.pace * 60} unidad="min/km" invert={true} />
        )}
      </div>

      {/* Datos reales detallados */}
      <div style={{ background:NOAH_C.cardBg, borderRadius:12, padding:16,
        border:`1px solid ${NOAH_C.border}` }}>
        <div style={{ fontSize:10, fontWeight:600, color:NOAH_C.ink4, letterSpacing:1,
          textTransform:'uppercase', marginBottom:12 }}>Datos reales Garmin</div>
        <div style={{ display:'flex', gap:20, flexWrap:'wrap' }}>
          {[
            [Activity, 'Duración', durReal ? `${Math.round(durReal)} min` : '--'],
            [HeartPulse, 'HR prom', hrReal ? `${Math.round(hrReal)} bpm` : '--'],
            [Zap, 'TSS', tssReal ? tssReal.toFixed(1) : '--'],
            [Ruler, 'Distancia', sesionReal.distance_km ? `${sesionReal.distance_km.toFixed(1)} km` : '--'],
            [Footprints, 'Pace', sesionReal.pace ? `${Math.floor(sesionReal.pace)}:${String(Math.round((sesionReal.pace%1)*60)).padStart(2,'0')} /km` : '--'],
            [BikeIcon, 'NP', sesionReal.np_watts ? `${sesionReal.np_watts}W` : null],
          ].filter(([,,v]) => v).map(([Icon, label, val]) => (
            <div key={label}>
              <div style={{ fontSize:11, color:NOAH_C.ink4, display:'flex', alignItems:'center', gap:4 }}><Icon size={12}/> {label}</div>
              <div style={{ fontSize:16, fontWeight:700, color:NOAH_C.ink, marginTop:2 }}>{val}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}



// ── Vista de actividad realizada — estilo Garmin/TrainingPeaks ───────────────
function NutricionPost({ atletaId, fecha }) {
  const [nut, setNut] = useState(null)

  useEffect(() => {
    if (!atletaId || !fecha) return
    authFetch(`${API}/atletas/${atletaId}/nutricion_post?fecha=${fecha}`)
      .then(r=>r.json())
      .then(r=>setNut(r.data))
      .catch(()=>setNut(null))
  }, [atletaId, fecha])

  if (!nut || nut.sin_actividad) return null

  if (nut.sin_datos_atleta) return (
    <div style={{ marginTop:12, padding:'10px 14px', background:NOAH_C.warningL,
      border:`1px solid ${NOAH_C.warning}40`, borderRadius:8, fontSize:12, color:NOAH_C.warning,
      display:'flex', alignItems:'flex-start', gap:6 }}>
      <AlertTriangle size={13} style={{flexShrink:0, marginTop:1}}/> {nut.mensaje}
    </div>
  )

  if (!nut.recuperacion) return null

  const r = nut.recuperacion
  return (
    <div style={{ marginTop:12, padding:'12px 14px', background:NOAH_C.successL,
      border:`1px solid ${NOAH_C.success}40`, borderRadius:8, fontSize:12, color:NOAH_C.success, lineHeight:1.6 }}>
      <div style={{ fontWeight:700, marginBottom:6, display:'flex', alignItems:'center', gap:5 }}>
        <GlassWater size={14}/> Recuperación post-entreno
      </div>
      <div><b>Proteína:</b> {r.proteina_g_por_toma}g por toma — {(r.fuentes_proteina||[]).slice(0,3).join(', ')}</div>
      {r.cho_recuperacion_g_total_4h && (
        <div style={{marginTop:4}}><b>CHO recuperación:</b> {r.cho_recuperacion_g_total_4h}g en las próximas 4h — {(r.fuentes_cho||[]).slice(0,3).join(', ')}</div>
      )}
      <div style={{marginTop:4, opacity:0.85}}>{r.cho_mensaje}</div>
    </div>
  )
}


function ActividadRealizada({ sesionPresc, atletaId }) {
  const [actividades, setActividades] = useState([])
  const [cargando, setCargando]       = useState(false)

  const fecha = sesionPresc?.fecha?.slice(0,10)

  useEffect(() => {
    if (!atletaId || !fecha) return
    setCargando(true)
    authFetch(`${API}/atletas/${atletaId}/actividades_dia?fecha=${fecha}&exacto=true`)
      .then(r=>r.json())
      .then(r=>{ setActividades(r.data?.actividades||[]); setCargando(false) })
      .catch(()=>setCargando(false))
  }, [atletaId, fecha])

  // Filtrar por deporte de la sesión prescripta — si el día tiene varias
  // actividades (ej: nadó Y corrió el mismo día), cada SesionCard debe
  // mostrar SOLO la actividad real de SU propio deporte, no todas las del
  // día. Antes esto mezclaba: la tarjeta de Swim podía mostrar el gráfico
  // de Running si ambas ocurrieron el mismo día.
  const sportPresc = sesionPresc?.sport
  const actividadesFiltradas = sportPresc
    ? actividades.filter(a => a.sport === sportPresc)
    : actividades

  if (cargando) return (
    <div style={{padding:'16px 0',color:NOAH_C.ink3,fontSize:12,display:'flex',alignItems:'center',gap:6}}>
      <RotateCw size={13} className="noah-spin"/> Cargando actividades...
    </div>
  )
  if (!actividadesFiltradas.length) return (
    <div style={{padding:'16px 0',color:NOAH_C.ink3,fontSize:12,display:'flex',alignItems:'center',gap:8}}>
      <Satellite size={16}/>
      <span>Sin actividad Garmin para este día. Sincronizá para ver los datos.</span>
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      {actividadesFiltradas.map((act, idx) => (
        <ActividadCard key={act.sesion_id || act.id || `${fecha}-${idx}`} act={act} sesionPresc={sesionPresc} atletaId={atletaId}/>
      ))}
      <NutricionPost atletaId={atletaId} fecha={fecha} />
    </div>
  )
}





// ── Gráfico de actividad con curvas reales ───────────────────────────────────
// ── Gráfico de actividad con curvas reales — PREMIUM ESMERILADO ──────────────
// Eje Y izq: FC (bpm) — curva violeta bezier, Eje Y der: pace/watts/swolf
// Columnas de fondo coloreadas por zona, línea LTHR amber, hover tooltip
// ── GraficoActividad → GraficoActividadStreams ────────────────────────────────
const GraficoActividad = memo(function GraficoActividad({ act, laps, sport, lthr = 162, sesionId, atletaId }) {
  return (
    <GraficoActividadStreams
      act={act}
      laps={laps || []}
      sport={sport}
      lthr={lthr}
      sesionId={sesionId || act?.sesion_id}
      atletaId={atletaId}
      height={210}
    />
  )
}, (prev, next) => (
  // Solo re-renderiza si cambia sesionId, atletaId, lthr o sport — no por re-renders del padre
  prev.sesionId === next.sesionId &&
  prev.atletaId === next.atletaId &&
  prev.lthr     === next.lthr     &&
  prev.sport    === next.sport
))


const ActividadCard = memo(function ActividadCard({ act, sesionPresc, atletaId }) {
  // memo con comparador: solo re-renderiza si cambia la actividad concreta
  // sesionPresc se recrea en cada render del padre — no debe causar remount
  const [expandido, setExpandido] = useState(false)
  const laps  = act.laps || []
  const sport = (act.sport || 'running').toLowerCase()
  const s     = SPORT[sport] || SPORT.running
  const LTHR  = sesionPresc?.lthr || (sport==='cycling' ? 155 : 162)

  const distKm = act.distance_km > 500 ? act.distance_km/1000 : act.distance_km

  const tssR = act.tss_total
  const tssP = sesionPresc?.tss
  const pct  = tssP && tssR ? Math.round((tssR-tssP)/tssP*100) : null
  const cumplColor = !sesionPresc ? NOAH_C.danger
    : pct===null ? NOAH_C.ink3
    : Math.abs(pct)<=15 ? NOAH_C.success
    : Math.abs(pct)<=40 ? NOAH_C.warning
    : NOAH_C.danger
  const cumplLabel = !sesionPresc ? 'Sin prescripción'
    : pct===null ? 'Sin TSS'
    : Math.abs(pct)<=15 ? 'Cumplida'
    : pct>15 ? `+${pct}% sobre`
    : `${Math.abs(pct)}% bajo`

  return (
    <div style={{background:NOAH_C.cardBg,borderRadius:14,overflow:'hidden',
      border:`1px solid ${NOAH_C.border}`,borderTop:`4px solid ${s.color}`}}>

      {/* Header */}
      <div style={{padding:'14px 18px',display:'flex',alignItems:'center',gap:12,
        background:`linear-gradient(135deg,${s.color}12,${s.color}04)`}}>
        <div style={{width:46,height:46,borderRadius:10,background:s.light,
          display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:1}}>
          <s.Icon size={18} color={s.color}/>
          <span style={{fontSize:8,fontWeight:800,color:s.color}}>{s.short}</span>
        </div>
        <div style={{flex:1}}>
          <div style={{fontSize:15,fontWeight:700,color:NOAH_C.ink}}>
            {s.label} · {fmtDist(act.distance_km)}
          </div>
          <div style={{fontSize:11,color:NOAH_C.ink3}}>
            {act.fecha} · {Math.round(act.duration_min)}min
            {act.hr_avg ? ` · HR ${Math.round(act.hr_avg)} bpm avg` : ''}
            {act.hr_max ? ` · máx ${Math.round(act.hr_max)}` : ''}
          </div>
        </div>
        <div style={{padding:'4px 12px',borderRadius:99,fontSize:11,fontWeight:700,
          background:`${cumplColor}20`,color:cumplColor,border:`1px solid ${cumplColor}40`,flexShrink:0}}>
          {cumplLabel}
        </div>
        <button onClick={()=>setExpandido(e=>!e)} style={{
          background:'transparent',border:`1px solid ${NOAH_C.border}`,borderRadius:7,
          padding:'4px 10px',cursor:'pointer',fontSize:11,color:NOAH_C.ink3}}>
          {expandido?'▲':'▼'}
        </button>
      </div>

      {/* Métricas pills */}
      <div style={{padding:'10px 18px',display:'flex',gap:8,flexWrap:'wrap',
        borderBottom:`1px solid ${NOAH_C.border}`}}>
        {[
          [Activity, `${Math.round(act.duration_min)} min`],
          [Ruler, fmtDist(act.distance_km)],
          act.hr_avg  && [HeartPulse, `${Math.round(act.hr_avg)} bpm avg`],
          act.hr_max  && [Flame, `máx ${Math.round(act.hr_max)}`],
          act.tss_total && [Target, `TSS ${act.tss_total.toFixed(0)}`],
          act.pace && sport==='running' && [Footprints, fmtPaceStr(act.pace)],
          act.np_watts && [Zap, `${act.np_watts}W NP`],
          act.swolf    && [Waves, `Swolf ${act.swolf.toFixed(1)}`],
        ].filter(Boolean).map(([Icon,val])=>(
          <div key={val} style={{display:'flex',alignItems:'center',gap:4,
            padding:'4px 10px',borderRadius:99,background:`${s.color}10`,
            fontSize:11,fontWeight:600,color:NOAH_C.ink,border:`1px solid ${s.color}20`}}>
            <Icon size={12} color={s.color}/><span>{val}</span>
          </div>
        ))}
      </div>

      {/* Gráfico premium */}
      <div style={{padding:'12px 18px',borderBottom:`1px solid ${NOAH_C.border}`}}>
        <GraficoActividad act={act} laps={laps} sport={sport} lthr={LTHR}
          sesionId={act.sesion_id || act.id} atletaId={atletaId}/>
      </div>

      {/* Torque y W'bal — solo para ciclismo, bajo demanda */}
      {sport === 'cycling' && (
        <TorqueWbalBotones
          atletaId={atletaId}
          sesionId={act.sesion_id || act.id}
          ftp={act.ftp || 200}
          cadenciaOptima={85}
        />
      )}

      {/* Tabla de laps expandible */}
      {expandido && laps.length > 0 && (
        <div style={{padding:'0 18px 14px',
          background:'linear-gradient(160deg,rgba(8,8,20,0.95),rgba(12,12,28,0.92))',
          borderRadius:'0 0 14px 14px'}}>
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:10,marginTop:10}}>
            <thead>
              <tr>
                {['#','Dist','Tiempo','FC','Máx FC',
                  sport==='swimming'?'Swolf':sport==='cycling'?'Watts':'Pace',
                  'Cad','Zona'].map(h=>(
                  <th key={h} style={{padding:'4px 6px',textAlign:'left',
                    color:'rgba(255,255,255,0.3)',fontWeight:600,
                    textTransform:'uppercase',letterSpacing:0.5,fontSize:9}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {laps.map((l,i)=>{
                const zc = (() => {
                  if (!l.hr_avg||!LTHR) return '#94A3B8'
                  const r = l.hr_avg/LTHR
                  return r<0.82?'#94A3B8':r<0.88?NOAH_C.success:r<0.94?'#84CC16':r<1.00?NOAH_C.warning:r<1.06?'#F97316':NOAH_C.danger
                })()
                const zn = (() => {
                  if (!l.hr_avg||!LTHR) return 'Z1'
                  const r = l.hr_avg/LTHR
                  return r<0.82?'Z1':r<0.88?'Z2':r<0.94?'Z3':r<1.00?'Z4':r<1.06?'Z5':'Z6'
                })()
                const metrica = sport==='swimming'&&l.swolf?l.swolf.toFixed(1):
                  sport==='cycling'&&l.avg_power?`${Math.round(l.avg_power)}W`:
                  l.pace?fmtPaceStr(l.pace):'--'
                return (
                  <tr key={i} style={{borderBottom:'1px solid rgba(255,255,255,0.05)'}}>
                    <td style={{padding:'4px 6px',color:'rgba(255,255,255,0.38)',fontWeight:600}}>
                      {l.lap_num||i+1}</td>
                    <td style={{padding:'4px 6px',color:'rgba(255,255,255,0.65)'}}>
                      {l.distance_km?(l.distance_km*1000).toFixed(0)+'m':'--'}</td>
                    <td style={{padding:'4px 6px',color:'rgba(255,255,255,0.5)'}}>
                      {l.duration_min?`${Math.floor(l.duration_min)}'${String(Math.round((l.duration_min%1)*60)).padStart(2,'0')}"` :'--'}</td>
                    <td style={{padding:'4px 6px',fontWeight:700,color:zc}}>
                      {l.hr_avg?Math.round(l.hr_avg):'--'}</td>
                    <td style={{padding:'4px 6px',color:'rgba(255,255,255,0.38)'}}>
                      {l.hr_max?Math.round(l.hr_max):'--'}</td>
                    <td style={{padding:'4px 6px',color:'rgba(255,255,255,0.55)'}}>{metrica}</td>
                    <td style={{padding:'4px 6px',color:'rgba(255,255,255,0.38)'}}>
                      {l.cadence?Math.round(l.cadence):'--'}</td>
                    <td style={{padding:'4px 6px'}}>
                      <span style={{padding:'1px 5px',borderRadius:3,fontSize:9,fontWeight:700,
                        background:`${zc}22`,color:zc}}>{zn}</span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}, (prev, next) =>
  // Solo re-renderiza si cambia la actividad real — no por sesionPresc recreado
  (prev.act?.sesion_id || prev.act?.id) === (next.act?.sesion_id || next.act?.id) &&
  prev.atletaId === next.atletaId
)

// ── MiniCalendarioAtleta — versión para el dashboard del atleta (fondo claro) ─
function MiniCalendarioAtleta({ fechaSeleccionada, onSelect, actividades7dias }) {
  const hoy  = hoyKey()
  const dias = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400000)
    dias.push(d.toISOString().slice(0, 10))
  }
  const DIAS_CORTO = ['D','L','M','M','J','V','S']
  const sportColors = { running: NOAH_C.run, cycling: NOAH_C.bike, swimming: NOAH_C.success }

  return (
    <div style={{ display:'flex', gap:5, alignItems:'center' }}>
      {dias.map(dia => {
        const actsDia = (actividades7dias || {})[dia] || []
        const esHoy   = dia === hoy
        const esSel   = dia === fechaSeleccionada
        const dObj    = new Date(dia + 'T12:00:00')

        return (
          <div key={dia} onClick={() => onSelect && onSelect(dia)} style={{
            flex:1, borderRadius:10, cursor: onSelect ? 'pointer' : 'default',
            padding:'7px 4px', textAlign:'center',
            background: esSel
              ? `linear-gradient(135deg, ${NOAH_C.accent}22, ${NOAH_C.accent}0D)`
              : NOAH_C.cardBg2,
            border: esSel ? `1px solid ${NOAH_C.accent}55` : `1px solid ${NOAH_C.border}`,
            boxShadow: esSel ? `0 2px 8px ${NOAH_C.accent}30` : 'none',
            transition: 'all 0.15s',
          }}>
            <div style={{ fontSize:9, color: esSel ? NOAH_C.run : NOAH_C.ink4,
              fontWeight:700, textTransform:'uppercase', letterSpacing:0.5, marginBottom:2 }}>
              {DIAS_CORTO[dObj.getDay()]}
            </div>
            <div style={{ fontSize:15, fontWeight:700,
              color: esSel ? '#fff' : NOAH_C.ink3 }}>
              {dObj.getDate()}
            </div>
            {esHoy && !esSel && (
              <div style={{width:4,height:4,borderRadius:'50%',background:NOAH_C.accent,margin:'2px auto 0'}}/>
            )}
            <div style={{ display:'flex', justifyContent:'center', gap:2, marginTop:4, minHeight:6 }}>
              {actsDia.map((a, i) => (
                <div key={i} style={{
                  width:5, height:5, borderRadius:'50%',
                  background: sportColors[a.sport] || NOAH_C.ink4,
                }}/>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}


function SesionDelDia({ atletaId, presc }) {
  const hoy = hoyKey()
  const [acts, setActs]   = useState(null)
  const [acts7, setActs7] = useState({})
  // "Mi Sesión" arranca mostrando HOY, pero el atleta puede tocar otro día
  // del mini-calendario de 7 días para ver ese día en particular — a
  // diferencia del bug viejo, esto nunca pasa "solo" (sin que el usuario
  // lo toque) y siempre muestra el detalle del día exacto que se pidió,
  // sin mezclar actividades de otro día.
  const [fechaSel, setFechaSel] = useState(hoy)

  useEffect(() => {
    if (!atletaId) return
    setActs(null)
    setActs7({})
    const desde = new Date(Date.now() - 6 * 86400000).toISOString().slice(0, 10)
    const hasta  = new Date().toISOString().slice(0, 10)
    authFetch(`${API}/atletas/${atletaId}/actividades_rango?desde=${desde}&hasta=${hasta}`)
      .then(r => r.json())
      .then(r => {
        const map = r.data?.actividades || {}
        setActs7(map)
        setActs(map[fechaSel] ?? map[hoy] ?? [])
      })
      .catch(() => { setActs7({}); setActs([]) })
  }, [atletaId])

  // Cuando el atleta toca otro día del mini-calendario, usar lo que ya
  // está en caché (acts7) — no hace falta otro fetch, ya lo trajimos arriba.
  useEffect(() => {
    if (acts7[fechaSel] !== undefined) setActs(acts7[fechaSel])
  }, [fechaSel, acts7])

  const sesiones = presc?.prescripcion?.sesiones || []
  const sesDelDia = sesiones.filter(s => getDiaKey(s.fecha) === fechaSel)

  const esHoySel = fechaSel === hoy
  const diasAtras = Math.round((new Date(hoy) - new Date(fechaSel)) / 86400000)
  const labelActividad = esHoySel ? 'Lo que hiciste hoy'
    : diasAtras === 1 ? 'Lo que hiciste ayer'
    : `Lo que hiciste el ${new Date(fechaSel+'T12:00:00').toLocaleDateString('es-AR',{day:'numeric',month:'short'})}`
  const labelPrescripcion = esHoySel ? 'Prescripción de hoy' : 'Prescripción de ese día'

  return (
    <div style={{display:'flex',flexDirection:'column',gap:20}}>

      {/* Mini calendario 7 días — ahora navegable: tocar otro día muestra SU detalle */}
      <MiniCalendarioAtleta
        fechaSeleccionada={fechaSel}
        onSelect={setFechaSel}
        actividades7dias={acts7}
      />

      {acts === null && (
        <div style={{padding:24,textAlign:'center',color:NOAH_C.ink3}}>Cargando...</div>
      )}

      {/* Actividades del día seleccionado */}
      {acts !== null && acts.length > 0 && (
        <div>
          <div style={{fontSize:11,fontWeight:700,color:NOAH_C.ink4,textTransform:'uppercase',
            letterSpacing:1,marginBottom:12,display:'flex',alignItems:'center',gap:5}}>
            <Footprints size={12}/> {labelActividad}
          </div>
          {acts.map((act,i) => (
            <div key={act.sesion_id || act.id || `act-${act.fecha}-${act.sport}`} style={{marginBottom:i<acts.length-1?16:0}}>
              <ActividadCard
                act={act}
                sesionPresc={sesDelDia.find(s=>s.sport===act.sport)||null}
                atletaId={atletaId}
              />
            </div>
          ))}
        </div>
      )}

      {/* Sin actividad ese día */}
      {acts !== null && acts.length === 0 && (
        <div style={{padding:'24px 20px',background:NOAH_C.cardBg2,borderRadius:12,
          border:`1px solid ${NOAH_C.border}`,textAlign:'center'}}>
          <Satellite size={28} color={NOAH_C.ink4} style={{marginBottom:8}}/>
          <div style={{fontSize:14,fontWeight:600,color:NOAH_C.ink,marginBottom:4}}>
            {esHoySel ? 'Sin actividad registrada hoy' : 'Sin actividad registrada ese día'}
          </div>
          <div style={{fontSize:12,color:NOAH_C.ink3}}>
            Sincronizá Garmin para ver el entrenamiento.
          </div>
        </div>
      )}

      {/* Prescripción del día seleccionado */}
      {sesDelDia.length > 0 && (
        <div>
          <div style={{fontSize:11,fontWeight:700,color:NOAH_C.ink4,textTransform:'uppercase',
            letterSpacing:1,marginBottom:12,display:'flex',alignItems:'center',gap:5}}>
            <ClipboardList size={12}/> {labelPrescripcion}
          </div>
          {sesDelDia.map((ses,i) => (
            <div key={i} style={{background:NOAH_C.cardBg,borderRadius:12,padding:20,
              border:`1px solid ${NOAH_C.border}`,marginBottom:i<sesDelDia.length-1?12:0,
              borderLeft:`4px solid ${SPORT[ses.sport]?.color||NOAH_C.run}`}}>
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:12}}>
                <SportTag sport={ses.sport}/>
                <div>
                  <div style={{fontSize:16,fontWeight:700,color:NOAH_C.ink}}>{ses.nombre}</div>
                  <div style={{fontSize:12,color:NOAH_C.ink3}}>
                    {new Date(ses.fecha+'T12:00:00').toLocaleDateString('es-AR',
                      {weekday:'long',day:'numeric',month:'long'})}
                    {' · '}{Math.round(ses.duracion)}min · TSS {ses.tss}
                  </div>
                </div>
              </div>
              <WorkoutChart sesion={ses} atletaId={atletaId} />
            </div>
          ))}
        </div>
      )}

      {/* Sin nada ese día */}
      {acts !== null && acts.length === 0 && sesDelDia.length === 0 && (
        <div style={{padding:40,textAlign:'center',color:NOAH_C.ink3,fontSize:14}}>
          Sin actividad ni sesión planificada {esHoySel ? 'para hoy' : 'para ese día'}.<br/>
          <span style={{fontSize:12,opacity:0.7}}>Sincronizá Garmin o generá un ciclo nuevo.</span>
        </div>
      )}
    </div>
  )
}


function MiSesion({ presc, atletaId }) {
  const [actHoy, setActHoy] = useState(null)
  const sesiones = presc?.prescripcion?.sesiones || []
  const hoy = hoyKey()
  const ayer = new Date(Date.now()-86400000).toISOString().slice(0,10)

  // Buscar actividad real de hoy o ayer (independiente de prescripción)
  useEffect(() => {
    if (!atletaId) return
    // Buscar actividad real de hoy
    authFetch(`${API}/atletas/${atletaId}/actividad_detalle?fecha=${hoy}&sport=running`)
      .then(r=>r.json()).then(r=>{
        if (r.data?.actividad) { setActHoy({fecha:hoy, ...r.data}) }
        else {
          // Si no hay hoy, buscar ayer
          authFetch(`${API}/atletas/${atletaId}/ultima_actividad`)
            .then(r2=>r2.json()).then(r2=>{
              if (r2.data?.actividad) setActHoy({fecha:r2.data.actividad.fecha, esUltima:true, actividad:r2.data.actividad})
            }).catch(()=>{})
        }
      }).catch(()=>{})
  }, [atletaId, hoy])

  // Sesiones de hoy o la más próxima
  const sesHoy = sesiones.filter(s => getDiaKey(s.fecha) === hoy)
  const sesFuturas = sesiones.filter(s => getDiaKey(s.fecha) > hoy)
  const sesMostrar = sesHoy.length > 0 ? sesHoy : sesFuturas.slice(0,1)

  // Si no hay sesión prescripta hoy pero hay actividad real → mostrarla
  if (!sesMostrar.length) return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      {actHoy ? (
        <div style={{background:NOAH_C.cardBg,borderRadius:12,padding:20,border:`1px solid ${NOAH_C.border}`}}>
          <div style={{fontSize:10,fontWeight:600,color:NOAH_C.ink4,letterSpacing:1,
            textTransform:'uppercase',marginBottom:12}}>
            {actHoy.esAyer ? 'Última actividad — ayer' : 'Actividad de hoy'}
          </div>
          {(actHoy.actividades||[]).map((act,i)=>(
            <div key={i} style={{marginBottom:i<actHoy.actividades.length-1?16:0}}>
              <ActividadCard key={act.sesion_id || act.id} act={act} sesionPresc={null} atletaId={atletaId}/>
            </div>
          ))}
        </div>
      ) : (
        <div style={{padding:32,textAlign:'center',color:NOAH_C.ink3,fontSize:13}}>
          Sin sesiones planificadas para hoy. Generá un ciclo nuevo.
        </div>
      )}
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:16}}>
      {sesMostrar.map((ses,i) => (
        <div key={i} style={{background:NOAH_C.cardBg,borderRadius:12,padding:20,
          border:`1px solid ${NOAH_C.border}`}}>
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:14}}>
            <SportTag sport={ses.sport}/>
            <div>
              <div style={{fontSize:17,fontWeight:700,color:NOAH_C.ink}}>{ses.nombre}</div>
              <div style={{fontSize:12,color:NOAH_C.ink3}}>
                {new Date(ses.fecha+'T12:00:00').toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'long'})}
                {' · '}{Math.round(ses.duracion)}min · TSS {ses.tss}
              </div>
            </div>
          </div>

          {/* Plan de la sesión */}
          <WorkoutChart sesion={ses} atletaId={atletaId} />

          {/* Actividad real si la fecha ya pasó */}
          {getDiaKey(ses.fecha) <= hoy && (
            <div>
              <div style={{height:1,background:NOAH_C.border,margin:'16px 0'}}/>
              <div style={{fontSize:10,fontWeight:600,color:NOAH_C.ink4,letterSpacing:1,
                textTransform:'uppercase',marginBottom:12}}>Lo que hiciste</div>
              <ActividadRealizada sesionPresc={ses} atletaId={atletaId} />
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ── Zonas tables ──────────────────────────────────────────────────────────────
function ZonasRunningTable({ zonas, lthr }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw)
    ? _raw
    : (_raw && typeof _raw === 'object')
      ? Object.entries(_raw).map(([zona, d]) => ({zona, ...d}))
      : null
  const rec = zonas?.recomendacion || zonas?.data?.recomendacion

  if (!lista?.length) return (
    <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>
      Sin datos de zonas running
      {!lthr && <div style={{fontSize:11,color:NOAH_C.ink4,marginTop:4}}>Configurá el LTHR en el perfil del atleta</div>}
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {rec && (
        <div style={{
          padding:'10px 14px', borderRadius:8, marginBottom:12,
          background:`${rec.color}12`, border:`1px solid ${rec.color}30`,
          display:'flex', alignItems:'center', gap:8
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:rec.color,flexShrink:0}}/>
          <span style={{fontSize:12,color:NOAH_C.ink3}}>{rec.msg}</span>
        </div>
      )}
      {lista.map((z, i) => {
        const zColor = z.color || NOAH_C.run
        const pace_rango = z.pace_rango || (z.pace_min && z.pace_max ? `${z.pace_min} – ${z.pace_max} /km` : null)
        return (
          <div key={i} style={{
            padding:'13px 16px', borderBottom:`1px solid ${NOAH_C.border}`,
            display:'flex', justifyContent:'space-between', alignItems:'center',
            borderLeft:`4px solid ${zColor}`,
            background:`${zColor}12`,
          }}>
            <div>
              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>
              <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontSize:14, fontWeight:700, color:zColor}}>{pace_rango || '--'}</div>
              <div style={{fontSize:11, color:NOAH_C.ink3}}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ZonasCyclingTable({ zonas }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw)
    ? _raw
    : (_raw && typeof _raw === 'object')
      ? Object.entries(_raw).map(([zona, d]) => ({zona, ...d}))
      : null
  const rec = zonas?.recomendacion || zonas?.data?.recomendacion

  if (!lista?.length) return (
    <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>Sin datos de zonas ciclismo</div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {rec && (
        <div style={{
          padding:'10px 14px', borderRadius:8, marginBottom:12,
          background:`${rec.color}12`, border:`1px solid ${rec.color}30`,
          display:'flex', alignItems:'center', gap:8
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:rec.color,flexShrink:0}}/>
          <span style={{fontSize:12,color:NOAH_C.ink3}}>{rec.msg}</span>
        </div>
      )}
      {lista.map((z, i) => {
        const zColor = z.color || NOAH_C.bike
        return (
          <div key={i} style={{
            padding:'13px 16px', borderBottom:`1px solid ${NOAH_C.border}`,
            display:'flex', justifyContent:'space-between', alignItems:'center',
            borderLeft:`4px solid ${zColor}`,
            background:`${zColor}12`,
          }}>
            <div>
              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>
              <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>{z.pct_ftp}</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontSize:14, fontWeight:700, color:zColor}}>{z.w_rango||'--'}</div>
              <div style={{fontSize:11, color:NOAH_C.ink3}}>HR {z.hr_min||'--'}–{z.hr_max||'--'} · {z.wkg_min||'--'} W/kg</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ZonasSwimTable({ zonas }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw) ? _raw : (_raw && typeof _raw === "object") ? Object.entries(_raw).map(([zona,d])=>({zona,...d})) : null
  if (!lista?.length) return <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>Sin datos de zonas natación</div>

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {lista.map((z,i)=>(
        <div key={i} style={{
          padding:'13px 16px', borderBottom:`1px solid ${NOAH_C.border}`,
          display:'flex', justifyContent:'space-between', alignItems:'center',
          borderLeft:`4px solid ${NOAH_C.swim}`,
          background:`${NOAH_C.swim}12`,
        }}>
          <div>
            <span style={{fontWeight:800, color:NOAH_C.swim, marginRight:8, fontSize:14}}>{z.zona}</span>
            <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>
            <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>{z.descripcion}</div>
          </div>
          <div style={{textAlign:'right'}}>
            <div style={{fontSize:14, fontWeight:700, color:NOAH_C.swim}}>
              {z.pace_rango || ((z.pace_100m_min||z.pace_min) ? `${z.pace_100m_min||z.pace_min} – ${z.pace_100m_max||z.pace_max}` : '--')}
            </div>
            <div style={{fontSize:11, color:NOAH_C.ink3}}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
          </div>
        </div>
      ))}
    </div>
  )
}




// ── HANNA LIFE — Gráfico de vitalidad autonómica ────────────────────────────
function HannaLifeGrafico({ atletaId, modo = 'dark' }) {
  const [data, setData]   = useState(null)
  const [hover, setHover] = useState(null)
  const [dias, setDias]   = useState(90)
  const [bioIdx, setBioIdx] = useState(0) // carrusel de biomarcadores: 0=HANNA LIFE, 1=Carga, 2=Riesgo viral, 3=ACWR, 4=Monotonía
  const bioTouchRef = useRef(null)
  const [riesgoLesion, setRiesgoLesion] = useState(null)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/hanna_life?dias=${dias}`)
      .then(r=>r.json()).then(r=>setData(r.data)).catch(()=>{})
  }, [atletaId, dias])

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/riesgo_lesion?dias=${dias}`)
      .then(r=>r.json()).then(r=>setRiesgoLesion(r.data)).catch(()=>{})
  }, [atletaId, dias])

  const isDark = modo === 'dark'
  const bg     = isDark ? 'rgba(8,8,20,0.6)'  : '#FFFFFF'
  const brdr   = isDark ? 'rgba(255,255,255,0.08)' : '#E5E7EB'
  const txt    = isDark ? 'rgba(255,255,255,0.88)'  : '#111827'
  const txt2   = isDark ? 'rgba(255,255,255,0.45)'  : '#6B7280'
  const txt3   = isDark ? 'rgba(255,255,255,0.25)'  : '#9CA3AF'

  if (!data) return <div style={{padding:24,textAlign:'center',color:txt2}}>Cargando HANNA LIFE...</div>

  const pts = (data.puntos||[]).filter(p=>p.hanna_life!=null)
  const hoy = data.hanna_hoy || (pts.length ? pts[pts.length-1] : {})

  const NIVEL_COLOR = {
    'Óptimo':NOAH_C.success,'Bueno':NOAH_C.info,'Moderado':NOAH_C.warning,
    'Bajo':'#F97316','Crítico':NOAH_C.danger
  }
  const nColor  = NIVEL_COLOR[hoy.hanna_nivel] || NOAH_C.ink3
  const rColor  = (hoy.riesgo_viral||0)>=60 ? NOAH_C.danger : (hoy.riesgo_viral||0)>=30 ? NOAH_C.warning : NOAH_C.success
  const semaforo = (hoy.hanna_life||0)>=55
    ? {color:NOAH_C.success, icon:BatteryFull, txt:'Puede cargar'}
    : (hoy.hanna_life||0)>=40
    ? {color:NOAH_C.warning, icon:Zap,         txt:'Carga reducida'}
    : {color:NOAH_C.danger,  icon:BatteryLow,  txt:'Solo recuperación'}

  if (!pts.length) return (
    <div style={{padding:24,textAlign:'center',color:txt2,fontSize:12}}>
      Sin datos. Corré: <code>python noah_hanna_life.py --atleta {atletaId} --todo</code>
    </div>
  )

  // ── Proyección 7 días ────────────────────────────────────────────────────
  const genProyeccion = () => {
    if (pts.length < 5) return []
    const ultimos = pts.slice(-7)
    const hl      = hoy.hanna_life || 50
    const tsb     = hoy.hanna_scores?.tsb || 0
    const sleep   = hoy.hanna_scores?.sueno || 50
    const stress  = hoy.hanna_scores?.stress || 50
    // Tendencia: pendiente de los últimos 7 días
    const vals = ultimos.map(p=>p.hanna_life)
    const trend = vals.length > 1 ? (vals[vals.length-1] - vals[0]) / vals.length : 0
    // Proyección: si TSB muy negativo, baja; si buena recuperación, sube
    const factor = tsb < -15 ? -0.8 : tsb > 5 ? 0.3 : 0
    const proy = []
    let cur = hl
    for (let i=1; i<=7; i++) {
      cur = Math.max(10, Math.min(100, cur + (trend * 0.3) + factor + (Math.random()-0.5)*1.5))
      const d = new Date(); d.setDate(d.getDate()+i)
      proy.push({ fecha: d.toISOString().slice(0,10), hl: Math.round(cur*10)/10, proy: true })
    }
    return proy
  }
  const proyeccion = genProyeccion()

  // ── Narrativa inteligente ────────────────────────────────────────────────
  const genNarrativa = () => {
    const hl    = hoy.hanna_life || 0
    const hrv   = hoy.hrv || 0
    const tsb   = hoy.hanna_scores?.tsb || 0
    const sleep = hoy.hanna_scores?.sueno || 50
    const stress= hoy.hanna_scores?.stress || 50
    const rv    = hoy.riesgo_viral || 0
    const frases = []

    // Estado general
    if (hl >= 75) frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — sistema autónomo en condiciones óptimas.`)
    else if (hl >= 55) frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — estado aceptable, podés entrenar con carga moderada.`)
    else if (hl >= 40) frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — hay señales de fatiga acumulada. Reducí la carga.`)
    else frases.push(`Tu HANNA LIFE es ${hl.toFixed(0)} — sistema autónomo comprometido. Priorizar recuperación.`)

    // HRV
    if (hrv > 0) {
      if (hrv < 25) frases.push(`HRV de ${hrv.toFixed(0)}ms es bajo — posible sobrecarga autonómica o mala calidad de sueño.`)
      else if (hrv < 40) frases.push(`HRV de ${hrv.toFixed(0)}ms es moderado — el sistema nervioso autónomo está respondiendo.`)
      else frases.push(`HRV de ${hrv.toFixed(0)}ms es bueno — parasimpático activo, buena recuperación.`)
    }

    // TSB / carga
    if (tsb < -20) frases.push(`TSB ${tsb.toFixed(0)}: carga muy alta. Riesgo de lesión si continuás en zonas 5-6.`)
    else if (tsb < -10) frases.push(`TSB ${tsb.toFixed(0)}: en carga. Tolerás Z3-Z4 pero moderá volumen en zonas altas.`)
    else if (tsb > 10) frases.push(`TSB ${tsb.toFixed(0)}: buena frescura. Podés atacar entrenamientos de calidad.`)

    // Sueño
    if (sleep < 40) frases.push(`Calidad de sueño baja (${sleep.toFixed(0)}/100). Intentá llegar a 7-8h de sueño reparador.`)

    // Riesgo viral
    if (rv >= 50) frases.push(`Riesgo viral ${rv.toFixed(0)}% — RMSSD bajo. Si hay síntomas, no entrenar.`)
    else if (rv >= 30) frases.push(`Riesgo viral moderado (${rv.toFixed(0)}%). Monitoreá síntomas en las próximas 48h.`)

    // Proyección
    const pFinal = proyeccion[proyeccion.length-1]
    if (pFinal) {
      if (pFinal.hl < hl - 5) frases.push(`Proyección a 7 días: tendencia a la baja (${pFinal.hl.toFixed(0)}). Revisá la carga semanal.`)
      else if (pFinal.hl > hl + 3) frases.push(`Proyección a 7 días: tendencia favorable (${pFinal.hl.toFixed(0)}) si mantenés buena recuperación.`)
    }

    return frases
  }
  const narrativa = genNarrativa()

  // ── SVG ──────────────────────────────────────────────────────────────────
  const allPts = [...pts, ...proyeccion.map((p,i)=>({
    ...p, hanna_life: p.hl, hanna_nivel: p.hl>=75?'Óptimo':p.hl>=55?'Bueno':p.hl>=40?'Moderado':p.hl>=25?'Bajo':'Crítico'
  }))]

  const W=780, H=200, PT=24, PR=24, PB=28, PL=44
  const iW=W-PL-PR, iH=H-PT-PB
  const n = allPts.length

  const hannaVals = pts.map(p=>p.hanna_life)
  const baseline  = hannaVals.length>7 ? hannaVals.slice(-30).reduce((a,b)=>a+b,0)/Math.min(30,hannaVals.length) : 65
  const minY = Math.max(10, Math.min(30, ...hannaVals.filter(Boolean)) - 5)
  const maxY = Math.min(100, Math.max(80, ...hannaVals.filter(Boolean)) + 5)
  const xs = i => PL + (i/Math.max(n-1,1)) * iW
  const ys = v => PT + iH - ((v-minY)/(maxY-minY||1)) * iH
  const xHist = PL + (pts.length-1)/Math.max(n-1,1) * iW  // línea divisora hoy/proyección

  const step = Math.max(1, Math.floor(n/8))
  const xLabels = allPts.reduce((acc,p,i)=>{ if(i%step===0) acc.push({i,label:p.fecha.slice(5),proy:p.proy}); return acc }, [])

  const handleMouse = e => {
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = (e.clientX-rect.left)*(W/rect.width)
    setHover(Math.max(0,Math.min(n-1,Math.round((mx-PL)/iW*(n-1)))))
  }

  const umbral = baseline * 0.88

  return (
    <div style={{display:'flex',flexDirection:'column',gap:14}}>

      {/* Carrusel de biomarcadores — centro grande/protagonista, laterales chicas/borrosas (mismo criterio que el carrusel de tabs) */}
      {(() => {
        const nivelColor = { bajo:NOAH_C.success, optima:NOAH_C.success, moderado:NOAH_C.warning,
          atencion:NOAH_C.warning, alto:NOAH_C.danger }
        const bios = [
          { key:'hanna', color:nColor },
          { key:'carga', color:semaforo.color },
          { key:'viral', color:rColor },
          { key:'acwr', color: nivelColor[riesgoLesion?.acwr?.nivel_riesgo] || NOAH_C.ink3 },
          { key:'monotonia', color: nivelColor[riesgoLesion?.monotonia_strain?.nivel_riesgo] || NOAH_C.ink3 },
        ]
        const nB = bios.length
        const goToBio = (i) => setBioIdx(((i % nB) + nB) % nB)
        const idxPrev = (bioIdx - 1 + nB) % nB
        const idxNext = (bioIdx + 1) % nB

        const onTouchStart = (e) => { bioTouchRef.current = e.touches[0].clientX }
        const onTouchEnd = (e) => {
          if (bioTouchRef.current == null) return
          const dx = e.changedTouches[0].clientX - bioTouchRef.current
          if (dx > 40) goToBio(bioIdx - 1)
          else if (dx < -40) goToBio(bioIdx + 1)
          bioTouchRef.current = null
        }

        // Contenido interno de cada tarjeta (compacto para lateral, completo para centro)
        const BioContent = ({ k, color, compact }) => {
          if (k === 'hanna') return (
            <>
              <div style={{fontSize:compact?8:9,fontWeight:700,color,textTransform:'uppercase',letterSpacing:1,marginBottom:compact?2:4}}>
                HANNA LIFE
              </div>
              <div style={{fontSize:compact?22:40,fontWeight:900,color,lineHeight:1,letterSpacing:-1}}>
                {hoy.hanna_life?.toFixed(0)||'--'}
              </div>
              {!compact && <div style={{fontSize:12,color:txt2,marginTop:4}}>{hoy.hanna_nivel||'--'}</div>}
              {!compact && (
                <div style={{display:'flex',gap:7,marginTop:12,flexWrap:'wrap',justifyContent:'center'}}>
                  {[
                    ['HRV', hoy.hrv_ms ? Math.round(hoy.hrv_ms)+'ms' : null, NOAH_C.run],
                    ['FC',  hoy.hr_reposo ? Math.round(hoy.hr_reposo)+'bpm' : null, NOAH_C.success],
                    ['Stress', hoy.stress != null ? Math.round(hoy.stress) : null, NOAH_C.warning],
                    ['Sueño', hoy.sleep_h ? hoy.sleep_h.toFixed(1)+'h' : null, '#60A5FA'],
                    ['SpO2', hoy.spo2 ? hoy.spo2.toFixed(0)+'%' : null, NOAH_C.bike],
                    ['TSB', hoy.hanna_scores?.tsb != null ? hoy.hanna_scores.tsb.toFixed(0) : null,
                      (hoy.hanna_scores?.tsb||0) > 0 ? NOAH_C.success : (hoy.hanna_scores?.tsb||0) < -10 ? NOAH_C.danger : '#94A3B8'],
                  ].map(([l,v,c])=> v != null ? (
                    <div key={l} style={{textAlign:'center',minWidth:30}}>
                      <div style={{fontSize:12,fontWeight:700,color:c}}>{v}</div>
                      <div style={{fontSize:8,color:txt3}}>{l}</div>
                    </div>
                  ) : null)}
                </div>
              )}
            </>
          )
          if (k === 'carga') return (
            <>
              <semaforo.icon size={compact?20:38} color={color} strokeWidth={1.8}/>
              <div style={{fontSize:compact?10:14,fontWeight:700,color,textAlign:'center',marginTop:compact?4:8}}>{semaforo.txt}</div>
              {!compact && (
                <div style={{fontSize:11,color:txt2,textAlign:'center',marginTop:4}}>
                  {(hoy.hanna_life||0)>=55?'Sistema preparado':'Priorizar recuperación'}
                </div>
              )}
            </>
          )
          if (k === 'viral') return (
            <>
              <div style={{fontSize:compact?8:9,fontWeight:700,color,textTransform:'uppercase',letterSpacing:1,marginBottom:compact?2:4}}>
                Riesgo viral
              </div>
              <div style={{fontSize:compact?22:40,fontWeight:900,color,lineHeight:1,letterSpacing:-1}}>
                {hoy.riesgo_viral?.toFixed(0)||'0'}%
              </div>
              {!compact && (
                <>
                  <div style={{fontSize:12,color:txt2,marginTop:4,textTransform:'capitalize'}}>
                    {hoy.riesgo_viral_nivel||'bajo'}
                  </div>
                  <div style={{fontSize:10,color:txt2,marginTop:8,display:'flex',alignItems:'center',gap:5,textAlign:'left'}}>
                    {(hoy.riesgo_viral||0)>=60 ? <><AlertTriangle size={12} color={NOAH_C.danger}/> Descanso. Ver médico si hay síntomas.</>
                    :(hoy.riesgo_viral||0)>=30 ? <><Zap size={12} color={NOAH_C.warning}/> Reducir carga. Monitorear.</>
                    : <><CheckCircle2 size={12} color={NOAH_C.success}/> Sin señales de alerta.</>}
                  </div>
                  {hoy.riesgo_viral_alertas?.map((a,i)=>(
                    <div key={i} style={{fontSize:9,color:a.nivel==='alto'?NOAH_C.danger:NOAH_C.warning,marginTop:2}}>▸ {a.msg}</div>
                  ))}
                </>
              )}
            </>
          )
          // ACWR — riesgo mecánico de lesión por carga aguda vs crónica (Gabbett 2016).
          // Indicador independiente de HANNA LIFE/riesgo viral — no se fusiona con ellos.
          if (k === 'acwr') {
            const a = riesgoLesion?.acwr
            if (!a?.disponible) return (
              <>
                <Scale size={compact?20:34} color={color} strokeWidth={1.8}/>
                {!compact && <div style={{fontSize:11,color:txt2,textAlign:'center',marginTop:8}}>Historial insuficiente</div>}
              </>
            )
            return (
              <>
                <div style={{fontSize:compact?8:9,fontWeight:700,color,textTransform:'uppercase',letterSpacing:1,marginBottom:compact?2:4}}>
                  ACWR
                </div>
                <div style={{fontSize:compact?22:40,fontWeight:900,color,lineHeight:1,letterSpacing:-1}}>
                  {a.acwr?.toFixed(2)}
                </div>
                {!compact && (
                  <>
                    <div style={{fontSize:12,color:txt2,marginTop:4,textTransform:'capitalize'}}>
                      {a.zona?.replace('_',' ')}
                    </div>
                    <div style={{fontSize:10,color:txt2,marginTop:8,lineHeight:1.4,textAlign:'left'}}>
                      {a.mensaje}
                    </div>
                  </>
                )}
              </>
            )
          }
          // Monotonía/Strain — variación de carga día a día (Foster 1998).
          // También independiente — no se mezcla con los otros indicadores.
          const m = riesgoLesion?.monotonia_strain
          if (!m?.disponible) return (
            <>
              <Waves size={compact?20:34} color={color} strokeWidth={1.8}/>
              {!compact && <div style={{fontSize:11,color:txt2,textAlign:'center',marginTop:8}}>Historial insuficiente</div>}
            </>
          )
          return (
            <>
              <div style={{fontSize:compact?8:9,fontWeight:700,color,textTransform:'uppercase',letterSpacing:1,marginBottom:compact?2:4}}>
                Monotonía
              </div>
              <div style={{fontSize:compact?22:40,fontWeight:900,color,lineHeight:1,letterSpacing:-1}}>
                {m.monotonia_maxima ? '>2.0' : m.monotonia?.toFixed(1)}
              </div>
              {!compact && (
                <>
                  <div style={{fontSize:12,color:txt2,marginTop:4}}>
                    {m.strain ? `Strain ${m.strain.toFixed(0)}` : ''}
                  </div>
                  <div style={{fontSize:10,color:txt2,marginTop:8,lineHeight:1.4,textAlign:'left'}}>
                    {m.mensaje}
                  </div>
                </>
              )}
            </>
          )
        }

        const BioCard = ({ idx, pos }) => {
          const b = bios[idx]
          const isCenter = pos === 0
          return (
            <div
              key={b.key}
              onClick={() => !isCenter && goToBio(idx)}
              onTouchStart={isCenter ? onTouchStart : undefined}
              onTouchEnd={isCenter ? onTouchEnd : undefined}
              style={{
                flexShrink: 0,
                width: isCenter ? 168 : 86,
                minHeight: isCenter ? 190 : 110,
                padding: isCenter ? '16px 14px' : '10px 8px',
                borderRadius: 16,
                border: `1px solid ${isCenter ? b.color+'45' : 'rgba(255,255,255,0.08)'}`,
                background: isCenter
                  ? `linear-gradient(135deg, ${b.color}22, ${b.color}08)`
                  : 'transparent',
                boxShadow: isCenter
                  ? `0 14px 32px -10px rgba(0,0,0,0.55), 0 0 24px -6px ${b.color}38`
                  : 'none',
                opacity: isCenter ? 1 : 0.45,
                filter: isCenter ? 'none' : 'blur(0.5px)',
                transform: isCenter ? 'scale(1) translateY(0)' : 'scale(0.8) translateY(8px)',
                transition: 'all 0.3s cubic-bezier(.22,.68,0,1.15)',
                display: 'flex', flexDirection:'column', alignItems: 'center', justifyContent: 'center',
                textAlign: 'center',
                cursor: isCenter ? 'default' : 'pointer',
                userSelect: 'none', touchAction: isCenter ? 'pan-y' : 'auto',
                zIndex: isCenter ? 2 : 1,
              }}
            >
              <BioContent k={b.key} color={isCenter?b.color:'rgba(255,255,255,0.4)'} compact={!isCenter}/>
            </div>
          )
        }

        return (
          <div>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:6 }}>
              <button onClick={()=>goToBio(bioIdx-1)} aria-label="Biomarcador anterior" style={{
                width:26, height:26, borderRadius:'50%', flexShrink:0,
                background:'rgba(255,255,255,0.06)', border:`1px solid ${NOAH_C.border2}`,
                color:NOAH_C.ink2, display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <ChevronLeft size={14}/>
              </button>

              <BioCard idx={idxPrev} pos={-1}/>
              <BioCard idx={bioIdx} pos={0}/>
              <BioCard idx={idxNext} pos={1}/>

              <button onClick={()=>goToBio(bioIdx+1)} aria-label="Biomarcador siguiente" style={{
                width:26, height:26, borderRadius:'50%', flexShrink:0,
                background:'rgba(255,255,255,0.06)', border:`1px solid ${NOAH_C.border2}`,
                color:NOAH_C.ink2, display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <ChevronRight size={14}/>
              </button>
            </div>

            <div style={{display:'flex',justifyContent:'center',gap:6,marginTop:10}}>
              {bios.map((b,i) => (
                <button key={b.key} onClick={()=>goToBio(i)} style={{
                  width: i===bioIdx ? 18 : 6,
                  height: 6, borderRadius: 99, border: 'none', cursor: 'pointer',
                  background: i===bioIdx ? b.color : 'rgba(255,255,255,0.15)',
                  transition: 'all 0.25s ease', padding: 0,
                }}/>
              ))}
            </div>
          </div>
        )
      })()}

      {/* Narrativa inteligente */}
      {narrativa.length>0&&(
        <div style={{
          padding:'18px 20px',borderRadius:14,
          background:isDark?'rgba(99,102,241,0.08)':'#F0F0FF',
          border:`1px solid ${isDark?'rgba(99,102,241,0.2)':'#C7D2FE'}`,
          backdropFilter:'blur(8px)',
        }}>
          <div style={{fontSize:13,fontWeight:700,color:isDark?'#A5B4FC':'#4F46E5',
            textTransform:'uppercase',letterSpacing:0.8,marginBottom:12,display:'flex',alignItems:'center',gap:6}}>
            <Brain size={16}/> Análisis NOAH
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:10}}>
            {narrativa.map((f,i)=>(
              <div key={i} style={{fontSize:14,color:isDark?'rgba(255,255,255,0.85)':'#374151',
                lineHeight:1.6,paddingLeft:12,borderLeft:`2px solid ${isDark?'rgba(99,102,241,0.4)':'#818CF8'}`}}>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Selector días */}
      <div style={{display:'flex',gap:5,alignItems:'center'}}>
        <span style={{fontSize:10,color:txt3}}>Período:</span>
        {[30,60,90,180].map(d=>(
          <button key={d} onClick={()=>setDias(d)} style={{
            padding:'3px 9px',borderRadius:5,cursor:'pointer',fontSize:10,
            border:`1px solid ${dias===d?NOAH_C.run:brdr}`,
            background:dias===d?'rgba(167,139,250,0.18)':'transparent',
            color:dias===d?NOAH_C.run:txt3,
          }}>{d}d</button>
        ))}
        <span style={{fontSize:9,color:txt3,marginLeft:6}}>{pts.length} días con datos</span>
      </div>

      {/* Gráfico */}
      <div style={{
        background:'transparent',padding:'10px 0',
        overflowX:'auto',
      }}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          style={{display:'block',maxWidth:'100%',cursor:'crosshair'}}
          onMouseMove={handleMouse} onMouseLeave={()=>setHover(null)}>

          <defs>
            <linearGradient id={`gHL_${atletaId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={nColor} stopOpacity={isDark?"0.25":"0.15"}/>
              <stop offset="100%" stopColor={nColor} stopOpacity="0"/>
            </linearGradient>
          </defs>

          {/* Zonas de color de fondo */}
          {[[80,100,NOAH_C.success],[65,80,NOAH_C.info],[50,65,NOAH_C.warning],[35,50,'#F97316'],[minY,35,NOAH_C.danger]].map(([a,b,c])=>(
            <rect key={a} x={PL} y={ys(Math.min(b,maxY))} width={iW}
              height={Math.max(0,ys(Math.max(a,minY))-ys(Math.min(b,maxY)))}
              fill={c} opacity={isDark?0.05:0.04}/>
          ))}

          {/* Zona de riesgo */}
          {pts.map((p,i)=>{
            if(i===0||!pts[i-1]) return null
            if(p.hanna_life<umbral||pts[i-1].hanna_life<umbral)
              return <rect key={i} x={xs(i-1)} y={ys(umbral)}
                width={xs(i)-xs(i-1)} height={Math.max(0,PT+iH-ys(umbral))}
                fill="#EF444415"/>
            return null
          })}

          {/* Grid */}
          {[35,50,65,80].filter(v=>v>=minY&&v<=maxY).map(v=>(
            <line key={v} x1={PL} y1={ys(v)} x2={W-PR} y2={ys(v)}
              stroke={isDark?'rgba(255,255,255,0.05)':'rgba(0,0,0,0.05)'} strokeWidth="1"/>
          ))}

          {/* Líneas de referencia */}
          <line x1={PL} y1={ys(umbral)} x2={W-PR} y2={ys(umbral)}
            stroke={NOAH_C.danger} strokeWidth="1" strokeDasharray="3,3" opacity={0.35}/>
          <line x1={PL} y1={ys(baseline)} x2={W-PR} y2={ys(baseline)}
            stroke={NOAH_C.warning} strokeWidth="1.5" strokeDasharray="8,4" opacity={0.65}/>
          <foreignObject x={W-PR-28} y={ys(baseline)-15} width="14" height="14">
            <User size={11} color={NOAH_C.warning}/>
          </foreignObject>
          <text x={W-PR-12} y={ys(baseline)-4} textAnchor="end" fontSize="9"
            fill={NOAH_C.warning} opacity={0.8}>{baseline.toFixed(0)}</text>

          {/* Divisor HOY/PROYECCIÓN */}
          {proyeccion.length>0&&(
            <>
              <line x1={xHist} y1={PT} x2={xHist} y2={PT+iH}
                stroke={isDark?'rgba(255,255,255,0.2)':'rgba(0,0,0,0.15)'}
                strokeWidth="1.5" strokeDasharray="4,3"/>
              <text x={xHist+4} y={PT+10} fontSize="8"
                fill={isDark?'rgba(255,255,255,0.4)':'#9CA3AF'}>HOY</text>
              <text x={xHist+4} y={PT+20} fontSize="8"
                fill={isDark?'rgba(167,139,250,0.7)':NOAH_C.ctl}>→ proyección</text>
            </>
          )}

          {/* Área bajo histórico */}
          {pts.length>1&&(
            <path
              d={pts.map((p,i)=>`${i===0?'M':'L'}${xs(i).toFixed(1)},${ys(p.hanna_life).toFixed(1)}`).join(' ')
                +` L${xs(pts.length-1)},${PT+iH} L${xs(0)},${PT+iH} Z`}
              fill={`url(#gHL_${atletaId})`}/>
          )}

          {/* Curva histórica — segmentos coloreados */}
          {pts.slice(1).map((p,i)=>{
            const c=NIVEL_COLOR[p.hanna_nivel]||'#6B7280'
            return p.hanna_life!=null&&pts[i].hanna_life!=null
              ? <line key={i}
                  x1={xs(i).toFixed(1)} y1={ys(pts[i].hanna_life).toFixed(1)}
                  x2={xs(i+1).toFixed(1)} y2={ys(p.hanna_life).toFixed(1)}
                  stroke={c} strokeWidth="2.5" strokeLinecap="round" opacity="0.9"/>
              : null
          })}

          {/* Curva proyectada — línea punteada */}
          {proyeccion.length>1&&(
            <path
              d={proyeccion.map((p,i)=>`${i===0?'M':'L'}${xs(pts.length-1+i).toFixed(1)},${ys(p.hl).toFixed(1)}`).join(' ')}
              fill="none" stroke={isDark?'rgba(167,139,250,0.6)':'#818CF8'}
              strokeWidth="2" strokeDasharray="6,4"/>
          )}

          {/* Puntos históricos */}
          {pts.map((p,i)=>{
            const c=NIVEL_COLOR[p.hanna_nivel]||'#6B7280'
            const isH=hover===i
            return p.hrv
              ? <circle key={i} cx={xs(i)} cy={ys(p.hanna_life)} r={isH?6:2.5}
                  fill={c} stroke={isDark?'rgba(255,255,255,0.4)':'white'} strokeWidth="1.5"/>
              : <circle key={i} cx={xs(i)} cy={ys(p.hanna_life)} r={isH?5:2}
                  fill="none" stroke={c} strokeWidth="1.5"/>
          })}

          {/* Zonas de referencia ACWR (Gabbett 2016) — igual criterio que el
              baseline/umbral de HANNA LIFE: dos líneas finas marcando los
              límites documentados de la zona óptima (0.8-1.3) y el umbral
              de riesgo alto (1.5), para poder leer "dónde estoy" sin tener
              que memorizar la escala normalizada. */}
          {(() => {
            const hist = riesgoLesion?.historico_acwr || []
            if (hist.length < 2) return null
            const acwrMin = 0.5, acwrMax = 1.8
            const normY = v => minY + ((v-acwrMin)/(acwrMax-acwrMin)) * (maxY-minY)
            return (
              <g opacity={0.55}>
                <line x1={PL} y1={normY(0.8)} x2={W-PR} y2={normY(0.8)}
                  stroke={NOAH_C.bike} strokeWidth="0.75" strokeDasharray="2,3"/>
                <line x1={PL} y1={normY(1.5)} x2={W-PR} y2={normY(1.5)}
                  stroke={NOAH_C.danger} strokeWidth="0.75" strokeDasharray="2,3"/>
                <text x={PL+2} y={normY(0.8)-3} fontSize="7" fill={NOAH_C.bike} opacity={0.8}>0.8 óptimo</text>
                <text x={PL+2} y={normY(1.5)-3} fontSize="7" fill={NOAH_C.danger} opacity={0.8}>1.5 riesgo alto</text>
              </g>
            )
          })()}

          {/* Curva de ACWR — riesgo de lesión mecánica (Gabbett 2016), independiente
              de HANNA LIFE. Se dibuja en el MISMO lienzo pero normalizada a la
              escala visual del eje (no se suma ni promedia con HANNA LIFE en
              ningún momento — solo comparten coordenadas de pantalla para que
              se puedan comparar visualmente sin abrir un segundo gráfico).
              Trazo punteado + más fino + suavizado, para que nunca compita
              visualmente con la línea sólida de HANNA LIFE. */}
          {(() => {
            const hist = riesgoLesion?.historico_acwr || []
            if (hist.length < 2) return null
            // ACWR normal oscila ~0.5-1.8. Se mapea linealmente a minY-maxY
            // (el mismo rango del eje de HANNA LIFE) solo para POSICIONAR la
            // línea en el gráfico — el número real de ACWR se muestra en el
            // tooltip al pasar el mouse, nunca se mezcla con el valor de HL.
            const acwrMin = 0.5, acwrMax = 1.8
            const normY = v => minY + ((v-acwrMin)/(acwrMax-acwrMin)) * (maxY-minY)

            // Suavizado bezier simple — evita que la línea se vea "quebrada"
            // entre cada punto diario, dándole un trazo curvo más liviano.
            const validos = hist.map((h,i) => h.acwr!=null ? {i, v:h.acwr} : null).filter(Boolean)
            if (validos.length < 2) return null
            let d = `M${xs(validos[0].i).toFixed(1)},${normY(validos[0].v).toFixed(1)}`
            for (let k=1; k<validos.length; k++) {
              const p0 = validos[k-1], p1 = validos[k]
              const x0=xs(p0.i), y0=normY(p0.v), x1=xs(p1.i), y1=normY(p1.v)
              const cp1x = x0+(x1-x0)*0.4, cp2x = x1-(x1-x0)*0.4
              d += ` C${cp1x.toFixed(1)},${y0.toFixed(1)} ${cp2x.toFixed(1)},${y1.toFixed(1)} ${x1.toFixed(1)},${y1.toFixed(1)}`
            }

            const ultimo = [...hist].reverse().find(h => h.acwr != null)
            return (
              <g>
                <path d={d} fill="none" stroke={NOAH_C.bike} strokeWidth="1.4"
                  strokeDasharray="5,4" strokeLinecap="round" opacity="0.75"/>
                {ultimo && (
                  <>
                    <circle cx={xs(hist.length-1)} cy={normY(ultimo.acwr)} r={3}
                      fill={NOAH_C.bike} stroke={isDark?'rgba(255,255,255,0.4)':'white'} strokeWidth="1.2"/>
                    <text x={xs(hist.length-1)-6} y={normY(ultimo.acwr)-7} textAnchor="end"
                      fontSize="9" fill={NOAH_C.bike} fontWeight="700">ACWR {ultimo.acwr}</text>
                  </>
                )}
              </g>
            )
          })()}

          {/* Puntos proyectados */}
          {proyeccion.map((p,i)=>(
            <circle key={`p${i}`} cx={xs(pts.length-1+i)} cy={ys(p.hl)} r={2}
              fill="none" stroke={isDark?'rgba(167,139,250,0.6)':'#818CF8'} strokeWidth="1.5"
              strokeDasharray="2,2"/>
          ))}

          {/* Tooltip hover */}
          {hover!=null&&hover<allPts.length&&(()=>{
            const p   = allPts[hover]
            const col = NIVEL_COLOR[p.hanna_nivel]||'#6B7280'
            const tx  = Math.min(xs(hover)+10, W-PR-150)
            const ty  = PT+2
            const isProy = !!p.proy
            // Valor de ACWR del mismo día — se busca por índice en el histórico,
            // que está alineado 1:1 con allPts (mismo período/cantidad de días).
            const acwrHist = riesgoLesion?.historico_acwr || []
            const acwrPunto = acwrHist[hover]
            const boxH = isProy ? 70 : (acwrPunto?.acwr!=null ? 108 : 95)
            return <>
              <line x1={xs(hover)} y1={PT} x2={xs(hover)} y2={PT+iH}
                stroke={isDark?'rgba(255,255,255,0.12)':'rgba(0,0,0,0.07)'} strokeWidth="1"/>
              <rect x={tx} y={ty} width={145} height={boxH} rx={8}
                fill={isDark?'rgba(8,8,20,0.97)':'rgba(255,255,255,0.97)'}
                stroke={col} strokeWidth="1.5"/>
              <text x={tx+8} y={ty+13} fontSize="9" fill={txt3}>{p.fecha}{isProy?' (proyección)':''}</text>
              <text x={tx+8} y={ty+27} fontSize="13" fontWeight="800" fill={col}>
                {(p.hanna_life||p.hl)?.toFixed(0)} — {p.hanna_nivel}
              </text>
              {!isProy&&<>
                {p.hrv&&<text x={tx+8} y={ty+41} fontSize="10" fill="#A78BFA" fontWeight="600">HRV: {p.hrv?.toFixed(1)}ms</text>}
                {p.bb&&<text x={tx+8} y={ty+54} fontSize="10" fill={txt2}>BB: {Math.round(p.bb)}</text>}
                {p.sleep&&<text x={tx+8} y={ty+67} fontSize="10" fill={txt2}>Sueño: {p.sleep?.toFixed(1)}h</text>}
                <text x={tx+8} y={ty+80} fontSize="9" fill={p.riesgo_viral>30?NOAH_C.danger:NOAH_C.success}>
                  Riesgo viral: {p.riesgo_viral?.toFixed(0)||'0'}%
                </text>
                {acwrPunto?.acwr!=null && (
                  <text x={tx+8} y={ty+93} fontSize="10" fill={NOAH_C.bike} fontWeight="700">
                    ACWR: {acwrPunto.acwr}
                  </text>
                )}
              </>}
            </>
          })()}

          {/* Íconos eje Y */}
          <foreignObject x={PL-13} y={ys(90)-7} width="14" height="14"><BatteryFull size={12} color={NOAH_C.success}/></foreignObject>
          <foreignObject x={PL-13} y={ys(55)-7} width="14" height="14"><Zap size={11} color={NOAH_C.info}/></foreignObject>
          <foreignObject x={PL-13} y={ys(25)-7} width="14" height="14"><BatteryLow size={12} color={NOAH_C.danger}/></foreignObject>

          {/* Eje X */}
          {xLabels.map(({i,label,proy})=>(
            <text key={i} x={xs(i)} y={H-PB+14} textAnchor="middle" fontSize="8"
              fill={proy?(isDark?'rgba(167,139,250,0.6)':'#818CF8'):txt3}
              fontStyle={proy?'italic':'normal'}>{label}</text>
          ))}
        </svg>
      </div>

      {/* Leyenda */}
      <div style={{display:'flex',gap:10,flexWrap:'wrap',alignItems:'center'}}>
        {Object.entries(NIVEL_COLOR).map(([nivel,color])=>(
          <div key={nivel} style={{display:'flex',alignItems:'center',gap:3}}>
            <div style={{width:10,height:3,background:color,borderRadius:1,boxShadow:`0 0 4px ${color}80`}}/>
            <span style={{fontSize:9,color:txt2}}>{nivel}</span>
          </div>
        ))}
        <span style={{fontSize:9,color:txt3,marginLeft:4,display:'inline-flex',alignItems:'center',gap:3}}>
          ● HRV real · ○ estimado · <User size={9}/> baseline · - - proyección 7d
        </span>
        <span style={{fontSize:9,color:NOAH_C.bike,marginLeft:4,display:'inline-flex',alignItems:'center',gap:4}}>
          <span style={{width:12,height:2,background:NOAH_C.bike,borderRadius:1,display:'inline-block'}}/>
          ACWR
        </span>
      </div>

      {/* Nota */}
      <div style={{fontSize:9,color:txt3,fontStyle:'italic'}}>
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
    'Óptimo':NOAH_C.success,'Bueno':NOAH_C.info,
    'Moderado':NOAH_C.warning,'Bajo':'#F97316','Crítico':NOAH_C.danger
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
    { yi: 85, icon: BatteryFull, label: 'Óptimo',   color: NOAH_C.success },
    { yi: baselinePob, icon: Zap, label: 'Referencia', color: NOAH_C.info },
    { yi: baselinePerso, icon: User, label: 'Tu baseline', color: NOAH_C.warning },
    { yi: 25, icon: BatteryLow, label: 'Alerta',   color: NOAH_C.danger },
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
            {label:'╌╌ Ref. poblacional', color:NOAH_C.info},
            {label:'╌╌ Tu baseline', color:NOAH_C.warning},
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
              <stop offset="0%" stopColor={NOAH_C.danger} stopOpacity="0.0"/>
              <stop offset="100%" stopColor={NOAH_C.danger} stopOpacity="0.15"/>
            </linearGradient>
          </defs>

          {/* Baseline poblacional */}
          <path d={pathPob} fill="none" stroke={NOAH_C.info} strokeWidth="1.5"
            strokeDasharray="8,4" opacity={0.7}/>
          {/* Label baseline pob */}
          {basePobPts[1] && (
            <g transform={`translate(${basePobPts[1].sx+2},${basePobPts[1].sy-6})`}>
              <foreignObject width="14" height="14"><Zap size={11} color={NOAH_C.info}/></foreignObject>
              <text x={15} y={11} fontSize="10" fill={NOAH_C.info} opacity={0.8}>{baselinePob.toFixed(0)}</text>
            </g>
          )}

          {/* Baseline personal */}
          <path d={pathPerso} fill="none" stroke={NOAH_C.warning} strokeWidth="1.5"
            strokeDasharray="5,3" opacity={0.8}/>
          {basePersoPts[1] && (
            <g transform={`translate(${basePersoPts[1].sx+2},${basePersoPts[1].sy-6})`}>
              <foreignObject width="14" height="14"><User size={11} color={NOAH_C.warning}/></foreignObject>
              <text x={15} y={11} fontSize="10" fill={NOAH_C.warning} opacity={0.9}>{baselinePerso.toFixed(0)}</text>
            </g>
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
          {yAxisPts.map(({yi,icon:AxisIcon,label,color})=>{
            const p = toScreen(-2, yi, 0)
            return (
              <g key={label}>
                <foreignObject x={p.sx-15} y={p.sy-7} width="14" height="14">
                  <AxisIcon size={12} color={color}/>
                </foreignObject>
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
                  (hoverPt.hanna||0) >= baselinePob ? NOAH_C.success :
                  (hoverPt.hanna||0) >= baselinePerso ? NOAH_C.warning : NOAH_C.danger
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
          {icon:BatteryFull,label:'Sobre referencia poblacional',desc:'Vitalidad óptima',color:NOAH_C.success},
          {icon:Zap,label:'En línea con referencia',desc:'Nivel saludable normal',color:NOAH_C.info},
          {icon:User,label:'En tu baseline personal',desc:'Tu estado típico',color:NOAH_C.warning},
          {icon:BatteryLow,label:'Bajo tu baseline',desc:'Riesgo de enfermedad o sobrecarga',color:NOAH_C.danger},
        ].map(({icon:Icon,label,desc,color})=>(
          <div key={label} style={{display:'flex',gap:8,alignItems:'flex-start',
            padding:'8px 12px',borderRadius:8,background:`${color}10`,
            border:`1px solid ${color}25`,flex:'1 1 180px'}}>
            <Icon size={16} color={color} style={{flexShrink:0,marginTop:1}}/>
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


function PeriodizacionChart({ id }) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!id) return
    authFetch(`${API}/atletas/${id}/periodizacion`)
      .then(r => r.json()).then(r => setData(r.data)).catch(() => {})
  }, [id])
  if (!data) return <div style={{textAlign:'center',padding:32,color:NOAH_C.ink4,fontSize:13}}>Cargando...</div>
  const COLORES = {'A':NOAH_C.ctl,'T':NOAH_C.warning,'R':NOAH_C.danger,'TAPER':NOAH_C.success}
  const LABELS = {'A':'Acumulación','T':'Transformación','R':'Realización','TAPER':'Taper'}
  const hist = data?.historico || []
  const proy = data?.proyectado || []
  const todos = [...hist,...proy]
  if (!todos.length) return <div style={{padding:20,color:NOAH_C.ink4}}>Sin datos de planificación aún</div>
  const ctls = todos.map(p=>p.ctl)
  const minC = Math.max(0,Math.min(...ctls)-5), maxC = Math.max(...ctls)+10
  const W=680,H=220,PT=24,PR=20,PB=30,PL=44
  const iW=W-PL-PR, iH=H-PT-PB
  const xs = i => PL+(i/Math.max(todos.length-1,1))*iW
  const ys = v => PT+iH-((v-minC)/(maxC-minC||1))*iH
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
  const pH = hist.map((p,i)=>`${i===0?"M":"L"}${xs(i).toFixed(1)},${ys(p.ctl).toFixed(1)}`).join(" ")
  const pP = proy.map((p,i)=>{const xi=hist.length+i;return `${i===0?"M":"L"}${xs(xi).toFixed(1)},${ys(p.ctl).toFixed(1)}`}).join(" ")
  const xU = hist.length>0?xs(hist.length-1):PL
  const yO = ys(data.ctl_objetivo)
  return (
    <div style={{display:"flex",flexDirection:"column",gap:12}}>
      <div style={{display:"flex",gap:12,flexWrap:"wrap"}}>
        {["A","T","R","TAPER"].map(f=>(
          <div key={f} style={{display:"flex",alignItems:"center",gap:5}}>
            <div style={{width:12,height:12,borderRadius:3,background:COLORES[f]}}/>
            <span style={{fontSize:11,color:NOAH_C.ink3}}>{LABELS[f]}</span>
          </div>
        ))}
      </div>
      <div style={{overflowX:"auto"}}>
        <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{display:"block",maxWidth:"100%"}}>
          {bandas.map((b,i)=>(
            <rect key={i} x={xs(b.xS)} y={PT} width={Math.max(2,xs(b.xE)-xs(b.xS))} height={iH} fill={b.color||COLORES[b.fase]||'#888'} opacity={0.15}/>
          ))}
          {bandas.map((b,i)=>(
            <text key={i} x={(xs(b.xS)+xs(b.xE))/2} y={PT+13} textAnchor="middle" fontSize="11" fill={b.color||COLORES[b.fase]||'#888'} fontWeight="800">{b.fase}</text>
          ))}
          <line x1={PL} y1={yO} x2={W-PR} y2={yO} stroke="#555" strokeWidth="1" strokeDasharray="4,3"/>
          <text x={W-PR-2} y={yO-4} textAnchor="end" fontSize="9" fill="#555">CTL obj {data.ctl_objetivo}</text>
          <line x1={xU} y1={PT} x2={xU} y2={PT+iH} stroke="rgba(255,255,255,0.2)" strokeWidth="1" strokeDasharray="3,3"/>
          <text x={xU+3} y={PT+10} fontSize="9" fill="rgba(255,255,255,0.35)">hoy</text>
          <line x1={xs(todos.length-1)} y1={PT} x2={xs(todos.length-1)} y2={PT+iH} stroke="#10B981" strokeWidth="1.5" opacity={0.8}/>
          <text x={xs(todos.length-1)-3} y={PT+11} textAnchor="end" fontSize="10" fill="#10B981" fontWeight="700">carrera</text>
          {hist.length>1&&<path d={pH} fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="2"/>}
          {proy.length>1&&<path d={pP} fill="none" stroke="white" strokeWidth="2.5" opacity={0.9}/>}
          {hist.length>0&&<circle cx={xs(hist.length-1)} cy={ys(hist[hist.length-1]?.ctl||0)} r={5} fill="#8B5CF6" stroke="white" strokeWidth="2"/>}
          {[minC,Math.round((minC+maxC)/2),maxC].map(v=>(
            <text key={v} x={PL-5} y={ys(v)+4} textAnchor="end" fontSize="9" fill="#666">{Math.round(v)}</text>
          ))}
        </svg>
      </div>
      <div style={{display:"flex",gap:16,flexWrap:"wrap",fontSize:12,color:NOAH_C.ink3}}>
        <span>carrera: <b style={{color:NOAH_C.ink}}>{data.carrera_nombre}</b> {data.carrera_fecha}</span>
        <span>CTL: <b style={{color:NOAH_C.ink}}>{data.ctl_actual}</b> → <b style={{color:NOAH_C.ink}}>{data.ctl_objetivo}</b></span>
        <span>Taper: <b style={{color:"#10B981"}}>-{data.taper_reduccion_pct}%</b></span>
      </div>
    </div>
  )
}



// ══════════════════════════════════════════════════════════════════════════════
// CalendarioMensual — vista mensual estilo TrainingPeaks
// ══════════════════════════════════════════════════════════════════════════════
function CalendarioMensual({ atletaId, presc, dark = true }) {
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
    selBg:  '#E0E7FF', selBorder:NOAH_C.ctl,
    dayBg:  '#FFFFFF', tss:'#F5F3FF', tssBorder:'#DDD6FE',
    tssText:NOAH_C.ctl,
  }

  const E = {
    done:    {bg:dark?'rgba(34,197,94,0.15)':'#DCFCE7',   bd:dark?'rgba(34,197,94,0.35)':'#86EFAC',   dot:NOAH_C.success},
    partial: {bg:dark?'rgba(245,158,11,0.15)':'#FEF9C3',  bd:dark?'rgba(245,158,11,0.35)':'#FDE047',  dot:NOAH_C.warning},
    miss:    {bg:dark?'rgba(239,68,68,0.13)':'#FEE2E2',   bd:dark?'rgba(239,68,68,0.3)':'#FECACA',    dot:NOAH_C.danger},
    planned: {bg:dark?'rgba(99,102,241,0.1)':'#EEF2FF',   bd:dark?'rgba(99,102,241,0.25)':'#C7D2FE',  dot:NOAH_C.ctl},
    none:    {bg:'transparent', bd:'transparent', dot:null},
  }
  const SC = {running:NOAH_C.accent,cycling:NOAH_C.bike,swimming:NOAH_C.success}
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

      {/* Leyenda — compacta, una sola fila */}
      <div style={{padding:'6px 18px',display:'flex',gap:12,flexWrap:'wrap',borderBottom:`1px solid ${T.border}`}}>
        {[[NOAH_C.success,'Hecha'],[NOAH_C.warning,'Editada'],[NOAH_C.danger,'No hecha'],[NOAH_C.ctl,'A futuro']].map(([c,l])=>(
          <div key={l} style={{display:'flex',alignItems:'center',gap:4}}>
            <div style={{width:6,height:6,borderRadius:'50%',background:c}}/>
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
                    color:esHoy?(dark?'#A5B4FC':NOAH_C.ctl):T.text}}>{num}</span>
                  {est.dot&&<div style={{width:6,height:6,borderRadius:'50%',
                    background:est.dot,boxShadow:`0 0 3px ${est.dot}`}}/>}
                </div>
                {acts.slice(0,2).map((a,ai)=>{
                  const c=SC[a.sport]||'#94A3B8'
                  const dk=(a.distance_km>500?a.distance_km/1000:a.distance_km)?.toFixed(1)
                  return <div key={ai} style={{fontSize:8,fontWeight:600,color:c,
                    background:`${c}18`,borderRadius:3,padding:'1px 4px',marginBottom:1,
                    overflow:'hidden',whiteSpace:'nowrap',textOverflow:'ellipsis',
                    display:'flex',alignItems:'center',gap:2}}>
                    <SportIcon sport={a.sport} size={9} color={c}/> {dk}km
                  </div>
                })}
                {acts.length===0&&pres.slice(0,1).map((s,pi)=>(
                  <div key={pi} style={{fontSize:8,color:T.dim,borderRadius:3,padding:'1px 0',
                    display:'flex',alignItems:'center',gap:2}}>
                    <SportIcon sport={s.sport} size={9} color={T.dim}/> {s.nombre?.slice(0,10)}
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
              marginBottom:8,textTransform:'capitalize',display:'flex',alignItems:'center',gap:6}}>
              <CalendarDays size={13}/> {label}
            </div>
            {acts.length===0&&pres.length===0&&<div style={{fontSize:12,color:T.dim}}>Sin actividad</div>}
            {pres.map((s,i)=>(
              <div key={i} style={{padding:'7px 10px',borderRadius:7,marginBottom:5,
                background:dark?'rgba(255,255,255,0.04)':'#FFFFFF',
                border:`1px solid ${T.border}`,display:'flex',gap:8,alignItems:'center'}}>
                <SportIcon sport={s.sport} size={14}/>
                <div style={{flex:1}}>
                  <div style={{fontSize:11,fontWeight:600,color:T.text}}>{s.nombre}</div>
                  <div style={{fontSize:10,color:T.dim}}>{Math.round(s.duracion)}min · TSS {s.tss}</div>
                </div>
                <div style={{padding:'2px 7px',borderRadius:99,fontSize:9,fontWeight:600,
                  background:acts.some(a=>a.sport===s.sport)?(dark?'rgba(52,211,153,0.2)':NOAH_C.successL):(dark?'rgba(248,113,113,0.15)':NOAH_C.dangerL),
                  color:acts.some(a=>a.sport===s.sport)?NOAH_C.success:NOAH_C.danger,
                  display:'flex',alignItems:'center',gap:3}}>
                  {acts.some(a=>a.sport===s.sport)?<><Check size={10}/>Hecha</>:<><XCircle size={10}/>Pendiente</>}
                </div>
              </div>
            ))}
            {acts.map((a,i)=>(
              <div key={i} style={{marginBottom:i<acts.length-1?10:0}}>
                <ActividadCard act={a} sesionPresc={pres.find(s=>s.sport===a.sport)||null} atletaId={atletaId}/>
              </div>
            ))}
          </div>
        )
      })()}
    </div>
  )
}


// ── PMC del atleta — estilo 2026, con carreras integradas ────────────────────
function ModeloBanisterAtleta({ atletaId }) {
  const [data, setData]       = useState(null)
  const [carreras, setCarreras] = useState([])
  const [deporte, setDeporte] = useState('todos')
  const [hover, setHover]     = useState(null)
  const svgRef                = useRef(null)
  const deporteTouchRef        = useRef(null)

  useEffect(() => {
    if (!atletaId) return
    authFetch(`${API}/atletas/${atletaId}/fases`)
      .then(r => r.json()).then(r => {
        setData(r.data)
        if (r.data?.carreras) setCarreras(r.data.carreras)
      }).catch(() => {})
    authFetch(`${API}/atletas/${atletaId}/carreras`)
      .then(r => r.json()).then(r => setCarreras(prev =>
        r.data?.carreras?.length ? r.data.carreras : prev
      )).catch(() => {})
  }, [atletaId])

  if (!data) return (
    <div style={{padding:32,textAlign:'center',color:'rgba(255,255,255,0.3)',fontSize:13}}>
      Calculando proyección...
    </div>
  )

  const deportes = Object.keys(data.deportes || {})
  const esTodos  = deporte === 'todos'
  // En modo "todos" se usa como serie base el deporte con más histórico
  // (igual criterio que el resto de fases/carreras/ejes), y además se
  // superponen las curvas de CTL de cada deporte para poder compararlas.
  const deporteBase = esTodos
    ? deportes.reduce((best, dep) => {
        const len = data.deportes?.[dep]?.hist?.length || 0
        const bestLen = data.deportes?.[best]?.hist?.length || 0
        return len > bestLen ? dep : best
      }, deportes[0])
    : deporte
  const d = data.deportes?.[deporteBase]
  if (!d) return null

  // ── Paleta brillante (prompt Parte 2) ────────────────────────────────────
  const P = {
    ctl:    '#7C6CFF',   // violeta eléctrico
    atl:    '#FF5C7A',   // coral
    tsb:    '#2DE3A7',   // verde menta
    tsb_bg: 'rgba(45,227,167,0.08)',
    fases: {
      A:    'rgba(99,102,241,0.10)',   // violeta
      T:    'rgba(251,191,36,0.10)',   // ámbar
      R:    'rgba(239,68,68,0.10)',    // rojo
      Taper:'rgba(16,185,129,0.10)',  // verde
      'Taper-B':'rgba(251,191,36,0.07)',
      'Taper-C':'rgba(156,163,175,0.06)',
      Recuperacion:'rgba(156,163,175,0.05)',
      Carrera:'rgba(255,255,255,0.04)',
    },
    carreras: { A:'#EF4444', B:'#F59E0B', C:'#6366F1', D:'#6B7280' },
  }

  const SPORT_C = { running:NOAH_C.accent, cycling:NOAH_C.bike, swimming:NOAH_C.success }
  const hist  = d.hist || [], proy = d.proy || []
  const todos = [...hist, ...proy]
  if (!todos.length) return null

  // Series CTL de cada deporte, alineadas por índice para el modo comparación.
  // Se usan tal cual vienen del backend (no se interpola ni se rellena),
  // así que si un deporte tiene menos historial su línea es más corta.
  const seriesPorDeporte = esTodos
    ? deportes.map(dep => {
        const dd = data.deportes?.[dep]
        return { dep, color: SPORT_C[dep] || P.ctl,
          hist: dd?.hist || [], proy: dd?.proy || [] }
      }).filter(s => s.hist.length + s.proy.length > 0)
    : []

  const W=680, H=280, PT=36, PB=44, PL=50, PR=32
  const iW=W-PL-PR, iH=H-PT-PB

  const ctlV = todos.map(p=>p.ctl||0)
  const atlV = todos.map(p=>p.atl||0)
  const tsbV = todos.map(p=>p.tsb||0)
  // En modo comparación, el rango Y debe cubrir también el CTL de los otros
  // deportes — si no, una curva con CTL más alto se saldría del gráfico.
  const ctlVExtra = esTodos
    ? seriesPorDeporte.flatMap(s => [...s.hist, ...s.proy].map(p => p.ctl||0))
    : []
  const maxY = Math.max(...ctlV, ...atlV, ...ctlVExtra)+12
  const minY = Math.min(...tsbV)-10
  const rY   = maxY-minY||1

  const xs = i => PL+(i/Math.max(todos.length-1,1))*iW
  const ys = v => PT+iH-((v-minY)/rY)*iH
  const y0 = ys(0)

  // Curva suavizada con bezier — xsFn permite usar una escala X distinta
  // (necesario para superponer series de otros deportes con distinta
  // cantidad de días de histórico, alineadas por fecha en vez de índice)
  const mkSmooth = (arr, key, off=0, xsFn=xs) => {
    if (arr.length < 2) return ''
    const pts = arr.map((p,i) => [xsFn(i+off), ys(p[key]||0)])
    let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`
    for (let i=1; i<pts.length; i++) {
      const cp1x = pts[i-1][0] + (pts[i][0]-pts[i-1][0])*0.4
      const cp1y = pts[i-1][1]
      const cp2x = pts[i][0] - (pts[i][0]-pts[i-1][0])*0.4
      const cp2y = pts[i][1]
      d += ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${pts[i][0].toFixed(1)},${pts[i][1].toFixed(1)}`
    }
    return d
  }
  const mkArea = (arr, key, off=0) => {
    if (arr.length < 2) return ''
    const path = mkSmooth(arr, key, off)
    const lastX = xs(arr.length-1+off).toFixed(1)
    const firstX = xs(off).toFixed(1)
    return `${path} L${lastX},${y0.toFixed(1)} L${firstX},${y0.toFixed(1)} Z`
  }

  // Bandas de fases (agrupadas) — ahora recorre TODO el rango (histórico +
  // proyección), no solo el futuro. El backend ahora etiqueta cada día
  // histórico con su fase real (A/T/R/Taper) según las fechas del macrociclo
  // vigente, así que se puede ver desde cuándo se estableció el plan hasta
  // el objetivo de carrera, no solo lo que queda por venir. Los días sin
  // fase asignada (anteriores al inicio del macrociclo actual, o sin carrera
  // definida) simplemente no generan banda — quedan sin pintar.
  const bandas = []
  let cur = null
  todos.forEach((p,i) => {
    const faseRaw = p.fase
    const fase = !faseRaw ? null
               : faseRaw.startsWith('Taper') ? 'Taper'
               : faseRaw === 'Recuperacion' ? 'Recuperacion'
               : faseRaw === 'Carrera' ? 'Carrera'
               : faseRaw
    if (fase == null) {
      if (cur) { bandas.push(cur); cur = null }
      return
    }
    if (!cur || cur.fase !== fase) {
      if (cur) bandas.push(cur)
      cur = {fase, xS: i, xE: i}
    } else { cur.xE = i }
  })
  if (cur) bandas.push(cur)

  const step   = (maxY-minY)>80?20:(maxY-minY)>40?10:5
  const yTicks = []
  for(let v=Math.ceil(minY/step)*step; v<=maxY; v+=step) yTicks.push(v)

  const xLabels = todos.reduce((acc,p,i) => {
    if(i%Math.max(1,Math.floor(todos.length/8))===0) acc.push({i, label:(p.f||'').slice(5)})
    return acc
  },[])

  const handleMouse = e => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect) return
    const mx  = (e.clientX-rect.left)*(W/rect.width)
    const idx = Math.max(0, Math.min(todos.length-1, Math.round((mx-PL)/iW*(todos.length-1))))
    setHover({i:idx, x:xs(idx), p:todos[idx]})
  }

  const xHoy    = xs(hist.length-1)
  const actual  = hist[hist.length-1]||{}
  const faseAct = actual.fase || proy[0]?.fase || 'A'
  const faseLabel = faseAct.startsWith('Taper')?'Taper'
    : faseAct==='R'?'Realización':faseAct==='T'?'Transformación':'Acumulación'
  const tsbCol  = (actual.tsb||0)>5?P.tsb:(actual.tsb||0)<-15?P.atl:'#FFB454'
  const sc      = esTodos ? { Icon: BarChart3 } : (SPORT[deporte]||SPORT.running)

  return (
    <div style={{
      borderRadius:0, overflow:'visible',
      background:'transparent',
    }}>
      <style>{`
        @keyframes pmc-pulse { 0%,100%{opacity:1;r:5} 50%{opacity:0.5;r:8} }
        .pmc-hoy-dot { animation: pmc-pulse 2s ease-in-out infinite; }
        @media (prefers-reduced-motion) { .pmc-hoy-dot { animation: none; } }
      `}</style>

      {/* Header glassmorphism */}
      <div style={{
        padding:'14px 20px',
        background:`linear-gradient(90deg,${SPORT_C[deporte]||P.ctl}12,transparent)`,
        backdropFilter:'blur(20px)',
        borderBottom:'1px solid rgba(255,255,255,0.07)',
        display:'flex', alignItems:'center', gap:10, flexWrap:'wrap',
      }}>
        <sc.Icon size={15} color={SPORT_C[deporte]||P.ctl} style={{flexShrink:0}}/>
        <span style={{fontSize:13,fontWeight:800,color:'rgba(255,255,255,0.92)',letterSpacing:-0.3}}>
          Performance Management Chart
        </span>
        <div style={{
          padding:'3px 10px', borderRadius:99, fontSize:10, fontWeight:700,
          background:`rgba(124,108,255,0.15)`, color:P.ctl,
          border:`1px solid rgba(124,108,255,0.3)`,
        }}>
          {faseLabel}
        </div>
      </div>

      {/* Selector de deporte — carrusel 3D: centro grande, laterales chicas/esfumadas */}
      {(() => {
        const opciones = [
          { id:'todos', label:'Todo', Icon:BarChart3, color:P.ctl },
          ...deportes.map(dep => ({
            id:dep, label:dep.charAt(0).toUpperCase()+dep.slice(1),
            Icon:(SPORT[dep]||SPORT.running).Icon, color:SPORT_C[dep]||P.ctl,
          })),
        ]
        const n = opciones.length
        const activeIdx = Math.max(0, opciones.findIndex(o => o.id === deporte))
        const goTo = (i) => setDeporte(opciones[((i%n)+n)%n].id)
        const idxPrev = (activeIdx-1+n)%n
        const idxNext = (activeIdx+1)%n

        const onTouchStart = (e) => { deporteTouchRef.current = e.touches[0].clientX }
        const onTouchEnd = (e) => {
          if (deporteTouchRef.current == null) return
          const dx = e.changedTouches[0].clientX - deporteTouchRef.current
          if (dx > 40) goTo(activeIdx-1)
          else if (dx < -40) goTo(activeIdx+1)
          deporteTouchRef.current = null
        }

        const OpCard = ({ idx, pos }) => {
          const o = opciones[idx]
          const isCenter = pos === 0
          return (
            <div
              key={o.id}
              onClick={() => !isCenter && goTo(idx)}
              onTouchStart={isCenter ? onTouchStart : undefined}
              onTouchEnd={isCenter ? onTouchEnd : undefined}
              style={{
                flexShrink:0, width:isCenter?108:72,
                padding:isCenter?'7px 14px':'6px 6px',
                borderRadius:10,
                border:`1.5px solid ${isCenter?o.color+'80':'rgba(255,255,255,0.08)'}`,
                background:isCenter?`${o.color}1E`:'transparent',
                boxShadow:isCenter?`0 6px 18px -4px ${o.color}40`:'none',
                opacity:isCenter?1:0.4, filter:isCenter?'none':'blur(0.4px)',
                transform:isCenter?'scale(1)':'scale(0.82)',
                transition:'all 0.25s cubic-bezier(.22,.68,0,1.15)',
                display:'flex', alignItems:'center', justifyContent:'center', gap:5,
                cursor:isCenter?'default':'pointer', userSelect:'none',
                touchAction:isCenter?'pan-y':'auto',
              }}
            >
              <o.Icon size={isCenter?13:11} color={isCenter?o.color:'rgba(255,255,255,0.35)'}/>
              {isCenter && <span style={{fontSize:11,fontWeight:700,color:o.color}}>{o.label}</span>}
            </div>
          )
        }

        return (
          <div style={{ padding:'8px 10px', display:'flex', flexDirection:'column', gap:6,
            borderBottom:'1px solid rgba(255,255,255,0.05)' }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:6 }}>
              <button onClick={()=>goTo(activeIdx-1)} aria-label="Deporte anterior" style={{
                width:22, height:22, borderRadius:'50%', flexShrink:0,
                background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)',
                color:'rgba(255,255,255,0.5)', display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <ChevronLeft size={12}/>
              </button>
              <OpCard idx={idxPrev} pos={-1}/>
              <OpCard idx={activeIdx} pos={0}/>
              <OpCard idx={idxNext} pos={1}/>
              <button onClick={()=>goTo(activeIdx+1)} aria-label="Deporte siguiente" style={{
                width:22, height:22, borderRadius:'50%', flexShrink:0,
                background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)',
                color:'rgba(255,255,255,0.5)', display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <ChevronRight size={12}/>
              </button>
            </div>
            <div style={{display:'flex',justifyContent:'center',gap:5}}>
              {opciones.map((o,i) => (
                <button key={o.id} onClick={()=>goTo(i)} title={o.label} style={{
                  width:i===activeIdx?14:5, height:5, borderRadius:99, border:'none', cursor:'pointer',
                  background:i===activeIdx?o.color:'rgba(255,255,255,0.15)',
                  transition:'all 0.25s ease', padding:0,
                }}/>
              ))}
            </div>
          </div>
        )
      })()}

      {/* KPI cards glassmorphism — grid fijo de 3 columnas, siempre en una sola fila */}
      <div style={{padding:'10px 16px',display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:6,
        borderBottom:'1px solid rgba(255,255,255,0.05)'}}>
        {[
          {label:'CTL',sub:'Fitness',  val:actual.ctl?.toFixed(1)||'--', color:P.ctl,   icon:TrendingUp},
          {label:'ATL',sub:'Fatiga',   val:actual.atl?.toFixed(1)||'--', color:P.atl,   icon:Flame},
          {label:'TSB',sub:'Forma',    val:actual.tsb?.toFixed(1)||'--', color:tsbCol,  icon:BatteryFull},
        ].map(m=>(
          <div key={m.label} style={{
            padding:'8px 8px', borderRadius:10,
            background:'rgba(255,255,255,0.03)',
            backdropFilter:'blur(16px)',
            border:`1px solid ${m.color}25`,
            boxShadow:`0 2px 10px ${m.color}10`,
            textAlign:'center',
          }}>
            <div style={{fontSize:8,fontWeight:700,color:'rgba(255,255,255,0.35)',
              textTransform:'uppercase',letterSpacing:1,marginBottom:3,
              display:'flex',alignItems:'center',justifyContent:'center',gap:3}}>
              <m.icon size={9} color={m.color}/> {m.label}
            </div>
            <div style={{fontSize:19,fontWeight:800,color:m.color,
              fontVariantNumeric:'tabular-nums',letterSpacing:-0.5}}>
              {m.val}
            </div>
            <div style={{fontSize:8,color:'rgba(255,255,255,0.3)',marginTop:1}}>{m.sub}</div>
          </div>
        ))}
      </div>

      {/* Gráfico SVG */}
      <div style={{padding:'8px 0 0',position:'relative'}}>
        <svg ref={svgRef} width="100%" viewBox={`0 0 ${W} ${H}`}
          onMouseMove={handleMouse} onMouseLeave={()=>setHover(null)}
          style={{display:'block',cursor:'crosshair'}}>
          <defs>
            {/* Gradientes de área */}
            <linearGradient id={`gCTL_${atletaId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={P.ctl} stopOpacity="0.30"/>
              <stop offset="70%"  stopColor={P.ctl} stopOpacity="0.06"/>
              <stop offset="100%" stopColor={P.ctl} stopOpacity="0.00"/>
            </linearGradient>
            <linearGradient id={`gTSBp_${atletaId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor={P.tsb} stopOpacity="0.25"/>
              <stop offset="100%" stopColor={P.tsb} stopOpacity="0.00"/>
            </linearGradient>
            <linearGradient id={`gTSBn_${atletaId}`} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%"   stopColor={P.atl} stopOpacity="0.18"/>
              <stop offset="100%" stopColor={P.atl} stopOpacity="0.00"/>
            </linearGradient>
            {/* Glow filters */}
            <filter id={`glCTL_${atletaId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <filter id={`glTSB_${atletaId}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="2.5" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
          </defs>

          {/* Fondo del gráfico */}
          <rect x={PL} y={PT} width={iW} height={iH}
            fill="rgba(255,255,255,0.012)" rx={4}/>

          {/* Grid horizontal */}
          {yTicks.map(v=>(
            <line key={v} x1={PL} y1={ys(v)} x2={PL+iW} y2={ys(v)}
              stroke="rgba(255,255,255,0.05)" strokeWidth="1"/>
          ))}

          {/* Zona óptima TSB */}
          <rect x={PL} y={ys(20)} width={iW} height={Math.max(0,ys(5)-ys(20))}
            fill="rgba(45,227,167,0.05)"/>
          <line x1={PL} y1={ys(20)} x2={PL+iW} y2={ys(20)}
            stroke="rgba(45,227,167,0.2)" strokeWidth="1" strokeDasharray="4,4"/>
          <line x1={PL} y1={ys(5)} x2={PL+iW} y2={ys(5)}
            stroke="rgba(45,227,167,0.12)" strokeWidth="1" strokeDasharray="4,4"/>

          {/* Línea de cero */}
          <line x1={PL} y1={y0} x2={PL+iW} y2={y0}
            stroke="rgba(255,255,255,0.12)" strokeWidth="1.5"/>

          {/* Bandas de fases — fondo muy sutil, la identificación real es la
              barra superior de color sólido + el texto, no el área completa */}
          {bandas.map((b,i) => {
            const col = P.fases[b.fase] || 'rgba(255,255,255,0.05)'
            // Color sólido fuerte para barra superior y texto — independiente
            // del alfa tenue del fondo, así no depende de reemplazos de string
            const colFuerte = {
              A:'#818CF8', T:'#FBBF24', R:'#F87171', Taper:'#34D399',
              'Taper-B':'#FBBF24', 'Taper-C':'#9CA3AF', Recuperacion:'#9CA3AF', Carrera:'#fff',
            }[b.fase] || '#9CA3AF'
            const bW  = Math.max(2, xs(b.xE)-xs(b.xS)+iW/Math.max(todos.length-1,1))
            const lbl = b.fase==='A'?'Acumulación':b.fase==='T'?'Transformación'
              :b.fase==='R'?'Realización':b.fase==='Taper'?'Taper'
              :b.fase==='Recuperacion'?'Rec.':''
            return (
              <g key={i}>
                <rect x={xs(b.xS)} y={PT} width={bW} height={iH} fill={col} rx={2}/>
                {b.fase !== 'Recuperacion' && b.fase !== 'Carrera' && (
                  <>
                    <rect x={xs(b.xS)} y={PT} width={bW} height={2.5} fill={colFuerte} opacity={0.85}/>
                    {bW > 50 && (
                      <text x={xs(b.xS)+bW/2} y={PT+14} textAnchor="middle"
                        fontSize="9" fontWeight="800" fill={colFuerte}>
                        {b.fase}
                      </text>
                    )}
                    {bW > 80 && lbl && (
                      <text x={xs(b.xS)+bW/2} y={PT+24} textAnchor="middle"
                        fontSize="7" fill={colFuerte} opacity={0.7}>
                        {lbl}
                      </text>
                    )}
                  </>
                )}
              </g>
            )
          })}

          {/* Marcadores de carreras */}
          {carreras.filter(c=>c.estado!=='cancelada').map((c,i) => {
            if (!c.fecha || !todos.length) return null
            const fechaC = new Date(c.fecha+'T00:00:00')
            const fechaI = new Date((todos[0]?.f||'')+'T00:00:00')
            const fechaF = new Date((todos[todos.length-1]?.f||'')+'T00:00:00')
            const total  = fechaF - fechaI
            if (total <= 0) return null
            const ratio  = (fechaC - fechaI) / total
            if (ratio < 0 || ratio > 1.01) return null
            const xC  = PL + ratio * iW
            const col = P.carreras[c.prioridad] || P.carreras.D
            return (
              <g key={i}>
                <line x1={xC} y1={PT} x2={xC} y2={PT+iH}
                  stroke={col} strokeWidth="1.2" strokeDasharray="3,3" opacity="0.65"/>
                {/* Chip/pill con prioridad */}
                <rect x={xC-10} y={PT-20} width={20} height={14} rx={7}
                  fill={col} opacity="0.9"/>
                <text x={xC} y={PT-10} textAnchor="middle" fontSize="8"
                  fontWeight="800" fill="white">{c.prioridad}</text>
                {/* Nombre abajo */}
                <text x={xC} y={PT+iH+12} textAnchor="middle" fontSize="6.5"
                  fill={col} opacity="0.7">
                  {(c.nombre||'').slice(0,12)}
                </text>
              </g>
            )
          })}

          {/* Áreas relleno */}
          {hist.length>1 && <path d={mkArea(hist,'ctl')}
            fill={`url(#gCTL_${atletaId})`}/>}
          {hist.length>1 && <path
            d={`${mkSmooth(hist.filter(p=>p.tsb>=0), 'tsb')} L${xs(hist.length-1)},${y0} L${xs(0)},${y0} Z`}
            fill={`url(#gTSBp_${atletaId})`}/>}

          {/* Curvas ATL — trazo sólido (sin punteado, para no confundir con CTL/TSB) */}
          {hist.length>1 && <path d={mkSmooth(hist,'atl')} fill="none"
            stroke={P.atl} strokeWidth="2.2" opacity="0.9"/>}
          {proy.length>1 && <path d={mkSmooth(proy,'atl',hist.length)} fill="none"
            stroke={P.atl} strokeWidth="1.6" opacity="0.45" strokeDasharray="4,5"/>}

          {/* Curvas CTL — la más gruesa (línea principal), glow sutil para destacar sin saturar */}
          {hist.length>1 && <path d={mkSmooth(hist,'ctl')} fill="none"
            stroke={P.ctl} strokeWidth="3" filter={`url(#glCTL_${atletaId})`}/>}
          {proy.length>1 && <path d={mkSmooth(proy,'ctl',hist.length)} fill="none"
            stroke={P.ctl} strokeWidth="2" opacity="0.55" strokeDasharray="8,4"/>}

          {/* Modo comparación — CTL de cada deporte superpuesto (sin ATL/TSB individual para no saturar) */}
          {/* Cada serie se alinea por fecha: el último punto histórico de TODOS los
              deportes corresponde a "hoy", así que se escala con su propio largo
              en vez del índice de la serie base — evita desalinear curvas de
              deportes con menos días de histórico. */}
          {esTodos && seriesPorDeporte.map(s => {
            const sTotal = s.hist.length + s.proy.length
            const sXs = i => PL + (i/Math.max(sTotal-1,1)) * iW
            return (
              <g key={s.dep}>
                {s.hist.length>1 && <path d={mkSmooth(s.hist,'ctl',0,sXs)} fill="none"
                  stroke={s.color} strokeWidth="2.2" opacity="0.85"/>}
                {s.proy.length>1 && <path d={mkSmooth(s.proy,'ctl',s.hist.length,sXs)} fill="none"
                  stroke={s.color} strokeWidth="1.6" opacity="0.45" strokeDasharray="6,4"/>}
              </g>
            )
          })}

          {/* Curvas TSB — la más fina (línea secundaria), trazo sólido */}
          {hist.length>1 && <path d={mkSmooth(hist,'tsb')} fill="none"
            stroke={P.tsb} strokeWidth="1.8" opacity="0.95"/>}
          {proy.length>1 && <path d={mkSmooth(proy,'tsb',hist.length)} fill="none"
            stroke={P.tsb} strokeWidth="1.4" opacity="0.5" strokeDasharray="5,4"/>}

          {/* Línea y punto HOY */}
          <line x1={xHoy} y1={PT} x2={xHoy} y2={PT+iH}
            stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" strokeDasharray="3,3"/>
          <circle cx={xHoy} cy={ys(actual.ctl||0)} r={5} className="pmc-hoy-dot"
            fill={P.ctl} stroke="white" strokeWidth="2.5"/>
          <text x={xHoy-5} y={PT+10} textAnchor="end" fontSize="9"
            fill="rgba(255,255,255,0.6)" fontWeight="700">HOY</text>
          <text x={xHoy+5} y={ys(actual.ctl||0)-7} textAnchor="start"
            fontSize="9" fill={P.ctl} fontWeight="700">CTL {actual.ctl?.toFixed(1)}</text>
          <circle cx={xHoy} cy={ys(actual.tsb||0)} r={4}
            fill={tsbCol} stroke="white" strokeWidth="2"/>
          <text x={xHoy+5} y={ys(actual.tsb||0)+12} textAnchor="start"
            fontSize="9" fill={tsbCol} fontWeight="700">TSB {actual.tsb?.toFixed(1)}</text>

          {/* Crosshair + tooltip hover */}
          {hover && (
            <g>
              <line x1={hover.x} y1={PT} x2={hover.x} y2={PT+iH}
                stroke="rgba(255,255,255,0.2)" strokeWidth="1"/>
              <circle cx={hover.x} cy={ys(hover.p.ctl||0)} r={4}
                fill={P.ctl} stroke="white" strokeWidth="2"/>
              <circle cx={hover.x} cy={ys(hover.p.atl||0)} r={3}
                fill={P.atl} stroke="white" strokeWidth="1.5"/>
              <circle cx={hover.x} cy={ys(hover.p.tsb||0)} r={3}
                fill={P.tsb} stroke="white" strokeWidth="1.5"/>
              {/* Tooltip glass */}
              {(() => {
                const tx = hover.x > W*0.65 ? hover.x-145 : hover.x+10
                const ty = PT+4
                const fase = hover.p.fase || ''
                const faseCol = P.fases[fase] ? fase === 'A' ? '#818CF8'
                  : fase === 'T' ? '#FCD34D' : fase === 'R' ? NOAH_C.danger
                  : fase.startsWith('Taper') ? NOAH_C.success : 'rgba(255,255,255,0.5)'
                  : 'rgba(255,255,255,0.5)'
                return (
                  <g>
                    <rect x={tx} y={ty} width={138} height={70} rx={10}
                      fill="rgba(8,9,20,0.92)" stroke="rgba(255,255,255,0.1)" strokeWidth="1"/>
                    <text x={tx+10} y={ty+14} fontSize="9" fill="rgba(255,255,255,0.4)">
                      {hover.p.f} {fase && `· ${fase}`}
                    </text>
                    <text x={tx+10} y={ty+30} fontSize="11" fontWeight="700" fill={P.ctl}>
                      CTL {hover.p.ctl?.toFixed(1)}
                    </text>
                    <text x={tx+70} y={ty+30} fontSize="11" fontWeight="700" fill={P.atl}>
                      ATL {hover.p.atl?.toFixed(1)}
                    </text>
                    <text x={tx+10} y={ty+48} fontSize="11" fontWeight="700"
                      fill={hover.p.tsb>=0?P.tsb:P.atl}>
                      TSB {hover.p.tsb?.toFixed(1)}
                    </text>
                    {hover.p.tss_p && (
                      <text x={tx+70} y={ty+48} fontSize="10" fill="rgba(255,255,255,0.4)">
                        TSS {hover.p.tss_p?.toFixed(0)}
                      </text>
                    )}
                  </g>
                )
              })()}
            </g>
          )}

          {/* Ejes */}
          {yTicks.map(v=>(
            <text key={v} x={PL-6} y={ys(v)+4} textAnchor="end"
              fontSize="9" fill="rgba(255,255,255,0.25)">{v}</text>
          ))}
          {xLabels.map(({i,label})=>(
            <text key={i} x={xs(i)} y={H-PB+14} textAnchor="middle"
              fontSize="8.5" fill="rgba(255,255,255,0.25)">{label}</text>
          ))}
        </svg>
      </div>

      {/* Leyenda */}
      <div style={{
        padding:'8px 20px 14px',
        display:'flex', gap:16, flexWrap:'wrap', alignItems:'center',
        borderTop:'1px solid rgba(255,255,255,0.05)',
      }}>
        {(esTodos
          ? seriesPorDeporte.map(s => ({
              color:s.color,
              label:`CTL ${SPORT[s.dep]?.label || s.dep}`,
              dash:false,
            }))
          : [
              {color:P.ctl,  label:'CTL — Fitness',  dash:false},
              {color:P.atl,  label:'ATL — Fatiga',   dash:true},
              {color:P.tsb,  label:'TSB — Forma',    dash:false},
              {color:'rgba(45,227,167,0.4)', label:'Zona óptima TSB', dash:true},
            ]
        ).map(l=>(
          <div key={l.label} style={{display:'flex',alignItems:'center',gap:5}}>
            <svg width={22} height={8}>
              <line x1={0} y1={4} x2={22} y2={4}
                stroke={l.color} strokeWidth={l.dash?1.5:2.5}
                strokeDasharray={l.dash?'5,3':'none'} opacity="0.9"/>
            </svg>
            <span style={{fontSize:10,color:'rgba(255,255,255,0.4)'}}>{l.label}</span>
          </div>
        ))}
        <span style={{marginLeft:'auto',fontSize:10,color:'rgba(255,255,255,0.2)'}}>
          {hist.length}d hist · {proy.length}d proy · hover para detalle
        </span>
      </div>
    </div>
  )
}




// ── SyncBar — dots de estado bio/actividad ───────────────────────────────────
function SyncBar({ syncStatus, onSyncBio, onSyncAct, bioLoading, actLoading }) {
  const bioDias = syncStatus?.bio_dias_atras
  const actDias = syncStatus?.act_dias_atras
  const Dot = ({ label, esHoy, dias, loading, onClick }) => {
    const color = esHoy ? NOAH_C.success : (dias != null && dias < 2) ? NOAH_C.warning : NOAH_C.danger
    const txt   = esHoy ? 'hoy' : dias < 999 ? `hace ${dias}d` : 'sin datos'
    return (
      <div style={{display:'flex',alignItems:'center',gap:4}}>
        <div style={{width:6,height:6,borderRadius:'50%',background:color,boxShadow:`0 0 5px ${color}`}}/>
        <span style={{fontSize:9,color:'rgba(255,255,255,0.45)'}}>{label}:</span>
        <span style={{fontSize:9,fontWeight:700,color}}>{txt}</span>
        <button onClick={onClick} disabled={loading} style={{
          padding:'1px 6px',borderRadius:3,fontSize:8,fontWeight:700,
          border:`1px solid ${color}40`,background:`${color}12`,
          color:loading?'rgba(255,255,255,0.2)':color,
          cursor:loading?'default':'pointer',
        }}>{loading?'…':'↻'}</button>
      </div>
    )
  }
  return (
    <div style={{display:'flex',alignItems:'center',gap:12,padding:'4px 16px',
      background:'rgba(255,255,255,0.015)',
      borderBottom:'1px solid rgba(255,255,255,0.05)',flexWrap:'wrap'}}>
      <span style={{fontSize:8,color:'rgba(255,255,255,0.25)',fontWeight:600,
        textTransform:'uppercase',letterSpacing:0.8,display:'flex',alignItems:'center',gap:3}}>
        <Satellite size={9}/> sync
      </span>
      <Dot label="Bio" esHoy={syncStatus?.bio_es_hoy} dias={bioDias}
        loading={bioLoading} onClick={onSyncBio}/>
      <Dot label="Actividad" esHoy={syncStatus?.act_es_hoy} dias={actDias}
        loading={actLoading} onClick={onSyncAct}/>
    </div>
  )
}


// ── TorqueWbalBotones — análisis de ciclismo bajo demanda en el atleta ──────
function TorqueWbalBotones({ atletaId, sesionId, ftp = 200, cadenciaOptima = 85 }) {
  const [vista,      setVista]   = useState(null) // null | 'torque' | 'wbal'
  const [data,       setData]    = useState(null)
  const [cargando,   setCargando] = useState(false)

  const cargar = async () => {
    if (data) return  // ya cargado, no volver a pedir
    setCargando(true)
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/sesiones/${sesionId}/torque_wbal`)
      const d = await r.json()
      setData(d.data || d)
    } catch {}
    setCargando(false)
  }

  const toggle = (v) => {
    if (vista === v) { setVista(null); return }
    setVista(v)
    if (!data) cargar()
  }

  const Q_COLOR = { Q1:'#F97316', Q2:'#EF4444', Q3:'#22C55E', Q4:'#3B82F6' }
  const torque_umbral = Math.round((9.549 * ftp) / cadenciaOptima)
  const { samples=[], cuadrantes={}, metricas={} } = data || {}

  const step1 = Math.max(1, Math.floor(samples.length / 1200))
  const scatterData = samples
    .filter((_,i) => i % step1 === 0 && samples[i].cadence > 0)
    .map(s => ({ x: s.cadence, y: s.torque, w: s.wbal_pct }))

  const step2 = Math.max(1, Math.floor(samples.length / 350))
  const lineData = samples
    .filter((_,i) => i % step2 === 0)
    .map(s => ({ t: Math.round(s.ts_s / 60), wbal: s.wbal_pct, torque: s.torque }))

  return (
    <div style={{ padding:'12px 16px', borderBottom:`1px solid ${NOAH_C.border}` }}>
      {/* Botones azules */}
      <div style={{ display:'flex', gap:10, marginBottom: vista ? 14 : 0 }}>
        {[['torque','⚙ Torque'],['wbal',"🔋 W'bal"]].map(([v, label]) => (
          <button key={v} onClick={() => toggle(v)} style={{
            flex:1, padding:'10px 0', borderRadius:10, fontSize:13, fontWeight:700,
            background: vista===v ? '#007AFF' : 'rgba(0,122,255,0.12)',
            color: vista===v ? '#fff' : '#007AFF',
            border:`1.5px solid ${vista===v ? '#007AFF' : 'rgba(0,122,255,0.3)'}`,
            cursor:'pointer',
            boxShadow: vista===v ? '0 4px 12px rgba(0,122,255,0.35)' : 'none',
            transition:'all 0.15s',
          }}>{cargando && !data ? '⏳' : label}</button>
        ))}
      </div>

      {/* Gráfico de cuadrantes */}
      {vista === 'torque' && (
        <div>
          {!data && cargando && (
            <div style={{ textAlign:'center', padding:20, color:NOAH_C.ink3, fontSize:12 }}>
              Calculando Torque...
            </div>
          )}
          {data && scatterData.length > 0 && (
            <>
              {/* Métricas rápidas */}
              <div style={{ display:'flex', gap:8, marginBottom:12, flexWrap:'wrap' }}>
                {[
                  { label:'Q2 (veneno)', value:`${cuadrantes?.Q2??'--'}%`, color:'#EF4444' },
                  { label:'NME', value:metricas?.nme?metricas.nme.toFixed(1):'--', color:'#3B82F6' },
                ].map(({ label, value, color }) => (
                  <div key={label} style={{ flex:1, background:`${color}12`, borderRadius:8,
                    padding:'8px 12px', border:`1px solid ${color}25` }}>
                    <div style={{ fontSize:10, color:NOAH_C.ink3 }}>{label}</div>
                    <div style={{ fontSize:18, fontWeight:800, color }}>{value}</div>
                  </div>
                ))}
              </div>
              <div style={{ fontSize:11, color:NOAH_C.ink3, marginBottom:6 }}>
                Cadencia (RPM) vs Torque (N·m) · {scatterData.length} puntos
              </div>
              <svg width="100%" viewBox="0 0 300 200" style={{ background:'rgba(255,255,255,0.02)', borderRadius:8 }}>
                {scatterData.map((d, i) => {
                  const cx = ((d.x - 40) / 90) * 280 + 10
                  const cy = 190 - ((d.y / (torque_umbral * 2)) * 180)
                  const alta_fuerza = d.y > torque_umbral
                  const alta_cad   = d.x >= cadenciaOptima
                  const q = alta_fuerza && alta_cad ? 'Q1'
                          : alta_fuerza && !alta_cad ? 'Q2'
                          : !alta_fuerza && !alta_cad ? 'Q3' : 'Q4'
                  return <circle key={i} cx={cx} cy={Math.max(5,Math.min(195,cy))} r={2}
                    fill={Q_COLOR[q]} fillOpacity={0.6}/>
                })}
                {/* Líneas de referencia */}
                <line x1={((cadenciaOptima-40)/90)*280+10} y1="0"
                  x2={((cadenciaOptima-40)/90)*280+10} y2="200"
                  stroke="rgba(255,255,255,0.2)" strokeDasharray="3 3"/>
                <line x1="0" y1={190-((torque_umbral/(torque_umbral*2))*180)}
                  x2="300" y2={190-((torque_umbral/(torque_umbral*2))*180)}
                  stroke="rgba(255,255,255,0.2)" strokeDasharray="3 3"/>
                {/* Labels ejes */}
                <text x="5" y="10" fill="rgba(255,255,255,0.3)" fontSize="8">N·m↑</text>
                <text x="260" y="198" fill="rgba(255,255,255,0.3)" fontSize="8">RPM→</text>
              </svg>
              {/* Leyenda */}
              <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:4, marginTop:8 }}>
                {Object.entries({Q1:'Explosivo',Q2:'⚠ Veneno triatlón',Q3:'Recuperación',Q4:'Eficiencia cardio'}).map(([q,desc]) => (
                  <div key={q} style={{ display:'flex', alignItems:'center', gap:5, fontSize:10, color:NOAH_C.ink3 }}>
                    <div style={{ width:7,height:7,borderRadius:'50%',background:Q_COLOR[q],flexShrink:0 }}/>
                    <span><b style={{color:Q_COLOR[q]}}>{q} {cuadrantes?.[q]}%</b> {desc}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {/* Gráfico W'bal */}
      {vista === 'wbal' && (
        <div>
          {!data && cargando && (
            <div style={{ textAlign:'center', padding:20, color:NOAH_C.ink3, fontSize:12 }}>
              Calculando W'bal...
            </div>
          )}
          {data && lineData.length > 0 && (
            <>
              <div style={{ display:'flex', gap:8, marginBottom:12 }}>
                <div style={{ flex:1, background:'rgba(34,197,94,0.1)', borderRadius:8, padding:'8px 12px', border:'1px solid rgba(34,197,94,0.25)' }}>
                  <div style={{ fontSize:10, color:NOAH_C.ink3 }}>W'bal final</div>
                  <div style={{ fontSize:18, fontWeight:800, color:'#22C55E' }}>{metricas?.wbal_final_pct??'--'}%</div>
                </div>
                <div style={{ flex:1, background:'rgba(249,115,22,0.1)', borderRadius:8, padding:'8px 12px', border:'1px solid rgba(249,115,22,0.25)' }}>
                  <div style={{ fontSize:10, color:NOAH_C.ink3 }}>Vaciados críticos</div>
                  <div style={{ fontSize:18, fontWeight:800, color:'#F97316' }}>{metricas?.vaciados_criticos??'--'}</div>
                </div>
              </div>
              <div style={{ fontSize:11, color:NOAH_C.ink3, marginBottom:6 }}>
                Verde = W'bal (%) · Línea punteada = límite crítico 30%
              </div>
              <svg width="100%" viewBox="0 0 300 120" style={{ background:'rgba(255,255,255,0.02)', borderRadius:8 }}>
                {/* Zona crítica */}
                <rect x="0" y={120-(30/100*110)} width="300" height={30/100*110}
                  fill="rgba(239,68,68,0.06)"/>
                {/* Línea crítica */}
                <line x1="0" y1={120-(30/100*110)} x2="300" y2={120-(30/100*110)}
                  stroke="#EF4444" strokeOpacity={0.4} strokeDasharray="4 3"/>
                {/* W'bal path */}
                {lineData.length > 1 && (
                  <polyline
                    points={lineData.map((d, i) =>
                      `${(i / (lineData.length-1)) * 290 + 5},${120 - (Math.max(0,Math.min(100,d.wbal)) / 100) * 110}`
                    ).join(' ')}
                    fill="none" stroke="#22C55E" strokeWidth="2" strokeLinejoin="round"/>
                )}
                <text x="5" y="10" fill="rgba(255,255,255,0.3)" fontSize="8">100%</text>
                <text x="5" y={120-(30/100*110)-3} fill="#EF4444" fontSize="7" opacity="0.6">30%</text>
                <text x="5" y="118" fill="rgba(255,255,255,0.3)" fontSize="8">0%</text>
              </svg>
              {metricas?.vaciados_criticos > 0 && (
                <div style={{ marginTop:8, padding:'8px 12px', borderRadius:8,
                  background:'rgba(239,68,68,0.08)', border:'1px solid rgba(239,68,68,0.2)',
                  fontSize:11, color:'#FCA5A5' }}>
                  ⚡ {metricas.vaciados_criticos} vaciado{metricas.vaciados_criticos>1?'s':''} crítico{metricas.vaciados_criticos>1?'s':''} — 
                  {cuadrantes?.Q2 > 15 ? ` Elevá la cadencia, pasaste ${cuadrantes.Q2}% en Q2.` : ' Revisá los picos de esfuerzo.'}
                </div>
              )}
              {metricas?.vaciados_criticos === 0 && (
                <div style={{ marginTop:8, padding:'8px 12px', borderRadius:8,
                  background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)',
                  fontSize:11, color:'#86EFAC' }}>
                  ✓ Excelente gestión de energía — W' siempre sobre el 30%.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}


export default function AtletaDashboard({ atletaId }) {
  const [atleta, setAtleta]       = useState(null)
  const [estado, setEstado]       = useState(null)
  const [presc, setPresc]         = useState(null)
  const [zonasRun, setZonasRun]   = useState(null)
  const [zonasBike, setZonasBike] = useState(null)
  const [zonasSwim, setZonasSwim] = useState(null)
  const [health, setHealth]       = useState(null)
  const [diag, setDiag]           = useState(null)
  const [tab, setTab]             = useState('hoy')
  const [activeTabIdx, setActiveTabIdx] = useState(0)
  const tabsTrackRef = useRef(null)
  const touchXRef = useRef(null)
  const [subTabZonas, setSubTabZonas] = useState('running')
  const [sesionExp, setSesionExp] = useState(null)
  const [syncLoading, setSyncLoading]   = useState(false)
  const [syncBioLoading, setSyncBioLoad] = useState(false)
  const [syncStatus, setSyncStatus]     = useState(null)
  const [syncResult, setSyncResult]     = useState(null)  // resultado del último sync
  const [metricaIdx, setMetricaIdx] = useState(0) // carrusel de métricas CTL/ATL/TSB/HRV/etc
  const metricaTouchRef = useRef(null)
  const [actReal, setActReal]           = useState(null)  // actividad real del día
  const [ultimaAct, setUltimaAct] = useState(null)

  const id = atletaId || 1

  // Refrescar la prescripción cada vez que el atleta cambia de pestaña —
  // si el coach editó algo mientras el atleta tenía el dashboard abierto,
  // sin esto seguiría viendo los datos viejos hasta recargar toda la página.
  useEffect(() => {
    if (!id) return
    axios.get(`${API}/atletas/${id}/prescripcion`).then(r=>setPresc(r.data.data)).catch(()=>{})
  }, [tab, id])

  // Polling liviano en background — por si el coach edita mientras el
  // atleta sigue en la misma pestaña sin cambiar de sección.
  useEffect(() => {
    if (!id) return
    const interval = setInterval(() => {
      axios.get(`${API}/atletas/${id}/prescripcion`).then(r=>setPresc(r.data.data)).catch(()=>{})
    }, 45000)
    return () => clearInterval(interval)
  }, [id])

  useEffect(() => {
    axios.get(`${API}/atletas/${id}`).then(r => {
      setAtleta(r.data.data)
      const dep = r.data.data?.deporte_ppal||'running'
      // Siempre cargar los 3 deportes — se muestra solo lo que tiene datos
      axios.get(`${API}/atletas/${id}/zonas/running`).then(r2=>setZonasRun(r2.data.data)).catch(()=>{})
      axios.get(`${API}/atletas/${id}/zonas/cycling`).then(r2=>setZonasBike(r2.data.data)).catch(()=>{})
      axios.get(`${API}/atletas/${id}/zonas/swimming`).then(r2=>setZonasSwim(r2.data.data)).catch(()=>{})
    }).catch(()=>{})
    axios.get(`${API}/atletas/${id}/estado`).then(r=>setEstado(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${id}/prescripcion`).then(r=>setPresc(r.data.data)).catch(()=>{})
    // ── Auto-sync al cargar: baja días perdidos en background ──────────────
    axios.get(`${API}/atletas/${id}/sync_status`).then(async r => {
      const st = r.data.data
      setSyncStatus(st)

      const bioDias = st?.bio_dias_atras ?? 999
      const actDias = st?.act_dias_atras ?? 999

      // Si hay datos de más de 1 día atrás → UNA sola llamada de sync
      if (bioDias > 1 || actDias > 1) {
        authFetch(`${API}/atletas/${id}/sincronizar`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ modo: 'todo' })
        })
        .then(r2=>r2.json())
        .then(() => {
          axios.get(`${API}/atletas/${id}/estado`).then(r3=>setEstado(r3.data.data)).catch(()=>{})
          axios.get(`${API}/atletas/${id}/sync_status`).then(r3=>setSyncStatus(r3.data.data)).catch(()=>{})
          axios.get(`${API}/atletas/${id}/prescripcion`).then(r3=>setPresc(r3.data.data)).catch(()=>{})
          axios.get(`${API}/atletas/${id}/ultima_actividad`).then(r3=>setActReal(r3.data.data?.actividad)).catch(()=>{})
        })
        .catch(()=>{})
      }
    }).catch(()=>{})
    axios.get(`${API}/atletas/${id}/ultima_actividad`).then(r=>setActReal(r.data.data?.actividad)).catch(()=>{})
    axios.get(`${API}/atletas/${id}/ultima_actividad`).then(r=>setUltimaAct(r.data.data?.actividad)).catch(()=>{})
    axios.get(`${API}/atletas/${id}/health`).then(r=>setHealth(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${id}/diagnostico`).then(r=>setDiag(r.data.data)).catch(()=>{})
  }, [id])

  const deporte  = atleta?.deporte_ppal||'running'
  const ctl      = estado?.estado?.ctl
  const atl      = estado?.estado?.atl
  const tsb      = estado?.estado?.tsb
  const hrv_ms      = estado?.estado?.hrv_ms
  const sleep       = estado?.estado?.sleep_h
  const recovery    = estado?.estado?.recovery
  const body_battery = estado?.estado?.body_battery
  const stress_avg   = estado?.estado?.stress
  const hr_reposo    = estado?.estado?.hr_reposo
  const tsbColor = tsb>5?NOAH_C.tsbPos:tsb<-15?NOAH_C.tsbNeg:NOAH_C.tsbNeu
  const hoyStr   = new Date().toLocaleDateString('es-AR',{weekday:'long',day:'numeric',month:'long'})
  const ctlData  = (estado?.training||[]).slice(-42).map(d=>({f:d.d?.slice(5),CTL:d.ctl,ATL:d.atl,TSB:d.tsb}))
  const semanas  = diag?.carrera_fecha ? Math.round((new Date(diag.carrera_fecha)-new Date())/(7*24*3600*1000)) : null
  const deporteLabel = deporte==='triatlon'?'Triatlón':SPORT[deporte]?.label||'Running'

  const tabs = [
    {id:'hoy',           label:'Mi Sesión',     icon: Footprints},
    {id:'semana',        label:'Esta Semana',   icon: CalendarDays},
    {id:'metricas',      label:'Métricas',      icon: BarChart3},
    {id:'calendario',    label:'Calendario',    icon: Calendar},
    {id:'periodizacion', label:'Planificación', icon: TrendingUp},
    {id:'zonas',         label:'Mis Zonas',     icon: Target},
    {id:'race',          label:'Race',          icon: Flag},
    {id:'tests',         label:'Tests',         icon: FlaskConical},
  ]
  const zonasSubTabs = [
    {id:'running',  label:'Running',  show: true},
    {id:'cycling',  label:'Ciclismo', show: true},
    {id:'swimming', label:'Natación', show: true},
  ].filter(t => t.show)

  return (
    <div style={{ minHeight:'100vh', background:`
        radial-gradient(circle at 12% -5%, rgba(167,139,250,0.13) 0%, transparent 42%),
        radial-gradient(circle at 88% 8%, rgba(56,189,248,0.10) 0%, transparent 42%),
        radial-gradient(circle at 50% 105%, rgba(52,211,153,0.07) 0%, transparent 50%),
        linear-gradient(145deg, #0A0A0F 0%, #0D0D14 55%, #080810 100%)
      `, fontFamily:'Inter, system-ui, -apple-system, sans-serif' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { background: #0A0F1E !important; }
        button { font-family: inherit; }
        ::-webkit-scrollbar { width: 4px; height: 4px; }
        ::-webkit-scrollbar-track { background: rgba(255,255,255,0.02); }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.10); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.18); }

        /* ── Tab carrusel real — una sola tarjeta activa, transición suave al cambiar ── */
        @keyframes noah-header-in { from{opacity:0;transform:translateY(-8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes noah-tab-pop { from{opacity:0;transform:scale(0.92)} to{opacity:1;transform:scale(1)} }
        .noah-tab-active-card {
          cursor: default;
          animation: noah-tab-pop 0.22s cubic-bezier(.22,.68,0,1.15);
        }
        @keyframes noah-spin-kf { to { transform: rotate(360deg); } }
        .noah-spin { animation: noah-spin-kf 0.9s linear infinite; }

        /* ── Header glow text ── */
        .noah-logo-letter {
          text-shadow: 0 0 20px currentColor, 0 0 40px currentColor;
          animation: noah-header-in 0.6s ease both;
        }
        .noah-athlete-name {
          text-shadow: 0 2px 12px rgba(255,255,255,0.15);
        }
        .noah-sync-btn {
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
          transition: all 0.2s ease;
        }
        .noah-sync-btn:hover {
          background: rgba(255,255,255,0.18) !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 14px rgba(0,0,0,0.3);
        }
      `}</style>

      {/* HEADER estilo Garmin — imagen hero grande (30%), nombre prominente,
          botones azules, logo arriba. Logica de sync identica. */}
      <div style={{ position:'relative', overflow:'hidden', minHeight:'85vh' }}>
        {/* Imagen hero */}
        <div style={{
          position:'absolute', inset:0,
          backgroundImage:'url(/assets/hero_dashboard.png)',
          backgroundSize:'cover',
          backgroundPosition:'center 25%',
          filter:'saturate(1.05)',
        }}/>
        {/* Overlay de abajo hacia arriba — negro abajo, transparente arriba */}
        <div style={{
          position:'absolute', inset:0,
          background:'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.30) 30%, transparent 60%)',
        }}/>
        {/* Contenido */}
        <div style={{ position:'relative', zIndex:1, display:'flex', flexDirection:'column', minHeight:'85vh' }}>
          {/* Logo + logout arriba */}
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', padding:'12px 16px' }}>
            <div style={{ display:'flex', alignItems:'baseline', gap:1 }}>
              {['N','O','A','H'].map((l,i) => (
                <span key={i} className="noah-logo-letter" style={{
                  fontSize:20, fontWeight:900, letterSpacing:4,
                  color: i%2===1 ? NOAH_C.run : '#fff',
                  animationDelay:`${i*0.08}s`,
                }}>{l}</span>
              ))}
            </div>
            <button onClick={() => {
              try {
                const raw = localStorage.getItem('noah_sesion')
                const s = raw ? JSON.parse(raw) : null
                if (s?.token) authFetch(`${API}/logout`, { method:'POST' }).catch(()=>{})
              } catch {}
              localStorage.removeItem('noah_sesion')
              window.location.href = '/login'
            }} title="Cerrar sesión" style={{
              width:28, height:28, borderRadius:'50%', flexShrink:0,
              background:'rgba(255,255,255,0.08)', border:'1px solid rgba(255,255,255,0.15)',
              color:'rgba(255,255,255,0.5)', display:'flex', alignItems:'center', justifyContent:'center',
              cursor:'pointer',
            }}>
              <LogOut size={13}/>
            </button>
          </div>

          {/* Espacio flexible empuja el nombre hacia abajo */}
          <div style={{ flex:1 }}/>

          {/* Nombre + fecha + alerta + botones abajo */}
          <div style={{ padding:'0 16px 16px' }}>
            <div className="noah-athlete-name" style={{
              fontSize:24, fontWeight:800, color:'#fff',
              textShadow:'0 2px 8px rgba(0,0,0,0.7)',
              marginBottom:2,
            }}>
              {atleta?.nombre||'...'}
            </div>
            <div style={{ fontSize:12, color:'rgba(255,255,255,0.55)', marginBottom:12 }}>
              {deporteLabel} · {hoyStr}
            </div>
            {syncStatus?.alerta && (
              <div style={{ fontSize:10, color:'#FCA5A5', background:'rgba(239,68,68,0.12)',
                padding:'4px 10px', borderRadius:7, border:'1px solid rgba(239,68,68,0.2)',
                display:'flex', alignItems:'center', gap:5, width:'fit-content', marginBottom:10 }}>
                <AlertTriangle size={11}/> Sin sync hace {syncStatus.dias_sin_sync}d
              </div>
            )}
            <div style={{ display:'flex', gap:10 }}>
              <button className="noah-sync-btn" onClick={async () => {
                setSyncBioLoad(true); setSyncResult(null)
                try {
                  const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'bio'})
                  const bio = r.data.data
                  const detalles = [bio?.body_battery&&`BB:${bio.body_battery}`,bio?.hr_reposo&&`FC:${bio.hr_reposo}`,bio?.sleep_h&&`Sueño:${bio.sleep_h}h`,bio?.hrv_ms&&`HRV:${bio.hrv_ms}ms`].filter(Boolean).join(' · ')
                  setSyncResult({tipo:'bio', ok:bio?.exito, msg: bio?.exito ? `Biomarcadores actualizados${detalles?' — '+detalles:''}` : 'Sin datos nuevos de Garmin'})
                  axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
                  axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
                } catch { setSyncResult({tipo:'bio', ok:false, msg:'Error al sincronizar'}) }
                setSyncBioLoad(false)
              }} disabled={syncBioLoading} style={{
                flex:1, padding:'11px 16px', borderRadius:10, fontSize:13, fontWeight:700,
                background:'#007AFF', color:'#fff', border:'none', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center', gap:6,
                boxShadow:'0 4px 14px rgba(0,122,255,0.45)',
              }}>
                {syncBioLoading ? <RotateCw size={13} className="noah-spin"/> : <Moon size={13}/>} Sincronizar Bio
              </button>
              <button className="noah-sync-btn" onClick={async () => {
                setSyncLoading(true); setSyncResult(null)
                try {
                  const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'actividad'})
                  const out = r.data.data?.output || ''
                  const nueva = out.includes('nueva') || out.includes('guardado')
                  setSyncResult({tipo:'actividad', ok:r.data.data?.exito, nueva, msg: nueva ? 'Actividad descargada' : 'Sin actividades nuevas'})
                  if (nueva) {
                    axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
                    axios.get(`${API}/atletas/${id}/ultima_actividad`).then(r2=>setActReal(r2.data.data?.actividad)).catch(()=>{})
                    axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
                  }
                } catch { setSyncResult({tipo:'actividad', ok:false, msg:'Error al sincronizar'}) }
                setSyncLoading(false)
              }} disabled={syncLoading} style={{
                flex:1, padding:'11px 16px', borderRadius:10, fontSize:13, fontWeight:700,
                background:'#007AFF', color:'#fff', border:'none', cursor:'pointer',
                display:'flex', alignItems:'center', justifyContent:'center', gap:6,
                boxShadow:'0 4px 14px rgba(0,122,255,0.45)',
              }}>
                {syncLoading ? <RotateCw size={13} className="noah-spin"/> : <Footprints size={13}/>} Actividad
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Dots de estado sync */}
      <SyncBar
        syncStatus={syncStatus}
        onSyncBio={async () => {
          setSyncBioLoad(true); setSyncResult(null)
          try {
            const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'bio'})
            const bio = r.data.data
            const detalles = [bio?.body_battery&&`BB:${bio.body_battery}`, bio?.hr_reposo&&`FC:${bio.hr_reposo}`, bio?.sleep_h&&`Sueño:${bio.sleep_h}h`, bio?.hrv_ms&&`HRV:${bio.hrv_ms}ms`].filter(Boolean).join(' · ')
            setSyncResult({tipo:'bio', ok:bio?.exito, msg: bio?.exito ? `Bio actualizado${detalles?' — '+detalles:''}` : 'Sin datos nuevos'})
            axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
            axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
          } catch { setSyncResult({tipo:'bio', ok:false, msg:'Error'}) }
          setSyncBioLoad(false)
        }}
        onSyncAct={async () => {
          setSyncLoading(true); setSyncResult(null)
          try {
            const r = await axios.post(`${API}/atletas/${id}/sincronizar`, {modo:'actividad'})
            const nueva = (r.data.data?.output||'').includes('nueva')
            setSyncResult({tipo:'actividad', ok:r.data.data?.exito, msg: nueva ? 'Actividad descargada' : 'Sin actividades nuevas'})
            axios.get(`${API}/atletas/${id}/sync_status`).then(r2=>setSyncStatus(r2.data.data)).catch(()=>{})
            if (nueva) axios.get(`${API}/atletas/${id}/estado`).then(r2=>setEstado(r2.data.data)).catch(()=>{})
          } catch { setSyncResult({tipo:'actividad', ok:false, msg:'Error'}) }
          setSyncLoading(false)
        }}
        bioLoading={syncBioLoading}
        actLoading={syncLoading}
      />

      {/* SYNC RESULT */}
      {syncResult && (
        <div style={{
          background: syncResult.ok ? NOAH_C.successL : NOAH_C.dangerL,
          borderBottom: `1px solid ${syncResult.ok ? NOAH_C.success+'30' : NOAH_C.danger+'30'}`,
          padding:'8px 16px', display:'flex', alignItems:'center', gap:10
        }}>
          {syncResult.ok ? <CheckCircle2 size={14} color={NOAH_C.success}/> : <XCircle size={14} color={NOAH_C.danger}/>}
          <span style={{fontSize:12, color: syncResult.ok ? NOAH_C.success : NOAH_C.danger, fontWeight:600}}>
            {syncResult.msg}
          </span>
          {syncResult.nueva && (
            <span style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginLeft:4}}>
              · La actividad aparece en "Mi Sesión"
            </span>
          )}
          <button onClick={()=>setSyncResult(null)}
            style={{marginLeft:'auto',background:'none',border:'none',color:'rgba(255,255,255,0.3)',cursor:'pointer',fontSize:16}}>×</button>
        </div>
      )}

      {/* STATUS BAR — sin bandeja de fondo propia: los botones (HANNA LIFE,
          Objetivo, CTL/ATL/TSB) flotan directo sobre el fondo general de
          la pantalla. Cada boton conserva su propio estilo/sombra. */}
      <div style={{ padding:'14px 16px' }}>

        {/* Fila 1 — bloques especiales: HANNA LIFE + objetivo de carrera, lado a lado */}
        <div style={{ display:'flex', gap:10, marginBottom:10 }}>
          {(() => {
            const hannaColor = {'Óptimo':NOAH_C.success,'Bueno':NOAH_C.info,'Moderado':NOAH_C.warning,'Bajo':'#F97316','Crítico':NOAH_C.danger}[estado?.estado?.hanna_nivel] || '#6B7280'
            return (
              <div style={{
                flex:1, position:'relative', overflow:'hidden',
                background:`linear-gradient(150deg, ${hannaColor}26 0%, ${hannaColor}0A 70%)`,
                borderRadius:13, padding:'12px 14px', textAlign:'center',
                backdropFilter:'blur(16px) saturate(150%)', WebkitBackdropFilter:'blur(16px) saturate(150%)',
                border:`1px solid ${hannaColor}40`,
                boxShadow:`0 10px 30px -8px rgba(0,0,0,0.5), 0 0 28px -8px ${hannaColor}40, inset 0 1px 0 rgba(255,255,255,0.12)`,
              }}>
                <div style={{ position:'absolute', top:0, left:'10%', right:'10%', height:2.5,
                  background:`linear-gradient(90deg, transparent, ${hannaColor}, transparent)`, boxShadow:`0 0 10px ${hannaColor}` }} />
                <div style={{fontSize:9,fontWeight:700,color:'rgba(255,255,255,0.5)',textTransform:'uppercase',letterSpacing:0.8}}>HANNA LIFE</div>
                <div style={{fontSize:26,fontWeight:800,color:hannaColor,textShadow:`0 0 18px ${hannaColor}80, 0 0 4px ${hannaColor}50`,lineHeight:1.15}}>
                  {estado?.estado?.hanna_life?.toFixed(0)||'--'}
                </div>
                <div style={{fontSize:10,color:'rgba(255,255,255,0.55)',fontWeight:600}}>{estado?.estado?.hanna_nivel||'sin datos'}</div>
              </div>
            )
          })()}
          {semanas && (
            <div style={{ flex:1, position:'relative', overflow:'hidden', textAlign:'center', padding:'12px 14px',
              background:`linear-gradient(150deg, ${NOAH_C.run} 0%, #6D28D9 100%)`, borderRadius:13,
              boxShadow:`0 10px 28px -6px ${NOAH_C.run}55, 0 0 24px -4px ${NOAH_C.run}40, inset 0 1px 0 rgba(255,255,255,0.25)` }}>
              <div style={{ position:'absolute', top:0, left:0, right:0, height:'50%',
                background:'linear-gradient(180deg, rgba(255,255,255,0.18), transparent)' }} />
              <div style={{ fontSize:9,fontWeight:700,color:'rgba(255,255,255,0.7)',textTransform:'uppercase',letterSpacing:0.8 }}>Objetivo</div>
              <div style={{ fontSize:24, fontWeight:800, color:'#fff', lineHeight:1.15, textShadow:'0 2px 8px rgba(0,0,0,0.25)' }}>{semanas}<span style={{fontSize:11,fontWeight:600}}> sem</span></div>
              <div style={{ fontSize:9, color:'rgba(255,255,255,0.7)', marginTop:2, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{diag?.carrera}</div>
            </div>
          )}
        </div>

        {/* Fila 2 — métricas en carrusel 3D: una protagonista al centro, el resto chicas y esfumadas a los costados */}
        {(() => {
          const metricas = [
            { id:'ctl', label:'CTL', value:ctl?.toFixed(0), unit:'fitness', color:NOAH_C.ctl },
            { id:'atl', label:'ATL', value:atl?.toFixed(0), unit:'fatiga', color:NOAH_C.atl },
            { id:'tsb', label:'TSB', value:tsb?.toFixed(1), unit:'frescura', color:tsbColor },
            { id:'hrv', label:estado?.estado?.hrv_es_estimado ? 'HRV (est.)' : 'HRV',
              value:hrv_ms ? Math.round(hrv_ms) : '--', unit:'ms', color:NOAH_C.hrv },
            { id:'bb', label:'Body Battery', value:body_battery ? Math.round(body_battery) : '--', unit:'/100',
              color:body_battery>70?NOAH_C.done:body_battery>40?NOAH_C.amber:NOAH_C.miss },
            { id:'sleep', label:'Sueño', value:sleep ? sleep.toFixed(1) : '--', unit:'h', color:NOAH_C.ink3 },
            { id:'stress', label:'Stress', value:stress_avg ? Math.round(stress_avg) : '--', unit:'/100',
              color:stress_avg<25?NOAH_C.done:stress_avg<50?NOAH_C.amber:NOAH_C.miss },
          ]
          const n = metricas.length
          const goTo = (i) => setMetricaIdx(((i%n)+n)%n)
          const idxPrev = (metricaIdx-1+n)%n
          const idxNext = (metricaIdx+1)%n

          const onTouchStart = (e) => { metricaTouchRef.current = e.touches[0].clientX }
          const onTouchEnd = (e) => {
            if (metricaTouchRef.current == null) return
            const dx = e.changedTouches[0].clientX - metricaTouchRef.current
            if (dx > 40) goTo(metricaIdx-1)
            else if (dx < -40) goTo(metricaIdx+1)
            metricaTouchRef.current = null
          }

          const MetCard = ({ idx, pos }) => {
            const m = metricas[idx]
            const isCenter = pos === 0
            return (
              <div
                key={m.id}
                onClick={() => !isCenter && goTo(idx)}
                onTouchStart={isCenter ? onTouchStart : undefined}
                onTouchEnd={isCenter ? onTouchEnd : undefined}
                style={{
                  flex: isCenter ? '1 1 auto' : '0 0 auto',
                  width: isCenter ? undefined : 64,
                  padding: isCenter ? '14px 16px' : '10px 6px',
                  borderRadius: 13,
                  background: isCenter
                    ? `linear-gradient(135deg, ${m.color}22, ${m.color}08)`
                    : 'transparent',
                  border: `1px solid ${isCenter ? m.color+'40' : 'rgba(255,255,255,0.08)'}`,
                  boxShadow: isCenter ? `0 8px 24px -6px ${m.color}30` : 'none',
                  opacity: isCenter ? 1 : 0.4,
                  filter: isCenter ? 'none' : 'blur(0.4px)',
                  transform: isCenter ? 'scale(1)' : 'scale(0.84)',
                  transition: 'all 0.28s cubic-bezier(.22,.68,0,1.15)',
                  textAlign: 'center',
                  cursor: isCenter ? 'default' : 'pointer',
                  userSelect: 'none', touchAction: isCenter ? 'pan-y' : 'auto',
                }}
              >
                <div style={{fontSize:isCenter?9:8,fontWeight:700,
                  color:isCenter?'rgba(255,255,255,0.5)':'rgba(255,255,255,0.3)',
                  textTransform:'uppercase',letterSpacing:0.8,marginBottom:isCenter?5:3,
                  whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                  {m.label}
                </div>
                <div style={{fontSize:isCenter?28:16,fontWeight:800,
                  color:isCenter?m.color:'rgba(255,255,255,0.4)',
                  fontVariantNumeric:'tabular-nums',letterSpacing:-0.5,lineHeight:1}}>
                  {m.value ?? '--'}
                </div>
                {isCenter && <div style={{fontSize:10,color:'rgba(255,255,255,0.35)',marginTop:3}}>{m.unit}</div>}
              </div>
            )
          }

          return (
            <div>
              <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                <button onClick={()=>goTo(metricaIdx-1)} aria-label="Métrica anterior" style={{
                  width:24, height:24, borderRadius:'50%', flexShrink:0,
                  background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)',
                  color:'rgba(255,255,255,0.5)', display:'flex', alignItems:'center', justifyContent:'center',
                  cursor:'pointer',
                }}>
                  <ChevronLeft size={13}/>
                </button>
                <MetCard idx={idxPrev} pos={-1}/>
                <MetCard idx={metricaIdx} pos={0}/>
                <MetCard idx={idxNext} pos={1}/>
                <button onClick={()=>goTo(metricaIdx+1)} aria-label="Métrica siguiente" style={{
                  width:24, height:24, borderRadius:'50%', flexShrink:0,
                  background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)',
                  color:'rgba(255,255,255,0.5)', display:'flex', alignItems:'center', justifyContent:'center',
                  cursor:'pointer',
                }}>
                  <ChevronRight size={13}/>
                </button>
              </div>
              <div style={{display:'flex',justifyContent:'center',gap:5,marginTop:8}}>
                {metricas.map((m,i) => (
                  <button key={m.id} onClick={()=>goTo(i)} title={m.label} style={{
                    width:i===metricaIdx?16:5, height:5, borderRadius:99, border:'none', cursor:'pointer',
                    background:i===metricaIdx?m.color:'rgba(255,255,255,0.15)',
                    transition:'all 0.25s ease', padding:0,
                  }}/>
                ))}
              </div>
            </div>
          )
        })()}
      </div>

      {/* LEYENDA — solo tiene sentido donde se muestran sesiones individuales
          (Mi Sesion / Semana). En Metricas, Planificacion, etc. no aplica. */}
      {(tab === 'hoy' || tab === 'semana') && (
        <div style={{ background:'rgba(255,255,255,0.03)', borderBottom:`1px solid ${NOAH_C.border}`, padding:'7px 16px', display:'flex', gap:14, alignItems:'center', flexWrap:'wrap' }}>
          {['done','miss','partial','planned'].map(k => {
            const e = ESTADO[k]
            const labelCorto = {done:'Hecha', miss:'No hecha', partial:'Editada', planned:'A futuro'}[k]
            return <span key={k} style={{ fontSize:10, color:e.color, fontWeight:600, display:'flex', alignItems:'center', gap:4 }}><span style={{ width:6,height:6,borderRadius:'50%',background:e.color,display:'inline-block' }} />{labelCorto}</span>
          })}
        </div>
      )}

      {/* TABS — carrusel real 3D: centro grande, laterales chicas/borrosas, navegable por swipe/flecha/tap-lateral/dot */}
      {(() => {
        const n = tabs.length
        const goTo = (i) => {
          const next = ((i % n) + n) % n
          setActiveTabIdx(next)
          setTab(tabs[next].id)
        }
        const idxPrev = (activeTabIdx - 1 + n) % n
        const idxNext = (activeTabIdx + 1) % n

        const onTouchStart = (e) => { touchXRef.current = e.touches[0].clientX }
        const onTouchEnd = (e) => {
          if (touchXRef.current == null) return
          const dx = e.changedTouches[0].clientX - touchXRef.current
          if (dx > 40) goTo(activeTabIdx - 1)
          else if (dx < -40) goTo(activeTabIdx + 1)
          touchXRef.current = null
        }

        // Tarjeta — pos: -1 lateral izq, 0 centro activo, 1 lateral der
        const TabCard = ({ idx, pos }) => {
          const t = tabs[idx]
          const isCenter = pos === 0
          return (
            <div
              key={t.id}
              onClick={() => !isCenter && goTo(idx)}
              onTouchStart={isCenter ? onTouchStart : undefined}
              onTouchEnd={isCenter ? onTouchEnd : undefined}
              style={{
                flexShrink: 0,
                width: isCenter ? 168 : 96,
                padding: isCenter ? '12px 18px' : '10px 8px',
                borderRadius: 16,
                border: `1px solid ${isCenter ? NOAH_C.accent+'55' : 'rgba(255,255,255,0.08)'}`,
                background: isCenter
                  ? `linear-gradient(135deg, ${NOAH_C.accent}2A, ${NOAH_C.accent}0D)`
                  : 'transparent',
                boxShadow: isCenter
                  ? `0 14px 36px -10px rgba(0,0,0,0.6), 0 0 28px -6px ${NOAH_C.accent}40, inset 0 1px 0 rgba(255,255,255,0.10)`
                  : 'none',
                opacity: isCenter ? 1 : 0.45,
                filter: isCenter ? 'none' : 'blur(0.5px)',
                transform: isCenter ? 'scale(1) translateY(0)' : 'scale(0.82) translateY(8px)',
                transition: 'all 0.3s cubic-bezier(.22,.68,0,1.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: isCenter?10:6,
                cursor: isCenter ? 'default' : 'pointer',
                userSelect: 'none', touchAction: isCenter ? 'pan-y' : 'auto',
                zIndex: isCenter ? 2 : 1,
              }}
            >
              <t.icon size={isCenter?20:14} color={isCenter?NOAH_C.run:'rgba(255,255,255,0.35)'} strokeWidth={2.1}/>
              {isCenter && (
                <span style={{ fontSize:14, fontWeight:800, color:'#fff', letterSpacing:0.3, whiteSpace:'nowrap' }}>
                  {t.label}
                </span>
              )}
            </div>
          )
        }

        return (
          <div style={{
            background: 'rgba(10,15,30,0.88)',
            backdropFilter: 'blur(24px)',
            WebkitBackdropFilter: 'blur(24px)',
            borderBottom: '1px solid rgba(255,255,255,0.07)',
            position: 'sticky', top: 0, zIndex: 50,
            padding: '14px 10px 12px',
          }}>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
              <button onClick={()=>goTo(activeTabIdx-1)} aria-label="Tab anterior" style={{
                width:28, height:28, borderRadius:'50%', flexShrink:0,
                background:'rgba(255,255,255,0.06)', border:`1px solid ${NOAH_C.border2}`,
                color:NOAH_C.ink2, display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <ChevronLeft size={15}/>
              </button>

              <TabCard idx={idxPrev} pos={-1}/>
              <TabCard idx={activeTabIdx} pos={0}/>
              <TabCard idx={idxNext} pos={1}/>

              <button onClick={()=>goTo(activeTabIdx+1)} aria-label="Tab siguiente" style={{
                width:28, height:28, borderRadius:'50%', flexShrink:0,
                background:'rgba(255,255,255,0.06)', border:`1px solid ${NOAH_C.border2}`,
                color:NOAH_C.ink2, display:'flex', alignItems:'center', justifyContent:'center',
                cursor:'pointer',
              }}>
                <ChevronRight size={15}/>
              </button>
            </div>

            {/* Dots de progreso */}
            <div style={{display:'flex',justifyContent:'center',gap:6,marginTop:10}}>
              {tabs.map((t,i) => (
                <button key={t.id} onClick={()=>goTo(i)} title={t.label} style={{
                  width: i===activeTabIdx ? 20 : 6,
                  height: 6, borderRadius: 99, border: 'none', cursor: 'pointer',
                  background: i===activeTabIdx ? NOAH_C.accent : 'rgba(255,255,255,0.15)',
                  transition: 'all 0.25s ease', padding: 0,
                }}/>
              ))}
            </div>
          </div>
        )
      })()}

      {/* CONTENT */}
      <div style={{ padding:'20px 16px', maxWidth:960, margin:'0 auto' }}>
        {tab==='hoy' && <SesionDelDia atletaId={id} presc={presc} />}
        {tab==='semana' && <SemanaCompleta presc={presc} atletaId={id} sesionExpandida={sesionExp} setSesionExpandida={setSesionExp} />}

        {tab==='calendario' && (
          <CalendarioMensual
            atletaId={id}
            presc={presc}
            dark={true}
          />
        )}
        {tab==='periodizacion' && (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <div style={{ fontSize:16, fontWeight:700, color:NOAH_C.ink, display:'flex', alignItems:'center', gap:8 }}>
              <TrendingUp size={17}/> Planificación A/T/R/Taper
            </div>
            <div style={{ fontSize:13, color:NOAH_C.ink3 }}>
              Tu curva de CTL proyectada hacia la carrera.
            </div>
            <div style={{ background:NOAH_C.cardBg, borderRadius:12, padding:20, border:`1px solid ${NOAH_C.border}` }}>
              <ModeloBanisterAtleta atletaId={id} />
            </div>
          </div>
        )}

        {tab==='metricas' && (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <div style={{background:NOAH_C.cardBg,borderRadius:12,padding:'14px 18px',border:`1px solid ${NOAH_C.border}`}}>
              <HannaLifeGrafico atletaId={id} modo="dark" />

            </div>

            <div style={{ background:NOAH_C.cardBg, borderRadius:12, padding:20, border:`1px solid ${NOAH_C.border}`, boxShadow:'0 1px 3px rgba(0,0,0,0.04)' }}>
              <div style={{ fontSize:11, fontWeight:600, color:NOAH_C.ink3, letterSpacing:0.8, textTransform:'uppercase', marginBottom:14 }}>Forma atlética — 42 días</div>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={ctlData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
                  <XAxis dataKey="f" tick={{ fill:NOAH_C.ink4, fontSize:10 }} />
                  <YAxis tick={{ fill:NOAH_C.ink4, fontSize:10 }} />
                  <Tooltip contentStyle={{ background:'#0F1428', border:`1px solid ${NOAH_C.border2}`, borderRadius:8, fontSize:12, color:NOAH_C.ink }}
                    labelStyle={{ color:NOAH_C.ink2 }} itemStyle={{ color:NOAH_C.ink }}/>
                  <Line type="monotone" dataKey="CTL" stroke={NOAH_C.ctl} dot={false} strokeWidth={2.5} />
                  <Line type="monotone" dataKey="ATL" stroke={NOAH_C.atl} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="TSB" stroke={NOAH_C.tsbPos} dot={false} strokeWidth={1.5} strokeDasharray="4 3" />
                  <ReferenceLine y={0} stroke={NOAH_C.border2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
            <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:14 }}>
              {[{title:'Recuperación',rows:[{label:'CTL — Fitness',value:ctl,max:120,color:NOAH_C.ctl},{label:'Recovery Score',value:recovery,max:100,color:NOAH_C.done,unit:'/100'},{label:'Horas de sueño',value:sleep,max:9,color:NOAH_C.hrv,unit:'h'}]},{title:'Sistema nervioso',rows:[
              {label:'HRV (ms)',value:hrv_ms?Math.round(hrv_ms):null,max:100,color:NOAH_C.hrv,unit:' ms'},
              {label:'Body Battery',value:body_battery?Math.round(body_battery):null,max:100,color:body_battery>70?NOAH_C.done:body_battery>40?NOAH_C.amber:NOAH_C.miss,unit:'/100'},
              {label:'Stress',value:stress_avg?Math.round(stress_avg):null,max:100,color:stress_avg<25?NOAH_C.done:stress_avg<50?NOAH_C.amber:NOAH_C.miss,unit:'/100'},
              {label:'TSB — Frescura',value:Math.max(0,(tsb||0)+30),max:60,color:tsbColor}]}].map(({title,rows})=>(
                <div key={title} style={{ background:NOAH_C.cardBg, borderRadius:12, padding:18, border:`1px solid ${NOAH_C.border}`, boxShadow:'0 1px 3px rgba(0,0,0,0.04)' }}>
                  <div style={{ fontSize:11, fontWeight:600, color:NOAH_C.ink3, letterSpacing:0.8, textTransform:'uppercase', marginBottom:14 }}>{title}</div>
                  {rows.map(r=><ProgressBar key={r.label} {...r} />)}
                  {title==='Sistema nervioso'&&<div style={{ marginTop:8, padding:'10px 12px', background:NOAH_C.cardBg2, borderRadius:8, border:`1px solid ${NOAH_C.border}` }}><div style={{ fontSize:10, color:NOAH_C.ink4, fontWeight:600, textTransform:'uppercase', letterSpacing:1 }}>HANNA LIFE</div><div style={{ fontSize:16, fontWeight:700, color:NOAH_C.run, marginTop:3 }}>{estado?.estado?.hanna_life?.toFixed(0)||'--'} — {estado?.estado?.hanna_nivel||'sin datos'}</div></div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab==='race' && (
        <SeccionRace atletaId={atletaId} modoAtleta={true} />
      )}

      {tab==='tests' && (
        <SeccionTests atletaId={atletaId} modoAtleta={true} />
      )}

      {tab==='zonas' && (
          <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
            {/* Banner adaptativo según TSB actual */}
            {(() => {
              const tsb = estado?.estado?.tsb
              const ctl = estado?.estado?.ctl
              if (tsb == null) return null
              let banner = null
              if (tsb > 10) {
                banner = { color:NOAH_C.success, bg:NOAH_C.successL, border:NOAH_C.success+'40',
                  icon:CheckCircle2, msg:`Forma óptima (TSB ${tsb?.toFixed(1)}) — Podés entrenar en zonas altas con seguridad.` }
              } else if (tsb < -20) {
                banner = { color:NOAH_C.danger, bg:NOAH_C.dangerL, border:NOAH_C.danger+'40',
                  icon:AlertTriangle, msg:`Alta fatiga acumulada (TSB ${tsb?.toFixed(1)}) — Priorizá Z1-Z2. Evitá umbrales y VO2max.` }
              } else if (tsb < -10) {
                banner = { color:NOAH_C.warning, bg:NOAH_C.warningL, border:NOAH_C.warning+'40',
                  icon:Zap, msg:`En carga (TSB ${tsb?.toFixed(1)}) — Tolerás Z3-Z4 pero moderá el volumen en Z5-Z6.` }
              }
              if (!banner) return null
              return (
                <div style={{ padding:'10px 16px', borderRadius:10,
                  background:banner.bg, border:`1px solid ${banner.border}`,
                  display:'flex', alignItems:'center', gap:10 }}>
                  <banner.icon size={20} color={banner.color} style={{flexShrink:0}}/>
                  <div>
                    <div style={{fontSize:12,fontWeight:700,color:banner.color,marginBottom:2}}>
                      Recomendación según tu estado actual
                    </div>
                    <div style={{fontSize:12,color:NOAH_C.ink2}}>{banner.msg}</div>
                  </div>
                </div>
              )
            })()}
            {zonasSubTabs.length>1 && (
              <div style={{ display:'flex', gap:6 }}>
                {zonasSubTabs.map(t => {
                  const sp = SPORT[t.id]
                  const sel = subTabZonas===t.id
                  return (
                    <button key={t.id} onClick={()=>setSubTabZonas(t.id)} style={{ padding:'7px 16px', fontSize:12, fontWeight:sel?600:400, color:sel?sp.color:NOAH_C.ink3, background:sel?sp.light:'transparent', border:`1.5px solid ${sel?sp.color+'44':NOAH_C.border}`, borderRadius:8, cursor:'pointer', display:'flex', alignItems:'center', gap:6 }}>
                      <sp.Icon size={14} color={sp.color} />
                      {t.label}
                    </button>
                  )
                })}
              </div>
            )}
            {subTabZonas==='running' && <div style={{ background:NOAH_C.cardBg, borderRadius:12, padding:20, border:`1px solid ${NOAH_C.border}` }}><div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}><div style={{ display:'flex', alignItems:'center', gap:8 }}><IconRun size={18} color={NOAH_C.run} /><span style={{ fontSize:16, fontWeight:700, color:NOAH_C.ink }}>Zonas Running</span></div><div style={{ fontSize:13, color:NOAH_C.ink3 }}>LTHR <b style={{ color:NOAH_C.run }}>{atleta?.lthr_run}</b> bpm</div></div><ZonasRunningTable zonas={zonasRun} lthr={atleta?.lthr_run} /></div>}
            {subTabZonas==='cycling' && <div style={{ background:NOAH_C.cardBg, borderRadius:12, padding:20, border:`1px solid ${NOAH_C.border}` }}><div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}><div style={{ display:'flex', alignItems:'center', gap:8 }}><IconBike size={18} color={NOAH_C.bike} /><span style={{ fontSize:16, fontWeight:700, color:NOAH_C.ink }}>Zonas Ciclismo</span></div><div style={{ fontSize:13, color:NOAH_C.ink3 }}>FTP <b style={{ color:NOAH_C.bike }}>{zonasBike?.ftp}</b>W</div></div><ZonasCyclingTable zonas={zonasBike} /></div>}
            {subTabZonas==='swimming' && <div style={{ background:NOAH_C.cardBg, borderRadius:12, padding:20, border:`1px solid ${NOAH_C.border}` }}><div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:14 }}><div style={{ display:'flex', alignItems:'center', gap:8 }}><IconSwim size={18} color={NOAH_C.swim} /><span style={{ fontSize:16, fontWeight:700, color:NOAH_C.ink }}>Zonas Natación</span></div><div style={{ fontSize:13, color:NOAH_C.ink3 }}>CSS <b style={{ color:NOAH_C.swim }}>{zonasSwim?.css}</b> min/100m</div></div><ZonasSwimTable zonas={zonasSwim} /></div>}
          </div>
        )}
      </div>
    </div>
  )
}
