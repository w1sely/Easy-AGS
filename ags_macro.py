import tkinter as tk
import keyboard
import time
import threading
import sys
import ctypes
import os
import psutil

# --- 1. ПРОВЕРКА ПРАВ АДМИНА ---
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    if getattr(sys, 'frozen', False):
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv[1:]), None, 1)
    else:
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{sys.argv[0]}"', None, 1)
    sys.exit()

# --- 2. ВЫСОКОТОЧНЫЙ ТАЙМЕР ---
def precise_sleep(duration):
    target = time.perf_counter() + duration
    while time.perf_counter() < target:
        pass 

class AGSMacroApp:
    def __init__(self, root):
        self.root = root
        
        # --- НАСТРОЙКИ ОКНА-ОВЕРЛЕЯ ---
        self.root.geometry("240x40")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        self.root.overrideredirect(True) # Убираем стандартные рамки Windows для дизайна
        
        self.saved_duration = None
        self.is_running = False

        # Фон (темная тема) для перетаскивания окна мышкой
        self.frame = tk.Frame(root, bg="#2b2b2b", highlightbackground="#555555", highlightthickness=1)
        self.frame.pack(expand=True, fill='both')

        self.frame.bind("<ButtonPress-1>", self.start_move)
        self.frame.bind("<ButtonRelease-1>", self.stop_move)
        self.frame.bind("<B1-Motion>", self.do_move)

        # --- ИНТЕРФЕЙС ---
        # 1. Поле для времени
        self.time_var = tk.StringVar(value="0.70")
        self.entry = tk.Entry(self.frame, textvariable=self.time_var, width=5, justify='center', font=("Arial", 12, "bold"), bg="#1e1e1e", fg="white", insertbackground="white", bd=0)
        self.entry.pack(side=tk.LEFT, padx=(10, 5), pady=7)
        
        # 2. Кнопка "Наводка"
        self.btn_nav = tk.Button(self.frame, text="НАВОДКА", command=self.save_time, font=("Arial", 9, "bold"), bg="#4CAF50", fg="white", activebackground="#45a049", bd=0, cursor="hand2")
        self.btn_nav.pack(side=tk.LEFT, padx=5, pady=7, fill=tk.Y)
        
        # 3. Кнопка "Закрыть (Крестик)"
        self.btn_close = tk.Button(self.frame, text=" ✖ ", command=self.root.destroy, font=("Arial", 10, "bold"), bg="#F44336", fg="white", activebackground="#D32F2F", bd=0, cursor="hand2")
        self.btn_close.pack(side=tk.RIGHT, padx=(0, 10), pady=7, fill=tk.Y)

        # --- БИНДЫ ---
        # Биндим на английский апостроф ('), который соответствует русской 'э'
        keyboard.add_hotkey("'", self.on_hotkey_pressed)

        # --- ФОНОВЫЙ МОНИТОРИНГ ИГРЫ ---
        threading.Thread(target=self.monitor_game, daemon=True).start()

    # --- ЛОГИКА ПЕРЕТАСКИВАНИЯ ---
    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def stop_move(self, event):
        self.x = None
        self.y = None

    def do_move(self, event):
        if self.x is not None and self.y is not None:
            deltax = event.x - self.x
            deltay = event.y - self.y
            x = self.root.winfo_x() + deltax
            y = self.root.winfo_y() + deltay
            self.root.geometry(f"+{x}+{y}")

    # --- ЛОГИКА "ЗАПОМНИТЬ ВРЕМЯ" ---
    def save_time(self):
        try:
            val = float(self.time_var.get().replace(',', '.'))
            if 0 < val <= 10.0:
                self.saved_duration = val
                # Кнопка меняет цвет и текст, подтверждая запоминание
                self.btn_nav.config(text=f"Э = {val}с", bg="#2196F3")
            else:
                self.btn_nav.config(text="ОШИБКА", bg="#FF9800")
        except ValueError:
            self.btn_nav.config(text="ОШИБКА", bg="#FF9800")

    # --- ЛОГИКА МАКРОСА ---
    def on_hotkey_pressed(self):
        # Проверяем, нажали ли мы предварительно кнопку "Наводка"
        if self.saved_duration is None:
            return
        
        if not self.is_running:
            threading.Thread(target=self.macro_thread, daemon=True).start()
            
    def macro_thread(self):
        self.is_running = True
        try:
            keyboard.press('s')
            precise_sleep(self.saved_duration)
        finally:
            keyboard.release('s')
            self.is_running = False

    # --- АВТОМАТИЧЕСКОЕ ЗАКРЫТИЕ ПРИ ВЫХОДЕ ИЗ SQUAD ---
    def monitor_game(self):
        game_detected = False
        while True:
            time.sleep(3) # Проверяем каждые 3 секунды
            is_running = False
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and 'squad' in proc.info['name'].lower():
                        is_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if is_running:
                # Игра запущена и найдена
                game_detected = True
            elif game_detected and not is_running:
                # Игра БЫЛА запущена, но теперь процесс пропал (закрылась)
                os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = AGSMacroApp(root)
    root.mainloop()
