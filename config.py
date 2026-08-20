# config.py
import time

FUENTES = {
    "general": {
        "id": "14BK3P6HigQOnNW6vAMc7RF5ioETKop4GUWxlZIPfmm0",
        "gid": "0",
        "ancla": "CC Prospecto",
    },
    "formacion": {
        "id": "1J0u5EiA-82N1LTKT-Qt8qdJYI_sbc_hhjH33AWxCvZo",
        "gid": "225050212",
        "ancla": "Cedula",
    },
    "orientacion_consolidado": {
        "id": "15pgRouShB-tUNbdtGYs-ziYeuDeqV0tl21Hb9lkDXto",
        "gid": "978755551",
        "ancla": "NÚMERO DE DOCUMENTO",
    },
    "remisiones": {
        "id": "1EfxYCCEZsKqJK8Icou3hbZDBWEEm9T4VUK5EESI8ea0",
        "gid": "0",
        "ancla": "NÚMERO DE DOCUMENTO",
    },
    "verificacion": {
        "id": "1Ws-dR69INyipAU9bIVTL6VgCEJXkkfMpzm2H4Kaamm8",
        "gid": "1240996279",
        "ancla": "Número Documento",
    },
    "encuesta_basico_jco": {
        "id": "1YeJUSrX8WnD_kf5Y8z5dsFb_mH7XNX9i8-EYP0aW-gA",
        "gid": "851734049",
        "ancla": "CEDULA",
    },
    "encuesta_especializado": {
        "id": "1YeJUSrX8WnD_kf5Y8z5dsFb_mH7XNX9i8-EYP0aW-gA",
        "gid": "1685171350",
        "ancla": "CEDULA",
    },
    "parametros": {
        "id": "14BK3P6HigQOnNW6vAMc7RF5ioETKop4GUWxlZIPfmm0",
        "gid": "1516261654",
        "ancla": "Mes",
    },
    "matriz_documental": {
        "id": "1SLHtpzoL03kb0XWWzH1ZU_Ff4DhkNKuXlGHbjwyQcIQ",
        "gid": "1167929471",
        "ancla": "CÉDULA",
    },
    "subsanaciones": {
        "id": "15pgRouShB-tUNbdtGYs-ziYeuDeqV0tl21Hb9lkDXto",
        "gid": "1376346035",
        "ancla": "Documento",
    },
}

def url_csv(nombre_fuente: str) -> str:
    f = FUENTES[nombre_fuente]
    return f"https://docs.google.com/spreadsheets/d/{f['id']}/export?format=csv&gid={f['gid']}&_={int(time.time())}"