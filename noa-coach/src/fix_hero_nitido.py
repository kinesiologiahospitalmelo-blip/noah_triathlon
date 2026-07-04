path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# Altura: 210 → 50vh
viejo_h = "      <div style={{ position:'relative', overflow:'hidden', minHeight:210 }}>"
nuevo_h  = "      <div style={{ position:'relative', overflow:'hidden', minHeight:'50vh' }}>"
if viejo_h in contenido:
    contenido = contenido.replace(viejo_h, nuevo_h, 1); cambios += 1
    print("OK 1/3: altura 50vh")
else:
    print("AVISO 1/3: no encontrado minHeight:210")

# Imagen: sin filter oscuro
viejo_img = """          filter:'brightness(0.72) saturate(1.1)',"""
nuevo_img  = """          filter:'saturate(1.05)',"""
if viejo_img in contenido:
    contenido = contenido.replace(viejo_img, nuevo_img, 1); cambios += 1
    print("OK 2/3: imagen sin oscurecimiento")
else:
    print("AVISO 2/3: no encontrado filter imagen")

# Overlay: solo esfumado suave en el borde inferior
viejo_ov = """          background:'linear-gradient(to top, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.55) 50%, rgba(0,0,0,0.18) 100%)',"""
nuevo_ov  = """          background:'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.30) 30%, transparent 60%)',"""
if viejo_ov in contenido:
    contenido = contenido.replace(viejo_ov, nuevo_ov, 1); cambios += 1
    print("OK 3/3: overlay solo esfumado inferior")
else:
    print("AVISO 3/3: no encontrado overlay")

# También el minHeight interno del contenido
contenido = contenido.replace("minHeight:210 }}", "minHeight:'50vh' }}", 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal: {cambios} (esperado: 3)")
