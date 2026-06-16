"""Gamma ramp 计算与应用

核心原理：通过操控显卡的 gamma 查找表 (LUT) 来改变所有像素的输出。
- 色温：调整 R/G/B 三通道的比例（低色温 = 减蓝增红绿）
- 亮度：整体缩放 gamma 曲线
- 黑白：均匀灰阶（色温不影响），三通道使用相同亮度值
- 反色：反转输入亮度后叠加色温色调
- 淡色：对比度压缩 + 固定暖色调，低饱和度柔和
- 多显示器一致性：构建一份 gamma ramp，同时应用到所有显示器
- 过渡取消：使用 generation counter 确保旧过渡线程可靠退出
"""
import ctypes
import ctypes.wintypes
import math
import threading
import time
from typing import Optional

from config import TEMP_MIN, TEMP_MAX, BRIGHTNESS_MIN, TRANSITION_MS, TRANSITION_STEPS

# ─── Windows API ──────────────────────────────────────────────────────────────
_gdi32 = ctypes.windll.gdi32

_set_gamma_ramp = _gdi32.SetDeviceGammaRamp
_set_gamma_ramp.argtypes = [ctypes.wintypes.HDC, ctypes.c_void_p]
_set_gamma_ramp.restype = ctypes.wintypes.BOOL

_get_gamma_ramp = _gdi32.GetDeviceGammaRamp
_get_gamma_ramp.argtypes = [ctypes.wintypes.HDC, ctypes.c_void_p]
_get_gamma_ramp.restype = ctypes.wintypes.BOOL

RAMP_SIZE = 256

# ─── 过渡管理 ────────────────────────────────────────────────────────────────
# 使用 generation counter 而非 Event 来取消旧过渡：
# - 每次 apply_gamma_smooth 递增 _generation
# - 过渡线程创建时捕获当前 generation
# - 每步检查 generation 是否变化，变化则退出
# - 主线程永不 sleep，消除 UI 卡顿
_generation = 0
_generation_lock = threading.Lock()


def _get_generation() -> int:
    with _generation_lock:
        return _generation


def _next_generation() -> int:
    with _generation_lock:
        global _generation
        _generation += 1
        return _generation


# ─── 色温 → RGB ──────────────────────────────────────────────────────────────
def kelvin_to_rgb(kelvin: int) -> tuple[float, float, float]:
    """将色温 (Kelvin) 转换为 [0,1] 归一化的 RGB 系数。

    基于 Tanner Helland 的近似算法。
    输入范围: 1000K ~ 40000K，超出范围自动夹持。
    """
    kelvin = max(1000, min(40000, kelvin))
    temp = kelvin / 100.0

    # Red
    if temp <= 66:
        r = 1.0
    else:
        r = temp - 60
        r = 329.698727446 * (r ** -0.1332047592)
        r = max(0.0, min(1.0, r / 255.0))

    # Green
    if temp <= 66:
        g = max(1.0, temp)  # 防止 temp=0 导致 log(0)
        g = 99.4708025861 * math.log(g) - 161.1195681661
    else:
        g = temp - 60
        g = 288.1221695283 * (g ** -0.0755148492)
    g = max(0.0, min(1.0, g / 255.0))

    # Blue
    if temp >= 66:
        b = 1.0
    elif temp <= 19:
        b = 0.0
    else:
        b = max(11.0, temp - 10)
        b = 138.5177312231 * math.log(b) - 305.0447927307
        b = max(0.0, min(1.0, b / 255.0))

    return r, g, b


# ─── Gamma Ramp 构建 ─────────────────────────────────────────────────────────
def _make_ramp_array():
    """创建 256*3 大小的 WORD 数组，用于 Windows API"""
    return (ctypes.c_uint16 * (RAMP_SIZE * 3))()


def build_gamma_ramp(temperature: int, brightness: float,
                     transform: str = "normal") -> ctypes.Array:
    """构建 gamma ramp。

    Args:
        temperature: 色温 (自动夹持到 TEMP_MIN~TEMP_MAX)
        brightness: 亮度系数 (自动夹持到 0.05~1.0，防止全黑)
        transform: 变换模式 — "normal" / "grayscale" / "invert" / "light"

    Returns:
        ctypes 数组，可直接传给 SetDeviceGammaRamp
    """
    temperature = max(TEMP_MIN, min(TEMP_MAX, temperature))
    brightness = max(BRIGHTNESS_MIN / 100.0, min(1.0, brightness))

    r_factor, g_factor, b_factor = kelvin_to_rgb(temperature)
    if transform == "light":
        lr, lg, lb = kelvin_to_rgb(6000)
        contrast = 0.65
    ramp = _make_ramp_array()

    for i in range(RAMP_SIZE):
        normalized = i / 255.0  # 0~1

        # ─── 变换 ────────────────────────────────────────────────────────
        if transform == "grayscale":
            # 灰度模式：基于亮度的均匀灰阶，色温不影响灰度输出
            gray = normalized * brightness
            r_val = g_val = b_val = gray

        elif transform == "invert":
            # 反色模式：反转输入亮度，再叠加色温色调
            inv = (1.0 - normalized) * brightness
            r_val = inv * r_factor
            g_val = inv * g_factor
            b_val = inv * b_factor

        elif transform == "light":
            # 淡色：对比度压缩 + 固定暖色调，低饱和度柔和效果
            soft = 0.5 + (normalized - 0.5) * contrast
            r_val = soft * lr * brightness
            g_val = soft * lg * brightness
            b_val = soft * lb * brightness

        else:
            # 正常模式：色温 + 亮度
            r_val = normalized * r_factor * brightness
            g_val = normalized * g_factor * brightness
            b_val = normalized * b_factor * brightness

        # 限制到 [0, 1]，映射到 16-bit
        ramp[i]                  = int(max(0.0, min(1.0, r_val)) * 65535)
        ramp[i + RAMP_SIZE]      = int(max(0.0, min(1.0, g_val)) * 65535)
        ramp[i + 2 * RAMP_SIZE]  = int(max(0.0, min(1.0, b_val)) * 65535)

    return ramp


def build_identity_ramp() -> ctypes.Array:
    """构建线性（恒等）gamma ramp — 直接生成，不依赖 kelvin_to_rgb。"""
    ramp = _make_ramp_array()
    for i in range(RAMP_SIZE):
        val = int(i / 255.0 * 65535)
        ramp[i]                  = val
        ramp[i + RAMP_SIZE]      = val
        ramp[i + 2 * RAMP_SIZE]  = val
    return ramp


# ─── Gamma Ramp 应用 ──────────────────────────────────────────────────────────
def _apply_gamma(hdc, ramp) -> bool:
    """将 gamma ramp 应用到指定显示器的 DC（内部使用）"""
    if not hdc:
        return False
    return bool(_set_gamma_ramp(hdc, ctypes.byref(ramp)))


def get_gamma_ramp(hdc) -> Optional[ctypes.Array]:
    """获取当前 gamma ramp"""
    if not hdc:
        return None
    ramp = _make_ramp_array()
    if _get_gamma_ramp(hdc, ctypes.byref(ramp)):
        return ramp
    return None


def apply_ramp_to_all(hdc_list: list, ramp) -> bool:
    """将同一份 gamma ramp 应用到所有显示器 — 保证多显示器一致性。"""
    ok = False
    for hdc in hdc_list:
        if _apply_gamma(hdc, ramp):
            ok = True
    return ok


def _stop_transition():
    """递增 generation counter，使正在运行的过渡线程在下一步自动退出。

    不阻塞调用线程，不依赖 Event 或 sleep。
    """
    _next_generation()


# ─── 平滑过渡 ────────────────────────────────────────────────────────────────
def _lerp_ramp(ramp_a, ramp_b, t: float) -> ctypes.Array:
    """在两个 gamma ramp 之间线性插值"""
    result = _make_ramp_array()
    for i in range(RAMP_SIZE * 3):
        val = int(ramp_a[i] + (ramp_b[i] - ramp_a[i]) * t)
        result[i] = max(0, min(65535, val))
    return result


def apply_gamma_smooth(hdc_list: list, temperature: int, brightness: float,
                       transform: str = "normal"):
    """平滑过渡到目标色温、亮度和变换模式。

    构建一份 gamma ramp，同时应用到所有显示器，确保多显示器效果一致。
    使用 generation counter 取消旧过渡，不在调用线程 sleep。
    """
    # 递增 generation，旧过渡线程将在下一步自动退出
    my_gen = _next_generation()

    target_ramp = build_gamma_ramp(temperature, brightness, transform)

    # 从主显示器获取当前 ramp 作为过渡起点
    current_ramp = None
    if hdc_list:
        current_ramp = get_gamma_ramp(hdc_list[0])
    if current_ramp is None:
        current_ramp = build_identity_ramp()

    def _transition():
        steps = TRANSITION_STEPS
        interval = TRANSITION_MS / steps / 1000.0

        for step in range(1, steps + 1):
            t = step / steps
            t_eased = t * t * (3 - 2 * t)  # ease-in-out

            interpolated = _lerp_ramp(current_ramp, target_ramp, t_eased)
            apply_ramp_to_all(hdc_list, interpolated)

            if step < steps:
                # 睡眠后、下一帧前检查 generation，确保新过渡能及时取消旧线程
                if _get_generation() != my_gen:
                    return
                time.sleep(interval)

        # 循环正常结束后，确保最终状态精确为目标 ramp（消除浮点误差）
        if _get_generation() == my_gen:
            apply_ramp_to_all(hdc_list, target_ramp)

    t = threading.Thread(target=_transition, daemon=True)
    t.start()


def apply_gamma_instant(hdc_list: list, temperature: int, brightness: float,
                        transform: str = "normal"):
    """立即应用色温、亮度和变换（无过渡动画）。

    构建一份 gamma ramp，同时应用到所有显示器。
    """
    _stop_transition()
    ramp = build_gamma_ramp(temperature, brightness, transform)
    apply_ramp_to_all(hdc_list, ramp)


def reset_all_gamma(hdc_list: list):
    """恢复所有显示器的默认 gamma。

    先停止正在进行的过渡，再应用 identity ramp。
    """
    _stop_transition()
    ramp = build_identity_ramp()
    apply_ramp_to_all(hdc_list, ramp)
