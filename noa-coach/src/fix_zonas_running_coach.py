path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

# Buscar y reemplazar el bloque exacto de running
# Puede venir con el pace_ref original O con la version ya parcheada por fmtPaceStr
viejo_a = """                  <div key={zona} style={{ padding:'11px 14px', borderBottom:`1px solid ${C.border}`,
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
                  </div>"""

viejo_b = """                  <div key={zona} style={{ padding:'11px 14px', borderBottom:`1px solid ${C.border}`,
                    display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                    <div>
                      <span style={{ fontWeight:700, color:C.run, marginRight:8 }}>{zona}</span>
                      <span style={{ fontWeight:500 }}>{z.nombre}</span>
                      <div style={{ fontSize:11, color:C.text2, marginTop:2 }}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>
                    </div>
                    <div style={{ textAlign:'right' }}>
                      <div style={{ fontSize:13, fontWeight:700, color:C.run }}>{z.pace_ref ? fmtPaceStr(z.pace_ref) : '--'}</div>
                      <div style={{ fontSize:11, color:C.text2 }}>HR {z.hr_min}–{z.hr_max} bpm</div>
                    </div>
                  </div>"""

nuevo = """                  <div key={zona} style={{
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
                  </div>"""

if viejo_a in contenido:
    contenido = contenido.replace(viejo_a, nuevo, 1)
    print("OK: bloque running corregido (version original)")
elif viejo_b in contenido:
    contenido = contenido.replace(viejo_b, nuevo, 1)
    print("OK: bloque running corregido (version con fmtPaceStr)")
else:
    print("ERROR: no se encontro el bloque de running. Revisar manualmente.")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)
