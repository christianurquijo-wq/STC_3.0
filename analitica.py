# analitica.py
import pandas as pd
import streamlit as st
from cargar_datos import cargar_fuente
from normalizador import normalizar_cedula
from column_mapping import CAMPO_ESTADO_FCS

# Columnas del FCS a excluir de la auditoría de vacíos (G y H = fechas de
# inscripción en plataformas que legítimamente quedan vacías para muchos casos)
COLUMNAS_EXCLUIR_VACIOS = [6, 7]  # índices 0-based de G y H
FCS_ULTIMA_COLUMNA_AUDITORIA = 83  # A hasta CE

def _set_cedulas(df: pd.DataFrame, columna: str) -> set:
    return set(df[columna].apply(normalizar_cedula).dropna())

def cargar_todo():
    fuentes = {}
    for nombre in ["general", "verificacion", "formacion", "orientacion_consolidado",
                   "remisiones", "encuesta_basico_jco", "encuesta_especializado"]:
        df, _ = cargar_fuente(nombre)
        fuentes[nombre] = df
    return fuentes

# --- Caso 1: Leads sin gestión ---
def leads_sin_gestion(general: pd.DataFrame) -> pd.DataFrame:
    return general[general["Momento del proceso"] == "0.Sin gestión"]

# --- Caso 2: Leads en verificación ---
def leads_en_verificacion(general: pd.DataFrame) -> pd.DataFrame:
    return general[general["Momento del proceso"] == "1.En verificación"]

# --- Caso 3: Verificados sin reporte de orientación ---
def verificados_sin_reporte_orientacion(general: pd.DataFrame, orientacion: pd.DataFrame) -> pd.DataFrame:
    verificados = general[general["Verificado"] == "1"].copy()
    verificados["cedula_norm"] = verificados["CC Prospecto"].apply(normalizar_cedula)

    orient_con_reporte = orientacion[orientacion["REPORTE"].notna() & (orientacion["REPORTE"].str.strip() != "")]
    cedulas_con_reporte = _set_cedulas(orient_con_reporte, "NÚMERO DE DOCUMENTO")

    return verificados[~verificados["cedula_norm"].isin(cedulas_con_reporte)]

# --- Caso 4: Formación vs Orientados Especializado (100% dentro de General) ---
def formados_sin_orientar(general: pd.DataFrame) -> pd.DataFrame:
    """AX (Estado de la formación) lleno + AE (Reporte) vacío = está en formación pero sin reporte de orientación."""
    en_formacion = general["Estado de la formación"].notna() & (general["Estado de la formación"].astype(str).str.strip() != "")
    sin_reporte = general["Reporte"].isna() | (general["Reporte"].astype(str).str.strip() == "")
    return general[en_formacion & sin_reporte]

def orientados_especializado_sin_formacion(general: pd.DataFrame) -> pd.DataFrame:
    """AE (Reporte) lleno + AH (Paquete)=ESPECIALIZADO + AX (Estado de la formación) vacío = orientado especializado que no está en formación."""
    con_reporte = general["Reporte"].notna() & (general["Reporte"].astype(str).str.strip() != "")
    es_especializado = general["Paquete"].astype(str).str.strip().str.upper() == "ESPECIALIZADO"
    sin_formacion = general["Estado de la formación"].isna() | (general["Estado de la formación"].astype(str).str.strip() == "")
    return general[con_reporte & es_especializado & sin_formacion]

# --- Caso 5: Orientados vs Remitidos ---
def diff_orientados_vs_remitidos(orientacion: pd.DataFrame, remisiones: pd.DataFrame) -> dict:
    cedulas_orientados = _set_cedulas(orientacion, "NÚMERO DE DOCUMENTO")
    cedulas_remitidos = _set_cedulas(remisiones, "NÚMERO DE DOCUMENTO")

    solo_orientados = cedulas_orientados - cedulas_remitidos
    solo_remitidos = cedulas_remitidos - cedulas_orientados

    return {
        "solo_orientados": orientacion[orientacion["NÚMERO DE DOCUMENTO"].apply(normalizar_cedula).isin(solo_orientados)],
        "solo_remitidos": remisiones[remisiones["NÚMERO DE DOCUMENTO"].apply(normalizar_cedula).isin(solo_remitidos)],
    }

# --- Caso 6: Encuestados vs Listos para reportar ---
def diff_encuestados_vs_listos_reportar(orientacion: pd.DataFrame, enc_basico: pd.DataFrame, enc_esp: pd.DataFrame) -> dict:
    cedulas_encuestados = _set_cedulas(enc_basico, "CEDULA") | _set_cedulas(enc_esp, "CEDULA")

    listos = orientacion[orientacion[CAMPO_ESTADO_FCS].str.strip().str.upper() == "LISTO PARA REPORTAR"]
    cedulas_listos = _set_cedulas(listos, "NÚMERO DE DOCUMENTO")

    solo_encuestados = cedulas_encuestados - cedulas_listos
    solo_listos = cedulas_listos - cedulas_encuestados

    return {
        "solo_encuestados": solo_encuestados,   # sets simples, no siempre hay fila completa disponible
        "solo_listos": listos[listos["NÚMERO DE DOCUMENTO"].apply(normalizar_cedula).isin(solo_listos)],
    }

# --- Auditoría de campos vacíos en el FCS (A hasta CE, excepto G y H) ---
def campos_vacios_fcs(orientacion: pd.DataFrame) -> pd.DataFrame:
    # Solo auditar filas con cédula real (descarta filas fantasma vacías del rango de la API)
    tiene_cedula = orientacion["NÚMERO DE DOCUMENTO"].notna() & (orientacion["NÚMERO DE DOCUMENTO"].astype(str).str.strip() != "")
    orientacion = orientacion[tiene_cedula]

    columnas_auditar = [
        c for i, c in enumerate(orientacion.columns[:FCS_ULTIMA_COLUMNA_AUDITORIA])
        if i not in COLUMNAS_EXCLUIR_VACIOS
    ]

    registros = []
    for _, fila in orientacion.iterrows():
        cedula = fila.get("NÚMERO DE DOCUMENTO", "SIN CÉDULA")
        for col in columnas_auditar:
            valor = fila.get(col)
            if pd.isna(valor) or str(valor).strip() == "":
                registros.append({"cedula": cedula, "campo_vacio": col})

    return pd.DataFrame(registros)

# --- Resumen para el dashboard (Tab 3) ---
def generar_resumen(f: dict) -> dict:
    """Corre las 6 reglas y devuelve un dict {nombre_caso: DataFrame} listo para graficar y filtrar."""
    general = f["general"]
    orientacion = f["orientacion_consolidado"]
    remisiones = f["remisiones"]
    enc_basico = f["encuesta_basico_jco"]
    enc_esp = f["encuesta_especializado"]

    diff_or = diff_orientados_vs_remitidos(orientacion, remisiones)
    diff_enc = diff_encuestados_vs_listos_reportar(orientacion, enc_basico, enc_esp)

    resultado = {
        "Leads sin gestión": leads_sin_gestion(general),
        "Leads en verificación": leads_en_verificacion(general),
        "Verificados sin reporte orientación": verificados_sin_reporte_orientacion(general, orientacion),
        "Formados sin orientar": formados_sin_orientar(general),
        "Orientados Esp. sin formación": orientados_especializado_sin_formacion(general),
        "Orientados sin remitir": diff_or["solo_orientados"],
        "Remitidos sin orientar": diff_or["solo_remitidos"],
        "Encuestados sin marcar listo": general[general["CC Prospecto"].apply(normalizar_cedula).isin(diff_enc["solo_encuestados"])],
        "Listos sin encuestar": diff_enc["solo_listos"],
    }
    return resultado

from column_mapping import (
    CAMPO_MOMENTO_BACKUP, CAMPO_ENTREGADO, META_TOTAL_BASICO,
    META_TOTAL_ESPECIALIZADO, META_TOTAL_PROGRAMA, MESES_ORDEN,
)
import datetime

def cargar_metas() -> pd.DataFrame:
    df, _ = cargar_fuente("parametros")
    for col in ["Básico", "Especializado", "Total"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df

def meta_acumulada(df_metas: pd.DataFrame, mes_actual: str, columna: str) -> float:
    """Suma la meta de esa columna desde Julio (inicio del programa en la tabla) hasta el mes actual."""
    if mes_actual not in MESES_ORDEN:
        return 0
    idx_actual = MESES_ORDEN.index(mes_actual)
    meses_validos = set(MESES_ORDEN[:idx_actual + 1])
    return df_metas[df_metas["Mes"].isin(meses_validos)][columna].sum()

def mes_actual_es() -> str:
    meses = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
             7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}
    return meses[datetime.date.today().month]

def es_entregado(serie: pd.Series) -> pd.Series:
    """True solo si el valor contiene la palabra 'Reportado' (ej. 'Entregado P1 - Reportado')."""
    return serie.astype(str).str.contains("Reportado", case=False, na=False)

def resumen_looker(general: pd.DataFrame, df_metas: pd.DataFrame, excluir_entregados: bool = False) -> dict:
    mes_actual = mes_actual_es()

    df = general.copy()
    if excluir_entregados and CAMPO_ENTREGADO in df.columns:
        df = df[~es_entregado(df[CAMPO_ENTREGADO])]

    leads = len(df)
    matriculados = (df["Estado CRM"].astype(str).str.strip() == "Matriculado").sum()
    en_proceso = (df[CAMPO_MOMENTO_BACKUP].astype(str).str.strip() == "1.En verificación").sum()

    reporte = df["Reporte"].astype(str).str.strip()
    paquete = df["Paquete"].astype(str).str.strip().str.upper()
    finalizados_reporte = reporte.isin(["FINALIZADO", "FINALIZADO PENDIENTE X REMISIÓN"])

    orientados = finalizados_reporte.sum()
    orientados_basicos = (finalizados_reporte & (paquete == "BÁSICO")).sum()
    orientados_especializados = (finalizados_reporte & (paquete == "ESPECIALIZADO")).sum()

    estado_form = df["Estado de la formación"].astype(str).str.strip().str.upper()
    formados_en_curso = (estado_form == "EN CURSO").sum()
    finalizados_formacion = estado_form.isin(["FINALIZADO", "CERTIFICADO"]).sum()

    if CAMPO_ENTREGADO in general.columns:
        cantidad_entregados = es_entregado(general[CAMPO_ENTREGADO]).sum()
    else:
        cantidad_entregados = 0

    meta_acum_basico = meta_acumulada(df_metas, mes_actual, "Básico")
    meta_acum_especializado = meta_acumulada(df_metas, mes_actual, "Especializado")
    meta_acum_total = meta_acumulada(df_metas, mes_actual, "Total")

    def pct(num, den):
        return round(100 * num / den, 2) if den else 0

    return {
        "mes_actual": mes_actual,
        "leads": leads,
        "matriculados": matriculados,
        "en_proceso": en_proceso,
        "orientados": orientados,
        "orientados_basicos": orientados_basicos,
        "orientados_especializados": orientados_especializados,
        "formados_en_curso": formados_en_curso,
        "finalizados_formacion": finalizados_formacion,
        "cantidad_entregados": cantidad_entregados,
        "avance_fecha_verificacion": pct(matriculados, meta_acum_total),
        "avance_general_orientacion": pct(orientados, META_TOTAL_PROGRAMA),
        "avance_general_formacion": pct(finalizados_formacion, META_TOTAL_ESPECIALIZADO),
        "avance_entregas": pct(cantidad_entregados, META_TOTAL_PROGRAMA),
    }


def tabla_estados(general: pd.DataFrame, enc_basico: pd.DataFrame, enc_esp: pd.DataFrame,
                   excluir_entregados: bool = False, por_paquete: bool = False) -> pd.DataFrame:
    df = general.copy()
    if excluir_entregados and CAMPO_ENTREGADO in df.columns:
        df = df[~es_entregado(df[CAMPO_ENTREGADO])]

    paquete = df["Paquete"].astype(str).str.strip().str.upper()
    reporte = df["Reporte"].astype(str).str.strip()
    finalizados_reporte = reporte.isin(["FINALIZADO", "FINALIZADO PENDIENTE X REMISIÓN"])
    estado_form = df["Estado de la formación"].astype(str).str.strip().str.upper()
    finalizados_formacion = estado_form.isin(["FINALIZADO", "CERTIFICADO"])
    matriculados = df["Estado CRM"].astype(str).str.strip() == "Matriculado"

    paquete_enc_basico = enc_basico["PAQUETE"].astype(str).str.strip().str.upper() if "PAQUETE" in enc_basico.columns else pd.Series(dtype=str)
    paquete_enc_esp = enc_esp["PAQUETE"].astype(str).str.strip().str.upper() if "PAQUETE" in enc_esp.columns else pd.Series(dtype=str)

    if not por_paquete:
        filas = [
            {"Etapa": "Verificación (Matriculados)", "Total": matriculados.sum()},
            {"Etapa": "Orientación", "Total": finalizados_reporte.sum()},
            {"Etapa": "Formación (Finalizada)", "Total": finalizados_formacion.sum()},
            {"Etapa": "Encuesta", "Total": len(enc_basico) + len(enc_esp)},
        ]
        return pd.DataFrame(filas)

    filas = [
        {
            "Etapa": "Verificación (Matriculados)",
            "Básico": (matriculados & (paquete == "BÁSICO")).sum(),
            "Especializado": (matriculados & (paquete == "ESPECIALIZADO")).sum(),
            "Total": matriculados.sum(),
        },
        {
            "Etapa": "Orientación",
            "Básico": (finalizados_reporte & (paquete == "BÁSICO")).sum(),
            "Especializado": (finalizados_reporte & (paquete == "ESPECIALIZADO")).sum(),
            "Total": finalizados_reporte.sum(),
        },
        {
            "Etapa": "Formación (Finalizada)",
            "Básico": None,  # Formación solo aplica a Especializado/JCO
            "Especializado": finalizados_formacion.sum(),
            "Total": finalizados_formacion.sum(),
        },
        {
            "Etapa": "Encuesta",
            "Básico": (paquete_enc_basico == "BÁSICO").sum(),
            "Especializado": (paquete_enc_esp == "ESPECIALIZADO").sum(),
            "Total": len(enc_basico) + len(enc_esp),
        },
    ]
    return pd.DataFrame(filas)

def serie_temporal(general: pd.DataFrame, columna_fecha: str, granularidad: str = "Diaria") -> pd.DataFrame:
    """Cuenta leads por fecha, agrupando diario o por semana calendario (lunes a domingo)."""
    fechas = pd.to_datetime(general[columna_fecha], dayfirst=True, errors="coerce").dropna()

    if granularidad == "Diaria":
        conteo = fechas.dt.date.value_counts().sort_index()
        df = conteo.reset_index()
        df.columns = ["Fecha", "Cantidad"]
    else:  # Semanal
        inicio_semana = (fechas - pd.to_timedelta(fechas.dt.weekday, unit="D")).dt.date
        conteo = inicio_semana.value_counts().sort_index()
        df = conteo.reset_index()
        df.columns = ["Fecha", "Cantidad"]
        df["Fecha"] = df["Fecha"].apply(lambda d: f"Semana del {d.strftime('%d/%m/%Y')}")

    return df

from contextlib import contextmanager

@contextmanager
def carga_personalizada(mensaje="Cargando..."):
    placeholder = st.empty()
    placeholder.markdown(f'''
        <div style="display:flex; align-items:center; gap:12px; padding:20px 0;">
            <div style="width:28px; height:28px; border:3px solid #EAEAEA; border-top:3px solid #FD531E;
                        border-radius:50%; animation: girar 0.8s linear infinite;"></div>
            <span style="color:#656A71; font-size:14px;">{mensaje}</span>
        </div>
        <style>
        @keyframes girar {{ 0% {{transform: rotate(0deg);}} 100% {{transform: rotate(360deg);}} }}
        </style>
    ''', unsafe_allow_html=True)
    try:
        yield
    finally:
        placeholder.empty()

def calcular_progreso_ruta(cedula_norm: str, general: pd.DataFrame, remisiones: pd.DataFrame,
                            orientacion: pd.DataFrame, enc_basico: pd.DataFrame, enc_esp: pd.DataFrame) -> dict:
    persona = general[general["cedula_norm"] == cedula_norm]
    if persona.empty:
        return None
    persona = persona.iloc[0]

    jco = normalizar_texto(persona.get("JCO"))
    paquete = normalizar_texto(persona.get("Paquete"))

    if jco == "SI":
        ruta = "JCO"
        etapas = ["Verificación", "Orientación", "Formación", "Remisión", "Encuesta"]
    elif paquete == "ESPECIALIZADO":
        ruta = "Especializado"
        etapas = ["Verificación", "Orientación", "Formación", "Remisión", "Mitigación", "Encuesta"]
    elif paquete == "BÁSICO":
        ruta = "Básico"
        etapas = ["Verificación", "Orientación", "Remisión", "Encuesta"]
    else:
        return {"ruta": "Sin clasificar todavía", "etapas": [], "completado": {}}

    completado = {}
    completado["Verificación"] = str(persona.get("Estado CRM", "")).strip() == "Matriculado"

    reporte = str(persona.get("Reporte", "")).strip()
    completado["Orientación"] = reporte in ["FINALIZADO", "FINALIZADO PENDIENTE X REMISIÓN"]

    if "Formación" in etapas:
        completado["Formación"] = str(persona.get("Estado de la formación", "")).strip() == "FINALIZADO"

    ced_remision = remisiones[remisiones["NÚMERO DE DOCUMENTO"].apply(normalizar_cedula) == cedula_norm]
    completado["Remisión"] = (ced_remision["REPORTE"].astype(str).str.strip() == "FINALIZADO").any()

    if "Mitigación" in etapas:
        completado["Mitigación"] = str(persona.get("Bono enviado", "")).strip().upper() == "SI"

    en_encuesta_basico = cedula_norm in set(enc_basico["CEDULA"].apply(normalizar_cedula).dropna())
    en_encuesta_esp = cedula_norm in set(enc_esp["CEDULA"].apply(normalizar_cedula).dropna())
    completado["Encuesta"] = en_encuesta_basico or en_encuesta_esp

    return {"ruta": ruta, "etapas": etapas, "completado": completado}

def html_diagrama_ruta(progreso: dict) -> str:
    if not progreso or not progreso["etapas"]:
        return f'<p style="color:#656A71;">{progreso["ruta"] if progreso else "Cédula no encontrada en General"}</p>'

    pasos_html = ""
    total = len(progreso["etapas"])
    for i, etapa in enumerate(progreso["etapas"]):
        hecho = progreso["completado"].get(etapa, False)
        color = "#FD531E" if hecho else "#D9D9D9"
        texto_color = "#FFFFFF" if hecho else "#656A71"
        icono = "✓" if hecho else str(i + 1)
        linea = "" if i == total - 1 else f'<div style="flex:1; height:3px; background-color:{"#FD531E" if hecho else "#D9D9D9"}; margin-top:19px;"></div>'
        pasos_html += f'''
            <div style="display:flex; flex-direction:column; align-items:center; min-width:90px;">
                <div style="width:38px; height:38px; border-radius:50%; background-color:{color};
                            display:flex; align-items:center; justify-content:center; font-weight:bold; color:{texto_color};">
                    {icono}
                </div>
                <div style="font-size:12px; color:#292929; margin-top:6px; text-align:center;">{etapa}</div>
            </div>
            {linea}
        '''

    return f'''
        <div style="margin:16px 0;">
            <div style="font-size:13px; color:#656A71; margin-bottom:12px;">Ruta: <b style="color:#292929;">{progreso["ruta"]}</b></div>
            <div style="display:flex; align-items:flex-start;">{pasos_html}</div>
        </div>
    '''