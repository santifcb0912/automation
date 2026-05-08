# ============================================================
# sheets/reader.py
# Lee el Google Sheets y retorna la lista de leads a procesar
# Equivalente a un @Repository en Spring Boot que lee de base de datos
# Aquí la "base de datos" es el Google Sheets de UTEL
# ============================================================

import gspread                              # Librería para Google Sheets
from google.oauth2.service_account import Credentials  # Para autenticarse con Google
from datetime import datetime               # Para detectar la semana actual
from typing import List, Optional           # Para tipos de datos
from loguru import logger                   # Para logs

from config.settings import settings        # Configuración del sistema
from config.models import LeadRow, FormType # Modelos de datos


# Permisos que necesitamos de Google
# Estos "scopes" le dicen a Google qué puede hacer el sistema
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",  # Leer y escribir en Sheets
    "https://www.googleapis.com/auth/drive",          # Subir archivos a Drive
]


class SheetsReader:
    """
    Lee el Google Sheets y retorna los leads a procesar.
    Equivalente a un @Repository en Spring Boot.
    Se conecta a Google una sola vez y reutiliza la conexión.
    """

    def __init__(self):
        # Cliente de Google Sheets — se inicializa en connect()
        self._client: Optional[gspread.Client] = None

        # Conectamos a Google al crear la instancia
        self._connect()

    def _connect(self) -> None:
        """
        Establece la conexión con Google Sheets usando la Service Account.
        Equivalente a configurar el DataSource en Spring Boot.
        Solo se ejecuta una vez al inicio.
        """
        try:
            logger.info("🔗 Conectando con Google Sheets...")

            # Cargamos las credenciales desde el archivo JSON de la Service Account
            # Este archivo lo descargaste de Google Cloud Console
            credentials = Credentials.from_service_account_file(
                settings.google_credentials_path,  # Ruta al archivo JSON
                scopes=GOOGLE_SCOPES               # Permisos que necesitamos
            )

            # Creamos el cliente de gspread con las credenciales
            self._client = gspread.authorize(credentials)
            logger.info("✅ Conexión con Google Sheets establecida")

        except FileNotFoundError:
            # Si no encuentra el archivo JSON, mostramos instrucciones claras
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
        # Obtenemos el día del mes de hoy (ej: 27 para el 27 de abril)
        today_day = datetime.now().day

        logger.info(f"📅 Día actual: {today_day} — buscando hoja correspondiente")

        # Obtenemos los nombres de todas las hojas del Sheets
        sheet_names = [ws.title for ws in spreadsheet.worksheets()]
        logger.info(f"📋 Hojas disponibles: {sheet_names}")

        # Recorremos cada hoja y verificamos si el día de hoy está en su rango
        for sheet_name in sheet_names:
            # Ignoramos la hoja "Val" que es de validación, no de leads
            if sheet_name.lower() == "val":
                continue

            # Intentamos parsear el rango de días de la hoja
            # El formato es "DD-DD" o "DD-MM" (ej: "27-30", "30-03")
            try:
                # Separamos el nombre de la hoja por el guion
                parts = sheet_name.split("-")
                if len(parts) != 2:
                    continue

                # El primer número es el día de inicio de la semana
                start_day = int(parts[0])

                # El segundo número puede ser el día final o el mes siguiente
                end_str = parts[1]
                end_day = int(end_str)

                # Verificamos si hoy está en el rango de la hoja
                if start_day <= today_day <= end_day:
                    logger.info(f"✅ Hoja detectada automáticamente: {sheet_name}")
                    return sheet_name

                # Caso especial: semana que cruza fin de mes (ej: "30-03")
                # Si el día inicio es mayor al día fin, es porque cruza el mes
                if start_day > end_day:
                    if today_day >= start_day or today_day <= end_day:
                        logger.info(f"✅ Hoja detectada (cruza mes): {sheet_name}")
                        return sheet_name

            except (ValueError, IndexError):
                # Si el nombre de la hoja no tiene el formato esperado, la saltamos
                continue

        # Si no encontramos coincidencia, usamos la última hoja de leads disponible
        # Filtramos las hojas que no son "Val"
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
        sheet_tab: Optional[str] = None
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
        # Usamos el ID del Sheets pasado o el del .env
        spreadsheet_id = sheet_id or settings.google_sheet_id

        try:
            logger.info(f"📖 Abriendo Sheets ID: {spreadsheet_id}")

            # Abrimos el Sheets por su ID
            spreadsheet = self._client.open_by_key(spreadsheet_id)

            # Detectamos o usamos la hoja indicada
            tab_name = sheet_tab or self.detect_current_tab(spreadsheet)

            logger.info(f"📋 Leyendo hoja: {tab_name} | País: {country_name}")

            # Abrimos la hoja específica
            worksheet = spreadsheet.worksheet(tab_name)

            # Leemos todas las filas como lista de listas
            # La primera fila son los encabezados (Country, Nivel, etc.)
            all_rows = worksheet.get_all_values()

            # Procesamos cada fila y construimos la lista de LeadRow
            leads = []
            # Empezamos en fila 1 (índice 1) para saltarnos los encabezados (fila 0)
            for row_idx, row in enumerate(all_rows[1:], start=2):
                # Verificamos que la fila tenga suficientes columnas
                if len(row) < 5:
                    continue

                # Leemos cada columna de la fila
                # Columna A (índice 0): Responsable — no la necesitamos
                country_col = row[1].strip() if row[1] else ""   # Columna B: Country
                nivel_col   = row[2].strip() if row[2] else None  # Columna C: Nivel
                url_col     = row[3].strip() if row[3] else ""   # Columna D: URL LP
                location_col = row[4].strip() if row[4] else ""  # Columna E: Location
                cliente_col  = row[5].strip() if len(row) > 5 and row[5] else ""  # Columna F

                # Saltamos filas que no tienen URL (filas vacías)
                if not url_col:
                    continue

                # Filtramos por país — solo procesamos el país solicitado
                # Comparación flexible: ignoramos mayúsculas y tildes parcialmente
                if country_name.lower() not in country_col.lower() and \
                   country_col.lower() not in country_name.lower():
                    continue

                # Limpiamos la URL — a veces tiene espacios o saltos de línea
                # También puede tener dos URLs en la misma celda (como la fila 19 de Perú)
                clean_url = url_col.split()[0] if url_col else ""

                # Normalizamos el tipo de formulario
                # "Targeta" y "Tarjeta" son el mismo tipo (error tipográfico en el Sheets)
                form_type = location_col
                if form_type.lower() in ["targeta", "tarjeta"]:
                    form_type = "Tarjeta"

                # Creamos el objeto LeadRow con los datos de la fila
                lead = LeadRow(
                    row_number=row_idx,    # Número de fila para escribir el resultado
                    country_name=country_col,
                    nivel=nivel_col,
                    landing_url=clean_url,
                    form_type=form_type,
                    cliente=cliente_col,
                )

                # Agregamos el lead a la lista
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
        # datetime.now().weekday() retorna:
        # 0=Lunes, 1=Martes, 2=Miércoles, 3=Jueves, 4=Viernes
        day_of_week = datetime.now().weekday()

        # Mapa de día de semana a letra de columna
        day_to_column = {
            0: "G",  # Lunes
            1: "H",  # Martes
            2: "I",  # Miércoles
            3: "J",  # Jueves
            4: "K",  # Viernes
        }

        # Si es fin de semana (5=Sábado, 6=Domingo), usamos Viernes por defecto
        column = day_to_column.get(day_of_week, "K")

        logger.info(f"📅 Día {day_of_week} → Columna {column}")
        return column
