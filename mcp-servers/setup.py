from __future__ import annotations

from pathlib import Path

from setuptools import setup


def load_dependencies() -> list[str]:
    """Assemble install_requires with a local path to agentworld-core."""
    project_root = Path(__file__).resolve().parent
    core_path = project_root.parent / "agentworld-core"
    core_requirement = f"agentworld-core @ file://{core_path.resolve()}"

    return [
        # Core MCP and HTTP
        "mcp>=1.13.1",
        "aiohttp>=3.8.0",
        core_requirement,
        # Data handling
        "pydantic>=2.0.0",
        "typing-extensions>=4.0.0",
        # Async utilities
        "asyncio-mqtt>=0.16.1",
        "aiofiles>=23.1.0",
        # Desktop screenshot dependencies
        "mss>=9.0.0",
        "pygetwindow>=0.0.9",
        "pillow>=10.0.0",
        "pyscreenshot>=3.1",
        # Platform-specific screenshot dependencies
        "python-xlib>=0.33; sys_platform=='linux'",
        "ewmh>=0.1.6; sys_platform=='linux'",
        "pywin32>=306; sys_platform=='win32'",
        "win32gui>=0.1.0; sys_platform=='win32'",
        "pyobjc-framework-Quartz>=10.0; sys_platform=='darwin'",
        "pyobjc-framework-Cocoa>=10.0; sys_platform=='darwin'",
        # Utilities
        "rich>=13.7.0",
        "structlog>=23.2.0",
        "click>=8.1.0",
    ]


setup(install_requires=load_dependencies())
