# ui/main_window.py
import os
import subprocess
import threading
import time
from datetime import datetime
import customtkinter as ctk
from PIL import Image, ImageOps
from tkinter import filedialog, messagebox

from core.scanner import buscar_juegos
from core.cover_manager import get_best_cover
from core import launcher as core_launcher  # usando core/launcher.launch_game si existe

from ui.controller_window import ControllerWindow

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GAME LAUNCHER")
        self.geometry("1180x720")

        # data
        self.juegos = []           # lista de dicts {nombre, ruta, folder, ...}
        self._known_paths = set()  # para evitar duplicados (rutas absolutas)
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

        # Search / status area (optional)
        self.status_label = ctk.CTkLabel(top, text="Juegos: 0", anchor="w")
        self.status_label.pack(side="left", padx=12)

        # Scrollable area for games
        self.scroll_area = ctk.CTkScrollableFrame(self, width=1140, height=600)
        self.scroll_area.pack(padx=12, pady=(0,12), fill="both", expand=True)

        # container inside scrollable for grid/list layout
        self.games_frame = ctk.CTkFrame(self.scroll_area, fg_color="transparent")
        self.games_frame.pack(fill="both", expand=True, padx=8, pady=8)

    # ----------------------------
    # Folder scanning and adding
    # ----------------------------
    def _add_games_from_folder(self, folder_path):
        if not folder_path or not os.path.isdir(folder_path):
            return 0
        try:
            nuevos = buscar_juegos(folder_path)
        except Exception:
            # fallback: buscar exes simples
            nuevos = []
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if f.lower().endswith(".exe"):
                        nuevos.append({"nombre": os.path.splitext(f)[0], "ruta": os.path.join(root, f), "folder": root})

        added = 0
        for g in nuevos:
            ruta = os.path.abspath(g.get("ruta", ""))
            if not ruta or ruta in self._known_paths:
                continue
            # asegurar folder key
            if "folder" not in g or not g["folder"]:
                g["folder"] = os.path.dirname(ruta)
            self.juegos.append(g)
            self._known_paths.add(ruta)
            added += 1
        if added:
            self.refresh_games()
        return added

    def add_folder(self):
        folder = filedialog.askdirectory(title="Selecciona carpeta para agregar juegos (se agregan sin quitar existentes)")
        if not folder:
            return
        added = self._add_games_from_folder(folder)
        messagebox.showinfo("Agregar carpeta", f"Se agregaron {added} juegos desde:\n{folder}")

    def add_single_game(self):
        file_path = filedialog.askopenfilename(
            title="Selecciona un juego",
            filetypes=[("Ejecutable", "*.exe")]
        )

        if not file_path:
            return

        file_path = os.path.abspath(file_path)

        # evitar duplicados
        if file_path in self._known_paths:
            messagebox.showinfo("Ya agregado", "Este juego ya está en la lista.")
            return

        nombre = os.path.splitext(os.path.basename(file_path))[0]

        game = {
            "nombre": nombre,
            "ruta": file_path,
            "folder": os.path.dirname(file_path),
            "playtime": 0,
            "last_played": None
        }

        self.juegos.append(game)
        self._known_paths.add(file_path)

        self.refresh_games()

    # ----------------------------
    # View mode handling
    # ----------------------------
    def toggle_view(self):
        self.view_mode = "list" if self.view_mode == "grid" else "grid"
        self.refresh_games()

    def refresh_games(self):
        # limpiar referencias y widgets
        for w in self.games_frame.winfo_children():
            w.destroy()
        self.image_refs.clear()

        if not self.juegos:
            ctk.CTkLabel(self.games_frame, text="No hay juegos. Usa 'Agregar carpeta' o 'Agregar Juego'").pack(pady=30)
            self.status_label.configure(text=f"Juegos: 0")
            return

        if self.view_mode == "grid":
            self._draw_grid()
        else:
            self._draw_list()

        self.status_label.configure(text=f"Juegos: {len(self.juegos)}")

    # ----------------------------
    # Image loader helper
    # ----------------------------
    def load_game_image(self, game, size=(180, 240)):
        """
        Devuelve un ctk.CTkImage preparado, y guarda referencia en self.image_refs.
        Usa core.cover_manager.get_best_cover para elegir imagen.
        """
        try:
            folder = game.get("folder") or os.path.dirname(game.get("ruta", ""))
            cover_path = get_best_cover(game.get("nombre", ""), folder)
        except Exception:
            cover_path = None

        # fallback default
        if not cover_path or not os.path.isfile(cover_path):
            # intenta path relativo assets/default_cover.png
            cover_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "default_cover.png")
            if not os.path.isfile(cover_path):
                cover_path = None

        # crear imagen PIL y CTkImage
        try:
            if cover_path:
                img = Image.open(cover_path).convert("RGBA")
                img = ImageOps.contain(img, size)
            else:
                img = Image.new("RGBA", size, (30,30,30,255))
        except Exception:
            img = Image.new("RGBA", size, (30,30,30,255))

        ctk_img = ctk.CTkImage(img, size=size)
        # mantener referencia para que no la borre el garbage collector de Tk
        self.image_refs.append(ctk_img)
        return ctk_img

    # ----------------------------
    # Drawing functions
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

            cover = self.load_game_image(game, size=(180,240))
            cover_label = ctk.CTkLabel(frame, image=cover, text="")
            cover_label.image = cover
            cover_label.pack(pady=(12,8))

            name_lbl = ctk.CTkLabel(frame, text=game.get("nombre","Sin nombre"), wraplength=200, font=("Arial", 12))
            name_lbl.pack()

            btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
            btn_frame.pack(side="bottom", fill="x", pady=(8,12), padx=6)

            play_btn = ctk.CTkButton(btn_frame, text="Jugar", command=lambda g=game: self.launch_game(g))
            play_btn.pack(side="left", expand=True, fill="x", padx=(0,4))

            cover_btn = ctk.CTkButton(btn_frame, text="Portada", command=lambda g=game: self.change_cover_dialog(g))
            cover_btn.pack(side="left", expand=True, fill="x", padx=(4,0))

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

            name_label = ctk.CTkLabel(row, text=game.get("nombre","Sin nombre"), font=("Arial", 15, "bold"))
            name_label.pack(side="left", padx=20)

            # tiempo jugado
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
                row,
                text="Jugar",
                width=100,
                command=lambda g=game: self.launch_game(g)
            )
            play_btn.pack(side="right", padx=10, pady=5)

    # ----------------------------
    # Cover change dialog (uses cover_manager.set_custom_cover)
    # ----------------------------
    def change_cover_dialog(self, game):
        from core.cover_manager import set_custom_cover
        file = filedialog.askopenfilename(title="Selecciona imagen para portada", filetypes=[("Imágenes","*.png *.jpg *.jpeg *.bmp")])
        if not file:
            return
        try:
            newpath = set_custom_cover(game.get("nombre",""), file)
            # actualizar UI
            self.refresh_games()
            messagebox.showinfo("Portada guardada", f"Portada guardada en:\n{newpath}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la portada:\n{e}")

    # ----------------------------
    # Launch game (uses core.launcher.launch_game if posible)
    # ----------------------------
    def launch_game(self, game):
        # preferir resolved_path si existe (exe real)
        path_to_run = (game.get("resolved_path") or game.get("ruta") or "")
        if not path_to_run:
            messagebox.showerror("Error", "Ruta de juego inválida.")
            return

        # si la ruta es un exe existente -> lanzar con subprocess y monitorizar tiempo jugado
        if path_to_run.lower().endswith(".exe") and os.path.isfile(path_to_run):
            try:
                cwd = game.get("folder") or os.path.dirname(path_to_run)
                proc = subprocess.Popen([path_to_run], cwd=cwd)
            except Exception as e:
                messagebox.showerror("Error al abrir", f"No se pudo iniciar el juego:\n{e}")
                return

            # monitor en hilo para no bloquear la interfaz
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
                # refrescar UI en hilo principal
                try:
                    self.after(0, self.refresh_games)
                except Exception:
                    pass

            threading.Thread(target=monitor_process, args=(proc, game), daemon=True).start()
            return

        # si no es un exe (por ejemplo .lnk) o no pudimos lanzar con subprocess, intentar core_launcher
        try:
            if hasattr(core_launcher, "launch_game"):
                core_launcher.launch_game(game.get("ruta"), resolved_path=game.get("resolved_path"))
                # no podemos medir tiempo si el launcher maneja el proceso; salimos.
                return
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo lanzar el juego (fallback):\n{e}")
            return

        messagebox.showerror("Error", "No se pudo ejecutar el juego. Ruta inválida o sin soporte.")

    # ----------------------------
    # Controllers window
    # ----------------------------
    def open_controllers(self):
        win = ControllerWindow(self)
        # asegurar que la ventana esté en frente temporalmente
        try:
            win.lift()
            win.attributes("-topmost", True)
            win.after(200, lambda: win.attributes("-topmost", False))
        except Exception:
            pass