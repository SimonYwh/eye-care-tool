"""Windows Magnification color effects."""
import ctypes
from ctypes import wintypes

from config import TRANSFORM_DEFAULT

_mag = ctypes.windll.LoadLibrary("Magnification.dll")

ColorMatrix = ctypes.c_float * 25

_mag.MagInitialize.argtypes = []
_mag.MagInitialize.restype = wintypes.BOOL
_mag.MagUninitialize.argtypes = []
_mag.MagUninitialize.restype = wintypes.BOOL
_mag.MagSetFullscreenColorEffect.argtypes = [ctypes.POINTER(ColorMatrix)]
_mag.MagSetFullscreenColorEffect.restype = wintypes.BOOL

_initialized = False

_IDENTITY = ColorMatrix(
    1, 0, 0, 0, 0,
    0, 1, 0, 0, 0,
    0, 0, 1, 0, 0,
    0, 0, 0, 1, 0,
    0, 0, 0, 0, 1,
)

_GRAYSCALE = ColorMatrix(
    0.2126, 0.2126, 0.2126, 0, 0,
    0.7152, 0.7152, 0.7152, 0, 0,
    0.0722, 0.0722, 0.0722, 0, 0,
    0,      0,      0,      1, 0,
    0,      0,      0,      0, 1,
)

_INVERT = ColorMatrix(
    -1,  0,  0, 0, 0,
     0, -1,  0, 0, 0,
     0,  0, -1, 0, 0,
     0,  0,  0, 1, 0,
     1,  1,  1, 0, 1,
)

_LIGHT = ColorMatrix(
    0.58, 0,    0,    0, 0,
    0,    0.58, 0,    0, 0,
    0,    0,    0.58, 0, 0,
    0,    0,    0,    1, 0,
    0.21, 0.21, 0.21, 0, 1,
)

_MATRICES = {
    TRANSFORM_DEFAULT: _IDENTITY,
    "grayscale": _GRAYSCALE,
    "invert": _INVERT,
    "light": _LIGHT,
}


def apply_color_effect(transform: str) -> bool:
    global _initialized
    if not _initialized:
        _initialized = bool(_mag.MagInitialize())
    if not _initialized:
        return False

    matrix = _MATRICES.get(transform, _IDENTITY)
    return bool(_mag.MagSetFullscreenColorEffect(ctypes.byref(matrix)))


def reset_color_effect():
    if _initialized:
        _mag.MagSetFullscreenColorEffect(ctypes.byref(_IDENTITY))


def shutdown_color_effect():
    global _initialized
    if _initialized:
        reset_color_effect()
        _mag.MagUninitialize()
        _initialized = False
