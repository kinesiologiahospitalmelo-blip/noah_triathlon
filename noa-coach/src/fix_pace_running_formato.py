path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = "<div style={{ fontSize:13, fontWeight:700, color:C.run }}>{z.pace_ref && `${z.pace_ref} /km`}</div>"
nuevo = "<div style={{ fontSize:13, fontWeight:700, color:C.run }}>{z.pace_ref ? fmtPaceStr(z.pace_ref) : '--'}</div>"

if viejo not in contenido:
    print("ERROR: no se encontro la linea exacta del pace de running. No se modifico el archivo.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: pace de running ahora usa fmtPaceStr (formato min:seg/km en vez del numero crudo)")
