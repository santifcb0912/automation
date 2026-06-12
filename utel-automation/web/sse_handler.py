"""Server-Sent Events handler — comunicación en tiempo real con el browser.

HTMX en el frontend escucha este endpoint con hx-sse.
"""

import json
import asyncio
from fastapi import Request
from fastapi.responses import StreamingResponse
from loguru import logger

from core.interfaces.i_event_publisher import IEventPublisher


async def event_generator(request: Request, event_queue: IEventPublisher):
    async for event in event_queue.consume():
        if await request.is_disconnected():
            logger.info("Cliente SSE desconectado")
            break
        yield event


def stream_response(request: Request, event_queue: IEventPublisher) -> StreamingResponse:
    return StreamingResponse(
        event_generator(request, event_queue),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
