import sys
import types
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
EXTENSIONS_ROOT = TESTS_DIR.parent
PROJECT_ROOT = EXTENSIONS_ROOT.parent


def _ensure_module(name: str, attrs: dict | None = None):
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    if attrs:
        for key, value in attrs.items():
            setattr(module, key, value)
    sys.modules[name] = module
    return module


# Stub Omni and PXR modules so extension imports succeed in headless tests
omni = _ensure_module("omni")

ext_module = _ensure_module("omni.ext")
if not hasattr(ext_module, "IExt"):
    class _IExt:  # minimal base class stub
        pass
    ext_module.IExt = _IExt

ui_module = _ensure_module("omni.ui")
if not hasattr(ui_module, "Window"):
    class _Window:
        def __init__(self, *_, **__):
            self.visible = True
    ui_module.Window = _Window

usd_module = _ensure_module("omni.usd")
if not hasattr(usd_module, "get_context"):
    class _UsdContext:
        def get_stage(self):
            return None
    usd_module.get_context = lambda: _UsdContext()

kit_module = _ensure_module("omni.kit")
kit_app_module = _ensure_module("omni.kit.app")
if not hasattr(kit_app_module, "get_app_interface"):
    kit_app_module.get_app_interface = lambda: None
kit_module.app = kit_app_module

pxr_module = _ensure_module("pxr")
pxr_module.Usd = types.SimpleNamespace()
pxr_module.UsdGeom = types.SimpleNamespace(Xform=types.SimpleNamespace(Define=lambda *args, **kwargs: types.SimpleNamespace(GetPrim=lambda: types.SimpleNamespace(IsValid=lambda: True))))
pxr_module.Gf = types.SimpleNamespace()
pxr_module.Sdf = types.SimpleNamespace(ValueTypeNames=types.SimpleNamespace(Bool=bool, String=str, Double=float, Int=int))

# Ensure repo root (for fallback imports)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure top-level extensions helpers are importable
if str(EXTENSIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(EXTENSIONS_ROOT))

# Add extension package roots for direct module imports
for package_dir in EXTENSIONS_ROOT.glob("omni.agent.*"):
    if package_dir.is_dir():
        package_path = package_dir
        if str(package_path) not in sys.path:
            sys.path.insert(0, str(package_path))
