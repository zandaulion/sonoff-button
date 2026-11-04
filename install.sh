#!/bin/sh
set -eu
if [ "$(id -u)" -eq 0 ]; then
    echo 'Run install.sh as your regular user, without sudo.' >&2
    exit 1
fi
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
install_dir="$HOME/.local/share/sonoff-button"
mkdir -p "$install_dir" "$HOME/.local/bin" "$HOME/.config/systemd/user"
chmod 700 "$install_dir"
cp "$source_dir/src/controller.py" "$source_dir/src/listener.py" "$install_dir/"
python3 -m venv "$install_dir/venv"
"$install_dir/venv/bin/python" -m pip install -r "$source_dir/requirements.txt"
"$install_dir/venv/bin/python" - "$install_dir" <<'PY'
import pathlib
import sys
import urllib.request

root = pathlib.Path(sys.argv[1]) / 'upstream'
root.mkdir(exist_ok=True)
revision = '3f329db36477fcc6ebc148db7b35e1187c20097d'
base = f'https://raw.githubusercontent.com/AlexxIT/SonoffLAN/{revision}'
for name in ('base.py', 'cloud.py', 'local.py'):
    data = urllib.request.urlopen(f'{base}/custom_components/sonoff/core/ewelink/{name}', timeout=30).read()
    (root / name).write_bytes(data)
(root / '__init__.py').touch()
(root / 'LICENSE.md').write_bytes(urllib.request.urlopen(f'{base}/LICENSE.md', timeout=30).read())
(root / 'SOURCE.txt').write_text(f'https://github.com/AlexxIT/SonoffLAN\nRevision: {revision}\n')
PY
cat > "$HOME/.local/bin/sonoff-button" <<'SH'
#!/bin/sh
exec "$HOME/.local/share/sonoff-button/venv/bin/python" "$HOME/.local/share/sonoff-button/controller.py" "$@"
SH
chmod 700 "$HOME/.local/bin/sonoff-button"
cp "$source_dir/systemd/sonoff-input.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
echo 'Installed. Run ~/.local/bin/sonoff-button login, then follow README.md to configure your input device.'
