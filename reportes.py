# reportes.py
import os
import smtplib
import io
import streamlit as st
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv

load_dotenv()

def _credenciales_gmail():
    try:
        usuario = st.secrets["GMAIL_USER"]
        clave = st.secrets["GMAIL_APP_PASSWORD"]
    except Exception:
        usuario = os.getenv("GMAIL_USER")
        clave = os.getenv("GMAIL_APP_PASSWORD")
    return usuario, clave


def construir_html_resumen(r: dict) -> str:
    return f"""
    <html><body style="font-family: Arial, sans-serif; color:#292929;">
        <h2 style="color:#FD531E;">Avance STC 3.0 — {r['mes_actual']}</h2>
        <table style="border-collapse: collapse; width:100%;">
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Leads en CRM</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold;">{r['leads']}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Matriculados CRM</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold;">{r['matriculados']}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Avance a la fecha (Verificación)</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold; color:#FD531E;">{r['avance_fecha_verificacion']}%</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Orientados (Total)</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold;">{r['orientados']}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Avance Orientación (meta total 5102)</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold; color:#FD531E;">{r['avance_general_orientacion']}%</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Finalizados Formación</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold;">{r['finalizados_formacion']}</td></tr>
            <tr><td style="padding:8px; border-bottom:1px solid #eee;">Cantidad entregados</td><td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold;">{r['cantidad_entregados']}</td></tr>
            <tr><td style="padding:8px;">Avance Entregas (meta total 5102)</td><td style="padding:8px; font-weight:bold; color:#FD531E;">{r['avance_entregas']}%</td></tr>
        </table>
        <p style="color:#656A71; font-size:12px; margin-top:20px;">Adjunto encontrarás el detalle por etapa. Generado automáticamente desde el dashboard STC 3.0.</p>
    </body></html>
    """


def enviar_reporte(destinatarios: list, r: dict, tabla_detalle) -> tuple:
    """Envía el reporte. Retorna (exito: bool, mensaje: str)."""
    usuario, clave = _credenciales_gmail()
    if not usuario or not clave:
        return False, "Faltan las credenciales de Gmail (GMAIL_USER / GMAIL_APP_PASSWORD)."

    msg = MIMEMultipart()
    msg["From"] = usuario
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = f"Avance STC 3.0 — {r['mes_actual']}"
    msg.attach(MIMEText(construir_html_resumen(r), "html"))

    csv_buffer = io.StringIO()
    tabla_detalle.to_csv(csv_buffer, index=False, encoding="utf-8-sig")
    adjunto = MIMEApplication(csv_buffer.getvalue().encode("utf-8-sig"), Name="detalle_por_etapa.csv")
    adjunto["Content-Disposition"] = 'attachment; filename="detalle_por_etapa.csv"'
    msg.attach(adjunto)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(usuario, clave)
            server.sendmail(usuario, destinatarios, msg.as_string())
        return True, f"Reporte enviado a {len(destinatarios)} destinatario(s)."
    except Exception as e:
        return False, f"Error al enviar: {e}"