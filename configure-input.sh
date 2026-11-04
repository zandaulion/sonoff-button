#!/bin/sh
# Grant access only to the selected physical input device, not the input group.
set -eu
if [ "$(id -u)" -ne 0 ] || [ -z "${SUDO_USER:-}" ] || [ "$SUDO_USER" = root ]; then
    echo 'Run with sudo from your regular account: sudo ./configure-input.sh /dev/input/by-id/DEVICE mouse|keyboard' >&2
    exit 1
fi
case "$SUDO_USER" in *[!a-zA-Z0-9_-]*) exit 1;; esac
device=${1:-}
kind=${2:-mouse}
case "$device" in /dev/input/by-id/*) ;; *) echo 'Choose a stable /dev/input/by-id/ event device.' >&2; exit 1;; esac
case "$device" in *[!a-zA-Z0-9_./:-]*) echo 'Unsupported characters in device path.' >&2; exit 1;; esac
resolved=$(readlink -f -- "$device")
case "$resolved" in /dev/input/event[0-9]*) ;; *) echo 'Not an evdev input device.' >&2; exit 1;; esac
test -c "$resolved"
case "$kind" in
    mouse) codes='272 273 274 275 276 277 278 279';;
    keyboard) codes='57';;
    *) echo 'Choose mouse or keyboard.' >&2; exit 1;;
esac
name=$(cat "/sys/class/input/$(basename -- "$resolved")/device/name")
case "$name" in *[!a-zA-Z0-9\ ._:/+-]*) echo 'Unsupported characters in hardware name.' >&2; exit 1;; esac
rule=/etc/udev/rules.d/80-sonoff-input.rules
if [ -L "$rule" ]; then echo 'Refusing to overwrite a symlink.' >&2; exit 1; fi
if [ -f "$rule" ] && [ "$(head -n 1 "$rule")" != '# Managed by sonoff-button' ]; then
    echo 'An unrelated input rule exists; leaving it unchanged.' >&2
    exit 1
fi
umask 022
cat > "$rule" <<EOF
# Managed by sonoff-button
SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="$name", RUN+="/usr/bin/setfacl -m u:$SUDO_USER:r /dev/%k"
EOF
udevadm control --reload-rules
setfacl -m "u:$SUDO_USER:r" "$resolved"
target_uid=$(id -u "$SUDO_USER")
target_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
# Write user configuration as that user; do not follow user-controlled paths as root.
runuser -u "$SUDO_USER" -- env HOME="$target_home" sh -c '
    umask 077
    mkdir -p "$HOME/.config/sonoff-button"
    printf "SONOFF_INPUT_DEVICE=%s\nSONOFF_BUTTON_CODES=\"%s\"\n" "$1" "$2" > "$HOME/.config/sonoff-button/input.env"
' sh "$device" "$codes"
runuser -u "$SUDO_USER" -- env HOME="$target_home" XDG_RUNTIME_DIR="/run/user/$target_uid" DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$target_uid/bus" sh -c '
    systemctl --user enable sonoff-input.service
    systemctl --user restart sonoff-input.service
'
echo 'Input control activated. The selected device’s configured buttons now toggle the relay.'
