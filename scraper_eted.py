import os
import re
import asyncio
from datetime import datetime, timezone, timedelta
from io import BytesIO
import requests
from PIL import Image
import pytesseract
from twscrape import API

def descargar_y_hacer_ocr(image_url: str) -> str:
    """Descarga la imagen del afiche y extrae el texto usando Tesseract OCR."""
    try:
        response = requests.get(image_url, timeout=15)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            # Se usa el paquete de idioma español de tesseract
            texto = pytesseract.image_to_string(img, lang="spa")
            return texto
    except Exception as e:
        print(f"Error procesando OCR en {image_url}: {e}")
    return ""

def parsear_contenido_mantenimiento(texto_completo: str) -> dict:
    """Extrae campos clave tanto de afiches como de avisos en texto plano."""
    texto_limpio = texto_completo.replace("\r", " ").strip()
    
    # 1. Subestación o Línea
    subestacion_match = re.search(
        r"((?:SUBESTACIÓN|LÍNEA DE TRANSMISIÓN)[^\n\r]+?(?:BARRA|\d+\s*kV[^\n\r]*|))", 
        texto_limpio, 
        re.IGNORECASE
    )
    subestacion = subestacion_match.group(1).strip() if subestacion_match else "No especificada"

    # 2. Rango de Horario (ej: 7:00 a.m. - 11:00 a.m.)
    horario_match = re.search(
        r"(\d{1,2}:\d{2}\s*(?:a\.?\s*m\.?|p\.?\s*m\.?)\s*[-–a]\s*\d{1,2}:\d{2}\s*(?:a\.?\s*m\.?|p\.?\s*m\.?))", 
        texto_limpio, 
        re.IGNORECASE
    )
    horario = horario_match.group(1).strip() if horario_match else "No especificado"

    # 3. Tipo de evento (Avería o Mantenimiento Preventivo)
    if "AVERÍA" in texto_limpio.upper():
        tipo = "Avería"
    else:
        tipo = "Mantenimiento Preventivo"

    # 4. Comunidades o Zonas afectadas
    comunidades_match = re.search(
        r"(?:Comunidades afectadas|Zonas afectadas)[\s:]+([^\n\r]+(?:\n[^\n\r]+)?)", 
        texto_limpio, 
        re.IGNORECASE
    )
    comunidades = comunidades_match.group(1).strip() if comunidades_match else ""

    # 5. Empresas afectadas
    empresas_match = re.search(
        r"(?:Empresas afectadas)[\s:]+([^\n\r]+)", 
        texto_limpio, 
        re.IGNORECASE
    )
    empresas = empresas_match.group(1).strip() if empresas_match else ""

    return {
        "tipo": tipo,
        "circuito_o_subestacion": subestacion,
        "horario": horario,
        "comunidades_afectadas": comunidades,
        "empresas_afectadas": empresas
    }

async def _extraer_tweets_semana():
    api = API()
    
    # Cargar sesión desde variables de entorno (GitHub Secrets)
    auth_token = os.getenv("TWITTER_AUTH_TOKEN")
    ct0 = os.getenv("TWITTER_CT0")
    username = os.getenv("TWITTER_USERNAME", "bot_edes")

    if auth_token and ct0:
        await api.pool.add_account(
            username=username,
            password="dummy_password",
            email="dummy@mail.com",
            email_password="dummy_password",
            cookies=f"auth_token={auth_token}; ct0={ct0}"
        )
        await api.pool.set_active(username, True)

    # Calcular el inicio de la semana en curso (Lunes 00:00 UTC)
    ahora = datetime.now(timezone.utc)
    inicio_semana = (ahora - timedelta(days=ahora.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    query = "from:ETED_RD -is:retweet"
    reportes = []

    async for tweet in api.search(query, limit=40):
        # Filtrar solo reportes que pertenezcan a la semana en curso
        if tweet.date < inicio_semana:
            continue

        raw_text = tweet.rawContent
        es_relevante = any(k in raw_text.lower() for k in [
            "mantenimiento", "avería", "averia", "subestación", "subestacion", "interrupción", "informamos"
        ])

        # Extraer enlaces a imágenes si existen (afiches)
        imagenes = []
        if tweet.media and tweet.media.photos:
            imagenes = [photo.url for photo in tweet.media.photos]

        if not es_relevante and not imagenes:
            continue

        # Procesamiento de OCR si el tweet adjunta un afiche gráfico
        texto_ocr = ""
        for img_url in imagenes:
            texto_ocr += " " + descargar_y_hacer_ocr(img_url)

        texto_consolidado = f"{raw_text}\n{texto_ocr}"
        datos_parseados = parsear_contenido_mantenimiento(texto_consolidado)

        reportes.append({
            "empresa": "ETED",
            "id_reporte": str(tweet.id),
            "fecha_publicacion": tweet.date.strftime("%Y-%m-%d %H:%M:%S"),
            "tipo": datos_parseados["tipo"],
            "subestacion": datos_parseados["circuito_o_subestacion"],
            "horario": datos_parseados["horario"],
            "comunidades": datos_parseados["comunidades_afectadas"],
            "empresas": datos_parseados["empresas_afectadas"],
            "texto_original": raw_text,
            "imagenes": imagenes,
            "url_tweet": f"https://x.com/ETED_RD/status/{tweet.id}"
        })

    return reportes

def get_mantenimientos_eted() -> list:
    """Punto de entrada sincrónico para ser llamado desde main_scraper.py."""
    try:
        return asyncio.run(_extraer_tweets_semana())
    except Exception as e:
        print(f"Error al ejecutar scraper de ETED: {e}")
        return []

if __name__ == "__main__":
    resultados = get_mantenimientos_eted()
    print(f"Reportes ETED encontrados esta semana: {len(resultados)}")
