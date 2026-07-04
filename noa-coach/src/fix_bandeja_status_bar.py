path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """      {/* STATUS BAR — bloques especiales arriba, métricas en grid fijo de 2 columnas (ordenado en mobile) */}
      <div style={{ background:'linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015))', backdropFilter:'blur(20px) saturate(150%)', WebkitBackdropFilter:'blur(20px) saturate(150%)', borderBottom:'1px solid rgba(255,255,255,0.07)', padding:'14px 16px' }}>"""

nuevo = """      {/* STATUS BAR — sin bandeja de fondo propia: los botones (HANNA LIFE,
          Objetivo, CTL/ATL/TSB) flotan directo sobre el fondo general de
          la pantalla. Cada boton conserva su propio estilo/sombra. */}
      <div style={{ padding:'14px 16px' }}>"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto del STATUS BAR. No se modifico el archivo.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: bandeja de fondo del STATUS BAR removida. Los botones individuales quedan intactos.")
