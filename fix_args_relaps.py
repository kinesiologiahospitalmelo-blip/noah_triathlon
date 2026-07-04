path = r"C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = "if gid and args.relaps:"
nuevo = "if gid and False:  # --relaps no se usa en este flujo (bug: 'args' no existia aca)"

if viejo not in contenido:
    print("ERROR: no se encontro la linea exacta. No se modifico el archivo.")
else:
    contenido_nuevo = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido_nuevo)
    print("OK: linea corregida.")
