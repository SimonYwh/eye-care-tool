"""应用配置和预设管理"""
import json
import os
import tempfile
from pathlib import Path

# ─── 预设定义 ───────────────────────────────────────────────────────────────
PRESETS = {
    "night": {"name": "🌙 夜间", "temp": 3400, "brightness": 70},
    "eye":   {"name": "👁 护眼", "temp": 4500, "brightness": 85},
    "day":   {"name": "🌤 日间", "temp": 5500, "brightness": 90},
    "reset": {"name": "☀️ 原始", "temp": 6500, "brightness": 100},
}

# ─── 色温范围 ───────────────────────────────────────────────────────────────
TEMP_MIN = 2700
TEMP_MAX = 6500
TEMP_DEFAULT = 5500        # 开机默认微微护眼

# ─── 亮度范围 ───────────────────────────────────────────────────────────────
BRIGHTNESS_MIN = 10
BRIGHTNESS_MAX = 100
BRIGHTNESS_DEFAULT = 90    # 开机默认亮度 90%

# ─── 变换模式 ───────────────────────────────────────────────────────────────
TRANSFORMS = {
    "normal":   {"name": "🌈 正常", "desc": "标准色彩"},
    "grayscale": {"name": "🔘 黑白", "desc": "灰度模式"},
    "invert":    {"name": "🔄 反色", "desc": "颜色反转"},
    "light":     {"name": "🌸 淡色", "desc": "低饱和度柔和"},
}
TRANSFORM_DEFAULT = "normal"

# ─── 过渡时间 (毫秒) ─────────────────────────────────────────────────────────
TRANSITION_MS = 800
TRANSITION_STEPS = 30

# ─── 配置文件路径 ─────────────────────────────────────────────────────────────
# os.path.expanduser 可以正确展开 '~'，Path('~') 不能
_appdata = os.environ.get("APPDATA")
if _appdata:
    CONFIG_DIR = Path(_appdata) / "EyeComfort"
else:
    CONFIG_DIR = Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "EyeComfort"
CONFIG_FILE = CONFIG_DIR / "settings.json"


def load_settings() -> dict:
    """加载用户设置，不存在则返回默认值。

    包含类型和范围校验，防止损坏的配置文件导致下游崩溃。
    """
    defaults = {
        "temperature": TEMP_DEFAULT,
        "brightness": BRIGHTNESS_DEFAULT,
        "auto_start": False,
        "last_preset": "day",
        "transform": TRANSFORM_DEFAULT,
    }
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                # 只合并已知键，丢弃未知键防止配置文件膨胀
                known_keys = set(defaults.keys())
                filtered = {k: v for k, v in saved.items() if k in known_keys}
                defaults.update(filtered)
        except (json.JSONDecodeError, OSError):
            # JSON 解析错误或文件读取错误，使用默认值
            pass

    # ─── 校验并夹持 ─────────────────────────────────────────────────────────
    # 温度：必须是 int/float，在合法范围内
    temp = defaults.get("temperature", TEMP_DEFAULT)
    if not isinstance(temp, (int, float)):
        temp = TEMP_DEFAULT
    defaults["temperature"] = max(TEMP_MIN, min(TEMP_MAX, int(temp)))

    # 亮度：必须是 int/float，在合法范围内
    brightness = defaults.get("brightness", BRIGHTNESS_DEFAULT)
    if not isinstance(brightness, (int, float)):
        brightness = BRIGHTNESS_DEFAULT
    defaults["brightness"] = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, int(brightness)))

    # last_preset：必须是字符串且是有效的预设键，或 None 表示自定义
    preset = defaults.get("last_preset", "day")
    if preset is not None and (not isinstance(preset, str) or preset not in PRESETS):
        defaults["last_preset"] = "day"  # 与启动默认一致

    # auto_start：必须是 bool
    auto = defaults.get("auto_start", False)
    defaults["auto_start"] = bool(auto)

    # transform：必须是合法的变换模式
    transform = defaults.get("transform", TRANSFORM_DEFAULT)
    if transform not in TRANSFORMS:
        defaults["transform"] = TRANSFORM_DEFAULT

    return defaults


def save_settings(settings: dict):
    """保存用户设置到 JSON（原子写入，防止崩溃导致数据丢失）"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        # 先写入临时文件，再原子替换，防止崩溃时截断原文件
        fd, tmp_path = tempfile.mkstemp(
            dir=str(CONFIG_DIR), suffix=".tmp", prefix="settings_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, str(CONFIG_FILE))
        except BaseException:
            # 写入失败时清理临时文件
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except OSError:
        # 写入失败（磁盘满等），静默忽略
        pass
