path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# Texto exacto del archivo real (extraido del findstr)
viejo = """          backgroundImage: deporte === 'cycling'
            ? 'url(https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=1400&q=80)'
            : deporte === 'swimming'
            ? 'url(https://images.unsplash.com/photo-1560090995-01632a28895b?w=1400&q=80)'
            : deporte === 'triatlon'
            ? 'url(https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=1400&q=80)'
            : 'url(https://images.unsplash.com/photo-1502904550040-7534597429ae?w=1400&q=80)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 30%',
          opacity: 0.45,
          filter: 'saturate(1.4)',"""

nuevo = """          backgroundImage: 'url(/assets/hero_dashboard.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 20%',
          opacity: 0.60,
          filter: 'saturate(1.1) brightness(0.85)',"""

if viejo in contenido:
    contenido = contenido.replace(viejo, nuevo, 1)
    cambios += 1
    print("OK: imagen hero_dashboard aplicada al header")
else:
    print("AVISO: no se encontro el bloque exacto, buscando por partes...")
    if "unsplash.com/photo-1541625602330" in contenido:
        print("  -> Las URLs de Unsplash estan en el archivo")
    if "backgroundImage: deporte" in contenido:
        print("  -> El inicio del bloque existe")
    if "saturate(1.4)" in contenido:
        print("  -> El final del bloque existe")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nCambios: {cambios}")
