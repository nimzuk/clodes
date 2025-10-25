import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("backend.main", str(Path(__file__).parent / "main.py"))
mod = importlib.util.module_from_spec(spec); sys.modules["backend.main"]=mod; spec.loader.exec_module(mod)  # type: ignore
app = mod.app
