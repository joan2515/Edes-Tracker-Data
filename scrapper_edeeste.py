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


def limpiar_texto(valor):
    if not valor:
        return ""
    return " ".join(str(valor).replace("\n", " ").split()).strip()


def extraer_fecha_cabecera(texto):
    dias = [
        "lunes", "martes", "miércoles", "miercoles",
        "jueves", "viernes", "sábado", "sabado", "domingo"
    ]
    patron = rf"({'|'.join(dias)})\s+\d{{1,2}}\s+de\s+[a-záéíóú]+(\s+del?\s+\d{{4}})?"
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        return match.group(0).strip().title()
    return None


def obtener_url_ultimo_pdf(session: requests.Session):
    print(f"[*] Consultando portal de Edeeste: {URL_PROGRAMA}")
    resp = session.get(URL_PROGRAMA, headers=HEADERS, timeout=25)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    url_pagina_intermedia = None

    exclusiones = [
        "sharer", "facebook.com", "twitter.com", "addtoany.com",
        "pluginsmarket.com", "wpdmpro.com"
    ]

    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        texto = link.get_text(strip=True).lower()

        if any(ignore in href.lower() for ignore in exclusiones):
            continue

        if href.lower().endswith(".pdf"):
            return urljoin(URL_PROGRAMA, href)

        if "/download/" in href.lower() or "wpdmdl=" in href or "descargar" in texto:
            url_pagina_intermedia = urljoin(URL_PROGRAMA, href)
            break

    if not url_pagina_intermedia:
        return None

    resp_sub = session.get(url_pagina_intermedia, headers=HEADERS, timeout=25)
    resp_sub.raise_for_status()
    html_sub = resp_sub.text

    match_downloadurl = re.search(r'data-downloadurl=["\']([^"\']+)["\']', html_sub)
    if match_downloadurl:
        return match_downloadurl.group(1).replace("&amp;", "&")

    match_wpdmdl = re.search(r"wpdmdl=(\d+)", html_sub)
    if match_wpdmdl:
        return f"{url_pagina_intermedia.rstrip('/')}/?wpdmdl={match_wpdmdl.group(1)}"

    match_post = re.search(r'id=["\']post-(\d+)["\']', html_sub)
    if match_post:
        return f"{url_pagina_intermedia.rstrip('/')}/?wpdmdl={match_post.group(1)}"

    return None


def procesar_panel_tabla(crop_page, fecha_default, contador_id_inicial):
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

            if "circuito" in texto_fila and "zonas de mantenimiento" in texto_fila:
                continue
            if "municipio" in texto_fila and "código" in texto_fila:
                continue
            if any(dia in texto_fila for dia in ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]) and len(celdas) <= 4:
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
                val_causa = celdas[7] if len(celdas) > 7 else "Mantenimiento preventivo"
            elif len(celdas) == 7:
                val_municipio = celdas[0]
                val_circuito = celdas[1]
                val_codigo = celdas[2]
                val_h_inicio = celdas[3]
                val_h_fin = celdas[4]
                val_zonas = celdas[5]
                val_causa = celdas[6]

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
                "motivo": val_causa if val_causa else "Mantenimiento preventivo",
            })
            contador_id += 1

    return mantenimientos_panel, contador_id, fecha_panel


def extraer_datos_edeeste():
    """Función principal exportable para extraer los datos de Edeeste."""
    session = requests.Session()
    session.headers.update(HEADERS)

    url_pdf = obtener_url_ultimo_pdf(session)
    if not url_pdf:
        print("[!] No se encontró ningún PDF en Edeeste.")
        return []

    print(f"[*] Descargando PDF de Edeeste: {url_pdf}")
    headers_descarga = HEADERS.copy()
    headers_descarga["Referer"] = URL_PROGRAMA

    resp = session.get(url_pdf, headers=headers_descarga, timeout=45, allow_redirects=True)
    resp.raise_for_status()

    if not resp.content.startswith(b"%PDF"):
        print("[!] El archivo obtenido de Edeeste no tiene cabecera PDF.")
        return []

    pdf_bytes = io.BytesIO(resp.content)
    mantenimientos_totales = []
    contador_id = 1

    with pdfplumber.open(pdf_bytes) as pdf:
        for num_pag, pagina in enumerate(pdf.pages, start=1):
            texto_p = pagina.extract_text() or ""
            if "TRABAJOS DE MANTENIMIENTOS" in texto_p and len(texto_p) < 200:
                continue

            ancho = pagina.width
            alto = pagina.height
            mitad_x = ancho / 2.0

            # Panel Izquierdo
            items_izq, contador_id, _ = procesar_panel_tabla(
                pagina.crop((0, 0, mitad_x, alto)), f"Página {num_pag} - Izq", contador_id
            )
            mantenimientos_totales.extend(items_izq)

            # Panel Derecho
            items_der, contador_id, _ = procesar_panel_tabla(
                pagina.crop((mitad_x, 0, ancho, alto)), f"Página {num_pag} - Der", contador_id
            )
            mantenimientos_totales.extend(items_der)

    print(f"[✓] Edeeste: {len(mantenimientos_totales)} cortes extraídos.")
    return mantenimientos_totales


if __name__ == "__main__":
    datos = extraer_datos_edeeste()
    with open("mantenimientos_edeeste.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
