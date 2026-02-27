# core/launcher.py
import os
import subprocess

# Intento de soporte para resolver .lnk usando pywin32 si está instalado
_HAS_PYWIN32 = False
try:
    from win32com.client import Dispatch  # type: ignore
    _HAS_PYWIN32 = True
except Exception:
    _HAS_PYWIN32 = False

def _resolve_lnk(lnk_path: str):
    """Si pywin32 está disponible intenta resolver el .lnk al target."""
    if not _HAS_PYWIN32:
        return None
    try:
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(lnk_path)
        target = shortcut.Targetpath
        if target and os.path.exists(target):
            return os.path.abspath(target)
    except Exception:
        return None
    return None

def _run_as_admin(path: str, cwd: str = None):
    """Intentar ejecutar como administrador. Devuelve True si parece ok."""
    try:
        import ctypes
        params = None
        res = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, params, cwd or os.path.dirname(path), 1)
        return int(res) > 32
    except Exception:
        return False

def launch_game(path: str, resolved_path: str = None):
    """
    Lanza el juego de forma robusta.
    - path: la ruta que tenemos (puede ser .exe o .lnk)
    - resolved_path: si conoces el exe real, pásalo (preferido)
    """
    if not path:
        raise FileNotFoundError("No se proporcionó ruta al juego.")

    # Si resolved_path válido, preferirlo
    exe_to_launch = None
    cwd = None

    if resolved_path and os.path.isfile(resolved_path) and resolved_path.lower().endswith(".exe"):
        exe_to_launch = resolved_path
        cwd = os.path.dirname(resolved_path)
    else:
        # si path es lnk intentar resolver
        if path.lower().endswith(".lnk"):
            dynamic = _resolve_lnk(path)
            if dynamic and os.path.isfile(dynamic) and dynamic.lower().endswith(".exe"):
                exe_to_launch = dynamic
                cwd = os.path.dirname(dynamic)
            else:
                # no pudimos resolver: usar startfile sobre .lnk (mantiene args/workingdir que tenga el lnk)
                try:
                    os.startfile(path)
                    return True
                except Exception as e_start:
                    raise RuntimeError(f"Fallo al abrir shortcut con startfile: {e_start}")
        else:
            # path suele ser .exe
            exe_to_launch = path
            cwd = os.path.dirname(path)

    if not exe_to_launch or not os.path.exists(exe_to_launch):
        raise FileNotFoundError(f"Archivo a ejecutar no existe: {exe_to_launch}")

    # Intentar lanzar con subprocess
    try:
        # Intento normal
        subprocess.Popen([exe_to_launch], cwd=cwd)
        return True
    except Exception as e_sub:
        # Intentar con shell
        try:
            subprocess.Popen(exe_to_launch, cwd=cwd, shell=True)
            return True
        except Exception:
            # Intentar elevar a administrador
            ok = _run_as_admin(exe_to_launch, cwd=cwd)
            if ok:
                return True
            # si todo falla, reportar el error original
            raise RuntimeError(f"Fallo al lanzar con subprocess: {e_sub}")