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

    # 夹持温度到有效范围，防止图标颜色异常
    temp = max(2700, min(6500, temp))
    # 根据色温计算颜色
    # 2700K → 暖橙 (255, 170, 50)
    # 6500K → 浅蓝白 (180, 210, 255)
    t = (temp - 2700) / (6500 - 2700)  # 0~1
    r = int(255 - t * 75)
    g = int(170 + t * 40)
    b = int(50 + t * 205)

    center = size // 2
    radius = size // 2 - 4

    # 外圈光晕
    for i in range(radius + 4, radius - 1, -1):
        alpha = int(80 * (1 - (i - radius + 1) / 5))
        draw.ellipse(
            [center - i, center - i, center + i, center + i],
            fill=(r, g, b, alpha),
        )

    # 实心圆
    draw.ellipse(
        [center - radius, center - radius, center + radius, center + radius],
        fill=(r, g, b, 255),
    )

    # 中心高光
    highlight_r = radius // 3
    draw.ellipse(
        [center - highlight_r - 2, center - highlight_r - 4,
         center + highlight_r - 2, center + highlight_r - 4],
        fill=(min(255, r + 60), min(255, g + 60), min(255, b + 60), 120),
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
        """根据色温更新托盘图标颜色"""
        self._current_temp = temperature
        if self._icon:
            self._icon.icon = _create_icon_image(temperature)

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
