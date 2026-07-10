import random
import asyncio


# Espera aleatoria entre acciones para simular tics humanos y evitar deteccion de Cloudflare.
async def human_delay(min_ms: int = 500, max_ms: int = 1500) -> None:
    delay_ms = random.randint(min_ms, max_ms)
    await asyncio.sleep(delay_ms / 1000)
