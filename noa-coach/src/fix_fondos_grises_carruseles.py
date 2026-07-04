path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. BioCard (carrusel de biomarcadores: HANNA LIFE, Carga, Riesgo viral...) ──
viejo_1 = """                background: isCenter
                  ? `linear-gradient(135deg, ${b.color}22, ${b.color}08)`
                  : 'rgba(255,255,255,0.03)',"""
nuevo_1 = """                background: isCenter
                  ? `linear-gradient(135deg, ${b.color}22, ${b.color}08)`
                  : 'transparent',"""
if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1); cambios += 1
    print("OK 1/4: BioCard sin fondo gris lateral")
else:
    print("AVISO 1/4: no encontrado BioCard")

# ── 2. OpCard (carrusel de opciones de receta/zona) ─────────────────────────
viejo_2 = "background:isCenter?`${o.color}1E`:'rgba(255,255,255,0.03)',"
nuevo_2 = "background:isCenter?`${o.color}1E`:'transparent',"
if viejo_2 in contenido:
    contenido = contenido.replace(viejo_2, nuevo_2, 1); cambios += 1
    print("OK 2/4: OpCard sin fondo gris lateral")
else:
    print("AVISO 2/4: no encontrado OpCard")

# ── 3. MetCard (carrusel CTL/ATL/TSB/HRV/Body Battery) ──────────────────────
viejo_3 = """                  background: isCenter
                    ? 'linear-gradient(150deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02))'
                    : 'rgba(255,255,255,0.03)',"""
nuevo_3 = """                  background: isCenter
                    ? `linear-gradient(135deg, ${m.color}22, ${m.color}08)`
                    : 'transparent',"""
if viejo_3 in contenido:
    contenido = contenido.replace(viejo_3, nuevo_3, 1); cambios += 1
    print("OK 3/4: MetCard sin fondo gris (central ahora usa el color propio de la metrica, igual que los otros carruseles)")
else:
    print("AVISO 3/4: no encontrado MetCard")

# ── 4. TabCard (pestañas Mi Sesion / Semana / Metricas / Planificacion...) ──
viejo_4 = """                background: isCenter
                  ? `linear-gradient(135deg, ${NOAH_C.accent}2A, ${NOAH_C.accent}0D)`
                  : 'rgba(255,255,255,0.03)',"""
nuevo_4 = """                background: isCenter
                  ? `linear-gradient(135deg, ${NOAH_C.accent}2A, ${NOAH_C.accent}0D)`
                  : 'transparent',"""
if viejo_4 in contenido:
    contenido = contenido.replace(viejo_4, nuevo_4, 1); cambios += 1
    print("OK 4/4: TabCard sin fondo gris lateral")
else:
    print("AVISO 4/4: no encontrado TabCard")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\\nTotal cambios aplicados: {cambios} (esperado: 4)")
