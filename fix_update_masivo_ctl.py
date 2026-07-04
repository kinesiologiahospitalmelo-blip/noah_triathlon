path = r"C:\Users\Win10\Desktop\noah_cloud\noa_db.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

viejo = """        conn2 = self._conn()
        for _, row in df.iterrows():
            vals = ctl_map.get(str(row['fecha'])[:10])
            if not vals:
                continue
            ctl_v, atl_v, tsb_v = float(vals[0]), float(vals[1]), float(vals[2])
            conn2.execute('''
                UPDATE sesiones SET ctl=%s, atl=%s, tsb=%s, form_status=%s
                WHERE id=%s
            ''', (ctl_v, atl_v, tsb_v, form_status(tsb_v), int(row['id'])))
        conn2.commit()
        conn2.close()"""

nuevo = """        # UPDATE masivo en UNA sola query (en vez de un UPDATE por cada
        # sesion, que con 1000+ sesiones provocaba timeout en Supabase).
        # Se construye una tabla temporal de valores (id, ctl, atl, tsb,
        # form_status) con VALUES y se hace un solo UPDATE...FROM contra
        # esa tabla. Esto es decenas de veces mas rapido porque viaja una
        # sola vez por la red en lugar de 1 round-trip por sesion.
        filas_update = []
        for _, row in df.iterrows():
            vals = ctl_map.get(str(row['fecha'])[:10])
            if not vals:
                continue
            ctl_v, atl_v, tsb_v = float(vals[0]), float(vals[1]), float(vals[2])
            filas_update.append((int(row['id']), ctl_v, atl_v, tsb_v, form_status(tsb_v)))

        if not filas_update:
            return

        conn2 = self._conn()
        # Insertar en bloques (por si hay miles de sesiones, evitar un
        # statement gigante de una sola vez) y cada bloque en UNA query.
        BLOQUE = 500
        for i in range(0, len(filas_update), BLOQUE):
            bloque = filas_update[i:i+BLOQUE]
            placeholders = ','.join(['(%s,%s,%s,%s,%s)'] * len(bloque))
            params = [v for fila in bloque for v in fila]
            conn2.execute(f'''
                UPDATE sesiones AS s
                SET ctl = v.ctl, atl = v.atl, tsb = v.tsb, form_status = v.form_status
                FROM (VALUES {placeholders}) AS v(id, ctl, atl, tsb, form_status)
                WHERE s.id = v.id
            ''', params)
        conn2.commit()
        conn2.close()"""

if viejo not in contenido:
    print("ERROR: no se encontro el bloque exacto del loop de UPDATE. No se modifico el archivo.")
else:
    contenido = contenido.replace(viejo, nuevo, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: loop de 1000+ UPDATEs reemplazado por UPDATE masivo en bloques de 500.")
