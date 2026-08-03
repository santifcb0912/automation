import asyncio
import io
import time
from datetime import datetime
from typing import Optional

from playwright.async_api import Page
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from loguru import logger

from config.settings import settings
from config.google_auth import get_google_credentials

DRIVE_UPLOAD_MAX_ATTEMPTS = 3
DRIVE_UPLOAD_RETRY_DELAY_SECONDS = 3


class ScreenshotManager:

    # Conecta con Google Drive usando Service Account u OAuth. Propaga excepcion si falla
    def __init__(self):
        self._drive_service = None
        self._connect_drive()
        logger.debug("ScreenshotManager inicializado")

    # Conecta con Google Drive usando Service Account u OAuth. Propaga excepcion si falla
    def _connect_drive(self) -> None:
        try:
            logger.info("Conectando con Google Drive...")
            credentials = get_google_credentials()
            self._drive_service = build("drive", "v3", credentials=credentials)
            logger.info("Conexion con Google Drive establecida")
        except FileNotFoundError:
            logger.error(f"Archivo de credenciales no encontrado: {settings.google_credentials_path}")
            raise
        except Exception as e:
            logger.error(f"Error conectando con Google Drive: {e}")
            raise

    # Reinicia el servicio de Drive y reconecta. Errores solo se loguean
    def _reconnect_drive(self) -> None:
        try:
            self._drive_service = None
            self._connect_drive()
        except Exception as e:
            logger.warning(f"No se pudo reconectar Google Drive: {e}")

    # Toma screenshot en RAM, sube a Drive raiz (sin carpeta) y retorna link publico o None
    async def take_and_upload(self, page: Page, country_name: str, test_email: str) -> Optional[str]:
        try:
            result = await self._take_screenshot(page, country_name, test_email)
            if not result:
                return None
            img_bytes, filename = result
            return self._upload_to_drive_with_retries(img_bytes, filename)
        except Exception as e:
            logger.error(f"Error en take_and_upload: {e}")
            return None

    # Captura screenshot en RAM (sin disco). Retorna (bytes, filename) o None
    async def _take_screenshot(self, page: Page, country_name: str, test_email: str) -> Optional[tuple[bytes, str]]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        email_clean = test_email.replace("@", "_").replace(".", "_")
        filename = f"captura_{country_name}_{email_clean}_{timestamp}.png"

        for attempt in range(1, 3):
            try:
                img_bytes = await asyncio.wait_for(
                    page.screenshot(type="png", timeout=15000, animations="disabled"),
                    timeout=20,
                )
                logger.info(f"Screenshot tomado: {filename}")
                return img_bytes, filename
            except asyncio.TimeoutError:
                logger.error(f"Timeout capturando screenshot (intento {attempt}/2) | url: {page.url}")
                if attempt == 1:
                    await asyncio.sleep(1)
                    continue
                return None
            except Exception as e:
                logger.error(f"Error tomando screenshot: {e}")
                return None

    # Reintenta subida a Drive hasta N veces con reconexion entre intentos. Retorna link o None
    def _upload_to_drive_with_retries(self, img_bytes: bytes, file_name: str) -> Optional[str]:
        for attempt in range(1, DRIVE_UPLOAD_MAX_ATTEMPTS + 1):
            drive_link = self._upload_to_drive(img_bytes, file_name)
            if drive_link:
                return drive_link
            if attempt < DRIVE_UPLOAD_MAX_ATTEMPTS:
                logger.warning(f"Reintentando subida a Drive ({attempt + 1}/{DRIVE_UPLOAD_MAX_ATTEMPTS})")
                self._reconnect_drive()
                time.sleep(DRIVE_UPLOAD_RETRY_DELAY_SECONDS)
        return None

    # Sube bytes a la raiz de Drive (sin carpeta), hace publico el archivo y retorna link
    def _upload_to_drive(self, img_bytes: bytes, file_name: str) -> Optional[str]:
        try:
            media = MediaIoBaseUpload(io.BytesIO(img_bytes), mimetype="image/png", resumable=False)
            uploaded_file = self._drive_service.files().create(
                body={"name": file_name}, media_body=media, fields="id", supportsAllDrives=True,
            ).execute()
            file_id = uploaded_file["id"]
            logger.info(f"Archivo subido a Drive: ID={file_id}")
            self._make_file_public(file_id)
            public_link = f"https://drive.google.com/file/d/{file_id}/view"
            logger.success(f"Link de captura: {public_link}")
            return public_link
        except Exception as e:
            logger.error(f"Error subiendo a Google Drive: {e}")
            return None

    # Otorga permiso publico al archivo subido (anyone con link puede verlo)
    def _make_file_public(self, file_id: str) -> None:
        try:
            permission = {"type": "anyone", "role": "reader"}
            self._drive_service.permissions().create(
                fileId=file_id, body=permission, supportsAllDrives=True,
            ).execute()
            logger.debug(f"Archivo {file_id} configurado como publico")
        except Exception as e:
            logger.warning(f"No se pudo hacer publico el archivo: {e}")
