#!/bin/bash

echo "=========================================="
echo "Starting Worldbuilder Wiki..."
echo "=========================================="

# Проверка наличия Node.js
if ! command -v node &> /dev/null
then
    echo "[ОШИБКА] Node.js не установлен!"
    echo "Пожалуйста, скачайте и установите версию 22.x с сайта https://nodejs.org/"
    exit 1
fi

# Проверка минимальной версии Node.js (>= 20.12.0)
NODE_VERSION=$(node -v | sed 's/v//')
IFS='.' read -r -a VERSION_PARTS <<< "$NODE_VERSION"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}

if [ "$MAJOR" -lt 20 ] || ( [ "$MAJOR" -eq 20 ] && [ "$MINOR" -lt 12 ] ); then
    echo "[ОШИБКА] Требуется Node.js версии 20.12.0 или выше (рекомендуется 22.x)."
    echo "У вас установлена версия: v$NODE_VERSION"
    echo "Пожалуйста, обновите Node.js: https://nodejs.org/"
    exit 1
fi

echo "[OK] Node.js v$NODE_VERSION найден."

# Установка зависимостей
if [ ! -d "node_modules" ]; then
    echo "Установка зависимостей (это может занять пару минут при первом запуске)..."
    npm install
else
    echo "Проверка зависимостей..."
    npm install > /dev/null 2>&1
fi

# Запуск сервера
echo ""
echo "=========================================="
echo "Сервер запускается..."
echo "Браузер откроется автоматически через несколько секунд."
echo "Если этого не произошло, откройте вручную: http://localhost:3000"
echo "=========================================="

# Функция для открытия браузера с задержкой
(sleep 3 && {
    if command -v xdg-open > /dev/null; then
        xdg-open http://localhost:3000
    elif command -v open > /dev/null; then
        open http://localhost:3000
    elif command -v start > /dev/null; then
        start http://localhost:3000
    fi
}) &

npm run dev
