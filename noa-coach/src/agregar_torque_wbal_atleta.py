path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Agregar estado para los botones torque/wbal en GraficoActividad ───────
# Insertamos los botones después del gráfico premium, solo para ciclismo
viejo = """      {/* Gráfico premium */}
      <div style={{padding:'12px 18px',borderBottom:`1px solid ${NOAH_C.border}`}}>
        <GraficoActividad act={act} laps={laps} sport={sport} lthr={LTHR}
          sesionId={act.sesion_id || act.id} atletaId={atletaId}/>
      </div>

      {/* Tabla de laps expandible */}"""

nuevo = """      {/* Gráfico premium */}
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

      {/* Tabla de laps expandible */}"""

if viejo in contenido:
    contenido = contenido.replace(viejo, nuevo, 1); cambios += 1
    print("OK 1/2: botones TorqueWbal agregados en ActividadRealizada")
else:
    print("AVISO 1/2: no se encontró el bloque del gráfico premium")

# ── 2. Agregar el componente TorqueWbalBotones antes del export default ───────
comp = '''
// ── TorqueWbalBotones — análisis de ciclismo bajo demanda en el atleta ──────
function TorqueWbalBotones({ atletaId, sesionId, ftp = 200, cadenciaOptima = 85 }) {
  const [vista,      setVista]   = React.useState(null) // null | 'torque' | 'wbal'
  const [data,       setData]    = React.useState(null)
  const [cargando,   setCargando] = React.useState(false)

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
              Calculando W\'bal...
            </div>
          )}
          {data && lineData.length > 0 && (
            <>
              <div style={{ display:'flex', gap:8, marginBottom:12 }}>
                <div style={{ flex:1, background:'rgba(34,197,94,0.1)', borderRadius:8, padding:'8px 12px', border:'1px solid rgba(34,197,94,0.25)' }}>
                  <div style={{ fontSize:10, color:NOAH_C.ink3 }}>W\'bal final</div>
                  <div style={{ fontSize:18, fontWeight:800, color:'#22C55E' }}>{metricas?.wbal_final_pct??'--'}%</div>
                </div>
                <div style={{ flex:1, background:'rgba(249,115,22,0.1)', borderRadius:8, padding:'8px 12px', border:'1px solid rgba(249,115,22,0.25)' }}>
                  <div style={{ fontSize:10, color:NOAH_C.ink3 }}>Vaciados críticos</div>
                  <div style={{ fontSize:18, fontWeight:800, color:'#F97316' }}>{metricas?.vaciados_criticos??'--'}</div>
                </div>
              </div>
              <div style={{ fontSize:11, color:NOAH_C.ink3, marginBottom:6 }}>
                Verde = W\'bal (%) · Línea punteada = límite crítico 30%
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
                  ✓ Excelente gestión de energía — W\' siempre sobre el 30%.
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

'''

# Insertar antes del export default
marcador = "\nexport default function AtletaDashboard"
if marcador in contenido:
    contenido = contenido.replace(marcador, comp + marcador, 1); cambios += 1
    print("OK 2/2: componente TorqueWbalBotones agregado al atleta")
else:
    print("AVISO 2/2: no se encontró export default function AtletaDashboard")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 2)")
