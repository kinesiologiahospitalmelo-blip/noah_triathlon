path = r"C:\Users\Win10\Desktop\noah_cloud\noa-coach\src\App.js"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

# Reemplazar solo dentro del componente nuevo — buscar el bloque
reemplazos = [
    ("React.useState",    "useState"),
    ("React.useEffect",   "useEffect"),
    ("React.useCallback", "useCallback"),
]

cambios = 0
for viejo, nuevo in reemplazos:
    n = contenido.count(viejo)
    if n > 0:
        contenido = contenido.replace(viejo, nuevo)
        cambios += n
        print(f"OK: {n} ocurrencias de {viejo} → {nuevo}")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal reemplazos: {cambios}")
