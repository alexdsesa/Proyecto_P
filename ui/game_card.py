# ui/game_card.py
import customtkinter as ctk
from PIL import Image, ImageOps
import os
import subprocess
from core.cover_manager import get_best_cover, set_custom_cover
from tkinter import filedialog, messagebox

# Intento de soporte para resolver .lnk usando pywin32 si está instalado
_HAS_PYWIN32 = False
try:
    from win32com.client import Dispatch  # type: ignore
    _HAS_PYWIN32 = True
except Exception:
    _HAS_PYWIN32 = False


def _resolve_lnk(lnk_path: str):
    """
    Intenta resolver .lnk a su target usando pywin32.
    Devuelve ruta al target o None si no puede resolver.
    """
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
    """
    Intenta ejecutar el archivo como administrador usando ShellExecuteW.
    Devuelve True si el intento devuelve código > 32 (éxito), False en otro caso.
    """
    try:
        import ctypes
        params = None
        # ShellExecuteW devuelve >32 si éxito
        res = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, params, cwd or os.path.dirname(path), 1)
        return int(res) > 32
    except Exception:
        return False


def _launch_process(exe_path: str, cwd: str):
    """
    Intenta iniciar el ejecutable de forma robusta:
    - si es .lnk: usa os.startfile (o intentará resolver)
    - intenta subprocess.Popen(cwd=...)
    - si falla, intenta _run_as_admin
    Lanza excepciones si todo falla.
    """
    # Si es shortcut .lnk y no pudimos resolver antes, abrir con os.startfile
    if exe_path.lower().endswith(".lnk"):
        try:
            os.startfile(exe_path)
            return
        except Exception as e:
            raise RuntimeError(f"Intento con os.startfile falló: {e}")

    # Si no es lnk: intentar lanzar con subprocess
    try:
        # subprocess.Popen con lista es más seguro
        subprocess.Popen([exe_path], cwd=cwd)
        return
    except Exception as e_sub:
        # intentar con shell True (algunos launchers requieren esto)
        try:
            subprocess.Popen(exe_path, cwd=cwd, shell=True)
            return
        except Exception:
            # intentar elevar a admin
            ok = _run_as_admin(exe_path, cwd=cwd)
            if ok:
                return
            # si todo falla, propagar el error original
            raise RuntimeError(f"Fallo al lanzar con subprocess: {e_sub}")


class GameCard(ctk.CTkFrame):
    def __init__(self, master, game, cover_size=(180, 240), *args, **kwargs):
        """
        game: dict con keys 'nombre','ruta' (y opcional 'folder' -> carpeta del exe)
        """
        super().__init__(master, corner_radius=8, *args, **kwargs)
        self.game = game
        self.cover_size = cover_size

        # container
        self.grid_propagate(False)

        # cover image
        self.cover_path = None
        self._load_cover_image()

        # label nombre
        name_lbl = ctk.CTkLabel(self, text=self.game.get("nombre", "Sin nombre"), anchor="w")
        name_lbl.pack(side="top", fill="x", padx=6, pady=(8, 4))

        # buttons frame
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=6, pady=8)

        play_btn = ctk.CTkButton(btn_frame, text="Jugar", command=self._play)
        play_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

        cover_btn = ctk.CTkButton(btn_frame, text="Cambiar portada", command=self._change_cover)
        cover_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _load_cover_image(self):
        # consigue la mejor portada y la muestra
        folder = self.game.get("folder") or os.path.dirname(self.game.get("ruta", ""))
        self.cover_path = get_best_cover(self.game.get("nombre", ""), folder)
        try:
            img = Image.open(self.cover_path).convert("RGBA")
            img = ImageOps.contain(img, self.cover_size)
        except Exception:
            from PIL import Image
            img = Image.new("RGBA", self.cover_size, (30, 30, 30, 255))
        self.ctk_image = ctk.CTkImage(img, size=self.cover_size)
        # imagen arriba
        img_label = ctk.CTkLabel(self, image=self.ctk_image, text="")
        img_label.pack(side="top", pady=(6, 4))

    def refresh_cover(self):
        # recarga la imagen (si cambió)
        for w in self.winfo_children():
            w.destroy()
        self._load_cover_image()
        # re-add name and buttons
        name_lbl = ctk.CTkLabel(self, text=self.game.get("nombre", "Sin nombre"), anchor="w")
        name_lbl.pack(side="top", fill="x", padx=6, pady=(8, 4))
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=6, pady=8)
        play_btn = ctk.CTkButton(btn_frame, text="Jugar", command=self._play)
        play_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        cover_btn = ctk.CTkButton(btn_frame, text="Cambiar portada", command=self._change_cover)
        cover_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

    def _play(self):
        ruta = self.game.get("ruta")
        resolved = self.game.get("resolved_path")  # si el scanner devolvió resolved_path, lo preferimos

        # Determinar ruta final a lanzar y cwd
        exe_to_launch = None
        cwd = None

        try:
            # Priorizar resolved_path si existe y es un exe
            if resolved and os.path.isfile(resolved) and resolved.lower().endswith(".exe"):
                exe_to_launch = resolved
                cwd = os.path.dirname(resolved)
            else:
                # si la ruta original es .lnk, intentar resolver dinámicamente
                if ruta and ruta.lower().endswith(".lnk"):
                    dynamic = _resolve_lnk(ruta)
                    if dynamic and os.path.isfile(dynamic) and dynamic.lower().endswith(".exe"):
                        exe_to_launch = dynamic
                        cwd = os.path.dirname(dynamic)
                    else:
                        # no se pudo resolver: abrimos directamente el .lnk con os.startfile
                        exe_to_launch = ruta
                        cwd = os.path.dirname(ruta)
                else:
                    # ruta usual (.exe)
                    exe_to_launch = ruta
                    cwd = os.path.dirname(ruta)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo preparar la ejecución:\n{e}")
            return

        if not exe_to_launch or not os.path.exists(exe_to_launch):
            messagebox.showerror("Error", f"Archivo no encontrado:\n{exe_to_launch}")
            return

        # Intentar lanzar
        try:
            _launch_process(exe_to_launch, cwd)
        except Exception as e:
            # mostrar mensaje con detalle
            messagebox.showerror("Error al abrir", f"No se pudo abrir el juego.\n{e}")
            return

    def _change_cover(self):
        # abrir file dialog para seleccionar imagen
        f = filedialog.askopenfilename(title="Selecciona una imagen para la portada",
                                       filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp")])
        if not f:
            return
        try:
            newpath = set_custom_cover(self.game.get("nombre", ""), f)
            self.cover_path = newpath
            self.refresh_cover()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo establecer la portada:\n{e}")