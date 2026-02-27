import customtkinter as ctk
import pygame

class ControllerWindow(ctk.CTkToplevel):

    def __init__(self, parent):
        super().__init__(parent)

        self.title("Controller Tester")
        self.geometry("600x500")

        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        self.lift()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

        pygame.init()
        pygame.joystick.init()

        self.joystick = None

        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()

        self.label = ctk.CTkLabel(self, text="Estado del Control", font=("Arial", 18))
        self.label.pack(pady=10)

        self.info = ctk.CTkTextbox(self, width=550, height=200)
        self.info.pack(pady=10)

        self.update_loop()

    def update_loop(self):

        if self.joystick:

            pygame.event.pump()

            text = ""

            for i in range(self.joystick.get_numbuttons()):
                if self.joystick.get_button(i):
                    text += f"Botón {i} PRESIONADO\n"

            for i in range(self.joystick.get_numaxes()):
                axis = round(self.joystick.get_axis(i), 2)
                text += f"Eje {i}: {axis}\n"

            self.info.delete("1.0", "end")
            self.info.insert("1.0", text)

        else:
            self.info.delete("1.0", "end")
            self.info.insert("1.0", "No hay control conectado")

        self.after(50, self.update_loop)