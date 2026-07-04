"""
noah_matching.py — NOAH Feedback Loop
======================================
Une las sesiones reales (Garmin) con las prescripciones de NOAH.
Calcula indicadores de cumplimiento y efectividad.
NOAH usa estos datos para aprender qué funciona para cada atleta.

Corre:
  python noah_matching.py                    # todos los atletas
  python noah_matching.py --atleta 3         # atleta específico
  python noah_matching.py --atleta 3 --dias 30  # últimos 30 días

Lo que hace:
  1. Busca prescripciones con sesion_fecha en el rango
  2. Para cada prescripción busca la sesión real Garmin más cercana (±2 días, mismo sport)
  3. Calcula: cumplimiento TSS, zonas, consistencia series, impacto HRV
  4. Actualiza sesiones.presc_tss, cumplimiento_pct, cumplimiento_flag
  5. Guarda resumen en tabla noah_feedback para que NOAH aprenda
"""

import psycopg2
import psycopg2.extras
import json
import argparse
import sys
import os
from datetime import date, timedelta
from pathlib import Path
from db_compat import ConexionCompat


def get_conn():
    conn = psycopg2.connect(os.environ.get('DATABASE_URL', ''), cursor_factory=psycopg2.extras.DictCursor)
    return ConexionCompat(conn)


def migrar_tabla_feedback(conn):
    """Crea la tabla noah_feedback si no existe."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS noah_feedback (
            id                    SERIAL PRIMARY KEY,
            atleta_id             INTEGER NOT NULL,
            sesion_id             INTEGER,              -- sesiones.id (Garmin)
            prescripcion_id       INTEGER,              -- prescripciones.id
            prescripcion_bloque_sesion_num INTEGER,     -- sesion_num en prescripcion_bloques
            biblioteca_id         TEXT,                 -- ID del metodo en sesiones_biblioteca.json
            fecha                 TEXT NOT NULL,
            sport                 TEXT,
            sesion_nombre_presc   TEXT,                 -- nombre prescripto
            sesion_nombre_real    TEXT,                 -- nombre sesion Garmin
            tss_planificado       REAL,
            tss_real              REAL,
            cumplimiento_tss      REAL,                 -- tss_real / tss_planificado
            tiempo_zona_obj_seg   REAL,                 -- tiempo real en zona objetivo
            consistencia_series   REAL,                 -- sesiones.consistencia_series
            hrv_dia_sesion        REAL,                 -- HRV ese dia
            hrv_dia_siguiente     REAL,                 -- HRV dia siguiente
            impacto_hrv           REAL,                 -- hrv_siguiente - hrv_sesion
            body_battery_dia      REAL,
            tsb_dia               REAL,
            nivel_carga_asignado  TEXT,                 -- ALTO/NORMAL/REDUCIDO/MINIMO
            resultado             TEXT,                 -- optima/buena/incompleta/sobrecarga/sin_datos
            notas                 TEXT,
            fecha_calculado       TEXT DEFAULT CURRENT_DATE,
            UNIQUE(atleta_id, prescripcion_id, prescripcion_bloque_sesion_num)
        )
    """)
    conn.commit()


def determinar_resultado(cumpl_tss, consistencia, impacto_hrv):
    """
    Clasifica el resultado de la sesion.
    """
    if cumpl_tss is None:
        return 'sin_datos'
    if cumpl_tss > 1.20:
        return 'sobrecarga'
    if cumpl_tss < 0.70:
        return 'incompleta'
    if cumpl_tss >= 0.90 and cumpl_tss <= 1.10:
        if consistencia is None or consistencia >= 0.85:
            if impacto_hrv is None or impacto_hrv >= -3:
                return 'optima'
            else:
                return 'buena'
        else:
            return 'buena'
    return 'buena'


def calcular_tiempo_zona_objetivo(sesion_row, zona_objetivo):
    """
    Calcula tiempo real en zona objetivo de la sesion.
    Usa hr_zone_1_s a hr_zone_5_s de sesiones.
    """
    zonas_map = {
        'Z1':    'hr_zone_1_s',
        'Z2':    'hr_zone_2_s',
        'Z3':    'hr_zone_3_s',
        'Z4':    'hr_zone_4_s',
        'Z5':    'hr_zone_5_s',
        'Z1-Z2': None,  # suma Z1+Z2
        'BZ2':   'hr_zone_2_s',
        'BZ3':   'hr_zone_3_s',
        'BZ4':   'hr_zone_4_s',
        'BZ5':   'hr_zone_5_s',
    }
    try:
        if zona_objetivo == 'Z1-Z2':
            z1 = sesion_row['hr_zone_1_s'] or 0
            z2 = sesion_row['hr_zone_2_s'] or 0
            return z1 + z2
        col = zonas_map.get(zona_objetivo)
        if col:
            return sesion_row[col] or 0
    except Exception:
        pass
    return None


def buscar_sesion_real(conn, atleta_id, fecha_presc, sport, ventana_dias=2):
    """
    Busca la sesion real de Garmin mas cercana a la fecha prescripta.
    Ventana: ±ventana_dias dias, mismo sport.
    Retorna la mas cercana en tiempo.
    """
    fecha = date.fromisoformat(fecha_presc)
    fecha_min = str(fecha - timedelta(days=ventana_dias))
    fecha_max = str(fecha + timedelta(days=ventana_dias))

    # Mapear sport de prescripcion a sport de sesiones
    sport_map = {
        'running': 'running',
        'cycling': 'cycling',
        'swimming': 'swimming',
        'swim': 'swimming',
        'bike': 'cycling',
        'run': 'running',
    }
    sport_real = sport_map.get(sport.lower(), sport.lower())

    rows = conn.execute("""
        SELECT id, fecha, sport, tss_total, duration_min, hr_avg,
               consistencia_series, hr_zone_1_s, hr_zone_2_s, hr_zone_3_s,
               hr_zone_4_s, hr_zone_5_s, tipo_sesion, session_type,
               cumplimiento_pct, cumplimiento_flag,
               presc_tss, presc_tipo
        FROM sesiones
        WHERE atleta_id=%s AND sport=%s AND fecha BETWEEN %s AND %s
        ORDER BY ABS(fecha::date - %s::date)
        LIMIT 1
    """, (atleta_id, sport_real, fecha_min, fecha_max, fecha_presc)).fetchall()

    return rows[0] if rows else None


def get_hrv_dia(conn, atleta_id, fecha):
    """Retorna HRV RMSSD del dia."""
    row = conn.execute(
        "SELECT hrv_rmssd, body_battery, modificador_carga FROM sleep_hrv WHERE atleta_id=%s AND fecha=%s",
        (atleta_id, fecha)
    ).fetchone()
    return row


def matching_atleta(conn, atleta_id, dias=60, verbose=True):
    """
    Corre el matching para un atleta en los últimos N dias.
    """
    fecha_min = str(date.today() - timedelta(days=dias))

    # Traer todas las prescripciones con sesiones en el rango
    presc_rows = conn.execute("""
        SELECT DISTINCT
            pb.prescripcion_id,
            pb.sesion_num,
            pb.sesion_fecha,
            pb.sesion_sport,
            pb.sesion_nombre,
            pb.sesion_tss,
            p.estado as presc_estado
        FROM prescripcion_bloques pb
        JOIN prescripciones p ON p.id = pb.prescripcion_id
        WHERE pb.atleta_id=%s
          AND pb.bloque_num=1
          AND pb.sesion_fecha >= %s
          AND pb.sesion_fecha <= %s
        ORDER BY pb.sesion_fecha
    """, (atleta_id, fecha_min, str(date.today()))).fetchall()

    if not presc_rows:
        if verbose:
            print(f"  Sin prescripciones en los últimos {dias} días para atleta {atleta_id}")
        return 0

    matched = 0
    sin_match = 0

    for presc in presc_rows:
        presc_id   = presc['prescripcion_id']
        sesion_num = presc['sesion_num']
        fecha      = presc['sesion_fecha']
        sport      = presc['sesion_sport']
        nombre     = presc['sesion_nombre']
        tss_plani  = presc['sesion_tss']

        # Buscar sesion real
        sesion = buscar_sesion_real(conn, atleta_id, fecha, sport)

        if not sesion:
            sin_match += 1
            if verbose:
                print(f"  ⚠ Sin match: {fecha} {sport} ({nombre[:30]})")
            continue

        # Calcular indicadores
        tss_real = sesion['tss_total']
        cumpl_tss = round(tss_real / tss_plani, 3) if tss_plani and tss_plani > 0 else None
        consistencia = sesion['consistencia_series']

        # HRV impacto
        hrv_dia   = get_hrv_dia(conn, atleta_id, fecha)
        fecha_sig = str(date.fromisoformat(fecha) + timedelta(days=1))
        hrv_sig   = get_hrv_dia(conn, atleta_id, fecha_sig)

        hrv_val      = hrv_dia['hrv_rmssd']   if hrv_dia  else None
        hrv_val_sig  = hrv_sig['hrv_rmssd']   if hrv_sig  else None
        body_battery = hrv_dia['body_battery'] if hrv_dia  else None
        impacto_hrv  = round(hrv_val_sig - hrv_val, 2) if hrv_val and hrv_val_sig else None

        # TSB del dia de la sesion
        tsb_row = conn.execute(
            "SELECT tsb FROM sesiones WHERE atleta_id=%s AND fecha=%s ORDER BY id LIMIT 1",
            (atleta_id, fecha)
        ).fetchone()
        tsb_dia = tsb_row['tsb'] if tsb_row else None

        # Resultado
        resultado = determinar_resultado(cumpl_tss, consistencia, impacto_hrv)

        # Cumplimiento flag
        if cumpl_tss is None:
            flag = 'sin_datos'
        elif cumpl_tss >= 0.90 and cumpl_tss <= 1.10:
            flag = 'ok'
        elif cumpl_tss < 0.75:
            flag = 'bajo'
        elif cumpl_tss > 1.20:
            flag = 'alto'
        else:
            flag = 'parcial'

        # Actualizar sesiones con datos de prescripción
        conn.execute("""
            UPDATE sesiones SET
                presc_tipo     = %s,
                presc_tss      = %s,
                presc_duracion = %s,
                cumplimiento_pct  = %s,
                cumplimiento_flag = %s
            WHERE id = %s
        """, (nombre, tss_plani, presc['sesion_tss'],
              round(cumpl_tss * 100, 1) if cumpl_tss else None,
              flag, sesion['id']))

        # Guardar en noah_feedback — INSERT OR REPLACE (SQLite) se traduce a
        # ON CONFLICT DO UPDATE sobre la restricción UNIQUE real de la tabla
        # (atleta_id, prescripcion_id, prescripcion_bloque_sesion_num),
        # confirmada contra el esquema real de noa.db.
        conn.execute("""
            INSERT INTO noah_feedback (
                atleta_id, sesion_id, prescripcion_id,
                prescripcion_bloque_sesion_num,
                fecha, sport,
                sesion_nombre_presc, sesion_nombre_real,
                tss_planificado, tss_real, cumplimiento_tss,
                consistencia_series,
                hrv_dia_sesion, hrv_dia_siguiente, impacto_hrv,
                body_battery_dia, tsb_dia,
                resultado
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (atleta_id, prescripcion_id, prescripcion_bloque_sesion_num)
            DO UPDATE SET
                sesion_id=excluded.sesion_id, fecha=excluded.fecha, sport=excluded.sport,
                sesion_nombre_presc=excluded.sesion_nombre_presc,
                sesion_nombre_real=excluded.sesion_nombre_real,
                tss_planificado=excluded.tss_planificado, tss_real=excluded.tss_real,
                cumplimiento_tss=excluded.cumplimiento_tss,
                consistencia_series=excluded.consistencia_series,
                hrv_dia_sesion=excluded.hrv_dia_sesion,
                hrv_dia_siguiente=excluded.hrv_dia_siguiente,
                impacto_hrv=excluded.impacto_hrv,
                body_battery_dia=excluded.body_battery_dia,
                tsb_dia=excluded.tsb_dia, resultado=excluded.resultado
        """, (
            atleta_id, sesion['id'], presc_id, sesion_num,
            fecha, sport,
            nombre, sesion['tipo_sesion'] or sesion['session_type'],
            tss_plani, tss_real, cumpl_tss,
            consistencia,
            hrv_val, hrv_val_sig, impacto_hrv,
            body_battery, tsb_dia,
            resultado
        ))

        matched += 1
        if verbose:
            estado_icon = {'optima':'✓','buena':'~','incompleta':'↓','sobrecarga':'↑','sin_datos':'?'}.get(resultado,'?')
            print(f"  {estado_icon} {fecha} {sport:8} TSS {tss_plani:.0f}→{tss_real:.0f} ({flag}) {resultado}")

    conn.commit()
    return matched


def resumen_aprendizaje(conn, atleta_id):
    """
    Muestra resumen de lo que NOAH aprendió para este atleta.
    """
    print(f"\n{'='*55}")
    print(f"  NOAH FEEDBACK — Atleta {atleta_id}")
    print(f"{'='*55}")

    rows = conn.execute("""
        SELECT resultado, COUNT(*) as n,
               ROUND(AVG(cumplimiento_tss)::numeric,2) as cumpl_avg,
               ROUND(AVG(impacto_hrv)::numeric,1) as hrv_avg
        FROM noah_feedback
        WHERE atleta_id=%s
        GROUP BY resultado
        ORDER BY n DESC
    """, (atleta_id,)).fetchall()

    if not rows:
        print("  Sin datos de feedback todavía.")
        return

    for r in rows:
        print(f"  {r['resultado']:12} {r['n']:3} sesiones  "
              f"cumpl={r['cumpl_avg']}  impacto_hrv={r['hrv_avg']}")

    # Patrones por sport
    print(f"\n  Por deporte:")
    rows2 = conn.execute("""
        SELECT sport, resultado, COUNT(*) as n
        FROM noah_feedback
        WHERE atleta_id=%s
        GROUP BY sport, resultado
        ORDER BY sport, n DESC
    """, (atleta_id,)).fetchall()

    for r in rows2:
        print(f"    {r['sport']:10} {r['resultado']:12} {r['n']} sesiones")

    # Alertas de aprendizaje — fechas relativas calculadas en Python en vez
    # de date('now', '-N days') (SQLite), que no existe en Postgres.
    fecha_lim_30 = str(date.today() - timedelta(days=30))
    fecha_lim_14 = str(date.today() - timedelta(days=14))

    print(f"\n  Alertas:")
    sobrecargas = conn.execute("""
        SELECT COUNT(*) as n FROM noah_feedback
        WHERE atleta_id=%s AND resultado='sobrecarga'
        AND fecha >= %s
    """, (atleta_id, fecha_lim_30)).fetchone()['n']

    if sobrecargas >= 2:
        print(f"  ⚠ {sobrecargas} sobrecargas en últimos 30 días — revisar TSS semanal")

    hrv_neg = conn.execute("""
        SELECT COUNT(*) as n FROM noah_feedback
        WHERE atleta_id=%s AND impacto_hrv < -3
        AND fecha >= %s
    """, (atleta_id, fecha_lim_30)).fetchone()['n']

    if hrv_neg >= 3:
        print(f"  ⚠ {hrv_neg} sesiones con impacto HRV negativo en 30 días — atleta acumulando fatiga")

    incompletas = conn.execute("""
        SELECT COUNT(*) as n FROM noah_feedback
        WHERE atleta_id=%s AND resultado='incompleta'
        AND fecha >= %s
    """, (atleta_id, fecha_lim_14)).fetchone()['n']

    if incompletas >= 2:
        print(f"  ⚠ {incompletas} sesiones incompletas en 14 días — revisar carga o disponibilidad")


def main():
    ap = argparse.ArgumentParser(description='NOAH — Matching prescripción vs sesión real')
    ap.add_argument('--atleta', type=int, default=None, help='ID del atleta (default: todos)')
    ap.add_argument('--dias',   type=int, default=60,   help='Días hacia atrás (default: 60)')
    ap.add_argument('--quiet',  action='store_true',    help='Sin output detallado')
    args = ap.parse_args()

    conn = get_conn()
    migrar_tabla_feedback(conn)

    verbose = not args.quiet

    if args.atleta:
        atletas = [args.atleta]
    else:
        rows = conn.execute("SELECT id, nombre FROM atletas WHERE activo=1").fetchall()
        atletas = [r['id'] for r in rows]
        if verbose:
            print(f"Atletas activos: {[r['nombre'] for r in rows]}")

    total = 0
    for aid in atletas:
        if verbose:
            print(f"\n{'─'*55}")
            row = conn.execute("SELECT nombre FROM atletas WHERE id=%s", (aid,)).fetchone()
            print(f"  Atleta: {row['nombre'] if row else aid}")
            print(f"{'─'*55}")

        n = matching_atleta(conn, aid, dias=args.dias, verbose=verbose)
        total += n

        if verbose:
            resumen_aprendizaje(conn, aid)

    conn.close()

    if verbose:
        print(f"\n{'='*55}")
        print(f"  Total sesiones matcheadas: {total}")
        print(f"{'='*55}")


if __name__ == '__main__':
    main()
