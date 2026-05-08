# ============================================================
# automation/screenshot.py
# Toma la captura de pantalla del panel de InConcert
# y la sube a Google Drive retornando el link público
# Equivalente a un @Service de almacenamiento en Spring Boot
# ============================================================

import os                                               # Para manejo de archivos
from pathlib import Path                                # Para rutas de archivos
from datetime import datetime                           # Para nombres únicos de archivos
from typing import Optional                             # Para tipos opcionales
from playwright.async_api import Page                   # Tipo de página de Playwright
from google.oauth2.service_account import Credentials  # Para autenticarse con Google
from googleapiclient.discovery import build            # Para usar la API de Drive
from googleapiclient.http import MediaFileUpload       # Para subir archivos a Drive
from loguru import logger                               # Para logs

from config.settings import settings                    # Configuración del sistema


# Permisos necesarios para Google Drive
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/drive",           # Acceso completo a Drive
    "https://www.googleapis.com/auth/spreadsheets",    # Acceso a Sheets
]


class ScreenshotManager:
    """
    Maneja la captura de pantalla y su subida a Google Drive.
    Equivalente a un @Service de storage en Spring Boot.

    Proceso completo:
    1. Playwright toma el screenshot de las 3 columnas
    2. Se guarda temporalmente en /screenshots/
    3. Se sube a Google Drive en la carpeta "Capturas UTEL"
    4. Se genera un link público compartible
    5. Se elimina el archivo temporal local
    6. Se retorna el link para escribirlo en Sheets
    """

    def __init__(self):
        # ID de la carpeta en Google Drive donde se guardan las capturas
        # Se obtiene o crea automáticamente en get_or_create_folder()
        self._drive_folder_id: Optional[str] = None

        # Servicio de Google Drive API
        self._drive_service = None

        # Inicializamos la conexión con Drive
        self._connect_drive()

        # Aseguramos que existe la carpeta local de screenshots
        Path(settings.screenshots_dir).mkdir(parents=True, exist_ok=True)

        logger.debug("📸 ScreenshotManager inicializado")

    def _connect_drive(self) -> None:
        """
        Establece la conexión con Google Drive usando la Service Account.
        Usa las mismas credenciales que Google Sheets.
        """
        try:
            logger.info("🔗 Conectando con Google Drive...")

            # Cargamos las credenciales del archivo JSON de la Service Account
            credentials = Credentials.from_service_account_file(
                settings.google_credentials_path,
                scopes=GOOGLE_SCOPES
            )

            # Construimos el servicio de Drive API v3
            # Es la versión más actual de la API de Google Drive
            self._drive_service = build(
                "drive",   # Nombre del servicio
                "v3",      # Versión de la API
                credentials=credentials
            )

            logger.info("✅ Conexión con Google Drive establecida")

        except FileNotFoundError:
            logger.error(f"❌ Archivo de credenciales no encontrado: {settings.google_credentials_path}")
            raise

        except Exception as e:
            logger.error(f"❌ Error conectando con Google Drive: {e}")
            raise

    def _get_or_create_folder(self) -> str:
        """
        Obtiene el ID de la carpeta "Capturas UTEL" en Google Drive.
        Si la carpeta no existe, la crea automáticamente.

        Retorna:
            ID de la carpeta en Google Drive
        """
        # Si ya tenemos el ID guardado, lo retornamos directamente
        if self._drive_folder_id:
            return self._drive_folder_id

        folder_name = settings.google_drive_folder_name
        logger.info(f"📁 Buscando carpeta '{folder_name}' en Google Drive...")

        # Buscamos la carpeta por nombre en Drive
        # La query de Drive API usa su propio lenguaje de consulta
        query = (
            f"name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )

        # Ejecutamos la búsqueda
        results = self._drive_service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)"
        ).execute()

        folders = results.get("files", [])

        if folders:
            # La carpeta ya existe — usamos su ID
            self._drive_folder_id = folders[0]["id"]
            logger.info(f"✅ Carpeta encontrada: ID={self._drive_folder_id}")
        else:
            # La carpeta no existe — la creamos
            logger.info(f"📁 Creando carpeta '{folder_name}' en Google Drive...")

            folder_metadata = {
                "name": folder_name,
                # Este mimeType le dice a Drive que es una carpeta
                "mimeType": "application/vnd.google-apps.folder"
            }

            folder = self._drive_service.files().create(
                body=folder_metadata,
                fields="id"
            ).execute()

            self._drive_folder_id = folder["id"]
            logger.info(f"✅ Carpeta creada: ID={self._drive_folder_id}")

            # Hacemos la carpeta pública para que los links funcionen
            self._make_folder_public(self._drive_folder_id)

        return self._drive_folder_id

    def _make_folder_public(self, folder_id: str) -> None:
        """
        Hace pública una carpeta de Google Drive.
        Necesario para que los links de las capturas sean accesibles.
        """
        try:
            # Creamos un permiso de lectura para "cualquier persona"
            permission = {
                "type": "anyone",   # Cualquier persona
                "role": "reader",   # Solo lectura
            }

            self._drive_service.permissions().create(
                fileId=folder_id,
                body=permission
            ).execute()

            logger.info("✅ Carpeta de Drive configurada como pública")

        except Exception as e:
            logger.warning(f"⚠️  No se pudo hacer pública la carpeta: {e}")

    async def take_and_upload(
        self,
        page: Page,
        country_name: str,
        test_email: str
    ) -> Optional[str]:
        """
        Método principal: toma el screenshot y lo sube a Drive.

        El screenshot captura el estado actual del panel de InConcert
        con las 3 columnas en el estado correcto:
        - Columna izquierda: sección "Contacto" expandida, scroll al fondo
        - Columna central: evento "Creación" expandido, "Origen Id" visible
        - Columna derecha: panel "Gestión" intacto (no se tocó)

        Parámetros:
            page: la pestaña del navegador con InConcert abierto
            country_name: nombre del país (para nombrar el archivo)
            test_email: correo de prueba (para nombrar el archivo)

        Retorna:
            link público del archivo en Google Drive
            None si hubo algún error
        """
        local_path = None

        try:
            # Paso 1: Tomamos el screenshot y lo guardamos localmente
            local_path = await self._take_screenshot(page, country_name, test_email)

            if not local_path:
                return None

            # Paso 2: Subimos el archivo a Google Drive
            drive_link = self._upload_to_drive(local_path, country_name)

            return drive_link

        except Exception as e:
            logger.error(f"❌ Error en take_and_upload: {e}")
            return None

        finally:
            # Paso 3: Eliminamos el archivo temporal local siempre
            # El "finally" garantiza que se ejecuta aunque haya error
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                    logger.debug(f"🗑️  Archivo temporal eliminado: {local_path}")
                except Exception:
                    pass

    async def _take_screenshot(
        self,
        page: Page,
        country_name: str,
        test_email: str
    ) -> Optional[str]:
        """
        Toma el screenshot de la página actual de Playwright.
        Genera un nombre de archivo único con fecha, país y email.

        Retorna la ruta local del archivo de imagen.
        """
        try:
            # Generamos un nombre de archivo único para evitar colisiones
            # Formato: captura_Colombia_test190326N001_20260519_103045.png
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Limpiamos el email para usarlo como nombre de archivo
            email_clean = test_email.replace("@", "_").replace(".", "_")
            filename = f"captura_{country_name}_{email_clean}_{timestamp}.png"

            # Ruta completa donde guardamos el archivo
            filepath = os.path.join(settings.screenshots_dir, filename)

            logger.info(f"📸 Tomando screenshot → {filename}")

            # Tomamos el screenshot de toda la página visible
            # full_page=False captura solo lo que se ve en pantalla
            # (las 3 columnas deben estar visibles sin scroll adicional)
            await page.screenshot(
                path=filepath,
                full_page=False,   # Solo lo visible — no toda la página
                type="png"         # Formato PNG para mejor calidad
            )

            logger.info(f"✅ Screenshot guardado: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Error tomando screenshot: {e}")
            return None

    def _upload_to_drive(self, local_path: str, country_name: str) -> Optional[str]:
        """
        Sube el archivo de screenshot a Google Drive.
        Lo coloca en la carpeta "Capturas UTEL" y genera un link público.

        Parámetros:
            local_path: ruta local del archivo PNG
            country_name: nombre del país (para organizar en Drive)

        Retorna:
            link público del archivo en Google Drive
            None si hubo error
        """
        try:
            # Obtenemos el ID de la carpeta destino
            folder_id = self._get_or_create_folder()

            # Nombre del archivo en Drive (usamos el nombre del archivo local)
            file_name = os.path.basename(local_path)

            logger.info(f"☁️  Subiendo a Google Drive: {file_name}")

            # Metadatos del archivo en Drive
            file_metadata = {
                "name": file_name,
                # Indicamos en qué carpeta de Drive guardar el archivo
                "parents": [folder_id]
            }

            # MediaFileUpload prepara el archivo para ser subido
            # mimetype indica que es una imagen PNG
            media = MediaFileUpload(
                local_path,
                mimetype="image/png",
                resumable=False  # Para archivos pequeños, no necesitamos subida resumable
            )

            # Subimos el archivo a Drive
            uploaded_file = self._drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id"  # Solo necesitamos el ID del archivo subido
            ).execute()

            file_id = uploaded_file["id"]
            logger.info(f"✅ Archivo subido a Drive: ID={file_id}")

            # Hacemos el archivo público para que el link sea accesible
            self._make_file_public(file_id)

            # Construimos el link público de Google Drive
            # Este formato genera un link que cualquiera puede ver
            public_link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

            logger.success(f"✅ Link de captura: {public_link}")
            return public_link

        except Exception as e:
            logger.error(f"❌ Error subiendo a Google Drive: {e}")
            return None

    def _make_file_public(self, file_id: str) -> None:
        """
        Hace público un archivo en Google Drive.
        Sin esto, el link solo funciona para el propietario.
        """
        try:
            # Permiso de lectura para cualquier persona con el link
            permission = {
                "type": "anyone",
                "role": "reader",
            }

            self._drive_service.permissions().create(
                fileId=file_id,
                body=permission
            ).execute()

            logger.debug(f"✅ Archivo {file_id} configurado como público")

        except Exception as e:
            logger.warning(f"⚠️  No se pudo hacer público el archivo: {e}")
