#!/usr/bin/env python3
"""Toggle Sonoff with any mouse button on a dedicated input device."""
import errno
import os
from pathlib import Path
import select
import struct
import subprocess
import threading
import time

DEVICE = os.environ.get('SONOFF_INPUT_DEVICE', '')
EVENT = struct.Struct('@llHHi')
BUTTON_CODES = frozenset(int(code) for code in os.environ.get('SONOFF_BUTTON_CODES', '272 273 274 275 276 277 278 279').split())


class PressGate:
    def __init__(self):
        self.pressed = set()
        self.last_press = float('-inf')

    def accept(self, kind, code, value, now):
        if kind != 1 or code not in BUTTON_CODES:
            return False
        if value == 0:
            self.pressed.discard(code)
            return False
        if value != 1 or code in self.pressed:
            return False
        self.pressed.add(code)
        if now - self.last_press < 0.6:
            return False
        self.last_press = now
        return True


busy = threading.Lock()


def toggle():
    try:
        result = subprocess.run(
            [str(Path.home() / '.local/bin/sonoff-button'), 'toggle'],
            capture_output=True, timeout=40, text=True,
        )
        if result.returncode:
            print('Toggle failed; not retried. Check sonoff-button status.', flush=True)
        else:
            print('Toggle verified.', flush=True)
    except subprocess.TimeoutExpired:
        print('Toggle timed out; not retried.', flush=True)
    finally:
        busy.release()


def listen():
    if not DEVICE.startswith('/dev/input/') or not BUTTON_CODES:
        raise RuntimeError('Configure SONOFF_INPUT_DEVICE and SONOFF_BUTTON_CODES first.')
    print('Listening for configured buttons on the dedicated input device.', flush=True)
    while True:
        try:
            fd = os.open(DEVICE, os.O_RDONLY | os.O_NONBLOCK)
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.EACCES, errno.ENODEV):
                raise
            time.sleep(2)
            continue
        gate = PressGate()
        try:
            while True:
                if not select.select([fd], [], [], 2)[0]:
                    continue
                data = os.read(fd, EVENT.size * 64)
                if not data:
                    break
                for _, _, kind, code, value in EVENT.iter_unpack(data):
                    # SYN_DROPPED means event history is incomplete; wait for
                    # a release before accepting another button press.
                    if kind == 0 and code == 3:
                        gate.pressed.update(BUTTON_CODES)
                    elif gate.accept(kind, code, value, time.monotonic()):
                        if busy.acquire(blocking=False):
                            threading.Thread(target=toggle, daemon=True).start()
        except OSError as exc:
            if exc.errno not in (errno.ENODEV, errno.EIO):
                raise
        finally:
            os.close(fd)
        time.sleep(1)


if __name__ == '__main__':
    listen()
