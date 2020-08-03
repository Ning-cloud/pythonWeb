import logging
logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

async def init(loop):
    pass

loop=asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()

