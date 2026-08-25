"""Puerto a Python de FCS.gs — cruce con el Consolidado FCS."""
from typing import Dict, List, Optional, Tuple

from utilidades import normalizar_documento, quitar_acentos

FCS_ENCABEZADOS = {
    'numeroDocumento': 'NUMERO DE DOCUMENTO',
    'paquete': 'TIPO DE PAQUETE DE SERVICIO',
    'jco': 'EN RUTA DEL PROGRAMA JOVENES CON OPORTUNIDADES',
}


def cargar_fcs(gc, config, avisos: Optional[List[Tuple[str, str]]] = None) -> Dict[str, dict]:
    """
    Lee el FCS completo en una sola llamada (get_all_values) y arma un mapa
    numeroDocumento -> {paquete, jco}. Si algo falla, agrega un aviso a
    `avisos` (lista de (titulo, mensaje), igual espíritu que los toast de
    Apps Script) y devuelve un mapa vacío — el resto del script sigue
    funcionando igual que sin FCS.
    """
    avisos = avisos if avisos is not None else []
    mapa: Dict[str, dict] = {}
    if not config.USAR_FCS:
        return mapa

    try:
        ss_fcs = gc.open_by_key(config.FCS_SPREADSHEET_ID)
        try:
            hoja = ss_fcs.worksheet(config.FCS_HOJA)
        except Exception:
            avisos.append(('Aviso', f'No se encontró la pestaña "{config.FCS_HOJA}" en el FCS. Se continúa sin cruce FCS.'))
            return mapa

        datos = hoja.get_all_values()  # una sola lectura en bloque

        fila_encabezado = -1
        col_index = {}
        for f in range(min(20, len(datos))):
            idx = _mapear_encabezados(datos[f])
            if idx['numeroDocumento'] != -1:
                fila_encabezado = f
                col_index = idx
                break

        if fila_encabezado == -1:
            avisos.append(('Aviso', 'No se encontró la columna "Número de documento" en las primeras filas del FCS. Se continúa sin cruce FCS.'))
            return mapa

        for f in range(fila_encabezado + 1, len(datos)):
            fila = datos[f]
            doc = normalizar_documento(_valor(fila, col_index['numeroDocumento']))
            if not doc:
                continue
            mapa[doc] = {
                'paquete': str(_valor(fila, col_index.get('paquete', -1)) or '').strip().upper(),
                'jco': str(_valor(fila, col_index.get('jco', -1)) or '').strip().upper(),
            }
    except Exception as e:
        avisos.append(('Aviso', f'No se pudo leer el FCS ({e}). Se continúa sin cruce FCS.'))

    return mapa


def _valor(fila: List[str], indice: int):
    if indice == -1 or indice >= len(fila):
        return ''
    return fila[indice]


def _mapear_encabezados(fila: List[str]) -> dict:
    resultado = {'numeroDocumento': -1, 'paquete': -1, 'jco': -1}
    for c, celda in enumerate(fila):
        texto = quitar_acentos(str(celda or '').strip().upper())
        for clave, encabezado in FCS_ENCABEZADOS.items():
            if texto == encabezado:
                resultado[clave] = c
    return resultado
