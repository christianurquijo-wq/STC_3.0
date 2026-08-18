# reportes.py
import os
import smtplib
import streamlit as st
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
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


def _fila_kpi(etiqueta, valor, destacado=False):
    color_valor = "#FD531E" if destacado else "#292929"
    return f'''
        <tr>
            <td style="padding:8px; border-bottom:1px solid #eee; color:#656A71;">{etiqueta}</td>
            <td style="padding:8px; border-bottom:1px solid #eee; font-weight:bold; color:{color_valor};">{valor}</td>
        </tr>
    '''


def _barra_horizontal(etiqueta, valor, maximo, color="#FD531E"):
    ancho = round((valor / maximo) * 100, 1) if maximo else 0
    return f'''
        <tr>
            <td style="padding:6px 10px 6px 0; font-size:12px; color:#656A71; width:180px; white-space:nowrap;">{etiqueta}</td>
            <td style="padding:6px 0;">
                <table style="width:100%; border-collapse:collapse;"><tr>
                    <td style="background-color:{color}; width:{ancho}%; height:14px; border-radius:3px;"></td>
                    <td style="width:{100-ancho}%;"></td>
                </tr></table>
            </td>
            <td style="padding:6px 0 6px 10px; font-size:12px; font-weight:bold; color:#292929; text-align:right; width:50px;">{valor}</td>
        </tr>
    '''


def _tabla_barras(titulo, df: pd.DataFrame, col_etiqueta: str, col_valor: str, color="#FD531E") -> str:
    if df.empty:
        return f'<h3 style="color:#292929; margin-top:24px;">{titulo}</h3><p style="color:#656A71; font-size:13px;">Sin datos disponibles.</p>'
    maximo = df[col_valor].max()
    filas = "".join(_barra_horizontal(str(row[col_etiqueta]), row[col_valor], maximo, color) for _, row in df.iterrows())
    return f'''
        <h3 style="color:#292929; margin-top:24px;">{titulo}</h3>
        <table style="width:100%; border-collapse:collapse;">{filas}</table>
    '''


def _tabla_estados_html(tabla: pd.DataFrame) -> str:
    encabezados = "".join(f'<th style="padding:8px; text-align:left; border-bottom:2px solid #292929; font-size:12px; color:#656A71;">{c}</th>' for c in tabla.columns)
    filas = ""
    for _, row in tabla.iterrows():
        celdas = "".join(f'<td style="padding:8px; border-bottom:1px solid #eee; font-size:13px;">{"" if pd.isna(v) else v}</td>' for v in row)
        filas += f"<tr>{celdas}</tr>"
    return f'''
        <h3 style="color:#292929; margin-top:24px;">Tabla de procesos por etapa</h3>
        <table style="width:100%; border-collapse:collapse;">
            <tr>{encabezados}</tr>
            {filas}
        </table>
    '''


def construir_html_completo(r: dict, tabla_estados_df: pd.DataFrame, conteo_momento_df: pd.DataFrame, series: dict) -> str:
    kpis = "".join([
        _fila_kpi("Leads en CRM", r["leads"]),
        _fila_kpi("Matriculados CRM", r["matriculados"]),
        _fila_kpi("En proceso (Verificación)", r["en_proceso"]),
        _fila_kpi("Avance a la fecha (Verificación)", f"{r['avance_fecha_verificacion']}%", destacado=True),
        _fila_kpi("Orientados (Total)", r["orientados"]),
        _fila_kpi("Orientados Básicos", r["orientados_basicos"]),
        _fila_kpi("Orientados Especializados", r["orientados_especializados"]),
        _fila_kpi("Avance Orientación (meta total 5102)", f"{r['avance_general_orientacion']}%", destacado=True),
        _fila_kpi("Formación en curso", r["formados_en_curso"]),
        _fila_kpi("Formación finalizada", r["finalizados_formacion"]),
        _fila_kpi("Avance Formación (meta Especializado)", f"{r['avance_general_formacion']}%", destacado=True),
        _fila_kpi("Cantidad entregados", r["cantidad_entregados"]),
        _fila_kpi("Avance Entregas (meta total 5102)", f"{r['avance_entregas']}%", destacado=True),
    ])

    tabla_html = _tabla_estados_html(tabla_estados_df)
    momento_html = _tabla_barras("Momento del proceso (Back UP)", conteo_momento_df, "Etapa", "Cantidad", color="#292929")

    verificacion_html = _tabla_barras("Evolución — Verificación (por semana)", series["verificacion"], "Fecha", "Cantidad", color="#FD531E")
    orientacion_html = _tabla_barras("Evolución — Orientación (por semana)", series["orientacion"], "Fecha", "Cantidad", color="#821F0D")
    formacion_html = _tabla_barras("Evolución — Formación (por semana)", series["formacion"], "Fecha", "Cantidad", color="#656A71")

    return f'''
    <html><body style="font-family: Arial, sans-serif; color:#292929; max-width:700px; margin:0 auto;">
        <h2 style="color:#FD531E; border-bottom:3px solid #FD531E; padding-bottom:8px;">Avance STC 3.0 — {r['mes_actual']}</h2>

        <table style="width:100%; border-collapse:collapse; margin-top:12px;">{kpis}</table>

        {tabla_html}
        {momento_html}
        {verificacion_html}
        {orientacion_html}
        {formacion_html}

        <p style="color:#656A71; font-size:11px; margin-top:30px; border-top:1px solid #eee; padding-top:12px;">
            Generado automáticamente desde el Dashboard de Control de Calidad STC 3.0.
        </p>
    </body></html>
    '''


def enviar_reporte(destinatarios: list, r: dict, tabla_estados_df: pd.DataFrame, conteo_momento_df: pd.DataFrame, series: dict) -> tuple:
    """Envía el reporte HTML completo (sin adjuntos). Retorna (exito: bool, mensaje: str)."""
    usuario, clave = _credenciales_gmail()
    if not usuario or not clave:
        return False, "Faltan las credenciales de Gmail (GMAIL_USER / GMAIL_APP_PASSWORD)."

    msg = MIMEMultipart("alternative")
    msg["From"] = usuario
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = f"Avance STC 3.0 — {r['mes_actual']}"
    msg.attach(MIMEText(construir_html_completo(r, tabla_estados_df, conteo_momento_df, series), "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(usuario, clave)
            server.sendmail(usuario, destinatarios, msg.as_string())
        return True, f"Reporte enviado a {len(destinatarios)} destinatario(s)."
    except Exception as e:
        return False, f"Error al enviar: {e}"

def enviar_tabla_generica(destinatarios: list, titulo: str, tabla: pd.DataFrame) -> tuple:
    usuario, clave = _credenciales_gmail()
    if not usuario or not clave:
        return False, "Faltan las credenciales de Gmail."

    from email.mime.application import MIMEApplication
    msg = MIMEMultipart()
    msg["From"] = usuario
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = titulo

    cuerpo = f'''
        <html><body style="font-family: Arial, sans-serif; color:#292929;">
            <h3 style="color:#FD531E;">{titulo}</h3>
            <p style="color:#656A71;">Se adjunta el detalle en formato CSV — {len(tabla)} registros.</p>
        </body></html>
    '''
    msg.attach(MIMEText(cuerpo, "html"))

    import io
    buffer = io.StringIO()
    tabla.to_csv(buffer, index=False, encoding="utf-8-sig")
    adjunto = MIMEApplication(buffer.getvalue().encode("utf-8-sig"), Name="detalle.csv")
    adjunto["Content-Disposition"] = 'attachment; filename="detalle.csv"'
    msg.attach(adjunto)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(usuario, clave)
            server.sendmail(usuario, destinatarios, msg.as_string())
        return True, f"Tabla enviada a {len(destinatarios)} destinatario(s)."
    except Exception as e:
        return False, f"Error al enviar: {e}"