# analitica.py
import pandas as pd
import streamlit as st
from cargar_datos import cargar_fuente
from normalizador import normalizar_cedula
from column_mapping import CAMPO_ESTADO_FCS
from normalizador_texto import normalizar_texto

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

@st.cache_data(ttl=600)
def cargar_todo_cache():
    return cargar_todo()

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

def calcular_progreso_ruta(cedula_norm: str, general: pd.DataFrame,
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

    completado["Remisión"] = normalizar_texto(persona.get("Remitido")) == "SI"
    
    if "Mitigación" in etapas:
        completado["Mitigación"] = str(persona.get("Bono enviado", "")).strip().upper() == "SI"

    en_encuesta_basico = cedula_norm in set(enc_basico["CEDULA"].apply(normalizar_cedula).dropna())
    en_encuesta_esp = cedula_norm in set(enc_esp["CEDULA"].apply(normalizar_cedula).dropna())
    completado["Encuesta"] = en_encuesta_basico or en_encuesta_esp

    return {"ruta": ruta, "etapas": etapas, "completado": completado}

def html_diagrama_ruta(progreso: dict) -> str:
    if not progreso or not progreso["etapas"]:
        mensaje = progreso["ruta"] if progreso else "Cédula no encontrada en General"
        return f'<p style="color:#656A71;">{mensaje}</p>'

    total = len(progreso["etapas"])
    pasos_html = ""
    for i, etapa in enumerate(progreso["etapas"]):
        hecho = progreso["completado"].get(etapa, False)
        color = "#FD531E" if hecho else "#D9D9D9"
        texto_color = "#FFFFFF" if hecho else "#656A71"
        icono = "✓" if hecho else str(i + 1)

        paso = (
            f'<div style="display:flex; flex-direction:column; align-items:center; min-width:90px;">'
            f'<div style="width:38px; height:38px; border-radius:50%; background-color:{color}; '
            f'display:flex; align-items:center; justify-content:center; font-weight:bold; color:{texto_color};">'
            f'{icono}</div>'
            f'<div style="font-size:12px; color:#292929; margin-top:6px; text-align:center;">{etapa}</div>'
            f'</div>'
        )

        if i < total - 1:
            color_linea = "#FD531E" if hecho else "#D9D9D9"
            paso += f'<div style="flex:1; height:3px; background-color:{color_linea}; margin-top:19px;"></div>'

        pasos_html += paso

    return (
        f'<div style="margin:16px 0;">'
        f'<div style="font-size:13px; color:#656A71; margin-bottom:12px;">Ruta: '
        f'<b style="color:#292929;">{progreso["ruta"]}</b></div>'
        f'<div style="display:flex; align-items:flex-start;">{pasos_html}</div>'
        f'</div>'
    )

import datetime as dt

def calcular_prediccion(orientacion: pd.DataFrame) -> dict:
    fecha_inicio = dt.date(2026, 7, 10)
    fecha_fin = dt.date(2026, 11, 30)
    hoy = dt.date.today()

    dias_totales = (fecha_fin - fecha_inicio).days
    dias_transcurridos = max(0, min((hoy - fecha_inicio).days, dias_totales))
    dias_restantes = max(0, (fecha_fin - hoy).days)
    pct_tiempo = round((dias_transcurridos / dias_totales) * 100, 1) if dias_totales else 0

    estado = orientacion[CAMPO_ESTADO_FCS].astype(str).str.strip()
    listos = estado != ""  # cualquier valor no vacío = "Listo para reportar" o ya "Reportado"

    paquete = orientacion["TIPO DE PAQUETE DE SERVICIO"].astype(str).str.strip().str.upper()

    listos_basico = (listos & (paquete == "BÁSICO")).sum()
    listos_especializado = (listos & (paquete == "ESPECIALIZADO")).sum()
    listos_total = listos.sum()

    def pct(num, den):
        return round((num / den) * 100, 1) if den else 0

    return {
        "hoy": hoy.strftime("%d/%m/%Y"),
        "dias_totales": dias_totales,
        "dias_restantes": dias_restantes,
        "pct_tiempo": pct_tiempo,
        "basico": {"real": listos_basico, "meta": META_TOTAL_BASICO, "pct_real": pct(listos_basico, META_TOTAL_BASICO)},
        "especializado": {"real": listos_especializado, "meta": META_TOTAL_ESPECIALIZADO, "pct_real": pct(listos_especializado, META_TOTAL_ESPECIALIZADO)},
        "total": {"real": listos_total, "meta": META_TOTAL_PROGRAMA, "pct_real": pct(listos_total, META_TOTAL_PROGRAMA)},
    }


def html_barra_prediccion(etiqueta: str, real_pct: float, esperado_pct: float, real_num: int, meta_num: int) -> str:
    color_barra = "#FD531E" if real_pct >= esperado_pct else "#821F0D"
    ancho_real = min(real_pct, 100)
    ancho_esperado = min(esperado_pct, 100)
    diferencia = round(real_pct - esperado_pct, 1)
    signo = "+" if diferencia >= 0 else ""
    color_dif = "#1E8E3E" if diferencia >= 0 else "#821F0D"

    return (
        f'<div style="margin-bottom:14px;">'
        f'<div style="display:flex; justify-content:space-between; font-size:12px; color:#656A71; margin-bottom:4px;">'
        f'<span><b style="color:#292929;">{etiqueta}</b> — {real_num}/{meta_num} ({real_pct}%)</span>'
        f'<span style="color:{color_dif}; font-weight:bold;">{signo}{diferencia}% vs ritmo esperado</span>'
        f'</div>'
        f'<div style="position:relative; background-color:#EAEAEA; border-radius:4px; height:14px; width:100%;">'
        f'<div style="background-color:{color_barra}; width:{ancho_real}%; height:14px; border-radius:4px;"></div>'
        f'<div style="position:absolute; top:-3px; left:{ancho_esperado}%; width:2px; height:20px; background-color:#292929;"></div>'
        f'</div>'
        f'</div>'
    )


def html_franja_prediccion(pred: dict) -> str:
    barra_basico = html_barra_prediccion("Básico", pred["basico"]["pct_real"], pred["pct_tiempo"], pred["basico"]["real"], pred["basico"]["meta"])
    barra_especializado = html_barra_prediccion("Especializado", pred["especializado"]["pct_real"], pred["pct_tiempo"], pred["especializado"]["real"], pred["especializado"]["meta"])
    barra_total = html_barra_prediccion("Total", pred["total"]["pct_real"], pred["pct_tiempo"], pred["total"]["real"], pred["total"]["meta"])

    return (
        f'<div style="background-color:#FFFFFF; border:1px solid #EAEAEA; border-radius:10px; padding:16px 20px; margin-bottom:16px;">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">'
        f'<span style="font-size:13px; color:#656A71;">Proyecto: 10/07/2026 — 30/11/2026 &nbsp;·&nbsp; Hoy: {pred["hoy"]}</span>'
        f'<span style="font-size:13px; color:#292929; font-weight:bold;">⏳ {pred["dias_restantes"]} días restantes &nbsp;|&nbsp; {pred["pct_tiempo"]}% del tiempo transcurrido</span>'
        f'</div>'
        f'{barra_basico}{barra_especializado}{barra_total}'
        f'<div style="font-size:11px; color:#656A71; margin-top:4px;">La línea negra marca dónde deberías estar según el tiempo transcurrido. Verde/rojo indica si vas adelante o atrás del ritmo esperado.</div>'
        f'</div>'
    )