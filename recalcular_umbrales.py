"""
recalcular_umbrales.py — Umbrales desde RENDIMIENTO, no HR
=============================================================
Correr:  python recalcular_umbrales.py

REGLAS:
  1. Pace umbral run = desde carreras o mejores performances + Daniels VDOT
  2. FTP bike = best 20min power × 0.95 (Coggan)
  3. CSS swim = manual o Garmin
  4. Si Garmin envió nuevo umbral, tomarlo si difiere >3%
  5. NUNCA calcular pace desde HR
"""
import os, sys
try:
    import psycopg2, psycopg2.extras
except ImportError:
    print("pip install psycopg2-binary"); sys.exit(1)

DANIELS = {(0,5):0.97, (5,10):1.00, (10,15):1.02, (15,21.1):1.03, (21.1,30):1.05, (30,50):1.08}

def factor_daniels(d):
    for (lo,hi),f in DANIELS.items():
        if lo < d <= hi: return f
    return 1.03

def _fmt(p):
    if not p: return '--'
    return f'{int(p)}:{int((p%1)*60):02d}'

def recalc_pace(conn, aid, nombre):
    cur = conn.cursor()
    # 1. Carrera completada
    cur.execute("""
        SELECT s.duration_min, s.distance_km FROM carreras c
        LEFT JOIN sesiones s ON s.atleta_id=c.atleta_id
            AND s.fecha::date BETWEEN (c.fecha::date - 1) AND (c.fecha::date + 1)
            AND s.sport ILIKE '%%run%%'
        WHERE c.atleta_id=%s AND c.estado='completada' AND s.distance_km > 3
        ORDER BY c.fecha DESC LIMIT 1
    """, (aid,))
    r = cur.fetchone()
    if r and r[0] and r[1] and float(r[1]) > 3:
        pace = float(r[0]) / float(r[1])
        umb = round(pace / factor_daniels(float(r[1])), 2)
        if 3.5 < umb < 10:
            print(f'  Pace umbral desde carrera: {_fmt(umb)}/km ({float(r[1]):.1f}km a {_fmt(pace)})')
            return umb

    # 2. Garmin
    cur.execute("SELECT pace_umbral_run_garmin FROM atletas WHERE id=%s", (aid,))
    r = cur.fetchone()
    if r and r[0] and 3.5 < float(r[0]) < 10:
        print(f'  Pace umbral desde Garmin: {_fmt(float(r[0]))}/km')
        return float(r[0])

    # 3. Mejor sesión últimas 8 semanas
    cur.execute("""
        SELECT duration_min, distance_km FROM sesiones
        WHERE atleta_id=%s AND sport='running' AND duration_min>20 AND distance_km>3
        AND fecha::date >= CURRENT_DATE - INTERVAL '8 weeks'
        ORDER BY (duration_min/NULLIF(distance_km,0)) ASC LIMIT 1
    """, (aid,))
    r = cur.fetchone()
    if r and r[0] and r[1]:
        pace = float(r[0]) / float(r[1])
        umb = round(pace / factor_daniels(float(r[1])), 2)
        if 3.5 < umb < 10:
            print(f'  Pace umbral desde mejor sesión: {_fmt(umb)}/km ({float(r[1]):.1f}km a {_fmt(pace)})')
            return umb

    print(f'  Pace: sin datos suficientes')
    return None

def recalc_ftp(conn, aid, nombre):
    cur = conn.cursor()
    cur.execute("""
        SELECT power_w FROM activity_samples
        WHERE sesion_id IN (SELECT id FROM sesiones WHERE atleta_id=%s AND sport='cycling'
            AND fecha::date >= CURRENT_DATE - INTERVAL '8 weeks') AND power_w > 0
        ORDER BY power_w DESC
    """, (aid,))
    pws = [float(r[0]) for r in cur.fetchall()]
    if len(pws) >= 100:
        n = min(1200, len(pws))
        avg = sum(pws[:n]) / n
        ftp = round(avg * 0.95)
        if 50 < ftp < 500:
            print(f'  FTP: {ftp}W (best 20min avg {round(avg)}W × 0.95)')
            return ftp

    cur.execute("SELECT ftp_bike_garmin FROM atletas WHERE id=%s", (aid,))
    r = cur.fetchone()
    if r and r[0]:
        print(f'  FTP desde Garmin: {round(float(r[0]))}W')
        return round(float(r[0]))

    print(f'  FTP: sin datos')
    return None

def main():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url: print("ERROR: Falta DATABASE_URL"); sys.exit(1)
    conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, ftp_watts, pace_umbral_run, css_100m FROM atletas ORDER BY id")

    for a in cur.fetchall():
        aid, nombre = a[0], a[1]
        print(f'\n{"="*60}')
        print(f'  {nombre} (id={aid})')
        print(f'  FTP: {a[2]}W | Pace: {_fmt(float(a[3]) if a[3] else None)} | CSS: {_fmt(float(a[4]) if a[4] else None)}')

        updates = {}
        pace = recalc_pace(conn, aid, nombre)
        if pace and pace != (float(a[3]) if a[3] else None):
            updates['pace_umbral_run'] = pace

        ftp = recalc_ftp(conn, aid, nombre)
        if ftp and ftp != (int(a[2]) if a[2] else None):
            updates['ftp_watts'] = ftp

        if updates:
            sets = ', '.join(f"{k}=%s" for k in updates)
            cur.execute(f"UPDATE atletas SET {sets} WHERE id=%s", list(updates.values()) + [aid])
            conn.commit()
            print(f'  ✓ Guardado: {updates}')
        else:
            print(f'  Sin cambios')

    print(f'\n{"="*60}')
    print('[OK] Umbrales desde rendimiento (no HR)')
    conn.close()

if __name__ == '__main__':
    main()
