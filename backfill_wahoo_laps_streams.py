"""
backfill_wahoo_laps_streams.py
------------------------------------
Completa laps y streams para sesiones que YA se guardaron via Wahoo
(tienen wahoo_workout_id) pero que quedaron sin streams -- por
ejemplo, las primeras que se sincronizaron antes de agregar ese
codigo. No vuelve a bajar el resumen (TSS, distancia, etc, eso ya
esta bien) -- solo completa lo que falta.

USO (en la raiz del repo, con DATABASE_URL, WAHOO_CLIENT_ID y
WAHOO_CLIENT_SECRET seteadas):
    python backfill_wahoo_laps_streams.py --atleta_id 4
"""

import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sincronizar_wahoo import (
    get_conn, obtener_access_token, _bajar_laps_y_streams_wahoo,
    WAHOO_API_BASE,
)
from noa_db import NOADatabase

try:
    import requests
except ImportError:
    print("Falta requests. Instalar con: pip install requests --break-system-packages")
    sys.exit(1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--atleta_id', type=int, required=True)
    ap.add_argument('--dias', type=int, default=14,
                     help='Solo sesiones de los ultimos N dias (default 14 = 2 semanas). Usar 0 para sin limite.')
    args = ap.parse_args()

    conn = get_conn()
    db = NOADatabase(os.environ.get('DATABASE_URL'))

    access_token = obtener_access_token(conn, args.atleta_id)
    if not access_token:
        print("No hay token de Wahoo para este atleta.")
        return
    headers = {'Authorization': f'Bearer {access_token}'}

    from datetime import datetime, timedelta
    if args.dias > 0:
        fecha_desde = (datetime.now() - timedelta(days=args.dias)).strftime('%Y-%m-%d')
        filas = conn.execute("""
            SELECT id, fecha, sport, wahoo_workout_id
            FROM sesiones
            WHERE atleta_id=%s AND wahoo_workout_id IS NOT NULL
              AND (has_streams IS NULL OR has_streams=0)
              AND fecha >= %s
        """, (args.atleta_id, fecha_desde)).fetchall()
    else:
        filas = conn.execute("""
            SELECT id, fecha, sport, wahoo_workout_id
            FROM sesiones
            WHERE atleta_id=%s AND wahoo_workout_id IS NOT NULL
              AND (has_streams IS NULL OR has_streams=0)
        """, (args.atleta_id,)).fetchall()

    print(f"Sesiones de Wahoo sin streams: {len(filas)}")

    for f in filas:
        sesion_id, fecha, sport, wahoo_id = f[0], f[1], f[2], f[3]
        print(f"  Completando sesion {sesion_id} ({fecha} {sport})...")

        try:
            conn.close()
        except Exception:
            pass
        conn2 = get_conn()

        access_token = obtener_access_token(conn2, args.atleta_id)
        if not access_token:
            print("    [AVISO] No se pudo renovar el token de Wahoo, se corta aca.")
            break
        headers = {'Authorization': f'Bearer {access_token}'}

        r = requests.get(f'{WAHOO_API_BASE}/workouts/{wahoo_id}', headers=headers, timeout=20)
        if r.status_code != 200:
            print(f"    [AVISO] No se pudo re-consultar el workout: {r.status_code}")
            continue

        w = r.json()
        summary = w.get('workout_summary') or {}
        file_url = summary.get('file', {}).get('url') if isinstance(summary.get('file'), dict) else None
        if not file_url:
            print("    [AVISO] Ese workout no tiene archivo .FIT disponible.")
            continue

        _bajar_laps_y_streams_wahoo(conn2, db, args.atleta_id, sesion_id, fecha, file_url, headers)

        # FIX: calcular biomarcadores de la sesion (decoupling, EF, curva de
        # potencia, etc.) -- esto ya estaba conectado para Garmin pero NO
        # para Wahoo. Se lee lo recien guardado y se calcula ahora.
        try:
            from guardar_biomarcadores import calcular_y_guardar_biomarcadores
            muestras = conn2.execute("""
                SELECT ts_s, hr, speed_ms, cadence, power_w, altitude_m,
                       distance_m, left_right_pct
                FROM activity_samples WHERE sesion_id=%s ORDER BY ts_s
            """, (sesion_id,)).fetchall()
            if muestras:
                samples_dict = [{
                    'ts_s': m[0], 'hr': m[1], 'speed_ms': m[2], 'cadence': m[3],
                    'power_w': m[4], 'altitude_m': m[5], 'distance_m': m[6],
                    'left_right_pct': m[7],
                } for m in muestras]
                calcular_y_guardar_biomarcadores(conn2, sesion_id, sport, samples_dict)
                conn2.commit()
                print(f"    [OK] Biomarcadores calculados")
        except Exception as e:
            print(f"    [AVISO] No se pudieron calcular biomarcadores: {e}")

        conn = conn2

    print("\n[OK] Backfill terminado.")


if __name__ == '__main__':
    main()
