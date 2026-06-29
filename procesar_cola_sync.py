"""
procesar_cola_sync.py
----------------------
Corre dentro de GitHub Actions. Busca pedidos 'pendiente' en sync_log,
ejecuta sincronizar_garmin.py para cada atleta pendiente, y marca el
resultado (ok / error) en la misma tabla.
"""
import os
import sys
import subprocess
import psycopg2
import psycopg2.extras
from datetime import datetime

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('Falta DATABASE_URL')
    sys.exit(1)

conn = psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)
conn.autocommit = True
cur = conn.cursor()

cur.execute("SELECT id, atleta_id, modo FROM sync_log WHERE status='pendiente' ORDER BY id")
pendientes = cur.fetchall()

if not pendientes:
    print('Sin pedidos pendientes.')
    sys.exit(0)

print(f'Pedidos pendientes: {len(pendientes)}')

for row in pendientes:
    log_id, atleta_id, modo = row['id'], row['atleta_id'], row['modo'] or 'todo'
    print(f'\n--- Procesando atleta {atleta_id} (modo={modo}, log_id={log_id}) ---')

    # Marcar como 'en_proceso' para que no se vuelva a tomar si el job
    # de Actions corre de nuevo antes de terminar este.
    cur.execute("UPDATE sync_log SET status='en_proceso' WHERE id=%s", (log_id,))

    try:
        resultado = subprocess.run(
            [sys.executable, 'sincronizar_garmin.py',
             '--atleta', str(atleta_id), '--modo', modo],
            capture_output=True, text=True, timeout=900  # 15 min margen
        )
        ok = resultado.returncode == 0
        detalle = (resultado.stdout[-800:] + resultado.stderr[-400:])
    except subprocess.TimeoutExpired:
        ok = False
        detalle = 'timeout (15 min)'
    except Exception as e:
        ok = False
        detalle = str(e)

    nuevo_status = 'ok' if ok else 'error'
    cur.execute(
        "UPDATE sync_log SET status=%s, detalle=%s, ts=%s WHERE id=%s",
        (nuevo_status, detalle, datetime.now().isoformat(), log_id)
    )
    print(f'  Resultado: {nuevo_status}')

conn.close()
print('\nCola procesada.')
