from typing import Protocol


class IScreenshotService(Protocol):
    async def take_screenshot(self, page, lead_id: str, label: str) -> str:
        ...

    async def upload_to_drive(self, file_path: str, folder_name: str = "screenshots") -> str:
        ...
