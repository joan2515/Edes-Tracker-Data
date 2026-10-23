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
    """Convierte fechas a formato 'Lunes 19 de octubre del 2026'."""
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
    """Convierte horas al formato estándar '4:00 p.m.'."""
    if pd.isna(valor):
