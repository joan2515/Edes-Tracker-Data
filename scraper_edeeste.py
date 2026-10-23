import io
import json
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pdfplumber
import requests

URL_PROGRAMA = "https://edeeste.com.do/index.php/inicio/aprende-con-edeeste/programa-de-mantenimiento/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


def obtener_url_ultimo_pdf(session: requests.Session):
    """Rastrea el portal de Edeeste y construye la URL directa de descarga de WPDM."""
    print(f"[*] Consultando portal de Edeeste: {URL_PROGRAMA}")
    resp = session.get(URL_PROGRAMA, headers=HEADERS, timeout=25)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    url_pagina_intermedia = None

    exclusiones = [
        "sharer",
        "facebook.com",
        "twitter.com",
        "addtoany.com",
        "pluginsmarket.com",
        "wpdmpro.com",
    ]

    # 1. Encontrar la tarjeta de la semana actual
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        texto = link.get_text(strip=True).lower()

        if any(ignore in href.lower() for ignore in exclusiones):
            continue

        if href.lower().endswith(".pdf"):
            return urljoin(URL_PROGRAMA, href)

        if (
            "/download/" in href.lower()
            or "wpdmdl=" in href
            or "descargar" in texto
        ):
            url_pagina_intermedia = urljoin(URL_PROGRAMA, href)
            break

    if not url_pagina_intermedia:
        print("[!] No se encontró enlace al documento semanal.")
        return None

    print(f"[*] Siguiendo página intermedia: {url_pagina_intermedia}")
    resp_sub = session.get(url_pagina_intermedia, headers=HEADERS, timeout=25)
    resp_sub.raise_for_status()
    html_sub = resp_sub.text

    # 2. Buscar directamente con Regex la URL dentro de data-downloadurl
    match_downloadurl = re.search(r'data-downloadurl=["\']([^"\']+)["\']', html_sub)
    if match_downloadurl:
        url_descarga = match_downloadurl.group(1).replace("&amp;", "&")
        print(f"[✓] Encontrada en data-downloadurl: {url_descarga}")
        return url_descarga

    # 3. Buscar el parámetro wpdmdl en el contenido
    match_wpdmdl = re.search(r"wpdmdl=(\d+)", html_sub)
    if match_wpdmdl:
        id_descarga = match_wpdmdl.group(1)
        url_construida = f"{url_pagina_intermedia.rstrip('/')}/?wpdmdl={id_descarga}"
        print(f"[✓] URL construida por ID WPDM ({id_descarga}): {url_construida}")
        return url_construida

    # 4. Buscar el ID del post en la etiqueta <article id="post-XXXXX">
    match_post = re.search(r'id=["\']post-(\d+)["\']', html_sub)
    if match_post:
        id_post = match_post.group(1)
        url_construida = f"{url_pagina_intermedia.rstrip('/')}/?wpdmdl={id_post}"
        print(f"[✓] URL construida por ID de artículo ({id_post}): {url_construida}")
        return url_construida

    print("[!] No se pudo encontrar el enlace real de descarga dentro de la página.")
    return None


def limpiar_texto(valor):
    """Elimina saltos de línea y normaliza espacios en blanco."""
    if not valor:
        return ""
    return " ".join(str(valor).replace("\n", " ").split()).strip()


def extraer_fecha_cabecera(texto):
    """Busca franjas de fecha diaria (ej. LUNES 19 DE OCTUBRE, MIERCOLES 21 DE OCTUBRE)."""
    dias = [
        "lunes",
        "martes",
        "miércoles",
        "miercoles",
        "jueves",
        "viernes",
        "sábado",
        "sabado",
        "domingo",
    ]
    patron = rf"({'|'.join(dias)})\s+\d{{1,2}}\s+de\s+[a-záéíóú]+(\s+del?\s+\d{{4}})?"
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        return match.group(0).strip().title()
    return None


def procesar_panel_tabla(crop_page, fecha_default, contador_id_inicial):
    """Extrae los mantenimientos de medio panel horizontal de forma aislada."""
    mantenimientos_panel = []
    contador_id = contador_id_inicial

    texto_panel = crop_page.extract_text() or ""
    fecha_panel = extraer_fecha_cabecera(texto_panel) or fecha_default

    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_y_tolerance": 4,
        "snap_x_tolerance": 4,
        "intersection_x_tolerance": 15,
        "join_x_tolerance": 5,
        "join_y_tolerance": 5,
    }

    tablas = crop_page.extract_tables(table_settings=table_settings)
    if not tablas:
        tablas = crop_page.extract_tables()

    if not tablas:
        return mantenimientos_panel, contador_id, fecha_panel

    provincia_actual = "Santo Domingo"
    municipio_actual = "Santo Domingo Este"
    horario_actual = "9:20 a.m. a 5:20 p.m."

    for tabla in tablas:
        for fila in tabla:
            if not fila or len(fila) < 5:
                continue

            celdas = [limpiar_texto(c) for c in fila]
            texto_fila = " ".join(celdas).lower()

            # Omitir filas de encabezado o divisiones de día
            if "circuito" in texto_fila and "zonas de mantenimiento" in texto_fila:
                continue
            if "municipio" in texto_fila and "código" in texto_fila:
                continue
            if (
                any(
                    dia in texto_fila
                    for dia in [
                        "lunes",
                        "martes",
                        "miércoles",
                        "jueves",
                        "viernes",
                        "sábado",
                        "domingo",
                    ]
                )
                and len(celdas) <= 4
            ):
                f_ext = extraer_fecha_cabecera(" ".join(celdas))
                if f_ext:
                    fecha_panel = f_ext
                continue

            val_provincia = ""
            val_municipio = ""
            val_circuito = ""
            val_codigo = ""
            val_h_inicio = ""
            val_h_fin = ""
            val_zonas = ""
            val_causa = ""

            if len(celdas) >= 8:
                val_provincia = celdas[0]
                val_municipio = celdas[1]
                val_circuito = celdas[2]
                val_codigo = celdas[3]
                val_h_inicio = celdas[4]
                val_h_fin = celdas[5]
                val_zonas = celdas[6]
                val_causa = (
                    celdas[7] if len(celdas) > 7 else "Mantenimiento preventivo"
                )
            elif len(celdas) == 7:
                val_municipio = celdas[0]
                val_circuito = celdas[1]
                val_codigo = celdas[2]
                val_h_inicio = celdas[3]
                val_h_fin = celdas[4]
                val_zonas = celdas[5]
                val_causa = celdas[6]

            # Reconstruir "Santo Domingo" cuando se divida verticalmente en dos filas
            if val_provincia.lower() in ["santo", "domingo", "santo domingo"]:
                val_provincia = "Santo Domingo"

            if val_provincia:
                provincia_actual = val_provincia
            if val_municipio:
                municipio_actual = val_municipio

            if val_h_inicio and val_h_fin:
                horario_actual = f"{val_h_inicio} a {val_h_fin}"
            elif val_h_inicio:
                horario_actual = val_h_inicio

            if not val_circuito and not val_zonas:
                continue

            circuito_final = val_circuito if val_circuito else val_codigo
            if not circuito_final:
                circuito_final = "Circuito Edeeste"

            mantenimientos_panel.append({
                "id": f"edeeste_{contador_id}",
                "distribuidora": "EDEESTE",
                "provincia": provincia_actual,
                "municipio": municipio_actual,
                "circuito": circuito_final,
                "sector": val_zonas if val_zonas else "Sectores varios",
                "fecha": fecha_panel,
                "horario": horario_actual,
                "motivo": (
                    val_causa
                    if val_causa
                    else "Mantenimiento preventivo y adecuación de redes"
                ),
            })
            contador_id += 1

    return mantenimientos_panel, contador_id, fecha_panel


def extraer_datos_pdf(url_pdf, session: requests.Session):
    """Descarga el PDF y procesa los dos paneles paralelos (Izq/Der) de cada página."""
    print(f"[*] Descargando flujo binario desde: {url_pdf}")
    headers_descarga = HEADERS.copy()
    headers_descarga["Referer"] = URL_PROGRAMA

    resp = session.get(
        url_pdf, headers=headers_descarga, timeout=45, allow_redirects=True
    )
    resp.raise_for_status()

    if not resp.content.startswith(b"%PDF"):
        snippet = resp.text[:250].replace("\n", " ")
        raise ValueError(f"El servidor devolvió contenido no binario: {snippet}")

    pdf_bytes = io.BytesIO(resp.content)
    mantenimientos_totales = []
    contador_id = 1

    with pdfplumber.open(pdf_bytes) as pdf:
        print(f"[*] Total de páginas detectadas: {len(pdf.pages)}")

        for num_pag, pagina in enumerate(pdf.pages, start=1):
            texto_p = pagina.extract_text() or ""
            # Omitir portada institucional
            if "TRABAJOS DE MANTENIMIENTOS" in texto_p and len(texto_p) < 200:
                print(f"    - Página {num_pag}: Portada omitida")
                continue

            ancho = pagina.width
            alto = pagina.height
            mitad_x = ancho / 2.0

            # 1. Panel Izquierdo (ej. Lunes / Martes)
            bbox_izq = (0, 0, mitad_x, alto)
            panel_izq = pagina.crop(bbox_izq)
            items_izq, contador_id, fecha_izq = procesar_panel_tabla(
                panel_izq, "Semana - Izq", contador_id
            )
            print(
                f"    - Página {num_pag} [Panel Izquierdo - {fecha_izq}]:"
                f" {len(items_izq)} mantenimientos"
            )
            mantenimientos_totales.extend(items_izq)

            # 2. Panel Derecho (ej. Miércoles / Jueves)
            bbox_der = (mitad_x, 0, ancho, alto)
            panel_der = pagina.crop(bbox_der)
            items_der, contador_id, fecha_der = procesar_panel_tabla(
                panel_der, "Semana - Der", contador_id
            )
            print(
                f"    - Página {num_pag} [Panel Derecho - {fecha_der}]:"
                f" {len(items_der)} mantenimientos"
            )
            mantenimientos_totales.extend(items_der)

    print(f"[+] Total de mantenimientos extraídos de Edeeste: {len(mantenimientos_totales)}")
    return mantenimientos_totales


def extraer_datos_edeeste():
    """Función de entrada para main_scraper.py."""
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        url_pdf = obtener_url_ultimo_pdf(session)
        if not url_pdf:
            print("[!] No se pudo obtener la URL de descarga del PDF en Edeeste.")
            return []

        return extraer_datos_pdf(url_pdf, session)
    except Exception as e:
        print(f"[!] Error al procesar Edeeste: {e}")
        return []


def main():
    datos_edeeste = extraer_datos_edeeste()
    with open("mantenimientos_edeeste.json", "w", encoding="utf-8") as f:
        json.dump(datos_edeeste, f, ensure_ascii=False, indent=2)

    print("[✓] Archivo 'mantenimientos_edeeste.json' guardado exitosamente.")


if __name__ == "__main__":
    main()
