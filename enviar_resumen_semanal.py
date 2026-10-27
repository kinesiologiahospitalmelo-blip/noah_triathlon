# -*- coding: utf-8 -*-
"""
enviar_resumen_semanal.py — manda el resumen de la semana a CADA atleta por mail.

A PRUEBA DE CORTES (self-healing), igual que el sync de Garmin:
- Idempotente por atleta y por semana ISO: si ya se envio OK esta semana, NO repite.
- Catch-up: si el lunes GitHub Actions no disparo (o fallo), al correr CUALQUIER
  otro dia de la misma semana ISO lo COMPLETA — manda solo lo que falto.
- Reintentos por atleta ante fallo transitorio de SMTP (3 intentos).
- Si corta a mitad (p.ej. mando 6 de 10 y se cae), la proxima corrida manda
  solo los 4 que faltan. Deja registro en la tabla envios_resumen.

POR ESO EL WORKFLOW DEBE CORRER TODOS LOS DIAS (no solo el lunes): el primer dia
de la semana que logre correr envia; los dias siguientes no repiten lo ya enviado.
Asi, aunque GitHub se saltee el cron del lunes, el martes/miercoles lo completa.

Requiere en el entorno: DATABASE_URL, GMAIL_USER, GMAIL_APP_PASSWORD

Uso:
    python enviar_resumen_semanal.py            # manda lo que falte de ESTA semana
    python enviar_resumen_semanal.py --dry      # NO envia, solo muestra que haria
    python enviar_resumen_semanal.py --prueba TU_MAIL   # 1 de prueba a TU_MAIL (ignora registro)
    python enviar_resumen_semanal.py --forzar   # reenvia aunque ya figure enviado
"""
import os, sys, time, datetime
import psycopg2, psycopg2.extras

REINTENTOS_SMTP = 3          # por atleta, ante fallo transitorio
ESPERA_SMTP     = 8          # segundos entre reintentos


def _semana_clave(hoy=None):
    """Clave de la semana ISO en curso, p.ej. '2026-W44'. Lun..Dom comparten clave,
    por eso corriendo a diario solo el primer dia logrado envia."""
    hoy = hoy or datetime.date.today()
    iso = hoy.isocalendar()           # (anio, semana, dia)
    return f"{iso[0]}-W{iso[1]:02d}"


def _asegurar_tabla(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS envios_resumen (
            atleta_id  INTEGER NOT NULL,
            semana     TEXT    NOT NULL,
            estado     TEXT,            -- 'ok' | 'fallo' | 'sin_datos' | 'sin_email'
            intentos   INTEGER DEFAULT 0,
            detalle    TEXT,
            fecha      TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (atleta_id, semana)
        )""")
    conn.commit()


def _ya_enviado(conn, aid, semana):
    row = conn.execute(
        "SELECT estado FROM envios_resumen WHERE atleta_id=%s AND semana=%s",
        (aid, semana)
    ).fetchone()
    if not row:
        return False
    estado = row[0] if not hasattr(row, 'keys') else row['estado']
    return estado == 'ok'


def _registrar(conn, aid, semana, estado, detalle=''):
    conn.execute("""
        INSERT INTO envios_resumen (atleta_id, semana, estado, intentos, detalle, fecha)
        VALUES (%s, %s, %s, 1, %s, NOW())
        ON CONFLICT (atleta_id, semana) DO UPDATE SET
            estado   = EXCLUDED.estado,
            intentos = envios_resumen.intentos + 1,
            detalle  = EXCLUDED.detalle,
            fecha    = NOW()
    """, (aid, semana, estado, (detalle or '')[:300]))
    conn.commit()


def main():
    dsn = os.environ.get('DATABASE_URL', '')
    if not dsn:
        print('ERROR: falta DATABASE_URL en el entorno.'); sys.exit(1)

    dry       = '--dry' in sys.argv
    forzar    = '--forzar' in sys.argv
    prueba_to = None
    if '--prueba' in sys.argv:
        i = sys.argv.index('--prueba')
        prueba_to = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

    from noah_resumen_semanal import construir_resumen, render_html
    from noah_email import enviar_mail
    from db_compat import ConexionCompat

    raw  = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.DictCursor)
    conn = ConexionCompat(raw)

    semana    = _semana_clave()
    es_prueba = bool(prueba_to)
    if not es_prueba:
        _asegurar_tabla(conn)

    atletas = conn.execute("SELECT id, nombre FROM atletas ORDER BY id").fetchall()
    print(f'Semana {semana} · Atletas: {len(atletas)}')
    enviados = fallos = salteados = 0

    for a in atletas:
        aid = a[0] if not hasattr(a, 'keys') else a['id']

        # idempotencia / catch-up (salvo prueba o --forzar)
        if not es_prueba and not forzar and _ya_enviado(conn, aid, semana):
            salteados += 1
            continue

        res = construir_resumen(conn, aid)
        if not res:
            print(f'  #{aid}: sin datos, salteo')
            if not es_prueba:
                _registrar(conn, aid, semana, 'sin_datos')
            continue

        destino = prueba_to or res.get('email')
        asunto  = f"Tu semana en NOAH — {res['nombre']} ({res['tss_total']} TSS, {res['horas']}h)"

        if dry:
            ya = '' if es_prueba else (' [YA ENVIADO]' if _ya_enviado(conn, aid, semana) else '')
            print(f"  #{aid} {res['nombre']}: iria a {destino} · TSS {res['tss_total']} · "
                  f"{len(res['alertas'])} alertas{ya}")
            continue

        if not destino:
            print(f"  #{aid} {res['nombre']}: SIN email, salteo")
            if not es_prueba:
                _registrar(conn, aid, semana, 'sin_email')
            fallos += 1
            continue

        if prueba_to:
            asunto = '[PRUEBA] ' + asunto
        html = render_html(res)

        # reintentos ante fallo transitorio de SMTP
        ok = False; det = ''
        for intento in range(1, REINTENTOS_SMTP + 1):
            ok, det = enviar_mail(destino, asunto, html)
            if ok:
                break
            if intento < REINTENTOS_SMTP:
                print(f"    #{aid} fallo envio (intento {intento}/{REINTENTOS_SMTP}): "
                      f"{str(det)[:80]} — reintento en {ESPERA_SMTP}s")
                time.sleep(ESPERA_SMTP)

        print(f"  #{aid} {res['nombre']} -> {destino}: {'OK' if ok else 'FALLO ' + str(det)}")
        if ok:
            enviados += 1
            if not es_prueba:
                _registrar(conn, aid, semana, 'ok', str(det))
        else:
            fallos += 1
            if not es_prueba:
                _registrar(conn, aid, semana, 'fallo', str(det))

    conn.close()
    print(f'\nSemana {semana} — Enviados: {enviados} · Fallos: {fallos} · Ya estaban: {salteados}')


if __name__ == '__main__':
    main()
