# app.py
import streamlit as st
st.set_page_config(page_title="Control STC 3.0", layout="wide")

import pandas as pd
import plotly.express as px
from analitica import carga_personalizada
from cargar_datos import cargar_fuente
from normalizador import normalizar_columna_cedula
from column_mapping import CAMPO_ENTREGADO, MAPEO_CEDULA

@st.cache_data(ttl=600)
def cargar_general():
    df, _ = cargar_fuente("general")
    df = normalizar_columna_cedula(df, MAPEO_CEDULA["general"])
    return df

col_logo1, col_logo2, col_titulo, col_menu = st.columns([1, 1, 3, 1])
with col_logo1:
    st.image("assets/Logo_STC_3_0.png", width=140)
with col_logo2:
    st.image("assets/logo-Kuepa.png", width=140)
with col_titulo:
    st.markdown(
        "<h1 style='color:#292929; margin-top:10px;'>Control de Calidad STC 3.0</h1>",
        unsafe_allow_html=True,
    )

with col_menu:
    st.markdown("<div style='margin-top:35px;'></div>", unsafe_allow_html=True)
    with st.popover("Acciones", use_container_width=True):
        st.markdown("**Webhooks**")

        from webhooks import disparar_webhook, WEBHOOKS_REGISTRADOS

        for wh in WEBHOOKS_REGISTRADOS:
            key_confirmar = f"confirmar_{wh['id']}"
            if key_confirmar not in st.session_state:
                st.session_state[key_confirmar] = False

            if not st.session_state[key_confirmar]:
                if st.button(wh["etiqueta"], key=f"btn_{wh['id']}"):
                    if wh.get("confirmar"):
                        st.session_state[key_confirmar] = True
                        st.rerun()
                    else:
                        with st.spinner(f"Ejecutando {wh['etiqueta']}..."):
                            exito, mensaje = disparar_webhook(
                                wh["url_env"], wh["header_nombre_env"], wh["header_valor_env"]
                            )
                        if exito:
                            st.success(mensaje)
                        else:
                            st.error(mensaje)
            else:
                st.warning(wh.get("mensaje_confirmacion", "¿Confirmas ejecutar esta acción?"))
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✅ Sí", key=f"si_{wh['id']}"):
                        with st.spinner(f"Ejecutando {wh['etiqueta']}..."):
                            exito, mensaje = disparar_webhook(
                                wh["url_env"], wh["header_nombre_env"], wh["header_valor_env"]
                            )
                        st.session_state[key_confirmar] = False
                        if exito:
                            st.success(mensaje)
                        else:
                            st.error(mensaje)
                with c2:
                    if st.button("❌ No", key=f"no_{wh['id']}"):
                        st.session_state[key_confirmar] = False
                        st.rerun()
            st.markdown("<div style='margin-bottom:4px;'></div>", unsafe_allow_html=True)

        st.markdown("**Reporte por correo**")
        st.caption("Ve al tab Overview para enviar el reporte con el detalle completo.")

from analitica import cargar_todo_cache, calcular_prediccion, html_franja_prediccion

with carga_personalizada("Calculando proyección de avance..."):
    f_prediccion = cargar_todo_cache()
    pred = calcular_prediccion(f_prediccion["general"])

st.markdown(html_franja_prediccion(pred), unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Consulta por CC", "📄 Compilador FCS", "⏰ Alertas por tiempos", "📊 Overview", "🌐 Dashboard Proyecto",
])

# =========================================================
# TAB 1: Consulta por CC
# =========================================================
with tab1:
    with carga_personalizada("Cargando información general..."):
        df = cargar_general()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        paquetes = ["Todos"] + sorted(df["Paquete"].dropna().unique().tolist())
        filtro_paquete = st.selectbox("Paquete", paquetes)
    with col2:
        estados = ["Todos"] + sorted(df["Momento del proceso"].dropna().unique().tolist())
        filtro_estado = st.selectbox("Estado / Etapa", estados)
    with col3:
        eventos = ["Todos"] + sorted(df["Evento/Base"].dropna().unique().tolist())
        filtro_evento = st.selectbox("Evento/Base", eventos)
    with col4:
        hitos = ["Todos"] + sorted(df["Hito"].dropna().unique().tolist())
        filtro_hito = st.selectbox("Hito", hitos)
    with col5:
        filtro_cc = st.text_input("Buscar por CC (parcial o completo)")

    df_filtrado = df.copy()
    if filtro_paquete != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Paquete"] == filtro_paquete]
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Momento del proceso"] == filtro_estado]
    if filtro_evento != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Evento/Base"] == filtro_evento]
    if filtro_hito != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Hito"] == filtro_hito]
    if filtro_cc:
        df_filtrado = df_filtrado[df_filtrado["cedula_norm"].str.contains(filtro_cc, na=False)]

    st.write(f"**{len(df_filtrado)} personas encontradas**")

    columnas_mostrar = [
        "CC Prospecto", "Nombre completo", "ID CRM", "ID SIS",
        "Paquete", "JCO", "¿Es JCO?", "Resultado del VRD",
        "Momento del proceso", "Estado CRM", "Reporte",
        "Estado de la formación", "Evento/Base", "Hito",
    ]
    columnas_mostrar = [c for c in columnas_mostrar if c in df_filtrado.columns]
    st.dataframe(df_filtrado[columnas_mostrar], use_container_width=True)

    # --- Diagrama de ruta si la búsqueda de CC da un resultado único ---
    if filtro_cc and len(df_filtrado) == 1:
        from analitica import calcular_progreso_ruta, html_diagrama_ruta, cargar_todo_cache

        with carga_personalizada("Calculando progreso de la ruta..."):
            f_ruta = cargar_todo_cache()
            cedula_encontrada = df_filtrado.iloc[0]["cedula_norm"]
            general_normalizado = normalizar_columna_cedula(f_ruta["general"], MAPEO_CEDULA["general"])
            progreso = calcular_progreso_ruta(
                cedula_encontrada, general_normalizado,
                f_ruta["orientacion_consolidado"], f_ruta["encuesta_basico_jco"], f_ruta["encuesta_especializado"],
            )

        st.markdown("#### Progreso de ruta")
        st.markdown(html_diagrama_ruta(progreso), unsafe_allow_html=True)

    # --- Descarga y envío por correo de la tabla filtrada ---
    st.divider()
    col_desc, col_correo = st.columns(2)

    with col_desc:
        csv_filtrado = df_filtrado[columnas_mostrar].to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ Descargar tabla filtrada (CSV)", csv_filtrado, "consulta_cc.csv", "text/csv")

    with col_correo:
        with st.popover("📧 Enviar esta tabla por correo"):
            destinatarios_tabla = st.text_input("Correos (separados por coma)", key="correo_tabla_cc")
            if st.button("Enviar", key="btn_enviar_tabla_cc"):
                destinatarios = [d.strip() for d in destinatarios_tabla.split(",") if d.strip()]
                if not destinatarios:
                    st.warning("Escribe al menos un correo.")
                else:
                    from reportes import enviar_tabla_generica
                    with carga_personalizada("Enviando tabla por correo..."):
                        exito, mensaje = enviar_tabla_generica(
                            destinatarios, "Consulta por CC — Tabla filtrada", df_filtrado[columnas_mostrar]
                        )
                    if exito:
                        st.success(mensaje)
                    else:
                        st.error(mensaje)

# =========================================================
# TAB 2: Compilador FCS (siguiente paso)
# =========================================================
with tab2:
    df_or, _ = cargar_fuente("orientacion_consolidado")

    from column_mapping import (
        CAMPO_FECHA_FCS, CAMPO_ESTADO_FCS, CAMPO_PAQUETE_FCS,
        CAMPO_NO_PAGO, FCS_ULTIMA_COLUMNA,
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        paquetes_fcs = ["Todos"] + sorted(df_or[CAMPO_PAQUETE_FCS].dropna().unique().tolist())
        f_paquete = st.selectbox("Paquete", paquetes_fcs, key="fcs_paquete")

    with col2:
        if CAMPO_ESTADO_FCS in df_or.columns:
            estados_fcs = ["Todos"] + sorted(df_or[CAMPO_ESTADO_FCS].dropna().unique().tolist())
            f_estado = st.selectbox("Estado FCS", estados_fcs, key="fcs_estado")
        else:
            st.warning(f"No encuentro la columna '{CAMPO_ESTADO_FCS}' todavía en la hoja.")
            f_estado = "Todos"

    with col3:
        f_no_pago = st.text_input("No. PAGO (parcial o completo)", key="fcs_no_pago")

    with col4:
        fechas_validas = pd.to_datetime(df_or[CAMPO_FECHA_FCS], dayfirst=True, errors="coerce").dropna()
        if len(fechas_validas) > 0:
            rango = st.date_input(
                "Rango de Fecha de Atención",
                value=(fechas_validas.min(), fechas_validas.max()),
                key="fcs_rango_fecha",
            )
        else:
            rango = None

    # --- Aplicar filtros ---
    df_fcs = df_or.copy()
    df_fcs["_fecha_parseada"] = pd.to_datetime(df_fcs[CAMPO_FECHA_FCS], dayfirst=True, errors="coerce")

    if f_paquete != "Todos":
        df_fcs = df_fcs[df_fcs[CAMPO_PAQUETE_FCS] == f_paquete]
    if f_estado != "Todos" and CAMPO_ESTADO_FCS in df_fcs.columns:
        df_fcs = df_fcs[df_fcs[CAMPO_ESTADO_FCS] == f_estado]
    if f_no_pago:
        df_fcs = df_fcs[df_fcs[CAMPO_NO_PAGO].astype(str).str.contains(f_no_pago, na=False)]
    if rango and len(rango) == 2:
        inicio, fin = pd.Timestamp(rango[0]), pd.Timestamp(rango[1])
        df_fcs = df_fcs[df_fcs["_fecha_parseada"].between(inicio, fin)]

    st.write(f"**{len(df_fcs)} registros encontrados**")
    st.dataframe(df_fcs.iloc[:, :FCS_ULTIMA_COLUMNA], use_container_width=True)

    # --- Descarga con formato oficial FCS (columnas A hasta CE únicamente) ---
    csv_fcs = df_fcs.iloc[:, :FCS_ULTIMA_COLUMNA].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="⬇️ Descargar FCS (CSV)",
        data=csv_fcs,
        file_name="FCS_compilado.csv",
        mime="text/csv",
    )

# =========================================================
# TAB 3: Análisis de datos
# =========================================================
with tab3:
    from analitica import cargar_todo_cache, generar_resumen, campos_vacios_fcs

    with carga_personalizada("Cargando análisis de datos..."):
        f_tab3 = cargar_todo_cache()
        resumen = generar_resumen(f_tab3)
        vacios = campos_vacios_fcs(f_tab3["orientacion_consolidado"])

    st.subheader("Resumen de inconsistencias por caso")

    df_resumen = pd.DataFrame([
        {"Caso": nombre, "Cantidad": len(tabla)} for nombre, tabla in resumen.items()
    ]).sort_values("Cantidad", ascending=True)

    fig_resumen = px.bar(
        df_resumen, x="Cantidad", y="Caso", orientation="h", text="Cantidad",
    )
    fig_resumen.update_traces(marker_color="#821F0D", textposition="outside", cliponaxis=False)
    fig_resumen.update_layout(
        height=450,
        showlegend=False,
        margin=dict(l=220, r=60, t=20, b=20),  # margen izquierdo amplio para que no se corten las etiquetas
        yaxis=dict(automargin=True),
    )

    evento = st.plotly_chart(
        fig_resumen, use_container_width=True,
        on_select="rerun", selection_mode="points", key="grafica_resumen",
    )

    puntos = evento.get("selection", {}).get("points", []) if evento else []
    if puntos:
        caso_clic = puntos[0]["y"]
        st.markdown(f"### Detalle: {caso_clic}")
        tabla_clic = resumen[caso_clic]
        st.write(f"**{len(tabla_clic)} registros**")
        st.dataframe(tabla_clic, use_container_width=True)
        csv_clic = tabla_clic.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ Descargar este caso (CSV)", csv_clic, f"{caso_clic}.csv", "text/csv")
    else:
        st.info("Haz clic en una barra para ver el detalle de ese caso.")

    st.divider()
    st.subheader("Auditoría de campos vacíos en el FCS (columnas A–CE)")

    top_vacios = vacios["campo_vacio"].value_counts().reset_index()
    top_vacios.columns = ["Campo", "Cantidad"]
    top_vacios = top_vacios.sort_values("Cantidad", ascending=True).tail(20)

    fig_vacios = px.bar(
        top_vacios, x="Cantidad", y="Campo", orientation="h", text="Cantidad",
    )
    fig_vacios.update_traces(marker_color="#FD531E", textposition="outside", cliponaxis=False)
    fig_vacios.update_layout(
        height=600,
        showlegend=False,
        margin=dict(l=280, r=60, t=20, b=20),
        yaxis=dict(automargin=True),
    )

    evento_vacios = st.plotly_chart(
        fig_vacios, use_container_width=True,
        on_select="rerun", selection_mode="points", key="grafica_vacios",
    )

    puntos_vacios = evento_vacios.get("selection", {}).get("points", []) if evento_vacios else []
    if puntos_vacios:
        campo_clic = puntos_vacios[0]["y"]
        st.markdown(f"### Cédulas con '{campo_clic}' vacío")
        detalle_vacio = vacios[vacios["campo_vacio"] == campo_clic]
        st.dataframe(detalle_vacio, use_container_width=True)
        csv_vacio = detalle_vacio.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ Descargar (CSV)", csv_vacio, f"vacios_{campo_clic}.csv", "text/csv")
    else:
        st.info("Haz clic en una barra para ver qué cédulas tienen ese campo vacío.")

# =========================================================
# TAB 4: Overview
# =========================================================
with tab4:
    from analitica import cargar_todo_cache, cargar_metas, resumen_looker, tabla_estados, serie_temporal

    with carga_personalizada("Cargando datos del overview..."):
        f = cargar_todo_cache()
        metas = cargar_metas()

    def tarjeta(valor, etiqueta, color="#656A71", progreso=None):
        barra_html = ""
        if progreso is not None:
            progreso_clamp = max(0, min(100, progreso))
            barra_html = (
                f'<div style="background-color:#EAEAEA; border-radius:4px; height:6px; margin-top:10px;">'
                f'<div style="background-color:{color}; width:{progreso_clamp}%; height:6px; border-radius:4px;"></div>'
                f'</div>'
            )
        html = (
            f'<div style="background-color:#FFFFFF; border-left:4px solid {color}; padding:16px 18px; '
            f'border-radius:8px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,0.08);">'
            f'<div style="font-size:12px; color:#656A71; text-transform:uppercase; letter-spacing:0.5px;">{etiqueta}</div>'
            f'<div style="font-size:28px; color:#292929; font-weight:700; margin-top:4px;">{valor}</div>'
            f'{barra_html}'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    excluir_entregados = st.toggle(
        "Ver solo pendientes por entregar (excluye quienes ya tienen 'Hito' registrado)",
        value=False,
    )

    r = resumen_looker(f["general"], metas, excluir_entregados=excluir_entregados)

    st.subheader(f"Dashboard General — mes en curso: {r['mes_actual']}")

    # ============================================================
    # SECCIÓN 1: Datos generales (KPIs)
    # ============================================================
    with st.expander("📊 Datos generales", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1: tarjeta(r["leads"], "Leads en CRM", "#656A71")
        with c2: tarjeta(r["matriculados"], "Matriculados CRM", "#656A71")
        with c3: tarjeta(r["en_proceso"], "En proceso (Verificación)", "#656A71")
        with c4: tarjeta(f"{r['avance_fecha_verificacion']}%", "Avance a la fecha (Verif.)", "#FD531E", progreso=r['avance_fecha_verificacion'])

        st.markdown("#### Orientación")
        c1, c2, c3, c4 = st.columns(4)
        with c1: tarjeta(r["orientados"], "Orientados (Total)", "#656A71")
        with c2: tarjeta(r["orientados_basicos"], "Orientados Básicos", "#656A71")
        with c3: tarjeta(r["orientados_especializados"], "Orientados Especializados", "#656A71")
        with c4: tarjeta(f"{r['avance_general_orientacion']}%", "Avance sobre meta total (5102)", "#FD531E", progreso=r['avance_general_orientacion'])

        st.markdown("#### Formación")
        c1, c2, c3 = st.columns(3)
        with c1: tarjeta(r["formados_en_curso"], "En curso", "#656A71")
        with c2: tarjeta(r["finalizados_formacion"], "Finalizados", "#656A71")
        with c3: tarjeta(f"{r['avance_general_formacion']}%", "Avance sobre meta Especializado", "#FD531E", progreso=r['avance_general_formacion'])

        st.markdown("#### Entregas")
        c1, c2 = st.columns(2)
        with c1: tarjeta(r["cantidad_entregados"], "Cantidad entregados", "#656A71")
        with c2: tarjeta(f"{r['avance_entregas']}%", "Avance sobre meta total (5102)", "#FD531E", progreso=r['avance_entregas'])

        st.divider()
        st.markdown("### 📧 Enviar reporte por correo")

        from reportes import enviar_reporte

        destinatarios_texto = st.text_input(
            "Correos destinatarios (separados por coma)",
            placeholder="persona1@kuepa.com, persona2@kuepa.com",
        )

        if st.button("Enviar reporte ahora"):
            destinatarios = [d.strip() for d in destinatarios_texto.split(",") if d.strip()]
            if not destinatarios:
                st.warning("Escribe al menos un correo destinatario.")
            else:
                tabla_para_reporte = tabla_estados(
                    f["general"], f["encuesta_basico_jco"], f["encuesta_especializado"],
                    excluir_entregados=excluir_entregados, por_paquete=True,
                )

                df_momento_reporte = f["general"].copy()
                if excluir_entregados and CAMPO_ENTREGADO in df_momento_reporte.columns:
                    from analitica import es_entregado
                    df_momento_reporte = df_momento_reporte[~es_entregado(df_momento_reporte[CAMPO_ENTREGADO])]
                conteo_momento_reporte = df_momento_reporte["Momento del proceso (Back UP)"].value_counts().reset_index()
                conteo_momento_reporte.columns = ["Etapa", "Cantidad"]
                conteo_momento_reporte = conteo_momento_reporte.sort_values("Etapa")

                series_reporte = {
                    "verificacion": serie_temporal(f["general"], "Fecha", "Semanal"),
                    "orientacion": serie_temporal(f["general"], "Fecha Orientación", "Semanal"),
                    "formacion": serie_temporal(f["general"], "Fecha finalización", "Semanal"),
                }

                exito, mensaje = enviar_reporte(destinatarios, r, tabla_para_reporte, conteo_momento_reporte, series_reporte)
                if exito:
                    st.success(mensaje)
                else:
                    st.error(mensaje)

    # ============================================================
    # SECCIÓN 2: Tabla de estados + gráfica de Momento del proceso
    # ============================================================
    with st.expander("📋 Tabla de procesos y estado actual", expanded=False):
        vista_paquete = st.toggle("Ver desglosado por paquete (Básico/Especializado)", value=False)
        tabla = tabla_estados(
            f["general"], f["encuesta_basico_jco"], f["encuesta_especializado"],
            excluir_entregados=excluir_entregados, por_paquete=vista_paquete,
        )
        st.dataframe(tabla, use_container_width=True, hide_index=True)

        st.markdown("#### Momento del proceso (Back UP)")
        df_momento = f["general"].copy()
        if excluir_entregados and CAMPO_ENTREGADO in df_momento.columns:
            from analitica import es_entregado
            df_momento = df_momento[~es_entregado(df_momento[CAMPO_ENTREGADO])]

        conteo_momento = df_momento["Momento del proceso (Back UP)"].value_counts().reset_index()
        conteo_momento.columns = ["Etapa", "Cantidad"]
        conteo_momento = conteo_momento.sort_values("Etapa")

        fig_momento = px.bar(conteo_momento, x="Etapa", y="Cantidad", text="Cantidad")
        fig_momento.update_traces(marker_color="#292929", textposition="outside")
        fig_momento.update_layout(height=450)
        st.plotly_chart(fig_momento, use_container_width=True)

    # ============================================================
    # SECCIÓN 3: Gráficas de evolución temporal
    # ============================================================
    with st.expander("📈 Evolución temporal por proceso", expanded=False):

        st.markdown("#### Verificación")
        ver_semanal_verif = st.toggle("📅 Gráfica por semanas", value=False, key="toggle_verif")
        granularidad_verif = "Semanal" if ver_semanal_verif else "Diaria"
        serie_verificacion = serie_temporal(f["general"], "Fecha", granularidad_verif)
        fig_v = px.line(serie_verificacion, x="Fecha", y="Cantidad", markers=True, text="Cantidad")
        fig_v.update_traces(line_color="#FD531E", textposition="top center")
        fig_v.update_layout(height=350)
        st.plotly_chart(fig_v, use_container_width=True)

        st.markdown("#### Orientación")
        ver_semanal_orient = st.toggle("📅 Gráfica por semanas", value=False, key="toggle_orient")
        granularidad_orient = "Semanal" if ver_semanal_orient else "Diaria"
        serie_orientacion = serie_temporal(f["general"], "Fecha Orientación", granularidad_orient)
        fig_o = px.line(serie_orientacion, x="Fecha", y="Cantidad", markers=True, text="Cantidad")
        fig_o.update_traces(line_color="#821F0D", textposition="top center")
        fig_o.update_layout(height=350)
        st.plotly_chart(fig_o, use_container_width=True)

        st.markdown("#### Formación")
        ver_semanal_form = st.toggle("📅 Gráfica por semanas", value=False, key="toggle_form")
        granularidad_form = "Semanal" if ver_semanal_form else "Diaria"
        serie_formacion = serie_temporal(f["general"], "Fecha finalización", granularidad_form)
        fig_f = px.line(serie_formacion, x="Fecha", y="Cantidad", markers=True, text="Cantidad")
        fig_f.update_traces(line_color="#292929", textposition="top center")
        fig_f.update_layout(height=350)
        st.plotly_chart(fig_f, use_container_width=True)

# =========================================================
# TAB 5: Dashboard
# =========================================================

with tab5:
    import streamlit.components.v1 as components

    st.subheader("Dashboard Proyecto")
    components.iframe(
        "https://datastudio.google.com/embed/reporting/a656828b-105a-43c4-88cc-99bde8b3ea07/page/p_nzkle3pm5d",
        height=800,
        scrolling=True,
    )