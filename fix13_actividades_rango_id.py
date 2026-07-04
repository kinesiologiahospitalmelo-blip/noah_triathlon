path = r'C:\Users\Win10\Desktop\noah_cloud\app.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old = """        rows = conn.execute(
            "SELECT fecha, sport, distance_km, duration_min, hr_avg, tss_total, tipo_sesion FROM sesiones WHERE atleta_id=%s AND fecha BETWEEN %s AND %s AND tss_total>0 AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) ORDER BY fecha, sport",
            (atleta_id, desde, hasta)).fetchall()
        actividades = {}
        for r in rows:
            f = str(r[0])[:10]
            if f not in actividades: actividades[f] = []
            actividades[f].append({'fecha':f,'sport':r[1],'distance_km':r[2],'duration_min':r[3],'hr_avg':r[4],'tss':r[5],'tipo':r[6]})"""

new = """        rows = conn.execute(
            "SELECT id, fecha, sport, distance_km, duration_min, hr_avg, tss_total, tipo_sesion FROM sesiones WHERE atleta_id=%s AND fecha BETWEEN %s AND %s AND tss_total>0 AND (fuente IS NULL OR fuente NOT IN ('prescripcion','simulacion','generada')) ORDER BY fecha, sport",
            (atleta_id, desde, hasta)).fetchall()
        actividades = {}
        for r in rows:
            f = str(r[1])[:10]
            if f not in actividades: actividades[f] = []
            actividades[f].append({'sesion_id':r[0],'fecha':f,'sport':r[2],'distance_km':r[3],'duration_min':r[4],'hr_avg':r[5],'tss':r[6],'tipo':r[7]})"""

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - actividades_rango ahora devuelve sesion_id")
else:
    print("ERROR - no matcheo el texto exacto")
