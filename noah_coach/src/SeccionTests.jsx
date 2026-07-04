// SeccionTests.jsx — NOA Tests de Umbral v2 — Carrusel 3D Glassmorphism
import { useState, useEffect, useRef } from 'react'

// API — en la PC/celular de casa (red local) sigue usando el puerto 5000,
// como ya funcionaba. En Vercel (1 sola dirección para front y backend)
// no hay puerto separado: todo entra por /api en el mismo dominio. El
// navegador ya sabe en qué dirección está parado — solo se le pregunta.
const esLocal = window.location.hostname === "localhost" || window.location.hostname.startsWith("192.168.")
const API = esLocal
  ? `http://${window.location.hostname}:5000/api`
  : "/api"

// authFetch — mismo helper que en AtletaDashboard.jsx/App.js/GraficoActividadStreams.jsx
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

const TIPO_TEST = {
  umbral_run: {
    label: 'Umbral Running',
    short: 'LTHR RUN',
    icon: '🏃',
    bg: 'https://images.unsplash.com/photo-1571008887538-b36bb32f4571?w=600&q=80',
    gradient: 'linear-gradient(135deg,#1a0533 0%,#4c1d95 60%,#7c3aed 100%)',
    accent: '#A78BFA',
    dark: '#4c1d95',
    campos: ['pace_umbral','velocidad_umbral','hr_umbral','vo2est','rpe','potencia','notas'],
  },
  umbral_bike: {
    label: 'Umbral Ciclismo',
    short: 'FTP BIKE',
    icon: '🚴',
    bg: 'https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=600&q=80',
    gradient: 'linear-gradient(135deg,#1a2e05 0%,#4d7c0f 60%,#84cc16 100%)',
    accent: '#BEF264',
    dark: '#4d7c0f',
    campos: ['potencia_ftp','velocidad','cadencia','hr_umbral','rpe','vo2est','wkg','notas'],
  },
  umbral_swim: {
    label: 'Umbral Natación',
    short: 'CSS SWIM',
    icon: '🏊',
    bg: 'https://images.unsplash.com/photo-1530549387789-4c1017266635?w=600&q=80',
    gradient: 'linear-gradient(135deg,#0a1628 0%,#0369a1 60%,#38bdf8 100%)',
    accent: '#7DD3FC',
    dark: '#0369a1',
    campos: ['distancia_protocolo','tiempo_total','css_calculado','hr_umbral','rpe','notas'],
  },
  potencia_run: {
    label: 'Potencia Aeróbica',
    short: 'VAM RUN',
    icon: '⚡',
    bg: 'https://images.unsplash.com/photo-1476480862126-209bfaa8edc8?w=600&q=80',
    gradient: 'linear-gradient(135deg,#1c0a0a 0%,#9f1239 60%,#fb7185 100%)',
    accent: '#FDA4AF',
    dark: '#9f1239',
    campos: ['velocidad_max','distancia','tiempo','hr_max','rpe','notas'],
  },
  potencia_bike: {
    label: 'Sprint / Potencia',
    short: 'PWR BIKE',
    icon: '💥',
    bg: 'https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=600&q=80',
    gradient: 'linear-gradient(135deg,#1c1a00 0%,#d97706 60%,#fcd34d 100%)',
    accent: '#FDE68A',
    dark: '#d97706',
    campos: ['watts_pico','duracion','cadencia','hr_max','rpe','notas'],
  },
  potencia_swim: {
    label: 'Sprint Natación',
    short: 'SPR SWIM',
    icon: '💨',
    bg: 'https://images.unsplash.com/photo-1600679472829-3044539ce8ed?w=600&q=80',
    gradient: 'linear-gradient(135deg,#0c1445 0%,#1e3a5f 60%,#06b6d4 100%)',
    accent: '#67E8F9',
    dark: '#1e3a5f',
    campos: ['distancia','tiempo','hr_max','rpe','notas'],
  },
  record_carrera: {
    label: 'Récord en Carrera',
    short: 'RACE PR',
    icon: '🏁',
    bg: 'https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=600&q=80',
    gradient: 'linear-gradient(135deg,#0f0f0f 0%,#1f2937 60%,#374151 100%)',
    accent: '#FCD34D',
    dark: '#1f2937',
    campos: ['carrera_ref','deporte_rec','hr_umbral','pace_umbral','potencia','notas'],
  },
}

const CAMPOS_META = {
  pace_umbral:        { label: 'Pace umbral', placeholder: '4:30', unit: '/km' },
  velocidad_umbral:   { label: 'Velocidad', placeholder: '13.5', unit: 'km/h' },
  hr_umbral:          { label: 'LTHR', placeholder: '162', unit: 'bpm' },
  vo2est:             { label: 'VO2 estimado', placeholder: '52', unit: 'ml/kg/min' },
  rpe:                { label: 'Esfuerzo (RPE)', placeholder: '8', unit: '/10' },
  potencia:           { label: 'Potencia', placeholder: '210', unit: 'W' },
  potencia_ftp:       { label: "FTP (95% 20')", placeholder: '250', unit: 'W' },
  velocidad:          { label: 'Velocidad', placeholder: '38', unit: 'km/h' },
  cadencia:           { label: 'Cadencia', placeholder: '90', unit: 'rpm' },
  wkg:                { label: 'W/kg', placeholder: '3.2', unit: 'W/kg' },
  distancia_protocolo:{ label: 'Distancia', placeholder: '800', unit: 'm' },
  tiempo_total:       { label: 'Tiempo total', placeholder: '12:30', unit: 'mm:ss' },
  css_calculado:      { label: 'CSS', placeholder: '1:45', unit: '/100m' },
  velocidad_max:      { label: 'Vel. máxima', placeholder: '18', unit: 'km/h' },
  distancia:          { label: 'Distancia', placeholder: '50', unit: 'm' },
  tiempo:             { label: 'Tiempo', placeholder: '0:28', unit: '' },
  hr_max:             { label: 'HR máxima', placeholder: '185', unit: 'bpm' },
  watts_pico:         { label: 'Watts pico', placeholder: '850', unit: 'W' },
  duracion:           { label: 'Duración', placeholder: '10', unit: 's' },
  carrera_ref:        { label: 'Carrera', placeholder: 'Maratón BA 2026', unit: '' },
  deporte_rec:        { label: 'Deporte', placeholder: 'running', unit: '' },
  notas:              { label: 'Notas', placeholder: 'Condiciones, sensaciones...', unit: '', textarea: true },
}

function fmtFecha(f) {
  if (!f) return '--'
  return new Date(f + 'T12:00:00').toLocaleDateString('es-AR', { day:'numeric', month:'short', year:'numeric' })
}

// ── Estilos globales inyectados una vez ───────────────────────────────────────
const STYLES = `
  @keyframes slideIn {
    from { opacity:0; transform:translateY(20px) scale(0.97); }
    to   { opacity:1; transform:translateY(0) scale(1); }
  }
  @keyframes fadeIn { from{opacity:0} to{opacity:1} }
  .test-card-wrap {
    transition: transform 0.35s cubic-bezier(.22,.68,0,1.2), box-shadow 0.3s ease;
  }
  .test-card-wrap:hover {
    transform: translateY(-8px) scale(1.02) !important;
  }
  .test-card-wrap.center-card {
    transform: scale(1.06);
    z-index: 3;
  }
  .test-card-wrap.side-card {
    transform: scale(0.93) translateY(10px);
    opacity: 0.75;
    z-index: 1;
  }
  .glass-btn {
    backdrop-filter: blur(12px);
    transition: all 0.2s ease;
  }
  .glass-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }
  .carousel-track::-webkit-scrollbar { display: none; }
  .carousel-track { -ms-overflow-style: none; scrollbar-width: none; }
`

// ── Modal ────────────────────────────────────────────────────────────────────
function ModalTest({ test, atletaId, onClose, onGuardado }) {
  const esNuevo = !test?.id
  const [tipoSel, setTipoSel] = useState(test?.tipo || 'umbral_run')
  const [form, setForm] = useState({
    tipo: test?.tipo || 'umbral_run',
    fecha: test?.fecha || new Date().toISOString().slice(0,10),
    protocolo: test?.protocolo || "20' FTP",
    actualizar_perfil: test?.actualizar_perfil ?? true,
    ...test?.datos || {},
  })
  const [loading, setLoading] = useState(false)
  const set = (k,v) => setForm(f => ({...f,[k]:v}))
  const tipo = TIPO_TEST[tipoSel] || TIPO_TEST.umbral_run

  const guardar = async () => {
    if (!form.fecha) return alert('La fecha es requerida')
    setLoading(true)
    try {
      const body = {
        tipo: tipoSel, fecha: form.fecha,
        protocolo: form.protocolo,
        actualizar_perfil: form.actualizar_perfil,
        datos: {},
      }
      tipo.campos.forEach(c => { if (form[c] !== undefined && form[c] !== '') body.datos[c] = form[c] })
      const url = esNuevo
        ? `${API}/atletas/${atletaId}/tests`
        : `${API}/atletas/${atletaId}/tests/${test.id}`
      await fetch(url, {
        method: esNuevo ? 'POST' : 'PATCH',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify(body),
      })
      onGuardado(); onClose()
    } catch { alert('Error al guardar') }
    setLoading(false)
  }

  return (
    <div style={{
      position:'fixed',inset:0,zIndex:300,
      background:'rgba(0,0,0,0.92)',backdropFilter:'blur(16px)',
      display:'flex',alignItems:'center',justifyContent:'center',
      animation:'fadeIn 0.2s ease',
    }} onClick={e => e.target===e.currentTarget && onClose()}>
      <div style={{
        width:580,maxWidth:'96vw',maxHeight:'93vh',
        borderRadius:24,overflow:'hidden',
        background:'rgba(13,17,23,0.98)',
        border:'1px solid rgba(255,255,255,0.12)',
        boxShadow:`0 40px 120px rgba(0,0,0,0.9), 0 0 0 1px ${tipo.accent}20`,
        display:'flex',flexDirection:'column',
        animation:'slideIn 0.3s ease',
      }}>

        {/* Header imagen + glassmorphism */}
        <div style={{
          height:160, position:'relative', overflow:'hidden',
          background:tipo.gradient,
        }}>
          <div style={{
            position:'absolute',inset:0,
            backgroundImage:`url(${tipo.bg})`,
            backgroundSize:'cover',backgroundPosition:'center',
            opacity:0.35,
          }}/>
          <div style={{
            position:'absolute',inset:0,
            background:`linear-gradient(to bottom, ${tipo.dark}99 0%, rgba(13,17,23,0.95) 100%)`,
          }}/>
          <div style={{position:'relative',zIndex:1,padding:'20px 24px',height:'100%',display:'flex',flexDirection:'column',justifyContent:'space-between'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
              <div>
                <div style={{fontSize:10,fontWeight:800,color:tipo.accent,
                  textTransform:'uppercase',letterSpacing:2.5,marginBottom:8}}>
                  {esNuevo ? '+ Nuevo test' : 'Editar test'}
                </div>
                <div style={{fontSize:26,fontWeight:900,color:'#fff',lineHeight:1}}>
                  {tipo.icon} {tipo.label}
                </div>
              </div>
              <button onClick={onClose} className="glass-btn" style={{
                width:36,height:36,borderRadius:10,
                background:'rgba(255,255,255,0.1)',
                border:'1px solid rgba(255,255,255,0.15)',
                color:'#fff',cursor:'pointer',fontSize:20,
                display:'flex',alignItems:'center',justifyContent:'center',
              }}>×</button>
            </div>
            {/* Selector tipo */}
            {esNuevo && (
              <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
                {Object.entries(TIPO_TEST).map(([k,t]) => (
                  <button key={k} onClick={()=>{setTipoSel(k);set('tipo',k)}}
                    className="glass-btn" style={{
                    padding:'4px 11px',borderRadius:99,fontSize:10,fontWeight:700,
                    cursor:'pointer',
                    border:`1px solid ${tipoSel===k ? t.accent : 'rgba(255,255,255,0.15)'}`,
                    background:tipoSel===k ? `${t.accent}25` : 'rgba(0,0,0,0.3)',
                    color:tipoSel===k ? t.accent : 'rgba(255,255,255,0.45)',
                  }}>{t.short}</button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Formulario */}
        <div style={{flex:1,overflow:'auto',padding:'20px 24px'}}>
          <div style={{display:'flex',flexDirection:'column',gap:14}}>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
              <div>
                <label style={lbl}>Fecha *</label>
                <input style={inp} type="date" value={form.fecha}
                  onChange={e=>set('fecha',e.target.value)}/>
              </div>
              <div>
                <label style={lbl}>Protocolo</label>
                <input style={inp} value={form.protocolo}
                  onChange={e=>set('protocolo',e.target.value)}
                  placeholder="20' FTP, 30' campo..."/>
              </div>
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
              {tipo.campos.filter(c=>c!=='notas').map(c => {
                const m = CAMPOS_META[c]||{label:c,placeholder:'',unit:''}
                return (
                  <div key={c}>
                    <label style={lbl}>{m.label}{m.unit&&<span style={{color:'rgba(255,255,255,0.2)',fontWeight:400,marginLeft:4}}>({m.unit})</span>}</label>
                    <input style={inp} value={form[c]||''} onChange={e=>set(c,e.target.value)} placeholder={m.placeholder}/>
                  </div>
                )
              })}
            </div>
            {tipo.campos.includes('notas') && (
              <div>
                <label style={lbl}>Notas</label>
                <textarea style={{...inp,minHeight:70,resize:'vertical'}}
                  value={form.notas||''} onChange={e=>set('notas',e.target.value)}
                  placeholder="Condiciones, temperatura, sensaciones..."/>
              </div>
            )}
            {['umbral_run','umbral_bike','umbral_swim'].includes(tipoSel) && (
              <div style={{
                display:'flex',alignItems:'center',gap:10,
                padding:'10px 14px',borderRadius:10,
                background:`${tipo.accent}0f`,
                border:`1px solid ${tipo.accent}22`,
              }}>
                <input type="checkbox" id="act_p" checked={form.actualizar_perfil}
                  onChange={e=>set('actualizar_perfil',e.target.checked)}
                  style={{width:15,height:15,cursor:'pointer',accentColor:tipo.accent}}/>
                <label htmlFor="act_p" style={{fontSize:12,color:'rgba(255,255,255,0.6)',cursor:'pointer'}}>
                  Actualizar LTHR/CSS del atleta con este resultado
                </label>
              </div>
            )}
          </div>
        </div>

        <div style={{
          padding:'14px 24px',
          borderTop:'1px solid rgba(255,255,255,0.07)',
          display:'flex',gap:8,justifyContent:'flex-end',
          background:'rgba(0,0,0,0.2)',
        }}>
          <button onClick={onClose} className="glass-btn" style={{
            padding:'9px 20px',borderRadius:10,
            border:'1px solid rgba(255,255,255,0.1)',
            background:'rgba(255,255,255,0.05)',
            color:'rgba(255,255,255,0.5)',cursor:'pointer',fontSize:13,
          }}>Cancelar</button>
          <button onClick={guardar} disabled={loading} className="glass-btn" style={{
            padding:'9px 24px',borderRadius:10,border:'none',
            background:tipo.accent,color:'#000',
            cursor:'pointer',fontSize:13,fontWeight:800,
            boxShadow:`0 4px 20px ${tipo.accent}50`,
          }}>{loading?'Guardando...':esNuevo?'Registrar test':'Guardar'}</button>
        </div>
      </div>
    </div>
  )
}

// ── Card del carrusel ────────────────────────────────────────────────────────
function TestCard({ test, onEdit, onDelete, isCenter }) {
  const tipo = TIPO_TEST[test.tipo] || TIPO_TEST.umbral_run
  const [confirmDel, setConfirmDel] = useState(false)
  const d = test.datos || {}

  const metricas = []
  if (test.tipo==='umbral_run') {
    if (d.hr_umbral)    metricas.push({l:'LTHR',v:d.hr_umbral,u:'bpm',c:tipo.accent})
    if (d.pace_umbral)  metricas.push({l:'Pace',v:d.pace_umbral,u:'/km',c:'#fff'})
    if (d.vo2est)       metricas.push({l:'VO2',v:d.vo2est,u:'',c:'#10B981'})
  } else if (test.tipo==='umbral_bike') {
    if (d.potencia_ftp) metricas.push({l:'FTP',v:d.potencia_ftp,u:'W',c:tipo.accent})
    if (d.wkg)          metricas.push({l:'W/kg',v:d.wkg,u:'',c:'#fff'})
    if (d.hr_umbral)    metricas.push({l:'LTHR',v:d.hr_umbral,u:'bpm',c:'#F59E0B'})
  } else if (test.tipo==='umbral_swim') {
    if (d.css_calculado) metricas.push({l:'CSS',v:d.css_calculado,u:'/100m',c:tipo.accent})
    if (d.hr_umbral)     metricas.push({l:'HR',v:d.hr_umbral,u:'bpm',c:'#fff'})
  } else if (test.tipo==='potencia_bike') {
    if (d.watts_pico)   metricas.push({l:'Pico',v:d.watts_pico,u:'W',c:tipo.accent})
    if (d.duracion)     metricas.push({l:'Sprint',v:d.duracion,u:'s',c:'#fff'})
  } else {
    if (d.velocidad_max) metricas.push({l:'Vel.',v:d.velocidad_max,u:'km/h',c:tipo.accent})
    if (d.tiempo)        metricas.push({l:'Tiempo',v:d.tiempo,u:'',c:'#fff'})
    if (d.distancia)     metricas.push({l:'Dist.',v:d.distancia,u:'m',c:'rgba(255,255,255,0.6)'})
  }
  if (d.rpe) metricas.push({l:'RPE',v:d.rpe,u:'/10',c:'rgba(255,255,255,0.4)'})

  return (
    <div className={`test-card-wrap ${isCenter ? 'center-card' : 'side-card'}`}
      style={{
        flexShrink:0,width:260,
        borderRadius:20,overflow:'hidden',
        background:'rgba(13,17,23,0.85)',
        backdropFilter:'blur(20px)',
        border:`1px solid ${isCenter ? tipo.accent+'60' : 'rgba(255,255,255,0.08)'}`,
        boxShadow: isCenter
          ? `0 20px 60px rgba(0,0,0,0.7), 0 0 0 1px ${tipo.accent}30, inset 0 1px 0 rgba(255,255,255,0.1)`
          : '0 8px 30px rgba(0,0,0,0.5)',
        cursor:'pointer',
      }}
      onClick={()=>onEdit(test)}>

      {/* Imagen + overlay */}
      <div style={{height:140,position:'relative',overflow:'hidden'}}>
        <div style={{
          position:'absolute',inset:0,
          backgroundImage:`url(${tipo.bg})`,
          backgroundSize:'cover',backgroundPosition:'center',
          transition:'transform 0.4s ease',
        }}/>
        <div style={{
          position:'absolute',inset:0,
          background:`linear-gradient(to bottom, ${tipo.dark}88 0%, rgba(13,17,23,0.97) 100%)`,
        }}/>
        {/* Badge tipo */}
        <div style={{
          position:'absolute',top:12,left:12,
          padding:'4px 11px',borderRadius:99,
          background:'rgba(0,0,0,0.6)',
          backdropFilter:'blur(12px)',
          border:`1px solid ${tipo.accent}50`,
          fontSize:9,fontWeight:800,color:tipo.accent,
          textTransform:'uppercase',letterSpacing:1.5,
          zIndex:1,
        }}>{tipo.short}</div>
        {/* Fecha */}
        <div style={{
          position:'absolute',top:12,right:12,
          fontSize:9,color:'rgba(255,255,255,0.5)',
          zIndex:1,
        }}>{fmtFecha(test.fecha)}</div>
        {/* Título */}
        <div style={{
          position:'absolute',bottom:12,left:14,right:14,
          zIndex:1,
        }}>
          <div style={{fontSize:18,fontWeight:900,color:'#fff',lineHeight:1}}>
            {tipo.icon} {tipo.label}
          </div>
          {test.protocolo && (
            <div style={{fontSize:10,color:'rgba(255,255,255,0.4)',marginTop:3}}>
              {test.protocolo}
            </div>
          )}
        </div>
      </div>

      {/* Métricas en glass */}
      <div style={{padding:'14px 14px 10px'}}>
        {metricas.length > 0 ? (
          <div style={{display:'flex',flexWrap:'wrap',gap:6,marginBottom:10}}>
            {metricas.map((m,i) => (
              <div key={i} style={{
                flex:'1 1 70px',
                padding:'8px 10px',borderRadius:10,
                background:'rgba(255,255,255,0.05)',
                border:'1px solid rgba(255,255,255,0.08)',
                backdropFilter:'blur(8px)',
                textAlign:'center',
              }}>
                <div style={{fontSize:18,fontWeight:900,color:m.c,lineHeight:1}}>
                  {m.v}
                  {m.u&&<span style={{fontSize:8,fontWeight:500,marginLeft:2,opacity:0.7}}>{m.u}</span>}
                </div>
                <div style={{fontSize:8,color:'rgba(255,255,255,0.3)',marginTop:3,
                  textTransform:'uppercase',letterSpacing:0.8}}>
                  {m.l}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div style={{fontSize:11,color:'rgba(255,255,255,0.25)',marginBottom:10,textAlign:'center',padding:'8px 0'}}>
            Sin datos registrados
          </div>
        )}

        {d.notas && (
          <div style={{
            fontSize:10,color:'rgba(255,255,255,0.3)',
            borderTop:'1px solid rgba(255,255,255,0.06)',
            paddingTop:8,marginBottom:8,
            overflow:'hidden',textOverflow:'ellipsis',
            display:'-webkit-box',WebkitLineClamp:2,WebkitBoxOrient:'vertical',
          }}>{d.notas}</div>
        )}

        <div style={{display:'flex',justifyContent:'flex-end'}}
          onClick={e=>e.stopPropagation()}>
          <button onClick={()=>{
            if(!confirmDel){setConfirmDel(true);setTimeout(()=>setConfirmDel(false),3000);return}
            onDelete(test.id)
          }} style={{
            padding:'3px 10px',borderRadius:6,fontSize:10,fontWeight:600,cursor:'pointer',
            border:`1px solid ${confirmDel?'#EF444455':'rgba(255,255,255,0.07)'}`,
            background:confirmDel?'rgba(239,68,68,0.15)':'transparent',
            color:confirmDel?'#EF4444':'rgba(255,255,255,0.2)',
            transition:'all 0.2s',
          }}>{confirmDel?'¿Confirmar?':'🗑'}</button>
        </div>
      </div>
    </div>
  )
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function SeccionTests({ atletaId, modoAtleta = false }) {
  const [tests, setTests]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [modal, setModal]       = useState(null)
  const [activeIdx, setActiveIdx] = useState(0)
  const trackRef = useRef(null)

  const cargar = async () => {
    setLoading(true)
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/tests`)
      const j = await r.json()
      const lista = j.data?.tests || []
      setTests(lista)
      if (lista.length > 0) setActiveIdx(0)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { if (atletaId) cargar() }, [atletaId])

  const borrar = async (id) => {
    try {
      await authFetch(`${API}/atletas/${atletaId}/tests/${id}`, {method:'DELETE'})
      cargar()
    } catch { alert('Error al borrar') }
  }

  const goTo = (idx) => {
    const clamp = Math.max(0, Math.min(tests.length - 1, idx))
    setActiveIdx(clamp)
    if (trackRef.current) {
      const cardW = 276
      const offset = clamp * cardW - (trackRef.current.offsetWidth / 2 - cardW / 2)
      trackRef.current.scrollTo({ left: offset, behavior: 'smooth' })
    }
  }

  // Umbrales actuales
  const ordenados = [...tests].sort((a,b) => b.fecha > a.fecha ? 1 : -1)
  const ultimoRun  = tests.filter(t=>t.tipo==='umbral_run').sort((a,b)=>b.fecha>a.fecha?1:-1)[0]
  const ultimoBike = tests.filter(t=>t.tipo==='umbral_bike').sort((a,b)=>b.fecha>a.fecha?1:-1)[0]
  const ultimoSwim = tests.filter(t=>t.tipo==='umbral_swim').sort((a,b)=>b.fecha>a.fecha?1:-1)[0]

  return (
    <>
      <style>{STYLES}</style>
      <div style={{display:'flex',flexDirection:'column',gap:20}}>

        {/* Header */}
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:10}}>
          <div>
            <div style={{fontSize:17,fontWeight:900,color:'#E6EDF3',marginBottom:2,letterSpacing:-0.3}}>
              🔬 Tests de Umbral
            </div>
            <div style={{fontSize:11,color:'rgba(255,255,255,0.3)'}}>
              {tests.length} tests registrados
            </div>
          </div>
          <button onClick={()=>setModal('nuevo')} className="glass-btn" style={{
            padding:'9px 20px',borderRadius:12,
            border:'1px solid rgba(139,92,246,0.4)',
            background:'rgba(139,92,246,0.15)',
            backdropFilter:'blur(12px)',
            color:'#A78BFA',cursor:'pointer',
            fontSize:13,fontWeight:700,
            boxShadow:'0 4px 20px rgba(139,92,246,0.2)',
          }}>+ Registrar test</button>
        </div>

        {/* Resumen umbrales vigentes */}
        {(ultimoRun || ultimoBike || ultimoSwim) && (
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:10}}>
            {[
              {t:ultimoRun,  cfg:TIPO_TEST.umbral_run,  key:'hr_umbral',    lbl:'LTHR Run',  sub: d=>d.pace_umbral?`${d.pace_umbral}/km`:''},
              {t:ultimoBike, cfg:TIPO_TEST.umbral_bike, key:'potencia_ftp', lbl:'FTP Bike',  sub: d=>d.wkg?`${d.wkg} W/kg`:''},
              {t:ultimoSwim, cfg:TIPO_TEST.umbral_swim, key:'css_calculado',lbl:'CSS Swim',  sub: d=>d.hr_umbral?`HR ${d.hr_umbral}`:''},
            ].map(({t,cfg,key,lbl,sub},i) => t ? (
              <div key={i} style={{
                borderRadius:14,padding:'16px 18px',
                background:'rgba(13,17,23,0.8)',
                backdropFilter:'blur(20px)',
                border:`1px solid ${cfg.accent}25`,
                position:'relative',overflow:'hidden',
                boxShadow:`0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)`,
              }}>
                <div style={{
                  position:'absolute',inset:0,
                  backgroundImage:`url(${cfg.bg})`,
                  backgroundSize:'cover',backgroundPosition:'center',
                  opacity:0.08,
                }}/>
                <div style={{
                  position:'absolute',inset:0,
                  background:`linear-gradient(135deg,${cfg.dark}cc,transparent)`,
                }}/>
                <div style={{position:'relative',zIndex:1}}>
                  <div style={{fontSize:9,fontWeight:800,color:cfg.accent,
                    textTransform:'uppercase',letterSpacing:2,marginBottom:8}}>
                    {lbl} · ACTUAL
                  </div>
                  <div style={{fontSize:32,fontWeight:900,color:'#fff',lineHeight:1,marginBottom:4}}>
                    {t.datos?.[key]||'--'}
                  </div>
                  <div style={{fontSize:10,color:'rgba(255,255,255,0.4)'}}>
                    {sub(t.datos||'')} · {fmtFecha(t.fecha)}
                  </div>
                </div>
              </div>
            ) : (
              <div key={i} style={{
                borderRadius:14,padding:'16px 18px',
                background:'rgba(255,255,255,0.02)',
                border:'1px dashed rgba(255,255,255,0.07)',
                display:'flex',alignItems:'center',justifyContent:'center',
              }}>
                <div style={{fontSize:11,color:'rgba(255,255,255,0.15)'}}>Sin test</div>
              </div>
            ))}
          </div>
        )}

        {/* Carrusel 3D */}
        <div style={{position:'relative'}}>
          {/* Track */}
          <div ref={trackRef} className="carousel-track" style={{
            display:'flex',gap:16,
            overflowX:'auto',
            padding:'20px 40px 24px',
            alignItems:'center',
          }}>
            {loading && (
              <div style={{color:'rgba(255,255,255,0.25)',fontSize:13,padding:'40px 0',width:'100%',textAlign:'center'}}>
                Cargando tests...
              </div>
            )}

            {!loading && ordenados.length === 0 && (
              <div style={{
                width:260,height:220,borderRadius:20,flexShrink:0,
                border:'2px dashed rgba(255,255,255,0.08)',
                background:'rgba(255,255,255,0.015)',
                display:'flex',flexDirection:'column',
                alignItems:'center',justifyContent:'center',gap:10,
              }}>
                <div style={{fontSize:36,opacity:0.3}}>🔬</div>
                <div style={{fontSize:12,color:'rgba(255,255,255,0.2)'}}>Sin tests</div>
              </div>
            )}

            {!loading && ordenados.map((t,i) => (
              <div key={t.id} onClick={()=>goTo(i)} style={{flexShrink:0}}>
                <TestCard
                  test={t}
                  onEdit={t=>setModal(t)}
                  onDelete={borrar}
                  isCenter={i===activeIdx}
                />
              </div>
            ))}

            {/* Card agregar */}
            {!loading && (
              <div onClick={()=>setModal('nuevo')} className="test-card-wrap" style={{
                flexShrink:0,width:260,height:280,borderRadius:20,
                cursor:'pointer',
                border:'2px dashed rgba(139,92,246,0.2)',
                background:'rgba(139,92,246,0.03)',
                backdropFilter:'blur(12px)',
                display:'flex',flexDirection:'column',
                alignItems:'center',justifyContent:'center',gap:12,
              }}>
                <div style={{
                  width:52,height:52,borderRadius:16,
                  background:'rgba(139,92,246,0.12)',
                  border:'1px solid rgba(139,92,246,0.25)',
                  display:'flex',alignItems:'center',justifyContent:'center',
                  fontSize:26,
                  boxShadow:'0 4px 20px rgba(139,92,246,0.15)',
                }}>+</div>
                <div style={{fontSize:12,fontWeight:700,color:'rgba(139,92,246,0.6)'}}>
                  Nuevo test
                </div>
              </div>
            )}
          </div>

          {/* Navegación */}
          {ordenados.length > 1 && (
            <>
              <button onClick={()=>goTo(activeIdx-1)} className="glass-btn" style={{
                position:'absolute',left:0,top:'50%',transform:'translateY(-50%)',
                zIndex:10,width:36,height:36,borderRadius:'50%',
                background:'rgba(13,17,23,0.9)',
                border:'1px solid rgba(255,255,255,0.12)',
                color:'#fff',cursor:'pointer',fontSize:18,
                display:'flex',alignItems:'center',justifyContent:'center',
                backdropFilter:'blur(12px)',
              }}>‹</button>
              <button onClick={()=>goTo(activeIdx+1)} className="glass-btn" style={{
                position:'absolute',right:0,top:'50%',transform:'translateY(-50%)',
                zIndex:10,width:36,height:36,borderRadius:'50%',
                background:'rgba(13,17,23,0.9)',
                border:'1px solid rgba(255,255,255,0.12)',
                color:'#fff',cursor:'pointer',fontSize:18,
                display:'flex',alignItems:'center',justifyContent:'center',
                backdropFilter:'blur(12px)',
              }}>›</button>
            </>
          )}

          {/* Dots */}
          {ordenados.length > 1 && (
            <div style={{display:'flex',justifyContent:'center',gap:6,paddingTop:4}}>
              {ordenados.map((_,i) => (
                <button key={i} onClick={()=>goTo(i)} style={{
                  width: i===activeIdx ? 20 : 6,
                  height:6,borderRadius:99,border:'none',cursor:'pointer',
                  background: i===activeIdx ? '#8B5CF6' : 'rgba(255,255,255,0.15)',
                  transition:'all 0.3s ease',padding:0,
                }}/>
              ))}
            </div>
          )}
        </div>

        {modal && (
          <ModalTest
            test={modal==='nuevo'?null:modal}
            atletaId={atletaId}
            onClose={()=>setModal(null)}
            onGuardado={cargar}
          />
        )}
      </div>
    </>
  )
}

const lbl = {
  display:'block',fontSize:10,fontWeight:600,
  color:'rgba(255,255,255,0.35)',textTransform:'uppercase',
  letterSpacing:0.8,marginBottom:5,
}
const inp = {
  width:'100%',padding:'9px 12px',
  background:'rgba(255,255,255,0.06)',
  border:'1px solid rgba(255,255,255,0.1)',
  borderRadius:9,color:'#E6EDF3',fontSize:13,
  outline:'none',fontFamily:'inherit',
  boxSizing:'border-box',
  transition:'border-color 0.2s',
}
