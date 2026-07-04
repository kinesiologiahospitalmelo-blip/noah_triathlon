path = r"C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

marcador = """            conn.commit()
            print('    [OK] Performance guardado')
        except Exception as e: print(f'    Error performance DB: {e}')
"""

nueva_funcion = marcador + '''

def descargar_umbrales(client, atleta_id: int, conn):
    """
    Trae el LTHR/pace de running y FTP de cycling directo de Garmin
    (cuando el reloj los tiene calculados) y los guarda en columnas
    separadas (*_garmin) -- nunca pisa directamente lthr_run/ftp_watts,
    porque esos son el valor final que decide actualizar_umbral_final()
    combinando esta fuente con el calculo propio de NOAH.

    Garmin no siempre tiene un valor reciente (el reloj solo lo detecta
    en ciertas sesiones y el usuario debe aceptarlo) -- por eso esto es
    "best effort": si no hay dato, simplemente no se actualiza nada.
    """
    print('  -> Umbrales (Garmin):')
    lthr_garmin  = None
    pace_garmin  = None
    ftp_garmin   = None

    try:
        lt = client.get_lactate_threshold(latest=True)
        shr = (lt or {}).get('speed_and_heart_rate') or {}
        hr    = shr.get('heartRate')
        speed = shr.get('speed')  # metros/segundo
        if hr:
            lthr_garmin = float(hr)
        if speed and speed > 0:
            # m/s -> min/km
            pace_garmin = round(1000 / (speed * 60), 3)
        if lthr_garmin or pace_garmin:
            print(f"    LTHR run: {lthr_garmin} bpm | Pace umbral: {pace_garmin} min/km")
    except Exception as e:
        print(f'    Lactate threshold: {e}')

    try:
        ftp_data = client.get_cycling_ftp()
        if isinstance(ftp_data, list) and ftp_data:
            ftp_data = ftp_data[0]
        if isinstance(ftp_data, dict):
            ftp_garmin = (
                ftp_data.get('functionalThresholdPower')
                or ftp_data.get('ftp')
                or ftp_data.get('value')
            )
            if ftp_garmin:
                ftp_garmin = float(ftp_garmin)
                print(f"    FTP bike: {ftp_garmin} W")
    except Exception as e:
        print(f'    Cycling FTP: {e}')

    if lthr_garmin or pace_garmin or ftp_garmin:
        try:
            from db_compat import asegurar_columnas as _aseg
            _aseg(conn, 'atletas', [
                ('lthr_run_garmin',        'REAL'),
                ('pace_umbral_run_garmin', 'REAL'),
                ('ftp_bike_garmin',        'REAL'),
                ('fecha_umbral_garmin',    'TEXT'),
            ])
            sets, params = [], []
            if lthr_garmin is not None:
                sets.append('lthr_run_garmin=%s'); params.append(lthr_garmin)
            if pace_garmin is not None:
                sets.append('pace_umbral_run_garmin=%s'); params.append(pace_garmin)
            if ftp_garmin is not None:
                sets.append('ftp_bike_garmin=%s'); params.append(ftp_garmin)
            sets.append('fecha_umbral_garmin=%s')
            params.append(datetime.now().date().isoformat())
            params.append(atleta_id)
            conn.execute(f"UPDATE atletas SET {', '.join(sets)} WHERE id=%s", params)
            conn.commit()
            print('    [OK] Umbrales Garmin guardados')
        except Exception as e:
            print(f'    Error guardando umbrales: {e}')
    else:
        print('    Sin umbrales nuevos de Garmin (normal si el reloj no detecto cambios)')
'''

if marcador not in contenido:
    print("ERROR: no se encontro el marcador exacto al final de descargar_performance. No se modifico el archivo.")
elif "def descargar_umbrales" in contenido:
    print("AVISO: descargar_umbrales ya existe, no se duplico.")
else:
    contenido = contenido.replace(marcador, nueva_funcion, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido)
    print("OK: funcion descargar_umbrales agregada a sincronizar_garmin.py")
