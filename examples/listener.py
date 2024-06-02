from websockets.client import WebSocketClientProtocol

import json
import hashlib
import time
import websockets
import asyncio
import os
import typing

import process_externals


CACHE_TTL = 60 * 5


class CacheItem:
    def __init__(self, value, ttl: float) -> None:
        self.value = value
        self.expiry_time = time.time() + ttl

    def is_expired(self) -> bool:
        return time.time() > self.expiry_time

    def time_remaining(self) -> float:
        return max(0, self.expiry_time - time.time())


class Cache:
    def __init__(self, ttl: float):
        self._cache: dict[typing.Any, CacheItem] = {}
        self.ttl = ttl

    def set(self, key, value) -> None:
        self._cache[key] = CacheItem(value, self.ttl)

    def get(self, key) -> typing.Any | None:
        item = self._cache.get(key)

        if item and not item.is_expired():
            return item.value

        elif item and item.is_expired():
            del self._cache[key]

        return None

    def clear_expired(self) -> None:
        keys_to_delete = [
            key
            for key, item in self._cache.items()
            if item.is_expired()
        ]

        for key in keys_to_delete:
            try:
                del self._cache[key]
            except KeyError:
                pass

        print(f"Cleared {len(keys_to_delete)} expired items.")


async def clear_cache_periodically(cache: Cache, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)

        cache.clear_expired()


cache = Cache(CACHE_TTL)


async def process_response(query: str | bytes) -> None:
    print('\t', query)

    data = json.loads(query)

    if data['type'] == 'external':
        message_hash = hashlib.sha256(bytes.fromhex(data['data']))

        if cache.get(message_hash):
            return

        cache.set(message_hash, None)

        # add cache check
        process_externals.process_external_deserialize(data['data'])
        # await emulate_external_trace(message['data'])
        # await check_contract_type(message['data'])


async def send_external(websocket: WebSocketClientProtocol) -> None:
    boc_hex = 'b5...'

    await websocket.send(json.dumps({
        'type': 'send_external',
        'data': boc_hex
    }))


async def check_peers_amount(websocket: WebSocketClientProtocol) -> None:
    await websocket.send(json.dumps({
        'type': 'get_peers_amount'
    }))


async def subscribe_to_externals(websocket: WebSocketClientProtocol) -> None:
    # await websocket.send(json.dumps({
    #     'type': 'subscribe',
    #     'data': {
    #         'type': 'external',
    #         'from': 'all'
    #     }
    # }))
    await websocket.send(json.dumps({
        'type': 'subscribe',
        'data': {
            'type': 'external',
            'from': 'dest',
            'address': 'UQCnEmZBPv0yOwrgsp-GekXNEXvkeURM99N7DJh0fzjATwye'
        }
    }))


async def listener() -> None:
    PORT = os.getenv("WS_PORT", 8765)
    HOST = os.getenv("WS_HOST", "localhost")

    uri = "ws://{}:{}".format(HOST, PORT)

    asyncio.create_task(clear_cache_periodically(cache, CACHE_TTL))

    while True:
        async with websockets.connect(uri) as websocket:
            try:
                await check_peers_amount(websocket)

                await subscribe_to_externals(websocket)

                while True:
                    ext = await websocket.recv()
                    await process_response(ext)  # pass your processor here

            except websockets.ConnectionClosed:
                continue


if __name__ == "__main__":
    try:
        asyncio.run(listener())
    except KeyboardInterrupt:
        pass
