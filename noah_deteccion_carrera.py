"""
noah_deteccion_carrera.py — Detecta carreras y tests, vincula y actualiza umbrales
====================================================================================
Se llama desde sincronizar_garmin.py despues de guardar sesiones.

Logica:
  1. Para cada sesion nueva, busca si hay carrera en la tabla carreras
     con fecha similar (+-1 dia) y distancia similar (+-20%)
  2. Si encuentra match, vincula la sesion con la carrera y graba resultado
  3. Actualiza umbrales desde la performance de esa carrera
  4. Tambien detecta si Garmin envio nuevo umbral (pace_umbral_run_garmin)
"""

from datetime import date, timedelta


def detectar_y_vincular(conn, atleta_id, sesion_id):
    """
    Verifica si una sesion recien sincronizada es una carrera o test.
    Si lo es, vincula, graba resultado y actualiza umbrales.
    """
    cur = conn.cursor()

    # Datos de la sesion
    cur.execute("""
        SELECT fecha, sport, duration_min, tss_total, distance_km,
               hr_avg, tipo_sesion, garmin_activity_id
        FROM sesiones WHERE id=%s AND atleta_id=%s
    """, (sesion_id, atleta_id))
    ses = cur.fetchone()
    if not ses:
        return None

    fecha_ses = str(ses[0])[:10]
    sport = (ses[1] or '').lower()
    dist_km = float(ses[4] or 0)
    hr_avg = float(ses[5] or 0)
    tipo = ses[6] or ''

    resultado = {'vinculada': False, 'umbral_actualizado': False}

    # ══════════════════════════════════════════════════════════
    # 1. Buscar carrera que coincida en fecha y distancia
    # ══════════════════════════════════════════════════════════
    cur.execute("""
        SELECT id, nombre, fecha, distancia_km, deporte, estado, distancia
        FROM carreras
        WHERE atleta_id=%s AND estado='pendiente'
        AND fecha::date BETWEEN (%s::date - INTERVAL '1 day') AND (%s::date + INTERVAL '1 day')
    """, (atleta_id, fecha_ses, fecha_ses))
    carreras = cur.fetchall()

    carrera_match = None
    for c in carreras:
        # Distancia: intentar distancia_km (numerico) o parsear distancia (texto)
        c_dist = float(c[3]) if c[3] else 0
        if c_dist == 0 and c[6]:
            try:
                c_dist = float(''.join(ch for ch in str(c[6]) if ch.isdigit() or ch == '.'))
            except (ValueError, TypeError):
                c_dist = 0
        c_deporte = (c[4] or '').lower()

        # Match por distancia (+-20%) y deporte
        if c_dist > 0 and dist_km > 0:
            ratio = dist_km / c_dist
            if 0.8 <= ratio <= 1.2:
                # Deporte compatible
                if ('run' in sport and 'run' in c_deporte) or \
                   ('cycl' in sport and ('cycl' in c_deporte or 'bike' in c_deporte)) or \
                   ('swim' in sport and 'swim' in c_deporte) or \
                   c_deporte in ('triatlon', 'triathlon'):
                    carrera_match = c
                    break
        elif c_dist == 0:
            # Carrera sin distancia: match solo por fecha y deporte
            if ('run' in sport and 'run' in c_deporte) or c_deporte in ('triatlon',):
                carrera_match = c
                break

    if carrera_match:
        carrera_id = carrera_match[0]
        dur = float(ses[2] or 0)
        # Calcular pace promedio
        pace_avg = None
        if dist_km > 0 and dur > 0:
            pace_avg = round(dur / dist_km, 2)

        # Grabar resultado en la carrera
        try:
            cur.execute("""
                UPDATE carreras SET
                    estado='completada',
                    resultado_tiempo=%s
                WHERE id=%s
            """, (
                f"{int(dur//60)}:{int(dur%60):02d}",
                carrera_id
            ))
            conn.commit()
            resultado['vinculada'] = True
            resultado['carrera'] = carrera_match[1]
            print(f'  [CARRERA] Sesion {sesion_id} vinculada a "{carrera_match[1]}"')
        except Exception as e:
            print(f'  [CARRERA] Error vinculando: {e}')
            try: conn.rollback()
            except: pass

        # Actualizar umbral desde la carrera
        if pace_avg and 'run' in sport:
            _actualizar_umbral_desde_carrera(conn, atleta_id, pace_avg, dist_km, hr_avg)
            resultado['umbral_actualizado'] = True

    # ══════════════════════════════════════════════════════════
    # 2. Verificar si Garmin envio nuevo umbral
    # ══════════════════════════════════════════════════════════
    cur.execute("""
        SELECT pace_umbral_run_garmin, pace_umbral_run,
               ftp_bike_garmin, ftp_watts
        FROM atletas WHERE id=%s
    """, (atleta_id,))
    at = cur.fetchone()
    if at:
        garmin_pace = float(at[0]) if at[0] else None
        actual_pace = float(at[1]) if at[1] else None
        garmin_ftp = float(at[2]) if at[2] else None
        actual_ftp = float(at[3]) if at[3] else None

        updates = {}
        # Si Garmin tiene un umbral distinto al actual (>3% diferencia), tomarlo
        if garmin_pace and actual_pace:
            if abs(garmin_pace - actual_pace) / actual_pace > 0.03:
                updates['pace_umbral_run'] = garmin_pace
                print(f'  [GARMIN] Nuevo pace umbral: {garmin_pace} (era {actual_pace})')

        if garmin_ftp and actual_ftp:
            if abs(garmin_ftp - actual_ftp) / actual_ftp > 0.03:
                updates['ftp_watts'] = round(garmin_ftp)
                print(f'  [GARMIN] Nuevo FTP: {round(garmin_ftp)}W (era {actual_ftp})')

        if updates:
            sets = ', '.join(f"{k}=%s" for k in updates)
            cur.execute(f"UPDATE atletas SET {sets} WHERE id=%s", list(updates.values()) + [atleta_id])
            conn.commit()
            resultado['umbral_actualizado'] = True

    return resultado


def _actualizar_umbral_desde_carrera(conn, atleta_id, pace_avg, dist_km, hr_avg):
    """
    Actualiza pace umbral desde una carrera.
    El pace de carrera NO es el umbral — hay que corregir por distancia.
    Factor de correccion (Daniels):
      5K: pace_carrera / 0.95 = umbral
      10K: pace_carrera / 1.00 = umbral (10K ~ umbral)
      21K: pace_carrera / 1.07 = umbral
      Maraton: pace_carrera / 1.12 = umbral
    """
    # Determinar factor segun distancia
    if dist_km <= 7:
        factor = 0.97
    elif dist_km <= 12:
        factor = 1.00
    elif dist_km <= 16:
        factor = 1.03
    elif dist_km <= 25:
        factor = 1.05
    else:
        factor = 1.10

    umbral_estimado = round(pace_avg / factor, 2)

    # Validar rango razonable
    if umbral_estimado < 3.0 or umbral_estimado > 10.0:
        print(f'  [UMBRAL] Valor fuera de rango: {umbral_estimado}, no actualizo')
        return

    cur = conn.cursor()
    cur.execute("SELECT pace_umbral_run FROM atletas WHERE id=%s", (atleta_id,))
    actual = cur.fetchone()
    actual_pace = float(actual[0]) if actual and actual[0] else None

    # Solo actualizar si es mejor (mas rapido) o significativamente distinto
    if actual_pace is None or abs(umbral_estimado - actual_pace) / actual_pace > 0.02:
        cur.execute("UPDATE atletas SET pace_umbral_run=%s WHERE id=%s", (umbral_estimado, atleta_id))
        conn.commit()
        um = int(umbral_estimado)
        us = int((umbral_estimado % 1) * 60)
        print(f'  [UMBRAL] Pace umbral actualizado desde carrera: {um}:{us:02d}/km (carrera pace {pace_avg:.2f}, factor {factor})')


def detectar_test(conn, atleta_id, sesion_id):
    """
    Detecta si una sesion es un test (tipo_sesion='test' o nombre contiene 'test').
    Si lo es, actualiza umbrales.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT sport, tipo_sesion, duration_min, distance_km, hr_avg,
               bio_potencia_20min
        FROM sesiones WHERE id=%s AND atleta_id=%s
    """, (sesion_id, atleta_id))
    ses = cur.fetchone()
    if not ses:
        return

    tipo = (ses[1] or '').lower()
    sport = (ses[0] or '').lower()

    if 'test' not in tipo:
        return

    # Test de running: actualizar pace
    if 'run' in sport and ses[3] and ses[2]:
        dist = float(ses[3])
        dur = float(ses[2])
        if dist > 0 and dur > 0:
            pace = dur / dist
            _actualizar_umbral_desde_carrera(conn, atleta_id, pace, dist, float(ses[4] or 0))
            print(f'  [TEST] Pace umbral actualizado desde test running')

    # Test de cycling: actualizar FTP
    if 'cycl' in sport and ses[5]:
        ftp_new = round(float(ses[5]) * 0.95)
        cur.execute("UPDATE atletas SET ftp_watts=%s WHERE id=%s", (ftp_new, atleta_id))
        conn.commit()
        print(f'  [TEST] FTP actualizado: {ftp_new}W (20min power × 0.95)')
