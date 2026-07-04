path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# Running: nombre de zona en color de zona
viejo = "              <span style={{fontWeight:600}}>{z.nombre}</span>\n              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>"
nuevo = "              <span style={{fontWeight:600, color:NOAH_C.ink}}>{z.nombre}</span>\n              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>"

# En modo oscuro NOAH_C.ink es claro, en claro es oscuro -- usamos NOAH_C.ink que es el texto principal correcto
# El problema real es que el fondo de zona es semitransparente oscuro pero NOAH_C.ink puede ser #111
# La solucion: forzar color blanco/claro para el nombre cuando el fondo es oscuro

viejo_run_nombre = """              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600}}>{z.nombre}</span>
              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>"""

nuevo_run_nombre = """              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>
              <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>VO2: {z.vo2_pct} · Lactato: {z.lactato}</div>"""

if viejo_run_nombre in contenido:
    contenido = contenido.replace(viejo_run_nombre, nuevo_run_nombre, 1); cambios += 1
    print("OK 1/3: color nombre running corregido")
else:
    print("AVISO 1/3: no encontrado en running")

# Cycling
viejo_bike_nombre = """              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600}}>{z.nombre}</span>
              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>{z.pct_ftp}</div>"""

nuevo_bike_nombre = """              <span style={{fontWeight:800, color:zColor, marginRight:8, fontSize:14}}>{z.zona||`Z${i+1}`}</span>
              <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>
              <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>{z.pct_ftp}</div>"""

if viejo_bike_nombre in contenido:
    contenido = contenido.replace(viejo_bike_nombre, nuevo_bike_nombre, 1); cambios += 1
    print("OK 2/3: color nombre cycling corregido")
else:
    print("AVISO 2/3: no encontrado en cycling")

# Swimming
viejo_swim_nombre = """              <span style={{fontWeight:800, color:NOAH_C.swim, marginRight:8, fontSize:14}}>{z.zona}</span>
              <span style={{fontWeight:600}}>{z.nombre}</span>
              <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>{z.descripcion}</div>"""

nuevo_swim_nombre = """              <span style={{fontWeight:800, color:NOAH_C.swim, marginRight:8, fontSize:14}}>{z.zona}</span>
              <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>
              <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>{z.descripcion}</div>"""

if viejo_swim_nombre in contenido:
    contenido = contenido.replace(viejo_swim_nombre, nuevo_swim_nombre, 1); cambios += 1
    print("OK 3/3: color nombre swimming corregido")
else:
    print("AVISO 3/3: no encontrado en swimming")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 3)")
