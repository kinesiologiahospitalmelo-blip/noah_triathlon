import re

path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Imagen hero en el header (regex para tolerar CRLF/LF) ─────────────────
patron_img = re.compile(
    r"backgroundImage: deporte === 'cycling'.*?filter: 'saturate\(1\.4\)',",
    re.DOTALL
)
nuevo_img = """backgroundImage: 'url(/assets/hero_dashboard.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 20%',
          opacity: 0.55,
          filter: 'saturate(1.1) brightness(0.88)',"""

if patron_img.search(contenido):
    contenido = patron_img.sub(nuevo_img, contenido, count=1)
    cambios += 1
    print("OK 1/4: imagen hero aplicada al header")
else:
    print("AVISO 1/4: no se encontro el patron de imagen")

# ── 2. Overlay del header: mas transparente para ver la imagen ────────────────
viejo_overlay = "background: 'linear-gradient(90deg, rgba(10,15,30,0.82) 0%, rgba(10,15,30,0.50) 60%, rgba(10,15,30,0.75) 100%)',"
nuevo_overlay = "background: 'linear-gradient(90deg, rgba(5,5,15,0.88) 0%, rgba(5,5,15,0.45) 55%, rgba(5,5,15,0.78) 100%)',"
if viejo_overlay in contenido:
    contenido = contenido.replace(viejo_overlay, nuevo_overlay, 1)
    cambios += 1
    print("OK 2/4: overlay del header ajustado")
else:
    print("AVISO 2/4: no se encontro el overlay")

# ── 3. Fondo claro residual (#F9FAFB) → transparente estilo oscuro ────────────
# Este es el fondo claro en la referencia de zona que rompe el esquema oscuro
viejo_claro = "background:'#F9FAFB', borderRadius:8, border:`1px solid ${NOAH_C.border}`"
nuevo_claro = "background:'rgba(255,255,255,0.04)', borderRadius:8, border:`1px solid ${NOAH_C.border}`"
if viejo_claro in contenido:
    contenido = contenido.replace(viejo_claro, nuevo_claro)
    cambios += 1
    print("OK 3/4: fondo claro #F9FAFB eliminado")
else:
    print("AVISO 3/4: no se encontro el fondo claro")

# ── 4. Color de texto de la referencia de zona (era oscuro sobre fondo claro) ─
viejo_txt_ref = "fontSize:11, color:NOAH_C.ink3, marginBottom:10, padding:'8px 12px',"
nuevo_txt_ref = "fontSize:11, color:'rgba(255,255,255,0.55)', marginBottom:10, padding:'8px 12px',"
if viejo_txt_ref in contenido:
    contenido = contenido.replace(viejo_txt_ref, nuevo_txt_ref)
    cambios += 1
    print("OK 4/4: color texto referencia zona corregido")
else:
    print("AVISO 4/4: no se encontro el color de texto de referencia")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 4)")
