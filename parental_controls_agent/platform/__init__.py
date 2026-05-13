import sys

from parental_controls_agent.platform.base import PlatformBackend


def get_backend() -> PlatformBackend:
    if sys.platform == "win32":
        from parental_controls_agent.platform.windows import WindowsBackend
        return WindowsBackend()
    else:
        from parental_controls_agent.platform.linux import LinuxBackend
        return LinuxBackend()
