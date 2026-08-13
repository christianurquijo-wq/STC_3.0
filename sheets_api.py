# sheets_api.py
import os
import time
import httplib2
import plotly.express as px
from dotenv import load_dotenv
from googleapiclient.discovery import build

load_dotenv()
_API_KEY = os.getenv("GOOGLE_API_KEY")
_service = None

def _get_service():
    global _service
    if _service is None:
        http = httplib2.Http(timeout=30)  # evita que se cuelgue indefinidamente
        _service = build("sheets", "v4", developerKey=_API_KEY, http=http)
    return _service

def _con_reintentos(func, intentos=3, espera_base=2):
    """Reintenta una llamada a la API hasta 3 veces si falla por red, con espera creciente."""
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            return func()
        except Exception as e:
            ultimo_error = e
            if intento < intentos:
                time.sleep(espera_base * intento)
    raise ultimo_error

def _get_sheet_title(spreadsheet_id: str, gid: str) -> str:
    service = _get_service()
    meta = _con_reintentos(lambda: service.spreadsheets().get(
        spreadsheetId=spreadsheet_id, fields="sheets.properties"
    ).execute())
    for sheet in meta["sheets"]:
        props = sheet["properties"]
        if str(props["sheetId"]) == str(gid):
            return props["title"]
    raise ValueError(f"No encontré una pestaña con gid={gid} en el archivo {spreadsheet_id}")

def obtener_valores_crudos(spreadsheet_id: str, gid: str) -> list:
    service = _get_service()
    titulo = _get_sheet_title(spreadsheet_id, gid)
    resultado = _con_reintentos(lambda: service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{titulo}'",
        valueRenderOption="FORMATTED_VALUE",
    ).execute())
    return resultado.get("values", [])