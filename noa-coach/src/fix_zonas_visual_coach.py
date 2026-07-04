path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Running: rango de pace + color por zona ────────────────────────────────
viejo_run = """          {/* Running */}
          {subTabZonas==='running'&&zonas&&(
            <div>
              <SectionTitle>Zonas Running — LTHR {atleta?.lthr_run} bpm</SectionTitle>
              <Card>
                {Object.entries(zonas.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{ padding:'11px 14px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <div>
                      <span style={{ fontWeight:700, color:C.run, marginRight:8 }}>{zona}</span>
                      <span style={{ fontWeight:500 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:13, fontWeight:700, color:C.run }}>{z.pace_ref && `${z.pace_ref} /km`}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min}–{z.hr_max} bpm</div>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          )}"""

nuevo_run = """          {/* Running */}
          {subTabZonas==='running'&&zonas&&(
            <div>
              <SectionTitle>Zonas Running — LTHR {atleta?.lthr_run} bpm</SectionTitle>
              <Card>
                {Object.entries(zonas.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{
                    padding:'13px 16px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderLeft: `4px solid ${z.color||C.run}`,
                    background: `${z.color||C.run}12`,
                  }}>
                    <div>
                      <span style={{ fontWeight:800, color:z.color||C.run, marginRight:8, fontSize:14 }}>{zona}</span>
                      <span style={{ fontWeight:600 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:14, fontWeight:700, color:z.color||C.run }}>
                        {z.pace_rango || (z.pace_min && z.pace_max ? `${z.pace_min} – ${z.pace_max} /km` : z.pace_ref ? fmtPaceStr(z.pace_ref)+' /km' : '--')}
                      </div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
                    </div>
                  </div>
                ))}
              </Card>
            </div>
          )}"""

if viejo_run in contenido:
    contenido = contenido.replace(viejo_run, nuevo_run, 1); cambios += 1
    print("OK 1/3: running con rangos y colores")
else:
    print("AVISO 1/3: no se encontro el bloque de running")

# ── 2. Ciclismo: color por zona ───────────────────────────────────────────────
viejo_bike = """                {Object.entries(zonasBike.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{ padding:'11px 14px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <div>
                      <span style={{ fontWeight:700, color:C.bike, marginRight:8 }}>{zona}</span>
                      <span style={{ fontWeight:500 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>{z.pct_ftp}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:13, fontWeight:700, color:C.bike }}>{z.w_rango}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min}–{z.hr_max} · {z.wkg_min} W/kg</div>
                    </div>
                  </div>
                ))}"""

nuevo_bike = """                {Object.entries(zonasBike.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{
                    padding:'13px 16px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderLeft: `4px solid ${z.color||C.bike}`,
                    background: `${z.color||C.bike}12`,
                  }}>
                    <div>
                      <span style={{ fontWeight:800, color:z.color||C.bike, marginRight:8, fontSize:14 }}>{zona}</span>
                      <span style={{ fontWeight:600 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>{z.pct_ftp}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:14, fontWeight:700, color:z.color||C.bike }}>{z.w_rango}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max||'--'} · {z.wkg_min||'--'} W/kg</div>
                    </div>
                  </div>
                ))}"""

if viejo_bike in contenido:
    contenido = contenido.replace(viejo_bike, nuevo_bike, 1); cambios += 1
    print("OK 2/3: ciclismo con colores")
else:
    print("AVISO 2/3: no se encontro el bloque de ciclismo")

# ── 3. Natacion: color por zona ───────────────────────────────────────────────
viejo_swim = """                {Object.entries(zonasSwim.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{ padding:'11px 14px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <div>
                      <span style={{ fontWeight:700, color:C.swim, marginRight:8 }}>{zona}</span>
                      <span style={{ fontWeight:500 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>{z.descripcion}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:13, fontWeight:700, color:C.swim }}>{z.pace_rango}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max} bpm</div>
                    </div>
                  </div>
                ))}"""

nuevo_swim = """                {Object.entries(zonasSwim.zonas||{}).map(([zona,z])=>(
                  <div key={zona} style={{
                    padding:'13px 16px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center',
                    borderLeft: `4px solid ${C.swim}`,
                    background: `${C.swim}12`,
                  }}>
                    <div>
                      <span style={{ fontWeight:800, color:C.swim, marginRight:8, fontSize:14 }}>{zona}</span>
                      <span style={{ fontWeight:600 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:3 }}>{z.descripcion}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:14, fontWeight:700, color:C.swim }}>{z.pace_rango}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min||'--'}–{z.hr_max||'--'} bpm</div>
                    </div>
                  </div>
                ))}"""

if viejo_swim in contenido:
    contenido = contenido.replace(viejo_swim, nuevo_swim, 1); cambios += 1
    print("OK 3/3: natacion con colores")
else:
    print("AVISO 3/3: no se encontro el bloque de natacion")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 3)")
