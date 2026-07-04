path = r'C:\Users\Win10\Desktop\noah_cloud\noa_db.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Agregar helper _read_sql despues de los imports ──────────────────────
old1 = "# ─── CONFIGURACION ────────────────────────────────────────────────────────────"

new1 = """# ─── Helper pd.read_sql → _read_sql (pandas 2.x no soporta DBAPI2 directo) ────

def _read_sql(sql, conn, params=None):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ─── CONFIGURACION ────────────────────────────────────────────────────────────"""

if old1 in content:
    content = content.replace(old1, new1)
    print("OK 1 - helper _read_sql agregado en noa_db.py")
else:
    print("ERROR 1 - no matcheo el anchor")

# ── 2. Reemplazar todas las llamadas pd.read_sql por _read_sql ───────────────
count = content.count('pd.read_sql(')
content = content.replace('pd.read_sql(', '_read_sql(')
print(f"OK 2 - {count} llamadas pd.read_sql reemplazadas en noa_db.py")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("GUARDADO OK - noa_db.py actualizado")
