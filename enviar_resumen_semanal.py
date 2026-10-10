# -*- coding: utf-8 -*-
"""
enviar_resumen_semanal.py — manda el resumen de la semana a CADA atleta por mail.
Pensado para correr los LUNES (Programador de tareas de Windows o cron).

Requiere en el entorno:
    DATABASE_URL        (la misma del backend)
    GMAIL_USER          (tu Gmail; por defecto kinesiologia.hospital.melo@gmail.com)
    GMAIL_APP_PASSWORD  (clave de aplicación de Gmail — ver noah_email.py)

Uso:
    python enviar_resumen_semanal.py            # manda a todos
    python enviar_resumen_semanal.py --dry      # NO envía, solo muestra a quién iría
    python enviar_resumen_semanal.py --prueba TU_MAIL   # manda 1 de prueba a TU_MAIL
"""
import os, sys
import psycopg2, psycopg2.extras

def main():
    dsn = os.environ.get('DATABASE_URL', '')
    if not dsn:
        print('ERROR: falta DATABASE_URL en el entorno.'); sys.exit(1)

    dry = '--dry' in sys.argv
    prueba_to = None
    if '--prueba' in sys.argv:
        i = sys.argv.index('--prueba')
        prueba_to = sys.argv[i + 1] if i + 1 < len(sys.argv) else None

    from noah_resumen_semanal import construir_resumen, render_html
    from noah_email import enviar_mail

    from db_compat import ConexionCompat
    raw = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.DictCursor)
    conn = ConexionCompat(raw)

    atletas = conn.execute("SELECT id, nombre FROM atletas ORDER BY id").fetchall()
    print(f'Atletas: {len(atletas)}')
    enviados = fallos = 0

    for a in atletas:
        aid = a[0] if not hasattr(a, 'keys') else a['id']
        res = construir_resumen(conn, aid)
        if not res:
            print(f'  #{aid}: sin datos, salteo'); continue
        destino = prueba_to or res.get('email')
        asunto = f"Tu semana en NOAH — {res['nombre']} ({res['tss_total']} TSS, {res['horas']}h)"
        if dry:
            print(f"  #{aid} {res['nombre']}: iría a {destino} · TSS {res['tss_total']} · "
                  f"{len(res['alertas'])} alertas")
            continue
        if not destino:
            print(f"  #{aid} {res['nombre']}: SIN email, salteo"); fallos += 1; continue
        if prueba_to:
            asunto = '[PRUEBA] ' + asunto
        html = render_html(res)
        ok, det = enviar_mail(destino, asunto, html)
        print(f"  #{aid} {res['nombre']} -> {destino}: {'OK' if ok else 'FALLO ' + det}")
        if ok: enviados += 1
        else: fallos += 1
        # en modo prueba se mandan TODOS los resúmenes a tu casilla (no a los atletas)

    conn.close()
    print(f'\nEnviados: {enviados} · Fallos: {fallos}')

if __name__ == '__main__':
    main()
