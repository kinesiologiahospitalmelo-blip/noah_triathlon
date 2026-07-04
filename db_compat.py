"""
db_compat.py — Helpers de compatibilidad para la migración SQLite → Postgres
==============================================================================
Este módulo existe porque varios archivos (noa_db.py, noah_hanna_life.py)
tenían el patrón "verificar si una columna existe en una tabla y agregarla
si falta" usando sintaxis específica de SQLite (PRAGMA table_info + ALTER
TABLE). Postgres no tiene PRAGMA — el equivalente es consultar
information_schema.columns.

En vez de traducir esa lógica por separado en cada archivo (con riesgo de
que quedaran ligeramente distintas entre sí), se centraliza aquí UNA sola
vez, verificada, y los demás archivos la importan.

No cambia ningún comportamiento: el resultado final (la tabla terminando
con las columnas que se pidieron) es exactamente el mismo que con el
código SQLite original.
"""


class _ResultadoExecute:
    """
    Envuelve el cursor psycopg2 que devuelve conn.execute(), para que el
    resultado se comporte como el de sqlite3 (que devuelve directamente
    un objeto con .fetchone()/.fetchall()). psycopg2 en realidad ya
    soporta fetchone()/fetchall() en el cursor mismo, así que este
    envoltorio es simplemente "ser" ese cursor — existe sobre todo para
    dejar documentado el punto de contacto entre ambas APIs.
    """
    def __init__(self, cursor):
        self._cursor = cursor

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    @property
    def rowcount(self):
        return self._cursor.rowcount


class ConexionCompat:
    """
    Wrapper alrededor de una conexión psycopg2 (Postgres) que agrega un
    método .execute() directo sobre la conexión — el mismo atajo que
    sqlite3.Connection ofrecía de fábrica y que psycopg2 NO tiene (en
    psycopg2 hay que pasar siempre por connection.cursor().execute()).

    Por qué existe: el código de la app (app.py, noa_db.py,
    noah_hanna_life.py, patrones_sesion.py) fue escrito asumiendo
    conn.execute(...) en cientos de lugares. Reescribir cada uno a
    conn.cursor().execute(...) sería un cambio mecánico repetido con
    mucha superficie para errores de copiado. Este wrapper deja ese
    código de llamada EXACTAMENTE IGUAL — sólo cambia qué objeto es
    `conn` al conectar (ver get_conn() en app.py).

    Crea un cursor nuevo en cada .execute() (igual que sqlite3 hace
    internamente con su atajo), por lo que el patrón de uso
    "conn.execute(...).fetchone()" sigue funcionando sin cambios.
    """
    def __init__(self, psycopg2_conn):
        self._conn = psycopg2_conn

    def execute(self, query, params=None):
        cur = self._conn.cursor()
        cur.execute(query, params)
        return _ResultadoExecute(cur)

    def cursor(self):
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Mejora deliberada respecto al comportamiento original: el código
        # con SQLite (with sqlite3.connect(...) as conn:) solo hacía
        # commit/rollback al salir del 'with', pero NUNCA cerraba la
        # conexión explícitamente — confiaba en que el recolector de
        # basura de Python la liberase eventualmente. Eso es aceptable
        # con SQLite (conexiones livianas, sin límite real) pero NO es
        # seguro con Postgres/Supabase, que tiene un límite bajo de
        # conexiones simultáneas en el plan gratuito. Por eso aquí SÍ se
        # cierra la conexión real al salir del bloque 'with' — el código
        # que llama a estos métodos (with self._conn() as conn: ...) no
        # necesita cambiar nada, sigue funcionando igual.
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def columnas_de_tabla(conn, tabla: str) -> list[str]:
    """
    Devuelve la lista de nombres de columna de `tabla`. Equivalente Postgres de:

        cols = [r[1] for r in conn.execute('PRAGMA table_info(tabla)').fetchall()]

    Usado en los lugares donde el código original solo necesitaba SABER
    qué columnas existen (para construir un INSERT/UPDATE dinámico), sin
    necesidad de agregar ninguna — a diferencia de asegurar_columnas(),
    que además crea las que falten.
    """
    rows = conn.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position
        """,
        (tabla,)
    ).fetchall()
    return [r[0] for r in rows]


def asegurar_columnas(conn, tabla: str, columnas: list[tuple[str, str]]):
    """
    Verifica que `tabla` tenga todas las columnas pedidas; agrega las que
    falten. Equivalente Postgres de:

        cols = {r[1] for r in conn.execute('PRAGMA table_info(tabla)').fetchall()}
        for col, tipo in columnas:
            if col not in cols:
                conn.execute(f'ALTER TABLE tabla ADD COLUMN {col} {tipo}')

    Parámetros
    ----------
    conn : conexión psycopg (o cualquier conexión DB-API con .execute()
           que acepte placeholders %s)
    tabla : nombre de la tabla a revisar
    columnas : lista de tuplas (nombre_columna, tipo_sql). Los tipos deben
               ser válidos en Postgres — ver mapeo de tipos en MIGRACION.md
               (REAL→DOUBLE PRECISION, INTEGER→INTEGER, TEXT→TEXT siguen
               funcionando igual en Postgres, así que la mayoría de los
               tipos usados en este proyecto no necesitan cambio).
    """
    existentes = {
        row[0] for row in conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (tabla,)
        ).fetchall()
    }
    for col, tipo in columnas:
        if col not in existentes:
            # Nombres de tabla/columna no pueden parametrizarse con %s en DDL
            # (no son valores, son identificadores) — se interpolan directo.
            # Son siempre nombres fijos definidos en el propio código de la
            # app (nunca vienen de input de usuario), así que no hay riesgo
            # de inyección SQL acá.
            conn.execute(f'ALTER TABLE {tabla} ADD COLUMN {col} {tipo}')
