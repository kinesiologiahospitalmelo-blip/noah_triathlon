path = r'C:\Users\Win10\Desktop\noah_cloud\sincronizar_garmin.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

errors = []

# ── 1. Expandir KEY_MAP con todos los campos disponibles de Garmin ──────────
old1 = """    KEY_MAP = {
        'sumDistance':            ('distance_m',  100.0),
        'sumDuration':            ('ts_s',        1000.0),
        'directHeartRate':        ('hr',           1.0),
        'directSpeed':            ('speed_ms',     0.1),   # raw * 0.1 = m/s
        'directEnhancedSpeed':    ('speed_ms',     0.1),
        'directDoubleCadence':    ('cad_double',   1.0),
        'directRunCadence':       ('cad_run',      1.0),
        'directBikeCadence':      ('cadence',      1.0),
        'directElevation':        ('altitude_m',  100.0),
        'directEnhancedAltitude': ('altitude_m',  100.0),
        'directLatitude':         ('lat',          1.0),
        'directLongitude':        ('lon',          1.0),
        'directAirTemperature':   ('temperature',  1.0),
        'directPower':            ('power',        1.0),
        'sumAccumulatedPower':    ('power_acc',    1.0),
    }"""

new1 = """    KEY_MAP = {
        'sumDistance':                      ('distance_m',          100.0),
        'sumDuration':                      ('ts_s',                1000.0),
        'directHeartRate':                  ('hr',                   1.0),
        'directSpeed':                      ('speed_ms',             0.1),
        'directEnhancedSpeed':              ('speed_ms',             0.1),
        'directDoubleCadence':              ('cad_double',           1.0),
        'directRunCadence':                 ('cad_run',              1.0),
        'directBikeCadence':                ('cadence',              1.0),
        'directElevation':                  ('altitude_m',          100.0),
        'directEnhancedAltitude':           ('altitude_m',          100.0),
        'directLatitude':                   ('lat',                  1.0),
        'directLongitude':                  ('lon',                  1.0),
        'directAirTemperature':             ('temperature',          1.0),
        'directPower':                      ('power_w',              1.0),
        'sumAccumulatedPower':              ('power_acc',            1.0),
        # Running — dynamics
        'directGroundContactTime':          ('ground_contact_ms',   1.0),
        'directVerticalOscillation':        ('vertical_osc_mm',     1.0),
        'directStrideLength':               ('stride_length_m',  1000.0),
        'directVerticalRatio':              ('vertical_ratio',      1.0),
        'directGroundContactBalance':       ('ground_balance',    100.0),
        'directPerformanceCondition':       ('performance_cond',    1.0),
        'directRespirationRate':            ('respiration_rate',    1.0),
        # Cycling — dynamics
        'directLeftRightBalance':           ('left_right_pct',      1.0),
        'directPedalSmoothness':            ('pedal_smoothness',    1.0),
        'directTorqueEffectiveness':        ('torque_effectiveness', 1.0),
        # General
        'directSaturatedHemoglobinPercent': ('spo2_pct',            1.0),
        'directFractionalHemoglobinSaturation': ('spo2_pct',        1.0),
    }"""

if old1 in content:
    content = content.replace(old1, new1)
    print("OK 1 - KEY_MAP expandido")
else:
    errors.append("ERROR 1 - KEY_MAP no matcheo")

# ── 2. Expandir samples.append() con nuevos campos ──────────────────────────
old2 = """        samples.append({
            'ts_s':       round(s.get('ts_s', 0) - ts_min, 1),
            'hr':         int(hr)       if hr    else None,
            'speed_ms':   round(speed, 3) if speed else None,
            'cadence':    cadence,
            'altitude_m': round(s['altitude_m'], 1) if s.get('altitude_m') else None,
            'distance_m': round(s['distance_m'], 1) if s.get('distance_m') else None,
            'lat':        round(s['lat'], 6)         if s.get('lat')       else None,
            'lon':        round(s['lon'], 6)         if s.get('lon')       else None,
            'temperature':round(s['temperature'], 1) if s.get('temperature') else None,
            'power':      int(power)    if power else None,
        })"""

new2 = """        samples.append({
            'ts_s':                round(s.get('ts_s', 0) - ts_min, 1),
            'hr':                  int(hr)         if hr    else None,
            'speed_ms':            round(speed, 3) if speed else None,
            'cadence':             cadence,
            'altitude_m':          round(s['altitude_m'], 1)   if s.get('altitude_m')   else None,
            'distance_m':          round(s['distance_m'], 1)   if s.get('distance_m')   else None,
            'lat':                 round(s['lat'], 6)           if s.get('lat')          else None,
            'lon':                 round(s['lon'], 6)           if s.get('lon')          else None,
            'temperature':         round(s['temperature'], 1)  if s.get('temperature')  else None,
            'power_w':             int(power)      if power else None,
            # Running dynamics
            'ground_contact_ms':   round(s['ground_contact_ms'], 1)    if s.get('ground_contact_ms')   else None,
            'vertical_osc_mm':     round(s['vertical_osc_mm'], 1)      if s.get('vertical_osc_mm')     else None,
            'stride_length_m':     round(s['stride_length_m'], 3)      if s.get('stride_length_m')     else None,
            'vertical_ratio':      round(s['vertical_ratio'], 2)       if s.get('vertical_ratio')      else None,
            'ground_balance':      round(s['ground_balance'], 1)       if s.get('ground_balance')      else None,
            'performance_cond':    int(s['performance_cond'])          if s.get('performance_cond')    else None,
            'respiration_rate':    round(s['respiration_rate'], 1)     if s.get('respiration_rate')    else None,
            # Cycling dynamics
            'left_right_pct':      round(s['left_right_pct'], 1)       if s.get('left_right_pct')      else None,
            'pedal_smoothness':    round(s['pedal_smoothness'], 1)     if s.get('pedal_smoothness')    else None,
            'torque_effectiveness':round(s['torque_effectiveness'], 1) if s.get('torque_effectiveness') else None,
            # General
            'spo2_pct':            round(s['spo2_pct'], 1)             if s.get('spo2_pct')            else None,
        })"""

if old2 in content:
    content = content.replace(old2, new2)
    print("OK 2 - samples.append() expandido")
else:
    errors.append("ERROR 2 - samples.append() no matcheo")

# ── 3. Expandir INSERT en _guardar_streams ───────────────────────────────────
old3 = """            conn.execute('''
                INSERT INTO activity_samples
                (atleta_id, sesion_id, garmin_id, ts_s, hr, speed_ms,
                 cadence, altitude_m, distance_m, lat, lon, temperature, power)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (sesion_id, ts_s) DO NOTHING
            ''', (atleta_id, sesion_id, str(garmin_id),
                  s['ts_s'], s['hr'], s['speed_ms'], s['cadence'],
                  s['altitude_m'], s['distance_m'], s['lat'], s['lon'],
                  s['temperature'], s['power']))"""

new3 = """            conn.execute('''
                INSERT INTO activity_samples
                (atleta_id, sesion_id, garmin_id, ts_s, hr, speed_ms,
                 cadence, altitude_m, distance_m, lat, lon, temperature, power_w,
                 ground_contact_ms, vertical_osc_mm, stride_length_m, vertical_ratio,
                 ground_balance, performance_cond, respiration_rate,
                 left_right_pct, pedal_smoothness, torque_effectiveness, spo2_pct)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (sesion_id, ts_s) DO NOTHING
            ''', (atleta_id, sesion_id, str(garmin_id),
                  s['ts_s'], s['hr'], s['speed_ms'], s['cadence'],
                  s['altitude_m'], s['distance_m'], s['lat'], s['lon'],
                  s['temperature'], s['power_w'],
                  s['ground_contact_ms'], s['vertical_osc_mm'], s['stride_length_m'],
                  s['vertical_ratio'], s['ground_balance'], s['performance_cond'],
                  s['respiration_rate'], s['left_right_pct'], s['pedal_smoothness'],
                  s['torque_effectiveness'], s['spo2_pct']))"""

if old3 in content:
    content = content.replace(old3, new3)
    print("OK 3 - INSERT expandido con power_w y nuevos campos")
else:
    errors.append("ERROR 3 - INSERT no matcheo")

# ── 4. Fix CREATE TABLE: power → power_w ────────────────────────────────────
old4 = "            power        INTEGER,"
new4 = "            power_w      INTEGER,"

if old4 in content:
    content = content.replace(old4, new4)
    print("OK 4 - CREATE TABLE power -> power_w")
else:
    errors.append("ERROR 4 - CREATE TABLE power no matcheo")

if errors:
    for e in errors:
        print(e)
else:
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("GUARDADO OK - sincronizar_garmin.py actualizado")
