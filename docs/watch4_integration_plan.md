# AegisNeuro: план перехода на Samsung Galaxy Watch4

## Цель

Камера и фонарик больше не используются. Источник биосигнала переносится на Galaxy Watch4.

## Какие данные нужны в первую очередь

1. `HEART_RATE_BPM`
   - Базовый пульс.
   - Нужен для текущего состояния нагрузки и контроля артефактов.

2. `IBI` / R-R интервалы, если доступны на устройстве через Health Services или Samsung API
   - Главный сигнал для RMSSD и индекса стресса.
   - Если прямые IBI недоступны, используем HR как fallback, но HRV будет хуже.

3. Motion context: accelerometer / шаги / activity state
   - Нужен, чтобы отбраковывать HR/IBI во время движения.
   - Для диагностики AegisNeuro желательно состояние покоя 60-120 секунд.

## Второй этап

1. `SPO2`, если доступно
   - Не основной стресс-маркер, но полезно для контекста восстановления.

2. Sleep / passive history
   - Для утреннего baseline и долгосрочного профиля.

3. ECG/BP/BIA
   - Не закладывать в MVP: эти данные часто ограничены Samsung Health Monitor, регионом, разрешениями и не всегда доступны стороннему приложению.

## Архитектура

1. Wear OS app на часах
   - Kotlin/Compose.
   - Считывает HR/IBI через Health Services.
   - Показывает простой экран: статус сенсора, пульс, качество сигнала.

2. Phone companion в текущем AegisNeuro
   - Kivy/Python остается экраном управления, аудио и AI-контуром.
   - Принимает поток с часов и подает R-R интервалы в существующий StormPredictor/RL/audio.

3. Канал связи часы -> телефон
   - Wear OS Data Layer API.
   - Для live-потока: MessageClient.
   - Для последнего состояния/сводки: DataClient.

## MVP-поток

1. Пользователь запускает AegisNeuro на телефоне.
2. Пользователь запускает AegisNeuro Sensor на Watch4.
3. Часы начинают foreground measurement.
4. Каждые 1-2 секунды часы отправляют:
   - timestamp
   - heart_rate_bpm
   - ibi_ms array, если есть
   - motion/activity quality flag
5. Телефон принимает пакет.
6. AegisNeuro рассчитывает RMSSD, стресс-индекс, прогноз шторма.
7. RL-мозг выбирает частоту аудио.

## Следующая инженерная задача

Создать минимальный Wear OS модуль `wear/`:

- `MainActivity.kt`
- Health Services permissions
- MeasureClient / ExerciseClient поток HR
- Data Layer отправка JSON-пакетов на телефон

После этого добавить в телефонный app native bridge/receiver, который будет передавать данные в `WatchDataBridge`.

## v42 phone-side contract

Телефонная часть v42 принимает пакеты часов через JSONL inbox:

`watch_payloads.jsonl`

Каждая строка - один JSON-пакет:

```json
{"source":"galaxy_watch4","heart_rate_bpm":72,"ibi_ms":[820,830,810,840],"quality":"good"}
```

Поддерживаемые поля:

- `heart_rate_bpm` или `bpm` - текущий пульс, только для статуса.
- `ibi_ms`, `rr_intervals_ms`, `rr_ms` или `ibi` - R-R/IBI интервалы в миллисекундах.
- `quality` или `signal_quality` - качество сигнала (`good`, `poor`, `unknown`).
- `source` - источник, например `galaxy_watch4`.

Ограничения валидации:

- BPM принимается только в диапазоне 35-220.
- IBI/R-R принимаются только в диапазоне 300-2000 ms.
- Для HRV-анализа и выбора звуковой частоты нужно минимум 10 валидных IBI/R-R интервалов.

Важно: один BPM без IBI не подходит для RMSSD/стресс-индекса. В этом случае приложение покажет пульс, но не будет запускать диагностический контур.

## Wear OS module status

Добавлен отдельный Gradle-модуль `wear/`:

- standalone Gradle project in `wear/`
- app module: `wear/app`
- `org.aegisneuro.watch.MainActivity`
- Health Services `MeasureClient`
- Data Layer `MessageClient`
- Data Layer path: `/aegis/watch/vitals`
- отправляемый JSON совместим с `watch_payloads.jsonl`

Сборка часов после установки Gradle/Android Studio:

```powershell
cd wear
gradle :app:assembleDebug
```

Текущий поток часов:

```json
{"source":"galaxy_watch4","timestamp_ms":1781270000000,"heart_rate_bpm":72,"ibi_ms":[],"quality":"hr_only"}
```

Телефонная часть получила native receiver:

- `android_src/org/aegisneuro/aegisneuro/AegisWatchMessageService.java`
- манифест-фрагмент `android_manifest/aegis_watch_receiver.xml`
- receiver дописывает входящие сообщения в `watch_payloads.jsonl`, который читает `WatchDataBridge`

Важно: receiver пока не включен в `buildozer.spec` автоматически. Первая попытка подключить `com.google.android.gms:play-services-wearable` к python-for-android сборке сломала CI `v43`, поэтому код receiver оставлен в репозитории, а включение будет отдельным шагом после проверки совместимости Gradle dependency в Buildozer.

Ограничение текущего этапа: стандартный Health Services `MeasureClient` надежно дает `HEART_RATE_BPM`, но не гарантирует R-R/IBI на всех Wear OS устройствах. Поэтому `ibi_ms` пока отправляется пустым массивом. Для полноценного HRV нужно следующим шагом добавить отдельный источник IBI:

- Samsung Health/Samsung Privileged Health SDK, если доступен для проекта.
- Сырой PPG/сенсорный поток, если устройство и разрешения позволяют.
- Альтернативный сертифицированный внешний источник R-R, например BLE chest strap, как fallback.
