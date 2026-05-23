#!/usr/bin/env bash
# Lê a URL atual do túnel Cloudflare, gera QR code e abre janela com QR + URL.
# Atalho de desktop pra acessar o dashboard pelo celular sem digitar nada.

set -e

URL=$(journalctl --user -u garmin-relatorio-tunnel --no-pager 2>/dev/null \
      | grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" \
      | tail -1)

if [ -z "$URL" ]; then
    zenity --error \
        --title="Garmin Dashboard" \
        --text="Tunnel ainda nao subiu ou logs vazios.\n\nVerifica com:\nsystemctl --user status garmin-relatorio-tunnel"
    exit 1
fi

# Verifica se o tunnel esta de fato ativo
if ! systemctl --user is-active --quiet garmin-relatorio-tunnel.service; then
    zenity --warning \
        --title="Garmin Dashboard" \
        --text="O tunnel nao esta rodando.\n\nIniciar com:\nsystemctl --user start garmin-relatorio-tunnel"
fi

QR_PNG=$(mktemp --suffix=.png /tmp/garmin-qr-XXXXXX)

# Gera QR usando Python embutido do projeto (uv com qrcode lib)
cd "$(dirname "$0")/../backend"
uv run --quiet --with "qrcode[pil]" python -c "
import qrcode, sys
img = qrcode.make(sys.argv[1])
img.save(sys.argv[2])
" "$URL" "$QR_PNG"

# Abre janela com o QR code + URL no texto
zenity --info \
    --title="Garmin Dashboard — escaneie com o celular" \
    --width=480 \
    --no-wrap \
    --icon="$QR_PNG" \
    --text="<b>URL atual:</b>\n<tt>$URL</tt>\n\n<b>Usuario:</b> micaela\n\nEscaneia o QR code (camera do celular) ou copia a URL acima.\n\n<i>A URL muda toda vez que o PC reinicia.</i>" 2>/dev/null &

# Tambem abre a imagem do QR num viewer pra escanear sem dificuldade
xdg-open "$QR_PNG" 2>/dev/null &

# Limpa o PNG depois de 60s (tempo de escanear)
( sleep 60 && rm -f "$QR_PNG" ) &

exit 0
