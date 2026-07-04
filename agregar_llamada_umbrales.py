path = r"C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """        # Post-proceso
        for modulo, fn in ["""

nuevo = """        # Umbrales (LTHR run, pace umbral, FTP bike) -- una sola vez por
        # atleta, no por fecha (Garmin siempre da "el ultimo" valor).
        if args.modo in ('todo', 'perf'):
            try: descargar_umbrales(client, atleta_id, conn)
            except Exception as e: print(f'  Umbrales error: {e}')

        # Post-proceso
        for modulo, fn in ["""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto antes de Post-proceso. No se modifico el archivo.")
elif "descargar_umbrales(client, atleta_id, conn)" in contenido:
    print("AVISO: la llamada a descargar_umbrales ya existe, no se duplico.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: llamada a descargar_umbrales agregada al flujo principal (una vez por atleta)")
