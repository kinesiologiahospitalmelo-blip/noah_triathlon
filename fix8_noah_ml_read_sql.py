path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# ── 1. Agregar helper _read_sql despues de _safe_float ──────────────────────
old1 = """# ── Dataset builder ───────────────────────────────────────────────────────────
def construir_dataset(conn, atleta_id: int) -> pd.DataFrame:"""

new1 = """def _read_sql(sql, conn, params=None):
    \"\"\"
    Reemplazo de pd.read_sql() para conexiones psycopg2 directas.
    pandas 2.x depreco DBAPI2 en read_sql — usamos cursor directamente.
    \"\"\"
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)


# ── Dataset builder ───────────────────────────────────────────────────────────
def construir_dataset(conn, atleta_id: int) -> pd.DataFrame:"""

if old1 in content:
    content = content.replace(old1, new1)
    print("OK 1 - helper _read_sql agregado")
else:
    print("ERROR 1 - no matcheo el anchor para helper")

# ── 2. Reemplazar todas las llamadas pd.read_sql por _read_sql ───────────────
import re
count = content.count('pd.read_sql(')
content = content.replace('pd.read_sql(', '_read_sql(')
print(f"OK 2 - {count} llamadas pd.read_sql reemplazadas por _read_sql")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("GUARDADO OK - noah_ml.py actualizado")
