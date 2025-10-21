import asyncio
import logging

from heos_scrobbler.heos import initialize_heos_scrobbling

logging.basicConfig(
    format="%(asctime)s|%(levelname)s|%(name)s|%(module)s.%(funcName)s: %(message)s", level=logging.INFO
)


async def main():
    await initialize_heos_scrobbling()

    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
