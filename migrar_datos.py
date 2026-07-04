"""
migrar_datos.py — Copia los datos reales de noa.db (SQLite) a Supabase (Postgres)
====================================================================================
Migra el contenido de todas las tablas, preservando los IDs originales para
no romper las relaciones entre tablas (foreign keys: sesiones.atleta_id,
laps.sesion_id, etc).

NO TOCA estas 2 tablas — ya tienen datos creados directo en Supabase
(usuario coach + atletas) y no queremos perderlos ni duplicarlos:
  - usuarios_login
  - sesiones_login

CÓMO USAR:
  1. Asegurate de tener la variable de entorno DATABASE_URL configurada
     (la misma cadena del pooler que usás en Vercel/crear_usuarios.py).
     En PowerShell:
       $env:DATABASE_URL = "postgresql://postgres.xxxxx:clave@aws-1-...pooler.supabase.com:6543/postgres"
  2. Copiá noa.db a la misma carpeta que este script (o pasá la ruta con --db)
  3. python migrar_datos.py

Es seguro correrlo más de una vez: usa "ON CONFLICT DO NOTHING" sobre la
clave primaria de cada tabla, así que si una fila ya existe, simplemente
la salta en vez de duplicarla o fallar.
"""

import sqlite3
import psycopg2
import psycopg2.extras
import os
import sys
import argparse


TABLAS_A_OMITIR = {'usuarios_login', 'sesiones_login', 'sqlite_sequence'}

# Orden de migración: las tablas sin dependencias primero, las que
# referencian a otras (FOREIGN KEY) después — para que la fila "padre"
# ya exista cuando se inserta la fila "hija".
ORDEN_TABLAS = [
    'atletas',
    'perfiles_macro',
    'carreras',
    'carreras_historicas',
    'prescripciones',
    'prescripcion_bloques',
    'sesiones',
    'laps',
    'sleep_hrv',
    'activities',
    'activity_samples',
    'fc_intradiaria',
    'garmin_performance',
    'sync_log',
    'noah_feedback',
    'ml_modelos',
    'noah_optimizer',
    'atleta_clustering',
    'atleta_baseline',
    'tests_umbral',
    'variantes_sesion',
]


def conectar_sqlite(ruta_db):
    conn = sqlite3.connect(ruta_db)
    conn.row_factory = sqlite3.Row
    return conn


def conectar_postgres(database_url):
    return psycopg2.connect(database_url)


def columnas_postgres(conn_pg, tabla):
    """Devuelve el set de columnas reales que existen en la tabla Postgres,
    para no intentar insertar una columna que no existe ahí (por si el
    esquema real difiere levemente del de SQLite)."""
    cur = conn_pg.cursor()
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=%s",
        (tabla,)
    )
    return {r[0] for r in cur.fetchall()}


# Clave primaria / restricción única de cada tabla — fija y conocida (viene
# del esquema real que ya se creó en Supabase), en vez de detectarla en
# tiempo de ejecución (que fallaba de forma intermitente en pruebas reales).
PK_POR_TABLA = {
    'atletas': ['id'],
    'perfiles_macro': ['id'],
    'carreras': ['id'],
    'carreras_historicas': ['id'],
    'prescripciones': ['id'],
    'prescripcion_bloques': ['id'],
    'sesiones': ['id'],
    'laps': ['id'],
    'sleep_hrv': ['id'],
    'activities': ['id'],
    'activity_samples': ['id'],
    'fc_intradiaria': ['id'],
    'garmin_performance': ['id'],
    'sync_log': ['id'],
    'noah_feedback': ['id'],
    'ml_modelos': ['id'],
    'noah_optimizer': ['atleta_id'],
    'atleta_clustering': ['id'],
    'atleta_baseline': ['id'],
    'tests_umbral': ['id'],
    'variantes_sesion': ['id'],
}


def clave_primaria_postgres(conn_pg, tabla):
    return PK_POR_TABLA.get(tabla)


def migrar_tabla(conn_sqlite, conn_pg, tabla):
    cols_pg = columnas_postgres(conn_pg, tabla)
    if not cols_pg:
        print(f"  [SKIP] {tabla}: no existe en Postgres (¿esquema no creado?)")
        return 0

    rows = conn_sqlite.execute(f"SELECT * FROM {tabla}").fetchall()
    if not rows:
        print(f"  [OK] {tabla}: 0 filas en origen, nada para migrar")
        return 0

    cols_fila = [c for c in rows[0].keys() if c in cols_pg]
    if not cols_fila:
        print(f"  [SKIP] {tabla}: ninguna columna coincide con Postgres")
        return 0

    pk_cols = clave_primaria_postgres(conn_pg, tabla)
    placeholders = ','.join(['%s'] * len(cols_fila))
    cols_str = ','.join(cols_fila)

    if pk_cols:
        conflict_cols = ','.join(c for c in pk_cols if c in cols_fila)
        sql = (f"INSERT INTO {tabla} ({cols_str}) VALUES ({placeholders}) "
               f"ON CONFLICT ({conflict_cols}) DO NOTHING") if conflict_cols else \
              f"INSERT INTO {tabla} ({cols_str}) VALUES ({placeholders})"
    else:
        sql = f"INSERT INTO {tabla} ({cols_str}) VALUES ({placeholders})"

    cur = conn_pg.cursor()
    insertados = 0
    errores = 0
    total = len(rows)

    # Para tablas grandes (>5000 filas), insertar en lotes con
    # execute_batch en vez de fila por fila — mucho más rápido y evita
    # agotar la conexión con decenas de miles de viajes de ida y vuelta
    # individuales (lo que causó "server closed the connection
    # unexpectedly" en activity_samples con 85.000+ filas).
    if total > 5000:
        import psycopg2.extras
        TAM_LOTE = 1000
        for inicio in range(0, total, TAM_LOTE):
            lote = rows[inicio:inicio + TAM_LOTE]
            valores_lote = [[row[c] for c in cols_fila] for row in lote]
            try:
                psycopg2.extras.execute_batch(cur, sql, valores_lote, page_size=TAM_LOTE)
                insertados += len(lote)
            except (psycopg2.InterfaceError, psycopg2.OperationalError):
                # Conexión real cortada (no es un error de datos) — se
                # relanza para que main() reconecte y reintente la tabla
                # completa desde el principio (las filas ya insertadas no
                # se duplican gracias a ON CONFLICT DO NOTHING).
                raise
            except Exception as e:
                # Error de DATOS (ej: foreign key huérfana), no de conexión.
                # Reintentar fila por fila ese lote puntual para no perder
                # el resto del lote por una sola fila mala.
                for row in lote:
                    valores = [row[c] for c in cols_fila]
                    try:
                        cur.execute(sql, valores)
                        insertados += 1
                    except (psycopg2.InterfaceError, psycopg2.OperationalError):
                        raise
                    except Exception as e2:
                        errores += 1
                        if errores <= 3:
                            print(f"    [ERROR fila] {tabla}: {e2}")
            print(f"    ... {tabla}: {min(inicio+TAM_LOTE, total)}/{total} procesadas")
    else:
        for i, row in enumerate(rows, 1):
            valores = [row[c] for c in cols_fila]
            try:
                cur.execute(sql, valores)
                insertados += 1
            except (psycopg2.InterfaceError, psycopg2.OperationalError):
                raise
            except Exception as e:
                errores += 1
                if errores <= 3:
                    print(f"    [ERROR fila] {tabla}: {e}")
                continue
            if i % 2000 == 0:
                print(f"    ... {tabla}: {i}/{total} procesadas")

    # Reiniciar la secuencia de auto-incremento (SERIAL/IDENTITY) para que
    # el próximo INSERT sin id explícito no choque con los ids migrados.
    if pk_cols and len(pk_cols) == 1 and pk_cols[0] in cols_fila:
        try:
            cur.execute(
                f"SELECT setval(pg_get_serial_sequence('{tabla}', %s), "
                f"COALESCE((SELECT MAX({pk_cols[0]}) FROM {tabla}), 1))",
                (pk_cols[0],)
            )
        except Exception:
            pass  # la tabla puede no tener secuencia (ej: clave natural)

    print(f"  [OK] {tabla}: {insertados} filas migradas"
          + (f", {errores} con error" if errores else ""))
    return insertados


def main():
    ap = argparse.ArgumentParser(description='Migrar datos de noa.db a Supabase')
    ap.add_argument('--db', default='noa.db', help='Ruta al archivo noa.db (default: noa.db en esta carpeta)')
    args = ap.parse_args()

    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("ERROR: falta la variable de entorno DATABASE_URL.")
        print('Definila antes de correr este script, por ejemplo en PowerShell:')
        print('  $env:DATABASE_URL = "postgresql://usuario:clave@host:puerto/basededatos"')
        sys.exit(1)

    if not os.path.exists(args.db):
        print(f"ERROR: no se encontró el archivo {args.db}")
        sys.exit(1)

    print("=" * 60)
    print("  Migración noa.db → Supabase")
    print("=" * 60)
    print(f"  Origen: {args.db}")
    print(f"  Destino: {db_url.split('@')[-1] if '@' in db_url else '(oculto)'}")
    print()
    print("  NOTA: usuarios_login y sesiones_login NO se migran — ya tienen")
    print("  datos creados directo en Supabase y no se van a tocar.")
    print("=" * 60)

    conn_sqlite = conectar_sqlite(args.db)

    def nueva_conexion_pg():
        c = conectar_postgres(db_url)
        c.autocommit = True
        return c

    conn_pg = nueva_conexion_pg()

    total = 0
    for tabla in ORDEN_TABLAS:
        if tabla in TABLAS_A_OMITIR:
            continue
        # Reintenta la tabla hasta 3 veces si la conexión se cae a mitad
        # de camino (límite del plan gratuito de Supabase tras uso
        # prolongado) — reconecta sola, sin que haga falta volver a
        # correr el script a mano cada vez que se corta.
        intentos = 0
        while intentos < 3:
            try:
                total += migrar_tabla(conn_sqlite, conn_pg, tabla)
                break
            except (psycopg2.InterfaceError, psycopg2.OperationalError) as e:
                intentos += 1
                print(f"    [RECONECTANDO] {tabla}: conexión perdida ({e}). Intento {intentos}/3...")
                try:
                    conn_pg.close()
                except Exception:
                    pass
                conn_pg = nueva_conexion_pg()
        else:
            print(f"  [FALLO DEFINITIVO] {tabla}: no se pudo migrar tras 3 intentos")

    conn_sqlite.close()
    conn_pg.close()

    print("=" * 60)
    print(f"  Migración completada: {total} filas en total")
    print("=" * 60)


if __name__ == '__main__':
    main()
