path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = "NOAH_C.swim, marginRight:8, fontSize:14}}>{z.zona}</span>\n            <span style={{fontWeight:600}}>{z.nombre}</span>\n            <div style={{fontSize:11, color:NOAH_C.ink3, marginTop:3}}>{z.descrip"
nuevo = "NOAH_C.swim, marginRight:8, fontSize:14}}>{z.zona}</span>\n            <span style={{fontWeight:600, color:'rgba(255,255,255,0.9)'}}>{z.nombre}</span>\n            <div style={{fontSize:11, color:'rgba(255,255,255,0.5)', marginTop:3}}>{z.descrip"

if viejo in contenido:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: color swimming corregido")
else:
    print("ERROR: no se encontro")
