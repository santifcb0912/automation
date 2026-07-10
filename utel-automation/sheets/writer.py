"""Repositorio de escritura para Google Sheets.

Escribe el link final de Drive o un marcador de error en la columna del dia correspondiente a la fila procesada.
"""

import gspread
from typing import Optional
from loguru import logger

from config.google_auth import get_google_credentials



class SheetsWriter:

    #Escribe resultados en el Google Sheets.
    


 # Prepara el cliente de Google Sheets. La conexión se abre al instanciar.
    def __init__(self):
        self._client: Optional[gspread.Client] = None
        self._connect()

 
 #  Establece la conexión con Google Sheets.
    def _connect(self) -> None:
        
        #Establece la conexión con Google Sheets.
        try:
            logger.info("🔗 SheetsWriter conectando con Google...")
            credentials = get_google_credentials()
            self._client = gspread.authorize(credentials)
            logger.info("✅ SheetsWriter conectado")

        except Exception as e:
            logger.error(f"❌ Error conectando SheetsWriter: {e}")
            raise

 # Escribe el link de la captura en la celda {columna}{fila} del sheet.
    def write_success(
        self,
        sheet_id: str,
        tab_name: str,
        row_number: int,
        column: str,
        screenshot_link: str,
        test_email: str
    ) -> None:
        
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
     
        
    #Escribe un mensaje de error en la celda cuando el lead no llegó.
    #Se llama cuando el timeout de 2 minutos se cumplió sin encontrar el lead.
    def write_error(
        self,
        sheet_id: str,
        tab_name: str,
        row_number: int,
        column: str,
        test_email: str,
        reason: str = "timeout 2 min"
    ) -> None:
      
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
