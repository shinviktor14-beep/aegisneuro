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

# Главный модуль
mainfilename = main.py

# Иконка
icon.filename = icon.png
# presplash.filename = presplash.png  # можно добавить позже

# Ориентация экрана
orientation = portrait

# Android API
android.api = 33
android.minapi = 24
android.ndk_api = 21
# Принудительно просим buildozer через sdkmanager поставить build-tools.
# Иначе он ищет tools/bin/sdkmanager (устаревший путь) и падает.
android.sdk = 33

# Архитектура: только arm64 — современные Android 8+
android.archs = arm64-v8a

android.accept_sdk_licenses = True

# Разрешения
android.permissions = CAMERA,WAKE_LOCK,MODIFY_AUDIO_SETTINGS
android.meta_data = com.google.android.gms.version=0

# Зависимости для сборки
requirements = python3,kivy==2.3.0,numpy,pyjnius,kivymd

[buildozer]
log_level = 2
