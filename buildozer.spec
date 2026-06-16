# buildozer.spec — конфигурация сборки AegisNeuro в Android APK/AAB
# Генерируется автоматически; правьте при необходимости.

[app]
# Имя в системе (lowercase, без пробелов)
title = AegisNeuro
package.name = aegisneuro
package.domain = org.aegisneuro

# Источник
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_patterns = .git,__pycache__,*.pyc,*.pyo,*.swp,.buildozer,bin,*.md,__pycache__/*

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
android.ndk_api = 24
# Принудительно просим buildozer через sdkmanager поставить build-tools.
# Иначе он ищет tools/bin/sdkmanager (устаревший путь) и падает.
android.sdk = 33

# Архитектура: только arm64 — современные Android 8+
android.archs = arm64-v8a

android.accept_sdk_licenses = True

# Разрешения
android.permissions = WAKE_LOCK,MODIFY_AUDIO_SETTINGS,BLUETOOTH,BLUETOOTH_ADMIN,BLUETOOTH_SCAN,BLUETOOTH_CONNECT,ACCESS_FINE_LOCATION,FOREGROUND_SERVICE
android.enable_androidx = True
# Wear OS Data Layer receiver: accepts watch vitals into watch_payloads.jsonl.
android.add_src = android_src
android.add_manifest_xml = android_manifest/aegis_watch_receiver.xml
android.gradle_dependencies = com.google.android.gms:play-services-wearable:19.0.0

# Зависимости для сборки
# Kivy 2.3.1 поддерживает Python 3.8-3.13
requirements = hostpython3==3.13.5,python3==3.13.5,kivy==2.3.1,numpy,pyjnius,kivymd

# Signing (release) — единый keystore для phone + watch
# Пароли берутся из env vars (см. keystore/keystore.env или CI Secrets).
#android.keystore = debug_keystore
#android.key.alias = debug
#android.key.pass = debug
#android.store.pass = debug
android.release.artifact = apk

[buildozer]
log_level = 2
