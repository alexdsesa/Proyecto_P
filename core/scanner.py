# core/scanner.py
import os
import re

# Intenta usar pywin32 para resolver .lnk (opcional)
_HAS_PYWIN32 = False
try:
    from win32com.client import Dispatch  # type: ignore
    _HAS_PYWIN32 = True
except Exception:
    _HAS_PYWIN32 = False

def _resolve_lnk(lnk_path: str):
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

# patrones de exclusión por nombre / carpeta
EXCLUDE_NAME_PATTERNS = [
    r"uninst", r"uninstall", r"installer", r"\bsetup\b", r"install",
    r"updat", r"patch", r"update", r"repair", r"remove", r"autorun",
    r"readme", r"vcredist", r"redistributable", r"dxsetup", r"directx",
    r"crash", r"crashreport", r"crashreporter", r"unitcrash", r"launcher_helper",
    r"steamwebhelper", r"steamservice"
]
EXCLUDE_FOLDER_PATTERNS = [
    r"redist", r"commonredist", r"__installer", r"directx", r"vcredist",
    r"support", r"crashreporter", r"prereq", r"installer", r"tools"
]

_name_re = re.compile("|".join(EXCLUDE_NAME_PATTERNS), re.IGNORECASE)
_folder_re = re.compile("|".join(EXCLUDE_FOLDER_PATTERNS), re.IGNORECASE)

def _is_excluded_by_name(filename: str):
    return bool(_name_re.search(filename))

def _is_excluded_by_folder(folderpath: str):
    return bool(_folder_re.search(folderpath))

def _best_exe_for_group(exe_paths, top_folder_name):
    """
    Dada una lista de rutas exe dentro de un mismo top-level folder,
    escoger la mejor candidata según heurística:
      1) exe con mismo nombre que la carpeta
      2) exe cuyo nombre contiene palabras clave del folder
      3) si hay un solo exe -> ese
      4) sino -> exe más grande
    """
    if not exe_paths:
        return None

    top = (top_folder_name or "").lower()

    # 1) mismo nombre exacto
    for p in exe_paths:
        base = os.path.splitext(os.path.basename(p))[0].lower()
        if base == top:
            return p

    # 2) nombre que contiene partes del folder
    words = [w for w in re.split(r"[\s_\-\.]+", top) if w]
    for p in exe_paths:
        base = os.path.splitext(os.path.basename(p))[0].lower()
        for w in words:
            if w and w in base and len(w) >= 3:
                return p

    # 3) si sólo hay un exe
    if len(exe_paths) == 1:
        return exe_paths[0]

    # 4) el más grande
    try:
        return max(exe_paths, key=lambda x: os.path.getsize(x))
    except Exception:
        return exe_paths[0]

def buscar_juegos(root_folder: str, include_lnks_root: bool = True, debug: bool = False):
    """
    Escanea la carpeta root_folder y devuelve:
      - juegos: lista de dicts {nombre, ruta, folder, is_shortcut, resolved_path}
      - skipped (solo si debug=True): lista de (ruta, razon)

    Lógica:
      - agrupa EXE por top-level folder (primer nivel dentro de root_folder)
      - aplica heurísticas para escoger 1 exe por top-folder
      - también incluye .exe directamente en la raíz como entradas individuales
      - intenta resolver .lnk en la raíz si include_lnks_root True
    """
    root_folder = os.path.abspath(root_folder)
    jogos = []
    skipped = []
    grouped = {}  # top_level_name -> list of exe paths
    seen_exes = set()

    # Recorrer recursivamente y agrupar por top-level folder
    for dirpath, dirnames, filenames in os.walk(root_folder):
        # si estamos en root_folder mismo, top_key = None
        rel = os.path.relpath(dirpath, root_folder)
        if rel == ".":
            top_key = None
        else:
            top_key = rel.split(os.sep)[0]  # primer componente
        for f in filenames:
            if not f.lower().endswith(".exe"):
                continue
            ruta = os.path.join(dirpath, f)
            # Excluir por nombre o carpeta
            if _is_excluded_by_name(f):
                skipped.append((ruta, "excluded_by_name"))
                continue
            if _is_excluded_by_folder(dirpath):
                skipped.append((ruta, "excluded_by_folder"))
                continue
            # Añadir a grupo
            grouped.setdefault(top_key, []).append(ruta)

    # Procesar cada grupo
    for top, exe_list in grouped.items():
        # eliminar duplicados
        unique_list = []
        for p in exe_list:
            pa = os.path.abspath(p)
            if pa not in unique_list:
                unique_list.append(pa)
        # escoger la mejor exe para este top
        chosen = _best_exe_for_group(unique_list, top or "")
        if not chosen:
            continue
        seen_exes.add(os.path.abspath(chosen))

        # nombre para mostrar: si top existe, usar top (más limpio), si no usar nombre del exe
        if top:
            display_name = top
        else:
            display_name = os.path.splitext(os.path.basename(chosen))[0]

        jogos.append({
            "nombre": display_name,
            "ruta": os.path.abspath(chosen),
            "folder": os.path.dirname(os.path.abspath(chosen)),
            "is_shortcut": False,
            "resolved_path": os.path.abspath(chosen)
        })

    # Incluir EXE directamente en la raíz (si no ya incluidos)
    # grouped had key None for dirpath == root; we already processed that with top=None,
    # but in case we skipped root-exes earlier due to exclusion, add none here -- skip.

    # Procesar .lnk en la raíz (si se pide)
    if include_lnks_root:
        try:
            for f in os.listdir(root_folder):
                if f.lower().endswith(".lnk"):
                    lnk_path = os.path.join(root_folder, f)
                    resolved = _resolve_lnk(lnk_path)
                    if resolved and os.path.isfile(resolved) and resolved.lower().endswith(".exe"):
                        if _is_excluded_by_name(os.path.basename(resolved)):
                            skipped.append((lnk_path, "lnk_points_to_excluded_exe"))
                            continue
                        abs_res = os.path.abspath(resolved)
                        if abs_res in seen_exes:
                            # ya incluido
                            continue
                        # determinar display name y folder
                        top = os.path.relpath(os.path.dirname(abs_res), root_folder).split(os.sep)[0]
                        display_name = top if top and top != "." else os.path.splitext(os.path.basename(abs_res))[0]
                        jogos.append({
                            "nombre": display_name,
                            "ruta": os.path.abspath(lnk_path),   # abriremos el lnk (porque mantiene args/workingdir)
                            "folder": os.path.dirname(abs_res),
                            "is_shortcut": True,
                            "resolved_path": abs_res
                        })
                        seen_exes.add(abs_res)
                    else:
                        # no pudimos resolver: aun así lo añadimos como shortcut entry
                        display_name = os.path.splitext(f)[0]
                        possible_folder = os.path.join(root_folder, display_name)
                        folder_for_cover = possible_folder if os.path.isdir(possible_folder) else root_folder
                        jogos.append({
                            "nombre": display_name,
                            "ruta": os.path.abspath(lnk_path),
                            "folder": folder_for_cover,
                            "is_shortcut": True,
                            "resolved_path": None
                        })
        except Exception:
            pass

    # ordenar
    jogos.sort(key=lambda x: x["nombre"].lower())

    if debug:
        return jogos, skipped
    return jogos
