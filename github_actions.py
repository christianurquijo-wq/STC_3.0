# github_actions.py
import os
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

def _obtener_token():
    try:
        return st.secrets["GITHUB_TOKEN"]
    except Exception:
        return os.getenv("GITHUB_TOKEN")


def disparar_workflow(repo: str, workflow_file: str, rama: str = "main") -> tuple:
    """Dispara un GitHub Action vía workflow_dispatch. Retorna (exito, mensaje)."""
    token = _obtener_token()
    if not token:
        return False, "Falta configurar GITHUB_TOKEN en las variables de entorno/secrets."

    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    body = {"ref": rama}

    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code == 204:
            return True, "Workflow disparado correctamente en GitHub Actions."
        return False, f"GitHub respondió con código {resp.status_code}: {resp.text}"
    except Exception as e:
        return False, f"Error al conectar con GitHub: {e}"