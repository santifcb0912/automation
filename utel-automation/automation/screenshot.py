"""Servicio de captura de pantalla y almacenamiento en Google Drive.

Captura la vista preparada de InConcert, sube el PNG a Drive, lo comparte y retorna el link que SheetsWriter guarda en Google Sheets.
"""

import os
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from playwright.async_api import Page
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from loguru import logger

from config.settings import settings
from config.google_auth import get_google_credentials

DRIVE_UPLOAD_MAX_ATTEMPTS = 3
DRIVE_UPLOAD_RETRY_DELAY_SECONDS = 3


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
        self._drive_folder_id: Optional[str] = None

        self._drive_service = None

        self._connect_drive()

        Path(settings.screenshots_dir).mkdir(parents=True, exist_ok=True)

        logger.debug("📸 ScreenshotManager inicializado")

    def _connect_drive(self) -> None:
        """
        Establece la conexión con Google Drive usando la Service Account.
        Usa las mismas credenciales que Google Sheets.
        """
        try:
            logger.info("🔗 Conectando con Google Drive...")

            credentials = get_google_credentials()

            self._drive_service = build(
                "drive",
                "v3",
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
        if self._drive_folder_id:
            return self._drive_folder_id

        folder_name = settings.google_drive_folder_name
        logger.info(f"📁 Buscando carpeta '{folder_name}' en Google Drive...")

        query = (
            f"name='{folder_name}' "
            f"and mimeType='application/vnd.google-apps.folder' "
            f"and trashed=false"
        )

        results = self._drive_service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, driveId)",
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()

        folders = results.get("files", [])

        if folders:
            self._drive_folder_id = folders[0]["id"]
            logger.info(f"✅ Carpeta encontrada: ID={self._drive_folder_id}")
        else:
            logger.info(f"📁 Creando carpeta '{folder_name}' en Google Drive...")

            folder_metadata = {
                "name": folder_name,
                "mimeType": "application/vnd.google-apps.folder"
            }

            folder = self._drive_service.files().create(
                body=folder_metadata,
                fields="id",
                supportsAllDrives=True,
            ).execute()

            self._drive_folder_id = folder["id"]
            logger.info(f"✅ Carpeta creada: ID={self._drive_folder_id}")

            self._make_folder_public(self._drive_folder_id)

        return self._drive_folder_id

    def _make_folder_public(self, folder_id: str) -> None:
        """
        Hace pública una carpeta de Google Drive.
        Necesario para que los links de las capturas sean accesibles.
        """
        try:
            permission = {
                "type": "anyone",
                "role": "reader",
            }

            self._drive_service.permissions().create(
                fileId=folder_id,
                body=permission,
                supportsAllDrives=True,
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
        drive_link = None

        try:
            local_path = await self._take_screenshot(page, country_name, test_email)

            if not local_path:
                return None

            drive_link = self._upload_to_drive_with_retries(local_path, country_name)

            return drive_link

        except Exception as e:
            logger.error(f"❌ Error en take_and_upload: {e}")
            return None

        finally:
            if local_path and os.path.exists(local_path) and drive_link:
                try:
                    os.remove(local_path)
                    logger.debug(f"🗑️  Archivo temporal eliminado: {local_path}")
                except Exception:
                    pass
            elif local_path and os.path.exists(local_path):
                logger.warning(f"Screenshot local conservado porque no se obtuvo link de Drive: {local_path}")

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
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            email_clean = test_email.replace("@", "_").replace(".", "_")
            filename = f"captura_{country_name}_{email_clean}_{timestamp}.png"

            filepath = os.path.join(settings.screenshots_dir, filename)

            logger.info(f"📸 Tomando screenshot → {filename}")

            await page.screenshot(
                path=filepath,
                full_page=False,
                type="png"
            )

            logger.info(f"✅ Screenshot guardado: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"❌ Error tomando screenshot: {e}")
            return None

    def _upload_to_drive_with_retries(self, local_path: str, country_name: str) -> Optional[str]:
        for attempt in range(1, DRIVE_UPLOAD_MAX_ATTEMPTS + 1):
            drive_link = self._upload_to_drive(local_path, country_name)
            if drive_link:
                return drive_link

            if attempt < DRIVE_UPLOAD_MAX_ATTEMPTS:
                logger.warning(
                    f"Reintentando subida a Google Drive "
                    f"({attempt + 1}/{DRIVE_UPLOAD_MAX_ATTEMPTS})"
                )
                self._reconnect_drive()
                time.sleep(DRIVE_UPLOAD_RETRY_DELAY_SECONDS)

        return None

    def _reconnect_drive(self) -> None:
        try:
            self._drive_service = None
            self._connect_drive()
        except Exception as e:
            logger.warning(f"No se pudo reconectar Google Drive antes del reintento: {e}")

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
            folder_id = self._get_or_create_folder()

            file_name = os.path.basename(local_path)

            logger.info(f"☁️  Subiendo a Google Drive: {file_name}")

            file_metadata = {
                "name": file_name,
                "parents": [folder_id]
            }

            media = MediaFileUpload(
                local_path,
                mimetype="image/png",
                resumable=False
            )

            uploaded_file = self._drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()

            file_id = uploaded_file["id"]
            logger.info(f"✅ Archivo subido a Drive: ID={file_id}")

            self._make_file_public(file_id)

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
            permission = {
                "type": "anyone",
                "role": "reader",
            }

            self._drive_service.permissions().create(
                fileId=file_id,
                body=permission,
                supportsAllDrives=True,
            ).execute()

            logger.debug(f"✅ Archivo {file_id} configurado como público")

        except Exception as e:
            logger.warning(f"⚠️  No se pudo hacer público el archivo: {e}")
