path = r"C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

cambios = 0

# ── 1. Eliminar el 'return resultado' sobrante que rompia descargar_umbrales ──
viejo_1 = """        print('    Sin umbrales nuevos de Garmin (normal si el reloj no detecto cambios)')

    return resultado


# ── Helpers ───────────────────────────────────────────────────────────────────"""

nuevo_1 = """        print('    Sin umbrales nuevos de Garmin (normal si el reloj no detecto cambios)')


# ── Helpers ───────────────────────────────────────────────────────────────────"""

if viejo_1 in contenido:
    contenido = contenido.replace(viejo_1, nuevo_1, 1)
    cambios += 1
    print("OK 1/2: 'return resultado' sobrante eliminado de descargar_umbrales")
else:
    print("AVISO 1/2: no se encontro el bloque del return sobrante")

# ── 2. Agregar print de diagnostico para ver el valor crudo de 'speed' ──────
viejo_2 = """        if hr:
            lthr_garmin = float(hr)
        if speed and speed > 0:
            # m/s -> min/km
            pace_garmin = round(1000 / (speed * 60), 3)"""

nuevo_2 = """        if hr:
            lthr_garmin = float(hr)
        if speed and speed > 0:
            print(f"    [DEBUG] speed crudo de Garmin: {speed}")
            # m/s -> min/km
            pace_garmin = round(1000 / (speed * 60), 3)"""

if viejo_2 in contenido:
    contenido = contenido.replace(viejo_2, nuevo_2, 1)
    cambios += 1
    print("OK 2/2: print de diagnostico de speed agregado")
else:
    print("AVISO 2/2: no se encontro el bloque de conversion de pace")

with open(path, "w", encoding="utf-8") as f:
    f.write(contenido)

print(f"\nTotal cambios: {cambios} (esperado: 2)")
