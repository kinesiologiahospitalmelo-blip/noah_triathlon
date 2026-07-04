from pathlib import Path

path = r"C:\Users\Win10\Desktop\noah_cloud\noa_db.py"
path_codigo = Path(__file__).parent / "codigo_umbral_historial.txt"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

marcador = "    # ── SESIONES ──────────────────────────────────────────────────────────────"

with open(path_codigo, "r", encoding="utf-8") as f:
    codigo_nuevo = f.read()

if marcador not in contenido:
    print("ERROR: no se encontro el marcador de SESIONES. No se modifico el archivo.")
elif "def calcular_umbral_desde_historial" in contenido:
    print("AVISO: las funciones ya existen, no se duplicaron.")
else:
    contenido = contenido.replace(marcador, codigo_nuevo + marcador, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: calcular_umbral_desde_historial y actualizar_umbral_final agregadas a noa_db.py")
