"""Repositorio de escritura para Google Sheets.

Escribe el link final de Drive o un marcador de error en la columna del dia correspondiente a la fila procesada.
"""

import time
from typing import Optional

import gspread
from loguru import logger

from config.google_auth import get_google_credentials


WRITE_MAX_ATTEMPTS = 3
WRITE_RETRY_DELAY_SECONDS = 3


class SheetsWriter:

    # Prepara el cliente de Google Sheets. La conexion se abre al instanciar
    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._connect()

    # Establece la conexion con Google Sheets
    def _connect(self) -> None:
        try:
            logger.info("🔗 SheetsWriter conectando con Google...")
            credentials = get_google_credentials()
            self._client = gspread.authorize(credentials)
            logger.info("✅ SheetsWriter conectado")

        except Exception as e:
            logger.error(f"❌ Error conectando SheetsWriter: {e}")
            raise

    # Reintenta la escritura hasta N veces con reconexion entre intentos
    def _write_with_retries(self, write_fn, *args) -> None:
        for attempt in range(1, WRITE_MAX_ATTEMPTS + 1):
            try:
                write_fn(*args)
                return
            except Exception as e:
                if attempt < WRITE_MAX_ATTEMPTS:
                    logger.warning(f"Reintentando escritura en Sheets ({attempt + 1}/{WRITE_MAX_ATTEMPTS}): {e}")
                    self._connect()
                    time.sleep(WRITE_RETRY_DELAY_SECONDS)
                else:
                    raise

    # Abre el sheet y escribe el valor en la celda indicada
    def _do_write(self, sheet_id: str, tab_name: str, cell: str, value: list) -> None:
        spreadsheet = self._client.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(tab_name)
        worksheet.update(cell, value)

    # Escribe el link de la captura en la celda {columna}{fila} del sheet
    def write_success(
        self,
        sheet_id: str,
        tab_name: str,
        row_number: int,
        column: str,
        screenshot_link: str,
        test_email: str
    ) -> None:
        cell = f"{column}{row_number}"
        logger.info(f"✍️  Escribiendo en {tab_name}!{cell} → {screenshot_link[:50]}...")
        try:
            self._write_with_retries(self._do_write, sheet_id, tab_name, cell, [[screenshot_link]])
            logger.success(f"✅ Link escrito en {cell} para {test_email}")
        except Exception as e:
            logger.error(f"❌ Error escribiendo resultado en Sheets: {e}")
            logger.error(f"   Celda: {tab_name}!{column}{row_number}")
            raise

    # Escribe un mensaje de error en la celda cuando el lead no llego (timeout de 2 min)
    def write_error(
        self,
        sheet_id: str,
        tab_name: str,
        row_number: int,
        column: str,
        test_email: str,
        reason: str = "timeout 2 min"
    ) -> None:
        cell = f"{column}{row_number}"
        error_message = f"ERROR - lead no llegó ({reason}) - revisión manual"
        logger.warning(f"⚠️  Escribiendo error en {tab_name}!{cell} para {test_email}")
        try:
            self._write_with_retries(self._do_write, sheet_id, tab_name, cell, [[error_message]])
            logger.warning(f"❌ Error registrado en {cell}: {reason}")
        except Exception as e:
            logger.error(f"❌ Error escribiendo mensaje de error en Sheets: {e}")
            raise
