// OnboardingAtleta.jsx — NOA Onboarding v1
// Wizard de alta de atleta: carrusel de secciones con glassmorphism
import { useState, useRef, useEffect } from 'react'

const API = 'http://localhost:5000/api'

// ── Estilos globales ──────────────────────────────────────────────────────────
const STYLES = `
  @keyframes ob-fadeIn  { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }
  @keyframes ob-pulse   { 0%,100%{opacity:1} 50%{opacity:0.5} }
  @keyframes ob-shimmer { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
  .ob-card {
    transition: transform 0.4s cubic-bezier(.22,.68,0,1.15), box-shadow 0.35s ease, opacity 0.35s ease;
    cursor: pointer;
  }
  .ob-card.active {
    transform: scale(1.04) translateY(-6px) !important;
    z-index: 4;
  }
  .ob-card.side {
    transform: scale(0.88) translateY(12px) !important;
    opacity: 0.6;
    z-index: 1;
  }
  .ob-card.far {
    transform: scale(0.78) translateY(22px) !important;
    opacity: 0.35;
    z-index: 0;
  }
  .ob-card:hover { filter: brightness(1.08); }
  .ob-input:focus {
    border-color: rgba(139,92,246,0.6) !important;
    box-shadow: 0 0 0 3px rgba(139,92,246,0.12);
    outline: none;
  }
  .ob-btn-main {
    transition: all 0.25s ease;
  }
  .ob-btn-main:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 28px rgba(139,92,246,0.45) !important;
  }
  .ob-btn-main:active { transform: translateY(0); }
  .ob-section-track::-webkit-scrollbar { display:none; }
  .ob-section-track { -ms-overflow-style:none; scrollbar-width:none; }
`

// ── Configuración de secciones ────────────────────────────────────────────────
const SECCIONES = [
  {
    id: 'personal',
    titulo: 'Datos Personales',
    subtitulo: 'Identidad y contacto del atleta',
    icon: '👤',
    bg: 'https://images.unsplash.com/photo-1517649763962-0c623066013b?w=800&q=80',
    gradient: 'linear-gradient(135deg,#0f0c29,#302b63,#24243e)',
    accent: '#A78BFA',
    required: true,
  },
  {
    id: 'deportivo',
    titulo: 'Perfil Deportivo',
    subtitulo: 'Deporte, nivel y disponibilidad',
    icon: '🏃',
    bg: 'https://images.unsplash.com/photo-1571008887538-b36bb32f4571?w=800&q=80',
    gradient: 'linear-gradient(135deg,#1a0533,#4c1d95,#7c3aed)',
    accent: '#C4B5FD',
    required: true,
  },
  {
    id: 'umbrales',
    titulo: 'Umbrales Iniciales',
    subtitulo: 'LTHR, FTP y CSS si los conoce',
    icon: '📊',
    bg: 'https://images.unsplash.com/photo-1526506118085-60ce8714f8c5?w=800&q=80',
    gradient: 'linear-gradient(135deg,#0a1628,#0369a1,#0ea5e9)',
    accent: '#7DD3FC',
    required: false,
  },
  {
    id: 'carrera',
    titulo: 'Carrera Objetivo',
    subtitulo: 'La carrera principal del ciclo',
    icon: '🏁',
    bg: 'https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=800&q=80',
    gradient: 'linear-gradient(135deg,#1c1400,#92400e,#d97706)',
    accent: '#FCD34D',
    required: false,
  },
]

const NIVEL_OPTS = ['Principiante','Intermedio','Avanzado','Élite']
const DEPORTE_OPTS = [
  {v:'running',   l:'Running',   e:'🏃'},
  {v:'triatlon',  l:'Triatlón',  e:'🏊'},
  {v:'cycling',   l:'Ciclismo',  e:'🚴'},
  {v:'swimming',  l:'Natación',  e:'🏊'},
]

// ── Formularios por sección ───────────────────────────────────────────────────
function FormPersonal({ data, onChange }) {
  const f = (k,v) => onChange({...data,[k]:v})
  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,animation:'ob-fadeIn 0.3s ease'}}>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
        <div style={{gridColumn:'1/-1'}}>
          <label style={lbl}>Nombre completo *</label>
          <input className="ob-input" style={inp} value={data.nombre||''}
            onChange={e=>f('nombre',e.target.value)} placeholder="Ej: María González"/>
        </div>
        <div>
          <label style={lbl}>Email *</label>
          <input className="ob-input" style={inp} type="email" value={data.email||''}
            onChange={e=>f('email',e.target.value)} placeholder="maria@email.com"/>
        </div>
        <div>
          <label style={lbl}>Teléfono</label>
          <input className="ob-input" style={inp} value={data.telefono||''}
            onChange={e=>f('telefono',e.target.value)} placeholder="+54 11 1234-5678"/>
        </div>
        <div>
          <label style={lbl}>Edad</label>
          <input className="ob-input" style={inp} type="number" value={data.edad||''}
            onChange={e=>f('edad',e.target.value)} placeholder="32"/>
        </div>
        <div>
          <label style={lbl}>Sexo</label>
          <select className="ob-input" style={inp} value={data.sexo||''}
            onChange={e=>f('sexo',e.target.value)}>
            <option value="">Seleccionar</option>
            <option value="M">Masculino</option>
            <option value="F">Femenino</option>
            <option value="O">Otro</option>
          </select>
        </div>
        <div>
          <label style={lbl}>Ciudad</label>
          <input className="ob-input" style={inp} value={data.ciudad||''}
            onChange={e=>f('ciudad',e.target.value)} placeholder="Buenos Aires"/>
        </div>
        <div>
          <label style={lbl}>País</label>
          <input className="ob-input" style={inp} value={data.pais||'Argentina'}
            onChange={e=>f('pais',e.target.value)} placeholder="Argentina"/>
        </div>
      </div>
    </div>
  )
}

function FormDeportivo({ data, onChange }) {
  const f = (k,v) => onChange({...data,[k]:v})
  return (
    <div style={{display:'flex',flexDirection:'column',gap:16,animation:'ob-fadeIn 0.3s ease'}}>

      {/* Selector deporte */}
      <div>
        <label style={lbl}>Deporte principal *</label>
        <div style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:8,marginTop:6}}>
          {DEPORTE_OPTS.map(d => (
            <button key={d.v} onClick={()=>f('deporte_ppal',d.v)} style={{
              padding:'14px 8px',borderRadius:12,cursor:'pointer',
              border:`1px solid ${data.deporte_ppal===d.v ? '#8B5CF6' : 'rgba(255,255,255,0.1)'}`,
              background: data.deporte_ppal===d.v ? 'rgba(139,92,246,0.2)' : 'rgba(255,255,255,0.04)',
              color: data.deporte_ppal===d.v ? '#C4B5FD' : 'rgba(255,255,255,0.5)',
              transition:'all 0.2s',
              display:'flex',flexDirection:'column',alignItems:'center',gap:6,
            }}>
              <span style={{fontSize:24}}>{d.e}</span>
              <span style={{fontSize:10,fontWeight:700,letterSpacing:0.5}}>{d.l}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Nivel */}
      <div>
        <label style={lbl}>Nivel</label>
        <div style={{display:'flex',gap:6,flexWrap:'wrap',marginTop:6}}>
          {NIVEL_OPTS.map(n => (
            <button key={n} onClick={()=>f('nivel',n)} style={{
              padding:'6px 14px',borderRadius:99,cursor:'pointer',fontSize:12,fontWeight:600,
              border:`1px solid ${data.nivel===n ? '#8B5CF6' : 'rgba(255,255,255,0.1)'}`,
              background: data.nivel===n ? 'rgba(139,92,246,0.2)' : 'transparent',
              color: data.nivel===n ? '#C4B5FD' : 'rgba(255,255,255,0.4)',
              transition:'all 0.15s',
            }}>{n}</button>
          ))}
        </div>
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
        <div>
          <label style={lbl}>Años de experiencia</label>
          <input className="ob-input" style={inp} type="number" value={data.anos_exp||''}
            onChange={e=>f('anos_exp',e.target.value)} placeholder="5"/>
        </div>
        <div>
          <label style={lbl}>Hs semanales disponibles</label>
          <input className="ob-input" style={inp} type="number" value={data.horas_semana||''}
            onChange={e=>f('horas_semana',e.target.value)} placeholder="10"/>
        </div>
        <div>
          <label style={lbl}>Garmin Connect email</label>
          <input className="ob-input" style={inp} value={data.garmin_email||''}
            onChange={e=>f('garmin_email',e.target.value)} placeholder="garmin@email.com"/>
        </div>
        <div>
          <label style={lbl}>Garmin Connect password</label>
          <input className="ob-input" style={inp} type="password" value={data.garmin_password||''}
            onChange={e=>f('garmin_password',e.target.value)} placeholder="••••••••"/>
        </div>
        <div style={{gridColumn:'1/-1'}}>
          <label style={lbl}>Notas del coach</label>
          <textarea className="ob-input" style={{...inp,minHeight:72,resize:'vertical'}}
            value={data.notas||''} onChange={e=>f('notas',e.target.value)}
            placeholder="Lesiones, historial, objetivos generales..."/>
        </div>
      </div>
    </div>
  )
}

function FormUmbrales({ data, onChange }) {
  const f = (k,v) => onChange({...data,[k]:v})
  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,animation:'ob-fadeIn 0.3s ease'}}>
      <div style={{
        padding:'10px 14px',borderRadius:10,
        background:'rgba(125,211,252,0.08)',
        border:'1px solid rgba(125,211,252,0.2)',
        fontSize:12,color:'rgba(255,255,255,0.5)',
      }}>
        Opcional — si no los conoce, NOAH los estimará con el historial de Garmin
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
        <div>
          <label style={lbl}>LTHR Running <span style={{color:'rgba(255,255,255,0.2)',fontWeight:400}}>(bpm)</span></label>
          <input className="ob-input" style={inp} type="number" value={data.lthr_run||''}
            onChange={e=>f('lthr_run',e.target.value)} placeholder="162"/>
        </div>
        <div>
          <label style={lbl}>LTHR Ciclismo <span style={{color:'rgba(255,255,255,0.2)',fontWeight:400}}>(bpm)</span></label>
          <input className="ob-input" style={inp} type="number" value={data.lthr_bike||''}
            onChange={e=>f('lthr_bike',e.target.value)} placeholder="155"/>
        </div>
        <div>
          <label style={lbl}>FC Máxima <span style={{color:'rgba(255,255,255,0.2)',fontWeight:400}}>(bpm)</span></label>
          <input className="ob-input" style={inp} type="number" value={data.hr_max||''}
            onChange={e=>f('hr_max',e.target.value)} placeholder="185"/>
        </div>
        <div>
          <label style={lbl}>FTP Ciclismo <span style={{color:'rgba(255,255,255,0.2)',fontWeight:400}}>(W)</span></label>
          <input className="ob-input" style={inp} type="number" value={data.ftp||''}
            onChange={e=>f('ftp',e.target.value)} placeholder="250"/>
        </div>
        <div>
          <label style={lbl}>CSS Natación <span style={{color:'rgba(255,255,255,0.2)',fontWeight:400}}>(min/100m)</span></label>
          <input className="ob-input" style={inp} value={data.css||''}
            onChange={e=>f('css',e.target.value)} placeholder="1:45"/>
        </div>
        <div>
          <label style={lbl}>Peso <span style={{color:'rgba(255,255,255,0.2)',fontWeight:400}}>(kg)</span></label>
          <input className="ob-input" style={inp} type="number" value={data.peso||''}
            onChange={e=>f('peso',e.target.value)} placeholder="70"/>
        </div>
      </div>
    </div>
  )
}

function FormCarrera({ data, onChange }) {
  const f = (k,v) => onChange({...data,[k]:v})
  return (
    <div style={{display:'flex',flexDirection:'column',gap:14,animation:'ob-fadeIn 0.3s ease'}}>
      <div style={{
        padding:'10px 14px',borderRadius:10,
        background:'rgba(252,211,77,0.08)',
        border:'1px solid rgba(252,211,77,0.2)',
        fontSize:12,color:'rgba(255,255,255,0.5)',
      }}>
        Opcional — se creará automáticamente como Prioridad A en la sección Race
      </div>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12}}>
        <div style={{gridColumn:'1/-1'}}>
          <label style={lbl}>Nombre de la carrera</label>
          <input className="ob-input" style={inp} value={data.nombre||''}
            onChange={e=>f('nombre',e.target.value)} placeholder="Ironman 70.3 Buenos Aires"/>
        </div>
        <div>
          <label style={lbl}>Fecha</label>
          <input className="ob-input" style={inp} type="date" value={data.fecha||''}
            onChange={e=>f('fecha',e.target.value)}/>
        </div>
        <div>
          <label style={lbl}>Ciudad</label>
          <input className="ob-input" style={inp} value={data.ciudad||''}
            onChange={e=>f('ciudad',e.target.value)} placeholder="Buenos Aires"/>
        </div>
        <div>
          <label style={lbl}>Distancia / Modalidad</label>
          <input className="ob-input" style={inp} value={data.distancia||''}
            onChange={e=>f('distancia',e.target.value)} placeholder="70.3 / 42K / Sprint"/>
        </div>
        <div>
          <label style={lbl}>CTL objetivo</label>
          <input className="ob-input" style={inp} type="number" value={data.ctl_objetivo||''}
            onChange={e=>f('ctl_objetivo',e.target.value)} placeholder="75"/>
        </div>
        <div style={{gridColumn:'1/-1'}}>
          <label style={lbl}>Notas</label>
          <textarea className="ob-input" style={{...inp,minHeight:64,resize:'vertical'}}
            value={data.notas_coach||''} onChange={e=>f('notas_coach',e.target.value)}
            placeholder="Objetivos, estrategia..."/>
        </div>
      </div>
    </div>
  )
}

// ── Card de sección en el carrusel ────────────────────────────────────────────
function SeccionCard({ sec, pos, completado, onClick }) {
  // pos: 'active' | 'side' | 'far'
  const className = `ob-card ${pos}`
  return (
    <div className={className} onClick={onClick} style={{
      flexShrink:0, width:220,
      borderRadius:20, overflow:'hidden',
      background:'rgba(13,17,23,0.85)',
      backdropFilter:'blur(20px)',
      border:`1px solid ${pos==='active' ? sec.accent+'80' : 'rgba(255,255,255,0.08)'}`,
      boxShadow: pos==='active'
        ? `0 24px 60px rgba(0,0,0,0.7), 0 0 0 1px ${sec.accent}30`
        : '0 8px 24px rgba(0,0,0,0.4)',
    }}>
      {/* Imagen */}
      <div style={{height:130,position:'relative',overflow:'hidden'}}>
        <div style={{
          position:'absolute',inset:0,
          backgroundImage:`url(${sec.bg})`,
          backgroundSize:'cover',backgroundPosition:'center',
          opacity: pos==='active' ? 0.55 : 0.25,
          transition:'opacity 0.3s',
        }}/>
        <div style={{
          position:'absolute',inset:0,
          background:`linear-gradient(to bottom,${sec.gradient.split(',')[1]?.trim()||'#000'}88,rgba(13,17,23,0.97))`,
        }}/>
        {/* Check si completado */}
        {completado && (
          <div style={{
            position:'absolute',top:10,right:10,
            width:24,height:24,borderRadius:'50%',
            background:'#10B981',
            display:'flex',alignItems:'center',justifyContent:'center',
            fontSize:13,fontWeight:700,color:'#fff',
            boxShadow:'0 2px 8px rgba(16,185,129,0.5)',
            zIndex:2,
          }}>✓</div>
        )}
        {!sec.required && (
          <div style={{
            position:'absolute',top:10,left:10,
            padding:'2px 8px',borderRadius:99,
            background:'rgba(0,0,0,0.5)',
            border:'1px solid rgba(255,255,255,0.1)',
            fontSize:8,fontWeight:700,color:'rgba(255,255,255,0.4)',
            textTransform:'uppercase',letterSpacing:1,zIndex:2,
          }}>Opcional</div>
        )}
        <div style={{
          position:'absolute',bottom:10,left:14,zIndex:1,
        }}>
          <div style={{fontSize:28,marginBottom:4}}>{sec.icon}</div>
        </div>
      </div>
      {/* Texto */}
      <div style={{padding:'12px 14px 14px'}}>
        <div style={{
          fontSize:13,fontWeight:800,
          color: pos==='active' ? '#fff' : 'rgba(255,255,255,0.6)',
          marginBottom:4,lineHeight:1.2,
        }}>{sec.titulo}</div>
        <div style={{fontSize:10,color:'rgba(255,255,255,0.3)',lineHeight:1.4}}>
          {sec.subtitulo}
        </div>
        {pos==='active' && (
          <div style={{
            marginTop:10,
            padding:'4px 10px',borderRadius:99,
            background:`${sec.accent}18`,
            border:`1px solid ${sec.accent}30`,
            fontSize:9,fontWeight:700,color:sec.accent,
            display:'inline-block',textTransform:'uppercase',letterSpacing:1,
          }}>
            {completado ? 'Completado ✓' : 'Completar →'}
          </div>
        )}
      </div>
    </div>
  )
}

// ── Panel de éxito ────────────────────────────────────────────────────────────
function PantallaExito({ atleta, onClose }) {
  return (
    <div style={{
      display:'flex',flexDirection:'column',alignItems:'center',
      justifyContent:'center',gap:20,padding:'40px 24px',
      textAlign:'center',animation:'ob-fadeIn 0.5s ease',
    }}>
      <div style={{
        width:80,height:80,borderRadius:'50%',
        background:'linear-gradient(135deg,#10B981,#059669)',
        display:'flex',alignItems:'center',justifyContent:'center',
        fontSize:40,
        boxShadow:'0 8px 32px rgba(16,185,129,0.4)',
      }}>✓</div>
      <div>
        <div style={{fontSize:24,fontWeight:900,color:'#fff',marginBottom:8}}>
          ¡{atleta.nombre} fue creado!
        </div>
        <div style={{fontSize:13,color:'rgba(255,255,255,0.5)',lineHeight:1.6,maxWidth:380}}>
          El atleta ya aparece en el dashboard. Para activar NOAH completamente,
          ejecutá los siguientes comandos:
        </div>
      </div>

      {/* Comandos */}
      <div style={{
        width:'100%',maxWidth:460,
        background:'rgba(0,0,0,0.4)',
        border:'1px solid rgba(255,255,255,0.1)',
        borderRadius:12,padding:'16px 18px',
        textAlign:'left',
      }}>
        <div style={{fontSize:10,fontWeight:700,color:'rgba(255,255,255,0.4)',
          textTransform:'uppercase',letterSpacing:1,marginBottom:10}}>
          Próximos pasos
        </div>
        {[
          {cmd:`python sincronizar_garmin.py --atleta ${atleta.id} --modo bio --fecha hoy`, desc:'Bajar biomarcadores históricos'},
          {cmd:`python sincronizar_garmin.py --atleta ${atleta.id} --modo actividad --fecha hoy`, desc:'Bajar actividades Garmin'},
          {cmd:`python noah_hanna_life.py --atleta ${atleta.id} --todo --db noa.db`, desc:'Calcular HANNA LIFE'},
        ].map((c,i) => (
          <div key={i} style={{marginBottom:10}}>
            <div style={{fontSize:10,color:'rgba(255,255,255,0.3)',marginBottom:3}}>{c.desc}</div>
            <div style={{
              padding:'7px 12px',borderRadius:7,
              background:'rgba(255,255,255,0.04)',
              border:'1px solid rgba(255,255,255,0.08)',
              fontFamily:'monospace',fontSize:11,
              color:'#7DD3FC',wordBreak:'break-all',
            }}>{c.cmd}</div>
          </div>
        ))}
      </div>

      <button onClick={onClose} className="ob-btn-main" style={{
        padding:'12px 32px',borderRadius:12,
        border:'none',background:'linear-gradient(135deg,#7c3aed,#4f46e5)',
        color:'#fff',cursor:'pointer',fontSize:14,fontWeight:800,
        boxShadow:'0 4px 20px rgba(124,58,237,0.4)',
      }}>Ir al dashboard</button>
    </div>
  )
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function OnboardingAtleta({ onClose, onCreado }) {
  const [activeIdx, setActiveIdx]   = useState(0)
  const [completados, setCompletados] = useState({})
  const [exito, setExito]           = useState(null)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')
  const trackRef = useRef(null)

  // Datos por sección
  const [personal,  setPersonal]  = useState({ pais: 'Argentina' })
  const [deportivo, setDeportivo] = useState({ deporte_ppal: 'running' })
  const [umbrales,  setUmbrales]  = useState({})
  const [carrera,   setCarrera]   = useState({})

  const dataSec = { personal, deportivo, umbrales, carrera }
  const setDataSec = { personal:setPersonal, deportivo:setDeportivo, umbrales:setUmbrales, carrera:setCarrera }

  const secActiva = SECCIONES[activeIdx]

  // Sincronizar carrusel al cambiar sección
  useEffect(() => {
    if (!trackRef.current) return
    const cardW = 236
    const offset = activeIdx * cardW - (trackRef.current.offsetWidth / 2 - cardW / 2)
    trackRef.current.scrollTo({ left: offset, behavior: 'smooth' })
  }, [activeIdx])

  const marcarCompletado = () => {
    setCompletados(p => ({...p, [secActiva.id]: true}))
  }

  const posCard = (i) => {
    const diff = i - activeIdx
    if (diff === 0) return 'active'
    if (Math.abs(diff) === 1) return 'side'
    return 'far'
  }

  const guardar = async () => {
    if (!personal.nombre?.trim()) { setError('El nombre es requerido'); return }
    if (!personal.email?.trim())  { setError('El email es requerido'); return }
    setError('')
    setLoading(true)
    try {
      // 1. Crear atleta
      const body = {
        nombre:         personal.nombre.trim(),
        email:          personal.email.trim(),
        edad:           personal.edad || null,
        sexo:           personal.sexo || null,
        ciudad:         personal.ciudad || null,
        pais:           personal.pais || 'Argentina',
        telefono:       personal.telefono || null,
        deporte_ppal:   deportivo.deporte_ppal || 'running',
        nivel:          deportivo.nivel || null,
        anos_exp:       deportivo.anos_exp || null,
        horas_semana:   deportivo.horas_semana || null,
        garmin_email:   deportivo.garmin_email || null,
        garmin_password:deportivo.garmin_password || null,
        notas:          deportivo.notas || null,
        lthr_run:       umbrales.lthr_run || null,
        lthr_bike:      umbrales.lthr_bike || null,
        hr_max:         umbrales.hr_max || null,
        ftp:            umbrales.ftp || null,
        css:            umbrales.css || null,
        peso:           umbrales.peso || null,
      }

      const r = await fetch(`${API}/atletas`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify(body),
      })
      const j = await r.json()
      if (!j.ok && !j.data?.id) throw new Error(j.error || 'Error al crear atleta')

      const atletaId = j.data?.id || j.id

      // 2. Crear test de umbral si tiene datos
      const tieneUmbrales = umbrales.lthr_run || umbrales.lthr_bike || umbrales.ftp || umbrales.css
      if (tieneUmbrales && atletaId) {
        await fetch(`${API}/atletas/${atletaId}/tests`, {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            tipo: deportivo.deporte_ppal === 'cycling' ? 'umbral_bike'
                : deportivo.deporte_ppal === 'swimming' ? 'umbral_swim'
                : 'umbral_run',
            fecha: new Date().toISOString().slice(0,10),
            protocolo: 'Inicial al alta',
            actualizar_perfil: true,
            datos: {
              hr_umbral:     umbrales.lthr_run || umbrales.lthr_bike,
              potencia_ftp:  umbrales.ftp,
              css_calculado: umbrales.css,
            },
          }),
        }).catch(()=>{})
      }

      // 3. Crear carrera objetivo si tiene datos
      if (carrera.nombre && carrera.fecha && atletaId) {
        await fetch(`${API}/atletas/${atletaId}/carreras`, {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({
            nombre:      carrera.nombre,
            fecha:       carrera.fecha,
            deporte:     deportivo.deporte_ppal || 'running',
            distancia:   carrera.distancia || '',
            ciudad:      carrera.ciudad || '',
            prioridad:   'A',
            ctl_objetivo:carrera.ctl_objetivo || null,
            notas_coach: carrera.notas_coach || '',
            estado:      'pendiente',
          }),
        }).catch(()=>{})
      }

      setExito({ nombre: personal.nombre, id: atletaId })
      onCreado?.()
    } catch(e) {
      setError(e.message || 'Error al guardar')
    }
    setLoading(false)
  }

  const canSave = personal.nombre?.trim() && personal.email?.trim()

  return (
    <>
      <style>{STYLES}</style>
      <div style={{
        position:'fixed',inset:0,zIndex:200,
        background:'rgba(0,0,0,0.95)',
        backdropFilter:'blur(20px)',
        display:'flex',alignItems:'center',justifyContent:'center',
        animation:'ob-fadeIn 0.25s ease',
      }}>
        <div style={{
          width:680,maxWidth:'98vw',maxHeight:'96vh',
          borderRadius:24,overflow:'hidden',
          background:'rgba(10,12,20,0.98)',
          border:'1px solid rgba(255,255,255,0.1)',
          boxShadow:'0 40px 120px rgba(0,0,0,0.95)',
          display:'flex',flexDirection:'column',
        }}>

          {exito ? (
            <PantallaExito atleta={exito} onClose={()=>{ onClose?.() }} />
          ) : (
            <>
              {/* Header */}
              <div style={{
                padding:'22px 28px 16px',
                borderBottom:'1px solid rgba(255,255,255,0.07)',
                background:`linear-gradient(to bottom,${secActiva.gradient.split(',')[1]?.trim()||'#1a1a2e'}18,transparent)`,
                position:'relative',
              }}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                  <div>
                    <div style={{
                      fontSize:10,fontWeight:800,color:secActiva.accent,
                      textTransform:'uppercase',letterSpacing:2.5,marginBottom:6,
                    }}>Nuevo Atleta · NOAH</div>
                    <div style={{fontSize:22,fontWeight:900,color:'#fff',lineHeight:1}}>
                      Alta de atleta
                    </div>
                  </div>
                  <button onClick={onClose} style={{
                    width:36,height:36,borderRadius:10,
                    background:'rgba(255,255,255,0.08)',
                    border:'1px solid rgba(255,255,255,0.12)',
                    color:'rgba(255,255,255,0.6)',cursor:'pointer',fontSize:20,
                    display:'flex',alignItems:'center',justifyContent:'center',
                  }}>×</button>
                </div>

                {/* Barra de progreso */}
                <div style={{marginTop:14,display:'flex',gap:4}}>
                  {SECCIONES.map((s,i) => (
                    <div key={s.id} style={{
                      flex:1,height:3,borderRadius:99,overflow:'hidden',
                      background:'rgba(255,255,255,0.08)',
                    }}>
                      <div style={{
                        height:'100%',borderRadius:99,
                        background: completados[s.id] ? '#10B981'
                          : i===activeIdx ? secActiva.accent : 'transparent',
                        width: completados[s.id] ? '100%' : i===activeIdx ? '100%' : '0%',
                        transition:'width 0.4s ease, background 0.3s ease',
                      }}/>
                    </div>
                  ))}
                </div>
              </div>

              {/* Carrusel de secciones */}
              <div ref={trackRef} className="ob-section-track" style={{
                display:'flex',gap:16,
                overflowX:'auto',
                padding:'24px 40px',
                alignItems:'center',
                flexShrink:0,
              }}>
                {SECCIONES.map((s,i) => (
                  <SeccionCard
                    key={s.id}
                    sec={s}
                    pos={posCard(i)}
                    completado={!!completados[s.id]}
                    onClick={()=>setActiveIdx(i)}
                  />
                ))}
              </div>

              {/* Dots */}
              <div style={{display:'flex',justifyContent:'center',gap:6,marginTop:-12,marginBottom:4}}>
                {SECCIONES.map((_,i) => (
                  <button key={i} onClick={()=>setActiveIdx(i)} style={{
                    width: i===activeIdx ? 20 : 6,
                    height:6,borderRadius:99,border:'none',cursor:'pointer',
                    background: i===activeIdx ? secActiva.accent : 'rgba(255,255,255,0.15)',
                    transition:'all 0.3s ease',padding:0,
                  }}/>
                ))}
              </div>

              {/* Formulario activo */}
              <div style={{
                flex:1,overflow:'auto',
                padding:'16px 28px 8px',
              }}>
                <div style={{
                  fontSize:14,fontWeight:800,color:'#fff',marginBottom:4,
                  display:'flex',alignItems:'center',gap:8,
                }}>
                  <span>{secActiva.icon}</span>
                  <span>{secActiva.titulo}</span>
                  {!secActiva.required && (
                    <span style={{
                      fontSize:9,fontWeight:700,padding:'2px 8px',borderRadius:99,
                      background:'rgba(255,255,255,0.06)',
                      border:'1px solid rgba(255,255,255,0.1)',
                      color:'rgba(255,255,255,0.35)',
                      textTransform:'uppercase',letterSpacing:1,
                    }}>Opcional</span>
                  )}
                </div>
                <div style={{fontSize:11,color:'rgba(255,255,255,0.35)',marginBottom:16}}>
                  {secActiva.subtitulo}
                </div>

                {activeIdx===0 && <FormPersonal  data={personal}  onChange={setPersonal}/>}
                {activeIdx===1 && <FormDeportivo data={deportivo} onChange={setDeportivo}/>}
                {activeIdx===2 && <FormUmbrales  data={umbrales}  onChange={setUmbrales}/>}
                {activeIdx===3 && <FormCarrera   data={carrera}   onChange={setCarrera}/>}
              </div>

              {/* Footer */}
              <div style={{
                padding:'14px 28px',
                borderTop:'1px solid rgba(255,255,255,0.07)',
                display:'flex',alignItems:'center',gap:10,
                background:'rgba(0,0,0,0.2)',
                flexWrap:'wrap',
              }}>
                {error && (
                  <div style={{
                    fontSize:12,color:'#F87171',
                    padding:'4px 12px',borderRadius:8,
                    background:'rgba(239,68,68,0.1)',
                    border:'1px solid rgba(239,68,68,0.2)',
                  }}>{error}</div>
                )}
                <div style={{flex:1}}/>

                {/* Marcar completado */}
                <button onClick={marcarCompletado} style={{
                  padding:'8px 18px',borderRadius:10,
                  border:`1px solid ${secActiva.accent}40`,
                  background:`${secActiva.accent}12`,
                  color:secActiva.accent,cursor:'pointer',
                  fontSize:12,fontWeight:700,transition:'all 0.2s',
                }}>
                  {completados[secActiva.id] ? '✓ Completado' : 'Marcar completo'}
                </button>

                {/* Siguiente sección */}
                {activeIdx < SECCIONES.length - 1 && (
                  <button onClick={()=>setActiveIdx(i=>i+1)} style={{
                    padding:'8px 18px',borderRadius:10,
                    border:'1px solid rgba(255,255,255,0.12)',
                    background:'rgba(255,255,255,0.06)',
                    color:'rgba(255,255,255,0.6)',
                    cursor:'pointer',fontSize:12,fontWeight:600,
                    transition:'all 0.2s',
                  }}>Siguiente →</button>
                )}

                {/* Guardar atleta */}
                <button
                  onClick={guardar}
                  disabled={loading || !canSave}
                  className="ob-btn-main"
                  style={{
                    padding:'10px 24px',borderRadius:12,
                    border:'none',
                    background: canSave
                      ? 'linear-gradient(135deg,#7c3aed,#4f46e5)'
                      : 'rgba(255,255,255,0.08)',
                    color: canSave ? '#fff' : 'rgba(255,255,255,0.3)',
                    cursor: canSave ? 'pointer' : 'not-allowed',
                    fontSize:13,fontWeight:800,
                    boxShadow: canSave ? '0 4px 20px rgba(124,58,237,0.35)' : 'none',
                  }}>
                  {loading ? 'Creando...' : '✓ Crear atleta'}
                </button>
              </div>
            </>
          )}
        </div>
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
}
