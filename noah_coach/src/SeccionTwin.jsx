// SeccionTwin.jsx — Digital Twin for NOAH
// Athlete: visual + simple explanation
// Coach: execute + choose scenarios
//
// INTEGRAR:
//   AtletaDashboard.jsx:
//     import { TwinAtleta } from './SeccionTwin'
//     tabs: {id:'twin', label:'Mi Twin', icon: Brain}
//     content: {tab==='twin' && <TwinAtleta atletaId={id} />}
//
//   App.js (coach):
//     import { TwinCoach } from './SeccionTwin'
//     tabs: {id:'twin', label:'Digital Twin'}
//     content: {tab==='twin'&&atletaId&&<TwinCoach atletaId={atletaId} atleta={atleta} />}

import React, { useState, useEffect } from 'react'
import { Footprints, Bike as BikeIcon, Waves } from 'lucide-react'

const API = (window.location.hostname === 'localhost' || window.location.hostname.match(/^192\./))
  ? 'http://localhost:5000/api' : '/api'

const authFetch = (url, opts = {}) => {
  let token = null
  try {
    const raw = localStorage.getItem('noah_sesion')
    token = raw ? JSON.parse(raw)?.token : null
  } catch {}
  const headers = { ...(opts.headers || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(url, { ...opts, headers }).then(res => {
    if (res.status === 401) {
      try { localStorage.removeItem('noah_sesion') } catch {}
      if (!window.location.pathname.startsWith('/login')) window.location.href = '/login'
    }
    return res
  })
}

// ── Colors (NOAH_C match) ──
const NC = {
  run: '#A78BFA', bike: '#F59E0B', swim: '#38BDF8',
  accent: '#8B5CF6', cyan: '#06B6D4',
  ok: '#10B981', warn: '#F59E0B', bad: '#EF4444',
  ink: 'rgba(255,255,255,0.92)', ink2: 'rgba(255,255,255,0.70)',
  ink3: 'rgba(255,255,255,0.45)', ink4: 'rgba(255,255,255,0.28)',
  border: 'rgba(255,255,255,0.08)',
}
const SP = {
  running:  { c: NC.run, Icon: Footprints, l: 'Run' },
  cycling:  { c: NC.bike, Icon: BikeIcon, l: 'Bike' },
  swimming: { c: NC.swim, Icon: Waves, l: 'Swim' },
}
const INT_COL = { Recovery: NC.ink4, Endurance: NC.swim, Threshold: NC.warn, VO2max: NC.bad }

// ── SVG Ring ──
function Ring({ pct, color, size = 68, stroke = 5, children }) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const dash = circ * Math.min(Math.max(pct, 0), 1)
  return (
    <div style={{ position: 'relative', width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
          strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 6px ${color}88)`, transition: 'stroke-dasharray 0.8s ease' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
        {children}
      </div>
    </div>
  )
}

// ── Week SVG (mini visual of the 7-day plan with double sessions) ──
function WeekStrip({ plan }) {
  if (!plan || plan.length === 0) return null
  const dias = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
  // Group by day (some days have AM/PM marked as "Día (2da)")
  const byDay = []
  let cur = null
  for (const d of plan) {
    const isDbl = d.dia && d.dia.includes('2da')
    if (isDbl && cur) {
      cur.push(d)
    } else {
      cur = [d]
      byDay.push(cur)
    }
  }
  const maxTSS = Math.max(...byDay.map(ds => ds.reduce((a, d) => a + (d.tss || 0), 0)), 1)

  return (
    <svg width="100%" viewBox="0 0 280 64" style={{ display: 'block' }}>
      {byDay.map((ds, i) => {
        const x = i * 40 + 4
        const totalTSS = ds.reduce((a, d) => a + (d.tss || 0), 0)
        const isRest = ds[0]?.sesion === 'DESCANSO'
        const isDbl = ds.length > 1

        if (isRest) {
          return (
            <g key={i}>
              <rect x={x} y={47} width={30} height={3} rx={2} fill="rgba(255,255,255,0.08)" />
              <text x={x+15} y={60} textAnchor="middle" fontSize={8} fill={NC.ink4} fontWeight={600}>{dias[i]||''}</text>
            </g>
          )
        }

        if (isDbl) {
          // Two stacked bars for double session
          const h1 = Math.max(4, (ds[0].tss || 0) / maxTSS * 36)
          const h2 = Math.max(4, (ds[1].tss || 0) / maxTSS * 36)
          const c1 = SP[ds[0].sport]?.c || NC.ink4
          const c2 = SP[ds[1].sport]?.c || NC.ink4
          return (
            <g key={i}>
              <rect x={x} y={50-h1-h2-2} width={14} height={h1} rx={3}
                fill={c1} opacity={0.95} style={{ filter: `drop-shadow(0 2px 4px ${c1}55)` }} />
              <rect x={x+16} y={50-h2} width={14} height={h2} rx={3}
                fill={c2} opacity={0.95} style={{ filter: `drop-shadow(0 2px 4px ${c2}55)` }} />
              <text x={x+15} y={60} textAnchor="middle" fontSize={8} fill={NC.ink4} fontWeight={600}>{dias[i]||''}</text>
              <text x={x+15} y={44-h1-h2} textAnchor="middle" fontSize={7} fill={NC.ink3}>{totalTSS}</text>
            </g>
          )
        }

        // Single bar
        const h = Math.max(4, totalTSS / maxTSS * 38)
        const color = SP[ds[0].sport]?.c || NC.ink4
        return (
          <g key={i}>
            <rect x={x} y={50-h} width={30} height={h} rx={4}
              fill={color} opacity={0.9}
              style={{ filter: `drop-shadow(0 2px 6px ${color}55)` }} />
            <text x={x+15} y={60} textAnchor="middle" fontSize={8} fill={NC.ink4} fontWeight={600}>{dias[i]||''}</text>
            <text x={x+15} y={47-h} textAnchor="middle" fontSize={7} fill={NC.ink3}>{totalTSS}</text>
          </g>
        )
      })}
    </svg>
  )
}


// ═══════════════════════════════════════════════════════════════
//  VISTA ATLETA
// ═══════════════════════════════════════════════════════════════


export function TwinAtleta({ atletaId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [vista, setVista] = useState('prescripcion')

  useEffect(() => {
    if (!atletaId) return
    setLoading(true)
    authFetch(`${API}/atletas/${atletaId}/twin`)
      .then(r => r.json())
      .then(r => { setData(r.data || r); setLoading(false) })
      .catch(() => setLoading(false))
  }, [atletaId])

  if (loading) return (
    <div style={{ padding: 50, textAlign: 'center' }}>
      <div style={{ fontSize: 36, marginBottom: 10, animation: 'pulse 2s infinite' }}>◎</div>
      <div style={{ fontSize: 12, color: NC.ink3 }}>Calibrando tu Digital Twin...</div>
      <style>{`@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }`}</style>
    </div>
  )

  if (!data?.ok) return (
    <div style={{ padding: 32, fontSize: 12, color: NC.ink3 }}>
      {data?.error || 'Sin datos suficientes para tu Twin'}
    </div>
  )

  const presc = data.prescripcion || {}
  const best = (presc.mejores || [])[0]
  const met = presc.metricas_calibracion || data.metricas_calibracion || {}
  const evaluacion = data.evaluacion || {}
  const historial = data.historial || {}

  const tabs = [
    { id: 'prescripcion', label: 'Próxima semana', sub: data.semana_prescripcion },
    { id: 'evaluacion',   label: 'Semana pasada',  sub: data.semana_evaluacion },
  ]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Toggle tabs */}
      <div style={{ display: 'flex', gap: 0, borderRadius: 12, overflow: 'hidden',
        border: '1px solid rgba(255,255,255,0.08)' }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setVista(t.id)} style={{
            flex: 1, padding: '12px 8px', border: 'none', cursor: 'pointer',
            background: vista === t.id
              ? 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(56,189,248,0.10))'
              : 'rgba(255,255,255,0.02)',
            borderBottom: vista === t.id ? `2px solid ${NC.accent}` : '2px solid transparent',
            transition: 'all 0.2s',
          }}>
            <div style={{ fontSize: 12, fontWeight: vista === t.id ? 700 : 500,
              color: vista === t.id ? NC.ink : NC.ink3 }}>{t.label}</div>
            <div style={{ fontSize: 9, color: NC.ink4, marginTop: 2 }}>{t.sub}</div>
          </button>
        ))}
      </div>

      {/* PRESCRIPCIÓN */}
      {vista === 'prescripcion' && (
        <>
          <div style={{ background: 'linear-gradient(135deg, #0F172A, #1E293B)',
            borderRadius: 14, padding: '18px 20px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-around', gap: 8, marginBottom: 14 }}>
              {['running', 'cycling', 'swimming'].map(disc => {
                const m = met[disc]; const r2 = m?.r2 || 0; const sp = SP[disc]
                if (!m?.ok && r2 <= 0) return (
                  <div key={disc} style={{ textAlign: 'center', opacity: 0.3 }}>
                    <Ring pct={0} color={sp.c} size={58} stroke={4}>
                      <sp.Icon size={18} color={sp.c} style={{ opacity: 0.4 }} />
                    </Ring>
                    <div style={{ fontSize: 9, color: NC.ink4, marginTop: 4 }}>{sp.l}</div>
                  </div>
                )
                return (
                  <div key={disc} style={{ textAlign: 'center' }}>
                    <Ring pct={r2} color={sp.c} size={58} stroke={4}>
                      <span style={{ fontSize: 14, fontWeight: 800, color: sp.c,
                        textShadow: `0 0 12px ${sp.c}66` }}>{(r2*100).toFixed(0)}%</span>
                    </Ring>
                    <div style={{ fontSize: 9, color: NC.ink3, marginTop: 4, fontWeight: 600 }}>{sp.l}</div>
                  </div>
                )
              })}
            </div>
            <div style={{ fontSize: 11, color: NC.ink3, lineHeight: 1.6, textAlign: 'center' }}>
              NOAH evaluó <strong style={{ color: NC.accent }}>{presc.n_evaluados || 200}</strong> formas
              distintas de entrenar y encontró tu semana óptima.
              {presc.desde_cache ? ' Se mantiene hasta el domingo.' : ''}
            </div>
          </div>

          {best && (
            <div style={{ background: 'linear-gradient(165deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
              borderRadius: 14, padding: '18px 20px', border: '1px solid rgba(255,255,255,0.09)',
              boxShadow: '0 8px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                <div style={{ fontSize: 10, color: NC.cyan, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase' }}>
                  Tu semana óptima</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20,
                    background: best.riesgo < 0.15 ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
                    color: best.riesgo < 0.15 ? NC.ok : NC.warn }}>Riesgo {(best.riesgo*100).toFixed(0)}%</span>
                  <span style={{ fontSize: 10, fontWeight: 700, padding: '3px 10px', borderRadius: 20,
                    background: 'rgba(139,92,246,0.15)', color: NC.accent }}>TSS {best.tss_total}</span>
                </div>
              </div>
              <WeekStrip plan={best.plan || []} />
              <div style={{ marginTop: 10 }}>
                {(best.plan || []).map((dia, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '9px 0',
                    borderBottom: i < (best.plan?.length||0)-1 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
                    <div style={{ width: 28, fontSize: 10, fontWeight: 700, color: NC.ink4, paddingTop: 2 }}>
                      {(dia.dia||'').substring(0,3)}</div>
                    {dia.sesion === 'DESCANSO' ? (
                      <div style={{ fontSize: 11, color: NC.ink4, fontStyle: 'italic' }}>Descanso</div>
                    ) : (
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ width: 5, height: 5, borderRadius: 3,
                            background: SP[dia.sport]?.c || NC.ink4, boxShadow: `0 0 4px ${SP[dia.sport]?.c||NC.ink4}66` }} />
                          <span style={{ fontSize: 11, fontWeight: 600, color: NC.ink }}>{dia.tipo}</span>
                          <span style={{ fontSize: 9, color: INT_COL[dia.intensidad]||NC.ink4,
                            padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.04)' }}>{dia.intensidad}</span>
                          <span style={{ fontSize: 9, color: NC.ink4, marginLeft: 'auto' }}>TSS {dia.tss}</span>
                        </div>
                        <div style={{ fontSize: 10, color: NC.ink3, marginTop: 3, lineHeight: 1.4 }}>{dia.descripcion}</div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {/* EVALUACIÓN */}
      {vista === 'evaluacion' && (
        <div style={{ background: 'linear-gradient(135deg, #0F172A, #1E293B)',
          borderRadius: 14, padding: '22px 22px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)' }}>
          {evaluacion.ok ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginBottom: 20 }}>
                <Ring pct={evaluacion.acierto||0} color={
                  (evaluacion.acierto||0) >= 0.7 ? NC.ok : (evaluacion.acierto||0) >= 0.4 ? NC.warn : NC.bad
                } size={80} stroke={5}>
                  <span style={{ fontSize: 22, fontWeight: 800,
                    color: (evaluacion.acierto||0) >= 0.7 ? NC.ok : NC.warn }}>{evaluacion.acierto_pct||0}</span>
                  <span style={{ fontSize: 8, color: NC.ink4 }}>acierto</span>
                </Ring>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: NC.ink, marginBottom: 6 }}>
                    Semana {evaluacion.semana}</div>
                  <div style={{ fontSize: 11, color: NC.ink3, lineHeight: 1.6 }}>
                    {(evaluacion.acierto||0) >= 0.7 ? 'La predicción fue precisa — el Twin conoce bien tu cuerpo.'
                      : (evaluacion.acierto||0) >= 0.4 ? 'Predicción parcial — el Twin está aprendiendo.'
                      : 'El Twin necesita más datos para mejorar.'}</div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
                {[
                  { label: 'TSS predicho', value: evaluacion.tss_predicho, color: NC.ink },
                  { label: 'TSS real', value: evaluacion.tss_real, color: NC.accent },
                  { label: 'HRV', value: evaluacion.hrv_ok===true?'Mantenida ✓':evaluacion.hrv_ok===false?'Cayó ✗':'Sin datos',
                    color: evaluacion.hrv_ok===true?NC.ok:evaluacion.hrv_ok===false?NC.bad:NC.ink4 },
                  { label: 'CTL', value: evaluacion.absorcion_ok===true?'Subió ✓':evaluacion.absorcion_ok===false?'Bajó ✗':'Sin datos',
                    color: evaluacion.absorcion_ok===true?NC.ok:evaluacion.absorcion_ok===false?NC.bad:NC.ink4 },
                ].map((m,i) => (
                  <div key={i} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 10, padding: '10px 14px' }}>
                    <div style={{ fontSize: 9, color: NC.ink4, fontWeight: 600, marginBottom: 3 }}>{m.label}</div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: m.color }}>{m.value}</div>
                  </div>
                ))}
              </div>
              {historial.n_evaluaciones > 0 && (
                <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 10, padding: '12px 16px',
                  display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ fontSize: 24 }}>
                    {historial.tendencia==='mejorando'?'▲':historial.tendencia==='empeorando'?'▼':'—'}</div>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 700, color:
                      historial.tendencia==='mejorando'?NC.ok:historial.tendencia==='empeorando'?NC.bad:NC.ink2 }}>
                      {historial.tendencia==='mejorando'?'El Twin está mejorando'
                        :historial.tendencia==='empeorando'?'Necesita más datos':'Rendimiento estable'}</div>
                    <div style={{ fontSize: 10, color: NC.ink3, marginTop: 2 }}>
                      Acierto promedio: {((historial.promedio_acierto||0)*100).toFixed(0)}%
                      {' · '}{historial.n_evaluaciones} semanas</div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ textAlign: 'center', padding: 20 }}>
              <div style={{ fontSize: 28, marginBottom: 10, opacity: 0.5 }}>◉</div>
              <div style={{ fontSize: 12, color: NC.ink3 }}>
                {evaluacion.error || 'Sin evaluación para la semana pasada'}</div>
              <div style={{ fontSize: 10, color: NC.ink4, marginTop: 6 }}>
                La evaluación se activa cuando hay una predicción guardada y la semana terminó.</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function TwinCoach({ atletaId, atleta }) {
  const [data, setData]           = useState(null)
  const [loading, setLoading]     = useState(false)
  const [escSel, setEscSel]       = useState(0)
  const [tipoSem, setTipoSem]    = useState('carga')
  const [tssCustom, setTssCustom] = useState('')
  const [nEsc, setNEsc]           = useState(200)

  const ejecutar = () => {
    setLoading(true)
    const params = new URLSearchParams({ tipo_sem: tipoSem, n: nEsc })
    if (tssCustom) params.set('tss', tssCustom)
    authFetch(`${API}/atletas/${atletaId}/twin?${params}`)
      .then(r => r.json())
      .then(r => { setData(r.data || r); setLoading(false); setEscSel(0) })
      .catch(() => setLoading(false))
  }

  const nombre = atleta?.nombre || data?.atleta || ''
  const met = data?.metricas_calibracion || {}
  const mejores = data?.mejores || []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* Header */}
      <div style={{
        background: 'linear-gradient(135deg, #0F172A, #1E293B)',
        borderRadius: 14, padding: '18px 22px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 10, color: NC.cyan, fontWeight: 700, letterSpacing: 1.5, textTransform: 'uppercase' }}>
              DIGITAL TWIN
            </div>
            <div style={{ fontSize: 12, color: NC.ink3, marginTop: 3 }}>{nombre}</div>
          </div>
          <button onClick={ejecutar} disabled={loading} style={{
            padding: '8px 20px', borderRadius: 10, border: 'none', cursor: 'pointer',
            background: loading ? NC.ink4 : 'linear-gradient(135deg, #8B5CF6, #6D28D9)',
            color: '#fff', fontSize: 12, fontWeight: 700,
            boxShadow: loading ? 'none' : '0 6px 20px -4px rgba(139,92,246,0.5), inset 0 1px 0 rgba(255,255,255,0.25)',
          }}>
            {loading ? 'Calibrando...' : '◎ Ejecutar Twin'}
          </button>
        </div>

        {/* Controles */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {[
            { label: 'Semana', value: tipoSem, set: setTipoSem,
              opts: [['carga', 'Carga'], ['descarga', 'Descarga']] },
            { label: 'Escenarios', value: nEsc, set: v => setNEsc(Number(v)),
              opts: [['50', '50'], ['100', '100'], ['200', '200']] },
          ].map(({ label, value, set, opts }) => (
            <div key={label}>
              <div style={{ fontSize: 9, color: NC.ink4, marginBottom: 3, fontWeight: 600 }}>{label}</div>
              <select value={value} onChange={e => set(e.target.value)} style={{
                background: 'rgba(255,255,255,0.04)', color: NC.ink2, border: `1px solid ${NC.border}`,
                borderRadius: 6, padding: '5px 8px', fontSize: 11, cursor: 'pointer',
              }}>
                {opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          ))}
          <div>
            <div style={{ fontSize: 9, color: NC.ink4, marginBottom: 3, fontWeight: 600 }}>TSS (auto)</div>
            <input type="number" value={tssCustom} onChange={e => setTssCustom(e.target.value)}
              placeholder="auto" style={{
                width: 65, background: 'rgba(255,255,255,0.04)', color: NC.ink2,
                border: `1px solid ${NC.border}`, borderRadius: 6, padding: '5px 8px', fontSize: 11,
              }} />
          </div>
        </div>
      </div>

      {/* Resultados */}
      {data?.ok && (
        <>
          {/* Calibración rings */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            {['running', 'cycling', 'swimming'].map(disc => {
              const m = met[disc]
              if (!m?.ok && !(m?.r2 > 0)) return null
              const r2 = m.r2 || 0
              const sp = SP[disc]
              return (
                <div key={disc} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Ring pct={r2} color={sp.c} size={44} stroke={3.5}>
                    <span style={{ fontSize: 11, fontWeight: 800, color: sp.c }}>{(r2*100).toFixed(0)}</span>
                  </Ring>
                  <div>
                    <div style={{ fontSize: 10, fontWeight: 600, color: sp.c }}>{sp.l}</div>
                    <div style={{ fontSize: 9, color: NC.ink4 }}>n={m.n}</div>
                  </div>
                </div>
              )
            })}
            <div style={{ fontSize: 10, color: NC.ink3, marginLeft: 'auto' }}>
              TSS ref: <strong style={{ color: NC.ink }}>{data.tss_ref}</strong>
              {' · '}{data.n_evaluados} esc.
            </div>
          </div>

          {/* Scenario tabs */}
          <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
            {mejores.map((esc, i) => {
              const active = i === escSel
              const rCol = esc.riesgo < 0.15 ? NC.ok : esc.riesgo < 0.40 ? NC.warn : NC.bad
              return (
                <button key={i} onClick={() => setEscSel(i)} style={{
                  padding: '7px 14px', borderRadius: 8, cursor: 'pointer',
                  border: `1.5px solid ${active ? NC.accent : NC.border}`,
                  background: active ? 'rgba(139,92,246,0.12)' : 'transparent',
                  color: active ? NC.accent : NC.ink3, fontSize: 11, fontWeight: 600,
                  whiteSpace: 'nowrap', transition: 'all 0.15s',
                  boxShadow: active ? `0 0 12px ${NC.accent}33` : 'none',
                }}>
                  #{esc.id}
                  <span style={{ margin: '0 6px', color: NC.ink4 }}>·</span>
                  TSS {esc.tss_total}
                  <span style={{ marginLeft: 6, color: rCol, fontSize: 10 }}>
                    {(esc.riesgo*100).toFixed(0)}%
                  </span>
                </button>
              )
            })}
          </div>

          {/* Selected scenario detail */}
          {mejores[escSel] && <EscenarioCoach esc={mejores[escSel]} />}
        </>
      )}

      {data && !data.ok && (
        <div style={{ padding: 20, fontSize: 12, color: NC.ink3 }}>
          {data.error || 'No se pudo ejecutar'}
        </div>
      )}
    </div>
  )
}


function EscenarioCoach({ esc }) {
  const plan = esc.plan || []
  const rCol = esc.riesgo < 0.15 ? NC.ok : esc.riesgo < 0.40 ? NC.warn : NC.bad

  return (
    <div style={{
      background: 'linear-gradient(165deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.02) 100%)',
      borderRadius: 14, padding: '16px 18px',
      border: '1px solid rgba(255,255,255,0.09)',
      boxShadow: '0 8px 24px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.06)',
    }}>
      {/* Header + visual strip */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: NC.ink }}>Escenario #{esc.id}</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[
            { l: 'TSS', v: esc.tss_total, c: NC.ink },
            { l: 'Riesgo', v: `${(esc.riesgo*100).toFixed(0)}%`, c: rCol },
            { l: 'Score', v: esc.ranking?.toFixed(0), c: NC.accent },
          ].map(b => (
            <span key={b.l} style={{ fontSize: 9, color: NC.ink4 }}>
              {b.l} <strong style={{ color: b.c, fontSize: 11 }}>{b.v}</strong>
            </span>
          ))}
        </div>
      </div>

      <WeekStrip plan={plan} />

      {/* Days */}
      <div style={{ marginTop: 6 }}>
        {plan.map((dia, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 10, padding: '9px 0',
            borderBottom: i < plan.length - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
          }}>
            <div style={{ width: 28, fontSize: 10, fontWeight: 700, color: NC.ink4, paddingTop: 2 }}>
              {(dia.dia || '').substring(0, 3)}
            </div>
            {dia.sesion === 'DESCANSO' ? (
              <div style={{ fontSize: 11, color: NC.ink4, fontStyle: 'italic' }}>Descanso</div>
            ) : (
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 5, height: 5, borderRadius: 3,
                    background: SP[dia.sport]?.c || NC.ink4,
                    boxShadow: `0 0 4px ${SP[dia.sport]?.c || NC.ink4}66` }} />
                  <span style={{ fontSize: 11, fontWeight: 600, color: NC.ink }}>{dia.tipo}</span>
                  <span style={{
                    fontSize: 9, color: INT_COL[dia.intensidad] || NC.ink4,
                    padding: '1px 6px', borderRadius: 4, background: 'rgba(255,255,255,0.04)',
                  }}>
                    {dia.intensidad}
                  </span>
                  <span style={{ fontSize: 9, color: NC.ink4, marginLeft: 'auto' }}>
                    {dia.duracion}' · TSS {dia.tss}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: NC.ink3, marginTop: 3, lineHeight: 1.4 }}>
                  {dia.descripcion}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default TwinAtleta
