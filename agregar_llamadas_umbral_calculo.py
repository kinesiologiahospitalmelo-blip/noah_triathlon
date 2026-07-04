path = r"C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """        # Umbrales (LTHR run, pace umbral, FTP bike) -- una sola vez por
        # atleta, no por fecha (Garmin siempre da "el ultimo" valor).
        if args.modo in ('todo', 'perf'):
            try: descargar_umbrales(client, atleta_id, conn)
            except Exception as e: print(f'  Umbrales error: {e}')
"""

nuevo = """        # Umbrales (LTHR run, pace umbral, FTP bike) -- una sola vez por
        # atleta, no por fecha (Garmin siempre da "el ultimo" valor).
        if args.modo in ('todo', 'perf'):
            try: descargar_umbrales(client, atleta_id, conn)
            except Exception as e: print(f'  Umbrales error: {e}')

            # Calculo propio desde el historial (solo corre si pasaron
            # 21+ dias desde el ultimo calculo, ver dentro de la funcion)
            # y resolucion del valor final que usan las zonas.
            try:
                db.calcular_umbral_desde_historial(atleta_id)
                db.actualizar_umbral_final(atleta_id)
            except Exception as e: print(f'  Umbral historial error: {e}')
"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto. No se modifico el archivo.")
elif "calcular_umbral_desde_historial(atleta_id)" in contenido:
    print("AVISO: las llamadas ya existen, no se duplicaron.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: llamadas a calcular_umbral_desde_historial y actualizar_umbral_final agregadas")
