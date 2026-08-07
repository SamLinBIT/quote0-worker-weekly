"""环境配置加载（.env / 环境变量）。

load_config 会先尝试读取项目根目录 .env（极简解析，不依赖第三方库），
已存在的环境变量优先（wrapper 里 set -a; source .env 的场景不受影响）。
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

PUSH_MODES = ("canvas", "image")
MEME_MODES = ("fixed", "random")


def _parse_env_line(line: str) -> tuple[str, str] | None:
    """解析一行 `KEY=VALUE`：支持 `export` 前缀、行尾 `# 注释`（引号内除外）。

    不做变量展开；返回 (key, value) 或 None（注释/空行/格式非法）。
    """
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[7:].lstrip()
    if "=" not in line:
        return None

    key, _, value = line.partition("=")
    key = key.strip()
    if not key:
        return None

    value = value.strip()
    if value and value[0] in "\"'" :
        quote = value[0]
        end = value.find(quote, 1)  # 引号内视为字面值，注释不生效
        return key, value[1:end] if end != -1 else value[1:]
    value = value.split(" #", 1)[0].split("\t#", 1)[0].rstrip()
    return key, value.strip()


def _load_env_file(env_path: Path = ENV_PATH) -> None:
    """把 .env 的 KEY=VALUE 读入 os.environ（不覆盖已存在的变量）。

    支持 `export` 前缀、行尾注释；不做变量展开。
    """
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw)
        if parsed is None:
            continue
        key, value = parsed
        if key not in os.environ:
            os.environ[key] = value


@dataclass
class Config:
    dot_api_key: str
    dot_device_id: str
    push_mode: str = "image"   # image（默认，整卡 PNG） | canvas（DSL 设备端渲染）
    treatment: str = "bw"      # bw | fs | 4level
    meme_mode: str = "random"  # random（分组文件夹随机） | fixed（顶层单日文件）


def load_config(require_keys: bool = True) -> Config:
    """从 .env / 环境变量加载配置；缺失关键项时打印提示并退出。

    require_keys=False（--dry-run 用）：密钥缺失不退出——dry-run 只
    打印 payload 不推送，密钥用不上。
    """
    _load_env_file()
    api_key = os.environ.get("DOT_API_KEY", "")
    device_id = os.environ.get("DOT_DEVICE_ID", "")
    if require_keys and (not api_key or not device_id):
        print("[ERROR] 缺少 DOT_API_KEY / DOT_DEVICE_ID。"
              "请 cp .env.example .env 后填入密钥（见 .env.example）。")
        sys.exit(1)

    mode = os.environ.get("PUSH_MODE", "image").lower()
    if mode not in PUSH_MODES:
        print(f"[WARN] PUSH_MODE={mode} 非法，回退默认 image")
        mode = "image"

    treatment = os.environ.get("TREATMENT", "bw").lower()
    if treatment not in ("bw", "fs", "4level"):
        print(f"[WARN] TREATMENT={treatment} 非法，回退默认 bw")
        treatment = "bw"

    meme_mode = os.environ.get("MEME_MODE", "random").lower()
    if meme_mode not in MEME_MODES:
        print(f"[WARN] MEME_MODE={meme_mode} 非法，回退默认 random")
        meme_mode = "random"

    return Config(
        dot_api_key=api_key,
        dot_device_id=device_id,
        push_mode=mode,
        treatment=treatment,
        meme_mode=meme_mode,
    )
