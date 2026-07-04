// src/App.js — NOA Coach Dashboard
import { useState, useEffect } from 'react'
import axios from 'axios'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, BarChart, Bar, Cell } from 'recharts'
const API = 'http://localhost:5000/api'
const colors = {
  bg:'#0F0F13',bg2:'#18181F',bg3:'#22222C',border:'rgba(255,255,255,0.08)',
  purple:'#534AB7',purpleL:'#9B94E8',teal:'#1D9E75',amber:'#EF9F27',
  red:'#E24B4A',blue:'#378ADD',text:'#F5F4FF',text2:'#B8B6CC',text3:'#7A7890',
}
const css = `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: ${colors.bg}; color: ${colors.text}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
  ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-track { background: ${colors.bg2}; } ::-webkit-scrollbar-thumb { background: ${colors.bg3}; border-radius: 2px; }
  .btn { padding: 8px 16px; border-radius: 8px; border: 0.5px solid ${colors.border}; background: ${colors.bg3}; color: ${colors.text}; cursor: pointer; font-size: 13px; transition: all 0.15s; }
  .btn:hover { background: ${colors.purpleL}; color: #fff; }
  .btn-primary { background: ${colors.purple}; border-color: ${colors.purpleL}; color: #EEEDFE; }
  .btn-primary:hover { background: ${colors.purpleL}; }
  .pill-verde { background: rgba(29,158,117,0.2); color: #1D9E75; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
  .pill-amarillo { background: rgba(239,159,39,0.2); color: #EF9F27; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
  .pill-rojo { background: rgba(226,75,74,0.2); color: #E24B4A; padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 600; }
  input, select, textarea { background: ${colors.bg3}; border: 0.5px solid ${colors.border}; color: ${colors.text}; border-radius: 8px; padding: 8px 12px; font-size: 14px; width: 100%; outline: none; }
  input:focus, select:focus, textarea:focus { border-color: ${colors.purpleL}; }
  label { font-size: 12px; color: ${colors.text3}; margin-bottom: 4px; display: block; }
`
function Pill({ flag }) {
  if (!flag) return null
  return <span className={`pill-${flag}`}>{flag}</span>
}
function MetricCard({ label, value, sub, color }) {
  return (
    <div style={{ background: colors.bg2, border: `0.5px solid ${colors.border}`, borderRadius: 12, padding: '14px 12px', position: 'relative', overflow: 'hidden' }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: color || colors.purpleL, borderRadius: '12px 12px 0 0' }} />
      <div style={{ fontSize: 12, color: colors.text3, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value ?? '--'}</div>
      {sub && <div style={{ fontSize: 11, color: colors.text3, marginTop: 4 }}>{sub}</div>}
    </div>
  )
}
function SectionTitle({ children }) {
  return <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '1.5px', textTransform: 'uppercase', color: colors.text3, marginBottom: 12 }}>{children}</div>
}
function Card({ children, style }) {
  return <div style={{ background: colors.bg2, border: `0.5px solid ${colors.border}`, borderRadius: 12, overflow: 'hidden', ...style }}>{children}</div>
}
function CardRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 16px', borderBottom: `0.5px solid ${colors.border}` }}>
      <span style={{ fontSize: 13, color: colors.text2 }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: 500 }}>{value ?? '--'}</span>
    </div>
  )
}
function AtletaItem({ atleta, selected, onClick }) {
  const tsb = atleta.tsb
  const tsbColor = tsb > 5 ? colors.teal : tsb < -15 ? colors.red : colors.amber
  return (
    <div onClick={onClick} style={{ padding: '12px 16px', cursor: 'pointer', borderBottom: `0.5px solid ${colors.border}`, background: selected ? 'rgba(83,74,183,0.15)' : 'transparent', borderLeft: selected ? `2px solid ${colors.purpleL}` : '2px solid transparent', transition: 'all 0.15s' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>{atleta.nombre}</div>
          <div style={{ fontSize: 11, color: colors.text3, marginTop: 2 }}>{atleta.deporte}</div>
        </div>
        <Pill flag={atleta.hrv_flag} />
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
        <span style={{ fontSize: 12, color: colors.text3 }}>CTL <b style={{ color: colors.text }}>{atleta.ctl?.toFixed(0)}</b></span>
        <span style={{ fontSize: 12, color: colors.text3 }}>TSB <b style={{ color: tsbColor }}>{atleta.tsb?.toFixed(1)}</b></span>
        <span style={{ fontSize: 12, color: colors.text3 }}>LTHR <b style={{ color: colors.text }}>{atleta.lthr_run}</b></span>
      </div>
    </div>
  )
}
function BloqueItem({ bloque }) {
  const durStr = bloque.duracion_min < 1 ? `${Math.round(bloque.duracion_min * 60)}"` : `${Math.round(bloque.duracion_min)}'`
  const repsStr = bloque.repeticiones > 1 ? `${bloque.repeticiones}x` : ''
  const hrStr = bloque.hr_min ? `HR ${bloque.hr_min}-${bloque.hr_max}` : ''
  const paceStr = bloque.pace_ref ? `~${Math.floor(bloque.pace_ref)}:${String(Math.round((bloque.pace_ref % 1) * 60)).padStart(2, '0')} min/km` : ''
  const pausaStr = bloque.repeticiones > 1 && bloque.pausa_min ? ` / ${bloque.pausa_min < 1 ? `${Math.round(bloque.pausa_min * 60)}"` : `${Math.round(bloque.pausa_min)}'`} pausa ${bloque.pausa_activa ? 'activa' : 'pasiva'}` : ''
  return (
    <div style={{ padding: '6px 10px', background: colors.bg3, borderRadius: 6, fontSize: 12, color: colors.text2, lineHeight: 1.5, marginBottom: 4 }}>
      <span style={{ fontWeight: 700, color: colors.text, marginRight: 4 }}>{repsStr}{durStr}</span>
      <span style={{ color: colors.purpleL, marginRight: 4 }}>{bloque.zona} - {bloque.zona_nombre}</span>
      <span style={{ color: colors.text3 }}>{hrStr} {paceStr}{pausaStr}</span>
    </div>
  )
}
function SesionCard({ ses }) {
  return (
    <div style={{ borderBottom: `0.5px solid ${colors.border}`, padding: '14px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ fontSize: 11, color: colors.text3, fontWeight: 500 }}>{ses.dia} {ses.fecha ? ses.fecha.slice(5).replace('-', '/') : ''}</span>
        <span style={{ fontSize: 12, color: colors.purpleL, fontWeight: 600 }}>TSS {ses.tss}</span>
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{ses.nombre}</div>
      <div style={{ fontSize: 12, color: colors.text2, marginBottom: 8 }}>
        {ses.duracion ? `${Math.round(ses.duracion)} min` : '--'}
        {ses.hr_min ? ` - HR ${ses.hr_min}-${ses.hr_max} bpm` : ''}
      </div>
      {ses.bloques?.map((b, i) => <BloqueItem key={i} bloque={b} />)}
    </div>
  )
}
function TabDiagnostico({ diag }) {
  if (!diag) return <div style={{ padding: 24, color: colors.text3, textAlign: 'center' }}>Cargando diagnostico...</div>
  if (diag.error) return <div style={{ padding: 24, color: colors.text3 }}>{diag.resumen_coach || 'Sin datos suficientes.'}</div>

  const colMap = { verde: colors.teal, amarillo: colors.amber, rojo: colors.red }
  const scoreColor = colMap[diag.color] || colors.text3
  const dist = diag.distribucion || {}
  const real = dist.distribucion_real || {}
  const ideal = dist.distribucion_ideal || {}
  const gaps = dist.gaps || {}
  const proy = diag.proyeccion || {}

  const nivelColor = { alto: colors.red, moderado: colors.amber, info: colors.blue }

  // Bar chart data
  const barData = [
    { zona: 'Z1-Z2', real: real.z1z2_pct || 0, ideal: ideal.z1z2_pct || 0 },
    { zona: 'Z3-Z4', real: real.z3z4_pct || 0, ideal: ideal.z3z4_pct || 0 },
    { zona: 'Z5-Z6', real: real.z5z6_pct || 0, ideal: ideal.z5z6_pct || 0 },
  ]

  // Proyeccion chart
  const proyData = (proy.con_patron_actual?.proyeccion || []).map((v, i) => ({
    semana: `S${i+1}`,
    actual: v,
    correcto: proy.con_correccion?.proyeccion?.[i],
  }))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Score header */}
      <Card>
        <div style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16 }}>
          <div style={{ width: 56, height: 56, borderRadius: '50%', background: `${scoreColor}22`, border: `2px solid ${scoreColor}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, color: scoreColor }}>
            {diag.score_general}
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 4 }}>{diag.resumen_coach}</div>
            <div style={{ fontSize: 12, color: colors.text3 }}>
              {dist.total_horas}h analizadas · {dist.sesiones_n} sesiones · fase {dist.fase}
            </div>
          </div>
        </div>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* Distribucion de zonas */}
        <div>
          <SectionTitle>Distribucion real vs ideal</SectionTitle>
          <Card style={{ padding: 16 }}>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={barData} barCategoryGap="30%">
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="zona" tick={{ fill: colors.text3, fontSize: 11 }} />
                <YAxis tick={{ fill: colors.text3, fontSize: 10 }} unit="%" />
                <Tooltip contentStyle={{ background: colors.bg2, border: `0.5px solid ${colors.border}`, borderRadius: 8 }} formatter={(v) => `${v}%`} />
                <Bar dataKey="real" name="Real" fill={colors.purpleL} radius={[4,4,0,0]} />
                <Bar dataKey="ideal" name="Ideal" fill={colors.teal} radius={[4,4,0,0]} opacity={0.5} />
              </BarChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 12 }}>
              {[['Z1-Z2', real.z1z2_pct, ideal.z1z2_pct, gaps.z1z2],
                ['Z3-Z4', real.z3z4_pct, ideal.z3z4_pct, gaps.z3z4]].map(([z, r, id, g]) => (
                <div key={z} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '4px 0', borderBottom: `0.5px solid ${colors.border}` }}>
                  <span style={{ color: colors.text3 }}>{z}</span>
                  <span>Real <b>{r}%</b></span>
                  <span>Ideal <b style={{ color: colors.teal }}>{id}%</b></span>
                  <span style={{ color: g > 0 ? colors.red : colors.teal }}>{g > 0 ? '+' : ''}{g}%</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Proyeccion CTL */}
        <div>
          <SectionTitle>Proyeccion CTL — 16 semanas</SectionTitle>
          <Card style={{ padding: 16 }}>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={proyData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="semana" tick={{ fill: colors.text3, fontSize: 9 }} interval={3} />
                <YAxis tick={{ fill: colors.text3, fontSize: 10 }} />
                <Tooltip contentStyle={{ background: colors.bg2, border: `0.5px solid ${colors.border}`, borderRadius: 8 }} />
                <Line type="monotone" dataKey="actual" name="Sin cambio" stroke={colors.amber} dot={false} strokeWidth={2} strokeDasharray="4 3" />
                <Line type="monotone" dataKey="correcto" name="Con correccion" stroke={colors.teal} dot={false} strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
            <div style={{ marginTop: 8, fontSize: 12, color: colors.text3 }}>
              CTL actual: <b style={{ color: colors.text }}>{proy.ctl_actual}</b>
              {proy.con_correccion?.ganancia > 0 && (
                <span style={{ color: colors.teal, marginLeft: 8 }}>+{proy.con_correccion.ganancia} con correccion</span>
              )}
            </div>
          </Card>
        </div>
      </div>

      {/* Alertas */}
      {diag.alertas?.length > 0 && (
        <div>
          <SectionTitle>Alertas NOA</SectionTitle>
          <Card>
            {diag.alertas.map((a, i) => (
              <div key={i} style={{ padding: '12px 16px', borderBottom: `0.5px solid ${colors.border}`, display: 'flex', gap: 12 }}>
                <div style={{ width: 6, borderRadius: 3, background: nivelColor[a.nivel] || colors.text3, flexShrink: 0 }} />
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: nivelColor[a.nivel] || colors.text3, marginBottom: 4, textTransform: 'uppercase' }}>{a.nivel}</div>
                  <div style={{ fontSize: 13, color: colors.text2 }}>{a.texto_coach}</div>
                </div>
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  )
}
function ModalNuevoAtleta({ onClose, onCreado }) {
  const [form, setForm] = useState({ nombre: '', email: '', lthr_run: 155, hr_max: 185, edad: '', deporte_ppal: 'running' })
  const [loading, setLoading] = useState(false)
  const handleSubmit = async () => {
    if (!form.nombre || !form.email) return alert('Nombre y email son requeridos')
    setLoading(true)
    try { await axios.post(`${API}/atletas`, form); onCreado(); onClose() }
    catch (e) { alert('Error creando atleta') }
    setLoading(false)
  }
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
      <div style={{ background: colors.bg2, border: `0.5px solid ${colors.border}`, borderRadius: 16, padding: 24, width: 400, maxWidth: '90vw' }}>
        <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 20 }}>Nuevo atleta</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[['nombre','Nombre completo','text'],['email','Email','email'],['lthr_run','LTHR Running','number'],['hr_max','FC Maxima','number'],['edad','Edad','number']].map(([key, label, type]) => (
            <div key={key}><label>{label}</label><input type={type} value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} /></div>
          ))}
          <div><label>Deporte principal</label>
            <select value={form.deporte_ppal} onChange={e => setForm(f => ({ ...f, deporte_ppal: e.target.value }))}>
              <option value="running">Running</option>
              <option value="triatlon">Triatlon</option>
              <option value="cycling">Ciclismo</option>
              <option value="swim">Natacion</option>
            </select>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 20, justifyContent: 'flex-end' }}>
          <button className="btn" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={handleSubmit} disabled={loading}>{loading ? 'Creando...' : 'Crear atleta'}</button>
        </div>
      </div>
    </div>
  )
}
function DashboardAtleta({ atletaId, atleta }) {
  const [estado, setEstado] = useState(null)
  const [presc, setPresc] = useState(null)
  const [zonas, setZonas] = useState(null)
  const [health, setHealth] = useState(null)
  const [diag, setDiag] = useState(null)
  const [loadingCiclo, setLoadingCiclo] = useState(false)
  const [tab, setTab] = useState('prescripcion')
  useEffect(() => {
    if (!atletaId) return
    setEstado(null); setPresc(null); setZonas(null); setHealth(null); setDiag(null)
    axios.get(`${API}/atletas/${atletaId}/estado`).then(r => setEstado(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/prescripcion`).then(r => setPresc(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/zonas`).then(r => setZonas(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/health`).then(r => setHealth(r.data.data)).catch(()=>{})
    axios.get(`${API}/atletas/${atletaId}/diagnostico`).then(r => setDiag(r.data.data)).catch(()=>{})
  }, [atletaId])
  const generarCiclo = async () => {
    setLoadingCiclo(true)
    try { const r = await axios.post(`${API}/atletas/${atletaId}/ciclo`); setPresc(r.data.data); alert('Prescripcion generada') }
    catch (e) { alert('Error generando ciclo') }
    setLoadingCiclo(false)
  }
  if (!atleta) return <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.text3 }}>Selecciona un atleta</div>
  const ctl = estado?.estado?.ctl
  const atl = estado?.estado?.atl
  const tsb = estado?.estado?.tsb
  const tsbColor = tsb > 5 ? colors.teal : tsb < -15 ? colors.red : colors.amber
  const diagColor = { verde: colors.teal, amarillo: colors.amber, rojo: colors.red }
  const chartData = (estado?.training || []).slice(-60).map(d => ({ fecha: d.d?.slice(5), CTL: d.ctl, ATL: d.atl, TSB: d.tsb }))
  const tabs = ['prescripcion', 'estado', 'diagnostico', 'zonas']
  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700 }}>{atleta.nombre}</h1>
          <div style={{ fontSize: 13, color: colors.text3, marginTop: 2 }}>{atleta.deporte} - LTHR {atleta.lthr_run} - {atleta.email}</div>
        </div>
        <button className="btn btn-primary" onClick={generarCiclo} disabled={loadingCiclo}>{loadingCiclo ? 'Generando...' : 'Nuevo ciclo'}</button>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 24 }}>
        <MetricCard label="CTL" value={ctl?.toFixed(1)} sub="fitness" color={colors.blue} />
        <MetricCard label="ATL" value={atl?.toFixed(1)} sub="fatiga" color={colors.red} />
        <MetricCard label="TSB" value={<span style={{ color: tsbColor }}>{tsb?.toFixed(1)}</span>} sub="frescura" color={tsbColor} />
        <MetricCard label="NOA Score" value={health?.noa_score ? `${(health.noa_score * 100).toFixed(0)}%` : '--'} sub={health?.noa_score_nivel || 'sin datos'} color={health?.noa_score_color === 'verde' ? colors.teal : health?.noa_score_color === 'rojo' ? colors.red : colors.amber} />
        <MetricCard label="Diagnostico" value={diag?.score_general ? `${diag.score_general}/100` : '--'} sub={diag?.color || 'calculando'} color={diagColor[diag?.color] || colors.text3} />
      </div>
      <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
        {tabs.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding: '5px 14px', fontSize: 12, borderRadius: 99, border: `0.5px solid ${tab === t ? colors.purpleL : colors.border}`, background: tab === t ? 'rgba(83,74,183,0.15)' : 'transparent', color: tab === t ? colors.purpleL : colors.text3, cursor: 'pointer', fontWeight: tab === t ? 600 : 400 }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      {tab === 'prescripcion' && (
        <div>
          {presc?.prescripcion ? (
            <Card>
              <div style={{ padding: '12px 16px', background: colors.bg3, display: 'flex', justifyContent: 'space-between' }}>
                <div style={{ fontSize: 13, color: colors.text3 }}>Fase: <b style={{ color: colors.purpleL }}>{presc.prescripcion.fase}</b> - TSS: <b style={{ color: colors.text }}>{presc.prescripcion.tss_total}</b></div>
                <div style={{ fontSize: 11, color: colors.text3 }}>{presc.prescripcion.fecha_generada}</div>
              </div>
              {presc.prescripcion.sesiones?.map((ses, i) => <SesionCard key={i} ses={ses} />)}
            </Card>
          ) : (
            <Card><div style={{ padding: 24, textAlign: 'center', color: colors.text3 }}>Sin prescripcion. <br/><button className="btn btn-primary" style={{ marginTop: 12 }} onClick={generarCiclo}>Generar ciclo</button></div></Card>
          )}
        </div>
      )}
      {tab === 'estado' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div>
            <SectionTitle>Recuperacion</SectionTitle>
            <Card>
              <CardRow label="HRV ratio" value={<>{estado?.estado?.hrv_ratio ?? '--'} <Pill flag={estado?.estado?.hrv_flag} /></>} />
              <CardRow label="HRV nocturno" value={`${estado?.estado?.hrv_ms ?? '--'} ms`} />
              <CardRow label="Sueno" value={`${estado?.estado?.sleep_h ?? '--'} h`} />
              <CardRow label="Deep / REM" value={`${estado?.estado?.deep_h ?? '--'} / ${estado?.estado?.rem_h ?? '--'} h`} />
              <CardRow label="Recovery" value={`${estado?.estado?.recovery ?? '--'} /100`} />
            </Card>
          </div>
          <div>
            <SectionTitle>CTL / ATL / TSB</SectionTitle>
            <Card style={{ padding: 16 }}>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="fecha" tick={{ fill: colors.text3, fontSize: 10 }} />
                  <YAxis tick={{ fill: colors.text3, fontSize: 10 }} />
                  <Tooltip contentStyle={{ background: colors.bg2, border: `0.5px solid ${colors.border}`, borderRadius: 8 }} />
                  <Line type="monotone" dataKey="CTL" stroke={colors.blue} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="ATL" stroke={colors.red} dot={false} strokeWidth={2} />
                  <Line type="monotone" dataKey="TSB" stroke={colors.teal} dot={false} strokeWidth={1.5} strokeDasharray="4 3" />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>
        </div>
      )}
      {tab === 'diagnostico' && <TabDiagnostico diag={diag} />}
      {tab === 'zonas' && zonas && (
        <div>
          <SectionTitle>Zonas - {atleta.nombre}</SectionTitle>
          <Card>
            {Object.entries(zonas.zonas || {}).map(([zona, z]) => (
              <div key={zona} style={{ padding: '12px 16px', borderBottom: `0.5px solid ${colors.border}` }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontWeight: 600 }}>{zona} - {z.nombre}</span>
                  <span style={{ fontSize: 12, color: colors.text3 }}>HR {z.hr_min}-{z.hr_max} bpm{z.pace_ref ? ` - ${z.pace_ref}` : ''}</span>
                </div>
                <div style={{ fontSize: 11, color: colors.text3 }}>VO2: {z.vo2_pct} - Lactato: {z.lactato}</div>
                <div style={{ fontSize: 11, color: colors.text3, marginTop: 2 }}>{z.referencia}</div>
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  )
}
export default function App() {
  const [atletas, setAtletas] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [loading, setLoading] = useState(true)
  const cargarAtletas = async () => {
    try {
      const r = await axios.get(`${API}/atletas`)
      setAtletas(r.data.data)
      if (!selectedId && r.data.data.length > 0) setSelectedId(r.data.data[0].id)
    } catch (e) { console.error(e) }
    setLoading(false)
  }
  useEffect(() => { cargarAtletas() }, [])
  const selectedAtleta = atletas.find(a => a.id === selectedId) || null
  return (
    <>
      <style>{css}</style>
      <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
        <div style={{ width: 280, flexShrink: 0, background: colors.bg2, borderRight: `0.5px solid ${colors.border}`, display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '20px 16px 16px', borderBottom: `0.5px solid ${colors.border}` }}>
            <div style={{ fontSize: 24, fontWeight: 700, letterSpacing: 4 }}>N<span style={{ color: colors.purpleL }}>O</span>A</div>
            <div style={{ fontSize: 10, color: colors.text3, letterSpacing: 1, marginTop: 2 }}>COACH DASHBOARD</div>
          </div>
          <div style={{ flex: 1, overflow: 'auto' }}>
            {loading ? <div style={{ padding: 16, color: colors.text3, fontSize: 13 }}>Cargando...</div>
              : atletas.map(a => (
                <AtletaItem key={a.id} atleta={a} selected={selectedId === a.id} onClick={() => setSelectedId(a.id)} />
              ))}
          </div>
          <div style={{ padding: 12, borderTop: `0.5px solid ${colors.border}` }}>
            <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => setShowModal(true)}>+ Agregar atleta</button>
          </div>
        </div>
        <DashboardAtleta key={selectedId} atletaId={selectedId} atleta={selectedAtleta} />
      </div>
      {showModal && <ModalNuevoAtleta onClose={() => setShowModal(false)} onCreado={cargarAtletas} />}
    </>
  )
}
