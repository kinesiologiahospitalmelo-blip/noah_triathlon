path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

viejo = """  cardBg:  'rgba(255,255,255,0.05)',
  cardBg2: 'rgba(255,255,255,0.03)',"""

nuevo = """  cardBg:  'transparent',
  cardBg2: 'transparent',"""

if viejo in contenido:
    contenido = contenido.replace(viejo, nuevo, 1)
    cambios += 1
    print("OK: cardBg y cardBg2 → transparent. Gris sacado de todo el dashboard.")
else:
    print("AVISO: no se encontro el bloque exacto.")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"Cambios: {cambios}")
