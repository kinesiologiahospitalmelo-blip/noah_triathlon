path = r'C:\Users\Win10\Desktop\noah_cloud\app.py'

old = "    sql  = ('SELECT ts_s, power, cadence FROM activity_samples '\n            'WHERE sesion_id = %s AND atleta_id = %s ORDER BY ts_s')"

new = "    sql  = ('SELECT ts_s, power_w, cadence FROM activity_samples '\n            'WHERE sesion_id = %s AND atleta_id = %s ORDER BY ts_s')"

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Bug 4 resuelto — columna 'power' corregida a 'power_w'")
else:
    print("❌ No matcheó el texto exacto — verificar manualmente")
