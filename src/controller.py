#!/usr/bin/env python3
"""Local Sonoff control; account credentials are used once and never saved."""
import argparse
import asyncio
import fcntl
import getpass
import json
import os
from pathlib import Path
import sys

import aiohttp
from zeroconf.asyncio import AsyncZeroconf
from upstream.base import SIGNAL_UPDATE
from upstream.cloud import XRegistryCloud
from upstream.local import XRegistryLocal, decrypt

CONFIG = Path.home() / '.config/sonoff-button/device.json'


async def discover(session, key=None, deviceid=None):
    zc = AsyncZeroconf()
    registry = XRegistryLocal(session)
    found = {}
    ready = asyncio.Event()

    def update(msg):
        if deviceid and msg['deviceid'] != deviceid:
            return
        if key and 'data' in msg:
            msg['params'] = json.loads(decrypt(msg, key))
        found[msg['deviceid']] = msg
        if msg.get('host') and (not key or 'switch' in msg.get('params', {})):
            ready.set()

    registry.dispatcher_connect(SIGNAL_UPDATE, update)
    registry.start(zc.zeroconf)
    try:
        await asyncio.wait_for(ready.wait(), 12)
        if not deviceid:
            await asyncio.sleep(2)
        return found
    finally:
        await registry.stop()
        await zc.async_close()


async def login(args, session):
    devices = await discover(session)
    target = args.device
    if not target:
        if len(devices) != 1:
            raise RuntimeError('Multiple devices discovered; run login --device DEVICE_ID.')
        target = next(iter(devices))
    account = input('eWeLink email or phone: ').strip()
    password = getpass.getpass('eWeLink password (not saved): ')
    country = input('Account country dialling code (for example +1): ').strip()
    cloud = XRegistryCloud(session)
    await cloud.login(account, password, country_code=country)
    del password
    matches = [d for d in await cloud.get_devices() if d['deviceid'] == target]
    if not matches or not matches[0].get('devicekey'):
        raise RuntimeError('The discovered switch/key was not found in this account’s active home.')
    device = matches[0]
    key = device['devicekey']
    # Verify the key against a live encrypted LAN advertisement before saving.
    await discover(session, key, target)
    print('Matched model:', device.get('productModel', 'unknown'))
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = CONFIG.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump({'deviceid': target, 'devicekey': key}, stream)
    os.chmod(temporary, 0o600)
    temporary.replace(CONFIG)
    print('Device key saved privately. Account password and cloud token were not saved.')
    print('LAN authentication verified; the relay has not been switched.')


async def control(args, session):
    if not CONFIG.exists():
        raise RuntimeError('Login required: run sonoff-button login in an interactive terminal.')
    config = json.loads(CONFIG.read_text())
    devices = await discover(session, config['devicekey'], config['deviceid'])
    device = devices[config['deviceid']]
    current = device.get('params', {}).get('switch')
    if current not in ('on', 'off'):
        raise RuntimeError('Could not read current relay state; no command sent.')
    if args.action == 'status':
        print(current)
        return
    wanted = ('off' if current == 'on' else 'on') if args.action == 'toggle' else args.action
    device['devicekey'] = config['devicekey']
    registry = XRegistryLocal(session)
    result = await registry.send(device, {'switch': wanted}, timeout=5, cre_retry_counter=0)
    if result != 'online':
        raise RuntimeError('Switch command was not acknowledged; not retried.')
    print('Command acknowledged:', wanted)
    actual = await discover(session, config['devicekey'], config['deviceid'])
    if actual[config['deviceid']].get('params', {}).get('switch') != wanted:
        raise RuntimeError('Relay state verification failed.')
    print('Verified:', wanted)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['login', 'status', 'on', 'off', 'toggle'])
    parser.add_argument('--device', help='Target device ID when more than one is discovered')
    args = parser.parse_args()
    # Avoid concurrent toggles; never retain a stale local on/off state.
    lockdir = Path.home() / '.cache/sonoff-button'
    lockdir.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (lockdir / 'control.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another Sonoff command is in progress.')
        async with aiohttp.ClientSession(trust_env=False) as session:
            if args.action == 'login':
                await login(args, session)
            else:
                await control(args, session)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        # Avoid printing account responses, keys or authentication tokens.
        if isinstance(exc, RuntimeError):
            print(str(exc), file=sys.stderr)
        else:
            print(f'Operation failed ({type(exc).__name__}); no credentials were logged.', file=sys.stderr)
        sys.exit(1)
