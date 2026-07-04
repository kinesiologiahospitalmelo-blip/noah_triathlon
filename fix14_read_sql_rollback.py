import os

archivos = [
    r'C:\Users\Win10\Desktop\noah_cloud\noa_estados.py',
    r'C:\Users\Win10\Desktop\noah_cloud\noa_db.py',
    r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py',
]

helper_viejo = """def _read_sql(sql, conn, params=None):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)"""

helper_nuevo = """def _read_sql(sql, conn, params=None):
    import pandas as pd
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
    except Exception:
        # Transaccion abortada por error previo — hacer rollback y reintentar
        try:
            conn.rollback()
        except Exception:
            pass
        cur = conn.cursor()
        cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)"""

for path in archivos:
    if not os.path.exists(path):
        print(f"SKIP - no existe: {path}")
        continue
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if helper_viejo in content:
        content = content.replace(helper_viejo, helper_nuevo)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"OK - {os.path.basename(path)} actualizado")
    elif helper_nuevo in content:
        print(f"-- {os.path.basename(path)} ya tiene la version nueva, skip")
    else:
        print(f"ERROR - no matcheo helper en {os.path.basename(path)}")
