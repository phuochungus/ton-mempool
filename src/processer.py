from pytoniq import LiteBalancer, Slice
from pytoniq_core.tlb import MessageAny

import websockets
import hashlib
import time
import json
import typing

from . import liteserver_config
from .websocket import external_src_listeners, external_dest_listeners, external_all_listeners, WebSocketServerProtocol


messages_cache: dict[typing.Any, float] = dict()
client = LiteBalancer.from_config(liteserver_config, trust_level=2)
externals_counter = int()
externals_cache_delay = 60


async def broadcast_ws_clients(external_boc: str, ws_clients: list[WebSocketServerProtocol]) -> None:
    for ws_client in ws_clients:
        try:
            await ws_client.send(json.dumps({
                'type': 'external',
                'data': external_boc
            }))

        except websockets.ConnectionClosed:
            pass


async def broadcast_ws_clients_from_dict(external_boc: str, address_hash_part: bytes, listeners_dict: dict[bytes, list[WebSocketServerProtocol]]):
    await broadcast_ws_clients(external_boc, listeners_dict.get(address_hash_part, []))


async def broadcast(message: bytes) -> None:
    message_obj = MessageAny.deserialize(Slice.one_from_boc(message))

    external_boc: str = message.hex()

    if message_obj.info.src:
        await broadcast_ws_clients_from_dict(external_boc, message_obj.info.src.hash_part, external_src_listeners)
    elif message_obj.info.dest:
        await broadcast_ws_clients_from_dict(external_boc, message_obj.info.dest.hash_part, external_dest_listeners)

    await broadcast_ws_clients(external_boc, external_all_listeners)


async def process_external_message(data: dict, *args, **kwargs) -> None:
    global externals_counter
    externals_counter += 1

    if not externals_counter % 500:
        print(f'Got {externals_counter} messages')

    external_hash = hashlib.sha256(data['message']['data'])

    # if external_hash in messages_cache:
    #     return

    await broadcast(data['message']['data'])

    messages_cache[external_hash] = time.time()

    # NOTE: clearing cache
    for message_hash, timestamp in list(messages_cache.items()):
        if timestamp + externals_cache_delay < time.time():
            messages_cache.pop(message_hash)

    return data
