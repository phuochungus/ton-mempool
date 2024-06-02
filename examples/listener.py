from websockets.client import WebSocketClientProtocol

import websockets
import asyncio
import json
import os

import process_externals


async def process(query: bytes) -> None:
    print('\t', query)

    message = json.loads(query)

    if message['type'] == 'external':
        # do something with message['data']
        process_externals.process_external_deserialize(message['data'])
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

    while True:
        async with websockets.connect(uri) as websocket:
            try:
                await check_peers_amount(websocket)

                await subscribe_to_externals(websocket)

                while True:
                    ext = await websocket.recv()
                    await process(ext)  # pass your processor here

            except websockets.ConnectionClosed:
                continue


if __name__ == "__main__":
    try:
        asyncio.run(listener())
    except KeyboardInterrupt:
        pass
