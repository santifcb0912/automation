"""Repositorio de escritura para Google Sheets.

Escribe el link final de Drive o un marcador de error en la columna del dia correspondiente a la fila procesada.
"""

import gspread
from google.oauth2.service_account import Credentials
from typing import Optional
from loguru import logger

from config.google_auth import get_google_credentials

class SheetsWriter:
    """
    Escribe resultados en el Google Sheets.
    Equivalente a un @Repository con métodos save() en Spring Boot.
    """

    def __init__(self):
        self._client: Optional[gspread.Client] = None

        self._connect()

    def _connect(self) -> None:
        """
        Establece la conexión con Google Sheets.
        La misma lógica que en SheetsReader — reutilizamos credenciales.
        """
        try:
            logger.info("🔗 SheetsWriter conectando con Google...")

            credentials = get_google_credentials()

            self._client = gspread.authorize(credentials)
            logger.info("✅ SheetsWriter conectado")

        except Exception as e:
            logger.error(f"❌ Error conectando SheetsWriter: {e}")
            raise

    def write_success(
        self,
        sheet_id: str,
        tab_name: str,
        row_number: int,
        column: str,
        screenshot_link: str,
        test_email: str
    ) -> None:
        """
        Escribe el link de la captura de pantalla en la celda correcta.
        Se llama cuando el lead llegó exitosamente a InConcert.

        Parámetros:
            sheet_id: ID del Google Sheets del mes actual
            tab_name: nombre de la hoja (ej: "27-30")
            row_number: número de fila donde escribir (ej: 86)
            column: letra de columna del día actual (ej: "G" para Lunes)
            screenshot_link: link de Google Drive de la captura
            test_email: correo de prueba (para el log)
        """
        try:
            cell = f"{column}{row_number}"

            logger.info(f"✍️  Escribiendo en {tab_name}!{cell} → {screenshot_link[:50]}...")

            spreadsheet = self._client.open_by_key(sheet_id)

            worksheet = spreadsheet.worksheet(tab_name)

            worksheet.update(cell, [[screenshot_link]])

            logger.success(f"✅ Link escrito en {cell} para {test_email}")

        except Exception as e:
            logger.error(f"❌ Error escribiendo resultado en Sheets: {e}")
            logger.error(f"   Celda: {tab_name}!{column}{row_number}")
            raise

    def write_error(
        self,
        sheet_id: str,
        tab_name: str,
        row_number: int,
        column: str,
        test_email: str,
        reason: str = "timeout 5 min"
    ) -> None:
        """
        Escribe un mensaje de error en la celda cuando el lead no llegó.
        Se llama cuando el timeout de 5 minutos se cumplió sin encontrar el lead.

        Parámetros:
            sheet_id: ID del Google Sheets
            tab_name: nombre de la hoja
            row_number: número de fila
            column: letra de columna del día
            test_email: correo de prueba (para identificar el lead)
            reason: motivo del error
        """
        try:
            cell = f"{column}{row_number}"

            error_message = f"ERROR - lead no llegó ({reason}) - revisión manual"

            logger.warning(f"⚠️  Escribiendo error en {tab_name}!{cell} para {test_email}")

            spreadsheet = self._client.open_by_key(sheet_id)
            worksheet = spreadsheet.worksheet(tab_name)

            worksheet.update(cell, [[error_message]])

            logger.warning(f"❌ Error registrado en {cell}: {reason}")

        except Exception as e:
            logger.error(f"❌ Error escribiendo mensaje de error en Sheets: {e}")
            raise
