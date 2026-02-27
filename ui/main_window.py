# ui/main_window.py
import os
import subprocess
import threading
import time
from datetime import datetime
import customtkinter as ctk
from PIL import Image, ImageOps
from tkinter import filedialog, messagebox

from core.database import (
    init_db, get_all_games, insert_or_update_game,
    update_playtime, update_cover_path
)
from core.scanner import buscar_juegos
from core.cover_manager import get_best_cover, search_cover_online
from core import launcher as core_launcher
from ui.controller_window import ControllerWindow

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GAME LAUNCHER")
        self.geometry("1180x720")

        # Inicializar base de datos y cargar juegos
        init_db()
        self.juegos = get_all_games()
        self.image_refs = []       # referencias a CTkImage para evitar GC
        self.view_mode = "grid"    # "grid" o "list"

        # Top bar
        top = ctk.CTkFrame(self, height=60)
        top.pack(side="top", fill="x", padx=12, pady=12)

        title = ctk.CTkLabel(top, text="🎮 GAME LAUNCHER", font=("Arial", 22))
        title.pack(side="left", padx=12)

        # Right controls
        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right", padx=12)

        self.btn_add_folder = ctk.CTkButton(right, text="Agregar carpeta", command=self.add_folder)
        self.btn_add_folder.grid(row=0, column=0, padx=6)

        self.btn_add_single = ctk.CTkButton(right, text="Agregar Juego", command=self.add_single_game)
        self.btn_add_single.grid(row=0, column=1, padx=6)

        self.btn_toggle_view = ctk.CTkButton(right, text="Cambiar vista", command=self.toggle_view)
        self.btn_toggle_view.grid(row=0, column=2, padx=6)

        self.btn_controllers = ctk.CTkButton(right, text="Controllers", command=self.open_controllers)
        self.btn_controllers.grid(row=0, column=3, padx=6)

        # Status area
        self.status_label = ctk.CTkLabel(top, text=f"Juegos: {len(self.juegos)}", anchor="w")
        self.status_label.pack(side="left", padx=12)

        # Scrollable area for games
        self.scroll_area = ctk.CTkScrollableFrame(self, width=1140, height=600)
        self.scroll_area.pack(padx=12, pady=(0,12), fill="both", expand=True)

        # container inside scrollable for grid/list layout
        self.games_frame = ctk.CTkFrame(self.scroll_area, fg_color="transparent")
        self.games_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Dibujar vista inicial
        self.refresh_games()

    # ----------------------------
    # Añadir juegos
    # ----------------------------
    def add_folder(self):
        folder = filedialog.askdirectory()
        if not folder:
            return
        try:
            nuevos = buscar_juegos(folder)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo escanear la carpeta:\n{e}")
            return

        for game in nuevos:
            insert_or_update_game(game)
        self.juegos = get_all_games()
        self.refresh_games()
        messagebox.showinfo("Carpeta agregada", f"Se agregaron {len(nuevos)} juegos desde:\n{folder}")

    def add_single_game(self):
        file_path = filedialog.askopenfilename(
            title="Selecciona un juego",
            filetypes=[("Ejecutable", "*.exe")]
        )
        if not file_path:
            return

        file_path = os.path.abspath(file_path)
        nombre = os.path.splitext(os.path.basename(file_path))[0]

        game = {
            "nombre": nombre,
            "ruta": file_path,
            "folder": os.path.dirname(file_path),
            "is_shortcut": False,
            "resolved_path": file_path,
            "playtime": 0,
            "last_played": None,
            "cover_path": None
        }
        insert_or_update_game(game)
        self.juegos = get_all_games()
        self.refresh_games()
        messagebox.showinfo("Juego agregado", f"Se agregó '{nombre}' a la biblioteca.")

    # ----------------------------
    # Vista
    # ----------------------------
    def toggle_view(self):
        self.view_mode = "list" if self.view_mode == "grid" else "grid"
        self.refresh_games()

    def refresh_games(self):
        # Limpiar widgets anteriores
        for w in self.games_frame.winfo_children():
            w.destroy()
        self.image_refs.clear()

        if not self.juegos:
            ctk.CTkLabel(
                self.games_frame,
                text="No hay juegos. Usa 'Agregar carpeta' o 'Agregar Juego'"
            ).pack(pady=30)
            self.status_label.configure(text="Juegos: 0")
            return

        if self.view_mode == "grid":
            self._draw_grid()
        else:
            self._draw_list()

        self.status_label.configure(text=f"Juegos: {len(self.juegos)}")

    # ----------------------------
    # Carga de imágenes (con soporte asíncrono)
    # ----------------------------
    def get_default_cover_path(self):
       default = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "default_cover.png")
       if os.path.isfile(default):
        return default
       return None

    def _create_ctk_image(self, cover_path, size):
        try:
            if cover_path and os.path.isfile(cover_path):
               img = Image.open(cover_path).convert("RGBA")
               img = ImageOps.contain(img, size)
            else:
                img = Image.new("RGBA", size, (30, 30, 30, 255))
        except Exception:
           img = Image.new("RGBA", size, (30, 30, 30, 255))
        ctk_img = ctk.CTkImage(img, size=size)
        self.image_refs.append(ctk_img)
        return ctk_img

    def load_game_image(self, game, size=(180, 240)):
    # 1. Intentar cover_path de la BD
        cover_path = game.get("cover_path")
        if not cover_path or not os.path.isfile(cover_path):
        # 2. Buscar localmente (sin descargar)
           folder = game.get("folder") or os.path.dirname(game.get("ruta", ""))
           cover_path = get_best_cover(game["nombre"], folder)
        # Si sigue sin existir, usar default
           if not cover_path or not os.path.isfile(cover_path):
              cover_path = self.get_default_cover_path()

    # Crear imagen con la portada actual
        img = self._create_ctk_image(cover_path, size)

    # Si la portada es la predeterminada, buscar online en segundo plano
        if cover_path == self.get_default_cover_path():
           threading.Thread(target=self._fetch_cover_online, args=(game,), daemon=True).start()

        return img

    def _fetch_cover_online(self, game):
        from core.cover_manager import search_cover_online
        new_path = search_cover_online(game["nombre"])
        if new_path:
          from core.database import update_cover_path
          update_cover_path(game["ruta"], new_path)
          game["cover_path"] = new_path
        # Refrescar la UI en el hilo principal
          self.after(0, self.refresh_games)

    # ----------------------------
    # Dibujado
    # ----------------------------
    def _draw_grid(self):
        cols = 4
        row = 0
        col = 0
        padx = 18
        pady = 18

        for game in self.juegos:
            frame = ctk.CTkFrame(self.games_frame, width=220, height=320, corner_radius=8)
            frame.grid(row=row, column=col, padx=padx, pady=pady)
            frame.grid_propagate(False)

            cover = self.load_game_image(game, size=(180, 240))
            cover_label = ctk.CTkLabel(frame, image=cover, text="")
            cover_label.image = cover
            cover_label.pack(pady=(12, 8))

            name_lbl = ctk.CTkLabel(
                frame, text=game.get("nombre", "Sin nombre"),
                wraplength=200, font=("Arial", 12)
            )
            name_lbl.pack()

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.pack(side="bottom", fill="x", pady=(8, 12), padx=6)

            play_btn = ctk.CTkButton(
                btn_frame, text="Jugar",
                command=lambda g=game: self.launch_game(g)
            )
            play_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))

            cover_btn = ctk.CTkButton(
                btn_frame, text="Portada",
                command=lambda g=game: self.change_cover_dialog(g)
            )
            cover_btn.pack(side="left", expand=True, fill="x", padx=(4, 0))

            col += 1
            if col >= cols:
                col = 0
                row += 1

    def _draw_list(self):
        for index, game in enumerate(self.juegos):
            bg = "#2b2b2b" if index % 2 == 0 else "#242424"
            row = ctk.CTkFrame(self.games_frame, fg_color=bg, corner_radius=0)
            row.pack(fill="x")

            cover = self.load_game_image(game, size=(80, 50))
            img_label = ctk.CTkLabel(row, image=cover, text="")
            img_label.image = cover
            img_label.pack(side="left", padx=10, pady=5)

            name_label = ctk.CTkLabel(
                row, text=game.get("nombre", "Sin nombre"),
                font=("Arial", 15, "bold")
            )
            name_label.pack(side="left", padx=20)

            minutes = game.get("playtime", 0)
            hours = round(minutes / 60, 1)
            playtime_label = ctk.CTkLabel(row, text=f"{hours} h jugadas")
            playtime_label.pack(side="left", padx=20)

            last = game.get("last_played", "Nunca")
            last_label = ctk.CTkLabel(row, text=f"Última vez: {last}")
            last_label.pack(side="left", padx=20)

            spacer = ctk.CTkFrame(row, fg_color="transparent")
            spacer.pack(side="left", expand=True, fill="x")

            play_btn = ctk.CTkButton(
                row, text="Jugar", width=100,
                command=lambda g=game: self.launch_game(g)
            )
            play_btn.pack(side="right", padx=10, pady=5)

    # ----------------------------
    # Cambiar portada manualmente
    # ----------------------------
    def change_cover_dialog(self, game):
        from core.cover_manager import set_custom_cover
        file = filedialog.askopenfilename(
            title="Selecciona imagen para portada",
            filetypes=[("Imágenes", "*.png *.jpg *.jpeg *.bmp")]
        )
        if not file:
            return
        try:
            newpath = set_custom_cover(game["nombre"], file)
            # Actualizar en BD
            update_cover_path(game["ruta"], newpath)
            # Refrescar vista
            self.refresh_games()
            messagebox.showinfo("Portada guardada", f"Portada guardada en:\n{newpath}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la portada:\n{e}")

    # ----------------------------
    # Lanzar juego
    # ----------------------------
    def launch_game(self, game):
        path_to_run = game.get("resolved_path") or game.get("ruta") or ""
        if not path_to_run:
            messagebox.showerror("Error", "Ruta de juego inválida.")
            return

        # Si es .exe, lanzar con subprocess y monitorizar tiempo
        if path_to_run.lower().endswith(".exe") and os.path.isfile(path_to_run):
            try:
                cwd = game.get("folder") or os.path.dirname(path_to_run)
                proc = subprocess.Popen([path_to_run], cwd=cwd)
            except Exception as e:
                messagebox.showerror("Error al abrir", f"No se pudo iniciar el juego:\n{e}")
                return

            def monitor_process(p, g):
                start = time.time()
                try:
                    p.wait()
                except Exception:
                    pass
                end = time.time()
                minutes = int((end - start) / 60)
                if minutes > 0:
                    g["playtime"] = g.get("playtime", 0) + minutes
                g["last_played"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                # Guardar en BD
                update_playtime(g["ruta"], minutes, g["last_played"])
                # Refrescar UI
                self.after(0, self.refresh_games)

            threading.Thread(target=monitor_process, args=(proc, game), daemon=True).start()
            return

        # Si no es .exe (por ejemplo .lnk), usar core_launcher
        try:
            if hasattr(core_launcher, "launch_game"):
                core_launcher.launch_game(game.get("ruta"), resolved_path=game.get("resolved_path"))
                return
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo lanzar el juego (fallback):\n{e}")
            return

        messagebox.showerror("Error", "No se pudo ejecutar el juego. Ruta inválida o sin soporte.")

    # ----------------------------
    # Ventana de mandos
    # ----------------------------
    def open_controllers(self):
        win = ControllerWindow(self)
        try:
            win.lift()
            win.attributes("-topmost", True)
            win.after(200, lambda: win.attributes("-topmost", False))
        except Exception:
            pass