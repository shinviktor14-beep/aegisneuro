# Сборка AegisNeuro под Android

Этот документ — короткая инструкция, как получить **APK**, который устанавливается на телефон и запускается как обычное приложение.

## Что внутри

- `main.py` — мобильный UI на KivyMD (камера, PPG, Q-learning, бинауральный звук)
- `buildozer.spec` — конфиг сборки под arm64-v8a, Android 7.0+ (API 24)
- `.github/workflows/android.yml` — CI, который собирает APK при каждом push

## Шаг 1. Залить репозиторий на GitHub

Если ещё не залит:

```bash
cd D:\AegisNeuro
git init
git add .
git commit -m "Initial: AegisNeuro mobile build"
git branch -M main
git remote add origin https://github.com/<ваш-юзер>/<ваш-репо>.git
git push -u origin main
```

> В репозиторий **не нужно** коммитить файлы, которые генерируются сборкой:
> `aegis_user_brain_profile.json`, `aegis_historical_baseline.json`, `__pycache__/`,
> `.buildozer/`, `bin/`. Если в репо их нет — добавьте `.gitignore` (в файле `BUILD_ANDROID.md` есть образец ниже).

## Шаг 2. Дождаться сборки

1. Откройте репозиторий на GitHub → вкладка **Actions**.
2. Сверху должен быть запущен workflow **Build AegisNeuro Android APK**.
3. Первая сборка занимает **30–60 минут** (скачивает Android SDK/NDK ~1.5 ГБ, потом собирает).
4. Дождитесь зелёной галки ✓.

## Шаг 3. Скачать APK

1. Кликните на завершённый run → прокрутите вниз → **Artifacts**.
2. Скачайте **`aegisneuro-arm64-debug`**.
3. Распакуйте zip — внутри `bin/AegisNeuro-1.0.0-arm64-v8a-debug.apk`.

## Шаг 4. Установить на телефон

### Вариант A. Через USB-кабель (нужен `adb`)

```bash
# Установите platform-tools и подключите телефон с включённой отладкой
adb install bin/AegisNeuro-1.0.0-arm64-v8a-debug.apk
adb logcat | grep -i Aegis  # смотреть логи
```

### Вариант B. Скинуть APK и установить вручную

1. Перекиньте `AegisNeuro-1.0.0-arm64-v8a-debug.apk` на телефон (Telegram, Google Drive, по кабелю — неважно).
2. На телефоне откройте APK файловым менеджером.
3. Система попросит **«Разрешить установку из этого источника»** — разрешите.
4. Нажмите **«Установить»**.
5. Запустите **AegisNeuro** из лаунчера.

## Шаг 5. Пользоваться

1. При первом запуске приложение запросит **доступ к камере** — разрешите.
2. Включите фонарик (зажмите кнопку **«ЗАПУСТИТЬ НАСТОЯЩИЙ PPG ЗАМЕР»**), приложите палец к камере, держите 15 секунд.
3. На экране появится `Индекс стресса`, `RMSSD`, статус шторма и частота бинаурального стимула, который ИИ начинает играть в наушниках.
4. **Наушники обязательны** — иначе мозг не слышит разницу между каналами и бинауральных биений не возникает.

## Частые проблемы

| Проблема | Решение |
|---|---|
| `Buildozer: command not found` в CI | Не страшно, pipeline ставит его сам |
| Workflow упал на `license not accepted` | Запушьте любой коммит повторно; buildozer примет лицензии автоматически |
| APK собрался, но при запуске сразу крашится | Подключите телефон по USB, выполните `adb logcat \| grep -i "python\|aegis"`, ищите `ImportError` |
| `ImportError: No module named 'aegis_audio_engine'` | Убедитесь, что в репо залиты файлы `aegis_audio_engine.py`, `aegis_ppg_processor.py` |
| На телефоне чёрный экран камеры | Снимите защитную плёнку/стекло с объектива, дайте разрешение CAMERA повторно (Настройки → Приложения → AegisNeuro → Разрешения) |
| Не слышно звука | Вставьте наушники. Без них разница между левым и правым ухом не доходит до мозга |

## Образец `.gitignore`

```gitignore
# Runtime data
aegis_user_brain_profile.json
aegis_historical_baseline.json
data/*.json
!data/.gitkeep

# Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Buildozer
.buildozer/
bin/

# IDE
.vscode/
.idea/
*.swp
.DS_Store
```

## Локальная сборка (опционально)

На Windows собрать нельзя — нужен Linux. Самый быстрый путь — Docker:

```bash
docker run --rm -v $(pwd):/src kivy/buildozer:latest buildozer android debug
```

Или поднять ваш WSL2 Ubuntu:

```bash
wsl -d Ubuntu
sudo apt update
sudo apt install -y python3-pip cython openjdk-17-jdk autoconf libtool zlib1g-dev libncurses5-dev cmake libffi-dev libssl-dev
pip3 install --user buildozer cython==0.29.33
buildozer android debug
```

## Проверка перед push (на Windows-десктопе)

Чтобы не тратить CI-минуты на заведомо битый код, можно гонять UI локально:

```bash
pip install -r requirements-dev.txt
python main.py
```

На десктопе камера и фонарик работают в fallback-режиме (без вспышки, через вебку ноута), но UI полностью поднимается, и вы видите, что интерфейс не разломан.
