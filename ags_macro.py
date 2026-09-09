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


# --- 2. ТАБЛИЦА БАЛЛИСТИКИ И ИНТЕРПОЛЯЦИЯ ---
# Таблица, считанная с предоставленной фотографии
DATA_POINTS = [
    (280, 0), (325, 0.055), (350, 0.1), (375, 0.15), (400, 0.2), (425, 0.25),
    (450, 0.3), (475, 0.32), (500, 0.35), (525, 0.39), (550, 0.42), (575, 0.48),
    (600, 0.52), (625, 0.56), (650, 0.61), (675, 0.65), (700, 0.69), (725, 0.73),
    (750, 0.77), (775, 0.83), (800, 0.88), (825, 0.92), (850, 0.95), (875, 1.0),
    (900, 1.05), (925, 1.09), (950, 1.16), (975, 1.195), (1000, 1.24), (1025, 1.29),
    (1050, 1.33), (1075, 1.385), (1100, 1.43), (1125, 1.47), (1150, 1.54), (1175, 1.575),
    (1200, 1.65), (1225, 1.696), (1250, 1.76), (1275, 1.804), (1300, 1.86), (1325, 1.905),
    (1350, 1.98), (1375, 2.032), (1400, 2.07), (1425, 2.16), (1450, 2.21), (1475, 2.272),
    (1500, 2.34), (1525, 2.41), (1550, 2.45), (1575, 2.54), (1600, 2.60), (1625, 2.672),
    (1650, 2.73), (1675, 2.826), (1700, 2.92), (1725, 3.01), (1750, 3.12), (1775, 3.193),
    (1800, 3.30), (1825, 3.43), (1850, 3.55), (1875, 3.70), (1900, 3.84), (1915, 3.95),
    (1930, 4.1)
]

def get_time_for_distance(d):
    """Рассчитывает точное время зажатия с помощью линейной интерполяции между точками таблицы"""
    if d <= DATA_POINTS[0][0]: return DATA_POINTS[0][1]
    if d >= DATA_POINTS[-1][0]: return DATA_POINTS[-1][1]
    
    for i in range(len(DATA_POINTS)-1):
        d1, t1 = DATA_POINTS[i]
        d2, t2 = DATA_POINTS[i+1]
        if d1 <= d <= d2:
            # Математическая интерполяция
            fraction = (d - d1) / (d2 - d1)
            return t1 + fraction * (t2 - t1)
    return 0


# --- 3. ВЫСОКОТОЧНЫЙ ТАЙМЕР ---
def precise_sleep(duration):
    target = time.perf_counter() + duration
    while time.perf_counter() < target:
        pass 


class AGSMacroApp:
    def __init__(self, root):
        self.root = root
        
        # --- НАСТРОЙКИ ОКНА-ОВЕРЛЕЯ ---
        self.root.geometry("290x40")
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.9)
        self.root.overrideredirect(True) # Убираем рамки Windows
        
        self.saved_duration = None
        self.is_running = False

        # Фон (темная тема) для перетаскивания окна
        self.frame = tk.Frame(root, bg="#2b2b2b", highlightbackground="#555555", highlightthickness=1)
        self.frame.pack(expand=True, fill='both')

        self.frame.bind("<ButtonPress-1>", self.start_move)
        self.frame.bind("<ButtonRelease-1>", self.stop_move)
        self.frame.bind("<B1-Motion>", self.do_move)

        # Обработчик разворачивания (чтобы скрывать рамки при выходе из панели задач)
        self.root.bind("<Map>", self.on_map)

        # --- ИНТЕРФЕЙС ---
        # 1. Поле для дистанции (ввод метров)
        self.dist_var = tk.StringVar(value="1000")
        self.entry = tk.Entry(self.frame, textvariable=self.dist_var, width=5, justify='center', font=("Arial", 12, "bold"), bg="#1e1e1e", fg="white", insertbackground="white", bd=0)
        self.entry.pack(side=tk.LEFT, padx=(10, 0), pady=7)
        
        tk.Label(self.frame, text="м", bg="#2b2b2b", fg="gray", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=(2, 5))
        
        # 2. Кнопка "Расчет"
        self.btn_nav = tk.Button(self.frame, text="РАСЧЕТ", command=self.save_distance, font=("Arial", 9, "bold"), bg="#4CAF50", fg="white", activebackground="#45a049", bd=0, cursor="hand2", width=10)
        self.btn_nav.pack(side=tk.LEFT, padx=5, pady=7, fill=tk.Y)
        
        # 3. Кнопка "Закрыть (Крестик)"
        self.btn_close = tk.Button(self.frame, text=" ✖ ", command=self.root.destroy, font=("Arial", 10, "bold"), bg="#F44336", fg="white", activebackground="#D32F2F", bd=0, cursor="hand2")
        self.btn_close.pack(side=tk.RIGHT, padx=(0, 10), pady=7, fill=tk.Y)

        # 4. Кнопка "Свернуть" (_)
        self.btn_min = tk.Button(self.frame, text=" _ ", command=self.minimize_window, font=("Arial", 10, "bold"), bg="#555555", fg="white", activebackground="#777777", bd=0, cursor="hand2")
        self.btn_min.pack(side=tk.RIGHT, padx=(5, 5), pady=7, fill=tk.Y)

        # --- БИНДЫ ---
        # Биндим на скан-код 40 (соответствует английскому апострофу ' и русской 'э')
        keyboard.add_hotkey(40, self.on_hotkey_pressed)

        # --- ФОНОВЫЙ МОНИТОРИНГ ИГРЫ ---
        threading.Thread(target=self.monitor_game, daemon=True).start()

    # --- ЛОГИКА ПЕРЕТАСКИВАНИЯ И СВОРАЧИВАНИЯ ---
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

    def minimize_window(self):
        """Сворачивает приложение в панель задач"""
        # Возвращаем системные рамки, чтобы Windows мог свернуть приложение
        self.root.overrideredirect(False)
        self.root.iconify()

    def on_map(self, event):
        """Восстанавливает дизайн оверлея при разворачивании из панели задач"""
        if str(event.widget) == str(self.root):
            if not self.root.overrideredirect():
                self.root.update_idletasks()
                self.root.overrideredirect(True)

    # --- ЛОГИКА "РАСЧЕТА ПО ТАБЛИЦЕ" ---
    def save_distance(self):
        try:
            val = float(self.dist_var.get().replace(',', '.'))
            
            # Получаем время по интерполяции
            calc_time = get_time_for_distance(val)
            self.saved_duration = calc_time
            
            # Выводим время на кнопку (до 3 знаков после запятой)
            self.btn_nav.config(text=f"{calc_time:.3f}с", bg="#2196F3")
        except ValueError:
            self.btn_nav.config(text="ОШИБКА", bg="#FF9800")

    # --- ЛОГИКА МАКРОСА ---
    def on_hotkey_pressed(self):
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
            time.sleep(3)
            is_running = False
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'] and 'squad' in proc.info['name'].lower():
                        is_running = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    pass
            
            if is_running:
                game_detected = True
            elif game_detected and not is_running:
                os._exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = AGSMacroApp(root)
    root.mainloop()
