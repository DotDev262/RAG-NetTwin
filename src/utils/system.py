import os
import platform


def is_wsl() -> bool:
    """
    Detect if running inside WSL (Windows Subsystem for Linux).
    """
    if platform.system() != "Linux":
        return False
    try:
        if os.path.exists("/proc/version"):
            with open("/proc/version", "r") as f:
                return "microsoft" in f.read().lower()
    except (IOError, PermissionError):
        pass
    return False


def fix_path(path_str: str) -> str:
    """
    Convert Windows-style absolute paths to WSL-style if necessary.
    """
    if not path_str:
        return path_str
    if is_wsl() and len(path_str) > 2 and path_str[1] == ":" and path_str[2] == "\\":
        drive = path_str[0].lower()
        parts = path_str[3:].replace("\\", "/").split("/")
        return f"/mnt/{drive}/{'/'.join(parts)}"
    return path_str
