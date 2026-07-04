path = r'C:\Users\Win10\Desktop\noah_cloud\noa_estados.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

old1 = "# ── Tablas de referencia TrainingPeaks / literatura ──────────────────────────"

new1 = """def _read_sql(sql, conn, params=None):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ── Tablas de referencia TrainingPeaks / literatura ──────────────────────────"""

if old1 in content:
    content = content.replace(old1, new1)
    print("OK 1 - helper _read_sql agregado en noa_estados.py")
else:
    print("ERROR 1 - no matcheo el anchor")

count = content.count('pd.read_sql(')
content = content.replace('pd.read_sql(', '_read_sql(')
print(f"OK 2 - {count} llamadas pd.read_sql reemplazadas en noa_estados.py")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("GUARDADO OK - noa_estados.py actualizado")
