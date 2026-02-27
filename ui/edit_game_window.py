# ui/edit_game_window.py
import customtkinter as ctk
from core.database import insert_or_update_game

class EditGameWindow(ctk.CTkToplevel):
    def __init__(self, parent, game):
        super().__init__(parent)
        self.game = game
        self.title("Editar juego")
        self.geometry("400x300")
        self.transient(parent)
        self.grab_set()

        # Campos
        ctk.CTkLabel(self, text="Nombre:").pack(pady=5)
        self.name_entry = ctk.CTkEntry(self)
        self.name_entry.insert(0, game["nombre"])
        self.name_entry.pack(pady=5)

        ctk.CTkLabel(self, text="Ruta:").pack(pady=5)
        self.path_entry = ctk.CTkEntry(self)
        self.path_entry.insert(0, game["ruta"])
        self.path_entry.pack(pady=5)

        # Botón guardar
        btn = ctk.CTkButton(self, text="Guardar", command=self.save)
        btn.pack(pady=20)

    def save(self):
        nuevo_nombre = self.name_entry.get()
        nueva_ruta = self.path_entry.get()
        # Actualizar diccionario y BD
        self.game["nombre"] = nuevo_nombre
        self.game["ruta"] = nueva_ruta
        insert_or_update_game(self.game)  # asume que la función existe
        self.destroy()
        # Refrescar vista principal
        self.master.refresh_games()