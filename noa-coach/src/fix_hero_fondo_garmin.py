path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Imagen de fondo del header: Unsplash → hero_dashboard.png ─────────────
viejo_img = """        {/* Imagen de fondo según deporte */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: deporte === 'cycling'
            ? 'url(https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=1400&q=80)'
            : deporte === 'swimming'
            ? 'url(https://images.unsplash.com/photo-1560090995-01632a28895b?w=1400&q=80)'
            : deporte === 'triatlon'
            ? 'url(https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=1400&q=80)'
            : 'url(https://images.unsplash.com/photo-1502904550040-7534597429ae?w=1400&q=80)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 30%',
          opacity: 0.45,
          filter: 'saturate(1.4)',
        }}/>
        {/* Overlay gradiente */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(90deg, rgba(10,15,30,0.97) 0%, rgba(10,15,30,0.75) 60%, rgba(10,15,30,0.92) 100%)',
        }}/>"""

nuevo_img = """        {/* Imagen de fondo NOAH hero — misma para todos los deportes */}
        <div style={{
          position: 'absolute', inset: 0,
          backgroundImage: 'url(/assets/hero_dashboard.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 20%',
          opacity: 0.55,
          filter: 'saturate(1.2) brightness(0.9)',
        }}/>
        {/* Overlay gradiente — mas transparente para dejar ver la imagen */}
        <div style={{
          position: 'absolute', inset: 0,
          background: 'linear-gradient(90deg, rgba(5,8,20,0.92) 0%, rgba(5,8,20,0.60) 50%, rgba(5,8,20,0.85) 100%)',
        }}/>"""

if viejo_img in contenido:
    contenido = contenido.replace(viejo_img, nuevo_img, 1)
    cambios += 1
    print("OK 1/2: imagen hero aplicada al header")
else:
    print("AVISO 1/2: no se encontro el bloque exacto del header")

# ── 2. Fondo general de la pantalla: azul → negro puro estilo Garmin ──────────
viejo_bg = "        linear-gradient(145deg, #0F1B35 0%, #132040 55%, #0A1628 100%)"
nuevo_bg  = "        linear-gradient(145deg, #0A0A0F 0%, #0D0D14 55%, #080810 100%)"

if viejo_bg in contenido:
    contenido = contenido.replace(viejo_bg, nuevo_bg, 1)
    cambios += 1
    print("OK 2/2: fondo negro puro estilo Garmin aplicado")
else:
    print("AVISO 2/2: no se encontro el gradiente de fondo general")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 2)")
