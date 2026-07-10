"""Repositorio de lectura para Google Sheets.
"""

from enum import IntEnum

import gspread
from datetime import datetime
from typing import List, Optional
from loguru import logger
from config.settings import settings
from config.google_auth import get_google_credentials
from core.models import LeadRow


class Column(IntEnum):
    COUNTRY = 1
    NIVEL = 2
    URL = 3
    LOCATION = 4
    CLIENTE = 5


class SheetsReader:

    FORM_TYPE_MAP = {
        "footer": "Footer",
        "lateral": "Lateral",
        "tarjeta": "Tarjeta",
        "formlp": "FormLP",
        "form": "FormLP",
    }

    # Prepara el cliente de Google Sheets. La conexión se abre al instanciar.
    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._connect()

    # Establece la conexión con Google Sheets usando la Service Account.
    def _connect(self) -> None:
        try:
            logger.info("🔗 Conectando con Google Sheets...")
            credentials = get_google_credentials()
            self._client = gspread.authorize(credentials)
            logger.info("✅ Conexión con Google Sheets establecida")

        except FileNotFoundError:
            logger.error(f"❌ No se encontró el archivo de credenciales: {settings.google_credentials_path}")
            logger.error("   Sigue las instrucciones del README para crear la Service Account")
            raise

        except Exception as e:
            logger.error(f"❌ Error conectando con Google: {e}")
            raise

    # Lee el Sheets y retorna los leads del país indicado para la hoja especificada.
    def get_leads(
        self,
        country_name: str,
        sheet_id: str,
        sheet_tab: str,
    ) -> tuple[List[LeadRow], str]:
        logger.info(f"📖 Abriendo Sheets ID: {sheet_id}")
        logger.info(f"📋 Leyendo hoja: {sheet_tab} | País: {country_name}")

        try:
            spreadsheet = self._client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(sheet_tab)
            all_rows = worksheet.get_all_values()
        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"❌ Sheets no encontrado con ID: {sheet_id}")
            raise

        leads = []
        for row_idx, row in enumerate(all_rows[1:], start=2):
            if len(row) < 5:
                continue

            country_val = row[Column.COUNTRY].strip() if row[Column.COUNTRY] else ""
            if not country_val or country_name.lower() not in country_val.lower():
                continue

            url = row[Column.URL].strip() if row[Column.URL] else ""
            if not url:
                continue

            leads.append(LeadRow(
                row_number=row_idx,
                country_name=country_val,
                nivel=row[Column.NIVEL].strip() if row[Column.NIVEL] else None,
                landing_url=url.split()[0],
                form_type=self._normalize_form_type(row[Column.LOCATION].strip() if row[Column.LOCATION] else ""),
                cliente=row[Column.CLIENTE].strip() if len(row) > Column.CLIENTE and row[Column.CLIENTE] else "",
            ))

        logger.info(f"✅ {len(leads)} leads para {country_name} en hoja {sheet_tab}")
        return leads, sheet_tab

    # Normaliza el valor de tipo de formulario usando un mapa de sinónimos.
    @staticmethod
    def _normalize_form_type(raw: str) -> str:
        key = raw.lower().replace(" ", "").replace("-", "").replace("_", "")
        return SheetsReader.FORM_TYPE_MAP.get(key, raw)
        

    def get_column_for_today(self) -> str:
        """
        Retorna la letra de la columna del Sheets correspondiente al día de hoy.
        El sistema siempre escribe en la columna del día actual.

        Lunes    → columna G
        Martes   → columna H
        Miércoles → columna I
        Jueves   → columna J
        Viernes  → columna K
        """
        day_of_week = datetime.now().weekday()

        day_to_column = {
            0: "G",
            1: "H",
            2: "I",
            3: "J",
            4: "K",
        }

        column = day_to_column.get(day_of_week, "K")

        logger.info(f"📅 Día {day_of_week} → Columna {column}")
        return column
