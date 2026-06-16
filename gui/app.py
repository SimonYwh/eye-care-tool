"""主窗口 GUI — CustomTkinter 实现"""
import customtkinter as ctk
from typing import Callable, Optional

from config import (
    PRESETS, TEMP_MIN, TEMP_MAX, TEMP_DEFAULT,
    BRIGHTNESS_MIN, BRIGHTNESS_MAX, BRIGHTNESS_DEFAULT,
    TRANSFORMS, TRANSFORM_DEFAULT,
)

# ─── 设计规范 ───────────────────────────────────────────────────────────────
_BG           = "#0f1117"   # 主背景
_CARD         = "#1a1d27"   # 卡片背景
_BORDER       = "#2a2e3a"   # 边框/分隔线
_TEXT         = "#e8eaed"   # 主文字
_TEXT_SEC     = "#9aa0b0"   # 次要文字
_TEXT_MUTED   = "#5f6577"   # 辅助文字
_STYLE_DEFAULT = ("#2a2d35", "#3a3d48", "#4a4d58")  # 通用按钮默认样式

# 预设按钮配色：(背景, 悬停, 选中)
_PRESET_STYLE = {
    "night": ("#2a1f5e", "#3a2f7e", "#4a3f9e"),
    "eye":   ("#1a4a3a", "#2a6a5a", "#3a8a7a"),
    "day":   ("#2a4570", "#3a5a90", "#4a70b0"),
    "reset": ("#2a2d35", "#3a3d48", "#4a4d58"),
}

# 变换按钮配色：(背景, 悬停, 选中)
_TRANSFORM_STYLE = {
    "normal":    ("#1e3a2e", "#2a5a42", "#3a7a5a"),
    "grayscale": ("#303038", "#484850", "#606068"),
    "invert":    ("#3a2a4a", "#5a3a6a", "#7a5a8a"),
    "light":     ("#3a2a3a", "#5a4a5a", "#7a6a7a"),
}


class EyeComfortApp(ctk.CTk):
    """护眼软件主窗口"""

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
        self.title("护眼助手")
        self.geometry("440x590")
        self.resizable(False, False)
        self.configure(fg_color=_BG)

        self.update_idletasks()
        w, h = 440, 590
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.protocol("WM_DELETE_WINDOW", self._on_window_close)

    def _on_window_close(self):
        if self._on_close:
            self._on_close()
        else:
            self.withdraw()

    # ─── 辅助方法 ────────────────────────────────────────────────────────────
    @staticmethod
    def _make_card(parent, pady=6, inner_padx=16, inner_pady=10):
        """创建卡片容器：外层圆角卡片 + 内层透明面板。返回 (card, inner)。"""
        card = ctk.CTkFrame(parent, fg_color=_CARD, corner_radius=12)
        card.pack(fill="x", padx=16, pady=pady)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=inner_padx, pady=inner_pady)
        return card, inner

    @staticmethod
    def _update_button_highlight(buttons, style_map, active_key):
        """通用按钮高亮：选中用 active 色，未选用 bg 色。"""
        for key, btn in buttons.items():
            bg, _hover, active = style_map.get(key, _STYLE_DEFAULT)
            btn.configure(fg_color=active if key == active_key else bg)

    def _update_transform_ui(self, transform_key: str):
        self._current_transform = transform_key
        self._update_button_highlight(self._transform_buttons,
                                      _TRANSFORM_STYLE, transform_key)
        self._update_slider_state(transform_key)
        self._update_preset_highlight()

    def _update_slider_state(self, transform_key: str):
        uses_temp = TRANSFORMS.get(transform_key, {}).get("uses_temp")
        state = "normal" if uses_temp else "disabled"
        self._temp_slider.configure(state=state)

    def _update_preset_highlight(self):
        active_key = None
        if self._current_transform == TRANSFORM_DEFAULT:
            for key, preset in PRESETS.items():
                if (preset["temp"] == self._current_temp
                        and preset["brightness"] == self._current_brightness):
                    active_key = key
                    break
        self._update_button_highlight(self._preset_buttons, _PRESET_STYLE, active_key)

    # ─── 界面构建 ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ─── 标题栏 ──────────────────────────────────────────────────────────
        _, title_inner = self._make_card(self, pady=(12, 6), inner_padx=16, inner_pady=12)

        ctk.CTkLabel(
            title_inner,
            text="护眼助手",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        self._status_label = ctk.CTkLabel(
            title_inner,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=_TEXT_MUTED,
        )
        self._status_label.pack(side="right")

        # ─── 预设按钮 ────────────────────────────────────────────────────────
        _, preset_inner = self._make_card(self)

        self._preset_buttons = {}
        for key, preset in PRESETS.items():
            bg, hover, _active = _PRESET_STYLE.get(key, _STYLE_DEFAULT)
            btn = ctk.CTkButton(
                preset_inner,
                text=preset["name"],
                font=ctk.CTkFont(size=12),
                fg_color=bg,
                hover_color=hover,
                corner_radius=8,
                height=34,
                command=lambda k=key: self._on_preset_click(k),
            )
            btn.pack(side="left", expand=True, fill="x", padx=3)
            self._preset_buttons[key] = btn

        # ─── 变换模式 ────────────────────────────────────────────────────────
        _, transform_inner = self._make_card(self)

        ctk.CTkLabel(
            transform_inner,
            text="色彩模式",
            font=ctk.CTkFont(size=12),
            text_color=_TEXT_SEC,
        ).pack(side="left", padx=(0, 10))

        self._transform_buttons = {}
        for key, tf in TRANSFORMS.items():
            bg, hover, _active = _TRANSFORM_STYLE.get(key, _STYLE_DEFAULT)
            btn = ctk.CTkButton(
                transform_inner,
                text=tf["name"],
                font=ctk.CTkFont(size=12),
                fg_color=bg,
                hover_color=hover,
                corner_radius=8,
                height=32,
                command=lambda k=key: self._on_transform_click(k),
            )
            btn.pack(side="left", expand=True, fill="x", padx=3)
            self._transform_buttons[key] = btn

        # ─── 色温控制 ────────────────────────────────────────────────────────
        _, temp_inner = self._make_card(self, inner_padx=16, inner_pady=(12, 6))

        temp_header = ctk.CTkFrame(temp_inner, fg_color="transparent")
        temp_header.pack(fill="x")

        ctk.CTkLabel(
            temp_header,
            text="色温",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        self._temp_value_label = ctk.CTkLabel(
            temp_header,
            text=f"{TEMP_DEFAULT}K",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ffb347",
        )
        self._temp_value_label.pack(side="right")

        self._temp_slider = ctk.CTkSlider(
            temp_inner,
            from_=TEMP_MIN,
            to=TEMP_MAX,
            number_of_steps=(TEMP_MAX - TEMP_MIN) // 100,
            command=self._on_temp_slider,
            fg_color=_BORDER,
            progress_color="#ffb347",
            button_color="#ffb347",
            button_hover_color="#ffa020",
            height=16,
        )
        self._temp_slider.set(TEMP_DEFAULT)
        self._temp_slider.pack(fill="x", pady=(8, 0))

        self._build_slider_marks(temp_inner, "2700K", "暖色", "冷色", "6500K")

        # ─── 亮度控制 ────────────────────────────────────────────────────────
        _, bright_inner = self._make_card(self, inner_padx=16, inner_pady=(12, 6))

        bright_header = ctk.CTkFrame(bright_inner, fg_color="transparent")
        bright_header.pack(fill="x")

        ctk.CTkLabel(
            bright_header,
            text="亮度",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_TEXT,
        ).pack(side="left")

        self._brightness_value_label = ctk.CTkLabel(
            bright_header,
            text=f"{BRIGHTNESS_DEFAULT}%",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#6ec6ff",
        )
        self._brightness_value_label.pack(side="right")

        self._brightness_slider = ctk.CTkSlider(
            bright_inner,
            from_=BRIGHTNESS_MIN,
            to=BRIGHTNESS_MAX,
            number_of_steps=(BRIGHTNESS_MAX - BRIGHTNESS_MIN) // 5,
            command=self._on_brightness_slider,
            fg_color=_BORDER,
            progress_color="#6ec6ff",
            button_color="#6ec6ff",
            button_hover_color="#40a0e0",
            height=16,
        )
        self._brightness_slider.set(BRIGHTNESS_DEFAULT)
        self._brightness_slider.pack(fill="x", pady=(8, 0))

        self._build_slider_marks(bright_inner, "10%", "暗", "亮", "100%")

        # ─── 显示器信息 ──────────────────────────────────────────────────────
        _, monitor_inner = self._make_card(self)

        ctk.CTkLabel(
            monitor_inner,
            text="显示器",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_TEXT,
        ).pack(anchor="w")

        self._monitors_label = ctk.CTkLabel(
            monitor_inner,
            text="检测中...",
            font=ctk.CTkFont(size=11),
            text_color=_TEXT_SEC,
            wraplength=400,
            justify="left",
        )
        self._monitors_label.pack(anchor="w", pady=(4, 0))

        # ─── 底部按钮 ────────────────────────────────────────────────────────
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=16, pady=(8, 14))

        ctk.CTkButton(
            bottom_frame,
            text="恢复默认",
            font=ctk.CTkFont(size=12),
            fg_color="#2a2d35",
            hover_color="#3a3d48",
            border_width=1,
            border_color=_BORDER,
            corner_radius=8,
            height=36,
            width=130,
            command=self._on_reset_click,
        ).pack(side="left")

        ctk.CTkButton(
            bottom_frame,
            text="最小化到托盘",
            font=ctk.CTkFont(size=12),
            fg_color="#1e3a5e",
            hover_color="#2a5080",
            corner_radius=8,
            height=36,
            width=130,
            command=self._on_window_close,
        ).pack(side="right")

    @staticmethod
    def _build_slider_marks(parent, min_text, label_left, label_right, max_text):
        """在滑块下方添加刻度标注。"""
        marks = ctk.CTkFrame(parent, fg_color="transparent")
        marks.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(marks, text=min_text,
                     font=ctk.CTkFont(size=10), text_color=_TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(marks, text=label_left,
                     font=ctk.CTkFont(size=10), text_color=_TEXT_MUTED).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(marks, text=label_right,
                     font=ctk.CTkFont(size=10), text_color=_TEXT_MUTED).pack(side="right", padx=(0, 4))
        ctk.CTkLabel(marks, text=max_text,
                     font=ctk.CTkFont(size=10), text_color=_TEXT_MUTED).pack(side="right")

    # ─── 事件处理 ────────────────────────────────────────────────────────────
    def _on_preset_click(self, preset_key: str):
        if self._on_preset:
            self._on_preset(preset_key)

    def _on_reset_click(self):
        """恢复默认：通过 controller 原子重置（避免双重 gamma 过渡）"""
        if self._on_reset:
            self._on_reset()

    def _on_transform_click(self, transform_key: str):
        self._update_transform_ui(transform_key)
        name = TRANSFORMS[transform_key]["name"]
        self._update_status(name)
        if self._on_transform_change:
            self._on_transform_change(transform_key)

    def _on_temp_slider(self, value: float):
        if self._suppress_callbacks:
            return
        temp = int(round(value / 100) * 100)
        temp = max(TEMP_MIN, min(TEMP_MAX, temp))
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
        self._update_preset_highlight()

    def set_transform(self, transform_key: str):
        """设置当前变换模式（由外部调用，如托盘菜单）"""
        self._update_transform_ui(transform_key)
        name = TRANSFORMS.get(transform_key, {}).get("name", "")
        if name:
            self._update_status(name)

    def set_monitors_info(self, monitors: list):
        """更新显示器列表显示"""
        lines = []
        for i, m in enumerate(monitors):
            primary = " [主]" if m.is_primary else ""
            lines.append(f"  {m.name} ({m.width}x{m.height}){primary}")
        if len(monitors) > 1:
            lines.append("  所有屏幕使用统一色彩配置")
        self._monitors_label.configure(text="\n".join(lines) if lines else "未检测到显示器")

    def _update_status(self, text: str):
        self._status_label.configure(text=text)
