// SeccionTecnica.jsx — Análisis biomecánico visual con imágenes de fondo
import { useState, useEffect } from 'react'

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
}

function MetricaOverlay({ label, valor, unidad, estado, x, y }) {
  const color = estado === 'optima' || estado === 'bueno' || estado === 'equilibrado' ? C.green
    : estado === 'mejorar' || estado === 'significativo' ? C.red
    : estado === 'baja' || estado === 'leve' ? C.yellow : C.purple
  return (
    <div style={{
      position: 'absolute', left: `${x}%`, top: `${y}%`, transform: 'translate(-50%,-50%)',
      textAlign: 'center', zIndex: 2,
    }}>
      <div style={{
        background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(8px)',
        borderRadius: 12, padding: '6px 12px', border: `1px solid ${color}40`,
      }}>
        <div style={{ fontSize: 9, color: C.dim, fontWeight: 600 }}>{label}</div>
        <div style={{ fontSize: 18, fontWeight: 800, color }}>{valor}<span style={{ fontSize: 10, color: C.dim }}> {unidad}</span></div>
        <div style={{ fontSize: 8, color, fontWeight: 600, textTransform: 'uppercase' }}>{estado}</div>
      </div>
    </div>
  )
}

function BarraMetrica({ label, valor, min, max, optMin, optMax, unidad, color }) {
  const pct = Math.min(100, Math.max(0, ((valor - min) / (max - min)) * 100))
  const optPctMin = ((optMin - min) / (max - min)) * 100
  const optPctMax = ((optMax - min) / (max - min)) * 100
  const enRango = valor >= optMin && valor <= optMax
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 10, color: C.dim }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color: enRango ? C.green : C.yellow }}>{valor} {unidad}</span>
      </div>
      <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, position: 'relative' }}>
        {/* Zona óptima */}
        <div style={{
          position: 'absolute', left: `${optPctMin}%`, width: `${optPctMax - optPctMin}%`,
          height: '100%', background: `${C.green}20`, borderRadius: 3,
        }} />
        {/* Valor actual */}
        <div style={{
          position: 'absolute', left: `${pct}%`, top: -2, width: 10, height: 10,
          borderRadius: 5, background: enRango ? C.green : C.yellow,
          transform: 'translateX(-50%)', boxShadow: `0 0 8px ${enRango ? C.green : C.yellow}60`,
        }} />
      </div>
    </div>
  )
}

function PanelRunning({ data }) {
  const m = data.metricas || {}
  const cad = m.cadencia || {}
  const cpz = m.cadencia_por_pace || {}
  return (
    <div>
      {/* Imagen de fondo con overlays */}
      <div style={{ position: 'relative', width: '100%', height: 350, borderRadius: 16, overflow: 'hidden', marginBottom: 20 }}>
        <img src="/img/tecnica_run.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.6 }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.9) 100%)' }} />

        {cad.promedio && <MetricaOverlay label="CADENCIA" valor={cad.promedio} unidad="spm" estado={cad.estado} x={50} y={25} />}
        {cad.q1 && <MetricaOverlay label="INICIO" valor={cad.q1} unidad="spm" estado={cad.q1 >= (cad.referencia?.min||170) ? 'optima' : 'baja'} x={20} y={55} />}
        {cad.q4 && <MetricaOverlay label="FINAL" valor={cad.q4} unidad="spm" estado={cad.drift_pct < -3 ? 'mejorar' : 'optima'} x={80} y={55} />}
        {cad.drift_pct !== undefined && (
          <MetricaOverlay label="DRIFT" valor={`${cad.drift_pct > 0 ? '+' : ''}${cad.drift_pct}`} unidad="%" estado={Math.abs(cad.drift_pct) < 3 ? 'optima' : 'mejorar'} x={50} y={75} />
        )}

        {m.gct && <MetricaOverlay label="GCT" valor={m.gct.promedio_ms} unidad="ms" estado={m.gct.estado} x={30} y={40} />}
        {m.vertical_osc && <MetricaOverlay label="OSC VERT" valor={m.vertical_osc.promedio_cm} unidad="cm" estado={m.vertical_osc.estado} x={70} y={40} />}
      </div>

      {/* Barras de métricas */}
      {cad.promedio && (
        <BarraMetrica label="Cadencia" valor={cad.promedio} min={140} max={200}
          optMin={cad.referencia?.min || 168} optMax={cad.referencia?.max || 185} unidad="spm" />
      )}
      {m.gct?.promedio_ms && (
        <BarraMetrica label="Tiempo de contacto" valor={m.gct.promedio_ms} min={180} max={350}
          optMin={200} optMax={260} unidad="ms" />
      )}
      {m.vertical_osc?.promedio_cm && (
        <BarraMetrica label="Oscilación vertical" valor={m.vertical_osc.promedio_cm} min={4} max={14}
          optMin={6} optMax={9} unidad="cm" />
      )}

      {/* Cadencia por pace */}
      {Object.keys(cpz).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 10, color: C.dim, marginBottom: 8, fontWeight: 600 }}>CADENCIA POR VELOCIDAD</div>
          <div style={{ display: 'flex', gap: 8 }}>
            {Object.entries(cpz).map(([z, v]) => (
              <div key={z} style={{
                flex: 1, textAlign: 'center', padding: '8px 0', borderRadius: 8,
                background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ fontSize: 9, color: C.dim, textTransform: 'uppercase' }}>{z}</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.purple }}>{v}</div>
                <div style={{ fontSize: 8, color: C.dim }}>spm</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function PanelCycling({ data }) {
  const m = data.metricas || {}
  const cad = m.cadencia || {}
  const lr = m.lr_balance || {}
  const te = m.torque_effectiveness || {}
  const cpz = m.cadencia_por_zona || {}
  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 350, borderRadius: 16, overflow: 'hidden', marginBottom: 20 }}>
        <img src="/img/tecnica_bike.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.6 }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.9) 100%)' }} />

        {cad.promedio && <MetricaOverlay label="CADENCIA" valor={cad.promedio} unidad="rpm" estado={cad.estado} x={50} y={25} />}
        {lr.promedio_pct && <MetricaOverlay label="L/R BALANCE" valor={`${lr.promedio_pct}/${(100-lr.promedio_pct).toFixed(1)}`} unidad="%" estado={lr.estado} x={25} y={50} />}
        {te.promedio_pct && <MetricaOverlay label="TORQUE EFF" valor={te.promedio_pct} unidad="%" estado={te.estado} x={75} y={50} />}
      </div>

      {cad.promedio && <BarraMetrica label="Cadencia" valor={cad.promedio} min={50} max={120} optMin={80} optMax={95} unidad="rpm" />}
      {lr.promedio_pct && <BarraMetrica label="Balance L/R" valor={lr.promedio_pct} min={40} max={60} optMin={48} optMax={52} unidad="%" />}
      {te.promedio_pct && <BarraMetrica label="Torque Effectiveness" valor={te.promedio_pct} min={30} max={100} optMin={70} optMax={95} unidad="%" />}

      {Object.keys(cpz).length > 0 && (
        <div style={{ marginTop: 16 }}>
          <div style={{ fontSize: 10, color: C.dim, marginBottom: 8, fontWeight: 600 }}>CADENCIA POR ZONA DE POTENCIA</div>
          <div style={{ display: 'flex', gap: 6 }}>
            {Object.entries(cpz).map(([z, v]) => (
              <div key={z} style={{
                flex: 1, textAlign: 'center', padding: '8px 0', borderRadius: 8,
                background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
              }}>
                <div style={{ fontSize: 9, color: C.blue, fontWeight: 700 }}>{z}</div>
                <div style={{ fontSize: 16, fontWeight: 800, color: C.purple }}>{v}</div>
                <div style={{ fontSize: 8, color: C.dim }}>rpm</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function PanelSwimming() {
  return (
    <div>
      <div style={{ position: 'relative', width: '100%', height: 350, borderRadius: 16, overflow: 'hidden', marginBottom: 20 }}>
        <img src="/img/tecnica_swim.png" alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', opacity: 0.6 }} />
        <div style={{ position: 'absolute', inset: 0, background: 'linear-gradient(180deg, transparent 30%, rgba(13,17,23,0.9) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 14, color: C.cyan, fontWeight: 700 }}>ANÁLISIS DE SWIM</div>
            <div style={{ fontSize: 11, color: C.dim, marginTop: 8 }}>Requiere datos de stroke type y cadencia de nado</div>
            <div style={{ fontSize: 10, color: C.dim, marginTop: 4 }}>Se activa con Garmin Swim 2 o HRM-Swim</div>
          </div>
        </div>
      </div>
    </div>
  )
}

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
            border: `1px solid ${sport === s.id ? C.purple : 'rgba(255,255,255,0.08)'}`,
            background: sport === s.id ? `${C.purple}15` : 'rgba(255,255,255,0.02)',
            color: sport === s.id ? C.purple : C.dim, fontSize: 12, fontWeight: 700,
          }}>
            {s.icon} {s.label}
          </button>
        ))}
      </div>

      {loading && <div style={{ textAlign: 'center', color: C.dim, padding: 40 }}>Analizando...</div>}

      {!loading && data && (
        <>
          {sport === 'running' && <PanelRunning data={data} />}
          {sport === 'cycling' && <PanelCycling data={data} />}
          {sport === 'swimming' && <PanelSwimming />}

          {/* Recomendaciones */}
          {data.recomendaciones && data.recomendaciones.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={{ fontSize: 10, color: C.yellow, fontWeight: 700, marginBottom: 8, letterSpacing: 1 }}>RECOMENDACIONES</div>
              {data.recomendaciones.map((r, i) => (
                <div key={i} style={{
                  padding: '10px 14px', borderRadius: 10, marginBottom: 6,
                  background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.15)',
                  fontSize: 11, color: 'rgba(255,255,255,0.7)', lineHeight: 1.5,
                }}>
                  {r}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {!loading && data?.error && (
        <div style={{ textAlign: 'center', color: C.dim, padding: 40 }}>{data.error}</div>
      )}
    </div>
  )
}
