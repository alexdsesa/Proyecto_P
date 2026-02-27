# main.py (arranque)
import os
import tkinter as tk
from ui.intro_screen import IntroWindow
from ui.main_window import MainWindow  
def start_launcher_after_intro():
   
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    
    video_path = r"C:\Users\Alexander\Downloads\GAME LAUNCHER\assets\intro.mp4"

    
    intro = IntroWindow(video_path=video_path, mute=False, allow_skip=True)
    
    intro.mainloop()

   
    start_launcher_after_intro()

    

 
    
   