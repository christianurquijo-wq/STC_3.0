# column_mapping.py

MAPEO_CEDULA = {
    "general": "CC Prospecto",
    "verificacion": "Número Documento",
    "formacion": "Cedula",
    "orientacion_consolidado": "NÚMERO DE DOCUMENTO",
    "remisiones": "NÚMERO DE DOCUMENTO",
}

# Reglas de negocio confirmadas
CAMPO_JCO_GENERAL = "JCO"                          # texto SI/NO, tratar nan como "Pendiente"
CAMPO_FORMADO_GENERAL = "Estado de la formación"
VALOR_FORMADO = "FINALIZADO"
CAMPO_PAQUETE_GENERAL = "Paquete"
CAMPO_MOMENTO_PROCESO = "Momento del proceso"

# Campos rotos conocidos (no usar en lógica, solo reportar)
CAMPOS_ROTOS_CONOCIDOS = ["Tipo de paquete reportado", "Resultado del VRD"]

# --- Config para el compilador FCS (Tab 2) ---
CAMPO_FECHA_FCS = "FECHA DE ATENCIÓN"
CAMPO_ESTADO_FCS = "Estado Entregable"          # <-- AJUSTA AQUÍ si le pusiste otro nombre exacto
CAMPO_PAQUETE_FCS = "TIPO DE PAQUETE DE SERVICIO"
CAMPO_NO_PAGO = "No. PAGO"
FCS_ULTIMA_COLUMNA = 83   # A hasta CE = primeras 83 columnas (índice 0 a 82)

# --- Sección 4: Dashboard tipo Looker ---
CAMPO_MOMENTO_BACKUP = "Momento del proceso (Back UP)"
CAMPO_ENTREGADO = "Hito"  
META_TOTAL_BASICO = 3061
META_TOTAL_ESPECIALIZADO = 2041
META_TOTAL_PROGRAMA = 5102
MESES_ORDEN = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
               "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]