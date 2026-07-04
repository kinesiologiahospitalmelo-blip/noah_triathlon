path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """          backgroundImage: deporte === 'cycling'
            ? 'url(https://images.unsplash.com/photo-1541625602330-2277a4c46182?w=1400&q=80)'
            : deporte === 'swimming'
            ? 'url(https://images.unsplash.com/photo-1560090995-01632a28895b?w=1400&q=80)'
            : deporte === 'triatlon'
            ? 'url(https://images.unsplash.com/photo-1452626038306-9aae5e071dd3?w=1400&q=80)'
            : 'url(https://images.unsplash.com/photo-1502904550040-7534597429ae?w=1400&q=80)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 30%',
          opacity: 0.65,
          filter: 'saturate(1.3)',"""

nuevo = """          backgroundImage: 'url(/assets/hero_dashboard.png)',
          backgroundSize: 'cover',
          backgroundPosition: 'center 20%',
          opacity: 0.55,
          filter: 'saturate(1.1) brightness(0.88)',"""

if viejo in contenido:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: imagen hero aplicada")
else:
    print("ERROR: no encontrado")
