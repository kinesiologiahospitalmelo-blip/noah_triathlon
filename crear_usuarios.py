"""
crear_usuarios.py — Crear usuarios de login (coach y atletas)
================================================================
COMO USAR:
1. Asegurate de tener la variable de entorno DATABASE_URL configurada
   (la cadena de conexión a tu base Postgres/Supabase) — en tu PC podés
   definirla antes de correr el script, por ejemplo en PowerShell:
     $env:DATABASE_URL="postgresql://usuario:clave@host:puerto/basededatos"
2. Copiá este archivo en la misma carpeta donde está app.py
3. Abrí PowerShell en esa carpeta
4. Escribí: python crear_usuarios.py
5. Seguí las instrucciones que aparecen en pantalla

No hace falta tocar nada de app.py ni usar Postman.
"""

import psycopg2
import hashlib
import secrets
import os
import sys
from datetime import datetime, timezone
from db_compat import ConexionCompat

DB_URL = os.environ.get('DATABASE_URL', '')


def get_conn():
    if not DB_URL:
        print("ERROR: falta la variable de entorno DATABASE_URL "
              "(cadena de conexión a Postgres/Supabase). Definila antes de correr este script.")
        sys.exit(1)
    return ConexionCompat(psycopg2.connect(DB_URL))


def hash_password(password, salt):
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()


def init_tablas():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios_login (
            atleta_id     INTEGER UNIQUE,
            usuario       TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            rol           TEXT NOT NULL DEFAULT 'atleta',
            creado        TEXT NOT NULL,
            activo        INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sesiones_login (
            token      TEXT PRIMARY KEY,
            atleta_id  INTEGER,
            rol        TEXT NOT NULL DEFAULT 'atleta',
            creado     TEXT NOT NULL,
            expira     TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def listar_atletas():
    conn = get_conn()
    try:
        rows = conn.execute("SELECT id, nombre FROM atletas ORDER BY id").fetchall()
    except psycopg2.Error:
        rows = []
    conn.close()
    return rows


def crear_usuario(atleta_id, usuario, password, rol='atleta'):
    salt = secrets.token_hex(16)
    password_hash = hash_password(password, salt)
    ahora = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO usuarios_login (atleta_id, usuario, password_hash, salt, rol, creado, activo)
            VALUES (%s,%s,%s,%s,%s,%s,1)
            ON CONFLICT(atleta_id) DO UPDATE SET
                usuario=excluded.usuario,
                password_hash=excluded.password_hash,
                salt=excluded.salt
        """, (atleta_id, usuario, password_hash, salt, rol, ahora))
        conn.commit()
        return True, None
    except psycopg2.IntegrityError as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("  NOAH — Crear usuarios de login")
    print("=" * 60)
    init_tablas()

    conn = get_conn()
    ya_hay_coach = conn.execute(
        "SELECT COUNT(*) FROM usuarios_login WHERE rol='coach'"
    ).fetchone()[0]
    conn.close()

    # ── 1. Usuario del coach (solo si todavía no existe) ────────────────────
    if ya_hay_coach == 0:
        print("\n--- Crear usuario del COACH ---")
        usuario = input("Usuario para el coach (ej: coach): ").strip()
        password = input("Contraseña para el coach: ").strip()
        if usuario and len(password) >= 4:
            ok, err = crear_usuario(None, usuario, password, rol='coach')
            if ok:
                print(f"✓ Usuario coach '{usuario}' creado correctamente.")
            else:
                print(f"✗ Error: {err}")
        else:
            print("✗ Usuario o contraseña inválidos (contraseña mínimo 4 caracteres). Saltado.")
    else:
        print("\nYa existe un usuario coach, no se crea otro.")

    # ── 2. Usuarios de atletas ───────────────────────────────────────────────
    while True:
        print("\n--- Crear usuario de un ATLETA ---")
        atletas = listar_atletas()
        if atletas:
            print("Atletas disponibles:")
            for aid, nombre in atletas:
                print(f"   {aid} - {nombre}")
        else:
            print("(No se encontraron atletas en la tabla 'atletas' — fijate el ID a mano)")

        atleta_id_str = input("\nID del atleta (Enter para terminar): ").strip()
        if not atleta_id_str:
            break
        try:
            atleta_id = int(atleta_id_str)
        except ValueError:
            print("✗ Eso no es un número válido.")
            continue

        usuario = input("Usuario para este atleta: ").strip()
        password = input("Contraseña para este atleta: ").strip()
        if not usuario or len(password) < 4:
            print("✗ Usuario o contraseña inválidos (contraseña mínimo 4 caracteres).")
            continue

        ok, err = crear_usuario(atleta_id, usuario, password, rol='atleta')
        if ok:
            print(f"✓ Usuario '{usuario}' creado para el atleta {atleta_id}.")
        else:
            print(f"✗ Error: {err}")

    print("\nListo. Cerrando.")


if __name__ == '__main__':
    main()
