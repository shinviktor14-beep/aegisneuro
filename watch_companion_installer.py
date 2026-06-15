# Имя файла: watch_companion_installer.py
"""
Модуль автоматической установки AegisNeuro Watch Companion на Wear OS часы
через ADB (wireless debugging).

Поток:
  1. Обнаружены часы без companion → показать инструкцию включить
     Developer Options + ADB debugging + Wireless debugging.
  2. Пользователь вводит IP:port часов (или пытаемся обнаружить).
  3. adb connect <ip>:<port>
  4. adb install <watch_apk>  (APK из assets)
  5. adb shell am start <package>/<activity>  — запуск companion.
  6. Все строки на русском.
"""

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

from kivy.clock import Clock
from kivy.utils import platform

log = logging.getLogger("aegis.watch_installer")

WATCH_APK_NAME = "aegisneuro-watch-1.0.69-debug.apk"
WATCH_PACKAGE = "org.aegisneuro.watchcompanion"
WATCH_LAUNCH_ACTIVITY = "org.aegisneuro.watchcompanion.MainActivity"

# ──────────────────────────────────────────────────
# Русскоязычные строки (все пользовательские тексты)
# ──────────────────────────────────────────────────
RU = {
    "title": "Установка companion на часы",
    "step1_title": "Шаг 1: Включите режим разработчика",
    "step1_detail": (
        "На часах: Настройки → О часах → нажмите 7 раз\n"
        "на «Номер сборки»."
    ),
    "step2_title": "Шаг 2: Включите отладку ADB",
    "step1b_detail": (
        "На часах: Настройки → Для разработчиков →\n"
        "включите «Отладка по ADB»."
    ),
    "step3_title": "Шаг 3: Включите беспроводную отладку",
    "step3_detail": (
        "На часах: Настройки → Для разработчиков →\n"
        "включите «Беспроводная отладка».\n"
        "Запомните IP-адрес и порт\n"
        "(например 192.168.1.50:5555)."
    ),
    "ip_prompt": "IP-адрес и порт часов",
    "ip_placeholder": "192.168.1.50:5555",
    "btn_connect": "Подключиться",
    "btn_install": "Установить companion",
    "btn_start": "Запустить companion",
    "btn_close": "Закрыть",
    "status_connecting": "Подключение к часам…",
    "status_connected": "Подключено к часам",
    "status_connect_failed": "Не удалось подключиться",
    "status_installing": "Установка companion…",
    "status_installed": "Companion установлен!",
    "status_install_failed": "Ошибка установки",
    "status_starting": "Запуск companion на часах…",
    "status_started": "Companion запущен!",
    "status_start_failed": "Не удалось запустить companion",
    "status_extracting_apk": "Подготовка APK…",
    "error_no_adb": "ADB недоступен на устройстве",
    "error_apk_missing": "APK companion не найден",
}


class WatchCompanionInstaller:
    """Установщик companion-приложения на Wear OS часы через ADB."""

    def __init__(self):
        self._adb_path = None
        self._watch_apk_path = None
        self._connected = False
        self._installed = False
        self._started = False
        self._target = None  # ip:port

    # ── Определение пути ADB ──

    def _find_adb(self):
        """Ищет adb: сначала bundled binary, потом system, потом Android Runtime.exec()."""
        if platform == "android":
            try:
                from jnius import autoclass
                Runtime = autoclass("java.lang.Runtime")
                self._runtime = Runtime.getRuntime()
                self._adb_path = "runtime"  # флаг: используем Runtime.exec()
                log.info("ADB: будет использован через Runtime.exec()")
                return True
            except Exception as exc:
                log.error("ADB: Runtime недоступен: %s", exc)

        # Попытка найти adb в PATH (на десктопе для отладки)
        import shutil
        adb = shutil.which("adb")
        if adb:
            self._adb_path = adb
            log.info("ADB: найден в PATH: %s", adb)
            return True

        log.error("ADB: не найден")
        return False

    def _run_adb(self, *args, timeout=30):
        """Выполняет команду adb. Возвращает (returncode, stdout, stderr)."""
        if self._adb_path == "runtime":
            cmd_str = " ".join(["adb"] + list(args))
            try:
                proc = self._runtime.exec(cmd_str)
                stdout = proc.getInputStream()
                stderr = proc.getErrorStream()
                # Читаем stdout
                out_bytes = bytearray()
                while True:
                    b = stdout.read()
                    if b == -1:
                        break
                    out_bytes.append(b)
                err_bytes = bytearray()
                while True:
                    b = stderr.read()
                    if b == -1:
                        break
                    err_bytes.append(b)
                rc = proc.waitFor()
                return (rc, out_bytes.decode("utf-8", errors="replace"),
                        err_bytes.decode("utf-8", errors="replace"))
            except Exception as exc:
                log.error("ADB Runtime.exec ошибка: %s", exc)
                return (-1, "", str(exc))
        else:
            cmd = [self._adb_path] + list(args)
            try:
                result = subprocess.run(
                    cmd, capture_output=True, timeout=timeout, text=True
                )
                return (result.returncode, result.stdout, result.stderr)
            except Exception as exc:
                log.error("ADB subprocess ошибка: %s", exc)
                return (-1, "", str(exc))

    # ── Извлечение APK из assets ──

    def extract_watch_apk(self):
        """Копирует watch APK из assets во внутреннее хранилище приложения."""
        if platform != "android":
            # На десктопе — ищем в assets/ рядом с main.py
            local = Path(__file__).parent / "assets" / WATCH_APK_NAME
            if local.exists():
                self._watch_apk_path = str(local)
                log.info("Watch APK (desktop): %s", self._watch_apk_path)
                return True
            log.error("Watch APK не найден: %s", local)
            return False

        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            context = activity.getApplicationContext()

            # Целевой каталог
            files_dir = context.getFilesDir().getAbsolutePath()
            dest = os.path.join(files_dir, WATCH_APK_NAME)

            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                self._watch_apk_path = dest
                log.info("Watch APK уже извлечён: %s", dest)
                return True

            # Читаем из assets
            asset_mgr = context.getAssets()
            input_stream = asset_mgr.open(WATCH_APK_NAME)
            out_stream = autoclass("java.io.FileOutputStream")(dest)

            buf = autoclass("java.io.ByteArrayOutputStream")()
            buffer = bytearray(8192)
            while True:
                read = input_stream.read(buffer)
                if read == -1:
                    break
                out_stream.write(buffer, 0, read)

            out_stream.flush()
            out_stream.close()
            input_stream.close()

            # Даем разрешения на чтение
            autoclass("java.io.File")(dest).setReadable(True, False)

            self._watch_apk_path = dest
            log.info("Watch APK извлечён: %s", dest)
            return True

        except Exception as exc:
            log.error("Не удалось извлечь watch APK: %s", exc)
            return False

    # ── ADB-операции ──

    def adb_connect(self, ip_port):
        """Подключается к часам через adb connect."""
        self._target = ip_port
        rc, out, err = self._run_adb("connect", ip_port, timeout=15)
        log.info("adb connect %s → rc=%d out=%s err=%s", ip_port, rc, out.strip(), err.strip())
        # adb connect возвращает 0 даже если не подключилось, проверяем вывод
        if "connected" in out.lower() or "already connected" in out.lower():
            self._connected = True
            return True
        if "refused" in out.lower() or "cannot" in out.lower() or "failed" in out.lower():
            self._connected = False
            return False
        # Если rc==0 — считаем успехом
        self._connected = (rc == 0)
        return self._connected

    def adb_install(self):
        """Устанавливает watch APK на часы."""
        if not self._connected or not self._watch_apk_path:
            return False
        rc, out, err = self._run_adb(
            "-s", self._target, "install", "-r", "-g", self._watch_apk_path,
            timeout=120,
        )
        log.info("adb install → rc=%d out=%s err=%s", rc, out.strip(), err.strip())
        if rc == 0 and ("success" in out.lower() or rc == 0):
            self._installed = True
            return True
        self._installed = False
        return False

    def adb_start_companion(self):
        """Запускает companion на часах."""
        if not self._connected:
            return False
        component = f"{WATCH_PACKAGE}/{WATCH_LAUNCH_ACTIVITY}"
        rc, out, err = self._run_adb(
            "-s", self._target, "shell", "am", "start", "-n", component,
            timeout=15,
        )
        log.info("adb shell am start → rc=%d out=%s err=%s", rc, out.strip(), err.strip())
        if rc == 0:
            self._started = True
            return True
        return False

    def adb_disconnect(self):
        """Отключается от часов."""
        if self._target:
            self._run_adb("disconnect", self._target, timeout=10)
        self._connected = False

    # ── Статус ──

    def is_connected(self):
        return self._connected

    def is_installed(self):
        return self._installed

    def is_started(self):
        return self._started

    def reset(self):
        self._connected = False
        self._installed = False
        self._started = False
        self._target = None
