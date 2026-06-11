"""多显示器枚举

通过 Windows API 枚举所有连接的显示器，
并为每个显示器获取可用于 SetDeviceGammaRamp 的 HDC。
"""
import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from typing import Optional

# ─── Windows API 类型 ─────────────────────────────────────────────────────────
_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32

# MONITORINFOEXW 结构体（ctypes.wintypes 不提供，需手动定义）
CCHDEVICENAME = 32


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.DWORD),
        ("rcMonitor", ctypes.wintypes.RECT),
        ("rcWork", ctypes.wintypes.RECT),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szDevice", ctypes.wintypes.WCHAR * CCHDEVICENAME),
    ]


MONITORINFOF_PRIMARY = 0x00000001

# 回调函数类型
MONITORENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL,
    ctypes.wintypes.HDC,       # hMonitor
    ctypes.wintypes.HDC,       # hdcMonitor
    ctypes.POINTER(ctypes.wintypes.RECT),  # lprcMonitor
    ctypes.wintypes.LPARAM,    # dwData
)

# 锚定回调，防止 GC 回收（虽然 EnumDisplayMonitors 是同步的，
# 但存储在模块级可以防御性地防止极端 GC 场景下的回收）
_enum_callback_ref = None


@dataclass
class MonitorInfo:
    """显示器信息"""
    hdc: ctypes.wintypes.HDC   # 显示器 DC，用于 gamma ramp
    name: str                   # 显示器名称 (\\\\.\\DISPLAY1 等)
    rect: tuple                 # (left, top, right, bottom)
    is_primary: bool            # 是否为主显示器
    width: int                  # 像素宽度
    height: int                 # 像素高度
    is_created_dc: bool = True  # True=CreateDCW 创建 (用 DeleteDC)，
                                # False=GetDC 获取 (用 ReleaseDC)


def enumerate_monitors() -> list[MonitorInfo]:
    """枚举所有已连接的显示器。

    Returns:
        MonitorInfo 列表，包含每个显示器的 HDC 和位置信息。
        HDC 可直接用于 SetDeviceGammaRamp。
    """
    global _enum_callback_ref
    monitors = []

    def _callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        info = MONITORINFOEXW()
        info.cbSize = ctypes.sizeof(info)

        # 获取显示器信息
        if _user32.GetMonitorInfoW(hMonitor, ctypes.byref(info)):
            name = info.szDevice
            is_primary = bool(info.dwFlags & MONITORINFOF_PRIMARY)
        else:
            name = f"\\\\.\\DISPLAY{len(monitors) + 1}"
            is_primary = len(monitors) == 0

        # 用显示器设备名创建 DC，gamma ramp 会应用到该显示器的显卡适配器
        monitor_dc = _gdi32.CreateDCW(name, name, None, None)

        if not monitor_dc:
            # CreateDCW 失败（返回 NULL），跳过此显示器
            return True  # 继续枚举

        monitor = MonitorInfo(
            hdc=monitor_dc,
            name=name,
            rect=(rect.left, rect.top, rect.right, rect.bottom),
            is_primary=is_primary,
            width=rect.right - rect.left,
            height=rect.bottom - rect.top,
            is_created_dc=True,
        )
        monitors.append(monitor)
        return True  # 继续枚举

    # 存储回调引用，防止 GC 回收
    callback = MONITORENUMPROC(_callback)
    _enum_callback_ref = callback
    _user32.EnumDisplayMonitors(None, None, callback, 0)
    _enum_callback_ref = None

    # 如果没枚举到任何显示器，使用桌面 DC 作为回退
    if not monitors:
        hdc = _user32.GetDC(None)
        if hdc:
            monitors.append(MonitorInfo(
                hdc=hdc,
                name="\\\\.\\DISPLAY1",
                rect=(0, 0, 0, 0),
                is_primary=True,
                width=0,
                height=0,
                is_created_dc=False,  # GetDC 获取，需要用 ReleaseDC 释放
            ))

    return monitors


def release_monitors(monitors: list[MonitorInfo]):
    """释放所有显示器的 DC 资源。

    根据 DC 来源使用正确的释放方式：
    - CreateDCW 创建的 DC → DeleteDC
    - GetDC 获取的 DC → ReleaseDC
    释放后清零 hdc，防止悬垂句柄被误用。
    """
    for m in monitors:
        if m.hdc:
            if m.is_created_dc:
                _gdi32.DeleteDC(m.hdc)
            else:
                _user32.ReleaseDC(None, m.hdc)
            m.hdc = 0  # 释放后清零，防止悬垂句柄


def get_monitor_hdcs(monitors: list[MonitorInfo]) -> list:
    """提取所有显示器的 HDC 列表"""
    return [m.hdc for m in monitors]
