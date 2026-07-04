path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. ZonasRunningTable ─────────────────────────────────────────────────────
viejo_run = """function ZonasRunningTable({ zonas, lthr }) {
  // API returns zonas as object {Z1:{...}} or array — normalize to array
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw)
    ? _raw
    : (_raw && typeof _raw === 'object')
      ? Object.entries(_raw).map(([zona, d]) => ({zona, ...d}))
      : null
  const rec   = zonas?.recomendacion || zonas?.data?.recomendacion
  const tsb   = zonas?.tsb || zonas?.data?.tsb

  if (!lista?.length) return (
    <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>
      Sin datos de zonas running
      {!lthr && <div style={{fontSize:11,color:NOAH_C.ink4,marginTop:4}}>Configurá el LTHR en el perfil del atleta</div>}
    </div>
  )

  const ZONA_COLORS = {
    Z1:'#94A3B8', Z2:NOAH_C.success, Z3:'#84CC16',
    Z4:NOAH_C.warning, Z5:'#F97316', Z6:NOAH_C.danger, Z7:'#9333EA'
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {/* Recomendación adaptativa */}
      {rec && (
        <div style={{
          padding:'10px 14px', borderRadius:8, marginBottom:12,
          background:`${rec.color}12`, border:`1px solid ${rec.color}30`,
          display:'flex', alignItems:'center', gap:8
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:rec.color,flexShrink:0}}/>
          <span style={{fontSize:12,color:'#374151'}}>{rec.msg}</span>
        </div>
      )}
      {lista.map((z, i) => {
        const isOk     = !rec || rec.zonas_ok.includes(z.zona||`Z${i+1}`)
        const zColor   = ZONA_COLORS[z.zona||`Z${i+1}`] || '#94A3B8'
        return (
          <div key={i} style={{
            display:'flex', alignItems:'center', gap:12,
            padding:'10px 14px', borderRadius:8, marginBottom:4,
            background: isOk ? `${zColor}08` : 'rgba(0,0,0,0.02)',
            border:`1px solid ${isOk ? zColor+'22' : '#E5E7EB'}`,
            opacity: isOk ? 1 : 0.5,
            transition:'all 0.15s',
          }}>
            <div style={{
              width:36, height:36, borderRadius:8, flexShrink:0,
              background:`${zColor}20`,
              display:'flex', alignItems:'center', justifyContent:'center',
              fontSize:13, fontWeight:800, color:zColor,
            }}>
              {z.zona||`Z${i+1}`}
            </div>
            <div style={{flex:1}}>
              <div style={{fontSize:13,fontWeight:700,color:NOAH_C.ink}}>{z.nombre}</div>
              <div style={{fontSize:11,color:NOAH_C.ink3,marginTop:2}}>{z.descripcion||''}</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontSize:12,fontWeight:700,color:zColor}}>
                {z.hr_min && z.hr_max ? `HR ${z.hr_min}–${z.hr_max}` : '--'}
              </div>
              {z.pace_min && (
                <div style={{fontSize:11,color:NOAH_C.ink3}}>
                  {z.pace_min} – {z.pace_max} /km
                </div>
              )}
            </div>
            {!isOk && (
              <div style={{
                padding:'2px 8px', borderRadius:99, fontSize:9, fontWeight:700,
                background:'rgba(239,68,68,0.1)', color:NOAH_C.danger,
                border:'1px solid rgba(239,68,68,0.2)', flexShrink:0,
              }}>EVITAR</div>
            )}
          </div>
        )
      })}
    </div>
  )
}"""

nuevo_run = """function ZonasRunningTable({ zonas, lthr }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw)
    ? _raw
    : (_raw && typeof _raw === 'object')
      ? Object.entries(_raw).map(([zona, d]) => ({zona, ...d}))
      : null
  const rec = zonas?.recomendacion || zonas?.data?.recomendacion

  if (!lista?.length) return (
    <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>
      Sin datos de zonas running
      {!lthr && <div style={{fontSize:11,color:NOAH_C.ink4,marginTop:4}}>Configurá el LTHR en el perfil del atleta</div>}
    </div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {rec && (
        <div style={{
          padding:'10px 14px', borderRadius:8, marginBottom:12,
          background:`${rec.color}12`, border:`1px solid ${rec.color}30`,
          display:'flex', alignItems:'center', gap:8
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:rec.color,flexShrink:0}}/>
          <span style={{fontSize:12,color:NOAH_C.ink3}}>{rec.msg}</span>
        </div>
      )}
      {lista.map((z, i) => {
        const zColor = z.color || NOAH_C.run
        const pace_rango = z.pace_rango || (z.pace_min && z.pace_max ? `${z.pace_min} – ${z.pace_max} /km` : null)
        return (
          <div key={i} style={{
            padding:'13px 16px', borderBottom:`1px solid ${NOAH_C.border}`,
            display:'flex', justifyContent:'space-between', alignItems:'center',
            borderLeft:`4px solid ${zColor}`,
            background:`${zColor}12`,
          }}>
            <div>
              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600}}>{z.nombre}</span>
              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontSize:14, fontWeight:700, color:zColor}}>{pace_rango || '--'}</div>
              <div style={{fontSize:11, color:NOAH_C.ink3}}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}"""

if viejo_run in contenido:
    contenido = contenido.replace(viejo_run, nuevo_run, 1); cambios += 1
    print("OK 1/3: ZonasRunningTable reescrito igual que coach")
else:
    print("AVISO 1/3: no se encontro ZonasRunningTable exacta")

# ── 2. ZonasCyclingTable ─────────────────────────────────────────────────────
viejo_bike = """function ZonasCyclingTable({ zonas }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw)
    ? _raw
    : (_raw && typeof _raw === 'object')
      ? Object.entries(_raw).map(([zona, d]) => ({zona, ...d}))
      : null
  const rec   = zonas?.recomendacion || zonas?.data?.recomendacion

  if (!lista?.length) return (
    <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>Sin datos de zonas ciclismo</div>
  )

  const ZONA_COLORS = {
    Z1:'#94A3B8', Z2:NOAH_C.success, Z3:'#84CC16',
    Z4:NOAH_C.warning, Z5:'#F97316', Z6:NOAH_C.danger, Z7:'#9333EA'
  }

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {rec && (
        <div style={{
          padding:'10px 14px', borderRadius:8, marginBottom:12,
          background:`${rec.color}12`, border:`1px solid ${rec.color}30`,
          display:'flex', alignItems:'center', gap:8
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:rec.color,flexShrink:0}}/>
          <span style={{fontSize:12,color:'#374151'}}>{rec.msg}</span>
        </div>
      )}
      {lista.map((z, i) => {
        const isOk   = !rec || rec.zonas_ok.includes(z.zona||`Z${i+1}`)
        const zColor = ZONA_COLORS[z.zona||`Z${i+1}`] || '#94A3B8'
        return (
          <div key={i} style={{
            display:'flex', alignItems:'center', gap:12,
            padding:'10px 14px', borderRadius:8, marginBottom:4,
            background: isOk ? `${zColor}08` : 'rgba(0,0,0,0.02)',
            border:`1px solid ${isOk ? zColor+'22' : '#E5E7EB'}`,
            opacity: isOk ? 1 : 0.5,
          }}>
            <div style={{
              width:36, height:36, borderRadius:8, flexShrink:0,
              background:`${zColor}20`,
              display:'flex', alignItems:'center', justifyContent:'center',
              fontSize:13, fontWeight:800, color:zColor,
            }}>
              {z.zona||`Z${i+1}`}
            </div>
            <div style={{flex:1}}>
              <div style={{fontSize:13,fontWeight:700,color:NOAH_C.ink}}>{z.nombre}</div>
              <div style={{fontSize:11,color:NOAH_C.ink3,marginTop:2}}>{z.descripcion||''}</div>
            </div>
            <div style={{textAlign:'right'}}>
              {(z.w_min != null) && (
                <div style={{fontSize:12,fontWeight:700,color:zColor}}>
                  {z.w_min}–{z.w_max ? z.w_max+'W' : '∞'}
                </div>
              )}
              {z.pct_ftp && (
                <div style={{fontSize:11,color:NOAH_C.ink3}}>{z.pct_ftp} FTP</div>
              )}
              {z.hr_min && (
                <div style={{fontSize:11,color:NOAH_C.ink3}}>
                  HR {z.hr_min}–{z.hr_max}
                </div>
              )}
              {z.wkg_min && (
                <div style={{fontSize:10,color:NOAH_C.ink4}}>
                  {z.wkg_min}–{z.wkg_max||'∞'} w/kg
                </div>
              )}
            </div>
            {!isOk && (
              <div style={{
                padding:'2px 8px', borderRadius:99, fontSize:9, fontWeight:700,
                background:'rgba(239,68,68,0.1)', color:NOAH_C.danger,
                border:'1px solid rgba(239,68,68,0.2)', flexShrink:0,
              }}>EVITAR</div>
            )}
          </div>
        )
      })}
    </div>
  )
}"""

nuevo_bike = """function ZonasCyclingTable({ zonas }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw)
    ? _raw
    : (_raw && typeof _raw === 'object')
      ? Object.entries(_raw).map(([zona, d]) => ({zona, ...d}))
      : null
  const rec = zonas?.recomendacion || zonas?.data?.recomendacion

  if (!lista?.length) return (
    <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>Sin datos de zonas ciclismo</div>
  )

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {rec && (
        <div style={{
          padding:'10px 14px', borderRadius:8, marginBottom:12,
          background:`${rec.color}12`, border:`1px solid ${rec.color}30`,
          display:'flex', alignItems:'center', gap:8
        }}>
          <div style={{width:8,height:8,borderRadius:'50%',background:rec.color,flexShrink:0}}/>
          <span style={{fontSize:12,color:NOAH_C.ink3}}>{rec.msg}</span>
        </div>
      )}
      {lista.map((z, i) => {
        const zColor = z.color || NOAH_C.bike
        return (
          <div key={i} style={{
            padding:'13px 16px', borderBottom:`1px solid ${NOAH_C.border}`,
            display:'flex', justifyContent:'space-between', alignItems:'center',
            borderLeft:`4px solid ${zColor}`,
            background:`${zColor}12`,
          }}>
            <div>
              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600}}>{z.nombre}</span>
              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>{z.pct_ftp}</div>
            </div>
            <div style={{textAlign:'right'}}>
              <div style={{fontSize:14, fontWeight:700, color:zColor}}>{z.w_rango||'--'}</div>
              <div style={{fontSize:11, color:NOAH_C.ink3}}>HR {z.hr_min||'--'}–{z.hr_max||'--'} · {z.wkg_min||'--'} W/kg</div>
            </div>
          </div>
        )
      })}
    </div>
  )
}"""

if viejo_bike in contenido:
    contenido = contenido.replace(viejo_bike, nuevo_bike, 1); cambios += 1
    print("OK 2/3: ZonasCyclingTable reescrito igual que coach")
else:
    print("AVISO 2/3: no se encontro ZonasCyclingTable exacta")

# ── 3. ZonasSwimTable ────────────────────────────────────────────────────────
viejo_swim = """function ZonasSwimTable({ zonas }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw) ? _raw : (_raw && typeof _raw === "object") ? Object.entries(_raw).map(([zona,d])=>({zona,...d})) : null
  if (!lista?.length) return <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>Sin datos de zonas natación</div>
  return (
    <table style={{width:'100%',borderCollapse:'collapse',fontSize:13}}>
      <thead>
        <tr style={{borderBottom:`2px solid ${NOAH_C.border}`}}>
          {['Zona','Descripción','Pace (min/100m)','HR'].map(h=>(
            <th key={h} style={{padding:'6px 10px',textAlign:'left',fontSize:11,
              fontWeight:600,color:NOAH_C.ink4,textTransform:'uppercase'}}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {lista.map((z,i)=>(
          <tr key={i} style={{borderBottom:`1px solid ${NOAH_C.border}`,
            background:i%2===0?'transparent':'rgba(0,0,0,0.02)'}}>
            <td style={{padding:'8px 10px',fontWeight:700,color:NOAH_C.swim}}>{z.zona}</td>
            <td style={{padding:'8px 10px',color:NOAH_C.ink}}>{z.nombre}</td>
            <td style={{padding:'8px 10px',color:NOAH_C.ink3,fontVariantNumeric:'tabular-nums'}}>
              {z.pace_100m_min || z.pace_min || '--'} – {z.pace_100m_max || z.pace_max || '--'}
            </td>
            <td style={{padding:'8px 10px',color:NOAH_C.ink3}}>{z.hr_min||'--'}–{z.hr_max||'--'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}"""

nuevo_swim = """function ZonasSwimTable({ zonas }) {
  const _raw = zonas?.zonas || zonas?.data?.zonas || zonas
  const lista = Array.isArray(_raw) ? _raw : (_raw && typeof _raw === "object") ? Object.entries(_raw).map(([zona,d])=>({zona,...d})) : null
  if (!lista?.length) return <div style={{color:NOAH_C.ink3,fontSize:12,padding:'12px 0'}}>Sin datos de zonas natación</div>

  return (
    <div style={{display:'flex',flexDirection:'column',gap:0}}>
      {lista.map((z,i)=>(
        <div key={i} style={{
          padding:'13px 16px', borderBottom:`1px solid ${NOAH_C.border}`,
          display:'flex', justifyContent:'space-between', alignItems:'center',
          borderLeft:`4px solid ${NOAH_C.swim}`,
          background:`${NOAH_C.swim}12`,
        }}>
          <div>
            <span style={{fontWeight:800, color:NOAH_C.swim, marginRight:8, fontSize:14}}>{z.zona}</span>
            <span style={{fontWeight:600}}>{z.nombre}</span>
            <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>{z.descripcion}</div>
          </div>
          <div style={{textAlign:'right'}}>
            <div style={{fontSize:14, fontWeight:700, color:NOAH_C.swim}}>
              {z.pace_rango || ((z.pace_100m_min||z.pace_min) ? `${z.pace_100m_min||z.pace_min} – ${z.pace_100m_max||z.pace_max}` : '--')}
            </div>
            <div style={{fontSize:11, color:NOAH_C.ink3}}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
          </div>
        </div>
      ))}
    </div>
  )
}"""

if viejo_swim in contenido:
    contenido = contenido.replace(viejo_swim, nuevo_swim, 1); cambios += 1
    print("OK 3/3: ZonasSwimTable reescrito igual que coach")
else:
    print("AVISO 3/3: no se encontro ZonasSwimTable exacta")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 3)")
