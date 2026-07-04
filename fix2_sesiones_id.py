path = r'C:\Users\Win10\Desktop\noah_cloud\app.py'

old = """    rows  = conn.execute('''
        SELECT fecha, sport, distance_km, duration_min,
               hr_avg, tss_total, ctl, atl, tsb, tipo_sesion
        FROM sesiones WHERE atleta_id=%s
        ORDER BY fecha DESC LIMIT %s
    ''', (atleta_id, limit)).fetchall()
    conn.close()

    sesiones = [{
        'fecha'     : r[0], 'sport': r[1],
        'distance'  : r[2], 'duration': r[3],
        'hr_avg'    : r[4], 'tss': r[5],
        'ctl'       : r[6], 'atl': r[7], 'tsb': r[8],
        'tipo'      : r[9],
    } for r in rows]"""

new = """    rows  = conn.execute('''
        SELECT id, fecha, sport, distance_km, duration_min,
               hr_avg, tss_total, ctl, atl, tsb, tipo_sesion
        FROM sesiones WHERE atleta_id=%s
        ORDER BY fecha DESC LIMIT %s
    ''', (atleta_id, limit)).fetchall()
    conn.close()

    sesiones = [{
        'id'        : r[0],
        'fecha'     : r[1], 'sport': r[2],
        'distance'  : r[3], 'duration': r[4],
        'hr_avg'    : r[5], 'tss': r[6],
        'ctl'       : r[7], 'atl': r[8], 'tsb': r[9],
        'tipo'      : r[10],
    } for r in rows]"""

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Bug 2 resuelto — endpoint /sesiones ahora devuelve 'id'")
else:
    print("❌ No matcheó el texto exacto — verificar manualmente")
