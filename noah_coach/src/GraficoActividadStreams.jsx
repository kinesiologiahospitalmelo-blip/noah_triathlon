// ══════════════════════════════════════════════════════════════════════════════
// GraficoActividadStreams.jsx — NOAH
// ══════════════════════════════════════════════════════════════════════════════
import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Clock, Ruler, HeartPulse, Flame, Zap, BarChart3, Scale, Target,
  Ruler as RulerAlt, Footprints, Bike as BikeIcon, Waves, Mountain, RotateCw,
  ClipboardList
} from 'lucide-react'

// API — en la PC/celular de casa (red local) sigue usando el puerto 5000,
// como ya funcionaba. En Vercel (1 sola dirección para front y backend)
// no hay puerto separado: todo entra por /api en el mismo dominio. El
// navegador ya sabe en qué dirección está parado — solo se le pregunta.
const esLocal = window.location.hostname === "localhost" || window.location.hostname.startsWith("192.168.")
const API = esLocal
  ? `http://${window.location.hostname}:5000/api`
  : "/api"

// authFetch — mismo helper que en AtletaDashboard.jsx/App.js. Este archivo
// se había quedado afuera cuando se protegieron los demás fetch() nativos
// con el token de sesión — por eso el endpoint de streams devolvía 401 en
// silencio y el gráfico caía siempre al fallback de laps (muy pocos puntos).
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

// ── Cache de streams a nivel de módulo — persiste entre re-renders ────────────
const _streamsModuleCache = {}
// ── Fetches en vuelo — evita doble request en StrictMode ─────────────────────
const _streamsPending = {}

// ── Paleta de colores NOAH dark ──────────────────────────────────────────────
const D = {
  bg:       'rgba(7,9,18,0.98)',
  bg2:      'rgba(12,14,24,0.95)',
  glass:    'rgba(255,255,255,0.03)',
  border:   'rgba(255,255,255,0.07)',
  border2:  'rgba(255,255,255,0.13)',
  text:     'rgba(255,255,255,0.90)',
  text2:    'rgba(255,255,255,0.50)',
  text3:    'rgba(255,255,255,0.25)',
  hr:    { line: '#8B5CF6', area: 'rgba(139,92,246,0.22)', dot: '#A78BFA' },
  power: { line: '#F59E0B', area: 'rgba(245,158,11,0.18)', dot: '#FCD34D' },
  pace:  { line: '#38BDF8', area: 'rgba(56,189,248,0.18)', dot: '#7DD3FC' },
  cad:   { line: '#34D399', area: 'rgba(52,211,153,0.14)', dot: '#6EE7B7' },
  alt:   { line: 'rgba(156,163,175,0.5)', area: 'rgba(156,163,175,0.08)' },
  lthr:  '#F59E0B',
  zone: {
    Z1: '#94A3B8', Z2: '#22C55E', Z3: '#84CC16',
    Z4: '#F59E0B', Z5: '#F97316', Z6: '#EF4444',
  },
  sport: {
    running:  '#8B5CF6',
    cycling:  '#38BDF8',
    swimming: '#34D399',
  },
}

const fmtTime = s => {
  if (s == null) return '--'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const ss = Math.floor(s % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
    : `${m}:${String(ss).padStart(2,'0')}`
}
const fmtPace = p => {
  if (!p) return '--'
  const m = Math.floor(p)
  const s = Math.round((p - m) * 60)
  return `${m}:${String(s).padStart(2,'0')}`
}
const fmtDist = km => {
  if (!km && km !== 0) return '--'
  const r = km > 500 ? km / 1000 : km
  return r >= 1 ? `${r.toFixed(2)} km` : `${Math.round(r * 1000)} m`
}
const fmtDur = min => {
  if (!min) return '--'
  const h = Math.floor(min / 60)
  const m = Math.round(min % 60)
  return h > 0 ? `${h}h ${m}min` : `${m} min`
}
function getZone(hr, lthr) {
  if (!hr || !lthr) return 'Z1'
  const r = hr / lthr
  return r < 0.82 ? 'Z1' : r < 0.88 ? 'Z2' : r < 0.94 ? 'Z3'
       : r < 1.00 ? 'Z4' : r < 1.06 ? 'Z5' : 'Z6'
}
function bezierPath(points) {
  if (!points || points.length < 2) return ''
  return points.map(([x, y], i) => {
    if (i === 0) return `M${x.toFixed(1)},${y.toFixed(1)}`
    const [px, py] = points[i - 1]
    const cx = (x + px) / 2
    return `C${cx.toFixed(1)},${py.toFixed(1)} ${cx.toFixed(1)},${y.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}
function makeScale(vals, minV, maxV, height, pad, invert = false) {
  const range = maxV - minV || 1
  return v => {
    if (v == null) return null
    const norm = (v - minV) / range
    return invert
      ? pad + norm * height
      : pad + height - norm * height
  }
}

export default function GraficoActividadStreams({
  act, laps, sport, lthr = 162,
  sesionId, atletaId,
  height = 280,
}) {
  const svgRef = useRef(null)
  // Inicializar desde cache si ya existe — evita parpadeo al re-montar
  const _initCache = sesionId && atletaId ? _streamsModuleCache[`${atletaId}_${sesionId}`] : null
  const [streams, setStreams]         = useState(_initCache?.series || null)
  const [streamStats, setStreamStats] = useState(_initCache?.stats  || null)
  const [streamZonas, setStreamZonas] = useState(_initCache?.zonas  || null)
  const [loading, setLoading]         = useState(false)
  const [fuente, setFuente]           = useState(_initCache ? 'cache' : null)
  const [hover, setHover]             = useState(null)
  // Colapsar/expandir el grafico principal para ahorrar espacio -- abierto
  // por defecto, el usuario lo puede cerrar tocando el chevron del header.
  const [chartOpen, setChartOpen]     = useState(true)
  const defaultCanales = sport === 'cycling'
    ? { hr: false, power: true, pace: false, cadence: false, alt: false, temp: false, vert_osc: false, gct: false, stride: false, resp: false }
    : { hr: true,  power: true, pace: true,  cadence: false, alt: false, temp: false, vert_osc: false, gct: false, stride: false, resp: false }
  const [canalesOn, setCanalesOn] = useState(defaultCanales)

  useEffect(() => {
    if (!sesionId || !atletaId) return
    const cacheKey = `${atletaId}_${sesionId}`

    // Ya está en cache — cargar inmediatamente sin fetch
    if (_streamsModuleCache[cacheKey]) {
      const cached = _streamsModuleCache[cacheKey]
      setStreams(cached.series)
      setStreamStats(cached.stats)
      setStreamZonas(cached.zonas)
      setFuente('cache')
      setLoading(false)
      return
    }

    // Ya hay un fetch en vuelo (StrictMode double-mount) — suscribirse al mismo promise
    if (_streamsPending[cacheKey]) {
      setLoading(true)
      _streamsPending[cacheKey].then(data => {
        if (!data) { setLoading(false); return }
        setStreams(data.series)
        setStreamStats(data.stats)
        setStreamZonas(data.zonas)
        setFuente('cache')
        setLoading(false)
      }).catch(() => setLoading(false))
      return
    }

    // Primer fetch real — guardar el promise para que un segundo mount lo reutilice
    setLoading(true)
    const promise = authFetch(`${API}/atletas/${atletaId}/activity_streams?sesion_id=${sesionId}`)
      .then(r => r.json())
      .then(r => {
        if (r.data?.disponible && r.data?.series?.length > 1) {
          const data = { series: r.data.series, stats: r.data.stats, zonas: r.data.zonas }
          _streamsModuleCache[cacheKey] = data
          delete _streamsPending[cacheKey]
          setStreams(data.series)
          setStreamStats(data.stats)
          setStreamZonas(data.zonas)
          setFuente(r.data.fuente)
          setLoading(false)
          return data
        }
        delete _streamsPending[cacheKey]
        setLoading(false)
        return null
      })
      .catch(() => { delete _streamsPending[cacheKey]; setLoading(false); return null })

    _streamsPending[cacheKey] = promise
  }, [sesionId, atletaId])

  const tieneStreams = streams && streams.length > 5
  const tieneLaps   = laps && laps.length > 0
  // usarLaps = modo laps en el gráfico (perfil por vuelta en vez de stream segundo a segundo)
  // Solo tiene sentido mostrar "laps" cuando hay 3+ splits reales que armen un perfil
  // útil. Con 1-2 laps (actividad sin splits, o un solo lap = toda la sesión) los
  // streams reales (cientos de puntos) son siempre más informativos — antes esto
  // forzaba el modo laps igual y con 1 lap se inventaban 2 puntos por interpolación,
  // dejando el gráfico prácticamente vacío.
  const lapsUtilesParaPerfil = tieneLaps && laps.length >= 3
  const usarLaps = lapsUtilesParaPerfil && (sport !== 'cycling' || !tieneStreams)

  const _lapsRaw = tieneLaps
    ? [...laps]
        .filter(l => l && (l.duration_min > 0 || l.distance_km > 0))
        .sort((a,b) => (a.lap_num||a.lap||0) - (b.lap_num||b.lap||0))
    : []

  const _lapsNorm = _lapsRaw.map((l, i) => ({
    t:          _lapsRaw.slice(0,i).reduce((acc,x) => acc + (x.duration_min||0)*60, 0),
    hr:         l.hr_avg && l.hr_avg > 30 && l.hr_avg < 230 ? l.hr_avg : null,
    power:      l.norm_power || l.avg_power || l.watts,  // NP primero para bike
    avg_power:  l.avg_power || l.watts,
    norm_power: l.norm_power,
    max_power:  l.max_power,
    pace:       l.pace && l.pace > 1 && l.pace < 20 ? l.pace : null,
    cadence:    l.cadence || l.cadencia,
    alt:        null,
    dist_km:    l.distance_km,
    avg_speed:  l.avg_speed,
    lap_if:     l.lap_if,
    work_kj:    l.work_kj,
    _lap_num:   l.lap_num || l.lap || i + 1,
    duration_min: l.duration_min,
  }))

  const lapsComoSeries = _lapsNorm.length === 1
    ? [
        { ..._lapsNorm[0], t: 0,
          hr:    _lapsNorm[0].hr    ? _lapsNorm[0].hr    * 0.88 : null,
          pace:  _lapsNorm[0].pace  ? _lapsNorm[0].pace  * 1.05 : null,
          power: _lapsNorm[0].power ? _lapsNorm[0].power * 0.75 : null,
        },
        _lapsNorm[0],
      ]
    : _lapsNorm

  // FIX: antes, mientras los streams todavia cargaban (tieneStreams=false
  // por unos segundos), caia al relleno de laps si habia al menos 1 -- eso
  // causaba que el grafico se viera distinto por 1-2 segundos y despues
  // "cambiara solo" cuando los streams terminaban de llegar. Ahora, mientras
  // esta cargando, no se usa ese relleno -- se espera a que termine.
  const _rawSeries = usarLaps ? lapsComoSeries
    : (tieneStreams ? streams : (loading ? [] : (tieneLaps ? lapsComoSeries : [])))
  const series = _rawSeries.map(s => ({
    ...s,
    pace:  s.pace  != null ? s.pace  : (s.speed_ms && s.speed_ms > 0.3
      ? parseFloat((sport==='swimming' ? 100/(s.speed_ms*60) : 1000/(s.speed_ms*60)).toFixed(3))
      : null),
    power: s.power != null ? s.power : s.power_w,
    alt:   s.alt   != null ? s.alt   : s.altitude_m,
  }))

  const esLaps = usarLaps
  const stats  = streamStats || {}
  const distKm = act?.distance_km > 500 ? act.distance_km / 1000 : act?.distance_km
  const actLthr = lthr

  const hrVals   = series.map(s => s.hr).filter(v => v && v > 40 && v < 250)
  const powVals  = series.map(s => s.power).filter(v => v && v > 0 && v < 3000)
  const paceVals = series.map(s => s.pace).filter(v => v && v > 1.5 && v < 20)
  const altVals  = series.map(s => s.alt).filter(v => v != null)
  const tempVals = series.map(s => s.temp).filter(v => v != null)
  const vertVals = series.map(s => s.vert_osc).filter(v => v != null)
  const gctVals  = series.map(s => s.gct).filter(v => v != null)
  const stridVals= series.map(s => s.stride).filter(v => v != null)
  const respVals = series.map(s => s.resp).filter(v => v != null)

  const hrMin   = hrVals.length  ? Math.max(40, Math.min(...hrVals) - 8)   : actLthr * 0.55
  const hrMax   = hrVals.length  ? Math.min(220, Math.max(...hrVals) + 8)  : actLthr * 1.15
  const powMin  = 0
  const powMax  = powVals.length ? Math.max(...powVals) * 1.05              : 400
  const paceMin = paceVals.length ? Math.min(...paceVals) * 0.97           : 3.5
  const paceMax = paceVals.length ? Math.max(...paceVals) * 1.03           : 8.0
  const altMin  = altVals.length  ? Math.min(...altVals) - 10              : 0
  const altMax  = altVals.length  ? Math.max(...altVals) + 10              : 100

  const W = 720, H = height
  const PT = 22, PB = 34, PL = 52, PR = 52
  const iW = W - PL - PR
  const iH = H - PT - PB
  const n  = series.length

  // Para streams de bike: ts_s es índice secuencial, no tiempo real en segundos
  // Si la sesión tiene duración conocida, escalar al tiempo real
  const durRealS = act?.duration_min ? act.duration_min * 60 : null
  const maxTRaw = series.length > 0 ? (series[n-1].t || (n - 1)) : 1
  // Si los streams son índices (maxTRaw << durReal), escalar a duración real
  const maxT = (durRealS && maxTRaw < durRealS * 0.5) ? durRealS : maxTRaw
  const tScale = (durRealS && maxTRaw < durRealS * 0.5) ? durRealS / maxTRaw : 1.0
  const xs = i => {
    const s = series[i]
    const t = s.t != null ? s.t * tScale : i * tScale
    return PL + (t / maxT) * iW
  }

  const yHR   = makeScale(null, hrMin,   hrMax,   iH, PT)
  const yPow  = makeScale(null, powMin,  powMax,  iH, PT)
  const yPace = makeScale(null, paceMin, paceMax, iH, PT, true)
  const yAlt  = makeScale(null, altMin,  altMax,  iH, PT)

  const makePoints = (getY, getVal, minV, maxV) =>
    series.map((s, i) => {
      const v = getVal(s)
      if (v == null || v < minV || v > maxV) return null
      const y = getY(v)
      return y != null ? [xs(i), y] : null
    }).filter(Boolean)

  const hrPoints   = makePoints(yHR,   s => s.hr,    hrMin,      hrMax)
  const powPoints  = makePoints(yPow,  s => s.power, 0,          3000)
  const pacePoints = makePoints(yPace, s => s.pace,  1.5,        20)
  const altPoints  = makePoints(yAlt,  s => s.alt,   altMin - 50, altMax + 50)

  const hrPath   = bezierPath(hrPoints)
  const powPath  = bezierPath(powPoints)
  const pacePath = bezierPath(pacePoints)
  const altPath  = bezierPath(altPoints)

  const hrAreaPath  = hrPath  && n > 0 ? hrPath  + ` L${xs(n-1)},${PT+iH} L${PL},${PT+iH} Z` : ''
  const altAreaPath = altPath && n > 0 ? altPath + ` L${xs(n-1)},${PT+iH} L${PL},${PT+iH} Z` : ''

  const handleMouse = useCallback(e => {
    const rect = svgRef.current?.getBoundingClientRect()
    if (!rect || n === 0) return
    const mx  = (e.clientX - rect.left) * (W / rect.width)
    const xMx = (mx - PL) / iW
    let best = 0, bestDist = Infinity
    for (let i = 0; i < n; i++) {
      const xNorm = series[i].t != null ? series[i].t / maxT : i / (n - 1)
      const d = Math.abs(xNorm - xMx)
      if (d < bestDist) { bestDist = d; best = i }
    }
    setHover(best)
  }, [series, n, maxT, iW])

  const hrStep  = (hrMax - hrMin) > 60 ? 20 : 10
  const hrTicks = []
  for (let v = Math.ceil(hrMin / hrStep) * hrStep; v <= hrMax; v += hrStep) hrTicks.push(v)

  const durS     = maxT || 0  // ya está en segundos reales
  const xTickMin = Math.max(1, Math.floor(durS / 60 / 8))
  const xTicks   = []
  for (let min = 0; min <= durS / 60; min += xTickMin) xTicks.push(min * 60)

  const hS = hover != null && hover < n ? series[hover] : null
  const hX = hS != null ? xs(hover) : null

  const sportColor = D.sport[sport] || D.sport.running
  const SportIconC = sport === 'cycling' ? BikeIcon : sport === 'swimming' ? Waves : Footprints
  const paceUnit   = sport === 'swimming' ? '/100m' : '/km'

  // FIX: antes el eje izquierdo (principal) estaba hardcodeado a FC siempre.
  // Para running/swimming, si hay pace real y el canal esta activo, Pace pasa
  // a ser el eje principal (izquierda) y FC se mueve a la derecha.
  const mostrarPaceIzq = sport !== 'cycling' && canalesOn.pace && paceVals.length > 0

  const toggleCanal = key => setCanalesOn(prev => ({ ...prev, [key]: !prev[key] }))

  const CANALES = [
    { key: 'hr',       label: 'FC',        color: D.hr.line,    show: hrVals.length > 0 },
    { key: 'power',    label: 'Potencia',  color: D.power.line, show: powVals.length > 0 && sport !== 'swimming' },
    { key: 'pace',     label: sport === 'swimming' ? 'Pace /100m' : 'Pace',
      color: D.pace.line, show: paceVals.length > 0 || !!act?.pace },
    { key: 'cadence',  label: sport === 'cycling' ? 'Cad rpm' : 'Cad spm',
      color: D.cad.line, show: series.some(s => s.cadence) },
    { key: 'alt',      label: 'Altitud',   color: D.alt.line,   show: altVals.length > 0 },
    { key: 'temp',     label: 'Temp °C',   color: '#67E8F9',    show: tempVals.length > 0 },
    { key: 'vert_osc', label: 'Osc.Vert',  color: '#F472B6',    show: vertVals.length > 0 },
    { key: 'gct',      label: 'GCT',       color: '#FB923C',    show: gctVals.length > 0 },
    { key: 'stride',   label: 'Zancada',   color: '#A78BFA',    show: stridVals.length > 0 },
    { key: 'resp',     label: 'Resp',      color: '#67E8F9',    show: respVals.length > 0 },
  ].filter(c => c.show)

  return (
    <div style={{ borderRadius: 0, overflow: 'visible', background: 'transparent' }}>
      {/* HEADER -- sin caja, solo un separador sutil abajo */}
      <div style={{
        padding: '10px 4px 10px',
        borderBottom: `1px solid ${D.border}`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <SportIconC size={20} color={sportColor}/>
          {[
            act?.duration_min && { Icon: Clock, val: fmtDur(act.duration_min), color: D.text2 },
            distKm            && { Icon: Ruler, val: fmtDist(distKm),          color: D.text2 },
            (act?.hr_avg||stats.hr_avg) && { Icon: HeartPulse, val: `${Math.round(act?.hr_avg||stats.hr_avg)} bpm`, color: D.hr.line },
            (act?.hr_max||stats.hr_max) && { Icon: Flame, val: `máx ${Math.round(act?.hr_max||stats.hr_max)}`, color: '#F97316' },
            (act?.np_watts||stats.power_np) && { Icon: Zap, val: `${act?.np_watts||stats.power_np}W NP`, color: D.power.line },
            (act?.potencia_media||stats.power_avg) && { Icon: BarChart3, val: `${Math.round(act?.potencia_media||stats.power_avg)}W avg`, color: '#84CC16' },
            act?.wkg       && { Icon: Scale, val: `${act.wkg.toFixed(2)} w/kg`,      color: '#A78BFA' },
            act?.tss_total && { Icon: Target, val: `TSS ${act.tss_total.toFixed(0)}`,  color: '#38BDF8' },
            (sport==='cycling' && (act?.intensity_factor || (act?.np_watts && (act?.ftp_watts||act?.ftp)))) && {
              Icon: BarChart3,
              val: `IF ${act?.intensity_factor ? act.intensity_factor.toFixed(2) : ((act.np_watts/(act.ftp_watts||act.ftp)).toFixed(2))}`,
              color: '#FCD34D'
            },
            act?.calorias  && { Icon: Flame, val: `${act.calorias} kcal`,             color: '#F97316' },
            (act?.pace&&sport==='running') && { Icon: Footprints, val: fmtPace(act.pace)+'/km', color: sportColor },
          ].filter(Boolean).map((m, i) => (
            <div key={i} style={{
              display:'flex', alignItems:'center', gap:5,
              padding:'3px 10px', borderRadius:99, fontSize:11, fontWeight:600,
              background: D.glass, border:`1px solid ${D.border}`, color: m.color,
            }}>
              <m.Icon size={12} color={m.color}/>
              <span style={{ color: D.text }}>{m.val}</span>
            </div>
          ))}
          <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:8 }}>
            {loading && (
              <div style={{ fontSize:10, color:D.text3, display:'flex', alignItems:'center', gap:4 }}>
                <div style={{ width:6, height:6, borderRadius:'50%', background:'#38BDF8' }}/>
                Cargando streams...
              </div>
            )}
            {fuente === 'garmin_api' && !loading && (
              <div style={{ fontSize:9, padding:'2px 7px', borderRadius:4,
                background:'rgba(52,211,153,0.12)', color:'#34D399',
                border:'1px solid rgba(52,211,153,0.25)' }}>GARMIN LIVE</div>
            )}
            {fuente === 'db_cache' && (
              <div style={{ fontSize:9, padding:'2px 7px', borderRadius:4,
                background:D.glass, color:D.text3, border:`1px solid ${D.border}` }}>CACHE</div>
            )}
            {esLaps && (
              <div style={{ fontSize:9, padding:'2px 7px', borderRadius:4,
                background:D.glass, color:D.text3, border:`1px solid ${D.border}` }}>
                {laps.length} LAPS
              </div>
            )}
            {series.length >= 1 && (
              <button onClick={() => setChartOpen(o => !o)} title={chartOpen ? 'Ocultar gráfico' : 'Mostrar gráfico'} style={{
                background:'transparent', border:`1px solid ${D.border}`, borderRadius:7,
                padding:'3px 9px', cursor:'pointer', fontSize:11, color:D.text3,
                transition:'transform 0.2s', transform: chartOpen ? 'none' : 'rotate(180deg)',
              }}>▾</button>
            )}
          </div>
        </div>
        {hS && (
          <div style={{
            marginTop:8, display:'flex', gap:12, alignItems:'center',
            padding:'5px 12px', borderRadius:8, fontSize:11,
            background:'rgba(255,255,255,0.05)', border:`1px solid ${D.border2}`,
          }}>
            <span style={{ color:D.text3, fontSize:10 }}>{fmtTime(hS.t)}</span>
            {hS.hr && (
              <span style={{ color:D.zone[getZone(hS.hr,actLthr)], fontWeight:700, display:'flex', alignItems:'center', gap:3 }}>
                <HeartPulse size={12}/> {Math.round(hS.hr)} bpm
                <span style={{ color:D.text3, fontWeight:400, marginLeft:4, fontSize:9 }}>
                  {getZone(hS.hr,actLthr)}
                </span>
              </span>
            )}
            {hS.power   && <span style={{ color:D.power.dot, fontWeight:700, display:'flex', alignItems:'center', gap:3 }}><Zap size={12}/> {Math.round(hS.power)}W</span>}
            {hS.pace    && <span style={{ color:D.pace.dot,  fontWeight:700, display:'flex', alignItems:'center', gap:3 }}><Footprints size={12}/> {fmtPace(hS.pace)}{paceUnit}</span>}
            {hS.cadence && <span style={{ color:D.cad.dot,   fontWeight:600, display:'flex', alignItems:'center', gap:3 }}><RotateCw size={11}/> {Math.round(hS.cadence)}</span>}
            {hS.alt     && <span style={{ color:D.text3,     fontSize:10, display:'flex', alignItems:'center', gap:3 }}><Mountain size={11}/> {Math.round(hS.alt)}m</span>}
            {hS.dist_km != null && (
              <span style={{ color:D.text3, fontSize:10, marginLeft:'auto' }}>{fmtDist(hS.dist_km)}</span>
            )}
            {/* Datos del lap activo para bike */}
            {sport === 'cycling' && tieneLaps && (() => {
              const totalDurS = _lapsNorm.reduce((a,l)=>a+(l.duration_min||0)*60,0)
              const scaleT = totalDurS > 0 ? maxT/totalDurS : 1
              const tCursor = hS.t * tScale
              const lapActivo = _lapsNorm.find((l,i)=>{
                const t1 = l.t * scaleT
                const t2 = _lapsNorm[i+1] ? _lapsNorm[i+1].t * scaleT : maxT
                return tCursor >= t1 && tCursor < t2
              })
              if (!lapActivo) return null
              const npLap = lapActivo.norm_power || lapActivo.power || lapActivo.avg_power
              const ftp   = act?.ftp_watts || act?.ftp
              const ifLap = ftp && npLap ? (npLap/ftp).toFixed(2) : null
              return (
                <span style={{
                  marginLeft:8, padding:'2px 8px', borderRadius:6,
                  background:'rgba(245,158,11,0.15)',
                  border:'1px solid rgba(245,158,11,0.3)',
                  fontSize:10, color:'#F59E0B', fontWeight:700,
                }}>
                  Lap {lapActivo._lap_num}
                  {npLap ? ` · ${Math.round(npLap)}W` : ''}
                  {ifLap ? ` · IF ${ifLap}` : ''}
                  {lapActivo.duration_min ? ` · ${fmtDur(lapActivo.duration_min)}` : ''}
                </span>
              )
            })()}
          </div>
        )}
      </div>

      {/* SELECTOR CANALES */}
      {chartOpen && series.length >= 1 && CANALES.length > 1 && (
        <div style={{
          padding:'8px 16px 8px', display:'flex', gap:6, alignItems:'center',
          borderBottom:`1px solid ${D.border}`, flexWrap:'wrap',
        }}>
          <span style={{ fontSize:9, color:D.text3, textTransform:'uppercase',
            letterSpacing:1, marginRight:2 }}>Canales</span>
          <div style={{ display:'flex', gap:6, flexWrap:'wrap', flex:1 }}>
            {CANALES.map(c => (
              <button key={c.key} onClick={() => toggleCanal(c.key)} style={{
                padding:'4px 11px', borderRadius:99, fontSize:10, fontWeight:600,
                cursor:'pointer',
                border:`1px solid ${canalesOn[c.key] ? c.color+'60' : D.border}`,
                background: canalesOn[c.key] ? `${c.color}18` : 'transparent',
                color: canalesOn[c.key] ? c.color : D.text3,
                transition:'all 0.15s',
              }}>{c.label}</button>
            ))}
          </div>
        </div>
      )}

      {/* SVG -- width:'100%' + height:'auto' (en vez de solo maxWidth:'100%')
          es el fix real: sin height:'auto' el navegador mantenia la altura
          fija en mobile y el grafico quedaba "encajonado" sin usar el ancho
          completo (letterboxing por el viewBox). */}
      {chartOpen && series.length >= 1 ? (
        <svg ref={svgRef} width={W} height={H} viewBox={`0 0 ${W} ${H}`}
          style={{ display:'block', width:'100%', height:'auto', cursor:'crosshair' }}
          onMouseMove={handleMouse} onMouseLeave={() => setHover(null)}>
          <defs>
            <linearGradient id={`gHR_${sesionId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#8B5CF6" stopOpacity="0.22"/>
              <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0.01"/>
            </linearGradient>
            <linearGradient id={`gPow_${sesionId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="#F59E0B" stopOpacity="0.15"/>
              <stop offset="100%" stopColor="#F59E0B" stopOpacity="0.01"/>
            </linearGradient>
            <linearGradient id={`gAlt_${sesionId}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stopColor="rgba(156,163,175,0.25)" stopOpacity="1"/>
              <stop offset="100%" stopColor="rgba(156,163,175,0)"    stopOpacity="1"/>
            </linearGradient>
            <clipPath id={`clip_${sesionId}`}>
              <rect x={PL} y={PT} width={iW} height={iH}/>
            </clipPath>
          </defs>

          {/* Zonas HR fondo */}
          {[
            { z:'Z6', min:actLthr*1.06, max:hrMax,          c:'#EF444408' },
            { z:'Z5', min:actLthr*1.00, max:actLthr*1.06,   c:'#F9731606' },
            { z:'Z4', min:actLthr*0.94, max:actLthr*1.00,   c:'#F59E0B06' },
            { z:'Z3', min:actLthr*0.88, max:actLthr*0.94,   c:'#84CC1604' },
            { z:'Z2', min:actLthr*0.82, max:actLthr*0.88,   c:'#22C55E04' },
            { z:'Z1', min:hrMin,        max:actLthr*0.82,   c:'rgba(148,163,184,0.03)' },
          ].map(({ z, min, max, c }) => {
            const y1 = yHR(Math.min(max, hrMax))
            const y2 = yHR(Math.max(min, hrMin))
            if (y1 >= y2) return null
            return <rect key={z} x={PL} y={y1} width={iW} height={y2-y1} fill={c}/>
          })}

          {/* Grid */}
          {hrTicks.map(v => (
            <line key={v} x1={PL} y1={yHR(v)} x2={W-PR} y2={yHR(v)}
              stroke="rgba(255,255,255,0.04)" strokeWidth="1"/>
          ))}
          {xTicks.slice(1).map(t => {
            const x = PL + (t/maxT)*iW
            return <line key={t} x1={x} y1={PT} x2={x} y2={PT+iH}
              stroke="rgba(255,255,255,0.03)" strokeWidth="1"/>
          })}

          {/* Altitud */}
          {canalesOn.alt && altAreaPath && (
            <path d={altAreaPath} fill={`url(#gAlt_${sesionId})`} clipPath={`url(#clip_${sesionId})`}/>
          )}
          {canalesOn.alt && altPath && (
            <path d={altPath} fill="none" stroke={D.alt.line} strokeWidth="1.5"
              clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* Potencia área */}
          {canalesOn.power && powPath && sport !== 'swimming' && (
            <path d={powPath + (n>0?` L${xs(n-1)},${PT+iH} L${PL},${PT+iH} Z`:'')}
              fill={`url(#gPow_${sesionId})`} clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* HR área */}
          {canalesOn.hr && hrAreaPath && (
            <path d={hrAreaPath} fill={`url(#gHR_${sesionId})`} clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* LTHR */}
          {actLthr >= hrMin && actLthr <= hrMax && canalesOn.hr && (
            <>
              <line x1={PL} y1={yHR(actLthr)} x2={W-PR} y2={yHR(actLthr)}
                stroke={D.lthr} strokeWidth="1.5" strokeDasharray="8,5" opacity="0.65"/>
              <text x={PL-5} y={yHR(actLthr)+4} textAnchor="end"
                fontSize="9" fill={D.lthr} opacity="0.8">LTHR</text>
            </>
          )}

          {/* Cadencia */}
          {canalesOn.cadence && (
            <path d={bezierPath(
              series.map((s,i) => s.cadence ? [xs(i), PT+iH-((s.cadence-0)/300)*iH] : null).filter(Boolean)
            )} fill="none" stroke={D.cad.line} strokeWidth="1.5"
              strokeDasharray="3,2" opacity="0.7" clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* Pace */}
          {canalesOn.pace && pacePath && (
            <path d={pacePath} fill="none" stroke={D.pace.line} strokeWidth="3"
              strokeDasharray="6,3" clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* Potencia línea */}
          {canalesOn.power && powPath && sport !== 'swimming' && (
            <path d={powPath} fill="none" stroke={D.power.line} strokeWidth="3"
              clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* HR línea */}
          {canalesOn.hr && hrPath && (
            <path d={hrPath} fill="none" stroke={D.hr.line} strokeWidth="3.5"
              clipPath={`url(#clip_${sesionId})`}/>
          )}

          {/* Bloques de laps */}
          {esLaps && _lapsNorm.length > 1 && (() => {
            const lapPaces = _lapsNorm.map(l => l.pace).filter(Boolean)
            const pMin = lapPaces.length ? Math.min(...lapPaces) : 3
            const pMax = lapPaces.length ? Math.max(...lapPaces) : 8
            const pRange = pMax - pMin || 1
            const yPaceBlock = p => PT + iH - ((pMax - p) / pRange) * iH * 0.6
            const blockBase  = PT + iH
            return _lapsNorm.map((lap, i) => {
              const nextLap = _lapsNorm[i+1]
              const x1  = PL + (lap.t / Math.max(maxT,1)) * iW
              const x2  = nextLap ? PL + (nextLap.t / Math.max(maxT,1)) * iW : PL + iW
              const w   = Math.max(2, x2 - x1 - 1)
              const z   = lap.hr ? getZone(lap.hr, actLthr) : 'Z2'
              const col = D.zone[z] || '#6366F1'
              const paceY  = lap.pace ? yPaceBlock(lap.pace) : PT + iH * 0.3
              const blockH = blockBase - paceY
              const isHov  = hover === i
              return (
                <g key={i}>
                  <rect x={x1} y={paceY} width={w} height={Math.max(4,blockH)} rx={3}
                    fill={col} opacity={isHov ? 0.35 : 0.18}/>
                  <rect x={x1} y={paceY} width={w} height={3} rx={1}
                    fill={col} opacity={isHov ? 0.9 : 0.6}/>
                  <line x1={x2} y1={PT} x2={x2} y2={PT+iH}
                    stroke={col} strokeWidth="0.5" opacity="0.3" strokeDasharray="2,3"/>
                  {w > 18 && (
                    <text x={x1+w/2} y={PT+iH-4} textAnchor="middle"
                      fontSize="8" fill={col} opacity={isHov?1:0.6} fontWeight="600">
                      {lap._lap_num || i+1}
                    </text>
                  )}
                  {w > 28 && lap.pace && (
                    <text x={x1+w/2} y={Math.max(paceY-4,PT+10)} textAnchor="middle"
                      fontSize="8" fill={col} opacity={isHov?0.9:0.5}>
                      {fmtPace(lap.pace)}
                    </text>
                  )}
                </g>
              )
            })
          })()}

          {/* Bloques de laps para BIKE superpuestos sobre streams */}
          {sport === 'cycling' && !esLaps && tieneLaps && _lapsNorm.length > 1 && (() => {
            // Calcular posición temporal de cada lap en el gráfico de streams
            const totalDurS = _lapsNorm.reduce((acc,l) => acc + (l.duration_min||0)*60, 0)
            const scaleT = totalDurS > 0 ? maxT / totalDurS : 1

            const blockBase = PT + iH
            return _lapsNorm.map((lap, i) => {
              const nextLap = _lapsNorm[i+1]
              const t1 = lap.t * scaleT
              const t2 = nextLap ? nextLap.t * scaleT : maxT
              const x1 = PL + (t1 / Math.max(maxT,1)) * iW
              const x2 = PL + (t2 / Math.max(maxT,1)) * iW
              const w  = Math.max(2, x2 - x1 - 1)

              // Potencia real del lap desde streams
              const samplesInLap = series.filter(s => {
                const st = s.t * tScale
                return st >= t1 && st < t2 && s.power > 0
              })
              const lapPow = samplesInLap.length > 0
                ? Math.round(samplesInLap.reduce((a,s)=>a+s.power,0)/samplesInLap.length)
                : 0

              // Color por zona de potencia
              // Si hay FTP: zonas relativas. Si no: zonas absolutas por watts
              const ftp = act?.ftp_watts || act?.ftp
              const ifLap = ftp && lapPow ? lapPow/ftp : null
              const col = ifLap != null
                // Con FTP — zonas relativas
                ? (ifLap < 0.55 ? '#94A3B8'    // Z1 recovery
                  : ifLap < 0.75 ? '#22C55E'   // Z2 endurance
                  : ifLap < 0.87 ? '#84CC16'   // Z3 tempo
                  : ifLap < 0.95 ? '#F59E0B'   // Z4 threshold
                  : ifLap < 1.05 ? '#F97316'   // Z5 VO2max
                  : '#EF4444')                 // Z6 anaerobic
                // Sin FTP — zonas absolutas por watts (estimado para atleta recreativo)
                : (lapPow < 100 ? '#94A3B8'    // Z1
                  : lapPow < 150 ? '#22C55E'   // Z2
                  : lapPow < 185 ? '#84CC16'   // Z3
                  : lapPow < 210 ? '#F59E0B'   // Z4
                  : lapPow < 240 ? '#F97316'   // Z5
                  : '#EF4444')                 // Z6

              // Altura desde potencia del lap — mismo patrón que run con pace
              const powY  = lapPow > 0 ? yPow(lapPow) : PT + iH * 0.4
              const blockH = blockBase - powY
              const isHov = hover != null && series[hover] &&
                series[hover].t * tScale >= t1 && series[hover].t * tScale < t2

              return (
                <g key={i}>
                  <rect x={x1} y={powY} width={w} height={Math.max(4,blockH)} rx={3}
                    fill={col} opacity={isHov ? 0.35 : 0.18}/>
                  <rect x={x1} y={powY} width={w} height={3} rx={1}
                    fill={col} opacity={isHov ? 0.9 : 0.6}/>
                  <line x1={x2} y1={PT} x2={x2} y2={PT+iH}
                    stroke={col} strokeWidth="0.5" opacity="0.3" strokeDasharray="2,3"/>
                  {w > 14 && (
                    <text x={x1+w/2} y={PT+iH-5} textAnchor="middle"
                      fontSize="8" fill={col} opacity={isHov?1:0.6} fontWeight="700">
                      {lap._lap_num||i+1}
                    </text>
                  )}
                  {w > 28 && lapPow > 0 && (
                    <text x={x1+w/2} y={Math.max(powY-4,PT+10)} textAnchor="middle"
                      fontSize="8" fill={col} opacity={isHov?0.9:0.5} fontWeight="600">
                      {lapPow}W
                    </text>
                  )}
                </g>
              )
            })
          })()}

          {/* Puntos HR laps */}
          {esLaps && canalesOn.hr && hrPoints.map(([x,y], i) => {
            const s = series[i]
            if (!s?.hr) return null
            const z = getZone(s.hr, actLthr)
            return (
              <circle key={i} cx={x} cy={y} r={hover===i ? 7 : 4}
                fill={D.zone[z]}
                stroke={hover===i ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.2)'}
                strokeWidth={hover===i ? 2 : 1}/>
            )
          })}

          {/* Hover */}
          {hover != null && hX != null && (
            <>
              <line x1={hX} y1={PT} x2={hX} y2={PT+iH}
                stroke="rgba(255,255,255,0.2)" strokeWidth="1"/>
              {hS?.hr    != null && canalesOn.hr    && yHR(hS.hr)     != null &&
                <circle cx={hX} cy={yHR(hS.hr)}     r={5} fill={D.hr.dot}    stroke={D.bg} strokeWidth="2"/>}
              {hS?.power != null && canalesOn.power && yPow(hS.power)  != null &&
                <circle cx={hX} cy={yPow(hS.power)}  r={4} fill={D.power.dot} stroke={D.bg} strokeWidth="2"/>}
              {hS?.pace  != null && canalesOn.pace  && yPace(hS.pace)  != null &&
                <circle cx={hX} cy={yPace(hS.pace)}  r={4} fill={D.pace.dot}  stroke={D.bg} strokeWidth="2"/>}
            </>
          )}

          {/* Eje Y izquierdo -- Pace si mostrarPaceIzq, sino FC (como antes) */}
          {mostrarPaceIzq ? (
            <>
              {[paceMin, (paceMin+paceMax)/2, paceMax].map(v => (
                <text key={v} x={PL-7} y={yPace(v)+4} textAnchor="end"
                  fontSize="9" fill={D.text3}>{fmtPace(v)}</text>
              ))}
              <text x={14} y={H/2} textAnchor="middle" fontSize="9"
                fill="rgba(56,189,248,0.55)" transform={`rotate(-90,14,${H/2})`}>Pace {paceUnit}</text>
            </>
          ) : (
            <>
              {hrTicks.map(v => (
                <text key={v} x={PL-7} y={yHR(v)+4} textAnchor="end"
                  fontSize="9" fill={D.text3}>{v}</text>
              ))}
              <text x={14} y={H/2} textAnchor="middle" fontSize="9"
                fill="rgba(139,92,246,0.5)" transform={`rotate(-90,14,${H/2})`}>FC bpm</text>
            </>
          )}

          {/* Eje Y derecho -- FC si mostrarPaceIzq movio FC ahi, sino Potencia/Pace como antes */}
          {mostrarPaceIzq ? (
            <>
              {hrTicks.map(v => (
                <text key={v} x={W-PR+7} y={yHR(v)+4} textAnchor="start"
                  fontSize="9" fill="rgba(139,92,246,0.4)">{v}</text>
              ))}
              <text x={W-12} y={H/2} textAnchor="middle" fontSize="9"
                fill="rgba(139,92,246,0.4)"
                transform={`rotate(90,${W-12},${H/2})`}>FC bpm</text>
            </>
          ) : (
            <>
              {canalesOn.power && powVals.length > 0 && sport !== 'swimming' && (
                <>
                  {[0, Math.round(powMax*0.5), Math.round(powMax)].map(v => (
                    <text key={v} x={W-PR+7} y={yPow(v)+4} textAnchor="start"
                      fontSize="9" fill="rgba(245,158,11,0.4)">{v}W</text>
                  ))}
                  <text x={W-12} y={H/2} textAnchor="middle" fontSize="9"
                    fill="rgba(245,158,11,0.4)"
                    transform={`rotate(90,${W-12},${H/2})`}>W</text>
                </>
              )}
              {canalesOn.pace && paceVals.length > 0 && !canalesOn.power && (
                <>
                  {[paceMin, (paceMin+paceMax)/2, paceMax].map(v => (
                    <text key={v} x={W-PR+7} y={yPace(v)+4} textAnchor="start"
                      fontSize="9" fill="rgba(56,189,248,0.4)">{fmtPace(v)}</text>
                  ))}
                </>
              )}
            </>
          )}

          {/* Eje X */}
          {xTicks.map(t => {
            const x = PL + (t/maxT)*iW
            return (
              <text key={t} x={x} y={H-PB+16} textAnchor="middle"
                fontSize="9" fill={D.text3}>{fmtTime(t)}</text>
            )
          })}
          <text x={PL+iW/2} y={H-2} textAnchor="middle"
            fontSize="8" fill={D.text3} opacity="0.5">
            {esLaps
              ? `${laps.length} laps · tiempo acumulado (mm:ss)`
              : `${series.length} puntos GPS · tiempo (mm:ss) · pasá el mouse para ver detalle`}
          </text>
        </svg>
      ) : (!chartOpen && series.length >= 1) ? null : (
        <SinGrafico act={act} distKm={distKm} sport={sport} loading={loading}
          streamZonas={streamZonas} lthr={actLthr} sesionId={sesionId}/>
      )}

      {/* LEYENDA */}
      {series.length >= 1 && (
        <div style={{
          padding:'8px 16px 12px', borderTop:`1px solid ${D.border}`,
          display:'flex', gap:16, alignItems:'center', flexWrap:'wrap',
        }}>
          {CANALES.filter(c => canalesOn[c.key]).map(c => (
            <div key={c.key} style={{ display:'flex', alignItems:'center', gap:5 }}>
              <div style={{ width:18, height:3, borderRadius:2, background:c.color }}/>
              <span style={{ fontSize:10, color:D.text3 }}>{c.label}</span>
            </div>
          ))}
          <div style={{ display:'flex', alignItems:'center', gap:5 }}>
            <div style={{ width:18, height:0, borderTop:`1.5px dashed ${D.lthr}` }}/>
            <span style={{ fontSize:10, color:D.text3 }}>LTHR {actLthr}</span>
          </div>
          {streamZonas && (
            <div style={{ marginLeft:'auto', display:'flex', alignItems:'center', gap:8 }}>
              <div style={{ height:6, borderRadius:3, overflow:'hidden', display:'flex', width:120 }}>
                {Object.entries(streamZonas)
                  .filter(([,v]) => v.pct > 0)
                  .map(([z,v]) => (
                    <div key={z} style={{ width:`${v.pct}%`, background:D.zone[z] }}/>
                  ))}
              </div>
              <span style={{ fontSize:9, color:D.text3 }}>Zonas</span>
            </div>
          )}
          <span style={{ fontSize:9, color:D.text3, marginLeft:4 }}>
            {n} pts · hover para detalle
          </span>
        </div>
      )}

      {/* TABLA LAPS */}
      {tieneLaps && (
        <LapsColapsable laps={laps} sport={sport} lthr={actLthr}
          hover={hover} setHover={setHover}
          ftp={act?.ftp_watts || act?.ftp}
          defaultOpen={esLaps}/>
      )}
    </div>
  )
}

function SinGrafico({ act, distKm, sport, loading, streamZonas, lthr, sesionId }) {
  const tssZ12 = act?.tss_z12 || 0
  const tssZ34 = act?.tss_z34 || 0
  const tssZ56 = act?.tss_z56 || 0
  const tssT   = tssZ12 + tssZ34 + tssZ56 || 1
  const zonasPct = [
    { z:'Z1-2', pct:tssZ12/tssT*100, c:'#22C55E' },
    { z:'Z3-4', pct:tssZ34/tssT*100, c:'#F59E0B' },
    { z:'Z5-6', pct:tssZ56/tssT*100, c:'#EF4444' },
  ].filter(z => z.pct > 0)
  const zonasSource = streamZonas
    ? Object.entries(streamZonas).filter(([,v]) => v.pct>0).map(([z,v]) => ({
        z, pct:v.pct,
        c:{Z1:'#94A3B8',Z2:'#22C55E',Z3:'#84CC16',Z4:'#F59E0B',Z5:'#F97316',Z6:'#EF4444'}[z]
      }))
    : zonasPct
  return (
    <div style={{ padding:'16px 16px' }}>
      {loading ? (
        <div style={{ fontSize:12, color:D.text3, padding:'8px 0',
          display:'flex', gap:8, alignItems:'center' }}>
          <div style={{ width:8, height:8, borderRadius:'50%', background:'#38BDF8' }}/>
          Bajando streams de Garmin...
        </div>
      ) : (
        <>
          {zonasSource.length > 0 && (
            <div style={{ marginBottom:14 }}>
              <div style={{ fontSize:10, color:D.text3, textTransform:'uppercase',
                letterSpacing:1, marginBottom:7 }}>Distribución de zonas</div>
              <div style={{ height:10, borderRadius:5, overflow:'hidden', display:'flex', gap:1 }}>
                {zonasSource.map((z,i) => (
                  <div key={i} style={{ width:`${z.pct}%`, background:z.c }}/>
                ))}
              </div>
              <div style={{ display:'flex', gap:14, marginTop:6 }}>
                {zonasSource.map((z,i) => (
                  <span key={i} style={{ fontSize:10, color:z.c, fontWeight:600 }}>
                    {z.z} {z.pct.toFixed(0)}%
                  </span>
                ))}
              </div>
            </div>
          )}
          <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
            {[
              { Icon: Clock, label:'Duración',  v: act?.duration_min ? `${Math.round(act.duration_min)} min` : '--' },
              { Icon: Ruler, label:'Distancia', v: fmtDist(distKm) },
              act?.hr_avg    && { Icon: HeartPulse, label:'FC avg',  v:`${Math.round(act.hr_avg)} bpm`,  c:'#EF4444' },
              act?.hr_max    && { Icon: Flame, label:'FC máx',  v:`máx ${Math.round(act.hr_max)}`,  c:'#F97316' },
              act?.tss_total && { Icon: Target, label:'TSS',     v:act.tss_total.toFixed(1),          c:'#38BDF8' },
              act?.np_watts  && { Icon: Zap, label:'NP',      v:`${act.np_watts}W`,                c:'#F59E0B' },
              act?.calorias  && { Icon: Flame, label:'kcal',    v:`${act.calorias}` },
            ].filter(Boolean).map((m,i) => (
              <div key={i} style={{
                flex:1, minWidth:80,
                background:D.glass, border:`1px solid ${D.border}`,
                borderTop:`2px solid ${m.c||'rgba(255,255,255,0.15)'}`,
                borderRadius:10, padding:'10px 13px',
              }}>
                <div style={{ fontSize:10, color:D.text3, textTransform:'uppercase',
                  letterSpacing:0.8, marginBottom:4, display:'flex', alignItems:'center', gap:4 }}>
                  <m.Icon size={10}/> {m.label}
                </div>
                <div style={{ fontSize:18, fontWeight:700, color:m.c||D.text }}>{m.v}</div>
              </div>
            ))}
          </div>
          {!loading && (
            <div style={{ fontSize:10, color:D.text3, fontStyle:'italic', marginTop:12 }}>
              {sesionId ? 'Bajando streams de Garmin automáticamente...'
                : 'Activar laps automáticos en Garmin para ver el gráfico detallado.'}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function LapsColapsable({ laps, sport, lthr, hover, setHover, ftp, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen !== false)
  return (
    <div style={{ borderTop:`1px solid ${D.border}` }}>
      <button onClick={()=>setOpen(o=>!o)} style={{
        width:'100%', padding:'7px 16px',
        display:'flex', alignItems:'center', justifyContent:'space-between',
        background:'transparent', border:'none', cursor:'pointer',
        color:D.text3, fontSize:10, fontWeight:600, textTransform:'uppercase', letterSpacing:1,
      }}>
        <span style={{display:'flex',alignItems:'center',gap:5}}><ClipboardList size={11}/> {laps.length} laps</span>
        <span style={{ fontSize:11, transition:'transform 0.2s',
          transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>▼</span>
      </button>
      {open && <TablaLaps laps={laps} sport={sport} lthr={lthr}
        hover={hover} setHover={setHover} ftp={ftp}/>}
    </div>
  )
}

function TablaLaps({ laps, sport, lthr, hover, setHover, ftp }) {
  const fmtP    = p => { if(!p) return '--'; const m=Math.floor(p),s=Math.round((p-m)*60); return `${m}:${String(s).padStart(2,'0')} /km` }
  const fmtDur  = min => { if(!min) return '--'; return `${Math.floor(min)}'${String(Math.round((min%1)*60)).padStart(2,'0')}"` }
  const hrColor = hr => { if(!hr||!lthr) return '#94A3B8'; const r=hr/lthr; return r<0.82?'#94A3B8':r<0.88?'#22C55E':r<0.94?'#84CC16':r<1.00?'#F59E0B':r<1.06?'#F97316':'#EF4444' }
  const hrZone  = hr => { if(!hr||!lthr) return 'Z1'; const r=hr/lthr; return r<0.82?'Z1':r<0.88?'Z2':r<0.94?'Z3':r<1.00?'Z4':r<1.06?'Z5':'Z6' }
  const pwColor = (w,f) => { if(!w||!f) return '#F59E0B'; const r=w/f; return r<0.55?'#94A3B8':r<0.75?'#22C55E':r<0.87?'#84CC16':r<0.95?'#F59E0B':r<1.05?'#F97316':'#EF4444' }
  const pwZone  = (w,f) => { if(!w||!f) return '--'; const r=w/f; return r<0.55?'Z1':r<0.75?'Z2':r<0.87?'Z3':r<0.95?'Z4':r<1.05?'Z5':'Z6' }

  if (sport === 'cycling') {
    return (
      <div style={{ padding:'4px 16px 14px', overflowX:'auto' }}>
        <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10 }}>
          <thead>
            <tr style={{ borderBottom:`1px solid ${D.border}` }}>
              {['LAP','TIEMPO','DIST','W AVG','NP','W MÁX','IF','CAD','FC','VEL','ZONA'].map(h=>(
                <th key={h} style={{ padding:'4px 8px', textAlign:'right',
                  color:D.text3, fontWeight:700, textTransform:'uppercase', letterSpacing:0.5,
                  ...(h==='LAP'?{textAlign:'left'}:{}) }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {laps.map((l,i) => {
              const np    = l.norm_power || l.avg_power
              const avgW  = l.avg_power
              const ifVal = ftp && np ? (np/ftp) : l.lap_if
              const ifCol = !ifVal?D.text3:ifVal<0.75?'#94A3B8':ifVal<0.87?'#22C55E':ifVal<0.95?'#F59E0B':ifVal<1.05?'#F97316':'#EF4444'
              const pc    = pwColor(np,ftp)
              const pz    = pwZone(np,ftp)
              const isH   = hover===i
              return (
                <tr key={i} onMouseEnter={()=>setHover?.(i)} onMouseLeave={()=>setHover?.(null)}
                  style={{ background:isH?'rgba(245,158,11,0.06)':'transparent',
                    borderBottom:`1px solid rgba(255,255,255,0.04)` }}>
                  <td style={{ padding:'5px 8px', color:D.text3, fontWeight:700, textAlign:'left' }}>{l.lap_num||i+1}</td>
                  <td style={{ padding:'5px 8px', color:D.text2, textAlign:'right' }}>{fmtDur(l.duration_min)}</td>
                  <td style={{ padding:'5px 8px', color:D.text2, textAlign:'right' }}>
                    {l.distance_km?`${l.distance_km<1?Math.round(l.distance_km*1000)+'m':l.distance_km.toFixed(2)+'km'}`:'--'}
                  </td>
                  <td style={{ padding:'5px 8px', textAlign:'right', color:avgW?'#F59E0B':D.text3, fontWeight:600 }}>{avgW?Math.round(avgW)+'W':'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right', fontWeight:700, color:np?pc:D.text3 }}>{np?Math.round(np)+'W':'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right', color:D.text3 }}>{l.max_power?Math.round(l.max_power)+'W':'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right', fontWeight:700, color:ifCol }}>{ifVal?ifVal.toFixed(2):'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right', color:D.text3 }}>{l.cadence?Math.round(l.cadence):'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right', color:hrColor(l.hr_avg) }}>{l.hr_avg?Math.round(l.hr_avg):'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right', color:D.text3 }}>{l.avg_speed?l.avg_speed.toFixed(1)+'km/h':'--'}</td>
                  <td style={{ padding:'5px 8px', textAlign:'right' }}>
                    <span style={{ padding:'1px 5px', borderRadius:3, fontSize:9, fontWeight:700,
                      background:`${pc}22`, color:pc, border:`1px solid ${pc}40` }}>{pz}</span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    )
  }

  // Run / swim
  return (
    <div style={{ padding:'4px 16px 14px', overflowX:'auto' }}>
      <table style={{ width:'100%', borderCollapse:'collapse', fontSize:10 }}>
        <thead>
          <tr>
            {['Lap','Dist','Tiempo','FC avg','FC máx',
              sport==='swimming'?'Swolf':'Pace','Cad','Zona'].map(h=>(
              <th key={h} style={{ padding:'3px 7px', textAlign:'left',
                color:D.text3, fontWeight:600, textTransform:'uppercase', letterSpacing:0.5 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {laps.map((l,i) => {
            const zc  = hrColor(l.hr_avg)
            const zn  = hrZone(l.hr_avg)
            const isH = hover===i
            const metrica = sport==='swimming'&&l.swolf?l.swolf.toFixed(1)
              :(l.avg_power||l.watts)?`${Math.round(l.avg_power||l.watts)}W`
              :l.pace?fmtP(l.pace):'--'
            return (
              <tr key={i} onMouseEnter={()=>setHover?.(i)} onMouseLeave={()=>setHover?.(null)}
                style={{ background:isH?'rgba(255,255,255,0.05)':'transparent', cursor:'default' }}>
                <td style={{ padding:'3px 7px', color:D.text3, fontWeight:600 }}>{l.lap_num||l.lap||i+1}</td>
                <td style={{ padding:'3px 7px', color:'rgba(255,255,255,0.6)' }}>
                  {l.distance_km?`${Math.round(l.distance_km*1000)}m`:'--'}
                </td>
                <td style={{ padding:'3px 7px', color:D.text2 }}>{fmtDur(l.duration_min)}</td>
                <td style={{ padding:'3px 7px', fontWeight:700, color:zc }}>{l.hr_avg?Math.round(l.hr_avg):'--'}</td>
                <td style={{ padding:'3px 7px', color:D.text3 }}>{l.hr_max?Math.round(l.hr_max):'--'}</td>
                <td style={{ padding:'3px 7px', color:'rgba(255,255,255,0.55)' }}>{metrica}</td>
                <td style={{ padding:'3px 7px', color:D.text3 }}>{(l.cadence||l.cadencia)?Math.round(l.cadence||l.cadencia):'--'}</td>
                <td style={{ padding:'3px 7px' }}>
                  <span style={{ padding:'1px 6px', borderRadius:3, fontSize:9, fontWeight:700,
                    background:`${zc}22`, color:zc, border:`1px solid ${zc}40` }}>{zn}</span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

