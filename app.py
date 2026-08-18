# app.py
import streamlit as st
import pandas as pd
import plotly.express as px
from cargar_datos import cargar_fuente
from normalizador import normalizar_columna_cedula
from column_mapping import CAMPO_ENTREGADO, MAPEO_CEDULA

st.set_page_config(page_title="Control STC 3.0", layout="wide")

@st.cache_data(ttl=600)
def cargar_general():
    df, _ = cargar_fuente("general")
    df = normalizar_columna_cedula(df, MAPEO_CEDULA["general"])
    return df

col_logo1, col_logo2, col_titulo = st.columns([1, 1, 4])
with col_logo1:
    st.image("assets/Logo_STC_3_0.png", width=140)
with col_logo2:
    st.image("assets/logo-Kuepa.png", width=140)
with col_titulo:
    st.markdown(
        "<h1 style='color:#292929; margin-top:10px;'>Control de Calidad STC 3.0</h1>",
        unsafe_allow_html=True,
    )

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Consulta por CC", "📄 Compilador FCS", "⏰ Alertas por tiempos", "📊 Overview", "🌐 Dashboard Proyecto",
])

# =========================================================
# TAB 1: Consulta por CC
# =========================================================
with tab1:
    try:
        df = cargar_general()
    except Exception as e:
        st.error("No se pudo conectar con Google Sheets (posible bache de red). Intenta de nuevo.")
        st.exception(e)  # TEMPORAL — para diagnosticar, borrar después
        if st.button("🔄 Reintentar"):
            st.cache_data.clear()
            st.rerun()
        st.stop()

    col1, col2, col3 = st.columns(3)
    with col1:
        paquetes = ["Todos"] + sorted(df["Paquete"].dropna().unique().tolist())
        filtro_paquete = st.selectbox("Paquete", paquetes)
    with col2:
        estados = ["Todos"] + sorted(df["Momento del proceso"].dropna().unique().tolist())
        filtro_estado = st.selectbox("Estado / Etapa", estados)
    with col3:
        filtro_cc = st.text_input("Buscar por CC (parcial o completo)")

    df_filtrado = df.copy()
    if filtro_paquete != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Paquete"] == filtro_paquete]
    if filtro_estado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["Momento del proceso"] == filtro_estado]
    if filtro_cc:
        df_filtrado = df_filtrado[df_filtrado["cedula_norm"].str.contains(filtro_cc, na=False)]

    st.write(f"**{len(df_filtrado)} personas encontradas**")

    columnas_mostrar = [
        "CC Prospecto", "Nombre completo", "ID CRM", "ID SIS",
        "Paquete", "JCO", "¿Es JCO?", "Resultado del VRD",
        "Momento del proceso", "Estado CRM", "Reporte",
        "Estado de la formación",
    ]
    columnas_mostrar = [c for c in columnas_mostrar if c in df_filtrado.columns]
    st.dataframe(df_filtrado[columnas_mostrar], width='stretch')

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
    st.dataframe(df_fcs.iloc[:, :FCS_ULTIMA_COLUMNA], width='stretch')

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
    from analitica import cargar_todo, generar_resumen, campos_vacios_fcs

    @st.cache_data(ttl=600)
    def cargar_analitica():
        f = cargar_todo()
        resumen = generar_resumen(f)
        vacios = campos_vacios_fcs(f["orientacion_consolidado"])
        return resumen, vacios

    resumen, vacios = cargar_analitica()

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
        fig_resumen, width='stretch',
        on_select="rerun", selection_mode="points", key="grafica_resumen",
    )

    puntos = evento.get("selection", {}).get("points", []) if evento else []
    if puntos:
        caso_clic = puntos[0]["y"]
        st.markdown(f"### Detalle: {caso_clic}")
        tabla_clic = resumen[caso_clic]
        st.write(f"**{len(tabla_clic)} registros**")
        st.dataframe(tabla_clic, width='stretch')
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
        fig_vacios, width='stretch',
        on_select="rerun", selection_mode="points", key="grafica_vacios",
    )

    puntos_vacios = evento_vacios.get("selection", {}).get("points", []) if evento_vacios else []
    if puntos_vacios:
        campo_clic = puntos_vacios[0]["y"]
        st.markdown(f"### Cédulas con '{campo_clic}' vacío")
        detalle_vacio = vacios[vacios["campo_vacio"] == campo_clic]
        st.dataframe(detalle_vacio, width='stretch')
        csv_vacio = detalle_vacio.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("⬇️ Descargar (CSV)", csv_vacio, f"vacios_{campo_clic}.csv", "text/csv")
    else:
        st.info("Haz clic en una barra para ver qué cédulas tienen ese campo vacío.")

# =========================================================
# TAB 4: Overview
# =========================================================
with tab4:
    from analitica import cargar_todo, cargar_metas, resumen_looker, tabla_estados, serie_temporal

    @st.cache_data(ttl=600)
    def cargar_dashboard():
        f = cargar_todo()
        metas = cargar_metas()
        return f, metas

    f, metas = cargar_dashboard()

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
                exito, mensaje = enviar_reporte(destinatarios, r, tabla_para_reporte)
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
        st.dataframe(tabla, width='stretch', hide_index=True)

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
        st.plotly_chart(fig_momento, width='stretch')

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
        st.plotly_chart(fig_v, width='stretch')

        st.markdown("#### Orientación")
        ver_semanal_orient = st.toggle("📅 Gráfica por semanas", value=False, key="toggle_orient")
        granularidad_orient = "Semanal" if ver_semanal_orient else "Diaria"
        serie_orientacion = serie_temporal(f["general"], "Fecha Orientación", granularidad_orient)
        fig_o = px.line(serie_orientacion, x="Fecha", y="Cantidad", markers=True, text="Cantidad")
        fig_o.update_traces(line_color="#821F0D", textposition="top center")
        fig_o.update_layout(height=350)
        st.plotly_chart(fig_o, width='stretch')

        st.markdown("#### Formación")
        ver_semanal_form = st.toggle("📅 Gráfica por semanas", value=False, key="toggle_form")
        granularidad_form = "Semanal" if ver_semanal_form else "Diaria"
        serie_formacion = serie_temporal(f["general"], "Fecha clases", granularidad_form)
        fig_f = px.line(serie_formacion, x="Fecha", y="Cantidad", markers=True, text="Cantidad")
        fig_f.update_traces(line_color="#292929", textposition="top center")
        fig_f.update_layout(height=350)
        st.plotly_chart(fig_f, width='stretch')

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