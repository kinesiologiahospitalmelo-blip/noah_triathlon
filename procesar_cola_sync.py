"""
procesar_cola_sync.py - Proyecto NOAH
========================================
Este archivo se perdio durante la reorganizacion del repo (nunca llego a
subirse a GitHub) -- por eso el GitHub Action "Procesar cola de
sincronizacion NOAH" fallaba con "No such file or directory".

Que hace: lee la tabla `sync_log` (la misma que ya escribe el endpoint
POST /api/atletas/<id>/sincronizar en app.py con status='pendiente'), y
por cada pedido pendiente llama a sincronizar_garmin.py como subproceso
-- EXACTAMENTE igual a como Rodrigo ya lo corre a mano en su terminal
(python sincronizar_garmin.py --atleta X --modo Y). No reimplementa nada
de la logica interna de sincronizar_garmin.py, para no arriesgar romper
lo que ya funciona.

Requiere la variable de entorno DATABASE_URL (la misma que usa app.py y
sincronizar_garmin.py). En GitHub Actions ya viene del secret
DATABASE_URL definido en el workflow.

USO:
    python procesar_cola_sync.py
"""

import os
import sys
import subprocess
from datetime import datetime, timedelta

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    print("Falta psycopg2. Instalar con: pip install psycopg2-binary")
    sys.exit(1)

TIMEOUT_SEG = 280          # tope por atleta (el job entero de GH Actions tiene mucho mas margen)
MAX_DETALLE = 2000         # no guardar logs gigantes en sync_log.detalle


def get_conn():
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print('Falta la variable de entorno DATABASE_URL.')
        sys.exit(1)
    return psycopg2.connect(db_url, cursor_factory=psycopg2.extras.DictCursor)


def asegurar_tabla(conn):
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sync_log
        (id SERIAL PRIMARY KEY, atleta_id INTEGER, ts TEXT,
         modo TEXT, status TEXT, detalle TEXT)""")
    conn.commit()


def marcar(conn, row_id, status, detalle=''):
    cur = conn.cursor()
    cur.execute(
        "UPDATE sync_log SET status=%s, detalle=%s WHERE id=%s",
        (status, (detalle or '')[:MAX_DETALLE], row_id)
    )
    conn.commit()


def procesar_pendientes(conn):
    cur = conn.cursor()
    cur.execute(
        "SELECT id, atleta_id, modo FROM sync_log WHERE status='pendiente' ORDER BY id"
    )
    pendientes = cur.fetchall()

    if not pendientes:
        print('[INFO] No hay pedidos pendientes en sync_log.')
        return

    print(f'[INFO] {len(pendientes)} pedido(s) pendiente(s) a procesar.')

    for row in pendientes:
        row_id, atleta_id, modo = row['id'], row['atleta_id'], row['modo'] or 'todo'
        print(f'  -> Procesando id={row_id} atleta_id={atleta_id} modo={modo} ...')
        marcar(conn, row_id, 'procesando')

        cmd = [sys.executable, 'sincronizar_garmin.py',
               '--atleta', str(atleta_id), '--modo', modo]

        try:
            resultado = subprocess.run(
                cmd, capture_output=True, text=True, timeout=TIMEOUT_SEG,
                env=os.environ.copy()
            )
            salida = (resultado.stdout or '') + (resultado.stderr or '')
            if resultado.returncode == 0:
                marcar(conn, row_id, 'completado', salida)
                print(f'     [OK] atleta_id={atleta_id}')
            else:
                marcar(conn, row_id, 'error', salida)
                print(f'     [ERROR] atleta_id={atleta_id} (returncode {resultado.returncode})')

        except subprocess.TimeoutExpired:
            marcar(conn, row_id, 'error', f'Timeout despues de {TIMEOUT_SEG}s')
            print(f'     [ERROR] atleta_id={atleta_id} -- timeout')
        except Exception as e:
            marcar(conn, row_id, 'error', str(e))
            print(f'     [ERROR] atleta_id={atleta_id} -- {e}')


def limpiar_viejos(conn, dias=7):
    """Borra registros de sync_log completados/con error de hace mas de N dias
    (housekeeping simple, para que la tabla no crezca sin limite)."""
    cur = conn.cursor()
    limite = (datetime.now() - timedelta(days=dias)).isoformat()
    cur.execute(
        "DELETE FROM sync_log WHERE status IN ('completado','error') AND ts < %s",
        (limite,)
    )
    conn.commit()


def main():
    conn = get_conn()
    try:
        asegurar_tabla(conn)
        procesar_pendientes(conn)
        limpiar_viejos(conn)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
