"""系统托盘图标和菜单"""
import threading
from typing import Callable, Optional

import pystray
from PIL import Image, ImageDraw

from config import PRESETS


def _create_icon_image(temp: int = 6500, size: int = 64) -> Image.Image:
    """动态生成托盘图标 — 渐变圆形，颜色反映当前色温。

    低色温 → 暖黄，高色温 → 白蓝。
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    temp = max(2700, min(6500, temp))
    t = (temp - 2700) / (6500 - 2700)  # 0~1

    # 暖色 → 冷色渐变
    r = int(255 - t * 80)
    g = int(175 + t * 40)
    b = int(55 + t * 200)

    center = size // 2
    radius = size // 2 - 5

    # 外圈柔光
    for i in range(radius + 6, radius, -1):
        alpha = int(50 * (1 - (i - radius) / 6))
        draw.ellipse(
            [center - i, center - i, center + i, center + i],
            fill=(r, g, b, alpha),
        )

    # 实心圆
    draw.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        fill=(r, g, b, 240),
    )

    # 内环高光
    inner = radius - 3
    draw.ellipse(
        [center - inner, center - inner, center + inner, center + inner],
        fill=(min(255, r + 20), min(255, g + 20), min(255, b + 20), 60),
    )

    # 中心高光点
    hl = radius // 3
    draw.ellipse(
        [center - hl - 2, center - hl - 4,
         center + hl - 2, center + hl - 4],
        fill=(min(255, r + 70), min(255, g + 70), min(255, b + 70), 100),
    )

    return img


class TrayIcon:
    """系统托盘管理"""

    def __init__(self,
                 on_preset: Optional[Callable[[str], None]] = None,
                 on_show_window: Optional[Callable[[], None]] = None,
                 on_quit: Optional[Callable[[], None]] = None):
        self._on_preset = on_preset
        self._on_show_window = on_show_window
        self._on_quit = on_quit

        self._icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None
        self._current_temp = 6500

    def update_icon(self, temperature: int):
        """根据色温更新托盘图标颜色（应从 Tk 主线程调用）"""
        self._current_temp = temperature
        if self._icon:
            try:
                self._icon.icon = _create_icon_image(temperature)
            except Exception:
                # 图标更新失败（如 shutdown 阶段 Tcl 已销毁），忽略
                pass

    def _build_menu(self) -> pystray.Menu:
        items = []

        # 预设子菜单
        for key, preset in PRESETS.items():
            items.append(
                pystray.MenuItem(
                    preset["name"],
                    lambda _, k=key: self._on_preset(k) if self._on_preset else None,
                )
            )

        items.append(pystray.Menu.SEPARATOR)
        items.append(
            pystray.MenuItem(
                "显示主窗口",
                lambda *_: self._on_show_window() if self._on_show_window else None,
                default=True,
            )
        )
        items.append(pystray.Menu.SEPARATOR)
        items.append(
            pystray.MenuItem(
                "退出",
                lambda *_: self._quit(),
            )
        )

        return pystray.Menu(*items)

    def _quit(self):
        """退出应用"""
        if self._on_quit:
            self._on_quit()

    def start(self):
        """在后台线程中启动托盘图标"""
        self._icon = pystray.Icon(
            "EyeComfort",
            _create_icon_image(self._current_temp),
            "护眼助手",
            menu=self._build_menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        """停止托盘图标"""
        if self._icon:
            self._icon.stop()
            self._icon = None

    @property
    def is_running(self) -> bool:
        return self._icon is not None
