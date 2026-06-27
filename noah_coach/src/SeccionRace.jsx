// SeccionRace.jsx — NOA Race Section
// Carrusel de carreras con modal de edición, prioridades A/B/C/D
import { useState, useEffect, useRef } from 'react'

const API = `http://${window.location.hostname}:5000/api`

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

// ── Paleta acorde al resto de NOAH ───────────────────────────────────────────
const PRIORIDAD = {
  A: { color: '#EF4444', bg: 'rgba(239,68,68,0.15)',   label: 'Prioridad A', desc: 'Carrera principal' },
  B: { color: '#F59E0B', bg: 'rgba(245,158,11,0.15)',  label: 'Prioridad B', desc: 'Carrera importante' },
  C: { color: '#3B82F6', bg: 'rgba(59,130,246,0.15)',  label: 'Prioridad C', desc: 'Carrera secundaria' },
  D: { color: '#6B7280', bg: 'rgba(107,114,128,0.15)', label: 'Prioridad D', desc: 'Participación' },
}

const ESTADO = {
  pendiente:  { color: '#8B5CF6', label: 'Pendiente' },
  completada: { color: '#10B981', label: 'Completada' },
  cancelada:  { color: '#6B7280', label: 'Cancelada' },
}

const DEPORTE_CONFIG = {
  running:  {
    label: 'Running',
    gradient: 'linear-gradient(135deg, #1a0533 0%, #2d1b69 40%, #4c1d95 70%, #7c3aed 100%)',
    icon: '🏃',
    accent: '#8B5CF6',
  },
  triatlon: {
    label: 'Triatlón',
    gradient: 'linear-gradient(135deg, #0c1445 0%, #1e3a5f 40%, #0e7490 70%, #06b6d4 100%)',
    icon: '🏊',
    accent: '#06B6D4',
  },
  cycling: {
    label: 'Ciclismo',
    gradient: 'linear-gradient(135deg, #1a2e05 0%, #365314 40%, #4d7c0f 70%, #84cc16 100%)',
    icon: '🚴',
    accent: '#84CC16',
  },
  swimming: {
    label: 'Natación',
    gradient: 'linear-gradient(135deg, #0a1628 0%, #0c4a6e 40%, #0369a1 70%, #38bdf8 100%)',
    icon: '🏊',
    accent: '#38BDF8',
  },
}

function diasFaltantes(fecha) {
  const hoy = new Date()
  hoy.setHours(0,0,0,0)
  const d = new Date(fecha + 'T00:00:00')
  const diff = Math.ceil((d - hoy) / 86400000)
  return diff
}

function fmtFecha(fecha) {
  if (!fecha) return '--'
  const d = new Date(fecha + 'T12:00:00')
  return d.toLocaleDateString('es-AR', { day:'numeric', month:'long', year:'numeric' })
}

// ── Modal agregar/editar carrera ──────────────────────────────────────────────
function ModalCarrera({ carrera, atletaId, onClose, onGuardado }) {
  const esNueva = !carrera?.id
  const [form, setForm] = useState({
    nombre:               carrera?.nombre || '',
    fecha:                carrera?.fecha || '',
    deporte:              carrera?.deporte || 'running',
    distancia:            carrera?.distancia || '',
    modalidad:            carrera?.modalidad || '',
    ciudad:               carrera?.ciudad || '',
    prioridad:            carrera?.prioridad || 'B',
    ctl_objetivo:         carrera?.ctl_objetivo || '',
    notas_coach:          carrera?.notas_coach || '',
    estado:               carrera?.estado || 'pendiente',
    resultado_tiempo:     carrera?.resultado_tiempo || '',
    resultado_posicion:   carrera?.resultado_posicion || '',
    resultado_categoria:  carrera?.resultado_categoria || '',
  })
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('info') // 'info' | 'resultado'

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const guardar = async () => {
    if (!form.nombre || !form.fecha) return alert('Nombre y fecha son requeridos')
    setLoading(true)
    try {
      if (esNueva) {
        await authFetch(`${API}/atletas/${atletaId}/carreras`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
      } else {
        await authFetch(`${API}/atletas/${atletaId}/carreras/${carrera.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
        })
      }
      onGuardado()
      onClose()
    } catch (e) {
      alert('Error al guardar')
    }
    setLoading(false)
  }

  const dep = DEPORTE_CONFIG[form.deporte] || DEPORTE_CONFIG.running
  const pri = PRIORIDAD[form.prioridad] || PRIORIDAD.B

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(0,0,0,0.85)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      backdropFilter: 'blur(8px)',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        width: 520, maxWidth: '95vw', maxHeight: '90vh',
        borderRadius: 20, overflow: 'hidden',
        background: '#0D1117',
        border: '1px solid rgba(255,255,255,0.1)',
        boxShadow: '0 40px 100px rgba(0,0,0,0.8)',
        display: 'flex', flexDirection: 'column',
      }}>

        {/* Header con gradiente del deporte */}
        <div style={{
          padding: '24px 24px 20px',
          background: dep.gradient,
          position: 'relative',
          overflow: 'hidden',
        }}>
          <div style={{
            position: 'absolute', inset: 0,
            background: 'rgba(0,0,0,0.3)',
          }}/>
          <div style={{ position: 'relative', zIndex: 1 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div>
                <div style={{ fontSize: 11, fontWeight: 700, color: dep.accent,
                  textTransform: 'uppercase', letterSpacing: 2, marginBottom: 6 }}>
                  {esNueva ? 'Nueva carrera' : 'Editar carrera'}
                </div>
                <div style={{ fontSize: 20, fontWeight: 800, color: '#fff' }}>
                  {form.nombre || 'Sin nombre'}
                </div>
                {form.fecha && (
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)', marginTop: 4 }}>
                    {fmtFecha(form.fecha)}
                    {diasFaltantes(form.fecha) > 0 && (
                      <span style={{ marginLeft: 8, color: dep.accent, fontWeight: 700 }}>
                        · {diasFaltantes(form.fecha)}d
                      </span>
                    )}
                  </div>
                )}
              </div>
              <button onClick={onClose} style={{
                width: 32, height: 32, borderRadius: 8,
                background: 'rgba(255,255,255,0.15)',
                border: 'none', color: '#fff', cursor: 'pointer',
                fontSize: 18, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>×</button>
            </div>

            {/* Selector prioridad */}
            <div style={{ display: 'flex', gap: 6, marginTop: 16 }}>
              {Object.entries(PRIORIDAD).map(([k, p]) => (
                <button key={k} onClick={() => set('prioridad', k)} style={{
                  padding: '4px 12px', borderRadius: 99, fontSize: 11, fontWeight: 700,
                  cursor: 'pointer', border: `1px solid ${form.prioridad === k ? p.color : 'rgba(255,255,255,0.2)'}`,
                  background: form.prioridad === k ? p.bg : 'rgba(255,255,255,0.05)',
                  color: form.prioridad === k ? p.color : 'rgba(255,255,255,0.5)',
                  transition: 'all 0.15s',
                }}>{k}</button>
              ))}
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
          {[['info','📋 Info'],['resultado','🏆 Resultado']].map(([t, l]) => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, padding: '10px 0', fontSize: 12, fontWeight: 600,
              cursor: 'pointer', border: 'none',
              borderBottom: tab === t ? `2px solid ${dep.accent}` : '2px solid transparent',
              background: 'transparent',
              color: tab === t ? dep.accent : 'rgba(255,255,255,0.4)',
            }}>{l}</button>
          ))}
        </div>

        {/* Contenido scrolleable */}
        <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
          {tab === 'info' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ gridColumn: '1/-1' }}>
                  <label style={labelStyle}>Nombre de la carrera *</label>
                  <input style={inputStyle} value={form.nombre}
                    onChange={e => set('nombre', e.target.value)}
                    placeholder="Ej: Maratón de Buenos Aires" />
                </div>
                <div>
                  <label style={labelStyle}>Fecha *</label>
                  <input style={inputStyle} type="date" value={form.fecha}
                    onChange={e => set('fecha', e.target.value)} />
                </div>
                <div>
                  <label style={labelStyle}>Ciudad</label>
                  <input style={inputStyle} value={form.ciudad}
                    onChange={e => set('ciudad', e.target.value)}
                    placeholder="Buenos Aires" />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <div>
                  <label style={labelStyle}>Deporte</label>
                  <select style={inputStyle} value={form.deporte}
                    onChange={e => set('deporte', e.target.value)}>
                    <option value="running">Running</option>
                    <option value="triatlon">Triatlón</option>
                    <option value="cycling">Ciclismo</option>
                    <option value="swimming">Natación</option>
                  </select>
                </div>
                <div>
                  <label style={labelStyle}>Distancia</label>
                  <input style={inputStyle} value={form.distancia}
                    onChange={e => set('distancia', e.target.value)}
                    placeholder="42K / 70.3" />
                </div>
                <div>
                  <label style={labelStyle}>Modalidad</label>
                  <input style={inputStyle} value={form.modalidad}
                    onChange={e => set('modalidad', e.target.value)}
                    placeholder="Maratón / Sprint" />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={labelStyle}>CTL objetivo</label>
                  <input style={inputStyle} type="number" value={form.ctl_objetivo}
                    onChange={e => set('ctl_objetivo', e.target.value)}
                    placeholder="75" />
                </div>
                <div>
                  <label style={labelStyle}>Estado</label>
                  <select style={inputStyle} value={form.estado}
                    onChange={e => set('estado', e.target.value)}>
                    <option value="pendiente">Pendiente</option>
                    <option value="completada">Completada</option>
                    <option value="cancelada">Cancelada</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={labelStyle}>Notas del coach</label>
                <textarea style={{ ...inputStyle, minHeight: 80, resize: 'vertical' }}
                  value={form.notas_coach}
                  onChange={e => set('notas_coach', e.target.value)}
                  placeholder="Objetivos, estrategia de carrera, puntos clave..." />
              </div>
            </div>
          )}

          {tab === 'resultado' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{
                padding: '12px 16px', borderRadius: 10,
                background: 'rgba(16,185,129,0.08)',
                border: '1px solid rgba(16,185,129,0.2)',
                fontSize: 12, color: 'rgba(255,255,255,0.5)',
              }}>
                Completá estos datos después de la carrera
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={labelStyle}>Tiempo final</label>
                  <input style={inputStyle} value={form.resultado_tiempo}
                    onChange={e => set('resultado_tiempo', e.target.value)}
                    placeholder="3:45:22" />
                </div>
                <div>
                  <label style={labelStyle}>Posición general</label>
                  <input style={inputStyle} type="number" value={form.resultado_posicion}
                    onChange={e => set('resultado_posicion', e.target.value)}
                    placeholder="42" />
                </div>
                <div style={{ gridColumn: '1/-1' }}>
                  <label style={labelStyle}>Posición en categoría</label>
                  <input style={inputStyle} value={form.resultado_categoria}
                    onChange={e => set('resultado_categoria', e.target.value)}
                    placeholder="3° Cat. 40-44" />
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '16px 24px',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          display: 'flex', gap: 8, justifyContent: 'flex-end',
        }}>
          <button onClick={onClose} style={{
            padding: '8px 18px', borderRadius: 8,
            border: '1px solid rgba(255,255,255,0.12)',
            background: 'transparent', color: 'rgba(255,255,255,0.5)',
            cursor: 'pointer', fontSize: 13,
          }}>Cancelar</button>
          <button onClick={guardar} disabled={loading} style={{
            padding: '8px 22px', borderRadius: 8,
            border: 'none', background: dep.accent,
            color: '#fff', cursor: 'pointer', fontSize: 13, fontWeight: 700,
          }}>{loading ? 'Guardando...' : esNueva ? 'Crear carrera' : 'Guardar cambios'}</button>
        </div>
      </div>
    </div>
  )
}

const labelStyle = {
  display: 'block', fontSize: 10, fontWeight: 600,
  color: 'rgba(255,255,255,0.4)', textTransform: 'uppercase',
  letterSpacing: 0.8, marginBottom: 5,
}
const inputStyle = {
  width: '100%', padding: '8px 11px',
  background: 'rgba(255,255,255,0.06)',
  border: '1px solid rgba(255,255,255,0.1)',
  borderRadius: 8, color: '#E6EDF3', fontSize: 13,
  outline: 'none', fontFamily: 'inherit',
  boxSizing: 'border-box',
}

// ── Card de carrera ──────────────────────────────────────────────────────────
function RaceCard({ carrera, onEdit, onDelete, modoAtleta = false }) {
  const dep  = DEPORTE_CONFIG[carrera.deporte] || DEPORTE_CONFIG.running
  const pri  = PRIORIDAD[carrera.prioridad] || PRIORIDAD.B
  const est  = ESTADO[carrera.estado] || ESTADO.pendiente
  const dias = diasFaltantes(carrera.fecha)
  const esPasada = dias < 0
  const esCompletada = carrera.estado === 'completada'
  const [confirmDel, setConfirmDel] = useState(false)

  return (
    <div style={{
      flexShrink: 0,
      width: 280,
      borderRadius: 16,
      overflow: 'hidden',
      border: `1px solid ${esPasada ? 'rgba(255,255,255,0.06)' : pri.color + '40'}`,
      background: '#0D1117',
      boxShadow: esPasada ? 'none' : `0 8px 32px ${pri.color}20`,
      transition: 'transform 0.2s, box-shadow 0.2s',
      cursor: 'pointer',
      opacity: carrera.estado === 'cancelada' ? 0.5 : 1,
    }}
    onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = `0 16px 48px ${pri.color}30` }}
    onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = esPasada ? 'none' : `0 8px 32px ${pri.color}20` }}
    onClick={() => onEdit(carrera)}>

      {/* Header con gradiente */}
      <div style={{
        height: 130, background: dep.gradient,
        position: 'relative', overflow: 'hidden',
      }}>
        {/* Overlay oscuro */}
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)' }}/>

        {/* Prioridad badge */}
        <div style={{
          position: 'absolute', top: 12, left: 12,
          padding: '3px 10px', borderRadius: 99,
          background: pri.bg, border: `1px solid ${pri.color}60`,
          fontSize: 10, fontWeight: 800, color: pri.color,
          backdropFilter: 'blur(8px)',
          zIndex: 1,
        }}>{carrera.prioridad} · {pri.desc}</div>

        {/* Estado badge */}
        {carrera.estado !== 'pendiente' && (
          <div style={{
            position: 'absolute', top: 12, right: 12,
            padding: '3px 10px', borderRadius: 99,
            background: `${est.color}20`, border: `1px solid ${est.color}60`,
            fontSize: 10, fontWeight: 700, color: est.color,
            backdropFilter: 'blur(8px)',
            zIndex: 1,
          }}>{est.label}</div>
        )}

        {/* Icono deporte grande */}
        <div style={{
          position: 'absolute', bottom: 12, right: 16,
          fontSize: 48, opacity: 0.25, zIndex: 1,
          lineHeight: 1,
        }}>{dep.icon}</div>

        {/* Días faltantes */}
        <div style={{
          position: 'absolute', bottom: 12, left: 14,
          zIndex: 1,
        }}>
          {esCompletada && carrera.resultado_tiempo ? (
            <div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', marginBottom: 2 }}>TIEMPO FINAL</div>
              <div style={{ fontSize: 22, fontWeight: 900, color: '#10B981', lineHeight: 1 }}>
                {carrera.resultado_tiempo}
              </div>
            </div>
          ) : esPasada ? (
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontWeight: 600 }}>
              Hace {Math.abs(dias)}d
            </div>
          ) : (
            <div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.5)', marginBottom: 1 }}>FALTAN</div>
              <div style={{ fontSize: 28, fontWeight: 900, color: '#fff', lineHeight: 1 }}>
                {dias}<span style={{ fontSize: 12, fontWeight: 600, marginLeft: 2 }}>días</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Contenido */}
      <div style={{ padding: '14px 16px' }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#E6EDF3', marginBottom: 4, lineHeight: 1.3 }}>
          {carrera.nombre}
        </div>

        <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginBottom: 10 }}>
          {fmtFecha(carrera.fecha)}
          {carrera.ciudad && ` · ${carrera.ciudad}`}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 10 }}>
          {carrera.distancia && (
            <span style={{
              padding: '2px 8px', borderRadius: 6,
              background: `${dep.accent}18`, border: `1px solid ${dep.accent}30`,
              fontSize: 10, fontWeight: 700, color: dep.accent,
            }}>{carrera.distancia}</span>
          )}
          {carrera.modalidad && (
            <span style={{
              padding: '2px 8px', borderRadius: 6,
              background: 'rgba(255,255,255,0.06)',
              fontSize: 10, color: 'rgba(255,255,255,0.4)',
            }}>{carrera.modalidad}</span>
          )}
        </div>

        {carrera.ctl_objetivo && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 10px', borderRadius: 8,
            background: 'rgba(99,102,241,0.08)',
            border: '1px solid rgba(99,102,241,0.2)',
            marginBottom: 10,
          }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>CTL objetivo</span>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#6366F1', marginLeft: 'auto' }}>
              {carrera.ctl_objetivo}
            </span>
          </div>
        )}

        {esCompletada && carrera.resultado_posicion && (
          <div style={{
            display: 'flex', gap: 8,
            padding: '6px 10px', borderRadius: 8,
            background: 'rgba(16,185,129,0.08)',
            border: '1px solid rgba(16,185,129,0.2)',
            marginBottom: 10,
          }}>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)' }}>
              Pos. {carrera.resultado_posicion}
              {carrera.resultado_categoria && ` · ${carrera.resultado_categoria}`}
            </div>
          </div>
        )}

        {carrera.notas_coach && !modoAtleta && (
          <div style={{
            fontSize: 11, color: 'rgba(255,255,255,0.35)',
            borderTop: '1px solid rgba(255,255,255,0.06)',
            paddingTop: 8, marginTop: 2,
            overflow: 'hidden', textOverflow: 'ellipsis',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
          }}>
            {carrera.notas_coach}
          </div>
        )}

        {/* Botón borrar */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}
          onClick={e => e.stopPropagation()}>
          <button onClick={() => {
            if (!confirmDel) { setConfirmDel(true); setTimeout(() => setConfirmDel(false), 3000); return }
            onDelete(carrera.id)
          }} style={{
            padding: '3px 10px', borderRadius: 6, fontSize: 10, fontWeight: 600,
            cursor: 'pointer',
            border: `1px solid ${confirmDel ? '#EF444460' : 'rgba(255,255,255,0.1)'}`,
            background: confirmDel ? 'rgba(239,68,68,0.15)' : 'transparent',
            color: confirmDel ? '#EF4444' : 'rgba(255,255,255,0.3)',
          }}>
            {confirmDel ? '¿Confirmar?' : '🗑'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Card para agregar nueva carrera ──────────────────────────────────────────
function AddRaceCard({ onClick }) {
  return (
    <div onClick={onClick} style={{
      flexShrink: 0, width: 280, height: 340,
      borderRadius: 16, cursor: 'pointer',
      border: '2px dashed rgba(255,255,255,0.12)',
      background: 'rgba(255,255,255,0.02)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', gap: 12,
      transition: 'all 0.2s',
    }}
    onMouseEnter={e => { e.currentTarget.style.border = '2px dashed rgba(139,92,246,0.4)'; e.currentTarget.style.background = 'rgba(139,92,246,0.05)' }}
    onMouseLeave={e => { e.currentTarget.style.border = '2px dashed rgba(255,255,255,0.12)'; e.currentTarget.style.background = 'rgba(255,255,255,0.02)' }}>
      <div style={{
        width: 48, height: 48, borderRadius: 14,
        background: 'rgba(139,92,246,0.15)',
        border: '1px solid rgba(139,92,246,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: 24,
      }}>+</div>
      <div style={{ fontSize: 13, fontWeight: 600, color: 'rgba(255,255,255,0.4)' }}>
        Nueva carrera
      </div>
    </div>
  )
}

// ── Componente principal ──────────────────────────────────────────────────────
export default function SeccionRace({ atletaId, modoAtleta = false }) {
  const [carreras, setCarreras]   = useState([])
  const [loading, setLoading]     = useState(true)
  const [modal, setModal]         = useState(null) // null | 'nueva' | {carrera}
  const [filtro, setFiltro]       = useState('todas') // 'todas' | 'pendiente' | 'completada'
  const carruselRef = useRef(null)

  const cargar = async () => {
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/carreras`)
      const j = await r.json()
      setCarreras(j.data?.carreras || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { if (atletaId) cargar() }, [atletaId])

  const borrar = async (id) => {
    try {
      await authFetch(`${API}/atletas/${atletaId}/carreras/${id}`, { method: 'DELETE' })
      cargar()
    } catch { alert('Error al borrar') }
  }

  const scroll = (dir) => {
    if (carruselRef.current) {
      carruselRef.current.scrollBy({ left: dir * 300, behavior: 'smooth' })
    }
  }

  const carrerasFiltradas = carreras.filter(c => {
    if (filtro === 'todas') return true
    return c.estado === filtro
  })

  // Ordenar: primero pendientes por fecha, luego completadas
  const ordenadas = [...carrerasFiltradas].sort((a, b) => {
    if (a.estado === 'pendiente' && b.estado !== 'pendiente') return -1
    if (a.estado !== 'pendiente' && b.estado === 'pendiente') return 1
    return a.fecha > b.fecha ? 1 : -1
  })

  // Stats
  const proxima = carreras.filter(c => c.estado === 'pendiente' && diasFaltantes(c.fecha) > 0)
    .sort((a, b) => a.fecha > b.fecha ? 1 : -1)[0]

  const priA = carreras.filter(c => c.prioridad === 'A' && c.estado === 'pendiente').length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexWrap: 'wrap', gap: 10,
      }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 800, color: '#E6EDF3', marginBottom: 2 }}>
            🏁 Carreras
          </div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)' }}>
            {carreras.length} carreras · {priA} prioridad A
            {proxima && ` · Próxima: ${diasFaltantes(proxima.fecha)}d`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {/* Filtros */}
          {['todas','pendiente','completada'].map(f => (
            <button key={f} onClick={() => setFiltro(f)} style={{
              padding: '4px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600,
              cursor: 'pointer', border: '1px solid rgba(255,255,255,0.1)',
              background: filtro === f ? 'rgba(139,92,246,0.2)' : 'transparent',
              color: filtro === f ? '#8B5CF6' : 'rgba(255,255,255,0.4)',
            }}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
          <button onClick={() => setModal('nueva')} style={{
            padding: '6px 14px', borderRadius: 8,
            border: 'none', background: '#8B5CF6',
            color: '#fff', cursor: 'pointer', fontSize: 12, fontWeight: 700,
          }}>+ Carrera</button>
        </div>
      </div>

      {/* Próxima carrera destacada */}
      {proxima && filtro === 'todas' && (
        <div onClick={() => setModal(proxima)} style={{
          borderRadius: 14, overflow: 'hidden', cursor: 'pointer',
          background: DEPORTE_CONFIG[proxima.deporte]?.gradient || DEPORTE_CONFIG.running.gradient,
          position: 'relative', padding: '20px 24px',
          border: `1px solid ${PRIORIDAD[proxima.prioridad]?.color || '#8B5CF6'}40`,
        }}>
          <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)' }}/>
          <div style={{ position: 'relative', zIndex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: DEPORTE_CONFIG[proxima.deporte]?.accent,
                textTransform: 'uppercase', letterSpacing: 1.5, marginBottom: 6 }}>
                PRÓXIMA CARRERA · {PRIORIDAD[proxima.prioridad]?.label}
              </div>
              <div style={{ fontSize: 22, fontWeight: 900, color: '#fff', marginBottom: 4 }}>
                {proxima.nombre}
              </div>
              <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.6)' }}>
                {fmtFecha(proxima.fecha)}
                {proxima.ciudad && ` · ${proxima.ciudad}`}
                {proxima.distancia && ` · ${proxima.distancia}`}
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.5)', marginBottom: 4 }}>FALTAN</div>
              <div style={{ fontSize: 52, fontWeight: 900, color: '#fff', lineHeight: 1 }}>
                {diasFaltantes(proxima.fecha)}
              </div>
              <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.6)' }}>días</div>
            </div>
          </div>
        </div>
      )}

      {/* Carrusel */}
      <div style={{ position: 'relative' }}>
        {/* Botones navegación */}
        {ordenadas.length > 2 && (
          <>
            <button onClick={() => scroll(-1)} style={{
              position: 'absolute', left: -16, top: '50%', transform: 'translateY(-50%)',
              zIndex: 10, width: 32, height: 32, borderRadius: '50%',
              background: 'rgba(13,17,23,0.9)', border: '1px solid rgba(255,255,255,0.15)',
              color: '#fff', cursor: 'pointer', fontSize: 16,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>‹</button>
            <button onClick={() => scroll(1)} style={{
              position: 'absolute', right: -16, top: '50%', transform: 'translateY(-50%)',
              zIndex: 10, width: 32, height: 32, borderRadius: '50%',
              background: 'rgba(13,17,23,0.9)', border: '1px solid rgba(255,255,255,0.15)',
              color: '#fff', cursor: 'pointer', fontSize: 16,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>›</button>
          </>
        )}

        {/* Track del carrusel */}
        <div ref={carruselRef} style={{
          display: 'flex', gap: 16, overflowX: 'auto', paddingBottom: 8,
          scrollbarWidth: 'none', msOverflowStyle: 'none',
        }}>
          {loading && (
            <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13, padding: '20px 0' }}>
              Cargando...
            </div>
          )}
          {!loading && ordenadas.map(c => (
            <RaceCard key={c.id} carrera={c}
              onEdit={c => setModal(c)}
              onDelete={borrar}
              modoAtleta={modoAtleta}
            />
          ))}
          {!loading && (
            <AddRaceCard onClick={() => setModal('nueva')} />
          )}
        </div>
      </div>

      {/* Modal */}
      {modal && (
        <ModalCarrera
          carrera={modal === 'nueva' ? null : modal}
          atletaId={atletaId}
          onClose={() => setModal(null)}
          onGuardado={cargar}
        />
      )}
    </div>
  )
}
