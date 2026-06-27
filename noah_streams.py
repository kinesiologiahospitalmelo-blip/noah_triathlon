"""
noah_streams.py — NOAH Activity Streams v3
════════════════════════════════════════════════════════════════════════════
Baja y guarda streams punto a punto de Garmin Connect.

ESTRUCTURA REAL CONFIRMADA (Garmin API):
  metricDescriptors: [{metricsIndex, key, unit:{factor}}]
  activityDetailMetrics: [{metrics: [v0, v1, ..., vN]}]

  Cada valor raw se convierte según factor:
    factor < 1  → raw * factor   (ej: speed: raw * 0.1 = m/s)
    factor > 1  → raw / factor   (ej: distance: raw / 100 = metros)
    factor = 1  → raw directo    (ej: hr, power, temperature)

CAMPOS POR DEPORTE:
  Running:  HR, speed, cadencia, elevación, distancia, GPS, temperatura, tiempo
  Cycling:  HR, potencia, speed, distancia, temperatura, tiempo
  Swimming: HR, cadencia, distancia, tiempo

GRACEFUL DEGRADATION:
  Si un campo no existe → NULL en DB. Nunca rompe.

USO:
  python noah_streams.py --migrate
  python noah_streams.py --backfill --atleta 1 --dias 30
  python noah_streams.py --backfill   (todos los atletas)
  (requiere variable de entorno DATABASE_URL con la cadena de conexión a Postgres/Supabase)
════════════════════════════════════════════════════════════════════════════
"""

import psycopg2, base64, json
from datetime import date, timedelta
from pathlib import Path
from db_compat import asegurar_columnas


# ── Mapeo completo de claves Garmin → nombre NOAH ────────────────────────────
# (factor_use: si < 1 → multiplicar, si > 1 → dividir, si 1 → directo)
GARMIN_KEY_MAP = {
    # Tiempo
    "sumDuration":               ("ts_s",          1000.0),  # ms → s
    "sumElapsedDuration":        ("ts_s",           1000.0),
    "sumMovingDuration":         ("ts_s_mov",       1000.0),
    # Distancia
    "sumDistance":               ("distance_m",     100.0),   # cm → m
    # FC
    "directHeartRate":           ("hr",             1.0),
    # Velocidad → m/s
    "directSpeed":               ("speed_ms",       0.1),     # raw*0.1 = m/s
    "directEnhancedSpeed":       ("speed_ms",       0.1),
    # Potencia
    "directPower":               ("power_w",        1.0),
    "directFunctionalPower":     ("power_w",        1.0),
    "sumAccumulatedPower":       ("power_acc_j",    1.0),
    # Cadencia
    "directDoubleCadence":       ("cadence_double", 1.0),     # spm ambas piernas
    "directRunCadence":          ("cadence_run",    1.0),     # zancadas/min
    "directBikeCadence":         ("cadence_rpm",    1.0),     # rpm
    "directCadence":             ("cadence_rpm",    1.0),
    # Altitud
    "directElevation":           ("altitude_m",     100.0),   # cm → m
    "directEnhancedAltitude":    ("altitude_m",     100.0),
    # GPS
    "directLatitude":            ("lat",            1.0),
    "directLongitude":           ("lon",            1.0),
    # Temperatura
    "directAirTemperature":      ("temperature_c",  1.0),
    # Natación
    "directSwimStroke":          ("stroke_type",    1.0),
    "directSwimmingCadence":     ("cadence_swim",   1.0),
    # Running dynamics (HRM-Pro)
    "directVerticalOscillation": ("vert_osc_mm",    10.0),    # mm
    "directGroundContactTime":   ("gct_ms",         1.0),     # ms
    "directGroundContactBalance":("gct_balance",    100.0),   # %
    "directStrideLength":        ("stride_cm",      100.0),   # cm
    "directVerticalRatio":       ("vert_ratio",     100.0),   # %
    # Respiración
    "directRespirationRate":     ("respiration",    1.0),
    # Stress
    "directStress":              ("stress",         1.0),
}


def migrate_db(conn):
    """Crea tablas y columnas necesarias. Idempotente."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS activity_samples ("
        "id SERIAL PRIMARY KEY,"
        "atleta_id INTEGER NOT NULL,"
        "sesion_id INTEGER NOT NULL,"
        "garmin_id TEXT,"
        "ts_s INTEGER NOT NULL,"
        "ts_s_mov INTEGER,"
        "hr INTEGER,"
        "power_w INTEGER,"
        "power_acc_j REAL,"
        "respiration REAL,"
        "stress INTEGER,"
        "speed_ms REAL,"
        "cadence INTEGER,"
        "distance_m REAL,"
        "altitude_m REAL,"
        "lat REAL,"
        "lon REAL,"
        "temperature_c REAL,"
        "vert_osc_mm REAL,"
        "gct_ms REAL,"
        "gct_balance REAL,"
        "stride_cm REAL,"
        "vert_ratio REAL,"
        "stroke_type INTEGER,"
        "cadence_swim INTEGER,"
        "UNIQUE(sesion_id, ts_s))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_samp_sesion ON activity_samples(sesion_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_samp_atleta ON activity_samples(atleta_id, sesion_id)")

    # garmin_activity_id + has_streams en sesiones — PRAGMA table_info
    # (SQLite) reemplazado por el helper compartido asegurar_columnas.
    asegurar_columnas(conn, 'sesiones', [
        ("garmin_activity_id","TEXT"), ("has_streams","INTEGER DEFAULT 0")
    ])
    conn.commit()
    print("  [MIGRATE] OK")


def _get_client(conn, atleta_id: int):
    row = conn.execute(
        "SELECT garmin_user, garmin_pass FROM atletas WHERE id=%s", (atleta_id,)
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        from garminconnect import Garmin
        pwd = base64.b64decode(row[1].encode()).decode() if row[1] else ""
        c = Garmin(row[0], pwd)
        c.login()
        return c
    except Exception as e:
        print(f"  [STREAMS] Login fallido atleta {atleta_id}: {e}")
        return None


def _parsear(details: dict, sport: str) -> list:
    """
    Parsea get_activity_details() → lista de dicts con TODOS los campos disponibles.
    Campos faltantes quedan como None (graceful degradation).
    """
    if not details:
        return []

    descriptors = details.get("metricDescriptors", [])
    raw_metrics  = details.get("activityDetailMetrics", [])
    if not descriptors or not raw_metrics:
        return []

    # Construir mapa: índice → (nombre_noah, factor)
    idx_map = {}
    for d in descriptors:
        key    = d.get("key", "")
        idx    = d.get("metricsIndex", -1)
        factor = d.get("unit", {}).get("factor", 1.0) or 1.0
        if key in GARMIN_KEY_MAP:
            name, factor_use = GARMIN_KEY_MAP[key]
            # No sobreescribir si ya hay un campo mejor para el mismo nombre
            if name not in [v[0] for v in idx_map.values()]:
                idx_map[idx] = (name, factor_use)

    if not idx_map:
        print(f"  [STREAMS] Sin métricas reconocibles")
        return []

    names_found = [v[0] for v in idx_map.values()]
    print(f"  [STREAMS] Métricas: {names_found}")

    raw_samples = []
    for item in raw_metrics:
        flat = item.get("metrics", [])
        if not flat:
            continue
        s = {}
        for idx, (name, factor) in idx_map.items():
            if idx < len(flat) and flat[idx] is not None:
                v = flat[idx]
                if   factor < 1.0: v = v * factor
                elif factor > 1.0: v = v / factor
                s[name] = v
        if s:
            raw_samples.append(s)

    if not raw_samples:
        return []

    # Normalizar ts_s: restar el mínimo para que empiece en 0
    ts_min = min(s.get("ts_s", 0) for s in raw_samples)

    samples = []
    for i, s in enumerate(raw_samples):
        hr     = s.get("hr")
        speed  = s.get("speed_ms")
        power  = s.get("power_w")

        # Validar rangos fisiológicos
        if hr    and not (25 <= hr    <= 260): hr    = None
        if speed and not (0  <  speed <= 22):  speed = None
        if power and not (0  <  power <= 3000):power = None

        # Cadencia: unificar según deporte
        cadence = None
        if   s.get("cadence_double"): cadence = int(s["cadence_double"])
        elif s.get("cadence_run"):    cadence = int(s["cadence_run"] * 2)
        elif s.get("cadence_rpm"):    cadence = int(s["cadence_rpm"])
        elif s.get("cadence_swim"):   cadence = int(s["cadence_swim"])

        # GPS: convertir semicircles a grados si necesario
        lat = s.get("lat")
        lon = s.get("lon")
        if lat and abs(lat) > 90:  lat = lat * (180 / 2**31)
        if lon and abs(lon) > 180: lon = lon * (180 / 2**31)

        ts = i  # use loop index as sequential ts_s

        samples.append({
            "ts_s":         len(samples),  # índice secuencial — garantiza unicidad
            "ts_s_real":    ts,            # tiempo real en segundos (para el gráfico)
            "ts_s_mov":     int(round(s["ts_s_mov"] - ts_min)) if s.get("ts_s_mov") else None,
            "hr":           int(hr)            if hr     else None,
            "power_w":      int(power)         if power  else None,
            "power_acc_j":  round(s["power_acc_j"], 1) if s.get("power_acc_j") else None,
            "respiration":  round(s["respiration"], 1)  if s.get("respiration") else None,
            "stress":       int(s["stress"])   if s.get("stress") else None,
            "speed_ms":     round(speed, 4)    if speed  else None,
            "cadence":      cadence,
            "distance_m":   round(s["distance_m"], 2) if s.get("distance_m") else None,
            "altitude_m":   round(s["altitude_m"], 2) if s.get("altitude_m") else None,
            "lat":          round(lat, 7)      if lat    else None,
            "lon":          round(lon, 7)      if lon    else None,
            "temperature_c":round(s["temperature_c"], 1) if s.get("temperature_c") else None,
            "vert_osc_mm":  round(s["vert_osc_mm"], 1)  if s.get("vert_osc_mm") else None,
            "gct_ms":       round(s["gct_ms"], 1)        if s.get("gct_ms") else None,
            "gct_balance":  round(s["gct_balance"], 2)   if s.get("gct_balance") else None,
            "stride_cm":    round(s["stride_cm"], 1)     if s.get("stride_cm") else None,
            "vert_ratio":   round(s["vert_ratio"], 2)    if s.get("vert_ratio") else None,
            "stroke_type":  int(s["stroke_type"]) if s.get("stroke_type") else None,
            "cadence_swim": int(s["cadence_swim"]) if s.get("cadence_swim") else None,
        })

    return samples


def _guardar(conn, atleta_id, sesion_id, garmin_id, samples) -> int:
    saved = 0
    for i, s in enumerate(samples):
        try:
            conn.execute(
                "INSERT INTO activity_samples "
                "(atleta_id, sesion_id, garmin_id, ts_s, ts_s_mov, "
                "hr, power_w, power_acc_j, respiration, stress, "
                "speed_ms, cadence, distance_m, altitude_m, lat, lon, "
                "temperature_c, vert_osc_mm, gct_ms, gct_balance, "
                "stride_cm, vert_ratio, stroke_type, cadence_swim) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT (sesion_id, ts_s) DO UPDATE SET "
                "garmin_id=excluded.garmin_id, ts_s_mov=excluded.ts_s_mov, "
                "hr=excluded.hr, power_w=excluded.power_w, power_acc_j=excluded.power_acc_j, "
                "respiration=excluded.respiration, stress=excluded.stress, "
                "speed_ms=excluded.speed_ms, cadence=excluded.cadence, "
                "distance_m=excluded.distance_m, altitude_m=excluded.altitude_m, "
                "lat=excluded.lat, lon=excluded.lon, temperature_c=excluded.temperature_c, "
                "vert_osc_mm=excluded.vert_osc_mm, gct_ms=excluded.gct_ms, "
                "gct_balance=excluded.gct_balance, stride_cm=excluded.stride_cm, "
                "vert_ratio=excluded.vert_ratio, stroke_type=excluded.stroke_type, "
                "cadence_swim=excluded.cadence_swim",
                (atleta_id, sesion_id, str(garmin_id),
                 i, s.get("ts_s_mov"),
                 s["hr"], s["power_w"], s["power_acc_j"], s["respiration"], s["stress"],
                 s["speed_ms"], s["cadence"], s["distance_m"], s["altitude_m"],
                 s["lat"], s["lon"], s["temperature_c"],
                 s["vert_osc_mm"], s["gct_ms"], s["gct_balance"],
                 s["stride_cm"], s["vert_ratio"], s["stroke_type"], s["cadence_swim"],
            ))
            saved += 1
        except Exception as e:
            # Rollback OBLIGATORIO: este insert corre dentro de un loop de
            # potencialmente cientos de samples. En Postgres, si UNO falla
            # dentro de una transacción y no se hace rollback, TODOS los
            # inserts siguientes del mismo loop fallarían en cascada con
            # "current transaction is aborted" — a diferencia de SQLite,
            # que no tiene este comportamiento estricto.
            conn.rollback()
            print(f"  [INSERT ERROR] i={i} e={e}")
    if saved:
        conn.execute("UPDATE sesiones SET has_streams=1 WHERE id=%s", (sesion_id,))
    conn.commit()
    return saved

def leer_samples_db(conn, sesion_id: int, sport: str) -> list:
    """Lee samples de DB y calcula pace."""
    rows = conn.execute("""
        SELECT ts_s, hr, power_w, speed_ms, cadence,
               distance_m, altitude_m, lat, lon, temperature_c,
               vert_osc_mm, gct_ms, gct_balance, stride_cm, vert_ratio,
               respiration, stress
        FROM activity_samples WHERE sesion_id=%s ORDER BY ts_s
    """, (sesion_id,)).fetchall()

    n = len(rows)
    result = []
    for idx, r in enumerate(rows):
        speed = r[3]
        pace  = None
        if speed and speed > 0.3:
            p = (100/(speed*60)) if sport=="swimming" else (1000/(speed*60))
            pace = round(p, 3) if 1.5 < p < 20 else None
        result.append({
            "ts_s":          r[0],   # índice secuencial (= posición en la sesión)
            "hr":            r[1],
            "power_w":       r[2],
            "speed_ms":      speed,
            "pace":          pace,
            "cadence":       r[4],
            "distance_m":    r[5],
            "altitude_m":    r[6],
            "lat":           r[7],
            "lon":           r[8],
            "temperature_c": r[9],
            "vert_osc_mm":   r[10],
            "gct_ms":        r[11],
            "gct_balance":   r[12],
            "stride_cm":     r[13],
            "vert_ratio":    r[14],
            "respiration":   r[15],
            "stress":        r[16],
        })
    return result


def bajar_streams(conn, atleta_id, sesion_id, garmin_id, sport, client=None) -> list:
    if not garmin_id:
        return []
    if client is None:
        client = _get_client(conn, atleta_id)
    if client is None:
        return []
    print(f"  [STREAMS] Bajando garmin_id={garmin_id}...")
    try:
        details = client.get_activity_details(garmin_id)
    except Exception as e:
        print(f"  [STREAMS] Error: {e}")
        return []
    samples = _parsear(details, sport)
    if samples:
        n = _guardar(conn, atleta_id, sesion_id, garmin_id, samples)
        print(f"  [STREAMS] ✓ {n}/{len(samples)} samples guardados")
    return samples


def procesar_para_frontend(samples: list, sport: str, lthr: int = 162) -> dict:
    """Prepara los datos para el gráfico frontend."""
    if not samples:
        return {"series": [], "stats": {}, "zonas": {}, "n": 0}

    # Decimar a máx 500 puntos
    n = len(samples)
    if n > 500:
        step = n / 500
        samples = [samples[int(i*step)] for i in range(500)]
        samples.append(samples[-1])

    # Suavizado media móvil
    def smooth(vals, w=7):
        out = []
        half = w//2
        for i in range(len(vals)):
            chunk = [v for v in vals[max(0,i-half):i+half+1] if v is not None]
            out.append(round(sum(chunk)/len(chunk), 1) if chunk else None)
        return out

    hr_sm    = smooth([s.get("hr")      for s in samples], 7)
    pow_sm   = smooth([s.get("power_w") for s in samples], 7)
    pace_sm  = smooth([s.get("pace")    for s in samples], 5)

    # Scale index to real seconds using total duration
    n_samp = len(samples)
    dur_s_real = samples[-1]["ts_s"] if samples else 0
    # If ts_s is sequential index (0..N), scale to real time using dur_min
    if dur_s_real < n_samp * 0.5 and n_samp > 10:
        # ts_s looks like sequential index - estimate real time from session duration
        # Use distance-based time if available, else assume 1s per sample
        pass  # ts_s IS the index, use as-is for now

    series = []
    for i, s in enumerate(samples):
        series.append({
            "t":        s["ts_s"],  # index-based, frontend scales to time
            "hr":       hr_sm[i],
            "power":    pow_sm[i],
            "pace":     pace_sm[i],
            "cadence":  s["cadence"],
            "alt":      s["altitude_m"],
            "dist_km":  round(s["distance_m"]/1000, 3) if s.get("distance_m") else None,
            "temp":     s.get("temperature_c"),
            "vert_osc": s.get("vert_osc_mm"),
            "gct":      s.get("gct_ms"),
            "stride":   s.get("stride_cm"),
            "resp":     s.get("respiration"),
        })

    # Stats desde samples completos
    hr_all  = [s["hr"] for s in samples if s.get("hr")]
    pw_all  = [s["power_w"] for s in samples if s.get("power_w")]
    pa_all  = [s["pace"] for s in samples if s.get("pace")]
    ca_all  = [s["cadence"] for s in samples if s.get("cadence")]

    # NP (Normalized Power)
    np_w = None
    if len(pw_all) >= 30:
        window = 30
        rolling = []
        for i in range(len(pw_all)-window+1):
            chunk = pw_all[i:i+window]
            rolling.append(sum(chunk)/len(chunk))
        if rolling:
            np_w = round((sum(r**4 for r in rolling)/len(rolling))**0.25, 1)

    # Zonas
    ts_all = [s["ts_s"] for s in samples]
    hr_ts  = [s["hr"] for s in samples]
    zonas  = {f"Z{i}": {"s":0, "pct":0} for i in range(1,7)}
    for i, hr in enumerate(hr_ts):
        if not hr or not lthr: continue
        dt = (ts_all[i+1]-ts_all[i]) if i < len(ts_all)-1 else 1
        r  = hr/lthr
        z  = "Z1" if r<0.82 else "Z2" if r<0.88 else "Z3" if r<0.94 else "Z4" if r<1.00 else "Z5" if r<1.06 else "Z6"
        zonas[z]["s"] += dt
    total = sum(z["s"] for z in zonas.values()) or 1
    for z in zonas.values():
        z["pct"] = round(z["s"]/total*100, 1)

    dur_s = ts_all[-1] if ts_all else 0

    return {
        "series":  series,
        "stats": {
            "hr_avg":      round(sum(hr_all)/len(hr_all))  if hr_all else None,
            "hr_max":      max(hr_all)                      if hr_all else None,
            "power_avg":   round(sum(pw_all)/len(pw_all))  if pw_all else None,
            "power_max":   max(pw_all)                      if pw_all else None,
            "power_np":    np_w,
            "pace_avg":    round(sum(pa_all)/len(pa_all),3) if pa_all else None,
            "cadence_avg": round(sum(ca_all)/len(ca_all))  if ca_all else None,
            "n_samples":   len(samples),
            "dur_s":       dur_s,
        },
        "zonas":  zonas,
        "n":      len(series),
        "dur_min": round(dur_s/60, 1) if dur_s else None,
    }


def obtener_streams(conn, atleta_id, sesion_id, garmin_id,
                    sport, dur_min, lthr, force=False) -> dict:
    """Función principal: cache-first."""
    n_cached = conn.execute(
        "SELECT COUNT(*) FROM activity_samples WHERE sesion_id=%s",
        (sesion_id,)
    ).fetchone()[0]

    if n_cached > 10 and not force:
        samples = leer_samples_db(conn, sesion_id, sport)
        fuente  = "db_cache"
    elif garmin_id:
        samples = bajar_streams(conn, atleta_id, sesion_id, garmin_id, sport)
        fuente  = "garmin_api"
        if not samples:
            samples = leer_samples_db(conn, sesion_id, sport)
            fuente  = "db_fallback"
    else:
        return None

    if not samples:
        return None

    resultado = procesar_para_frontend(samples, sport, lthr)
    resultado["fuente"] = fuente
    return resultado


def save_garmin_id(conn, sesion_id, garmin_id):
    if garmin_id and sesion_id:
        conn.execute("UPDATE sesiones SET garmin_activity_id=%s WHERE id=%s",
                     (str(garmin_id), sesion_id))


def backfill_streams(db_path: str, atleta_id=None, max_acts=50, dias_atras=60):
    """Baja streams de actividades históricas sin streams."""
    import psycopg2.extras
    from db_compat import ConexionCompat
    conn = ConexionCompat(psycopg2.connect(db_path, cursor_factory=psycopg2.extras.DictCursor))
    migrate_db(conn)

    desde = str(date.today() - timedelta(days=dias_atras))
    where = f"AND s.atleta_id={atleta_id}" if atleta_id else ""

    rows = conn.execute(f"""
        SELECT s.id, s.atleta_id, s.fecha, s.sport,
               s.duration_min, s.garmin_activity_id
        FROM sesiones s
        LEFT JOIN (
            SELECT sesion_id, COUNT(*) as n
            FROM activity_samples GROUP BY sesion_id
        ) c ON c.sesion_id = s.id
        WHERE s.tss_total > 0 AND s.fecha >= %s
          AND (s.fuente IS NULL OR s.fuente NOT IN ('prescripcion','simulacion','generada'))
          {where}
          AND (c.n IS NULL OR c.n < 100)
        ORDER BY s.fecha DESC LIMIT %s
    """, (desde, max_acts)).fetchall()

    if not rows:
        print("  [BACKFILL] Sin sesiones pendientes")
        conn.close(); return

    print(f"  [BACKFILL] {len(rows)} sesiones a procesar")

    SPORT_MAP = {
        "running":"running","treadmill_running":"running",
        "cycling":"cycling","indoor_cycling":"cycling",
        "lap_swimming":"swimming","pool_swimming":"swimming",
    }

    from collections import defaultdict
    por_atleta = defaultdict(list)
    for r in rows:
        por_atleta[r[1]].append(r)

    for aid, sesiones in por_atleta.items():
        client = _get_client(conn, aid)
        if not client:
            print(f"  [BACKFILL] Sin cliente para atleta {aid}")
            continue

        fechas = sorted(set(s[2] for s in sesiones), reverse=True)
        for fecha in fechas:
            try:
                acts_g = client.get_activities_by_date(fecha, fecha)
            except Exception as e:
                print(f"  [BACKFILL] Error {fecha}: {e}"); continue

            for ses in [s for s in sesiones if s[2] == fecha]:
                ses_id, _, _, sport, dur, gid = ses
                # Buscar match por deporte
                matched = next(
                    (a for a in acts_g
                     if SPORT_MAP.get(a.get('activityType',{}).get('typeKey','')) == sport),
                    None
                )
                if not matched:
                    print(f"  [BACKFILL] Sin match: {fecha} {sport}"); continue

                real_gid = str(matched['activityId'])
                if not gid:
                    conn.execute("UPDATE sesiones SET garmin_activity_id=%s WHERE id=%s",
                                 (real_gid, ses_id))
                    conn.commit()

                bajar_streams(conn, aid, ses_id, real_gid, sport, client=client)

    conn.close()
    print("  [BACKFILL] Completado")


if __name__ == "__main__":
    import argparse, os, sys
    import psycopg2
    ap = argparse.ArgumentParser()
    ap.add_argument("--migrate",  action="store_true")
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--atleta",   type=int, default=None)
    ap.add_argument("--dias",     type=int, default=60)
    ap.add_argument("--max",      type=int, default=50)
    a = ap.parse_args()

    # --db (ruta a archivo SQLite) reemplazado por DATABASE_URL — mismo
    # patrón que el resto de los módulos migrados. backfill_streams ya
    # abre su propia conexión Postgres internamente, así que aquí solo
    # se necesita para el --migrate suelto.
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("Falta la variable de entorno DATABASE_URL (cadena de conexión a Postgres/Supabase)")
        sys.exit(1)

    if a.migrate or a.backfill:
        c = psycopg2.connect(db_url)
        from db_compat import ConexionCompat
        migrate_db(ConexionCompat(c))
        c.close()

    if a.backfill:
        backfill_streams(db_url, a.atleta, a.max, a.dias)
    elif not a.migrate:
        print("Uso:")
        print("  python noah_streams.py --migrate")
        print("  python noah_streams.py --backfill --atleta 1")
