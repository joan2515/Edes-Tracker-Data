import io
import json
import re
from datetime import datetime, date, time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import pandas as pd
import requests

URL_EDENORTE = "https://edenorte.com.do/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
}

DIAS_SEMANA = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}

MESES_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}


def formatear_fecha(valor):
    """Convierte fechas (date, Timestamp o str '19-10-2026') a 'Lunes 19 de octubre del 2026'."""
    if pd.isna(valor):
        return "Fecha no especificada"

    if isinstance(valor, (datetime, date, pd.Timestamp)):
        nom_dia = DIAS_SEMANA.get(valor.weekday(), "")
        nom_mes = MESES_ES.get(valor.month, "")
        return f"{nom_dia} {valor.day} de {nom_mes} del {valor.year}"

    val_str = str(valor).strip()
    partes = val_str.replace("/", "-").split("-")
    if len(partes) == 3:
        try:
            if len(partes[0]) == 4:  # YYYY-MM-DD
                y, m, d = int(partes[0]), int(partes[1]), int(partes[2])
            else:  # DD-MM-YYYY
                d, m, y = int(partes[0]), int(partes[1]), int(partes[2])
            dt = date(y, m, d)
            nom_dia = DIAS_SEMANA.get(dt.weekday(), "")
            nom_mes = MESES_ES.get(m, "")
            return f"{nom_dia} {d} de {nom_mes} del {y}"
        except Exception:
            pass

    return val_str


def formatear_hora(valor):
    """Convierte horas (time, Timestamp o str '16:00') al formato legible '4:00 p.m.'."""
    if pd.isna(valor):
        return ""

    if isinstance(valor, time):
        h, m = valor.hour, valor.minute
    elif isinstance(valor, (datetime, pd.Timestamp)):
        h, m = valor.hour, valor.minute
    else:
        val_str = str(valor).strip()
        match = re.match(r"^(\d{1,2}):(\d{2})", val_str)
        if match:
            h, m = int(match.group(1)), int(match.group(2))
        else:
            return val_str

    periodo = "a.m." if h < 12 else "p.m."
    h12 = 12 if (h == 0 or h == 12) else (h % 12)
    return f"{h12}:{m:02d} {periodo}"


def obtener_url_ultimo_excel(session: requests.Session):
    """Rastrea la página de EdeNorte para ubicar la publicación semanal y su archivo Excel."""
    print(f"[*] Consultando portal de EdeNorte: {URL_EDENORTE}")
    resp = session.get(URL_EDENORTE, headers=HEADERS, timeout=25)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    url_publicacion = None

    # 1. Buscar la entrada de la galería que contenga el enlace al post de mantenimientos
    for link in soup.find_all("a", href=True):
        href = link["href"].strip()
        texto = link.get_text(strip=True).lower()

        if "mantenimientos-programados" in href.lower() or "mantenimiento" in texto:
            url_publicacion = urljoin(URL_EDENORTE, href)
            break

    # Si no está en el index, buscar en la sección de mantenimiento
    if not url_publicacion:
        url_seccion = urljoin(URL_EDENORTE, "mantenimiento-de-redes/")
        resp_sec = session.get(url_seccion, headers=HEADERS, timeout=25)
        if resp_sec.ok:
            soup_sec = BeautifulSoup(resp_sec.text, "html.parser")
            for link in soup_sec.find_all("a", href=True):
                href = link["href"].strip()
                if "mantenimientos-programados" in href.lower():
                    url_publicacion = urljoin(url_seccion, href)
                    break

    if not url_publicacion:
        print("[!] No se encontró el enlace de la publicación de la semana.")
        return None

    print(f"[*] Entrando a la publicación semanal: {url_publicacion}")
    resp_post = session.get(url_publicacion, headers=HEADERS, timeout=25)
    resp_post.raise_for_status()

    soup_post = BeautifulSoup(resp_post.text, "html.parser")

    # 2. Localizar el enlace de descarga que termine en .xlsx o .xls
    for link in soup_post.find_all("a", href=True):
        href = link["href"].strip()
        if href.lower().endswith(".xlsx") or href.lower().endswith(".xls"):
            url_excel = urljoin(url_publicacion, href)
            print(f"[✓] Enlace de descarga de Excel encontrado: {url_excel}")
            return url_excel

    print("[!] No se encontró enlace directo a Excel (.xlsx) en el post.")
    return None


def extraer_datos_excel(contenido_bytes):
    """Lee el libro de Excel y normaliza los mantenimientos a formato JSON."""
    excel_file = pd.ExcelFile(io.BytesIO(contenido_bytes))
    print(f"[*] Hojas disponibles en el archivo: {excel_file.sheet_names}")

    # Prioridad: 'Publicacion Externa' unifica todas las provincias en una sola hoja
    if "Publicacion Externa" in excel_file.sheet_names:
        hojas_a_procesar = ["Publicacion Externa"]
    else:
        # Fallback si cambia el nombre de la hoja consolidada
        hojas_a_procesar = [h for h in excel_file.sheet_names if "resumen" not in h.lower()]

    mantenimientos = []
    contador_id = 1

    for nombre_hoja in hojas_a_procesar:
        df = pd.read_excel(excel_file, sheet_name=nombre_hoja, header=None)

        # Localizar la fila de cabecera que contenga 'Circuito' y 'Municipio' o 'Zonas'
        fila_cabecera = None
        for idx, fila in df.iterrows():
            texto_fila = " ".join([str(c).lower() for c in fila if pd.notna(c)])
            if "circuito" in texto_fila and ("zonas" in texto_fila or "municipio" in texto_fila):
                fila_cabecera = idx
                break

        if fila_cabecera is None:
            fila_cabecera = 8  # Fila 8 por defecto en el formato oficial de EdeNorte

        # Procesar los datos desde la fila posterior a los títulos
        df_datos = df.iloc[fila_cabecera + 1:].copy()

        for _, fila in df_datos.iterrows():
            if fila.isna().all():
                continue

            # Mapeo según la plantilla oficial de EdeNorte
            val_provincia = str(fila[1]).strip() if pd.notna(fila[1]) else "Santiago"
            val_municipio = str(fila[2]).strip() if pd.notna(fila[2]) else val_provincia
            val_circuito = str(fila[5]).strip() if pd.notna(fila[5]) else "Circuito EdeNorte"
            val_fecha_raw = fila[6]
            val_h_ini = fila[7]
            val_h_fin = fila[9]
            val_zonas = str(fila[10]).strip() if pd.notna(fila[10]) else "Sectores varios"
            val_causa = str(fila[11]).strip() if pd.notna(fila[11]) else "Mantenimiento preventivo"

            # Omitir si tanto el circuito como las zonas están vacíos
            if pd.isna(fila[5]) and pd.isna(fila[10]):
                continue

            fecha_texto = formatear_fecha(val_fecha_raw)
            h_ini_fmt = formatear_hora(val_h_ini)
            h_fin_fmt = formatear_hora(val_h_fin)

            if h_ini_fmt and h_fin_fmt:
                horario_texto = f"{h_ini_fmt} a {h_fin_fmt}"
            elif h_ini_fmt:
                horario_texto = h_ini_fmt
            else:
                horario_texto = "9:00 a.m. a 5:00 p.m."

            # Dividir la cadena de sectores por comas y saltos de línea
            val_zonas_limpio = val_zonas.replace("\n", ", ")
            sectores_individuales = [
                s.strip().rstrip(".") for s in val_zonas_limpio.split(",") if s.strip().rstrip(".")
            ]

            # Si no contenía comas, mantener el sector original
            if not sectores_individuales:
                sectores_individuales = [val_zonas.strip()]

            # Generar un elemento independiente por cada sector
            for sector_individual in sectores_individuales:
                mantenimientos.append({
                    "id": f"edenorte_{contador_id}",
                    "distribuidora": "EDENORTE",
                    "provincia": val_provincia,
                    "municipio": val_municipio,
                    "circuito": val_circuito,
                    "sector": sector_individual,
                    "fecha": fecha_texto,
                    "horario": horario_texto,
                    "motivo": val_causa
                })
                contador_id += 1

    print(f"[+] Total de mantenimientos extraídos de EdeNorte: {len(mantenimientos)}")
    return mantenimientos


# Alias para integración con main_scraper.py
extraer_datos_edenorte = extraer_datos_excel


def main():
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        url_excel = obtener_url_ultimo_excel(session)
        if not url_excel:
            print("[!] No se pudo obtener la URL del Excel.")
            return

        print(f"[*] Descargando archivo Excel desde: {url_excel}")
        resp_bin = session.get(url_excel, headers=HEADERS, timeout=40)
        resp_bin.raise_for_status()

        datos_edenorte = extraer_datos_excel(resp_bin.content)

        with open("mantenimientos_edenorte.json", "w", encoding="utf-8") as f:
            json.dump(datos_edenorte, f, ensure_ascii=False, indent=2)

        print("[✓] Archivo 'mantenimientos_edenorte.json' generado exitosamente.")

    except Exception as e:
        print(f"[!] Error durante el raspado de EdeNorte: {e}")


if __name__ == "__main__":
    main()
