path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """      {/* LEYENDA — global, fija arriba del carrusel. Texto simplificado, fondo oscuro coherente */}
      <div style={{ background:'rgba(255,255,255,0.03)', borderBottom:`1px solid ${NOAH_C.border}`, padding:'7px 16px', display:'flex', gap:14, alignItems:'center', flexWrap:'wrap' }}>
        {['done','miss','partial','planned'].map(k => {
          const e = ESTADO[k]
          const labelCorto = {done:'Hecha', miss:'No hecha', partial:'Editada', planned:'A futuro'}[k]
          return <span key={k} style={{ fontSize:10, color:e.color, fontWeight:600, display:'flex', alignItems:'center', gap:4 }}><span style={{ width:6,height:6,borderRadius:'50%',background:e.color,display:'inline-block' }} />{labelCorto}</span>
        })}
      </div>"""

nuevo = """      {/* LEYENDA — solo tiene sentido donde se muestran sesiones individuales
          (Mi Sesion / Semana). En Metricas, Planificacion, etc. no aplica. */}
      {(tab === 'hoy' || tab === 'semana') && (
        <div style={{ background:'rgba(255,255,255,0.03)', borderBottom:`1px solid ${NOAH_C.border}`, padding:'7px 16px', display:'flex', gap:14, alignItems:'center', flexWrap:'wrap' }}>
          {['done','miss','partial','planned'].map(k => {
            const e = ESTADO[k]
            const labelCorto = {done:'Hecha', miss:'No hecha', partial:'Editada', planned:'A futuro'}[k]
            return <span key={k} style={{ fontSize:10, color:e.color, fontWeight:600, display:'flex', alignItems:'center', gap:4 }}><span style={{ width:6,height:6,borderRadius:'50%',background:e.color,display:'inline-block' }} />{labelCorto}</span>
          })}
        </div>
      )}"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto de la leyenda. No se modifico el archivo.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: leyenda ahora condicionada a tab hoy/semana.")
