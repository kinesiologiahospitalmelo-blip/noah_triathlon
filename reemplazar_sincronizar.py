import re

path = r"C:\Users\Win10\Desktop\noah_cloud\app.py"

with open(path, "r", encoding="utf-8") as f:
    contenido = f.read()

nuevo_endpoint = '''@app.route('/api/atletas/<int:atleta_id>/sincronizar', methods=['POST'])
@requiere_login
def sincronizar_garmin_endpoint(atleta_id):
    """
    Encola un pedido de sincronizacion con Garmin. NO ejecuta nada pesado
    aca (Vercel no soporta procesos largos / subprocess) - solo anota el
    pedido en sync_log con status='pendiente'. Un GitHub Action separado
    revisa esta tabla cada pocos minutos y hace el trabajo real llamando
    a sincronizar_garmin.py.
    """
    datos = request.json or {}
    modo  = datos.get('modo', 'todo')

    conn = get_conn()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS sync_log
            (id SERIAL PRIMARY KEY, atleta_id INTEGER, ts TEXT,
             modo TEXT, status TEXT, detalle TEXT)""")

        ya_pendiente = conn.execute(
            "SELECT id FROM sync_log WHERE atleta_id=%s AND status='pendiente' "
            "ORDER BY id DESC LIMIT 1", (atleta_id,)
        ).fetchone()

        if ya_pendiente:
            conn.close()
            return ok({'exito': True, 'estado': 'ya_pendiente',
                       'mensaje': 'Ya hay una sincronizacion en curso para este atleta.'})

        conn.execute(
            'INSERT INTO sync_log (atleta_id, ts, modo, status, detalle) VALUES (%s,%s,%s,%s,%s)',
            (atleta_id, datetime.now().isoformat(), modo, 'pendiente', '')
        )
        conn.commit()
    finally:
        conn.close()

    return ok({'exito': True, 'estado': 'pendiente',
                'mensaje': 'Sincronizacion solicitada. Puede tardar unos minutos.'})
'''

patron = re.compile(
    r"@app\.route\('/api/atletas/<int:atleta_id>/sincronizar', methods=\['POST'\]\).*?return ok\(_limpiar_nan\(resp\)\)\n",
    re.DOTALL
)

contenido_nuevo, n = patron.subn(nuevo_endpoint, contenido, count=1)

if n == 0:
    print("ERROR: no se encontro el patron a reemplazar. No se modifico el archivo.")
else:
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenido_nuevo)
    print(f"OK: reemplazos hechos = {n}")
