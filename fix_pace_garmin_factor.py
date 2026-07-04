path = r"C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """        if hr:
            lthr_garmin = float(hr)
        if speed and speed > 0:
            print(f"    [DEBUG] speed crudo de Garmin: {speed}")
            # m/s -> min/km
            pace_garmin = round(1000 / (speed * 60), 3)"""

nuevo = """        if hr:
            lthr_garmin = float(hr)
        if speed and speed > 0:
            # El campo 'speed' que devuelve este endpoint de Garmin NO esta
            # en m/s puros -- viene escalado x10 (confirmado empiricamente:
            # speed=0.336 correspondia a un pace real de 4:58/km, que solo
            # cuadra multiplicando por 10 antes de convertir). Sin este
            # factor, el calculo daba paces absurdos (~49 min/km).
            speed_ms = speed * 10
            pace_garmin = round(1000 / (speed_ms * 60), 3)"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto. No se modifico el archivo.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: factor de correccion x10 aplicado al calculo de pace de Garmin")
