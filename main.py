"""护眼助手 — 主入口

一键调节所有屏幕的色温和亮度。
支持正常/黑白/反色/淡色模式切换。
多显示器使用统一 gamma ramp 确保效果一致。
"""
import logging
import threading
import atexit
from typing import Optional

from config import PRESETS, TRANSFORMS, TRANSFORM_DEFAULT, TEMP_MIN, TEMP_MAX, load_settings, save_settings
from core.monitor import enumerate_monitors, get_monitor_hdcs, release_monitors
from core.gamma import apply_gamma_smooth, apply_gamma_instant, reset_all_gamma
from core.color_effect import apply_color_effect, shutdown_color_effect
from gui.app import EyeComfortApp
from gui.tray import TrayIcon

logger = logging.getLogger(__name__)


class EyeComfortController:
    """控制器：连接 GUI 和核心引擎"""

    def __init__(self):
        self.settings = load_settings()

        # 枚举显示器
        self.monitors = enumerate_monitors()
        self.hdcs = get_monitor_hdcs(self.monitors)

        print(f"[护眼助手] 检测到 {len(self.monitors)} 个显示器:")
        for m in self.monitors:
            primary = " [主显示器]" if m.is_primary else ""
            print(f"  - {m.name} ({m.width}x{m.height}){primary}")
        if len(self.monitors) > 1:
            print("[护眼助手] 多显示器模式：所有屏幕使用统一色彩配置")

        # 当前状态
        self.current_temp = self.settings["temperature"]
        self.current_brightness = self.settings["brightness"]
        self.current_transform = self.settings.get("transform", TRANSFORM_DEFAULT)

        # 保护
        self._cleaned_up = False
        self._cleanup_lock = threading.Lock()
        self._save_timer: threading.Timer | None = None
        self._save_lock = threading.Lock()
        self._reset_in_progress = False  # 防止重置时触发多余 gamma 过渡

        # 创建 GUI
        self.app = EyeComfortApp(
            on_temp_change=self._on_temp_change,
            on_brightness_change=self._on_brightness_change,
            on_preset=self._on_preset,
            on_transform_change=self._on_transform_change,
            on_reset=self.reset_to_defaults,
            on_close=self._on_hide_window,
        )
        self.app.set_monitors_info(self.monitors)

        # 创建托盘
        self.tray = TrayIcon(
            on_preset=self._tray_on_preset,
            on_show_window=self._on_show_window,
            on_quit=self._on_quit,
        )

        # 恢复上次的状态
        self._restore_state()

        atexit.register(self._cleanup)

    def _restore_state(self):
        """恢复上次保存的状态（预设 + 变换模式）"""
        last_preset = self.settings.get("last_preset", "day")

        # 尝试恢复预设（包括 'reset'）
        if last_preset:
            preset = PRESETS.get(last_preset)
            if preset:
                self._apply(preset["temp"], preset["brightness"],
                           self.current_transform, smooth=False)
                self.app.set_values(preset["temp"], preset["brightness"],
                                   preset["name"])
                # 恢复变换模式 UI
                if self.current_transform != TRANSFORM_DEFAULT:
                    self.app.set_transform(self.current_transform)
                return

        # 没有有效预设 → 应用当前保存的温度/亮度
        self._apply(self.current_temp, self.current_brightness,
                   self.current_transform, smooth=False)
        self.app.set_values(self.current_temp, self.current_brightness,
                           "自定义")

        # 恢复变换模式 UI
        if self.current_transform != TRANSFORM_DEFAULT:
            self.app.set_transform(self.current_transform)

    # ─── 事件处理 ────────────────────────────────────────────────────────────
    def _on_preset(self, preset_key: str):
        """预设按钮点击（已在主线程中）— 唯一的 set_values 调用点"""
        preset = PRESETS.get(preset_key)
        if not preset:
            return
        # 重置模式下跳过 smooth 渐变，等 reset 全部就绪后再一次性应用
        smooth = not self._reset_in_progress
        self._apply(preset["temp"], preset["brightness"],
                   self.current_transform, smooth=smooth)
        self.app.set_values(preset["temp"], preset["brightness"], preset["name"])
        self.settings["last_preset"] = preset_key
        self._debounced_save()

    def _tray_on_preset(self, preset_key: str):
        """托盘菜单预设回调（在 pystray 线程中，路由到主线程）"""
        try:
            self.app.after(0, lambda: self._on_preset(preset_key))
        except Exception:
            # Tcl 解释器已销毁（shutdown 阶段），忽略
            pass

    def _on_temp_change(self, temp: int):
        """色温滑块变化"""
        self.current_temp = temp
        self._apply(temp, self.current_brightness, self.current_transform, smooth=False)
        with self._save_lock:
            self.settings["temperature"] = temp
            self.settings["last_preset"] = None
        self._debounced_save()

    def _on_brightness_change(self, brightness: int):
        """亮度滑块变化"""
        self.current_brightness = brightness
        self._apply(self.current_temp, brightness, self.current_transform, smooth=False)
        with self._save_lock:
            self.settings["brightness"] = brightness
            self.settings["last_preset"] = None
        self._debounced_save()

    def _on_transform_change(self, transform_key: str):
        """变换模式切换（正常/黑白/反色/淡色）"""
        self.current_transform = transform_key
        # 重置模式下跳过 smooth 渐变，等预设一起原子应用
        smooth = not self._reset_in_progress
        self._apply(self.current_temp, self.current_brightness, transform_key, smooth=smooth)
        with self._save_lock:
            self.settings["transform"] = transform_key
        self._debounced_save()

    def _on_hide_window(self):
        """隐藏主窗口"""
        self.app.withdraw()

    def reset_to_defaults(self):
        """重置到默认设置（原子操作，不启动任何 smooth 过渡）"""
        self._reset_in_progress = True
        try:
            self.current_transform = TRANSFORM_DEFAULT
            preset = PRESETS["reset"]
            self._apply(preset["temp"], preset["brightness"],
                       TRANSFORM_DEFAULT, smooth=False)
            self.app.set_values(preset["temp"], preset["brightness"],
                               preset["name"])
            self.app.set_transform(TRANSFORM_DEFAULT)
            with self._save_lock:
                self.settings["transform"] = TRANSFORM_DEFAULT
                self.settings["last_preset"] = "reset"
            self._debounced_save()
        finally:
            self._reset_in_progress = False

    def _on_show_window(self):
        """从托盘恢复主窗口（路由到主线程）"""
        try:
            self.app.after(0, self._show_window)
        except Exception:
            pass

    def _show_window(self):
        self.app.deiconify()
        self.app.lift()
        self.app.focus_force()

    def _on_quit(self):
        """退出应用（路由到主线程）"""
        try:
            self.app.after(0, self._do_quit)
        except Exception:
            # Tcl 解释器已销毁，直接清理
            self._cleanup()

    def _do_quit(self):
        self._cleanup()
        self.tray.stop()
        self.app.destroy()

    # ─── 核心操作 ────────────────────────────────────────────────────────────
    def _apply(self, temp: int, brightness: int,
               transform: Optional[str] = None,
               smooth: bool = True):
        """应用色温、亮度和变换到所有显示器。

        Args:
            transform: 变换模式，默认使用 self.current_transform
        """
        if transform is None:
            transform = self.current_transform

        # 夹持温度到有效范围，确保 update_icon 和 gamma 一致
        temp = max(TEMP_MIN, min(TEMP_MAX, temp))

        self.current_temp = temp
        self.current_brightness = brightness
        self.tray.update_icon(temp)

        brightness_f = brightness / 100.0

        apply_color_effect(transform)

        if smooth:
            apply_gamma_smooth(self.hdcs, temp, brightness_f, transform)
        else:
            apply_gamma_instant(self.hdcs, temp, brightness_f, transform)

    def _debounced_save(self):
        """去抖保存：延迟 500ms 写入"""
        with self._save_lock:
            if self._save_timer:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(0.5, self._do_save)
            self._save_timer.daemon = True
            self._save_timer.start()

    def _do_save(self):
        """实际执行保存 — 在 _save_lock 保护下完成快照和写入"""
        with self._save_lock:
            if self._cleaned_up:
                # 清理已完成，跳过保存（_cleanup 会负责最终写入）
                return
            snapshot = dict(self.settings)
        save_settings(snapshot)

    def _cleanup(self):
        """清理：恢复默认 gamma。带重入保护。"""
        with self._cleanup_lock:
            if self._cleaned_up:
                return
            self._cleaned_up = True

        # 取消并等待去抖保存完成，然后在锁内做最终写入
        with self._save_lock:
            if self._save_timer:
                self._save_timer.cancel()
                self._save_timer = None
            try:
                save_settings(self.settings)
            except Exception:
                logger.exception("清理时保存设置失败")

        try:
            shutdown_color_effect()
        except Exception:
            logger.exception("清理时重置颜色效果失败")
        try:
            reset_all_gamma(self.hdcs)
        except Exception:
            logger.exception("清理时重置 gamma 失败")
        try:
            release_monitors(self.monitors)
        except Exception:
            logger.exception("清理时释放显示器资源失败")

    # ─── 启动 ────────────────────────────────────────────────────────────────
    def run(self):
        self.tray.start()
        print("[护眼助手] 已启动，最小化到系统托盘")
        print("[护眼助手] 关闭窗口将最小化到托盘，退出请右键托盘图标 → 退出")
        self.app.mainloop()


def main():
    controller = EyeComfortController()
    controller.run()


if __name__ == "__main__":
    main()
