#!/usr/bin/env python3
"""macOS 权限检测与修复模块。
此模块已停用预检，写入失败时由 core.py 直接报错。
保留此文件以备将来扩展。
"""
import os
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
CODEX_DIR = HOME / ".codex"
CONFIG_TOML = CODEX_DIR / "config.toml"


def check_codex_directory_writable() -> tuple[bool, str]:
    """始终返回 True，不再预检。"""
    return True, ""


def fix_permissions_with_permission() -> tuple[bool, str]:
    """不再尝试修复，直接返回失败。"""
    return False, ""


def is_running_in_sandbox() -> bool:
    return False


def get_permission_guide() -> str:
    return ""


def request_full_disk_access() -> bool:
    return False
