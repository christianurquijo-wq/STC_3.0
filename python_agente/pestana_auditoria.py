"""
Pestaña de Auditoría de Calidad — para incrustar en tu app de Streamlit ya
publicada (la que ya tiene st.tabs() con la info del proyecto).

Uso en tu app.py:

    import pestana_auditoria

    tab_info, tab_otro, tab_auditoria = st.tabs(["Proyecto", "Otro", "🔍 Auditoría de calidad"])
    with tab_auditoria:
        pestana_auditoria.render()

Qué hace: en cuanto se abre la pestaña, LEE lo que ya está escrito en la Sheet
de reporte (Resumen/Hallazgos/Consumo) — no corre nada por sí sola. Muestra
métricas, las 3 tablas con filtros básicos, y un expander con los mismos 3
botones de acción (Ejecutar revisión / Diagnóstico / Estimar consumo) por si
los necesitas desde ahí mismo, sin cambiar de pestaña.
"""
import pandas as pd
import streamlit as st

from config import CAMPOS_PLATAFORMA, CONFIG
from google_clients import (
    obtener_cliente_sheets, obtener_credenciales, obtener_o_crear_hoja, obtener_servicio_drive,
)

ESTADOS = ('Verificado', 'Con novedad', 'No encontrado')


def _leer_hoja_como_df(ss, nombre_hoja: str) -> pd.DataFrame:
    ws = obtener_o_crear_hoja(ss, nombre_hoja)
    valores = ws.get_all_values()
    if len(valores) < 2:
        return pd.DataFrame(columns=valores[0] if valores else [])
    return pd.DataFrame(valores[1:], columns=valores[0])


def leer_resultados(ss) -> dict:
    """Lee las 3 hojas del reporte y las devuelve como DataFrames — separado de render() para poder testearlo sin Streamlit."""
    return {
        'resumen': _leer_hoja_como_df(ss, CONFIG.NOMBRE_HOJA_RESUMEN),
        'hallazgos': _leer_hoja_como_df(ss, CONFIG.NOMBRE_HOJA_HALLAZGOS),
        'consumo': _leer_hoja_como_df(ss, CONFIG.NOMBRE_HOJA_CONSUMO),
    }


def calcular_metricas(df_resumen: pd.DataFrame) -> dict:
    """
    Cuenta participantes y, por cada estado (Verificado/Con novedad/No
    encontrado), cuántas CELDAS de campo tienen ese estado en todo el
    resumen — función pura, testeable sin Streamlit ni Sheets.
    """
    campos_presentes = [c for c in CAMPOS_PLATAFORMA if c in df_resumen.columns]
    metricas = {'participantes': len(df_resumen), 'Verificado': 0, 'Con novedad': 0, 'No encontrado': 0}

    if df_resumen.empty or not campos_presentes:
        return metricas

    valores = df_resumen[campos_presentes].to_numpy().flatten()
    for estado in ESTADOS:
        metricas[estado] = int((valores == estado).sum())
    return metricas


def _fila_tiene_novedad(fila, campos_presentes) -> bool:
    return any(fila.get(c) == 'Con novedad' for c in campos_presentes)


def render():
    st.subheader('🔍 Auditoría de calidad documental — STC 3.0')

    try:
        credenciales = obtener_credenciales()
        gc = obtener_cliente_sheets(credenciales)
        ss = gc.open_by_key(CONFIG.REPORT_SPREADSHEET_ID)
    except Exception as e:
        st.error(f'No se pudo conectar con la Sheet de reporte: {e}')
        return

    if st.button('🔄 Actualizar', key='auditoria_refrescar'):
        st.rerun()

    resultados = leer_resultados(ss)
    df_resumen, df_hallazgos, df_consumo = resultados['resumen'], resultados['hallazgos'], resultados['consumo']

    metricas = calcular_metricas(df_resumen)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Participantes revisados', metricas['participantes'])
    col2.metric('Campos verificados', metricas['Verificado'])
    col3.metric('Campos con novedad', metricas['Con novedad'])
    col4.metric('Campos no encontrados', metricas['No encontrado'])

    if df_resumen.empty:
        st.info('Todavía no hay datos en la Sheet de reporte — corre una revisión desde el panel de abajo.')

    sub_resumen, sub_hallazgos, sub_consumo = st.tabs(['📋 Resumen por participante', '⚠️ Hallazgos', '📊 Consumo del agente'])

    with sub_resumen:
        if df_resumen.empty:
            st.caption('Sin datos todavía.')
        else:
            campos_presentes = [c for c in CAMPOS_PLATAFORMA if c in df_resumen.columns]
            col_f1, col_f2 = st.columns([2, 1])
            meses = sorted(df_resumen['Mes'].unique()) if 'Mes' in df_resumen.columns else []
            mes_sel = col_f1.multiselect('Filtrar por mes', meses, default=meses) if meses else []
            solo_con_novedad = col_f2.checkbox('Solo con alguna novedad')

            df_mostrar = df_resumen[df_resumen['Mes'].isin(mes_sel)] if meses else df_resumen
            if solo_con_novedad and campos_presentes:
                mask = df_mostrar.apply(lambda fila: _fila_tiene_novedad(fila, campos_presentes), axis=1)
                df_mostrar = df_mostrar[mask]

            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    with sub_hallazgos:
        if df_hallazgos.empty:
            st.caption('Sin hallazgos todavía.')
        else:
            col_f1, col_f2 = st.columns(2)
            campos_h = sorted(df_hallazgos['Campo'].unique()) if 'Campo' in df_hallazgos.columns else []
            campo_sel = col_f1.multiselect('Filtrar por campo', campos_h, default=campos_h) if campos_h else []
            texto_buscar = col_f2.text_input('Buscar por cédula o código')

            df_mostrar = df_hallazgos[df_hallazgos['Campo'].isin(campo_sel)] if campos_h else df_hallazgos
            if texto_buscar:
                mascara = (
                    df_mostrar['Participante (No. documento)'].astype(str).str.contains(texto_buscar, case=False, na=False)
                    | df_mostrar['Código'].astype(str).str.contains(texto_buscar, case=False, na=False)
                )
                df_mostrar = df_mostrar[mascara]

            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)

    with sub_consumo:
        if df_consumo.empty:
            st.caption('Sin registros de consumo todavía.')
        else:
            st.dataframe(df_consumo, use_container_width=True, hide_index=True)

    with st.expander('⚙️ Acciones (ejecutar / diagnosticar)'):
        col_a, col_b, col_c = st.columns(3)

        if col_a.button('▶ Ejecutar revisión', type='primary', key='auditoria_ejecutar'):
            import revision
            with st.spinner('Revisando documentos…'):
                try:
                    drive_service = obtener_servicio_drive(credenciales)
                    resultado = revision.ejecutar_revision(CONFIG, drive_service, gc)
                except Exception as e:
                    st.error(f'La revisión falló: {e}')
                else:
                    st.success(resultado['mensaje'])
                    for titulo, mensaje in resultado['avisos']:
                        st.warning(f'**{titulo}** — {mensaje}')
                    st.rerun()

        if col_b.button('🔧 Diagnóstico', key='auditoria_diagnostico'):
            import agente
            from diagnostico import buscar_primer_pdf
            from google_clients import descargar_bytes_archivo
            with st.spinner('Probando conexión…'):
                try:
                    drive_service = obtener_servicio_drive(credenciales)
                    primer_archivo = buscar_primer_pdf(drive_service, CONFIG.ROOT_FOLDER_ID)
                    if not primer_archivo:
                        st.warning('No se encontró ningún archivo para probar.')
                    else:
                        client = agente.obtener_cliente_gemini()
                        archivo_bytes = descargar_bytes_archivo(drive_service, primer_archivo['id'])
                        resultado = agente.probar_lectura_agente(client, CONFIG.MODELO_GEMINI, archivo_bytes)
                        if resultado['error']:
                            st.error(resultado['error'])
                        else:
                            st.success(f"OK ({resultado['tokens_usados']} token(s) usados) — {primer_archivo['name']}")
                except Exception as e:
                    st.error(f'Falló: {e}')

        if col_c.button('📊 Estimar consumo mensual', key='auditoria_estimar'):
            from consumo import estimar_consumo_mensual
            sh_consumo = obtener_o_crear_hoja(ss, CONFIG.NOMBRE_HOJA_CONSUMO)
            st.code(estimar_consumo_mensual(sh_consumo, CONFIG), language=None)
