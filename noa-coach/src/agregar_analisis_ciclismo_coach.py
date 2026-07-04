path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Agregar tab al array de tabs ──────────────────────────────────────────
viejo_tabs = "},{id:'aprendizaje',label:'📈 Aprendizaje'}]"
nuevo_tabs  = "},{id:'aprendizaje',label:'📈 Aprendizaje'},{id:'analisis_ciclismo',label:'⚡ Análisis Ciclismo'}]"
if viejo_tabs in contenido:
    contenido = contenido.replace(viejo_tabs, nuevo_tabs, 1); cambios += 1
    print("OK 1/3: tab Análisis Ciclismo agregado")
else:
    print("AVISO 1/3: no se encontró el array de tabs")

# ── 2. Renderizar el nuevo tab ────────────────────────────────────────────────
viejo_render = "{tab==='aprendizaje'&&atletaId&&<AprendizajePanel atletaId={atletaId} atleta={atleta} />}"
nuevo_render = """{tab==='aprendizaje'&&atletaId&&<AprendizajePanel atletaId={atletaId} atleta={atleta} />}
      {tab==='analisis_ciclismo'&&atletaId&&<AnalisisCiclismoPanel atletaId={atletaId} atleta={atleta} ftp={atleta?.ftp_watts||200} cadenciaOptima={atleta?.cadencia_optima||85} />}"""
if viejo_render in contenido:
    contenido = contenido.replace(viejo_render, nuevo_render, 1); cambios += 1
    print("OK 2/3: render del tab agregado")
else:
    print("AVISO 2/3: no se encontró el render de aprendizaje")

# ── 3. Agregar el componente AnalisisCiclismoPanel antes del export default ──
componente = '''
// ── Análisis Ciclismo — Torque y W'bal ──────────────────────────────────────
function AnalisisCiclismoPanel({ atletaId, atleta, ftp = 200, cadenciaOptima = 85 }) {
  const [fecha,      setFecha]     = React.useState(new Date().toISOString().slice(0,10))
  const [sesiones,   setSesiones]  = React.useState([])
  const [sesionId,   setSesionId]  = React.useState(null)
  const [data,       setData]      = React.useState(null)
  const [cargando,   setCargando]  = React.useState(false)
  const [vista,      setVista]     = React.useState(null) // 'torque' | 'wbal'
  const [loadingAnal,setLoadingAnal] = React.useState(false)

  // Cargar sesiones de ciclismo del atleta al cambiar fecha
  React.useEffect(() => {
    if (!atletaId) return
    setSesiones([]); setSesionId(null); setData(null); setVista(null)
    authFetch(`${API}/atletas/${atletaId}/sesiones?limit=30`)
      .then(r => r.json())
      .then(r => {
        const ses = (r.data || r || []).filter(s =>
          s.sport === 'cycling' && s.fecha?.slice(0,10) === fecha
        )
        setSesiones(ses)
        if (ses.length === 1) setSesionId(ses[0].id)
      })
      .catch(() => {})
  }, [atletaId, fecha])

  // Buscar sesiones de ciclismo en un rango si no hay en fecha exacta
  React.useEffect(() => {
    if (!atletaId) return
    setSesiones([]); setSesionId(null); setData(null); setVista(null)
    // Buscar en los últimos 90 días para el selector
    authFetch(`${API}/atletas/${atletaId}/sesiones?limit=100`)
      .then(r => r.json())
      .then(r => {
        const ses = (r.data || r || []).filter(s => s.sport === 'cycling')
        setSesiones(ses)
      })
      .catch(() => {})
  }, [atletaId])

  const analizar = async () => {
    if (!sesionId) return
    setLoadingAnal(true); setData(null)
    try {
      const r = await authFetch(`${API}/atletas/${atletaId}/sesiones/${sesionId}/torque_wbal`)
      const d = await r.json()
      setData(d.data || d)
    } catch {}
    setLoadingAnal(false)
  }

  const Q_COLOR = { Q1:'#F97316', Q2:'#EF4444', Q3:'#22C55E', Q4:'#3B82F6' }
  const Q_DESC  = {
    Q1:'Explosivo (fuerza alta + cadencia alta)',
    Q2:'⚠ Veneno triatlón (fuerza alta + cadencia baja)',
    Q3:'Recuperación aeróbica',
    Q4:'Eficiencia cardiovascular',
  }

  const torque_umbral = ftp > 0 && cadenciaOptima > 0
    ? Math.round((9.549 * ftp) / cadenciaOptima) : 30

  const { samples=[], cuadrantes={}, metricas={} } = data || {}

  // Datos para scatter (max 1500 pts)
  const step1 = Math.max(1, Math.floor(samples.length / 1500))
  const scatterData = samples
    .filter((_,i) => i % step1 === 0 && samples[i].cadence > 0)
    .map(s => ({ x: s.cadence, y: s.torque, w: s.wbal_pct }))

  // Datos para W'bal temporal (max 400 pts)
  const step2 = Math.max(1, Math.floor(samples.length / 400))
  const lineData = samples
    .filter((_,i) => i % step2 === 0)
    .map(s => ({ t: Math.round(s.ts_s / 60), wbal: s.wbal_pct, torque: s.torque }))

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16, padding:'4px 0' }}>
      <SectionTitle>Análisis de Ciclismo — Torque & W\'bal</SectionTitle>

      {/* Selector */}
      <Card>
        <div style={{ display:'flex', gap:10, alignItems:'flex-end', flexWrap:'wrap' }}>
          <div style={{ flex:1, minWidth:160 }}>
            <div style={{ fontSize:11, color:C.text2, marginBottom:4 }}>Sesión de ciclismo</div>
            <select value={sesionId||''} onChange={e => { setSesionId(Number(e.target.value)); setData(null); setVista(null) }}
              style={{ width:'100%', padding:'8px 10px', borderRadius:8, fontSize:13,
                background:C.bg, color:C.text, border:`1px solid ${C.border}` }}>
              <option value="">— Elegí una sesión —</option>
              {sesiones.map(s => (
                <option key={s.id} value={s.id}>
                  {s.fecha?.slice(0,10)} · {Math.round(s.duration||0)}min · {s.tss ? `TSS ${Math.round(s.tss)}` : ''}
                </option>
              ))}
            </select>
          </div>
          <button onClick={analizar} disabled={!sesionId || loadingAnal} style={{
            padding:'9px 20px', borderRadius:9, fontSize:13, fontWeight:700,
            background: sesionId ? '#007AFF' : C.bg2,
            color: sesionId ? '#fff' : C.text2,
            border:'none', cursor: sesionId ? 'pointer' : 'default',
            boxShadow: sesionId ? '0 4px 12px rgba(0,122,255,0.35)' : 'none',
            display:'flex', alignItems:'center', gap:6,
          }}>
            {loadingAnal ? '⏳ Calculando...' : '⚡ Analizar'}
          </button>
        </div>
        {sesiones.length === 0 && (
          <div style={{ fontSize:12, color:C.text2, marginTop:8 }}>
            Sin sesiones de ciclismo encontradas para este atleta.
          </div>
        )}
      </Card>

      {/* Resultado */}
      {data && (
        <>
          {/* Tarjetas métricas */}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:8 }}>
            {[
              { label:'% tiempo Q2', value:`${cuadrantes?.Q2??'--'}%`, color:'#EF4444', icon:'⚠', desc:'Veneno triatlón' },
              { label:"W'bal final",  value:`${metricas?.wbal_final_pct??'--'}%`, color:'#22C55E', icon:'🔋', desc:'Batería anaeróbica restante' },
              { label:'Vaciados críticos', value:metricas?.vaciados_criticos??'--', color:'#F97316', icon:'⚡', desc:"Veces bajo 30% W'" },
              { label:'NME', value:metricas?.nme?metricas.nme.toFixed(1):'--', color:'#3B82F6', icon:'⚙', desc:'Eficiencia neuromuscular' },
            ].map(({ label, value, color, icon, desc }) => (
              <div key={label} style={{
                background:`${color}12`, borderRadius:10, padding:'12px 14px',
                border:`1px solid ${color}30`,
              }}>
                <div style={{ fontSize:11, color:C.text2, marginBottom:4 }}>{icon} {label}</div>
                <div style={{ fontSize:22, fontWeight:800, color }}>{value}</div>
                <div style={{ fontSize:10, color:C.text2, marginTop:2 }}>{desc}</div>
              </div>
            ))}
          </div>

          {/* Botones torque / wbal */}
          <div style={{ display:'flex', gap:10 }}>
            {[['torque','⚙ Torque vs Cadencia'],['wbal',"🔋 W'bal Temporal"]].map(([v, label]) => (
              <button key={v} onClick={() => setVista(vista===v ? null : v)} style={{
                flex:1, padding:'11px 16px', borderRadius:10, fontSize:13, fontWeight:700,
                background: vista===v ? '#007AFF' : C.bg,
                color: vista===v ? '#fff' : C.text2,
                border:`1px solid ${vista===v ? '#007AFF' : C.border}`,
                cursor:'pointer',
                boxShadow: vista===v ? '0 4px 12px rgba(0,122,255,0.35)' : 'none',
              }}>{label}</button>
            ))}
          </div>

          {/* Gráfico de cuadrantes */}
          {vista === 'torque' && scatterData.length > 0 && (
            <Card>
              <div style={{ fontSize:12, color:C.text2, marginBottom:8 }}>
                Cada punto = 1 seg · Eje X = Cadencia (RPM) · Eje Y = Torque (N·m)
                · Líneas = FTP ({metricas.ftp_usado}W) / Cadencia óptima ({metricas.cadencia_optima}rpm)
              </div>
              <ScatterChart width={Math.min(window.innerWidth - 80, 600)} height={260}>
                <CartesianGrid stroke="rgba(255,255,255,0.06)" />
                <XAxis dataKey="x" type="number" domain={[40,130]} name="Cadencia"
                  tick={{ fill:C.text2, fontSize:10 }}
                  label={{ value:'RPM', position:'insideBottom', offset:-2, fill:C.text2, fontSize:10 }}/>
                <YAxis dataKey="y" type="number" name="Torque"
                  tick={{ fill:C.text2, fontSize:10 }}
                  label={{ value:'N·m', angle:-90, position:'insideLeft', fill:C.text2, fontSize:10 }}/>
                <Tooltip contentStyle={{ background:'#1C1C1E', border:`1px solid ${C.border}`, borderRadius:8, fontSize:11 }}
                  formatter={(v,n) => [v, n==='x'?'Cadencia (RPM)':'Torque (N·m)']} />
                <ReferenceLine x={cadenciaOptima} stroke="rgba(255,255,255,0.2)" strokeDasharray="4 4"
                  label={{ value:`${cadenciaOptima}rpm`, fill:'rgba(255,255,255,0.3)', fontSize:9 }}/>
                <ReferenceLine y={torque_umbral} stroke="rgba(255,255,255,0.2)" strokeDasharray="4 4"
                  label={{ value:`${torque_umbral}N·m`, fill:'rgba(255,255,255,0.3)', fontSize:9 }}/>
                <Scatter data={scatterData} shape={(p) => {
                  const { cx, cy, payload } = p
                  const q = payload.y > torque_umbral && payload.x >= cadenciaOptima ? 'Q1'
                          : payload.y > torque_umbral && payload.x < cadenciaOptima  ? 'Q2'
                          : payload.y <= torque_umbral && payload.x < cadenciaOptima  ? 'Q3' : 'Q4'
                  return <circle cx={cx} cy={cy} r={2.5} fill={Q_COLOR[q]} fillOpacity={0.65}/>
                }}/>
              </ScatterChart>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:6, marginTop:8 }}>
                {Object.entries(Q_DESC).map(([q,desc]) => (
                  <div key={q} style={{ display:'flex', alignItems:'center', gap:6, fontSize:10, color:C.text2 }}>
                    <div style={{ width:8,height:8,borderRadius:'50%',background:Q_COLOR[q],flexShrink:0 }}/>
                    <span><b style={{color:Q_COLOR[q]}}>{q} {cuadrantes?.[q]}%</b> — {desc}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Gráfico W'bal */}
          {vista === 'wbal' && lineData.length > 0 && (
            <Card>
              <div style={{ fontSize:12, color:C.text2, marginBottom:8 }}>
                Verde = W\'bal (batería anaeróbica) · Rojo = Torque · Línea punteada = límite crítico 30%
              </div>
              <AreaChart width={Math.min(window.innerWidth - 80, 600)} height={240} data={lineData}>
                <defs>
                  <linearGradient id="wG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#22C55E" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#22C55E" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="tG" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#EF4444" stopOpacity={0.2}/>
                    <stop offset="95%" stopColor="#EF4444" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(255,255,255,0.06)"/>
                <XAxis dataKey="t" tick={{ fill:C.text2, fontSize:10 }}
                  label={{ value:'min', position:'insideBottom', offset:-2, fill:C.text2, fontSize:10 }}/>
                <YAxis yAxisId="w" domain={[0,100]} tick={{ fill:'#22C55E', fontSize:10 }}/>
                <YAxis yAxisId="t" orientation="right" tick={{ fill:'#EF4444', fontSize:10 }}/>
                <Tooltip contentStyle={{ background:'#1C1C1E', border:`1px solid ${C.border}`, borderRadius:8, fontSize:11 }}
                  formatter={(v,n) => [n==='wbal' ? `${v?.toFixed(0)}%` : `${v?.toFixed(0)} N·m`, n==='wbal'?"W'bal":'Torque']}/>
                <ReferenceLine yAxisId="w" y={30} stroke="#EF4444" strokeOpacity={0.5} strokeDasharray="4 4"
                  label={{ value:'Crítico 30%', fill:'#EF4444', fontSize:9 }}/>
                <Area yAxisId="w" type="monotone" dataKey="wbal" stroke="#22C55E" strokeWidth={2} fill="url(#wG)" dot={false}/>
                <Area yAxisId="t" type="monotone" dataKey="torque" stroke="#EF4444" strokeWidth={1.5} fill="url(#tG)" dot={false} opacity={0.8}/>
              </AreaChart>
              {metricas?.vaciados_criticos > 0 && (
                <div style={{ marginTop:8, padding:'10px 14px', borderRadius:8,
                  background:'rgba(239,68,68,0.1)', border:'1px solid rgba(239,68,68,0.25)',
                  fontSize:12, color:'#FCA5A5' }}>
                  ⚡ {metricas.vaciados_criticos} vaciado{metricas.vaciados_criticos>1?'s':''} crítico{metricas.vaciados_criticos>1?'s':''} — 
                  W\' bajó del 30% en {metricas.vaciados_criticos} ocasión{metricas.vaciados_criticos>1?'es':''}.
                  {cuadrantes?.Q2 > 15 && ` Pasó ${cuadrantes.Q2}% en Q2 — recomendar elevar cadencia.`}
                </div>
              )}
              {metricas?.vaciados_criticos === 0 && (
                <div style={{ marginTop:8, padding:'10px 14px', borderRadius:8,
                  background:'rgba(34,197,94,0.08)', border:'1px solid rgba(34,197,94,0.2)',
                  fontSize:12, color:'#86EFAC' }}>
                  ✓ Excelente gestión energética — W\' siempre sobre el límite crítico.
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </div>
  )
}

'''

# Insertar antes del export default
marcador = "\nexport default function "
if marcador in contenido:
    contenido = contenido.replace(marcador, componente + marcador, 1); cambios += 1
    print("OK 3/3: componente AnalisisCiclismoPanel agregado")
else:
    print("AVISO 3/3: no se encontró 'export default function'")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 3)")
