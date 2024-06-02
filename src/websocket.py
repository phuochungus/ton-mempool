from pytoniq.adnl.overlay import ShardOverlay
from websockets.server import serve, WebSocketServerProtocol
from pytoniq import Address

import functools
import asyncio
import json
import websockets.exceptions


external_src_listeners: dict[bytes, list[WebSocketServerProtocol]] = dict()
external_dest_listeners: dict[bytes, list[WebSocketServerProtocol]] = dict()
external_all_listeners: list[WebSocketServerProtocol] = list()


def remove_ws_client_from_dict(ws_client_id: int, listeners_dict: dict[bytes, list[WebSocketServerProtocol]]) -> None:
    for address, ws_clients in listeners_dict.copy().items():
        for ws_client in ws_clients:
            if id(ws_client) == ws_client_id:
                try:
                    listeners_dict[address].remove(ws_client)
                except (KeyError, ValueError):
                    pass

        if len(ws_clients) == 0:
            try:
                del listeners_dict[address]
            except KeyError:
                pass


async def ws_client_handler(shard_node: ShardOverlay, ws_client: WebSocketServerProtocol) -> None:
    while True:
        try:
            message = await ws_client.recv()

        except websockets.exceptions.ConnectionClosed:
            ws_client_id = id(ws_client)

            remove_ws_client_from_dict(ws_client_id, external_src_listeners)
            remove_ws_client_from_dict(ws_client_id, external_dest_listeners)

            for ws_client in external_all_listeners.copy():
                if id(ws_client) == ws_client_id:
                    try:
                        external_all_listeners.remove(ws_client)
                    except ValueError:
                        pass

            break

        message = json.loads(message)

        if message['type'] == 'subscribe':
            if message['data']['type'] == 'external':
                data_from = message['data']['from']

                if data_from in ['src', 'dest']:
                    address_hash_part = Address(message['data']['address']).hash_part

                    if data_from == 'src':
                        if address_hash_part not in external_src_listeners:
                            external_src_listeners[address_hash_part] = []

                        external_src_listeners[address_hash_part] = ws_client

                    else:
                        if address_hash_part not in external_dest_listeners:
                            external_dest_listeners[address_hash_part] = []

                        external_dest_listeners[address_hash_part].append(ws_client)

                elif data_from == 'all':
                    external_all_listeners.append(ws_client)

                else:
                    pass  # TODO: raise error

                await ws_client.send(json.dumps({
                    'type': 'subscribe',
                    'answer': {
                        'type': 'external',
                        'status': 'ok',
                        'from': data_from,
                        'address': (
                            Address(message['data']['address']).to_str(
                                is_user_friendly = False
                            )
                            if 'address' in message['data']
                            else
                            None
                        )
                    }
                }))

            else:
                pass  # TODO: raise error

        elif message['type'] == 'send_external':
            await shard_node.send_external_message(bytes.fromhex(message['data']))

            await ws_client.send(json.dumps({
                'type': 'send_external',
                'answer': {
                    'status': 'ok'
                }
            }))

        elif message['type'] == 'get_peers_amount':
            await ws_client.send(json.dumps({
                'type': 'get_peers_amount',
                'answer': {
                    'amount': len(shard_node._overlay.peers)
                }
            }))


async def run_websocket(shard_node: ShardOverlay) -> None:
    async with serve(functools.partial(ws_client_handler, shard_node), "0.0.0.0", 8765):
        await asyncio.Future()  # run forever
