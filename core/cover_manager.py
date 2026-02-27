# core/cover_manager.py
import os
import json
from PIL import Image

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
COVERS_DIR = os.path.join(ASSETS_DIR, "covers")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
DEFAULT_COVER = os.path.join(ASSETS_DIR, "default_cover.png")

os.makedirs(COVERS_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)

def _load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_settings(s):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)

def _safe_name(name: str) -> str:
    # crea un nombre de archivo seguro a partir del nombre del juego
    invalid = '<>:"/\\|?*\n\r\t'
    out = "".join(ch for ch in name if ch not in invalid).strip()
    out = out.replace(" ", "_")
    if not out:
        out = "game"
    return out

def get_custom_cover_path(game_name: str):
    s = _load_settings()
    custom = s.get("custom_covers", {})
    path = custom.get(game_name)
    if path and os.path.isfile(path):
        return path
    # fallback: check assets/covers/<safe>.png
    candidate = os.path.join(COVERS_DIR, f"{_safe_name(game_name)}.png")
    if os.path.isfile(candidate):
        return candidate
    return None

def set_custom_cover(game_name: str, source_image_path: str):
    """
    Copia la imagen source_image_path a assets/covers/<safe_name>.png
    y lo registra en settings.json.
    Devuelve la ruta guardada.
    """
    if not os.path.isfile(source_image_path):
        raise FileNotFoundError(source_image_path)

    safe = _safe_name(game_name)
    dest = os.path.join(COVERS_DIR, f"{safe}.png")

    # abrir y convertir a PNG con tamaño razonable
    try:
        img = Image.open(source_image_path).convert("RGBA")
        img.thumbnail((600, 900))  # máximo
        img.save(dest, format="PNG")
    except Exception:
        # copia simple si falla
        import shutil
        shutil.copy2(source_image_path, dest)

    # registrar en settings
    s = _load_settings()
    if "custom_covers" not in s:
        s["custom_covers"] = {}
    s["custom_covers"][game_name] = dest
    _save_settings(s)
    return dest

def find_folder_cover(folder_path: str):
    """
    Busca una imagen dentro de la carpeta del juego con nombres comunes.
    Devuelve ruta o None.
    """
    if not os.path.isdir(folder_path):
        return None
    candidates = ["cover.jpg","cover.png","portada.jpg","portada.png","folder.jpg","folder.png","boxart.jpg","boxart.png"]
    for c in candidates:
        p = os.path.join(folder_path, c)
        if os.path.isfile(p):
            return p
    # si no, busca cualquier jpg/png en la carpeta
    for f in os.listdir(folder_path):
        if f.lower().endswith((".jpg", ".png")):
            return os.path.join(folder_path, f)
    return None

def get_best_cover(game_name: str, exe_folder: str):
    """
    Devuelve la mejor portada posible para un juego:
    1) portada personalizada guardada
    2) portada encontrada en la carpeta del juego
    3) assets/default_cover.png
    """
    custom = get_custom_cover_path(game_name)
    if custom:
        return custom
    folder_cover = find_folder_cover(exe_folder)
    if folder_cover:
        return folder_cover
    return DEFAULT_COVER