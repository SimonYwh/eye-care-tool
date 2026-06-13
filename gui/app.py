"""主窗口 GUI — CustomTkinter 实现"""
import customtkinter as ctk
from typing import Callable, Optional

from config import (
    PRESETS, TEMP_MIN, TEMP_MAX, TEMP_DEFAULT,
    BRIGHTNESS_MIN, BRIGHTNESS_MAX, BRIGHTNESS_DEFAULT,
    TRANSFORMS, TRANSFORM_DEFAULT,
)


class EyeComfortApp(ctk.CTk):
    """护眼软件主窗口"""

    # 变换模式按钮配色 — (默认色, 高亮色)
    _TRANSFORM_COLORS = {
        "normal":    ("#2d5a3d", "#3a7a5a"),    # 绿色调 — 正常
        "grayscale": ("#4a4a4a", "#666666"),     # 灰色 — 黑白
        "invert":    ("#2a2a2a", "#404040"),     # 深灰色 — 反色
        "light":     ("#6b4a5a", "#8b6a7a"),     # 粉紫色 — 淡色
    }
    _TRANSFORM_COLOR_DEFAULT = ("#3d3d3d", "#555555")

    def __init__(self,
                 on_temp_change: Optional[Callable[[int], None]] = None,
                 on_brightness_change: Optional[Callable[[int], None]] = None,
                 on_preset: Optional[Callable[[str], None]] = None,
                 on_transform_change: Optional[Callable[[str], None]] = None,
                 on_reset: Optional[Callable[[], None]] = None,
                 on_close: Optional[Callable[[], None]] = None):
        super().__init__()

        self._on_temp_change = on_temp_change
        self._on_brightness_change = on_brightness_change
        self._on_preset = on_preset
        self._on_transform_change = on_transform_change
        self._on_reset = on_reset
        self._on_close = on_close

        self._current_temp = TEMP_DEFAULT
        self._current_brightness = BRIGHTNESS_DEFAULT
        self._current_transform = TRANSFORM_DEFAULT
        self._suppress_callbacks = False

        self._setup_window()
        self._build_ui()

    # ─── 窗口设置 ────────────────────────────────────────────────────────────
    def _setup_window(self):
        self.title("👁 护眼助手")
        self.geometry("480x620")
        self.resizable(False, False)
        self.configure(fg_color="#1a1a2e")

        self.update_idletasks()
        w, h = 480, 620
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _on_window_close(self):
        if self._on_close:
            self._on_close()
        else:
            self.withdraw()

    def _build_ui(self):
        # ─── 标题 ────────────────────────────────────────────────────────────
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            title_frame,
            text="👁 护眼助手",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#e0e0e0",
        ).pack(side="left")

        self._status_label = ctk.CTkLabel(
            title_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#888888",
        )
        self._status_label.pack(side="right")

        # ─── 预设按钮 ────────────────────────────────────────────────────────
        preset_frame = ctk.CTkFrame(self, fg_color="transparent")
        preset_frame.pack(fill="x", padx=20, pady=(8, 4))

        self._preset_buttons = {}
        preset_colors = {
            "night": "#3a2d6b",
            "eye":   "#1b5e4b",
            "day":   "#4a6fa5",
            "reset": "#3d3d3d",
        }
        for key, preset in PRESETS.items():
            btn = ctk.CTkButton(
                preset_frame,
                text=preset["name"],
                font=ctk.CTkFont(size=12),
                fg_color=preset_colors.get(key, "#3d3d3d"),
                hover_color=preset_colors.get(key, "#3d3d3d"),
                corner_radius=8,
                height=36,
                command=lambda k=key: self._on_preset_click(k),
            )
            btn.pack(side="left", expand=True, fill="x", padx=2)
            self._preset_buttons[key] = btn

        # ─── 变换模式按钮 ───────────────────────────────────────────────────
        transform_frame = ctk.CTkFrame(self, fg_color="transparent")
        transform_frame.pack(fill="x", padx=20, pady=(4, 4))

        self._transform_buttons = {}
        for key, tf in TRANSFORMS.items():
            fg, hover = self._TRANSFORM_COLORS.get(key, self._TRANSFORM_COLOR_DEFAULT)
            btn = ctk.CTkButton(
                transform_frame,
                text=tf["name"],
                font=ctk.CTkFont(size=12),
                fg_color=fg,
                hover_color=hover,
                corner_radius=8,
                height=32,
                command=lambda k=key: self._on_transform_click(k),
            )
            btn.pack(side="left", expand=True, fill="x", padx=2)
            self._transform_buttons[key] = btn

        # ─── 分隔线 ──────────────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="#2a2a3e", height=1).pack(
            fill="x", padx=20, pady=10)

        # ─── 色温控制 ────────────────────────────────────────────────────────
        temp_frame = ctk.CTkFrame(self, fg_color="transparent")
        temp_frame.pack(fill="x", padx=20, pady=(0, 8))

        temp_header = ctk.CTkFrame(temp_frame, fg_color="transparent")
        temp_header.pack(fill="x")

        ctk.CTkLabel(
            temp_header,
            text="🎨 色温",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e0e0e0",
        ).pack(side="left")

        self._temp_value_label = ctk.CTkLabel(
            temp_header,
            text=f"{TEMP_DEFAULT}K",
            font=ctk.CTkFont(size=14),
            text_color="#ffaa44",
        )
        self._temp_value_label.pack(side="right")

        self._temp_slider = ctk.CTkSlider(
            temp_frame,
            from_=TEMP_MIN,
            to=TEMP_MAX,
            number_of_steps=(TEMP_MAX - TEMP_MIN) // 100,
            command=self._on_temp_slider,
            fg_color="#2a2a3e",
            progress_color="#ffaa44",
            button_color="#ffaa44",
            button_hover_color="#ff8800",
            height=18,
        )
        self._temp_slider.set(TEMP_DEFAULT)
        self._temp_slider.pack(fill="x", pady=(6, 0))

        temp_marks = ctk.CTkFrame(temp_frame, fg_color="transparent")
        temp_marks.pack(fill="x")
        ctk.CTkLabel(temp_marks, text="暖色 2700K",
                     font=ctk.CTkFont(size=10), text_color="#666666").pack(side="left")
        ctk.CTkLabel(temp_marks, text="6500K 冷色",
                     font=ctk.CTkFont(size=10), text_color="#666666").pack(side="right")

        # ─── 亮度控制 ────────────────────────────────────────────────────────
        bright_frame = ctk.CTkFrame(self, fg_color="transparent")
        bright_frame.pack(fill="x", padx=20, pady=(4, 8))

        bright_header = ctk.CTkFrame(bright_frame, fg_color="transparent")
        bright_header.pack(fill="x")

        ctk.CTkLabel(
            bright_header,
            text="☀️ 亮度",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e0e0e0",
        ).pack(side="left")

        self._brightness_value_label = ctk.CTkLabel(
            bright_header,
            text=f"{BRIGHTNESS_DEFAULT}%",
            font=ctk.CTkFont(size=14),
            text_color="#66bbff",
        )
        self._brightness_value_label.pack(side="right")

        self._brightness_slider = ctk.CTkSlider(
            bright_frame,
            from_=BRIGHTNESS_MIN,
            to=BRIGHTNESS_MAX,
            number_of_steps=(BRIGHTNESS_MAX - BRIGHTNESS_MIN) // 5,
            command=self._on_brightness_slider,
            fg_color="#2a2a3e",
            progress_color="#66bbff",
            button_color="#66bbff",
            button_hover_color="#3399ff",
            height=18,
        )
        self._brightness_slider.set(BRIGHTNESS_DEFAULT)
        self._brightness_slider.pack(fill="x", pady=(6, 0))

        bright_marks = ctk.CTkFrame(bright_frame, fg_color="transparent")
        bright_marks.pack(fill="x")
        ctk.CTkLabel(bright_marks, text="暗 10%",
                     font=ctk.CTkFont(size=10), text_color="#666666").pack(side="left")
        ctk.CTkLabel(bright_marks, text="100% 亮",
                     font=ctk.CTkFont(size=10), text_color="#666666").pack(side="right")

        # ─── 分隔线 ──────────────────────────────────────────────────────────
        ctk.CTkFrame(self, fg_color="#2a2a3e", height=1).pack(
            fill="x", padx=20, pady=8)

        # ─── 显示器列表 + 一致性说明 ─────────────────────────────────────────
        self._monitors_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._monitors_frame.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(
            self._monitors_frame,
            text="🖥 显示器 (效果已统一)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e0e0e0",
        ).pack(anchor="w")

        self._monitors_label = ctk.CTkLabel(
            self._monitors_frame,
            text="检测中...",
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            wraplength=400,
            justify="left",
        )
        self._monitors_label.pack(anchor="w", pady=(2, 0))

        # ─── 底部按钮 ────────────────────────────────────────────────────────
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=20, pady=(4, 16))

        ctk.CTkButton(
            bottom_frame,
            text="🔄 恢复默认",
            font=ctk.CTkFont(size=12),
            fg_color="#444455",
            hover_color="#555566",
            corner_radius=8,
            height=34,
            command=self._on_reset_click,
        ).pack(side="left")

        ctk.CTkButton(
            bottom_frame,
            text="最小化到托盘",
            font=ctk.CTkFont(size=12),
            fg_color="#444455",
            hover_color="#555566",
            corner_radius=8,
            height=34,
            command=self._on_window_close,
        ).pack(side="right")

    # ─── 事件处理 ────────────────────────────────────────────────────────────
    def _on_preset_click(self, preset_key: str):
        preset = PRESETS[preset_key]
        if self._on_preset:
            self._on_preset(preset_key)

    def _on_reset_click(self):
        """恢复默认：通过 controller 原子重置（避免双重 gamma 过渡）"""
        if self._on_reset:
            self._on_reset()

    def _on_transform_click(self, transform_key: str):
        self._current_transform = transform_key
        self._update_transform_highlight(transform_key)
        self._update_slider_state(transform_key)
        name = TRANSFORMS[transform_key]["name"]
        self._update_status(name)
        if self._on_transform_change:
            self._on_transform_change(transform_key)

    def _update_transform_highlight(self, active_key: str):
        """高亮当前选中的变换按钮"""
        for key, btn in self._transform_buttons.items():
            fg, hover = self._TRANSFORM_COLORS.get(key, self._TRANSFORM_COLOR_DEFAULT)
            if key == active_key:
                btn.configure(fg_color=hover)  # 选中状态用亮色
            else:
                btn.configure(fg_color=fg)     # 未选中用暗色

    def _update_slider_state(self, transform_key: str):
        """非 normal 模式下禁用色温滑块（这些模式忽略色温设置）"""
        is_normal = (transform_key == "normal")
        state = "normal" if is_normal else "disabled"
        self._temp_slider.configure(state=state)

    def _on_temp_slider(self, value: float):
        if self._suppress_callbacks:
            return
        temp = int(round(value / 100) * 100)
        temp = max(TEMP_MIN, min(TEMP_MAX, temp))  # 夹持到有效范围
        self._current_temp = temp
        self._temp_value_label.configure(text=f"{temp}K")
        self._update_status("自定义")
        if self._on_temp_change:
            self._on_temp_change(temp)

    def _on_brightness_slider(self, value: float):
        if self._suppress_callbacks:
            return
        brightness = int(round(value))
        self._current_brightness = brightness
        self._brightness_value_label.configure(text=f"{brightness}%")
        self._update_status("自定义")
        if self._on_brightness_change:
            self._on_brightness_change(brightness)

    # ─── 公共接口 ────────────────────────────────────────────────────────────
    def set_values(self, temp: int, brightness: int, label: str = ""):
        """更新滑块和标签"""
        self._current_temp = temp
        self._current_brightness = brightness
        self._suppress_callbacks = True
        try:
            self._temp_slider.set(temp)
            self._brightness_slider.set(brightness)
        finally:
            self._suppress_callbacks = False
        self._temp_value_label.configure(text=f"{temp}K")
        self._brightness_value_label.configure(text=f"{brightness}%")
        if label:
            self._update_status(label)

    def set_transform(self, transform_key: str):
        """设置当前变换模式（由外部调用，如托盘菜单）"""
        self._current_transform = transform_key
        self._update_transform_highlight(transform_key)
        self._update_slider_state(transform_key)
        name = TRANSFORMS.get(transform_key, {}).get("name", "")
        if name:
            self._update_status(name)

    def set_monitors_info(self, monitors: list):
        """更新显示器列表显示"""
        lines = []
        for i, m in enumerate(monitors):
            primary = " [主]" if m.is_primary else ""
            lines.append(f"  - {m.name} ({m.width}x{m.height}){primary}")
        if len(monitors) > 1:
            lines.append("  -> 所有屏幕使用同一色彩配置")
        self._monitors_label.configure(text="\n".join(lines) if lines else "未检测到显示器")

    def _update_status(self, text: str):
        self._status_label.configure(text=text)
