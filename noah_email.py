# -*- coding: utf-8 -*-
"""
noah_email.py — envío de mails por Gmail (SMTP SSL).
Lee las credenciales del entorno:
    GMAIL_USER          (ej: kinesiologia.hospital.melo@gmail.com)
    GMAIL_APP_PASSWORD  (clave de aplicación de 16 letras — NO tu contraseña normal)
Cómo sacar la clave de aplicación:
    cuenta Google -> Seguridad -> Verificación en 2 pasos (activada) ->
    "Contraseñas de aplicaciones" -> generás una para "Correo" -> copiás las 16 letras.
"""
import os, ssl, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER_DEFAULT = 'kinesiologia.hospital.melo@gmail.com'

def enviar_mail(destino, asunto, html, texto=None):
    """Devuelve (ok: bool, detalle: str)."""
    user = os.environ.get('GMAIL_USER') or GMAIL_USER_DEFAULT
    pwd = os.environ.get('GMAIL_APP_PASSWORD')
    if not pwd:
        return False, 'Falta GMAIL_APP_PASSWORD en el entorno'
    if not destino:
        return False, 'Sin destinatario'
    msg = MIMEMultipart('alternative')
    msg['Subject'] = asunto
    msg['From'] = f'NOAH Coach <{user}>'
    msg['To'] = destino
    if texto:
        msg.attach(MIMEText(texto, 'plain', 'utf-8'))
    msg.attach(MIMEText(html, 'html', 'utf-8'))
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ctx, timeout=30) as s:
            s.login(user, pwd)
            s.sendmail(user, [destino], msg.as_string())
        return True, 'enviado'
    except Exception as e:
        return False, f'{type(e).__name__}: {e}'
