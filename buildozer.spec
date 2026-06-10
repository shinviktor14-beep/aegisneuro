# buildozer.spec — конфигурация сборки AegisNeuro в Android APK
# Генерируется автоматически; правьте при необходимости.

[app]
# Имя в системе (lowercase, без пробелов)
title = AegisNeuro
package.name = aegisneuro
package.domain = org.aegisneuro

# Источник
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_patterns = .git,__pycache__,*.pyc,*.pyo,*.swp,.buildozer,bin,data,*.md,__pycache__/*,aegis/*

# Версия
version = 1.0.0
# version.filename оставляем пустым — buildozer сам генерирует имя
# (его шаблон %(app)s-%(version)s-... ломает configparser-интерполяцию)
# version.regex убран: опционален и без __version__ в коде шумит в логах.

# Главный модуль
mainfilename = main.py

# Иконка
icon.filename = icon.png
# presplash.filename = presplash.png  # можно добавить позже

# Ориентация экрана
orientation = portrait

# Включаем AIDL (нужно для Camera2 API)
android.enable_aidl = True

# Android API
android.api = 31
android.minapi = 24
android.ndk_api = 21

# Архитектура: только arm64 — современные Android 8+
android.archs = arm64-v8a

# Разрешения
android.permissions = CAMERA,FLASHLIGHT,WAKE_LOCK,MODIFY_AUDIO_SETTINGS
android.meta_data = com.google.android.gms.version=0

# Зависимости для сборки
requirements = python3,kivy==2.3.0,kivymd==1.1.1,numpy,pyjnius,android

# Цикл рендеринга (sdl2 — стандарт для Kivy)
p4a.activity_class_name = org.kivy.android.PythonActivity

[buildozer]
log_level = 2

# Цвета темы Android (по желанию)
android.antipattern = True
