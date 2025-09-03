import os
import time
import zipfile
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import mss
from pynput.mouse import Controller
from PIL import Image

# --- Default Configuration ---
DEFAULT_SS_INTERVAL = 5
DEFAULT_ARCHIVE_INTERVAL = 600 # 10 minutes
DEFAULT_QUALITY = "Medium"
QUALITY_MAP = {"Low": 30, "Medium": 50, "High": 85}

# --- Folder Setup ---
TEMP_DIR = "temp_screenshots"
ARCHIVE_DIR = "archives"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)


class ScreenshotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot Utility")
        self.root.geometry("420x300")
        
        # --- State Variables ---
        self.is_running = False
        self.worker_thread = None
        self.stop_event = threading.Event()

        # --- GUI Variables ---
        self.ss_interval = tk.IntVar(value=DEFAULT_SS_INTERVAL)
        self.archive_interval = tk.IntVar(value=DEFAULT_ARCHIVE_INTERVAL)
        self.quality = tk.StringVar(value=DEFAULT_QUALITY)
        self.note = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready. Starting in unattended mode...")

        # --- Create and layout widgets ---
        self.create_widgets()

        # --- Bind closing event ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # --- Start in unattended mode ---
        self.root.after(2000, self.start_capture)

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Settings Frame
        settings_frame = ttk.LabelFrame(main_frame, text="Settings", padding="10")
        settings_frame.pack(fill=tk.X, pady=5)
        
        # Screenshot Interval
        ttk.Label(settings_frame, text="Screenshot Interval (sec):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.ss_interval_entry = ttk.Entry(settings_frame, textvariable=self.ss_interval, width=10)
        self.ss_interval_entry.grid(row=0, column=1, sticky=tk.W)

        # Archive Interval
        ttk.Label(settings_frame, text="Archive Interval (sec):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.archive_interval_entry = ttk.Entry(settings_frame, textvariable=self.archive_interval, width=10)
        self.archive_interval_entry.grid(row=1, column=1, sticky=tk.W)
        
        # Quality
        ttk.Label(settings_frame, text="Image Quality:").grid(row=0, column=2, sticky=tk.W, padx=(10,0))
        self.quality_menu = ttk.Combobox(settings_frame, textvariable=self.quality, values=list(QUALITY_MAP.keys()), width=8, state="readonly")
        self.quality_menu.grid(row=0, column=3, sticky=tk.W)
        
        # Note
        ttk.Label(settings_frame, text="Archive Note (optional):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.note_entry = ttk.Entry(settings_frame, textvariable=self.note, width=35)
        self.note_entry.grid(row=2, column=1, columnspan=3, sticky=tk.W)

        # Controls Frame
        controls_frame = ttk.Frame(main_frame, padding="10")
        controls_frame.pack(fill=tk.X, pady=10)
        
        self.start_button = ttk.Button(controls_frame, text="Start Capture", command=self.start_capture)
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.stop_button = ttk.Button(controls_frame, text="Stop Capture", command=self.stop_capture, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        # Status Bar
        status_bar = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_ui_state(self, running):
        """Enable/disable widgets based on capture state."""
        self.is_running = running
        state = tk.NORMAL if not running else tk.DISABLED
        
        self.start_button.config(state=state)
        self.ss_interval_entry.config(state=state)
        self.archive_interval_entry.config(state=state)
        self.quality_menu.config(state=state)
        self.note_entry.config(state=state)
        
        self.stop_button.config(state=tk.NORMAL if running else tk.DISABLED)

    def start_capture(self):
        if self.is_running:
            return
            
        self.update_ui_state(running=True)
        self.status_text.set("🚀 Starting capture...")
        self.stop_event.clear()

        # Get settings from GUI
        settings = {
            "ss_interval": self.ss_interval.get(),
            "archive_interval": self.archive_interval.get(),
            "quality": QUALITY_MAP[self.quality.get()],
            "note": self.note.get().strip()
        }

        self.worker_thread = threading.Thread(
            target=self.capture_loop, 
            args=(settings,), 
            daemon=True
        )
        self.worker_thread.start()

    def stop_capture(self):
        if not self.is_running:
            return
            
        self.status_text.set("🛑 Stopping... please wait for final archive.")
        self.stop_event.set()
        # The UI will re-enable once the thread has finished and called update_ui_state

    def on_closing(self):
        if self.is_running:
            if messagebox.askyesno("Confirm Exit", "Capture is running. Are you sure you want to exit? The current batch will be archived."):
                self.stop_capture()
                # Wait for thread to finish before destroying window
                self.root.after(100, self.check_thread_and_exit)
        else:
            self.root.destroy()
            
    def check_thread_and_exit(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.root.after(100, self.check_thread_and_exit)
        else:
            self.root.destroy()

    def capture_loop(self, settings):
        """The main worker function that runs in a separate thread."""
        mouse = Controller()
        screenshot_files = []
        archive_start_time = datetime.now()

        with mss.mss() as sct:
            while not self.stop_event.is_set():
                start_time = time.time()
                
                # Take screenshot
                active_monitor = self._get_active_monitor(sct, mouse)
                new_file = self._process_screenshot(sct, active_monitor, settings['quality'])
                if new_file:
                    screenshot_files.append(new_file)
                    self.status_text.set(f"📸 Captured {os.path.basename(new_file)}")
                
                # Check for archiving
                current_time = datetime.now()
                if (current_time - archive_start_time).total_seconds() >= settings['archive_interval']:
                    self.status_text.set("🗜️ Archiving screenshots...")
                    self._archive_and_cleanup(screenshot_files, archive_start_time, current_time, settings['note'])
                    screenshot_files = []
                    archive_start_time = datetime.now()

                # Wait for the next interval, accounting for processing time
                elapsed = time.time() - start_time
                wait_time = max(0, settings['ss_interval'] - elapsed)
                self.stop_event.wait(wait_time) # Use event.wait for a non-blocking sleep

        # Final cleanup when loop is stopped
        self.status_text.set("📦 Performing final archive...")
        self._archive_and_cleanup(screenshot_files, archive_start_time, datetime.now(), settings['note'])
        self.status_text.set("✅ Capture stopped. Ready to start again.")
        self.root.after(0, self.update_ui_state, False) # Update UI from main thread

    def _get_active_monitor(self, sct, mouse):
        mouse_pos = mouse.position
        for monitor in sct.monitors[1:]:
            if (monitor["left"] <= mouse_pos[0] < monitor["left"] + monitor["width"] and
                    monitor["top"] <= mouse_pos[1] < monitor["top"] + monitor["height"]):
                return monitor
        return sct.monitors[1]

    def _process_screenshot(self, sct, monitor, quality):
        try:
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            img = img.convert('L')
            img = img.resize((500, 310), Image.Resampling.LANCZOS)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            filename = os.path.join(TEMP_DIR, f"ss_{timestamp}.webp")
            img.save(filename, 'webp', quality=quality)
            return filename
        except Exception as e:
            self.status_text.set(f"❌ Error: {e}")
            return None

    def _archive_and_cleanup(self, files, start_dt, end_dt, note):
        if not files:
            return

        ts_format = f"{start_dt.strftime('%Y-%m-%d-%H%M')}-{end_dt.strftime('%H%M')}"
        zip_filename = f"{note}_{ts_format}.zip" if note else f"{ts_format}.zip"
        zip_filepath = os.path.join(ARCHIVE_DIR, zip_filename)

        try:
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                for file_path in files:
                    zipf.write(file_path, os.path.basename(file_path))
            
            for file_path in files:
                os.remove(file_path)
            self.status_text.set(f"✅ Archived to {zip_filename}")
        except Exception as e:
            self.status_text.set(f"❌ Archive Error: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenshotApp(root)
    root.mainloop()