path = r'C:\Users\Win10\Desktop\noah_cloud\noah_ml.py'

old = '''def _read_sql(sql, conn, params=None):
    """
    Reemplazo de _read_sql() para conexiones psycopg2 directas.
    pandas 2.x depreco DBAPI2 en read_sql — usamos cursor directamente.
    """
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)'''

new = '''def _read_sql(sql, conn, params=None):
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        cur = conn.cursor()
        cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)'''

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

if old in content:
    content = content.replace(old, new)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("OK - noah_ml.py actualizado con rollback resilience")
else:
    print("ERROR - no matcheo")
