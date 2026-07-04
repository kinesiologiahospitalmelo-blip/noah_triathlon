path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\AtletaDashboard.jsx"
with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()
contenido = contenido.replace("minHeight:'70vh'", "minHeight:'85vh'")
with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)
print("OK: hero al 85vh")
