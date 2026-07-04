path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Imagen del header mas visible (opacity 0.45 → 0.65) ──────────────────
viejo_1 = "          opacity: 0.45,\r\n          filter: 'saturate(1.4)',"
nuevo_1 = "          opacity: 0.65,\r\n          filter: 'saturate(1.3)',"
if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1); cambios += 1
    print("OK 1/3: imagen header mas visible")
else:
    viejo_1b = "          opacity: 0.45,\n          filter: 'saturate(1.4)',"
    nuevo_1b = "          opacity: 0.65,\n          filter: 'saturate(1.3)',"
    if viejo_1b in contenido:
        contenido = contenido.replace(viejo_1b, nuevo_1b, 1); cambios += 1
        print("OK 1/3: imagen header mas visible (LF)")
    else:
        print("AVISO 1/3: no encontrado opacity header")

# ── 2. Overlay menos opaco (deja ver mas la imagen) ─────────────────────────
viejo_2 = "background: 'linear-gradient(90deg, rgba(10,15,30,0.97) 0%, rgba(10,15,30,0.75) 60%, rgba(10,15,30,0.92) 100%)',"
nuevo_2 = "background: 'linear-gradient(90deg, rgba(10,15,30,0.82) 0%, rgba(10,15,30,0.50) 60%, rgba(10,15,30,0.75) 100%)',"
if viejo_2 in contenido:
    contenido = contenido.replace(viejo_2, nuevo_2, 1); cambios += 1
    print("OK 2/3: overlay mas transparente")
else:
    print("AVISO 2/3: no encontrado overlay header")

# ── 3. Fondo principal: azul profesional mas rico ────────────────────────────
viejo_3 = "        linear-gradient(145deg, #0A0F1E 0%, #0D1528 55%, #081520 100%)"
nuevo_3 = "        linear-gradient(145deg, #0F1B35 0%, #132040 55%, #0A1628 100%)"
if viejo_3 in contenido:
    contenido = contenido.replace(viejo_3, nuevo_3, 1); cambios += 1
    print("OK 3/3: fondo principal azul profesional")
else:
    print("AVISO 3/3: no encontrado fondo principal")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 3)")
