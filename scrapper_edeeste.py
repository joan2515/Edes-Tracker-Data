import hashlib
import json
import re
import requests
from bs4 import BeautifulSoup

URL_EDESUR = "https://www.edesur.com.do/enlaces-empresa/mantenimientos-programados/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def limpiar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", texto).strip()

def parsear_mantenimientos():
    try:
        response = requests.get(URL_EDESUR, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except Exception as e:
        print(f"Error al descargar la página de Edesur: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    registros = []

    # 1. Extraer los días (tabs/botones) si están vinculados por contenedor
    # Si la página renderiza todos los paneles en el HTML, buscamos los contenedores de acordeón
    accordions = soup.find_all("div", class_=lambda c: c and "accordion" in c)

    for acc in accordions:
        # Intentar obtener la fecha asociada a este bloque o pestaña
        # (Si el acordeón está dentro de un tab-pane o tiene fecha asociada arriba)
        fecha_texto = "Semana actual"
        tab_parent = acc.find_parent("div", class_=lambda c: c and ("tab-pane" in c or "fade" in c))
        if tab_parent and tab_parent.get("id"):
            # Buscar el botón que apunta a este tab
            boton_tab = soup.find(attrs={"data-bs-target": f"#{tab_parent.get('id')}"}) or \
                        soup.find(attrs={"href": f"#{tab_parent.get('id')}"})
            if boton_tab:
                fecha_texto = limpiar_texto(boton_tab.get_text())

        # 2. Recorrer cada item del acordeón (Provincias)
        items = acc.find_all("div", class_=lambda c: c and "accordion-item" in c)
        for item in items:
            # Extraer provincia del h4 o accordion-button
            h4_tag = item.find("h4")
            provincia = limpiar_texto(h4_tag.get_text()) if h4_tag else "Santo Domingo"

            # Buscar el cuerpo del acordeón
            body = item.find("div", class_=lambda c: c and "accordion-body" in c)
            if not body:
                continue

            # Extraer los bloques de horarios y sectores dentro de este cuerpo
            titulos_zona = body.find_all("h5", class_=lambda c: c and "title-zona" in c)

            for tz in titulos_zona:
                texto_horario = limpiar_texto(tz.get_text())

                # Extrae el rango de hora (ej: "09:00 a. m. a 02:00 p. m.")
                horario_match = re.search(r"(\d{1,2}:\d{2}\s*(?:a\.\s*m\.|p\.\s*m\.)\s*a\s*\d{1,2}:\d{2}\s*(?:a\.\s*m\.|p\.\s*m\.))", texto_horario, re.IGNORECASE)
                horario = horario_match.group(1) if horario_match else texto_horario

                # El texto de sectores suele ser el siguiente párrafo <p> no vacío
                parrafo_sectores = tz.find_next_sibling("p")
                while parrafo_sectores and not limpiar_texto(parrafo_sectores.get_text()):
                    parrafo_sectores = parrafo_sectores.find_next_sibling("p")

                cadena_sectores = limpiar_texto(parrafo_sectores.get_text()) if parrafo_sectores else ""

                # Separar los sectores por coma para que la app pueda buscar individualmente
                lista_sectores = [s.strip() for s in cadena_sectores.split(",") if s.strip()]

                for sector_individual in lista_sectores:
                    # ID único para cada corte por sector
                    id_raw = f"{provincia}-{sector_individual}-{fecha_texto}-{horario}"
                    id_hash = hashlib.md5(id_raw.encode("utf-8")).hexdigest()[:10]

                    registros.append({
                        "id": id_hash,
                        "provincia": provincia,
                        "municipio": provincia,
                        "sector": sector_individual,
                        "circuito": "EDESUR",
                        "fecha": fecha_texto,
                        "horario": horario,
                        "motivo": "Mantenimiento preventivo"
                    })

    return registros

def main():
    datos = parsear_mantenimientos()
    print(f"Total de sectores con mantenimientos encontrados: {len(datos)}")

    with open("mantenimientos.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
