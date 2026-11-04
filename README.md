# Sonoff Button

Reuse an old wireless mouse or keyboard as a physical control for a SONOFF BASICR2, without opening the ceiling mount, changing wiring, replacing the relay, or adding a smart-home hub.

The USB receiver connects to an always-on Linux computer on the relay’s local network. Button presses send encrypted LAN commands using the original eWeLink firmware. Any mouse button toggles the relay; keyboard mode uses Space. Movement, scrolling, held-button repeats, and rapid combined clicks are ignored. Commands already in progress are not queued or retried.

## Requirements

- Linux with systemd user services, Python 3.10+, venv, pip, udev, and `setfacl` (usually the `acl` package).
- A compatible eWeLink relay with LAN discovery enabled, reachable from this computer.
- An eWeLink account for one-time retrieval of the device key. Internet is required for installation and initial login; normal switching uses the LAN.
- A spare USB mouse or keyboard, optionally wireless, with an evdev entry under `/dev/input/by-id/`.

## Install and authenticate

Run as your regular user:

```sh
./install.sh
~/.local/bin/sonoff-button login
~/.local/bin/sonoff-button status
```

The login prompts for your account, password, and country dialling code. It verifies the device key against a live encrypted advertisement before saving it. Your password and cloud token are not saved. If multiple devices are discovered, select yours with `sonoff-button login --device DEVICE_ID`.

The installer downloads three client modules from [SonoffLAN](https://github.com/AlexxIT/SonoffLAN), pinned to revision `3f329db36477fcc6ebc148db7b35e1187c20097d`, and retains its MIT license alongside the downloaded files. It does not install Home Assistant.

## Configure the physical control

List the available stable event paths:

```sh
ls -l /dev/input/by-id/
```

Choose your mouse’s `event-mouse` path or keyboard’s `event-kbd` path. Substitute that actual path below; the example device name is synthetic:

```sh
sudo ./configure-input.sh /dev/input/by-id/usb-Example_Mouse-event-mouse mouse
```

For a keyboard, supply its event path and `keyboard` instead. Administrator permission is needed once to grant your user read access to the chosen hardware model’s event device and persist that access after reconnection. The listener runs as your regular user. Its rule matches the device name; identical hardware names will share the permission grant.

The installer writes the selected path and button codes to `~/.config/sonoff-button/input.env`. Mouse mode uses Linux button codes 272–279. Keyboard mode uses code 57 (Space). You can edit that file to narrow the button selection, then restart the service.

```sh
systemctl --user status sonoff-input.service
journalctl --user -u sonoff-input.service -n 20
```

For operation after boot without an interactive login, enable user lingering once:

```sh
sudo loginctl enable-linger "$USER"
```

If migrating from the earlier standalone setup, stop its listeners after activating this service so a click cannot trigger both:

```sh
systemctl --user disable --now sonoff-mouse.service sonoff-keyboard.service
```

## Manual commands

```sh
~/.local/bin/sonoff-button status
~/.local/bin/sonoff-button on
~/.local/bin/sonoff-button off
~/.local/bin/sonoff-button toggle
```

Toggle reads the current relay state from LAN discovery before choosing the opposite state, then checks the resulting state. Discovery and verification can add latency. Concurrent operations and additional clicks during a command are dropped. A timeout can mean the command reached the relay without an acknowledgement; inspect `status` before trying again.

The relay must advertise multicast DNS (`_ewelink._tcp`) and expose its local control port. Wi-Fi isolation or blocked multicast can prevent this. Wireless mouse range depends on the mouse-to-receiver radio link; use a fresh battery and move the receiver clear of the computer with a spare USB extension cable if necessary. Wi-Fi coverage does not extend mouse range.

## Privacy and limitations

The device key lives in `~/.config/sonoff-button/device.json` with mode 0600. Keep that file, your input configuration, credentials, network details, and logs out of version control. This repository contains no deployment configuration or account data. The listener reads input events but stores no typing or pointer history. It does not grab the device exclusively, so clicks or keystrokes can also reach applications using that physical device.

The computer and USB receiver must remain powered and awake. This has been used with a BASICR2 and an ordinary wireless mouse and keyboard; other devices and firmware may behave differently. The upstream client is a community integration and cloud login availability may change.

## Stop and remove

```sh
systemctl --user disable --now sonoff-input.service
rm ~/.config/systemd/user/sonoff-input.service
systemctl --user daemon-reload
sudo rm /etc/udev/rules.d/80-sonoff-input.rules
sudo udevadm control --reload-rules
```

Unplug/replug the receiver to remove the per-device access grant, or revoke it immediately with `sudo setfacl -x "u:$USER" /dev/input/by-id/YOUR_EVENT_DEVICE`. Remove `~/.local/share/sonoff-button`, `~/.local/bin/sonoff-button`, and `~/.config/sonoff-button` if no longer needed. This does not change relay firmware or its eWeLink pairing.

## Checks

```sh
python3 -m unittest discover -s tests -v
sh -n install.sh
sh -n configure-input.sh
```

The tests exercise click filtering and repeat/bounce protection without sending commands to a real relay.

## License

[MIT](LICENSE). The downloaded SonoffLAN client modules retain their upstream MIT license and attribution.
