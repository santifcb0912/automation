"""Repositorio de lectura para Google Sheets.

Mapa mental si vienes de Spring Boot: similar a un repository con metodos tipo findLeadsByCountry.
Abre el spreadsheet configurado, detecta la pestana semanal cuando aplica, normaliza tipos de formulario y retorna LeadRow.
"""

import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from typing import List, Optional
from loguru import logger

from config.settings import settings
from config.models import LeadRow, FormType
from config.google_auth import get_google_credentials


class SheetsReader:
    """
    Lee el Google Sheets y retorna los leads a procesar.
    Equivalente a un @Repository en Spring Boot.
    Se conecta a Google una sola vez y reutiliza la conexión.
    """

    def __init__(self):
        self._client: Optional[gspread.Client] = None

        self._connect()

    def _connect(self) -> None:
        """
        Establece la conexión con Google Sheets usando la Service Account.
        Equivalente a configurar el DataSource en Spring Boot.
        Solo se ejecuta una vez al inicio.
        """
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

    def detect_current_tab(self, spreadsheet: gspread.Spreadsheet) -> str:
        """
        Detecta automáticamente qué hoja del Sheets usar según la fecha actual.
        Cada hoja representa una semana laboral (ej: "27-30", "06-10").

        Lógica:
        - Obtenemos el día de hoy
        - Buscamos la hoja cuyo rango de días incluya el día de hoy
        - Si no encontramos coincidencia exacta, usamos la primera hoja disponible
        """
        today_day = datetime.now().day

        logger.info(f"📅 Día actual: {today_day} — buscando hoja correspondiente")

        sheet_names = [ws.title for ws in spreadsheet.worksheets()]
        logger.info(f"📋 Hojas disponibles: {sheet_names}")

        for sheet_name in sheet_names:
            if sheet_name.lower() == "val":
                continue

            try:
                parts = sheet_name.split("-")
                if len(parts) != 2:
                    continue

                start_day = int(parts[0])

                end_str = parts[1]
                end_day = int(end_str)

                if start_day <= today_day <= end_day:
                    logger.info(f"✅ Hoja detectada automáticamente: {sheet_name}")
                    return sheet_name

                if start_day > end_day:
                    if today_day >= start_day or today_day <= end_day:
                        logger.info(f"✅ Hoja detectada (cruza mes): {sheet_name}")
                        return sheet_name

            except (ValueError, IndexError):
                continue

        lead_sheets = [s for s in sheet_names if s.lower() != "val"]
        if lead_sheets:
            fallback = lead_sheets[-1]
            logger.warning(f"⚠️  No se detectó hoja para hoy — usando última disponible: {fallback}")
            return fallback

        raise ValueError("No se encontraron hojas de leads en el Sheets")

    def get_leads(
        self,
        country_name: str,
        sheet_id: Optional[str] = None,
        sheet_tab: Optional[str] = None,
        mexico_flow: Optional[str] = None
    ) -> tuple[List[LeadRow], str]:
        """
        Lee el Sheets y retorna la lista de leads del país solicitado.
        Equivalente a un método findByCountry() en un @Repository de Spring.

        Parámetros:
            country_name: nombre del país como aparece en columna B
            sheet_id: ID del Sheets (opcional — si no se pasa usa el del .env)
            sheet_tab: nombre de la hoja (opcional — si no se pasa lo detecta)

        Retorna:
            tuple de (lista de LeadRow, nombre de la hoja usada)
        """
        spreadsheet_id = sheet_id or settings.google_sheet_id

        try:
            logger.info(f"📖 Abriendo Sheets ID: {spreadsheet_id}")

            spreadsheet = self._client.open_by_key(spreadsheet_id)

            tab_name = sheet_tab or self.detect_current_tab(spreadsheet)

            logger.info(f"📋 Leyendo hoja: {tab_name} | País: {country_name}")

            worksheet = spreadsheet.worksheet(tab_name)

            all_rows = worksheet.get_all_values()

            leads = []
            for row_idx, row in enumerate(all_rows[1:], start=2):
                if len(row) < 5:
                    continue

                country_col = row[1].strip() if row[1] else ""
                nivel_col   = row[2].strip() if row[2] else None
                url_col     = row[3].strip() if row[3] else ""
                location_col = row[4].strip() if row[4] else ""
                cliente_col  = row[5].strip() if len(row) > 5 and row[5] else ""

                if not url_col:
                    continue

                clean_url = url_col.split()[0] if url_col else ""
                url_lower = clean_url.lower()
                flow = (mexico_flow or "").strip().lower()
                if flow == "universidad" or "niversidad" in flow:
                    flow = "universidad"
                is_mexico = country_name.strip().lower() in ["mexico", "méxico", "mã©xico"]
                is_universidad_mexico_row = (
                    is_mexico
                    and flow == "universidad"
                    and url_lower.startswith("https://universidad.utel.edu.mx")
                )
                is_cms_mexico_row = (
                    is_mexico
                    and flow == "cms"
                    and url_lower.startswith("https://utel.edu.mx")
                )

                if (
                    country_name.lower() not in country_col.lower()
                    and country_col.lower() not in country_name.lower()
                    and not is_universidad_mexico_row
                    and not is_cms_mexico_row
                ):
                    continue

                form_type_raw = location_col.strip()
                form_type_key = form_type_raw.lower().replace(" ", "").replace("-", "").replace("_", "")
                form_type_map = {
                    "footer": "Footer",
                    "lateral": "Lateral",
                    "tarjeta": "Tarjeta",
                    "targeta": "Tarjeta",
                    "formlp": "FormLP",
                    "form": "FormLP",
                }
                form_type = form_type_map.get(form_type_key, form_type_raw)

                lead = LeadRow(
                    row_number=row_idx,
                    country_name=country_col,
                    nivel=nivel_col,
                    landing_url=clean_url,
                    form_type=form_type,
                    cliente=cliente_col,
                )

                leads.append(lead)

            logger.info(f"✅ {len(leads)} leads encontrados para {country_name} en hoja {tab_name}")
            return leads, tab_name

        except gspread.exceptions.SpreadsheetNotFound:
            logger.error(f"❌ Sheets no encontrado con ID: {spreadsheet_id}")
            logger.error("   Verifica que el GOOGLE_SHEET_ID en .env sea correcto")
            raise

        except Exception as e:
            logger.error(f"❌ Error leyendo Sheets: {e}")
            raise

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
