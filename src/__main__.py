from pytoniq.adnl import OverlayTransport, DhtClient, AdnlTransport
from pytoniq.adnl.overlay import ShardOverlay, OverlayManager
from pytoniq_core.crypto.ciphers import Client

import asyncio
import logging
import os

from . import liteserver_config
from .websocket import run_websocket
from .processer import process_external_message


logger = logging.getLogger(__name__)

minimum_peer_connections = 10


async def start_up(adnl_transport: AdnlTransport, overlay_transport: OverlayTransport) -> None:
    logger.info('Starting up!')

    logger.info('Starting ADNL transport...')
    await adnl_transport.start()
    logger.info('ADNL transport is launched ...')

    logger.info('Starting Overlay transport...')
    await overlay_transport.start()
    logger.info('Overlay transport is launched ...')

    dht = DhtClient.from_config(liteserver_config, adnl_transport)
    manager = OverlayManager(overlay_transport, dht, max_peers=30)

    await manager.start()

    shard_node = ShardOverlay(manager, external_messages_handler=process_external_message, shard_blocks_handler=lambda i, j: print(i))

    logger.info('Waiting for minimum {} peer connections ...'.format(minimum_peer_connections))
    while len(shard_node._overlay.peers) < minimum_peer_connections:
        await asyncio.sleep(2)

    logger.info('Starting websocket.')
    await run_websocket(shard_node)


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    WORKCHAIN = int(os.getenv('WORKCHAIN', 0))
    NETWORK = os.getenv('NETWORK', 'mainnet')

    if NETWORK == 'mainnet':
        overlay_id = OverlayTransport.get_mainnet_overlay_id(workchain=WORKCHAIN)

    elif NETWORK == 'testnet':
        overlay_id = OverlayTransport.get_testnet_overlay_id(workchain=WORKCHAIN)

    else:
        ZERO_STATE_FILE_HASH = os.getenv('ZERO_STATE_FILE_HASH')

        if ZERO_STATE_FILE_HASH is None:
            raise ValueError('ZERO_STATE_FILE_HASH is not set')

        overlay_id = OverlayTransport.get_overlay_id(ZERO_STATE_FILE_HASH, workchain=WORKCHAIN)

    print('Overlay ID:', overlay_id)

    try:
        with open('key.txt', 'rb') as f:
            key = f.read()

    except FileNotFoundError:
        key = Client.generate_ed25519_private_key()

        with open('key.txt', 'wb') as f:
            f.write(key)

    adnl_transport = AdnlTransport(timeout=5)

    overlay_transport = OverlayTransport(
        private_key = key,
        overlay_id = overlay_id,
        timeout = 10,
        allow_fec = True
    )

    await start_up(adnl_transport, overlay_transport)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
