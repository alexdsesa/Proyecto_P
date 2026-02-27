# ui/intro_screen.py
import os
import threading
import time
import tkinter as tk

# intentamos importar vlc
try:
    import vlc
    _HAS_VLC = True
except Exception:
    _HAS_VLC = False

class IntroWindow(tk.Tk):
    """
    Intro como ventana principal (Tk). Reproduce un video con python-vlc.
    Cuando termina (evento VLC EndReached) se detiene y se destruye,
    devolviendo el control al código que llamó a intro.mainloop().
    """

    def __init__(self, video_path: str, mute: bool = False, allow_skip: bool = True, timeout_fallback: int = 2000):
        super().__init__()
        self.video_path = video_path
        self.mute = mute
        self.allow_skip = allow_skip
        self.timeout_fallback = timeout_fallback  # ms en caso de fallback
        self.title("Intro")
        self.geometry("960x540")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self._on_skip)

        # frame contenedor para el video (usaremos su winfo_id)
        self.video_frame = tk.Frame(self, bg="black")
        self.video_frame.pack(fill="both", expand=True)

        # controles simples
        ctrl = tk.Frame(self, height=36)
        ctrl.pack(fill="x")
        if self.allow_skip:
            tk.Button(ctrl, text="Omitir intro", command=self._on_skip).pack(side="right", padx=8, pady=6)
        tk.Button(ctrl, text=("Silenciar" if not self.mute else "Activar sonido"), command=self._toggle_mute).pack(side="right", padx=8, pady=6)

        # Si no hay vlc o no existe el archivo -> fallback y cerrar rápido
        if (not _HAS_VLC) or (not os.path.isfile(self.video_path)):
            print("Intro: VLC no disponible o video no encontrado, saltando intro.")
            self.after(self.timeout_fallback, self._finish_and_close)
            return

        # Inicializar VLC con opciones seguras (sin HW acc. para evitar errores D3D)
        try:
            self.instance = vlc.Instance("--no-video-title-show", "--avcodec-hw=none", "--quiet")
            self.player = self.instance.media_player_new()
            media = self.instance.media_new(self.video_path)
            self.player.set_media(media)

            # asegurar que el handle esté disponible
            self.update_idletasks()
            handle = self.video_frame.winfo_id()
            if os.name == "nt":
                try:
                    self.player.set_hwnd(handle)
                except Exception as e:
                    print("Warning set_hwnd:", e)
            else:
                try:
                    self.player.set_xwindow(handle)
                except Exception as e:
                    print("Warning set_xwindow:", e)

            # evento fin de reproducción
            events = self.player.event_manager()
            events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end)

            # aplicar audio mute si se pidió
            self.player.audio_set_mute(self.mute)

            # reproducir en hilo separado para no bloquear el loop
            t = threading.Thread(target=self._play, daemon=True)
            t.start()

        except Exception as e:
            print("Intro: error inicializando VLC:", e)
            # fallback seguro
            self.after(self.timeout_fallback, self._finish_and_close)

    def _play(self):
        try:
            self.player.play()
            # si quieres, puedes esperar hasta que comience realmente
            time.sleep(0.1)
        except Exception as e:
            print("Intro play error:", e)
            self.after(0, self._finish_and_close)

    def _on_vlc_end(self, event):
        # llamado desde hilo de VLC -> usar after para volver al hilo de Tk
        self.after(0, self._finish_and_close)

    def _finish_and_close(self):
        try:
            if _HAS_VLC:
                try:
                    self.player.stop()
                except Exception:
                    pass
        except Exception:
            pass
        # destruimos la ventana; esto hará que intro.mainloop() termine
        try:
            self.destroy()
        except Exception:
            pass

    def _on_skip(self):
        # usuario solicita saltar
        try:
            if _HAS_VLC:
                self.player.stop()
        except Exception:
            pass
        self._finish_and_close()

    def _toggle_mute(self):
        self.mute = not self.mute
        try:
            if _HAS_VLC:
                self.player.audio_set_mute(self.mute)
        except Exception:
            pass