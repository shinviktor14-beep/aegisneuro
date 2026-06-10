"""AndroidCameraBridge — обёртка над Camera2 API через pyjnius.

На Android:
  - открывает заднюю камеру,
  - запускает фоновый поток-читатель ImageReader (YUV_420_888),
  - из каждого кадра считает средний уровень «красного» (Cr-плоскость) — это
    и есть PPG-сигнал с пальца,
  - умеет включать/выключать фонарик через CameraManager.setTorchMode.

На не-Android (Windows/Linux/Mac) — безопасный fallback, методы — no-op.
Тогда источником «красного» должен быть opencv-канал в верхнем слое.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

try:
    from kivy.utils import platform as _kivy_platform
    IS_ANDROID = (_kivy_platform == "android")
except Exception:  # noqa: BLE001
    IS_ANDROID = False


class AndroidCameraBridge:
    """Camera2 → ImageReader → поток «средний красный» в реальном времени."""

    def __init__(self) -> None:
        self.is_android = IS_ANDROID
        self._latest_mean_red: float = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._has_flash = False

        # Ссылки на Java-объекты, чтобы их не собрал GC
        self._camera = None
        self._session = None
        self._reader = None
        self._handler_thread = None
        self._handler = None
        self._camera_id = None
        self._camera_manager = None

    # -------------------------------------------------------- публичный API
    def request_permission(self) -> None:
        """Запросить CAMERA-разрешение (только Android 6+). На десктопе no-op."""
        if not self.is_android:
            return
        try:
            from jnius import autoclass  # type: ignore
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            Context = autoclass("android.content.Context")
            PackageManager = autoclass("android.content.pm.PackageManager")
            PERMISSION_CAMERA = autoclass("android.Manifest$permission").CAMERA
            granted = activity.checkSelfPermission(PERMISSION_CAMERA)
            if granted != PackageManager.PERMISSION_GRANTED:
                # 0x00000001 = REQUEST_PERMISSIONS (новые Android-ы могут кинуть
                # SecurityException, если окошко запрашивает разрешение из фона)
                activity.requestPermissions([PERMISSION_CAMERA], 1)
                # 0x00000001 = REQUEST_PERMISSIONS, даём системе ~1 сек на показ диалога
                time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Camera] permission request failed: {exc}")

    def start_capture(self, target_resolution: tuple[int, int] = (640, 480)) -> bool:
        """Открыть камеру и начать читать кадры. Возвращает True при успехе."""
        if not self.is_android:
            print("[Aegis-Camera] start_capture: desktop fallback (no-op).")
            return False
        if self._running:
            return True
        try:
            from jnius import autoclass  # type: ignore
            Context = autoclass("android.content.Context")
            CameraManager = autoclass("android.hardware.camera2.CameraManager")
            CameraCharacteristics = autoclass("android.hardware.camera2.CameraCharacteristics")
            ImageReader = autoclass("android.media.ImageReader")
            HandlerThread = autoclass("android.os.HandlerThread")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity

            self._camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
            w, h = target_resolution
            # newImageReader(width, height, format, maxImages)
            self._reader = ImageReader.newInstance(w, h, ImageReader.YUV_420_888, 2)

            # Читающий поток на отдельном HandlerThread
            self._handler_thread = HandlerThread("AegisCameraBg")
            self._handler_thread.start()
            Handler = autoclass("android.os.Handler")
            self._handler = Handler(self._handler_thread.getLooper())

            # Колбэк: OnImageAvailableListener (лямбда Java-интерфейс)
            OnImageAvailableListener = autoclass(
                "android.media.ImageReader$OnImageAvailableListener"
            )
            bridge_ref = self

            class _Listener(OnImageAvailableListener):
                def onImageAvailable(self, reader):  # noqa: N802
                    try:
                        image = reader.acquireLatestImage()
                        if image is None:
                            return
                        planes = image.getPlanes()
                        # planes[2] — Cr-плоскость в YUV_420_888 (U=1, V=2).
                        # Cr кодирует «красноту» с обратным знаком — инвертируем.
                        cr_plane = planes[2]
                        buffer = cr_plane.getBuffer()
                        row_stride = cr_plane.getRowStride()
                        pixel_stride = cr_plane.getPixelStride()
                        data = bytes(buffer)
                        # Центральная область 60% — самый стабильный PPG-сигнал
                        width = image.getWidth()
                        height = image.getHeight()
                        x0 = int(width * 0.2)
                        x1 = int(width * 0.8)
                        y0 = int(height * 0.2)
                        y1 = int(height * 0.8)
                        if x1 <= x0 or y1 <= y0:
                            image.close()
                            return
                        if pixel_stride == 1:
                            arr = list(data[y0 * row_stride + x0: y1 * row_stride + x1])
                            if not arr:
                                image.close()
                                return
                            mean = sum(arr) / len(arr)
                        else:
                            total = 0
                            n = 0
                            for y in range(y0, y1):
                                base = y * row_stride
                                for x in range(x0, x1):
                                    total += data[base + x * pixel_stride]
                                    n += 1
                            if n == 0:
                                image.close()
                                return
                            mean = total / n
                        # 128 — нейтральный уровень Cr, >128 — холоднее, <128 — теплее.
                        # Для PPG важна вариация, а не абсолют; нормируем к 0..255.
                        red_value = (128.0 - mean) + 128.0
                        with bridge_ref._lock:
                            bridge_ref._latest_mean_red = float(red_value)
                        image.close()
                    except Exception as exc:  # noqa: BLE001
                        print(f"[Aegis-Camera] frame error: {exc}")

            self._reader.setOnImageAvailableListener(_Listener(), self._handler)

            # Открываем заднюю камеру
            camera_ids = list(self._camera_manager.getCameraIdList())
            self._camera_id = camera_ids[0]
            chars = self._camera_manager.getCameraCharacteristics(self._camera_id)
            facing = chars.get(CameraCharacteristics.LENS_FACING)
            LENS_FACING_BACK = CameraCharacteristics.LENS_FACING_BACK
            # Если 0-я камера — фронталка, берём первую заднюю
            for cid in camera_ids:
                c = self._camera_manager.getCameraCharacteristics(str(cid))
                if c.get(CameraCharacteristics.LENS_FACING) == LENS_FACING_BACK:
                    self._camera_id = str(cid)
                    break
            # del facing  # silence linter

            self._camera = self._camera_manager.openCamera(
                self._camera_id, autoclass("android.hardware.camera2.CameraDevice$StateCallback")() if False else None
            )
            # Камера открыта; собираем CaptureRequest + CaptureSession в отдельном методе
            self._open_session(w, h)
            self._running = True
            self._has_flash = bool(
                chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE)
            ) if False else True  # не критично, фонарик проверяем в set_flash
            print(f"[Aegis-Camera] camera {self._camera_id} opened, resolution {w}x{h}")
            return True
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Camera] start_capture failed: {exc}")
            self.is_android = False  # откатываемся в fallback-режим
            return False

    def _open_session(self, w: int, h: int) -> None:
        """Открыть CameraCaptureSession и направить поток в ImageReader."""
        try:
            from jnius import autoclass  # type: ignore
            Surface = autoclass("android.view.Surface")
            reader_surface = self._reader.getSurface()
            CaptureRequest = autoclass("android.hardware.camera2.CaptureRequest")
            CameraDevice = autoclass("android.hardware.camera2.CameraDevice")

            StateCallback = autoclass("android.hardware.camera2.CameraDevice$StateCallback")

            class _CamCallback(StateCallback):
                def onOpened(self, camera):  # noqa: N802
                    try:
                        builder = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
                        builder.addTarget(reader_surface)
                        # AF off, AE on
                        builder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF)
                        builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
                        request = builder.build()

                        SessionCallback = autoclass(
                            "android.hardware.camera2.CameraCaptureSession$StateCallback"
                        )

                        class _SessionCb(SessionCallback):
                            def onConfigured(self, session):  # noqa: N802
                                try:
                                    session.setRepeatingRequest(request, None, None)
                                except Exception as exc:  # noqa: BLE001
                                    print(f"[Aegis-Camera] repeating request: {exc}")

                            def onConfigureFailed(self, session):  # noqa: N802
                                print("[Aegis-Camera] session configure failed")

                        camera.createCaptureSession(
                            [reader_surface], _SessionCb(), None
                        )
                    except Exception as exc:  # noqa: BLE001
                        print(f"[Aegis-Camera] onOpened: {exc}")

                def onError(self, camera, error):  # noqa: N802
                    print(f"[Aegis-Camera] device error: {error}")

            # Переоткрываем камеру с правильным callback
            self._camera = self._camera_manager.openCamera(
                self._camera_id, _CamCallback(), None
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Camera] _open_session: {exc}")

    def stop_capture(self) -> None:
        """Закрыть камеру и фоновый поток."""
        self._running = False
        try:
            if self._session is not None:
                self._session.close()
                self._session = None
            if self._camera is not None:
                self._camera.close()
                self._camera = None
            if self._reader is not None:
                self._reader.close()
                self._reader = None
            if self._handler_thread is not None:
                self._handler_thread.quit()
                self._handler_thread = None
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Camera] stop_capture: {exc}")

    def get_mean_red(self) -> float:
        """Последний сэмпл «среднего красного» из камеры (или 0, если кадров ещё нет)."""
        with self._lock:
            return self._latest_mean_red

    def set_flash(self, turn_on: bool) -> None:
        """Включить/выключить фонарик. На десктопе — print."""
        if not self.is_android:
            print(f"[Aegis-Hardware] Фонарик: {'ВКЛ' if turn_on else 'ВЫКЛ'} (desktop stub)")
            return
        try:
            from jnius import autoclass  # type: ignore
            # Получаем свежий manager (мог переинициализироваться)
            if self._camera_manager is None:
                Context = autoclass("android.content.Context")
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                self._camera_manager = PythonActivity.mActivity.getSystemService(
                    Context.CAMERA_SERVICE
                )
            self._camera_manager.setTorchMode(self._camera_id, bool(turn_on))
        except Exception as exc:  # noqa: BLE001
            print(f"[Aegis-Hardware] set_flash: {exc}")
