// ══════════════════════════════════════════════════════════════════════════════
// SeccionRoute.jsx — NOAH ROUTE
// Mapa satelital real (Esri World Imagery). Línea gruesa, color intenso fijo
// por deporte. Tooltip al hover con checklist de métricas a mostrar.
//
// Requiere: npm install maplibre-gl@3.6.2
// ══════════════════════════════════════════════════════════════════════════════
import { useState, useEffect, useRef, useMemo } from 'react'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

const esLocal = window.location.hostname === "localhost" || window.location.hostname.startsWith("192.168.")
const API = esLocal ? `http://${window.location.hostname}:5000/api` : "/api"

function authFetch(url, options = {}) {
  let token = null
  try { const raw = localStorage.getItem('noah_sesion'); token = raw ? JSON.parse(raw)?.token : null } catch {}
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

const _routeCache = {}
const D = {
  card: 'rgba(10,15,30,0.82)', border: 'rgba(255,255,255,0.10)',
  ink: 'rgba(255,255,255,0.95)', ink2: 'rgba(255,255,255,0.62)', ink3: 'rgba(255,255,255,0.38)',
  violet: '#7C3AED',
}
// Colores intensos y saturados — no pasteles
const SPORT_COLOR = { running: '#7C3AED', cycling: '#EA580C', swimming: '#0EA5E9' }

function bearing(a, b) {
  const y = Math.sin((b[0]-a[0])*Math.PI/180) * Math.cos(b[1]*Math.PI/180)
  const x = Math.cos(a[1]*Math.PI/180)*Math.sin(b[1]*Math.PI/180) - Math.sin(a[1]*Math.PI/180)*Math.cos(b[1]*Math.PI/180)*Math.cos((b[0]-a[0])*Math.PI/180)
  return Math.atan2(y, x) * 180 / Math.PI
}
function fmtDur(s) {
  if (s == null) return '—'
  const h = Math.floor(s/3600), m = Math.floor(s%3600/60), ss = Math.round(s%60)
  return h > 0 ? `${h}:${String(m).padStart(2,'0')}:${String(ss).padStart(2,'0')}` : `${m}:${String(ss).padStart(2,'0')}`
}
// Suaviza el trazo (ruido GPS punto a punto) sin tocar los valores numéricos reales
function smoothCoords(coords, w = 5) {
  const half = Math.floor(w/2)
  return coords.map((c, i) => {
    const chunk = coords.slice(Math.max(0, i-half), i+half+1)
    return [chunk.reduce((s,p)=>s+p[0],0)/chunk.length, chunk.reduce((s,p)=>s+p[1],0)/chunk.length]
  })
}
// Ritmo/velocidad reales del punto no se calculan instante a instante (eso se
// dispara a valores absurdos en cada pausa/semáforo) — se toma una ventana de
// +-4 muestras y se mide distancia/tiempo real recorrido en esa ventana, igual
// que hace Garmin/Strava para el "ritmo actual".
function paceVelEnPunto(series, i, win = 4) {
  const lo = Math.max(0, i - win), hi = Math.min(series.length - 1, i + win)
  const d0 = series[lo].dist_km, d1 = series[hi].dist_km, t0 = series[lo].t, t1 = series[hi].t
  if (d0 == null || d1 == null || t0 == null || t1 == null) return { pace: null, vel: null }
  const metros = (d1 - d0) * 1000, seg = t1 - t0
  if (seg <= 0 || metros <= 0) return { pace: null, vel: null }
  const speedMs = metros / seg
  if (speedMs < 0.3) return { pace: null, vel: 0 } // parado/pausa real
  return { pace: +(1000 / (speedMs * 60)).toFixed(2), vel: +(speedMs * 3.6).toFixed(1) }
}

const ICON_SVG = {
  running: `<path d="M6.5 18.5l3-4.5-2-3.2" stroke-linecap="round"/><circle cx="14.5" cy="4.5" r="1.6" fill="white" stroke="none"/><path d="M13 6.5l-2 3.5 3 2 1.5 4 3 1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M11 10l-4 1.5" stroke-linecap="round"/>`,
  cycling: `<circle cx="6" cy="17" r="3.2"/><circle cx="18" cy="17" r="3.2"/><path d="M6 17l4-8h4l3 8M10 9h3M13 5.5h2.5L18 9" stroke-linecap="round" stroke-linejoin="round"/>`,
  swimming: `<path d="M2 12c1 1 2 1 3 0s2-1 3 0 2 1 3 0 2-1 3 0 2 1 3 0 2-1 3 0" stroke-linecap="round"/><path d="M2 17c1 1 2 1 3 0s2-1 3 0 2 1 3 0 2-1 3 0 2 1 3 0 2-1 3 0" stroke-linecap="round"/><circle cx="15" cy="6" r="2" fill="white" stroke="none"/>`,
}
const FLAG_SVG = `<path d="M5 21V4" stroke-linecap="round"/><path d="M5 4s1.5-1.5 4-1.5 4 1.5 6.5 1.5S19 3 19 3v9s-1.5 1.5-3.5 1.5S12 12 9 12s-4 1.5-4 1.5z" stroke-linejoin="round"/>`
function svgBadge(inner, size = 22) { return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8">${inner}</svg>` }

// Todas las métricas posibles del hover. `total` = valor agregado de toda la
// actividad (no cambia con el mouse); el resto es el valor en el punto exacto.
function fieldDefs(sport) {
  const all = [
    { id:'km',    label:'KM',               unit:'km',   get:p=>p.dist_km },
    { id:'hr',    label:'HR',               unit:'bpm',  get:p=>p.hr },
    { id:'pace',  label:'Ritmo',            unit:'/km',  get:(p,i,s)=>paceVelEnPunto(s,i).pace,  hide: sport==='cycling' },
    { id:'vel',   label:'Velocidad',        unit:'km/h', get:(p,i,s)=>paceVelEnPunto(s,i).vel },
    { id:'power', label:'Potencia',         unit:'W',    get:p=>p.power, hide: sport!=='cycling' },
    { id:'elev',  label:'Elevación',        unit:'m',    get:p=>p.alt!=null?Math.round(p.alt):null },
    { id:'cad',   label:'Cadencia',         unit: sport==='running'?'spm':'rpm', get:p=>p.cadence },
    { id:'osc',   label:'Osc. vertical',    unit:'mm',   get:p=>p.vert_osc, hide: sport!=='running' },
    { id:'gct',   label:'Contacto suelo',   unit:'ms',   get:p=>p.gct, hide: sport!=='running' },
    { id:'stride',label:'Zancada',          unit:'cm',   get:p=>p.stride, hide: sport!=='running' },
    { id:'temp',  label:'Temperatura',      unit:'°C',   get:p=>p.temp },
    { id:'resp',  label:'Respiración',      unit:'rpm',  get:p=>p.resp },
    { id:'gctbal',label:'Balance apoyo',    unit:'%',    get:p=>p.gct_bal, hide: sport!=='running' },
    { id:'vratio',label:'Ratio vertical',   unit:'%',    get:p=>p.vert_ratio, hide: sport!=='running' },
    { id:'stress',label:'Estrés',           unit:'',     get:p=>p.stress },
    { id:'distT', label:'Distancia total',  unit:'km',   total:true, get:s=>s.distKm },
    { id:'durT',  label:'Tiempo total',     unit:'',     total:true, get:s=>fmtDur(s.dur) },
  ]
  return all.filter(f => !f.hide)
}
// Campos ya conocidos (arriba) — cualquier otro campo numérico que venga en el
// stream y no esté en esa lista (ej. algo específico de tu banda de pecho) se
// agrega igual acá, en vez de perderse en silencio.
const CAMPOS_CONOCIDOS = new Set(['t','lat','lon','dist_km','hr','power','pace','cadence','alt','temp','vert_osc','gct','stride','resp','gct_bal','vert_ratio','stress'])
function fieldsDinamicos(series) {
  if (!series?.length) return []
  const claves = new Set()
  series.forEach(p => Object.keys(p).forEach(k => { if (!CAMPOS_CONOCIDOS.has(k) && p[k] != null && typeof p[k] === 'number') claves.add(k) }))
  return [...claves].map(k => ({ id: `x_${k}`, label: k, unit: '', get: p => p[k] }))
}


export default function SeccionRoute({ sesionId, atletaId, sport = 'running', height = 560, streamsExternos = null }) {
  const mapDiv = useRef(null)
  const mapRef = useRef(null)
  const [series, setSeries] = useState(streamsExternos)
  const [loading, setLoading] = useState(false)
  const [is3D, setIs3D] = useState(false)
  const [hover, setHover] = useState(null)
  const [showConfig, setShowConfig] = useState(false)
  const sportColor = SPORT_COLOR[sport] || SPORT_COLOR.running
  const FIELDS = useMemo(() => [...fieldDefs(sport), ...fieldsDinamicos(series)], [sport, series])

  const [campos, setCampos] = useState(null)
  useEffect(() => {
    if (!series?.length || campos !== null) return
    // Por defecto: TODOS los campos que tengan al menos un dato real en esta actividad
    const disponibles = FIELDS.filter(f => {
      if (f.total) return stats && f.get(stats) != null
      return series.some(p => f.get(p, 0, series) != null)
    }).map(f => f.id)
    try {
      const saved = JSON.parse(localStorage.getItem('noah_route_campos') || 'null')
      setCampos(saved && saved.length ? saved : disponibles)
    } catch { setCampos(disponibles) }
  }, [series]) // eslint-disable-line react-hooks/exhaustive-deps
  const toggleCampo = (id) => {
    setCampos(prev => {
      const cur = prev || []
      const next = cur.includes(id) ? cur.filter(c => c !== id) : [...cur, id]
      try { localStorage.setItem('noah_route_campos', JSON.stringify(next)) } catch {}
      return next
    })
  }

  useEffect(() => {
    if (streamsExternos) { setSeries(streamsExternos); return }
    if (!sesionId || !atletaId) return
    const cacheKey = `${atletaId}_${sesionId}`
    if (_routeCache[cacheKey]) { setSeries(_routeCache[cacheKey]); return }
    setLoading(true)
    authFetch(`${API}/atletas/${atletaId}/activity_streams?sesion_id=${sesionId}`)
      .then(r => r.json())
      .then(r => {
        const s = r.data?.series || []
        const conGps = s.filter(p => p.lat != null && p.lon != null && !(p.lat === 0 && p.lon === 0))
        _routeCache[cacheKey] = conGps
        setSeries(conGps)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }, [sesionId, atletaId, streamsExternos])

  const stats = useMemo(() => {
    if (!series || series.length < 2) return null
    const distKm = series[series.length-1]?.dist_km
    const dur = series[series.length-1]?.t - series[0]?.t
    let elevGain = 0
    for (let i=1;i<series.length;i++){ const d=(series[i].alt??series[i-1].alt)-(series[i-1].alt??series[i].alt); if(d>0) elevGain+=d }
    const avg = (key) => { const vals = series.map(p=>p[key]).filter(v=>v!=null); return vals.length ? Math.round(vals.reduce((a,b)=>a+b,0)/vals.length) : null }
    return { distKm, dur, elevGain: Math.round(elevGain), power: avg('power'), hr: avg('hr'), cadence: avg('cadence') }
  }, [series])

  useEffect(() => {
    if (!series || series.length < 2 || mapRef.current) return
    const rawCoords = series.map(p => [p.lon, p.lat])
    const coords = smoothCoords(rawCoords, 5) // línea limpia, sin zigzag de ruido GPS
    const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]))
    const gradient = sport === 'cycling'
      ? ['interpolate', ['linear'], ['line-progress'], 0, '#EA580C', 1, '#FDE047']
      : ['interpolate', ['linear'], ['line-progress'], 0, sportColor, 1, sportColor]

    const map = new maplibregl.Map({
      container: mapDiv.current,
      style: {
        version: 8,
        sources: {
          sat: { type: 'raster', tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'], tileSize: 256, attribution: 'Esri' },
          ref: { type: 'raster', tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}'], tileSize: 256 },
        },
        layers: [ { id:'sat', type:'raster', source:'sat' }, { id:'ref', type:'raster', source:'ref', paint:{'raster-opacity':0.85} } ],
      },
      bounds, fitBoundsOptions: { padding: 36 }, attributionControl: true,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    map.on('error', (e) => console.error('[ROUTE] error de mapa:', e?.error || e))

    map.on('load', () => {
      try {
        const geojson = { type: 'Feature', geometry: { type: 'LineString', coordinates: coords } }
        map.addSource('route', { type: 'geojson', lineMetrics: true, data: geojson })
        // Fallback: línea sólida (siempre visible, incluso si gradient falla en mobile)
        map.addLayer({ id: 'route-solid', type: 'line', source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-width': 5, 'line-color': sportColor, 'line-opacity': 0.9 } })
        // Glow + gradient (puede fallar en mobile — route-solid es el respaldo)
        try {
        map.addLayer({ id: 'route-glow', type: 'line', source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-width': 16, 'line-blur': 8, 'line-opacity': 0.5, 'line-gradient': gradient } })
        map.addLayer({ id: 'route-line', type: 'line', source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-width': 6, 'line-gradient': gradient } })
        } catch(e) { console.warn('[ROUTE] gradient fallback:', e) }
        map.addLayer({ id: 'route-hit', type: 'line', source: 'route',
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: { 'line-width': 26, 'line-opacity': 0 } })

        const step = Math.max(1, Math.floor(coords.length / 22))
        const arrowFeats = []
        for (let i = step; i < coords.length; i += step) {
          arrowFeats.push({ type:'Feature', geometry:{type:'Point',coordinates:coords[i]}, properties:{bearing:bearing(coords[i-1],coords[i])} })
        }
        map.addSource('arrows', { type:'geojson', data:{type:'FeatureCollection',features:arrowFeats} })
        map.addLayer({ id:'route-arrows', type:'symbol', source:'arrows',
          layout:{'text-field':'▲','text-size':12,'text-rotate':['get','bearing'],'text-rotation-alignment':'map','text-allow-overlap':true,'text-ignore-placement':true},
          paint:{'text-color':'#fff','text-halo-color':'rgba(0,0,0,0.65)','text-halo-width':1.3} })

        if (!document.getElementById('noah-route-pulse-style')) {
          const st = document.createElement('style')
          st.id = 'noah-route-pulse-style'
          st.textContent = `
            @keyframes noahPulse{0%{transform:scale(1);opacity:.55}70%{transform:scale(2.1);opacity:0}100%{opacity:0}}
            .noah-route-card{ height:var(--noah-route-h); }
            @media (max-width:640px){
              .noah-route-wrap{ padding:0 10px; }
              .noah-route-card{ height:calc(var(--noah-route-h) * 0.62); border-radius:12px; }
              .noah-route-ctrl-btn{ width:28px !important; height:28px !important; font-size:12px !important; }
            }`
          document.head.appendChild(st)
        }
        const startEl = document.createElement('div')
        startEl.style.cssText = `position:relative;width:42px;height:42px;display:flex;align-items:center;justify-content:center;`
        startEl.innerHTML = `<div style="position:absolute;inset:0;border-radius:50%;background:${sportColor};animation:noahPulse 1.8s ease-out infinite;"></div>
          <div style="position:relative;width:42px;height:42px;border-radius:50%;background:${sportColor};border:3px solid #fff;box-shadow:0 2px 10px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;">${svgBadge(ICON_SVG[sport]||ICON_SVG.running)}</div>`
        new maplibregl.Marker({ element: startEl, anchor: 'center' }).setLngLat(coords[0]).addTo(map)

        const endEl = document.createElement('div')
        endEl.style.cssText = `width:38px;height:38px;border-radius:50%;background:#1a1a1a;border:3px solid #fff;box-shadow:0 2px 10px rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;`
        endEl.innerHTML = svgBadge(FLAG_SVG, 20)
        new maplibregl.Marker({ element: endEl, anchor: 'center' }).setLngLat(coords[coords.length-1]).addTo(map)

        map.on('mousemove', 'route-hit', (e) => {
          map.getCanvas().style.cursor = 'crosshair'
          const { lng, lat } = e.lngLat
          let nearest = 0, minD = Infinity
          for (let i = 0; i < coords.length; i++) {
            const dx = coords[i][0]-lng, dy = coords[i][1]-lat, d = dx*dx+dy*dy
            if (d < minD) { minD = d; nearest = i }
          }
          setHover({ data: series[nearest], i: nearest, x: e.point.x, y: e.point.y })
        })
        map.on('mouseleave', 'route-hit', () => { map.getCanvas().style.cursor = ''; setHover(null) })
      } catch (err) { console.error('[ROUTE] error dibujando la ruta:', err) }
    })
    return () => { map.remove(); mapRef.current = null }
  }, [series]) // eslint-disable-line react-hooks/exhaustive-deps

  const centrar = () => {
    if (!mapRef.current || !series) return
    const coords = smoothCoords(series.map(p => [p.lon, p.lat]), 5)
    const bounds = coords.reduce((b, c) => b.extend(c), new maplibregl.LngLatBounds(coords[0], coords[0]))
    mapRef.current.fitBounds(bounds, { padding: 36 })
  }
  const toggle3D = () => { const v = !is3D; setIs3D(v); mapRef.current?.easeTo({ pitch: v ? 55 : 0, duration: 500 }) }

  if (loading) return <div style={{ padding: 24, color: D.ink3, fontSize: 13 }}>Cargando ruta…</div>
  if (!series || series.length < 2) return <div style={{ padding: 24, color: D.ink3, fontSize: 13 }}>Esta actividad no tiene datos GPS.</div>

  return (
    <div className="noah-route-wrap" style={{ padding: '0 2px' }}>
    <div className="noah-route-card" style={{ '--noah-route-h': `${height}px`, position: 'relative', maxWidth: 960, margin: '0 auto',
                  borderRadius: 14, overflow: 'hidden', border: `1px solid ${D.border}`, boxShadow: '0 8px 28px rgba(0,0,0,0.35)' }}>
      <div ref={mapDiv} style={{ position: 'absolute', inset: 0 }} />

      <div style={{ position: 'absolute', top: 10, right: 10, display: 'flex', gap: 6, zIndex: 5 }}>
        <button className="noah-route-ctrl-btn" onClick={() => setShowConfig(v => !v)} title="Elegir métricas del hover"
          style={{ width: 30, height: 30, borderRadius: 8, background: showConfig ? D.violet : D.card, border: `1px solid ${D.border}`, color: '#fff', backdropFilter: 'blur(14px)', cursor: 'pointer', fontSize: 13 }}>⚙</button>
        <div style={{ display: 'flex', background: D.card, border: `1px solid ${D.border}`, borderRadius: 8, padding: 2, backdropFilter: 'blur(14px)' }}>
          <button onClick={() => is3D && toggle3D()} style={{ border:'none', background: !is3D?D.violet:'transparent', color: !is3D?'#fff':D.ink3, fontSize:10, fontWeight:700, padding:'5px 9px', borderRadius:6, cursor:'pointer' }}>2D</button>
          <button onClick={() => !is3D && toggle3D()} style={{ border:'none', background: is3D?D.violet:'transparent', color: is3D?'#fff':D.ink3, fontSize:10, fontWeight:700, padding:'5px 9px', borderRadius:6, cursor:'pointer' }}>3D</button>
        </div>
      </div>

      <button className="noah-route-ctrl-btn" onClick={centrar} title="Centrar ruta"
        style={{ position:'absolute', top:10, left:52, width:30, height:30, borderRadius:8, background:D.card, border:`1px solid ${D.border}`, color:D.ink2, backdropFilter:'blur(14px)', cursor:'pointer', zIndex:5, fontSize:12 }}>⌖</button>

      {/* Checklist de métricas para el hover */}
      {showConfig && (
        <div style={{ position:'absolute', top:54, right:12, background:D.card, border:`1px solid ${D.border}`, borderRadius:12, padding:'10px 6px', backdropFilter:'blur(16px)', zIndex:6, minWidth:170, maxHeight:280, overflowY:'auto' }}>
          <div style={{ fontSize:9.5, color:D.ink3, fontWeight:700, letterSpacing:1, padding:'2px 10px 8px' }}>MOSTRAR AL PASAR EL MOUSE</div>
          {FIELDS.map(f => (
            <label key={f.id} style={{ display:'flex', alignItems:'center', gap:8, padding:'6px 10px', cursor:'pointer', fontSize:12, color:D.ink2 }}>
              <input type="checkbox" checked={!!campos?.includes(f.id)} onChange={() => toggleCampo(f.id)} style={{ accentColor: sportColor }}/>
              {f.label}
            </label>
          ))}
        </div>
      )}

      {/* Tooltip de hover */}
      {hover && (
        <div style={{ position:'absolute', left:Math.min(hover.x+12,(mapDiv.current?.clientWidth||9999)-168), top:Math.max(hover.y-92,8),
                      background:'rgba(8,12,24,0.92)', border:`1px solid ${D.border}`, borderRadius:10, padding:'9px 12px', backdropFilter:'blur(18px)',
                      zIndex:6, pointerEvents:'none', minWidth:126, boxShadow:'0 6px 20px rgba(0,0,0,0.45)' }}>
          <div style={{ display:'flex', flexDirection:'column', gap:3.5, fontSize:12, color:D.ink }}>
            {FIELDS.filter(f => campos?.includes(f.id)).map(f => {
              const val = f.total ? (stats ? f.get(stats) : null) : f.get(hover.data, hover.i, series)
              if (val == null || val === '—') return null
              return <div key={f.id} style={{ display:'flex', justifyContent:'space-between', gap:14 }}>
                <span style={{ color:D.ink3, fontSize:10.5 }}>{f.label}</span>
                <b style={{ color:'#22D3EE', fontVariantNumeric:'tabular-nums' }}>{val}{f.unit ? ` ${f.unit}` : ''}</b>
              </div>
            })}
          </div>
        </div>
      )}

      {stats && (
        <div style={{ position:'absolute', left:10, right:10, bottom:10, background:'rgba(8,12,24,0.85)', border:`1px solid ${D.border}`, borderRadius:10,
                      padding:'8px 14px', backdropFilter:'blur(14px)', zIndex:5, display:'flex', gap:16, flexWrap:'wrap', fontSize:11.5, color:D.ink2, alignItems:'center' }}>
          <b style={{ color:D.ink }}>{stats.distKm ?? '—'} km</b>
          <span>{fmtDur(stats.dur)}</span>
          <span>+{stats.elevGain} m</span>
          {stats.power != null && <span>{stats.power} W</span>}
          {stats.hr != null && <span>{stats.hr} bpm</span>}
          {stats.cadence != null && <span>{stats.cadence} rpm</span>}
        </div>
      )}
    </div>
    </div>
  )
}
