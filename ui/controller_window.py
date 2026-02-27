# ui/controller_window.py

import customtkinter as ctk
import tkinter as tk
import pygame


class ControllerWindow(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)

        # Siempre al frente y centrada
        self.transient(parent)
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

        self.title("Controller Professional Tester")
        self.geometry("900x600")
        self.resizable(False, False)

        self.center_window(parent)

        pygame.init()
        pygame.joystick.init()

        self.joystick = None

        # -------- HEADER --------
        title = ctk.CTkLabel(self, text="🎮 Controller Professional Tester", font=("Arial", 22))
        title.pack(pady=10)

        # -------- SELECTOR --------
        self.device_var = ctk.StringVar()
        self.device_menu = ctk.CTkOptionMenu(
            self,
            values=self.get_devices(),
            variable=self.device_var,
            command=self.select_device
        )
        self.device_menu.pack(pady=5)

        refresh_btn = ctk.CTkButton(self, text="Actualizar dispositivos", command=self.refresh_devices)
        refresh_btn.pack(pady=5)

        # -------- MAIN FRAME --------
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=20, pady=15)

        # Canvas visual
        self.canvas = tk.Canvas(main, width=650, height=450, bg="#141414", highlightthickness=0)
        self.canvas.pack(side="left", padx=15)

        # Panel info
        self.info_panel = ctk.CTkTextbox(main, width=220)
        self.info_panel.pack(side="right", fill="y", padx=10)

        self.setup_visual()

        self.update_loop()

    # --------------------------------------------------
    # DETECCIÓN DE DISPOSITIVOS
    # --------------------------------------------------

    def get_devices(self):
        devices = []
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            devices.append(f"{i} - {joy.get_name()}")
        if not devices:
            devices = ["No hay controles"]
        return devices

    def refresh_devices(self):
        pygame.joystick.quit()
        pygame.joystick.init()
        devices = self.get_devices()
        self.device_menu.configure(values=devices)
        self.device_var.set(devices[0])

    def select_device(self, value):
        if "No hay" in value:
            self.joystick = None
            return

        index = int(value.split(" - ")[0])
        self.joystick = pygame.joystick.Joystick(index)
        self.joystick.init()

    # --------------------------------------------------
    # VISUAL PROFESIONAL
    # --------------------------------------------------

    def setup_visual(self):

        self.canvas.delete("all")

        # Base del control
        self.canvas.create_oval(100, 100, 550, 400, fill="#1e1e1e", outline="#333", width=3)

        # Sticks
        self.left_center = (250, 270)
        self.right_center = (400, 270)

        self.canvas.create_oval(200, 220, 300, 320, outline="#666", width=3)
        self.canvas.create_oval(350, 220, 450, 320, outline="#666", width=3)

        self.left_knob = self.canvas.create_oval(240, 260, 260, 280, fill="#00ff88")
        self.right_knob = self.canvas.create_oval(390, 260, 410, 280, fill="#00ff88")

        # D-Pad
        self.dpad = {
            "up": self.canvas.create_rectangle(150, 200, 180, 230, fill="#333"),
            "down": self.canvas.create_rectangle(150, 270, 180, 300, fill="#333"),
            "left": self.canvas.create_rectangle(120, 235, 150, 265, fill="#333"),
            "right": self.canvas.create_rectangle(180, 235, 210, 265, fill="#333"),
        }

        # Botones dinámicos (todos)
        self.button_visuals = {}
        base_x = 520
        base_y = 200

        for i in range(16):  # soporte hasta 16 botones
            x = base_x + (i % 4) * 35
            y = base_y + (i // 4) * 35
            self.button_visuals[i] = self.canvas.create_oval(
                x, y, x+25, y+25,
                fill="#333"
            )

    # --------------------------------------------------
    # LOOP ACTUALIZACIÓN
    # --------------------------------------------------

    def update_loop(self):

        if self.joystick:
            pygame.event.pump()

            info = f"Nombre: {self.joystick.get_name()}\n"
            info += f"Botones: {self.joystick.get_numbuttons()}\n"
            info += f"Ejes: {self.joystick.get_numaxes()}\n"
            info += f"Hats: {self.joystick.get_numhats()}\n\n"

            # -------- BOTONES --------
            for i in range(self.joystick.get_numbuttons()):
                pressed = self.joystick.get_button(i)
                info += f"Botón {i}: {'ON' if pressed else 'OFF'}\n"

                if i in self.button_visuals:
                    color = "#00ff88" if pressed else "#333"
                    self.canvas.itemconfig(self.button_visuals[i], fill=color)

            # -------- D-PAD (HAT) --------
            if self.joystick.get_numhats() > 0:
                hat = self.joystick.get_hat(0)

                up = hat[1] == 1
                down = hat[1] == -1
                left = hat[0] == -1
                right = hat[0] == 1

                self.canvas.itemconfig(self.dpad["up"], fill="#00ff88" if up else "#333")
                self.canvas.itemconfig(self.dpad["down"], fill="#00ff88" if down else "#333")
                self.canvas.itemconfig(self.dpad["left"], fill="#00ff88" if left else "#333")
                self.canvas.itemconfig(self.dpad["right"], fill="#00ff88" if right else "#333")

                info += f"\nDPad: {hat}"

            # -------- STICKS --------
            max_offset = 30

            if self.joystick.get_numaxes() >= 2:
                lx = self.joystick.get_axis(0)
                ly = self.joystick.get_axis(1)

                self.move_knob(self.left_knob, self.left_center, lx, ly, max_offset)

            if self.joystick.get_numaxes() >= 4:
                rx = self.joystick.get_axis(2)
                ry = self.joystick.get_axis(3)

                self.move_knob(self.right_knob, self.right_center, rx, ry, max_offset)

            self.info_panel.delete("1.0", "end")
            self.info_panel.insert("1.0", info)

        self.after(30, self.update_loop)

    # --------------------------------------------------

    def move_knob(self, knob, center, ax, ay, max_offset):
        new_x = center[0] + ax * max_offset
        new_y = center[1] + ay * max_offset

        self.canvas.coords(
            knob,
            new_x - 10, new_y - 10,
            new_x + 10, new_y + 10
        )

    # --------------------------------------------------

    def center_window(self, parent):
        parent.update_idletasks()

        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()

        w = 900
        h = 600

        x = px + (pw // 2) - (w // 2)
        y = py + (ph // 2) - (h // 2)

        self.geometry(f"{w}x{h}+{x}+{y}")