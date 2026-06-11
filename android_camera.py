"""AndroidCameraBridge — обёртка над камерой Android через pyjnius.

Поддерживает два режима:
  1. Camera2 API (Android 5+, предпочтительно) — ImageReader, YUV_420_888
  2. Старая Camera API (fallback) — PreviewCallback с NV21

На не-Android (Windows/Linux/Mac) — безопасный no-op.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

log = logging.getLogger(__name__)

try:
    from kivy.utils import platform as _kivy_platform
    IS_ANDROID = (_kivy_platform == "android")
except Exception:  # noqa: BLE001
    log.debug("Kivy platform detection failed, assuming non-Android")
    IS_ANDROID = False


class AndroidCameraBridge:
    """Camera → поток «средний красный» в реальном времени."""

    def __init__(self) -> None:
        self.is_android = IS_ANDROID
        self._latest_mean_red: float = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._ready = False  # True когда кадры реально поступают
        self._frame_count = 0
        self._has_flash = False
        self._camera_method = "none"  # "camera2", "camera1", "none"

        # Java-объекты
        self._camera = None
        self._camera1 = None
        self._session = None
        self._reader = None
        self._handler_thread = None
        self._handler = None
        self._camera_id = None
        self._camera_manager = None

    # -------------------------------------------------------- публичный API
    def request_permission(self) -> None:
        if not self.is_android:
            return
        try:
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            PackageManager = autoclass("android.content.pm.PackageManager")
            PERMISSION_CAMERA = autoclass("android.Manifest$permission").CAMERA
            granted = activity.checkSelfPermission(PERMISSION_CAMERA)
            if granted != PackageManager.PERMISSION_GRANTED:
                activity.requestPermissions([PERMISSION_CAMERA], 1)
                time.sleep(2.0)
        except Exception as exc:
            log.error(f"permission request failed: {exc}")

    def is_ready(self) -> bool:
        """Камера открыта и кадры поступают."""
        return self._ready

    def get_status_text(self) -> str:
        """Текстовый статус для UI."""
        if not self.is_android:
            return "Десктоп (камера недоступна)"
        if self._ready:
            return f"Камера активна ({self._camera_method}, {self._frame_count} кадров)"
        if self._running:
            return "Камера открывается..."
        return "Камера не подключена"

    def start_capture(self, target_resolution: tuple[int, int] = (640, 480)) -> bool:
        if not self.is_android:
            log.info("start_capture: desktop fallback (no-op).")
            return False
        if self._running:
            return True

        # Сначала пробуем Camera2, если падает — Camera1
        if self._start_camera2(target_resolution):
            self._camera_method = "camera2"
            return True
        log.warning("Camera2 failed, trying Camera1 fallback...")
        if self._start_camera1(target_resolution):
            self._camera_method = "camera1"
            return True
        log.error("Both Camera2 and Camera1 failed")
        self.is_android = False
        return False

    # -------------------------------------------------------- Camera2
    def _start_camera2(self, target_resolution: tuple[int, int] = (640, 480)) -> bool:
        try:
            from jnius import autoclass
            Context = autoclass("android.content.Context")
            CameraManager = autoclass("android.hardware.camera2.CameraManager")
            CameraCharacteristics = autoclass("android.hardware.camera2.CameraCharacteristics")
            ImageReader = autoclass("android.media.ImageReader")
            HandlerThread = autoclass("android.os.HandlerThread")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity

            self._camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
            w, h = target_resolution
            self._reader = ImageReader.newInstance(w, h, ImageReader.YUV_420_888, 2)

            self._handler_thread = HandlerThread("AegisCamera2Bg")
            self._handler_thread.start()
            Handler = autoclass("android.os.Handler")
            self._handler = Handler(self._handler_thread.getLooper())

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
                        cr_plane = planes[2]
                        buffer = cr_plane.getBuffer()
                        row_stride = cr_plane.getRowStride()
                        pixel_stride = cr_plane.getPixelStride()
                        data = bytes(buffer)
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
                        # PPG: больше красного = палец на камере = значение ниже
                        red_value = (128.0 - mean) + 128.0
                        with bridge_ref._lock:
                            bridge_ref._latest_mean_red = float(red_value)
                            bridge_ref._frame_count += 1
                            if bridge_ref._frame_count >= 3:
                                bridge_ref._ready = True
                        image.close()
                    except Exception as exc:
                        log.error(f"frame error: {exc}")

            self._reader.setOnImageAvailableListener(_Listener(), self._handler)

            camera_ids = list(self._camera_manager.getCameraIdList())
            self._camera_id = None
            for cid in camera_ids:
                c = self._camera_manager.getCameraCharacteristics(str(cid))
                if c.get(CameraCharacteristics.LENS_FACING) == CameraCharacteristics.LENS_FACING_BACK:
                    self._camera_id = str(cid)
                    break
            if self._camera_id is None and camera_ids:
                self._camera_id = str(camera_ids[0])

            chars = self._camera_manager.getCameraCharacteristics(self._camera_id)
            self._has_flash = bool(chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE))

            CaptureRequest = autoclass("android.hardware.camera2.CaptureRequest")
            CameraDevice = autoclass("android.hardware.camera2.CameraDevice")
            StateCallback = autoclass("android.hardware.camera2.CameraDevice$StateCallback")
            SessionCallback = autoclass(
                "android.hardware.camera2.CameraCaptureSession$StateCallback"
            )
            reader_surface = self._reader.getSurface()
            bridge = self

            class _CamCallback(StateCallback):
                def onOpened(self, camera):  # noqa: N802
                    try:
                        builder = camera.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
                        builder.addTarget(reader_surface)
                        builder.set(CaptureRequest.CONTROL_AF_MODE, CaptureRequest.CONTROL_AF_MODE_OFF)
                        builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_ON)
                        request = builder.build()

                        class _SessionCb(SessionCallback):
                            def onConfigured(self, session):  # noqa: N802
                                try:
                                    session.setRepeatingRequest(request, None, bridge._handler)
                                    bridge._session = session
                                    bridge._running = True
                                    log.info("Camera2 session configured, streaming frames")
                                except Exception as exc:
                                    log.error(f"repeating request: {exc}")

                            def onConfigureFailed(self, session):  # noqa: N802
                                log.error("Camera2 session configure failed")

                        camera.createCaptureSession([reader_surface], _SessionCb(), bridge._handler)
                    except Exception as exc:
                        log.error(f"Camera2 onOpened: {exc}")

                def onError(self, camera, error):  # noqa: N802
                    log.error(f"Camera2 device error: {error}")

                def onDisconnected(self, camera):  # noqa: N802
                    log.warning("Camera2 disconnected")

            self._camera = self._camera_manager.openCamera(
                self._camera_id, _CamCallback(), self._handler
            )
            log.info(f"Camera2 open requested: {self._camera_id}, {w}x{h}")
            return True
        except Exception as exc:
            log.error(f"Camera2 start_capture failed: {exc}")
            return False

    # -------------------------------------------------------- Camera1 fallback
    def _start_camera1(self, target_resolution: tuple[int, int] = (640, 480)) -> bool:
        """Fallback на старую Camera API — надёжнее на многих устройствах."""
        try:
            from jnius import autoclass
            Camera = autoclass("android.hardware.Camera")
            bridge_ref = self

            self._camera1 = Camera.open(0)  # задняя камера
            params = self._camera1.getParameters()
            w, h = target_resolution
            params.setPreviewSize(w, h)
            params.setFocusMode(Camera.Parameters.FOCUS_MODE_FIXED if hasattr(Camera.Parameters, 'FOCUS_MODE_FIXED') else "fixed")
            params.setFlashMode(Camera.Parameters.FLASH_MODE_OFF)
            self._camera1.setParameters(params)

            PreviewCallback = autoclass("android.hardware.Camera$PreviewCallback")
            self._has_flash = params.getSupportedFlashModes() is not None

            class _PreviewCb(PreviewCallback):
                def onPreviewFrame(self, data, camera):  # noqa: N802
                    try:
                        # NV21: Y plane first, then VU interleaved
                        # Для PPG берём средний Y (яркость) — это работает для красного света фонарика
                        length = len(data)
                        # Предполагаем 640x480 NV21
                        y_size = w * h
                        if length < y_size:
                            return
                        # Берём центральную область Y-плоскости
                        x0 = int(w * 0.2)
                        x1 = int(w * 0.8)
                        y0 = int(h * 0.2)
                        y1 = int(h * 0.8)
                        total = 0
                        n = 0
                        for row in range(y0, y1):
                            base = row * w
                            for col in range(x0, x1):
                                total += data[base + col] & 0xFF
                                n += 1
                        if n == 0:
                            return
                        mean = total / n
                        with bridge_ref._lock:
                            bridge_ref._latest_mean_red = float(mean)
                            bridge_ref._frame_count += 1
                            if bridge_ref._frame_count >= 3:
                                bridge_ref._ready = True
                    except Exception as exc:
                        log.error(f"Camera1 frame error: {exc}")

            self._camera1.setPreviewCallback(_PreviewCb())
            # Нужна Surface для preview — используем фейковую
            SurfaceTexture = autoclass("android.graphics.SurfaceTexture")
            self._camera1.setPreviewTexture(SurfaceTexture(10))
            self._camera1.startPreview()
            self._running = True
            log.info("Camera1 fallback started")
            return True
        except Exception as exc:
            log.error(f"Camera1 fallback failed: {exc}")
            return False

    # -------------------------------------------------------- управление
    def stop_capture(self) -> None:
        self._running = False
        self._ready = False
        try:
            if self._session is not None:
                self._session.close()
                self._session = None
        except Exception:
            pass
        try:
            if self._camera is not None:
                self._camera.close()
                self._camera = None
        except Exception:
            pass
        try:
            if self._camera1 is not None:
                self._camera1.stopPreview()
                self._camera1.setPreviewCallback(None)
                self._camera1.release()
                self._camera1 = None
        except Exception:
            pass
        try:
            if self._reader is not None:
                self._reader.close()
                self._reader = None
        except Exception:
            pass
        try:
            if self._handler_thread is not None:
                self._handler_thread.quit()
                self._handler_thread = None
        except Exception:
            pass

    def get_mean_red(self) -> float:
        with self._lock:
            return self._latest_mean_red

    def set_flash(self, turn_on: bool) -> None:
        if not self.is_android:
            log.info(f"Фонарик: {'ВКЛ' if turn_on else 'ВЫКЛ'} (desktop stub)")
            return
        # Camera2: torch mode
        if self._camera_method == "camera2" and self._camera_manager is not None:
            try:
                from jnius import autoclass
                if self._camera_id is None:
                    Context = autoclass("android.content.Context")
                    PythonActivity = autoclass("org.kivy.android.PythonActivity")
                    self._camera_manager = PythonActivity.mActivity.getSystemService(
                        Context.CAMERA_SERVICE
                    )
                self._camera_manager.setTorchMode(self._camera_id, bool(turn_on))
                return
            except Exception as exc:
                log.error(f"Camera2 set_flash: {exc}")
        # Camera1: flash mode
        if self._camera_method == "camera1" and self._camera1 is not None:
            try:
                from jnius import autoclass
                Camera = autoclass("android.hardware.Camera")
                params = self._camera1.getParameters()
                if turn_on:
                    params.setFlashMode(Camera.Parameters.FLASH_MODE_TORCH)
                else:
                    params.setFlashMode(Camera.Parameters.FLASH_MODE_OFF)
                self._camera1.setParameters(params)
                return
            except Exception as exc:
                log.error(f"Camera1 set_flash: {exc}")
        log.warning(f"set_flash: no active camera ({self._camera_method})")