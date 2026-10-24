import difflib
import io
import json
import re
import subprocess
import sys
import unicodedata
from urllib.parse import urljoin

# Automatically install pdfplumber if it is not available
try:
    import pdfplumber
except ImportError:
    print("[*] pdfplumber not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pdfplumber"])
    import pdfplumber

from bs4 import BeautifulSoup
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

# ==========================================
# CATÁLOGOS GEOGRÁFICOS, CIRCUITOS Y CAUSAS
# ==========================================

TERRITORIO_EDEESTE = {
    "Distrito Nacional": [
        "Distrito Nacional",
        "Santo Domingo Centro",
    ],
    "Santo Domingo": [
        "Santo Domingo Este",
        "Santo Domingo Norte",
        "Santo Domingo Oeste",
        "Boca Chica",
        "San Antonio de Guerra",
        "Los Alcarrizos",
        "Pedro Brand",
    ],
    "San Pedro de Macorís": [
        "San Pedro de Macorís",
        "Consuelo",
        "Guayacanes",
        "Quisqueya",
        "Ramón Santana",
        "San José de los Llanos",
    ],
    "La Romana": [
        "La Romana",
        "Guaymate",
        "Villa Hermosa",
    ],
    "La Altagracia": [
        "Higüey",
        "Salvaleón de Higüey",
        "San Rafael del Yuma",
        "Bávaro",
        "Punta Cana",
    ],
    "El Seibo": [
        "Santa Cruz del Seibo",
        "El Seibo",
        "Miches",
    ],
    "Hato Mayor": [
        "Hato Mayor del Rey",
        "Hato Mayor",
        "El Valle",
        "Sabana de la Mar",
    ],
    "Monte Plata": [
        "Monte Plata",
        "Bayaguana",
        "Sabana Grande de Boyá",
        "Yamasá",
        "Peralvillo",
    ],
}

PROVINCIAS_OFICIALES = list(TERRITORIO_EDEESTE.keys())
TODOS_MUNICIPIOS = [muni for sublist in TERRITORIO_EDEESTE.values() for muni in sublist]

TEXTOS_DESCARTABLES = [
    "trabajo", "mantenimiento", "circuito", "fecha", "horario",
    "sector", "zona", "interrupci", "municipio", "subestaci", "código"
]

# Catálogo oficial de causas/motivos de EDEEste
MOTIVOS_CANONICOS = [
    "Facilitar Trabajos Ministerio de Energía y Minas",
    "Facilitar Trabajos Contratista Privado",
    "Interconexión de Proyecto MT",
    "Construcción de Línea MT",
    "Mantenimiento Preventivo en Conductor",
    "Mantenimiento General de Equipos de Potencia y Protecciones",
    "Adecuación de Redes Eléctricas",
    "Sustitución de Postes",
    "Poda de Árboles y Limpieza de Servidumbre",
    "Cambio de Aisladores",
    "Instalación de Nuevos Equipos",
    "Traslado de Carga",
    "Mantenimiento Preventivo y Adecuación de Redes",
]

REGLAS_DIRECTAS_MOTIVOS = [
    (r"(?i)facilitar.*ministerio.*", "Facilitar Trabajos Ministerio de Energía y Minas"),
    (r"(?i)facilitar.*contratista.*", "Facilitar Trabajos Contratista Privado"),
    (r"(?i)interconexi.*proyecto.*", "Interconexión de Proyecto MT"),
    (r"(?i)construcci.*l[ií]nea.*", "Construcción de Línea MT"),
    (r"(?i)mantenim.*genera[ñn]?l?.*equipos?.*", "Mantenimiento General de Equipos de Potencia y Protecciones"),
    (r"(?i)mantenim.*(?:preventivo|conductor).*(?:conductor|preventivo).*", "Mantenimiento Preventivo en Conductor"),
    (r"(?i)mantenimiento\s+preventivo\s+en\b", "Mantenimiento Preventivo en Conductor"),
    (r"(?i)adecuaci[oó]n\s+de\s+red(es)?", "Adecuación de Redes Eléctricas"),
    (r"(?i)sustituci[oó]n\s+de\s+postes?", "Sustitución de Postes"),
    (r"(?i)poda\s+de\s+[aá]rboles?", "Poda de Árboles y Limpieza de Servidumbre"),
]

# Mapa de Circuitos -> Sector Base Estimado y Sectores Conocidos asociados
MAPA_CIRCUITO_SECTORES = {
    "LOS MINA": {
        "sector_base": "Los Mina",
        "sectores": [
            "Ensanche Ozama", "San Lorenzo", "Invivienda Los Mina", "Alma Rosa",
            "Alma Rosa II", "Jardines Alma Rosa", "Las Américas", "Patria Mella",
            "Capotillo Villa Faro", "El Rosal", "Italia", "Nuevo Sol Naciente",
            "Residencial Doña Amarilis I", "Villa Faro", "Los Mina Norte", "Los Mina Sur",
            "Katanga", "Vietnam", "San Antonio de Los Mina", "Mil Flores",
        ],
    },
    "ALMA ROSA": {
        "sector_base": "Alma Rosa",
        "sectores": [
            "Alma Rosa", "Alma Rosa I", "Alma Rosa II", "Ensanche Ozama",
            "Jardines Alma Rosa", "Las Américas", "Patria Mella", "Villa Faro",
        ],
    },
    "EL BRISAL": {
        "sector_base": "El Brisal",
        "sectores": [
            "Alpes II", "Acacia II", "Residencial Asepe", "Los Reyes",
            "Residencial Olimpia", "Residencial Valentina", "Ciudad Azul",
            "Residencial María Mercedes", "Villa Luisa", "Residencial Lares",
            "Residencial Los Calines", "Residencial Las Colinas II",
            "Residencial Las Colinas III Amalia", "Brisa Oriental VIII", "Fedemar",
            "Ralma", "Pradera del Este", "Prado Oriental", "Residencial Asturias",
            "Residencial Los Educadores", "Residencial Paco III",
            "Residencial Radiante Amanecer", "Urbanización Los Almirante",
            "Urbanización Villa San Isidro", "Residencial Kelvin", "Invidorex",
            "Molinos-América", "Marbella II", "Brisa Oriental I", "Cancela 1",
            "Cancela 2", "Farallones de la Ureña", "La Ureña", "Laura Mariel",
            "Los Chinos", "Paraíso", "Residencial Las Américas",
            "Valle de las Américas", "Residencial Villas del Mar",
            "Paseo Jardines Oriental", "Proyecto La Católica", "Lucerna del Mar",
            "Luz María (Frailes)", "Profesor Juan Bosch (Agua Loca)",
            "Frailes del Este (Autódromo)", "Paraje El Mamón", "Riviera del Caribe",
            "Valiente", "El Brisal", "Los Frailes", "Los Frailes I", "Los Frailes II",
        ],
    },
    "KM 26": {
        "sector_base": "Paseo del Este (Km 26)",
        "sectores": [
            "Alma Rosa", "Alma Rosa II", "Ensanche Ozama", "Jardines Alma Rosa",
            "Las Américas", "Patria Mella", "Valiente", "La Ureña",
            "Frailes del Este (Autódromo)", "Riviera del Caribe",
        ],
    },
    "SABANA PERDIDA": {
        "sector_base": "Sabana Perdida",
        "sectores": [
            "Brisa Los Palmares", "Los Palmares", "Marañón II",
            "Los Pinares del Norte", "Residencial Bello Hogar", "Paseo del Llano",
            "Residencial Claribel", "Residencial Maribel I",
            "Urbanización Sarah Gabriela", "Residencial Garden City II",
            "Campechito", "Campechito II", "Villa Laura", "Palmar Encantado",
            "Libertad", "Barrio Libertad", "Sabana Centro", "Villa Blanca",
            "Salomé Ureña", "2 de Enero", "Enriquillo", "Lotes y Servicios",
            "Elsa Patricia", "Brisas del Este S. P.", "Sabana Perdida",
            "Colinas del Ozama", "La Barquita", "El Milloncito",
        ],
    },
    "DAJAO": {
        "sector_base": "Sabana Perdida (El Dajao)",
        "sectores": [
            "Bambú II IV", "Barrio Agrario", "Brisa de los Palmares",
            "Brisas del Este S. P.", "Carole 1", "El Progreso", "Elsa Patricia",
            "Jardines de Sabana", "La Virgen", "Las Mercedes", "Libertad",
            "Los Guayuyos", "Lotes y Servicios", "Miraflores", "P/M La Virgen",
            "Urbanización Derechos Humanos", "Constitución", "El Dajao",
        ],
    },
    "BOCA CHICA": {
        "sector_base": "Boca Chica",
        "sectores": [
            "Cristo Rey", "Sueño Caribeño", "Coquitos Boca Chica", "Monterrey",
            "El Mesón (Alto de Chavón)", "Costa Blanca", "Residencial Mar del Rey",
            "Residencial Miramar Garden", "La Malena", "Sector Los Bancos",
            "Club Miramar", "Reparto Las Américas", "Ciudad Caribe", "Guayacanes",
            "Boca Chica", "Andrés Boca Chica", "La Caleta", "Monte Adentro",
        ],
    },
    "CAPOTILLO": {
        "sector_base": "Ensanche Capotillo",
        "sectores": [
            "Ensanche Capotillo", "Ensanche Luperón", "La Zurza", "Los Manguitos",
            "Villa Juana", "Villas Agrícolas", "Brisa de la Isabela",
            "Villa Agrícola", "24 de Abril", "Ensanche Espaillat",
            "Ensanche Simón Bolívar", "Gualey", "Las Cañitas",
        ],
    },
    "CESAR N PENSON": {
        "sector_base": "Gazcue",
        "sectores": [
            "Ciudad Nueva", "Gazcue", "Zona Colonial", "San Carlos",
            "Villa Francisca", "Don Bosco", "Miraflores",
        ],
    },
    "HAINAMOSA": {
        "sector_base": "Hainamosa",
        "sectores": ["Hainamosa", "Invi-Cea", "Respaldo Hainamosa", "El Almirante"],
    },
    "INVIVIENDA": {
        "sector_base": "Invivienda",
        "sectores": ["Invivienda", "Invivienda Los Mina", "Villa Carmen", "Mendoza"],
    },
    "TAMARINDO": {
        "sector_base": "El Tamarindo",
        "sectores": ["El Tamarindo", "Cancino Adentro", "Cancino", "Villa Liberación"],
    },
    "VILLA MELLA": {
        "sector_base": "Villa Mella",
        "sectores": ["Villa Mella", "Buena Vista I", "Buena Vista II", "Ponce", "Guaricano"],
    },
    "GUARICANO": {
        "sector_base": "Los Guaricanos",
        "sectores": ["Los Guaricanos", "Guaricano", "Villa Mella", "Ponce"],
    },
    "SAN ISIDRO": {
        "sector_base": "San Isidro",
        "sectores": ["San Isidro", "Prado Oriental", "Brisa Oriental I", "Brisa Oriental VIII"],
    },
    "VILLA DUARTE": {
        "sector_base": "Villa Duarte",
        "sectores": ["Villa Duarte", "Los Molinos", "Maquiteria", "Simonico", "Calero"],
    },
    "MENDOZA": {
        "sector_base": "Mendoza",
        "sectores": ["Mendoza", "Villa Faro", "Villa Carmen", "Ralma"],
    },
    "GUERRA": {
        "sector_base": "San Antonio de Guerra",
        "sectores": ["San Antonio de Guerra", "El Mamón", "Hato Viejo", "Bella Vista"],
    },
}

TODOS_SECTORES_CANONICOS = sorted(
    {s for info in MAPA_CIRCUITO_SECTORES.values() for s in info["sectores"]}
)

NUMEROS_ROMANOS = {
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII", "XVIII", "XIX", "XX"
}

CONECTORES_MINUSCULAS = {"de", "del", "la", "las", "el", "los", "y", "e", "en", "a", "al"}


# ==========================================
# UTILIDADES DE SIMILITUD Y DESENTRELAZADO
# ==========================================

def normalizar_sin_acentos(texto):
    """Convierte a minúsculas y elimina tildes/diacríticos."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def firma_letras(texto):
    """
    Devuelve todos los caracteres alfanuméricos ordenados alfabéticamente.
    Permite identificar con 100% de exactitud frases cuyas líneas se entrelazaron.
    """
    limpio = re.sub(r"[^a-z0-9]", "", normalizar_sin_acentos(texto))
    return "".join(sorted(limpio))


def limpiar_texto(valor):
    """Elimina saltos de línea y normaliza espacios en blanco."""
    if not valor:
        return ""
    return " ".join(str(valor).replace("\n", " ").split()).strip()


def extraer_fecha_cabecera(texto):
    """Busca franjas de fecha diaria (ej. LUNES 26 DE OCTUBRE)."""
    dias = [
        "lunes", "martes", "miércoles", "miercoles",
        "jueves", "viernes", "sábado", "sabado", "domingo",
    ]
    patron = rf"({'|'.join(dias)})\s+\d{{1,2}}\s+de\s+[a-záéíóú]+(\s+del?\s+\d{{4}})?"
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        return match.group(0).strip().title()
    return None


# ==========================================
# OBTENCIÓN DEL PDF (COMPATIBLE CON MAIN)
# ==========================================

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


# ==========================================
# VALIDACIÓN DE PROVINCIA, MUNICIPIO Y CAUSA
# ==========================================

def validar_y_corregir_provincia(texto_crudo):
    """Valida el nombre de la provincia descartando encabezados institucionales."""
    if not texto_crudo:
        return None

    texto = limpiar_texto(texto_crudo)
    texto_lower = texto.lower()

    if any(p in texto_lower for p in TEXTOS_DESCARTABLES):
        return None

    if any(k in texto_lower for k in ["santo d", "sto dgo", "sto. dgo", "s.d."]):
        return "Santo Domingo"
    if any(k in texto_lower for k in ["d.n.", "distrito nac", "distrito"]):
        return "Distrito Nacional"
    if "pedro" in texto_lower:
        return "San Pedro de Macorís"
    if "altagracia" in texto_lower or "higuey" in texto_lower:
        return "La Altagracia"
    if "romana" in texto_lower:
        return "La Romana"
    if "seibo" in texto_lower:
        return "El Seibo"
    if "hato" in texto_lower:
        return "Hato Mayor"
    if "monte plata" in texto_lower:
        return "Monte Plata"

    coincidencias = difflib.get_close_matches(texto, PROVINCIAS_OFICIALES, n=1, cutoff=0.70)
    return coincidencias[0] if coincidencias else None


def validar_y_corregir_municipio(texto_crudo, provincia_referencia=None):
    """Normaliza el municipio e infiere su provincia oficial."""
    if not texto_crudo:
        return None, None

    texto = limpiar_texto(texto_crudo)
    texto_lower = texto.lower()

    if any(p in texto_lower for p in TEXTOS_DESCARTABLES):
        return None, None

    if "distrito nacional" in texto_lower or texto_lower == "d.n.":
        return "Distrito Nacional", "Distrito Nacional"
    if any(k in texto_lower for k in ["sde", "sto dgo este", "santo domingo este"]):
        return "Santo Domingo Este", "Santo Domingo"
    if any(k in texto_lower for k in ["sdn", "sto dgo norte", "santo domingo norte"]):
        return "Santo Domingo Norte", "Santo Domingo"
    if any(k in texto_lower for k in ["sdo", "sto dgo oeste", "santo domingo oeste"]):
        return "Santo Domingo Oeste", "Santo Domingo"
    if "boca chica" in texto_lower:
        return "Boca Chica", "Santo Domingo"
    if "guerra" in texto_lower:
        return "San Antonio de Guerra", "Santo Domingo"
    if "higuey" in texto_lower or "higüey" in texto_lower:
        return "Higüey", "La Altagracia"
    if "bavaro" in texto_lower or "punta cana" in texto_lower:
        return "Higüey", "La Altagracia"

    candidatos = (
        TERRITORIO_EDEESTE.get(provincia_referencia, TODOS_MUNICIPIOS)
        if provincia_referencia
        else TODOS_MUNICIPIOS
    )

    coincidencias = difflib.get_close_matches(texto, candidatos, n=1, cutoff=0.65)
    if coincidencias:
        muni = coincidencias[0]
        for prov, munis in TERRITORIO_EDEESTE.items():
            if muni in munis:
                return muni, prov

    if provincia_referencia and not coincidencias:
        coincidencias_global = difflib.get_close_matches(texto, TODOS_MUNICIPIOS, n=1, cutoff=0.70)
        if coincidencias_global:
            muni = coincidencias_global[0]
            for prov, munis in TERRITORIO_EDEESTE.items():
                if muni in munis:
                    return muni, prov

    if len(texto) >= 4 and not any(p in texto_lower for p in TEXTOS_DESCARTABLES):
        return texto.title(), None

    return None, None


def corregir_motivo(motivo_crudo):
    """
    Desentrelaza y normaliza causas incluso si pdfplumber mezcló verticalmente dos líneas
    (ej. 'InterconexioMn Tde Proyecto' o 'MantenimCieonntdou pcrteovrentivo en').
    """
    if not motivo_crudo or len(str(motivo_crudo).strip()) < 3:
        return "Mantenimiento Preventivo y Adecuación de Redes"

    texto = limpiar_texto(motivo_crudo)

    # 1. Comparación por firma de letras (resuelve entrelazamientos al 100%)
    firma_entrada = firma_letras(texto)
    mejor_motivo = None
    mejor_score_firma = 0.0

    for canonico in MOTIVOS_CANONICOS:
        score = difflib.SequenceMatcher(None, firma_entrada, firma_letras(canonico)).ratio()
        if score > mejor_score_firma:
            mejor_score_firma = score
            mejor_motivo = canonico

    if mejor_score_firma >= 0.82:
        return mejor_motivo

    # 2. Reglas deterministas por expresiones regulares
    for patron, reemplazo in REGLAS_DIRECTAS_MOTIVOS:
        if re.search(patron, texto):
            return reemplazo

    # 3. Coincidencia difusa tradicional
    coincidencias = difflib.get_close_matches(texto, MOTIVOS_CANONICOS, n=1, cutoff=0.55)
    if coincidencias:
        return coincidencias[0]

    texto_limpio = re.sub(r"^[\s,;:.\-–—]+|[\s,;:.\-–—]+$", "", texto)
    return texto_limpio


def extraer_lista_causas(raw_causa):
    """
    Separa múltiples causas apiladas verticalmente o concatenadas accidentalmente
    (ej. 'InterconexioMn Tde Proyecto MantenimCieonntdou pcrteovrentivo en').
    """
    if not raw_causa or not str(raw_causa).strip():
        return ["Mantenimiento Preventivo y Adecuación de Redes"]

    # Insertar salto de línea antes de cualquier raíz de causa aunque esté a mitad de línea
    patron_corte = re.compile(
        r"(?<!\by\s)(?<!\bde\s)\s+(?=(?:Facilitar|Interconexi|Mantenim|Construcci|"
        r"Sustituci|Poda\b|Cambio\b|Instalaci|Traslado|Apertura|Reubicaci|Normalizaci))",
        re.IGNORECASE,
    )
    texto_preprocesado = patron_corte.sub("\n", str(raw_causa))

    lineas = [l.strip() for l in texto_preprocesado.splitlines() if l.strip()]
    if not lineas:
        return ["Mantenimiento Preventivo y Adecuación de Redes"]

    patron_inicio = re.compile(
        r"^(facilitar|interconexi|mantenim|construcci|adecuaci|"
        r"sustituci|poda|cambio|instalaci|traslado|apertura|reubicaci|"
        r"normalizaci|desmonte|correcci)",
        re.IGNORECASE,
    )

    causas_agrupadas = []
    buffer_actual = []

    for linea in lineas:
        if patron_inicio.match(linea) and buffer_actual:
            causas_agrupadas.append(corregir_motivo(" ".join(buffer_actual)))
            buffer_actual = [linea]
        else:
            buffer_actual.append(linea)
            # Si el buffer ya forma por sí mismo una causa completa entrelazada, cerrarla
            texto_buf = " ".join(buffer_actual)
            if len(texto_buf) >= 24:
                f_buf = firma_letras(texto_buf)
                if any(
                    difflib.SequenceMatcher(None, f_buf, firma_letras(c)).ratio() >= 0.92
                    for c in MOTIVOS_CANONICOS
                ):
                    causas_agrupadas.append(corregir_motivo(texto_buf))
                    buffer_actual = []

    if buffer_actual:
        texto_restante = " ".join(buffer_actual)
        # Ignorar residuos sueltos de 1 palabra (ej. 'MT' o 'Conductor' ya absorbidos)
        if len(texto_restante) > 4 or not causas_agrupadas:
            causas_agrupadas.append(corregir_motivo(texto_restante))

    return causas_agrupadas if causas_agrupadas else ["Mantenimiento Preventivo y Adecuación de Redes"]


# ==========================================
# CIRCUITOS Y ESTIMACIÓN/CORRECCIÓN DE SECTOR
# ==========================================

def obtener_info_circuito(circuito):
    """Busca la configuración de sectores conocidos para el circuito dado."""
    if not circuito:
        return None
    c_upper = normalizar_sin_acentos(circuito).upper()

    mapeo_codigos = {
        "LMIN": "LOS MINA",
        "RCL": "ALMA ROSA",
        "EBRI": "EL BRISAL",
        "KM26": "KM 26",
        "SPER": "SABANA PERDIDA",
        "DAJA": "DAJAO",
        "BOCA": "BOCA CHICA",
        "CAPO": "CAPOTILLO",
        "CNP": "CESAR N PENSON",
    }

    for clave, info in MAPA_CIRCUITO_SECTORES.items():
        if clave in c_upper:
            return info

    for prefijo, clave in mapeo_codigos.items():
        if prefijo in c_upper:
            return MAPA_CIRCUITO_SECTORES[clave]

    return None


def estimar_sector_desde_circuito(circuito, municipio=""):
    """Estima un nombre de sector limpio a partir del nombre del circuito."""
    info = obtener_info_circuito(circuito)
    if info:
        return info["sector_base"]

    if circuito and circuito.lower() != "circuito edeeste":
        # Limpiar números de tensión/código del nombre del circuito (ej. 'LOS MINA 138, NO 7' -> 'Los Mina')
        limpio = re.sub(r"(?i)\b(recloser|subestaci[oó]n|circuito|no\.?\s*\d+|\d+)\b", "", str(circuito))
        limpio = re.sub(r"[,;.\-_]+", " ", limpio)
        limpio = " ".join(limpio.split()).strip()
        if len(limpio) >= 3:
            return formatear_capitalizacion_sector(limpio)

    return municipio if municipio else "Zona de Concesión Edeeste"


def extraer_lista_circuitos(raw_circuito, raw_codigo=""):
    """Separa múltiples circuitos apilados en una misma celda."""
    lineas_c = [l.strip() for l in str(raw_circuito or "").splitlines() if l.strip()]
    circuitos = []

    for l in lineas_c:
        if circuitos and (
            re.match(r"^(no\.?\s*\d+|\d+)$", l, re.IGNORECASE)
            or circuitos[-1].endswith(",")
        ):
            circuitos[-1] = f"{circuitos[-1]} {l}".replace("  ", " ")
        else:
            circuitos.append(l)

    if not circuitos and raw_codigo:
        circuitos = [l.strip() for l in str(raw_codigo).splitlines() if l.strip()]

    return circuitos if circuitos else ["Circuito Edeeste"]


def extraer_parrafos_zonas(raw_zonas):
    """Divide la celda de zonas en párrafos independientes (uno por circuito)."""
    if not raw_zonas or not str(raw_zonas).strip():
        return ["Sectores varios"]

    lineas = [l.strip() for l in str(raw_zonas).splitlines() if l.strip()]
    if not lineas:
        return ["Sectores varios"]

    parrafos = []
    actual = []
    patron_abrev_final = re.compile(r"(?i)\b(res|urb|parc|barr|av|sto|dgo|no|dr|ing|lic)\.$")

    for l in lineas:
        actual.append(l)
        if l.endswith(".") and not patron_abrev_final.search(l):
            parrafos.append(" ".join(actual))
            actual = []

    if actual:
        parrafos.append(" ".join(actual))

    return parrafos if parrafos else ["Sectores varios"]


def formatear_capitalizacion_sector(texto):
    """Formatea cada palabra respetando números romanos, siglas y paréntesis."""
    palabras = texto.split()
    resultado = []

    for idx, palabra in enumerate(palabras):
        m = re.match(r"^([\(\[]*)([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9./\-]+)([\)\].]*)$", palabra)
        if not m:
            resultado.append(palabra)
            continue

        prefijo, nucleo, sufijo = m.groups()
        nucleo_upper = nucleo.upper()

        if nucleo_upper in NUMEROS_ROMANOS or nucleo_upper in {"P/M", "S.P.", "S.", "P.", "KM", "MT"}:
            palabra_fmt = f"{prefijo}{nucleo_upper}{sufijo}"
        elif idx > 0 and not prefijo and nucleo.lower() in CONECTORES_MINUSCULAS:
            palabra_fmt = nucleo.lower()
        elif "-" in nucleo:
            partes_g = [p.capitalize() for p in nucleo.split("-")]
            palabra_fmt = f"{prefijo}{'-'.join(partes_g)}{sufijo}"
        else:
            palabra_fmt = f"{prefijo}{nucleo.capitalize()}{sufijo}"

        resultado.append(palabra_fmt)

    return " ".join(resultado)


def es_sector_corrupto(texto):
    """Detecta si un nombre de sector presenta entrelazamiento de caracteres o ruido."""
    if not texto or len(texto) < 2:
        return True
    # Detectar mayúsculas incrustadas tras minúsculas (ej. 'InterconexioMn')
    if re.search(r"[a-záéíóúñ][A-ZÁÉÍÓÚÑ][a-záéíóúñ]", texto):
        return True
    # Detectar 4 o más consonantes seguidas no válidas en español (ej. 'ntdou', 'pcrte')
    sin_acentos = normalizar_sin_acentos(texto)
    for grupo in re.findall(r"[bcdfghjklmnpqrstvwxyz]{4,}", sin_acentos):
        if not any(val in grupo for val in ["nstr", "nsch", "nscl", "ngl", "mbl", "mbr", "ntr", "ndr", "rtr", "lpr"]):
            return True
    return False


def validar_y_corregir_sector(sector_crudo, circuito_actual="", municipio_actual=""):
    """
    Limpia, desentrelaza y valida un sector auxiliándose del catálogo del Circuito.
    Si el sector está corrupto, lo recupera o estima usando el Circuito.
    """
    if not sector_crudo:
        return ""

    s = " ".join(str(sector_crudo).split()).strip()

    # 1. Separar palabras pegadas tipo CamelCase en el PDF (ej. 'EnsancheLuperón' -> 'Ensanche Luperón')
    s = re.sub(r"([a-záéíóúüñ])([A-ZÁÉÍÓÚÜÑ])", r"\1 \2", s)

    # Separar prefijos urbanos si vinieron pegados en minúscula
    s = re.sub(
        r"(?i)\b(ensanche|residencial|urbanizaci[oó]n|barrio|jardines|villa|pradera|prado|ciudad|paraje|reparto)(?=[a-záéíóúñ]{3,})",
        r"\1 ",
        s,
    )

    # 2. Expandir abreviaturas estándar
    s = re.sub(r"(?i)\bRes\.?\s+", "Residencial ", s)
    s = re.sub(r"(?i)\bUrb\.?\s+", "Urbanización ", s)
    s = re.sub(r"(?i)\bParc\.?\s+", "Parcial ", s)
    s = re.sub(r"(?i)\bBarr\.?\s+", "Barrio ", s)

    # 3. Limpiar puntuación en los extremos conservando paréntesis de cierre
    s = re.sub(r"^[\s,;:.\-–—]+|[\s,;:\-–—]+$", "", s)
    if s.endswith(".") and not re.search(r"\b[A-Za-z]\.$", s):
        s = s[:-1].strip()

    if "(" in s and ")" not in s:
        s = s.replace("(", "").strip()
    elif ")" in s and "(" not in s:
        s = s.replace(")", "").strip()

    s = " ".join(s.split()).strip()
    if len(s) < 2 or s.lower() in {"sector", "sectores", "zona", "zonas", "parcial", "sectores varios"}:
        return ""

    # 4. Consultar sectores conocidos del circuito actual
    info_circ = obtener_info_circuito(circuito_actual)
    sectores_locales = info_circ["sectores"] if info_circ else []
    s_norm = normalizar_sin_acentos(s)
    s_firma = firma_letras(s)

    # 4a. Búsqueda prioritaria en los sectores propios del Circuito
    if sectores_locales:
        mejor_local = None
        mejor_score = 0.0
        for cand in sectores_locales:
            c_norm = normalizar_sin_acentos(cand)
            if s_norm == c_norm:
                return cand
            score_seq = difflib.SequenceMatcher(None, s_norm, c_norm).ratio()
            score_fir = (
                difflib.SequenceMatcher(None, s_firma, firma_letras(cand)).ratio()
                if len(s_firma) >= 5
                else 0.0
            )
            score = max(score_seq, score_fir * 0.96)
            if score > mejor_score:
                mejor_score = score
                mejor_local = cand

        if mejor_score >= 0.74:
            return mejor_local

    # 4b. Búsqueda en el catálogo global de sectores de EDEEste
    mejor_global = None
    mejor_score_g = 0.0
    for cand in TODOS_SECTORES_CANONICOS:
        c_norm = normalizar_sin_acentos(cand)
        if s_norm == c_norm:
            return cand
        score_seq = difflib.SequenceMatcher(None, s_norm, c_norm).ratio()
        score_fir = (
            difflib.SequenceMatcher(None, s_firma, firma_letras(cand)).ratio()
            if len(s_firma) >= 6
            else 0.0
        )
        score = max(score_seq, score_fir * 0.95)
        if score > mejor_score_g:
            mejor_score_g = score
            mejor_global = cand

    if mejor_score_g >= 0.82:
        return mejor_global

    # 5. Si el sector presenta signos de corrupción/entrelazamiento, estimar con el Circuito
    if es_sector_corrupto(sector_crudo) or es_sector_corrupto(s):
        if sectores_locales and mejor_score >= 0.55:
            return mejor_local
        if mejor_score_g >= 0.65:
            return mejor_global
        return estimar_sector_desde_circuito(circuito_actual, municipio_actual)

    return formatear_capitalizacion_sector(s)


def separar_zonas_de_parrafo(parrafo_zonas, circuito_actual="", municipio_actual=""):
    """Separa un párrafo de zonas en sectores individuales y los valida con su circuito."""
    if not parrafo_zonas:
        return [estimar_sector_desde_circuito(circuito_actual, municipio_actual)]

    t = re.sub(r"[\r\n\t•\*]+", " ", str(parrafo_zonas))
    partes = re.split(r"[,;]+", t)

    zonas_limpias = []
    vistos = set()

    for p in partes:
        s_val = validar_y_corregir_sector(p, circuito_actual, municipio_actual)
        if s_val:
            clave = normalizar_sin_acentos(s_val)
            if clave not in vistos:
                vistos.add(clave)
                zonas_limpias.append(s_val)

    if not zonas_limpias:
        return [estimar_sector_desde_circuito(circuito_actual, municipio_actual)]

    return zonas_limpias


def calcular_afinidad_parrafo_circuito(parrafo, circuito):
    """Calcula cuántos sectores del párrafo coinciden con los sectores conocidos del circuito."""
    info = obtener_info_circuito(circuito)
    if not info:
        return 0.0
    p_norm = normalizar_sin_acentos(parrafo)
    coincidencias = sum(
        1 for sec in info["sectores"] if normalizar_sin_acentos(sec) in p_norm
    )
    if normalizar_sin_acentos(info["sector_base"]) in p_norm:
        coincidencias += 2
    return float(coincidencias)


def alinear_parrafos_con_circuitos(lista_parrafos, lista_circuitos, lista_causas):
    """
    Empareja cada párrafo de sectores con su circuito y su causa correspondiente.
    Cuando hay más circuitos que párrafos (ej. un circuito con celda de zona en blanco),
    utiliza la afinidad entre los sectores del párrafo y el nombre del circuito.
    """
    num_p = len(lista_parrafos)
    num_c = len(lista_circuitos)
    num_m = len(lista_causas)

    asignaciones = []

    if num_p == num_c:
        indices_c = list(range(num_c))
    elif num_c == 1:
        indices_c = [0] * num_p
    else:
        # Selección monótona basada en afinidad de sectores + posición relativa
        indices_c = []
        ultimo_c = -1
        for idx_p, parrafo in enumerate(lista_parrafos):
            pos_esperada = idx_p * (num_c - 1) / max(1, num_p - 1)
            mejor_c = min(int(round(pos_esperada)), num_c - 1)
            mejor_puntaje = -999.0

            inicio_busqueda = max(0, ultimo_c)
            fin_busqueda = min(num_c, max(inicio_busqueda + 3, int(round(pos_esperada)) + 2))

            for cand_c in range(inicio_busqueda, fin_busqueda):
                afinidad = calcular_afinidad_parrafo_circuito(parrafo, lista_circuitos[cand_c])
                penalizacion_dist = abs(cand_c - pos_esperada) * 0.75
                puntaje = afinidad - penalizacion_dist
                if puntaje > mejor_puntaje:
                    mejor_puntaje = puntaje
                    mejor_c = cand_c

            indices_c.append(mejor_c)
            ultimo_c = mejor_c

    for idx_p, parrafo in enumerate(lista_parrafos):
        c_idx = indices_c[idx_p]
        circuito_asignado = lista_circuitos[c_idx]

        if num_m == num_p:
            causa_asignada = lista_causas[idx_p]
        elif num_m == num_c:
            causa_asignada = lista_causas[c_idx]
        elif num_m == 1:
            causa_asignada = lista_causas[0]
        else:
            pos_m = min(int(round(idx_p * (num_m - 1) / max(1, num_p - 1))), num_m - 1)
            causa_asignada = lista_causas[pos_m]

        asignaciones.append((parrafo, circuito_asignado, causa_asignada))

    return asignaciones


# ==========================================
# PROCESAMIENTO DEL PDF
# ==========================================

def procesar_panel_tabla(crop_page, fecha_default, contador_id_inicial):
    """Extrae los mantenimientos de medio panel horizontal de forma aislada."""
    mantenimientos_panel = []
    contador_id = contador_id_inicial

    texto_panel = crop_page.extract_text(x_tolerance=1.5, y_tolerance=1.0) or ""
    fecha_panel = extraer_fecha_cabecera(texto_panel) or fecha_default

    # text_y_tolerance=1.0 impide que pdfplumber entrelace renglones cercanos
    table_settings = {
        "vertical_strategy": "lines",
        "horizontal_strategy": "lines",
        "snap_y_tolerance": 5,
        "snap_x_tolerance": 5,
        "intersection_x_tolerance": 15,
        "join_x_tolerance": 5,
        "join_y_tolerance": 5,
        "text_y_tolerance": 1.0,
        "text_x_tolerance": 1.5,
    }

    tablas = crop_page.extract_tables(table_settings=table_settings)
    if not tablas:
        tablas = crop_page.extract_tables(
            table_settings={"text_y_tolerance": 1.0, "text_x_tolerance": 1.5}
        )

    if not tablas:
        return mantenimientos_panel, contador_id, fecha_panel

    provincia_actual = "Santo Domingo"
    municipio_actual = "Santo Domingo Este"
    horario_actual = "9:20 a.m. a 5:20 p.m."

    for tabla in tablas:
        for fila in tabla:
            if not fila or len(fila) < 5:
                continue

            celdas_raw = [str(c) if c is not None else "" for c in fila]
            celdas = [limpiar_texto(c) for c in celdas_raw]
            texto_fila = " ".join(celdas).lower()

            if "trabajos de mantenimientos" in texto_fila and not re.search(r"\d{1,2}:\d{2}", texto_fila):
                continue

            es_cabecera = ("circuito" in texto_fila and "zonas" in texto_fila) or (
                "municipio" in texto_fila and "código" in texto_fila
            )
            tiene_horario = bool(re.search(r"\d{1,2}:\d{2}", texto_fila))
            if es_cabecera and not tiene_horario:
                continue

            if any(
                dia in texto_fila
                for dia in [
                    "lunes", "martes", "miércoles", "miercoles",
                    "jueves", "viernes", "sábado", "sabado", "domingo",
                ]
            ):
                if not tiene_horario and len([c for c in celdas if c]) <= 3:
                    f_ext = extraer_fecha_cabecera(" ".join(celdas))
                    if f_ext:
                        fecha_panel = f_ext
                    continue

            raw_provincia = ""
            raw_municipio = ""
            raw_circuito = ""
            raw_codigo = ""
            raw_h_inicio = ""
            raw_h_fin = ""
            raw_zonas = ""
            raw_causa = ""

            if len(celdas_raw) >= 8:
                raw_provincia = celdas_raw[0]
                raw_municipio = celdas_raw[1]
                raw_circuito = celdas_raw[2]
                raw_codigo = celdas_raw[3]
                raw_h_inicio = celdas_raw[4]
                raw_h_fin = celdas_raw[5]
                raw_zonas = celdas_raw[6]
                raw_causa = celdas_raw[7]
            elif len(celdas_raw) == 7:
                raw_municipio = celdas_raw[0]
                raw_circuito = celdas_raw[1]
                raw_codigo = celdas_raw[2]
                raw_h_inicio = celdas_raw[3]
                raw_h_fin = celdas_raw[4]
                raw_zonas = celdas_raw[5]
                raw_causa = celdas_raw[6]
            elif len(celdas_raw) >= 5:
                raw_circuito = celdas_raw[0]
                raw_codigo = celdas_raw[1]
                raw_h_inicio = celdas_raw[2]
                raw_zonas = celdas_raw[3]
                raw_causa = celdas_raw[4]

            prov_validada = validar_y_corregir_provincia(raw_provincia)
            if prov_validada:
                provincia_actual = prov_validada

            muni_validado, prov_inferida = validar_y_corregir_municipio(raw_municipio, provincia_actual)
            if muni_validado:
                municipio_actual = muni_validado
            if prov_inferida:
                provincia_actual = prov_inferida

            val_h_inicio = limpiar_texto(raw_h_inicio)
            val_h_fin = limpiar_texto(raw_h_fin)
            if val_h_inicio and val_h_fin:
                horario_actual = f"{val_h_inicio} a {val_h_fin}"
            elif val_h_inicio:
                horario_actual = val_h_inicio

            if not limpiar_texto(raw_circuito) and not limpiar_texto(raw_zonas):
                continue

            lista_circuitos = extraer_lista_circuitos(raw_circuito, raw_codigo)
            lista_parrafos_zonas = extraer_parrafos_zonas(raw_zonas)
            lista_causas = extraer_lista_causas(raw_causa)

            asignaciones = alinear_parrafos_con_circuitos(
                lista_parrafos_zonas, lista_circuitos, lista_causas
            )

            for parrafo, circuito_asignado, causa_asignada in asignaciones:
                sectores_individuales = separar_zonas_de_parrafo(
                    parrafo, circuito_asignado, municipio_actual
                )
                for sector_limpio in sectores_individuales:
                    mantenimientos_panel.append({
                        "id": f"edeeste_{contador_id}",
                        "distribuidora": "EDEESTE",
                        "provincia": provincia_actual,
                        "municipio": municipio_actual,
                        "circuito": circuito_asignado,
                        "sector": sector_limpio,
                        "fecha": fecha_panel,
                        "horario": horario_actual,
                        "motivo": causa_asignada,
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
