#!/usr/bin/env bash

set -u

PROJECT="$HOME/projects/albion_yandex_maps_presentation_demo"
PORT="48309"

KEYS=(
    "d69ffe17-b984-45d3-b435-f06bdb8853f6"
    "892d3b65-eb5c-4c57-92d8-666266f880fa"
    "440cc39f-a2e1-4562-8c52-6d1c406ca018"
)

cd "$PROJECT" || exit 1

echo
echo "=============================================="
echo " ALBION — YANDEX MAPS API TEST"
echo "=============================================="
echo

if [ ! -f "index.html" ]; then
    echo "ОШИБКА: index.html не найден"
    exit 1
fi

# ------------------------------------------------
# РЕЗЕРВНАЯ КОПИЯ
# ------------------------------------------------

BACKUP="index.html.before-yandex-test.$(date +%Y%m%d_%H%M%S)"

cp index.html "$BACKUP"

echo "Создана резервная копия:"
echo "$BACKUP"
echo

WORKING_KEY=""

# ------------------------------------------------
# ПРОВЕРКА ВСЕХ КЛЮЧЕЙ
# ------------------------------------------------

for KEY in "${KEYS[@]}"; do

    echo "----------------------------------------------"
    echo "Проверка ключа: ${KEY:0:8}..."
    echo "----------------------------------------------"

    URL="https://api-maps.yandex.ru/v3/?apikey=$KEY&lang=ru_RU"

    RESPONSE_FILE="/tmp/yandex_response_$$.txt"
    HEADERS_FILE="/tmp/yandex_headers_$$.txt"

    HTTP_CODE=$(curl \
        --silent \
        --show-error \
        --location \
        --max-time 20 \
        --dump-header "$HEADERS_FILE" \
        --output "$RESPONSE_FILE" \
        --write-out "%{http_code}" \
        "$URL")

    CONTENT_TYPE=$(grep -i "^content-type:" "$HEADERS_FILE" \
        | tail -1 \
        | tr -d '\r')

    echo "HTTP статус: $HTTP_CODE"
    echo "$CONTENT_TYPE"

    echo "Начало ответа:"
    head -c 250 "$RESPONSE_FILE"
    echo
    echo

    # Рабочим считаем HTTP 200
    if [ "$HTTP_CODE" = "200" ]; then

        echo ">>> НАЙДЕН РАБОЧИЙ КЛЮЧ <<<"

        WORKING_KEY="$KEY"

        break

    fi

    sleep 2

done

# ------------------------------------------------
# ЕСЛИ РАБОЧИЙ КЛЮЧ НАЙДЕН
# ------------------------------------------------

if [ -n "$WORKING_KEY" ]; then

    echo
    echo "=============================================="
    echo "РАБОЧИЙ КЛЮЧ НАЙДЕН"
    echo "=============================================="
    echo

    echo "Подстановка ключа в index.html..."

    python3 - "$WORKING_KEY" <<'PY'
import re
import sys
from pathlib import Path

key = sys.argv[1]

path = Path("index.html")
text = path.read_text(encoding="utf-8")

pattern = r'(https://api-maps\.yandex\.ru/v3/\?apikey=)[^&"\']+'

new_text, count = re.subn(
    pattern,
    r'\g<1>' + key,
    text
)

if count == 0:
    print("ОШИБКА: URL Yandex Maps API не найден в index.html")
    sys.exit(1)

path.write_text(new_text, encoding="utf-8")

print("Ключ успешно заменён.")
PY

else

    echo
    echo "=============================================="
    echo "РАБОЧИЙ КЛЮЧ С HTTP 200 НЕ НАЙДЕН"
    echo "=============================================="
    echo
    echo "index.html НЕ изменён."
    echo "Проверьте результаты выше."
    echo

fi

# ------------------------------------------------
# ПРОВЕРКА ПОРТА
# ------------------------------------------------

echo
echo "Проверка порта $PORT..."

if ss -ltn | grep -q ":$PORT "; then

    echo
    echo "Порт $PORT уже занят."

    echo
    echo "Процесс:"
    sudo lsof -i :"$PORT"

    echo
    echo "Останавливаю процесс на порту $PORT..."

    sudo fuser -k "$PORT/tcp"

    sleep 2

fi

# ------------------------------------------------
# ЗАПУСК HTTP СЕРВЕРА
# ------------------------------------------------

echo
echo "=============================================="
echo "ЗАПУСК HTTP СЕРВЕРА"
echo "=============================================="
echo

echo "Адрес:"
echo
echo "http://localhost:$PORT/?v=$(date +%s)"
echo

echo "Для остановки нажмите Ctrl+C"
echo

python3 -m http.server "$PORT" --bind 127.0.0.1
