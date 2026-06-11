"""AndroidCameraBridge — камера Android через pyjnius.

Camera1 (основной, надёжнее через pyjnius) → Camera2 (fallback).
"""

from __future__ import annotations

import logging
import os
import threading
import time

log = logging.getLogger(__name__)

try:
    from kivy.utils import platform as _kivy_platform
    IS_ANDROID = (_kivy_platform == "android")
except Exception:
    IS_ANDROID = False


class AndroidCameraBridge:
    def __init__(self) -> None:
        self.is_android = IS_ANDROID
        self._latest_mean_red: float = 0.0
        self._lock = threading.Lock()
        self._running = False
        self._ready = False
        self._frame_count = 0
        self._has_flash = False
        self._camera_method = "none"
        self._error_detail = ""
        self._permission_granted = False

        self._camera1 = None
        self._camera2 = None
        self._session = None
        self._reader = None
        self._handler_thread = None
        self._handler = None
        self._camera_id = None
        self._camera_manager = None
        self._preview_callback = None
        self._image_listener = None

        self._debug_frame_dir = None
        self._debug_frames_left = 0
        self._debug_every_n_frames = 15
        self._debug_last_saved_frame = 0

    # ── публичный API ──
    def request_permission(self) -> bool:
        if not self.is_android:
            return False
        try:
            # Сначала проверяем, есть ли уже разрешение
            from jnius import autoclass
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            if activity is None:
                log.warning("request_permission: Activity is None, will retry later")
                return False
            PackageManager = autoclass("android.content.pm.PackageManager")
            PERMISSION_CAMERA = autoclass("android.Manifest$permission").CAMERA
            granted = activity.checkSelfPermission(PERMISSION_CAMERA)
            if granted == PackageManager.PERMISSION_GRANTED:
                self._permission_granted = True
                log.info("Camera permission already granted")
                return True
            # Запрашиваем
            activity.requestPermissions([PERMISSION_CAMERA], 1001)
            # Ждём результат (упрощённо — в реальности нужен callback)
            for _ in range(10):
                time.sleep(0.5)
                granted = activity.checkSelfPermission(PERMISSION_CAMERA)
                if granted == PackageManager.PERMISSION_GRANTED:
                    self._permission_granted = True
                    log.info("Camera permission granted by user")
                    return True
            self._error_detail = "Разрешение камеры не получено"
            log.warning("Camera permission not granted after request")
            return False
        except Exception as exc:
            self._error_detail = f"Permission check error: {exc}"
            log.error(f"request_permission failed: {exc}")
            return False

    def is_ready(self) -> bool:
        return self._ready

    def get_status_text(self) -> str:
        if not IS_ANDROID:
            return "Десктоп (камера недоступна)"
        if self._ready:
            return f"Камера активна ({self._camera_method}, кадров: {self._frame_count})"
        if self._error_detail:
            return self._error_detail
        if self._running:
            return "Камера открывается..."
        if not self._permission_granted:
            return "Нет разрешения на камеру"
        return "Камера не подключена"

    def start_capture(self, target_resolution: tuple = (640, 480)) -> bool:
        if not IS_ANDROID:
            return False
        if self._running:
            return True

        # Сначала — разрешение
        if not self._permission_granted:
            if not self.request_permission():
                return False

        # Camera1 — надёжнее
        err1 = ""
        ok = self._start_camera1(target_resolution)
        if ok:
            self._camera_method = "camera1"
            return True
        err1 = self._error_detail

        # Camera2 — fallback
        err2 = ""
        ok = self._start_camera2(target_resolution)
        if ok:
            self._camera_method = "camera2"
            return True
        err2 = self._error_detail

        self._error_detail = f"Camera1: {err1} | Camera2: {err2}"
        return False

    def enable_debug_frames(self, count: int = 5, every_n_frames: int = 15) -> str:
        """Сохранить несколько preview-кадров в PGM для отладки PPG."""
        self._debug_frame_dir = self._get_debug_frame_dir()
        os.makedirs(self._debug_frame_dir, exist_ok=True)
        self._debug_frames_left = max(0, int(count))
        self._debug_every_n_frames = max(1, int(every_n_frames))
        self._debug_last_saved_frame = 0
        return self._debug_frame_dir

    def _get_debug_frame_dir(self) -> str:
        if self.is_android:
            try:
                from jnius import autoclass
                PythonActivity = autoclass("org.kivy.android.PythonActivity")
                activity = PythonActivity.mActivity
                if activity is not None:
                    ext_dir = activity.getExternalFilesDir(None)
                    if ext_dir is not None:
                        return os.path.join(ext_dir.getAbsolutePath(), "aegis_frames")
                    return os.path.join(activity.getFilesDir().getAbsolutePath(), "aegis_frames")
            except Exception as exc:
                log.error(f"debug frame dir: {exc}")
        return os.path.abspath("aegis_frames")

    def _save_debug_pgm(self, data, width: int, height: int, label: str = "camera") -> None:
        if self._debug_frames_left <= 0 or self._debug_frame_dir is None:
            return
        if self._frame_count - self._debug_last_saved_frame < self._debug_every_n_frames:
            return
        self._debug_last_saved_frame = self._frame_count
        self._debug_frames_left -= 1

        try:
            y_size = width * height
            frame = bytes((data[i] & 0xFF for i in range(y_size)))
            filename = f"{label}_{int(time.time() * 1000)}_{width}x{height}.pgm"
            path = os.path.join(self._debug_frame_dir, filename)
            with open(path, "wb") as fh:
                fh.write(f"P5\n{width} {height}\n255\n".encode("ascii"))
                fh.write(frame)
            log.info(f"Saved debug camera frame: {path}")
        except Exception as exc:
            log.error(f"save debug frame: {exc}")

    # ── Camera1 ──
    def _start_camera1(self, target_resolution: tuple = (640, 480)) -> bool:
        try:
            from jnius import PythonJavaClass, autoclass, java_method
            Camera = autoclass("android.hardware.Camera")
            bridge_ref = self
            w, h = target_resolution

            self._camera1 = Camera.open(0)
            if self._camera1 is None:
                self._error_detail = "Camera.open() = None"
                return False

            params = self._camera1.getParameters()

            # Поддерживаемое разрешение
            supported = params.getSupportedPreviewSizes()
            best = None
            for s in supported:
                if s.width <= w and s.height <= h:
                    if best is None or s.width > best.width:
                        best = s
            if best is not None:
                w, h = best.width, best.height
            params.setPreviewSize(w, h)

            # Фиксированный фокус
            focus_modes = params.getSupportedFocusModes()
            if focus_modes:
                for m in ["fixed", "infinity", "continuous-video"]:
                    if m in focus_modes:
                        params.setFocusMode(m)
                        break
            flash_modes = params.getSupportedFlashModes()
            self._has_flash = flash_modes is not None and len(flash_modes) > 0
            if self._has_flash and "off" in flash_modes:
                params.setFlashMode("off")
            self._camera1.setParameters(params)

            final_w, final_h = w, h

            class _PreviewCb(PythonJavaClass):
                __javainterfaces__ = ["android/hardware/Camera$PreviewCallback"]
                __javacontext__ = "app"

                @java_method("([BLandroid/hardware/Camera;)V")
                def onPreviewFrame(self, data, camera):  # noqa: N802
                    try:
                        y_size = final_w * final_h
                        if len(data) < y_size:
                            return
                        x0 = int(final_w * 0.2)
                        x1 = int(final_w * 0.8)
                        y0 = int(final_h * 0.2)
                        y1 = int(final_h * 0.8)
                        total = 0
                        n = 0
                        for row in range(y0, y1):
                            base = row * final_w
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
                        bridge_ref._save_debug_pgm(data, final_w, final_h, "camera1")
                    except Exception as exc:
                        log.error(f"Camera1 frame: {exc}")

            self._preview_callback = _PreviewCb()
            self._camera1.setPreviewCallback(self._preview_callback)

            # Пробуем без SurfaceTexture (работает на большинстве устройств)
            try:
                self._camera1.startPreview()
                self._running = True
                log.info(f"Camera1 started (no surface): {w}x{h}")
                return True
            except Exception as e1:
                log.warning(f"Camera1 startPreview without surface failed: {e1}")
                # Fallback: SurfaceTexture
                try:
                    SurfaceTexture = autoclass("android.graphics.SurfaceTexture")
                    # Создаём SurfaceTexture с реальным GL контекстом или dummy
                    surface = SurfaceTexture(0)
                    surface.setDefaultBufferSize(w, h)
                    self._camera1.setPreviewTexture(surface)
                    self._camera1.startPreview()
                    self._running = True
                    log.info(f"Camera1 started (SurfaceTexture): {w}x{h}")
                    return True
                except Exception as e2:
                    # Последний шанс: Surface через SurfaceView
                    try:
                        Surface = autoclass("android.view.Surface")
                        # Создаём фейковую поверхность для preview
                        surface_texture = SurfaceTexture(0)
                        surface_texture.setDefaultBufferSize(w, h)
                        fake_surface = Surface(surface_texture)
                        try:
                            self._camera1.setPreviewDisplay(
                                autoclass("android.view.SurfaceHolder").getClass()
                            )
                        except Exception:
                            pass
                        self._camera1.startPreview()
                        self._running = True
                        log.info(f"Camera1 started (fake surface): {w}x{h}")
                        return True
                    except Exception as e3:
                        self._error_detail = f"no surface: {e1}, tex: {e2}, fake: {e3}"
                        log.error(f"Camera1 all surface attempts failed")
                        try:
                            self._camera1.release()
                        except Exception:
                            pass
                        self._camera1 = None
                        return False
        except Exception as exc:
            self._error_detail = str(exc)
            log.error(f"Camera1 failed: {exc}")
            try:
                if self._camera1 is not None:
                    self._camera1.release()
                    self._camera1 = None
            except Exception:
                pass
            return False

    # ── Camera2 ──
    def _start_camera2(self, target_resolution: tuple = (640, 480)) -> bool:
        try:
            from jnius import PythonJavaClass, autoclass, java_method
            Context = autoclass("android.content.Context")
            CameraManager = autoclass("android.hardware.camera2.CameraManager")
            CameraCharacteristics = autoclass("android.hardware.camera2.CameraCharacteristics")
            ImageReader = autoclass("android.media.ImageReader")
            ImageFormat = autoclass("android.graphics.ImageFormat")
            HandlerThread = autoclass("android.os.HandlerThread")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            activity = PythonActivity.mActivity
            if activity is None:
                self._error_detail = "Activity is None"
                return False

            self._camera_manager = activity.getSystemService(Context.CAMERA_SERVICE)
            w, h = target_resolution
            self._reader = ImageReader.newInstance(w, h, ImageFormat.YUV_420_888, 2)

            self._handler_thread = HandlerThread("AegisCam2")
            self._handler_thread.start()
            Handler = autoclass("android.os.Handler")
            self._handler = Handler(self._handler_thread.getLooper())

            bridge_ref = self

            class _Listener(PythonJavaClass):
                __javainterfaces__ = ["android/media/ImageReader$OnImageAvailableListener"]
                __javacontext__ = "app"

                @java_method("(Landroid/media/ImageReader;)V")
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
                        red_value = (128.0 - mean) + 128.0
                        with bridge_ref._lock:
                            bridge_ref._latest_mean_red = float(red_value)
                            bridge_ref._frame_count += 1
                            if bridge_ref._frame_count >= 3:
                                bridge_ref._ready = True
                        image.close()
                    except Exception as exc:
                        log.error(f"Camera2 frame: {exc}")

            self._image_listener = _Listener()
            self._reader.setOnImageAvailableListener(self._image_listener, self._handler)

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
            SessionCallback = autoclass("android.hardware.camera2.CameraCaptureSession$StateCallback")
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
                                    log.info("Camera2 streaming")
                                except Exception as exc:
                                    log.error(f"Camera2 repeat: {exc}")

                            def onConfigureFailed(self, session):  # noqa: N802
                                log.error("Camera2 session failed")

                        camera.createCaptureSession([reader_surface], _SessionCb(), bridge._handler)
                    except Exception as exc:
                        log.error(f"Camera2 onOpened: {exc}")

                def onError(self, camera, error):  # noqa: N802
                    log.error(f"Camera2 error: {error}")

                def onDisconnected(self, camera):  # noqa: N802
                    log.warning("Camera2 disconnected")

            self._camera2 = self._camera_manager.openCamera(
                self._camera_id, _CamCallback(), self._handler
            )
            log.info(f"Camera2 open requested: {self._camera_id}")
            return True
        except Exception as exc:
            self._error_detail = str(exc)
            log.error(f"Camera2 failed: {exc}")
            return False

    # ── управление ──
    def stop_capture(self) -> None:
        try:
            self.set_flash(False)
        except Exception:
            pass
        self._running = False
        self._ready = False
        for obj, cleanup in [
            (self._camera1, lambda: (self._camera1.stopPreview(), self._camera1.setPreviewCallback(None), self._camera1.release())),
            (self._session, lambda: self._session.close()),
            (self._camera2, lambda: self._camera2.close()),
            (self._reader, lambda: self._reader.close()),
            (self._handler_thread, lambda: self._handler_thread.quit()),
        ]:
            if obj is not None:
                try:
                    cleanup()
                except Exception:
                    pass
        self._camera1 = None
        self._session = None
        self._camera2 = None
        self._reader = None
        self._handler_thread = None
        self._preview_callback = None
        self._image_listener = None
        self._camera_method = "none"
        self._latest_mean_red = 0.0
        self._frame_count = 0

    def get_mean_red(self) -> float:
        with self._lock:
            return self._latest_mean_red

    def set_flash(self, turn_on: bool) -> bool:
        if not IS_ANDROID:
            return False
        if self._camera_method == "camera1" and self._camera1 is not None:
            try:
                params = self._camera1.getParameters()
                if turn_on and self._has_flash:
                    params.setFlashMode("torch")
                else:
                    params.setFlashMode("off")
                self._camera1.setParameters(params)
                return True
            except Exception as exc:
                log.error(f"Camera1 flash: {exc}")
                return False
        elif self._camera_method == "camera2" and self._camera_manager is not None:
            try:
                self._camera_manager.setTorchMode(self._camera_id, bool(turn_on))
                return True
            except Exception as exc:
                log.error(f"Camera2 flash: {exc}")
                return False
        return False
