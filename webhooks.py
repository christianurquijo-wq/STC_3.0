# webhooks.py
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def _obtener_secreto(nombre_env: str):
    try:
        return st.secrets[nombre_env]
    except Exception:
        return os.getenv(nombre_env)


def disparar_webhook(url_env: str, header_nombre_env: str = None, header_valor_env: str = None) -> tuple:
    """Dispara un webhook de n8n. Retorna (exito: bool, mensaje: str)."""
    url = _obtener_secreto(url_env)
    if not url:
        return False, f"Falta configurar {url_env} en las variables de entorno/secrets."

    headers = {}
    if header_nombre_env and header_valor_env:
        nombre_header = _obtener_secreto(header_nombre_env)
        valor_header = _obtener_secreto(header_valor_env)
        if nombre_header and valor_header:
            headers[nombre_header] = valor_header

    try:
        resp = requests.post(url, headers=headers, timeout=15)
        if resp.status_code in (200, 201, 202, 204):
            return True, "Flujo de remisiones disparado correctamente."
        return False, f"El webhook respondió con código {resp.status_code}."
    except Exception as e:
        return False, f"Error al conectar con el webhook: {e}"

WEBHOOKS_REGISTRADOS = [
    {
        "id": "remisiones",
        "etiqueta": "📤 Enviar remisiones (n8n)",
        "url_env": "WEBHOOK_REMISIONES_URL",
        "header_nombre_env": "WEBHOOK_REMISIONES_HEADER_NOMBRE",
        "header_valor_env": "WEBHOOK_REMISIONES_HEADER_VALOR",
        "confirmar": True,
        "mensaje_confirmacion": "¿Confirmas disparar el flujo de remisiones? Esta acción activa el proceso real en n8n.",
    },
    # Para agregar un webhook nuevo, copia este bloque completo y cambia los valores.
    # Si no necesita confirmación, pon "confirmar": False.
]