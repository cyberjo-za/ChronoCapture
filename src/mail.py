import os
import time
import zipfile
import configparser
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import mss
from pynput.mouse import Controller
from PIL import Image

# --- Default Configuration ---
DEFAULT_SS_INTERVAL = 5
DEFAULT_ARCHIVE_INTERVAL = 600 # 10 minutes
DEFAULT_QUALITY = "Medium"
QUALITY_MAP = {"Low": 30, "Medium": 50, "High": 85}
CONFIG_FILE = "config.ini"

# --- Folder Setup ---
TEMP_DIR = "temp_screenshots"
ARCHIVE_DIR = "archives"
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)


class ScreenshotApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Screenshot Utility")
        self.root.geometry("500x520")
        
        # --- State Variables ---
        self.capture_state = "stopped" # "stopped", "running", "paused"
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.time_log = []
        self.session_archives = []

        # --- GUI Variables ---
        self.name = tk.StringVar()
        self.company = tk.StringVar()
        self.ss_interval = tk.IntVar(value=DEFAULT_SS_INTERVAL)
        self.archive_interval = tk.IntVar(value=DEFAULT_ARCHIVE_INTERVAL)
        self.quality = tk.StringVar(value=DEFAULT_QUALITY)
        self.note = tk.StringVar()
        self.ticket_id = tk.StringVar()
        self.ticket_link = tk.StringVar()
        self.status_text = tk.StringVar(value="Ready to start capture.")

        # --- Load Config and Bind Saves ---
        self.config = configparser.ConfigParser()
        self.load_config()
        self.name.trace_add("write", lambda *args: self.save_config())
        self.company.trace_add("write", lambda *args: self.save_config())

        # --- Create and layout widgets ---
        self.setup_styles()
        self.create_widgets()

        # --- Bind closing event ---
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def load_config(self):
        """Loads user configuration from config.ini or creates it."""
        self.config.read(CONFIG_FILE)
        if 'User' not in self.config:
            self.config['User'] = {'Name': 'Anonymous', 'Company': 'None'}
            self.save_config()
        
        self.name.set(self.config.get('User', 'Name', fallback='Anonymous'))
        self.company.set(self.config.get('User', 'Company', fallback='None'))

    def save_config(self):
        """Saves current user settings to config.ini."""
        if 'User' not in self.config:
            self.config['User'] = {}
        self.config['User']['Name'] = self.name.get()
        self.config['User']['Company'] = self.company.get()
        with open(CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

    def setup_styles(self):
        """Configure custom ttk styles for a more modern look."""
        style = ttk.Style(self.root)
        style.theme_use('clam') # A cleaner, more modern theme

        # Style for buttons
        style.configure('TButton', padding=6, relief="flat", font=('Helvetica', 10))
        style.map('TButton',
                  foreground=[('pressed', 'black'), ('active', 'black')],
                  background=[('pressed', '!disabled', '#c0c0c0'), ('active', '#e0e0e0')])

        # Special style for the Start button
        style.configure('Start.TButton', foreground='white', background='#28a745') # Green
        style.map('Start.TButton',
                  background=[('pressed', '!disabled', '#1e7e34'), ('active', '#218838')])

        # Special style for the Stop button
        style.configure('Stop.TButton', foreground='white', background='#dc3545') # Red
        style.map('Stop.TButton',
                  background=[('pressed', '!disabled', '#b21f2d'), ('active', '#c82333')])

        style.configure('TLabelFrame', padding=10)
        style.configure('TLabelFrame.Label', font=('Helvetica', 11, 'bold'))

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._create_user_info_widgets(main_frame)
        self._create_ticket_info_widgets(main_frame)
        self._create_settings_widgets(main_frame)
        self._create_control_widgets(main_frame)
        self._create_status_bar()

    def _create_user_info_widgets(self, parent):
        user_frame = ttk.LabelFrame(parent, text="User Information")
        user_frame.pack(fill=tk.X, pady=5, padx=5)
        user_frame.columnconfigure(1, weight=1)
        
        ttk.Label(user_frame, text="Name:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        ttk.Entry(user_frame, textvariable=self.name).grid(row=0, column=1, sticky=tk.EW, padx=5)
        
        ttk.Label(user_frame, text="Company:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        ttk.Entry(user_frame, textvariable=self.company).grid(row=1, column=1, sticky=tk.EW, padx=5)

    def _create_ticket_info_widgets(self, parent):
        ticket_frame = ttk.LabelFrame(parent, text="Support Ticket (Optional)")
        ticket_frame.pack(fill=tk.X, pady=5, padx=5)
        ticket_frame.columnconfigure(1, weight=1)

        ttk.Label(ticket_frame, text="Ticket ID:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.ticket_id_entry = ttk.Entry(ticket_frame, textvariable=self.ticket_id)
        self.ticket_id_entry.grid(row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Label(ticket_frame, text="Ticket Link:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.ticket_link_entry = ttk.Entry(ticket_frame, textvariable=self.ticket_link)
        self.ticket_link_entry.grid(row=1, column=1, sticky=tk.EW, padx=5)

    def _create_settings_widgets(self, parent):
        settings_frame = ttk.LabelFrame(parent, text="Settings")
        settings_frame.pack(fill=tk.X, pady=5, padx=5)
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(3, weight=1)

        # --- Row 0: Screenshot Interval & Quality ---
        ttk.Label(settings_frame, text="SS Interval (s):").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        self.ss_interval_entry = ttk.Entry(settings_frame, textvariable=self.ss_interval, width=8)
        self.ss_interval_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 15))

        ttk.Label(settings_frame, text="Quality:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.quality_menu = ttk.Combobox(settings_frame, textvariable=self.quality, values=list(QUALITY_MAP.keys()), width=10, state="readonly")
        self.quality_menu.grid(row=0, column=3, sticky=tk.EW, padx=(0, 5))

        # --- Row 1: Archive Interval ---
        ttk.Label(settings_frame, text="Archive Interval (s):").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        self.archive_interval_entry = ttk.Entry(settings_frame, textvariable=self.archive_interval, width=8)
        self.archive_interval_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, 15))

        # --- Row 2: Archive Note ---
        ttk.Label(settings_frame, text="Note:").grid(row=2, column=0, sticky=tk.W, pady=5, padx=5)
        self.note_entry = ttk.Entry(settings_frame, textvariable=self.note)
        self.note_entry.grid(row=2, column=1, columnspan=3, sticky=tk.EW, padx=(0, 5))

    def _create_control_widgets(self, parent):
        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill=tk.X, pady=(10, 5), padx=5)

        self.start_button = ttk.Button(controls_frame, text="Start", command=self.start_capture, style='Start.TButton')
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.pause_button = ttk.Button(controls_frame, text="Pause", command=self.toggle_pause, state=tk.DISABLED)
        self.pause_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

        self.stop_button = ttk.Button(controls_frame, text="Stop", command=self.stop_capture, state=tk.DISABLED, style='Stop.TButton')
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)

    def _create_status_bar(self):
        status_bar = ttk.Label(self.root, textvariable=self.status_text, relief=tk.SUNKEN, anchor=tk.W, padding="2 5")
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def update_ui_state(self, new_state):
        """Enable/disable widgets based on capture state."""
        self.capture_state = new_state

        if new_state == "stopped":
            self.start_button.config(state=tk.NORMAL)
            self.pause_button.config(state=tk.DISABLED, text="Pause")
            self.stop_button.config(state=tk.DISABLED)
            for widget in [self.ss_interval_entry, self.archive_interval_entry, self.quality_menu, self.note_entry, self.ticket_id_entry, self.ticket_link_entry]:
                widget.config(state=tk.NORMAL)
        elif new_state == "running":
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL, text="Pause")
            self.stop_button.config(state=tk.NORMAL)
            for widget in [self.ss_interval_entry, self.archive_interval_entry, self.quality_menu, self.note_entry, self.ticket_id_entry, self.ticket_link_entry]:
                widget.config(state=tk.DISABLED)
        elif new_state == "paused":
            self.start_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.NORMAL, text="Resume")
            self.stop_button.config(state=tk.NORMAL)

    def start_capture(self):
        if self.capture_state != "stopped":
            return
            
        self.update_ui_state("running")
        self.status_text.set("🚀 Starting capture...")
        self.stop_event.clear()
        self.pause_event.clear()
        self.time_log = [("Session Start", datetime.now())]
        self.session_archives = []

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
        if self.capture_state == "stopped":
            return
            
        self.status_text.set("🛑 Stopping... please wait for final archive.")
        self.time_log.append(("Session Stop", datetime.now()))
        self.stop_event.set()
        self.pause_event.set() # Ensure paused thread continues to exit
        # The UI will re-enable once the thread has finished and called update_ui_state

    def toggle_pause(self):
        if self.capture_state == "running":
            self.update_ui_state("paused")
            self.pause_event.set()
            self.time_log.append(("Pause", datetime.now()))
            self.status_text.set("⏸️ Capture paused.")
        elif self.capture_state == "paused":
            self.update_ui_state("running")
            self.pause_event.clear()
            self.time_log.append(("Resume", datetime.now()))
            self.status_text.set("▶️ Capture resumed.")

    def on_closing(self):
        if self.capture_state != "stopped":
            if messagebox.askyesno("Confirm Exit", "Capture is running. Are you sure you want to exit? The current session will be archived."):
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
                
                # Handle pause state
                if self.pause_event.is_set():
                    # This blocks until pause_event.clear() is called
                    self.pause_event.wait()
                    continue # Re-check stop_event immediately after resuming

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
        self._archive_and_cleanup(screenshot_files, archive_start_time, datetime.now(), settings['note']) # Archive any remaining screenshots
        self._create_master_archive(settings['note'])
        self.status_text.set("✅ Capture stopped. Ready to start again.")
        self.root.after(0, self.update_ui_state, "stopped") # Update UI from main thread

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
        self.session_archives.append(zip_filepath)

        try:
            with zipfile.ZipFile(zip_filepath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zipf:
                for file_path in files:
                    zipf.write(file_path, os.path.basename(file_path))
            
            for file_path in files:
                os.remove(file_path)
            self.status_text.set(f"✅ Archived to {zip_filename}")
        except Exception as e:
            self.status_text.set(f"❌ Archive Error: {e}")

    def _create_master_archive(self, note):
        if not self.time_log:
            return

        start_dt = self.time_log[0][1]
        end_dt = self.time_log[-1][1]
        ts_format = f"{start_dt.strftime('%Y-%m-%d-%H%M')}-{end_dt.strftime('%H%M')}"
        master_zip_filename = f"MASTER_{note}_{ts_format}.zip" if note else f"MASTER_{ts_format}.zip"
        master_zip_filepath = os.path.join(ARCHIVE_DIR, master_zip_filename)

        try:
            with zipfile.ZipFile(master_zip_filepath, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as master_zipf:
                # 1. Add readme.txt
                readme_content = self._generate_readme()
                master_zipf.writestr("readme.txt", readme_content)

                # 2. Add all session archives and then delete them
                for archive_path in self.session_archives:
                    if os.path.exists(archive_path):
                        master_zipf.write(archive_path, os.path.basename(archive_path))
                        os.remove(archive_path)
            self.status_text.set(f"📦 Master archive created: {master_zip_filename}")
        except Exception as e:
            self.status_text.set(f"❌ Master Archive Error: {e}")

    def _generate_readme(self):
        # --- Calculate Durations ---
        total_duration = timedelta()
        active_duration = timedelta()
        paused_duration = timedelta()
        last_time = None
        last_event = None

        if self.time_log:
            total_duration = self.time_log[-1][1] - self.time_log[0][1]
            
            for event, dt in self.time_log:
                if last_time:
                    delta = dt - last_time
                    if last_event in ("Session Start", "Resume"):
                        active_duration += delta
                    elif last_event == "Pause":
                        paused_duration += delta
                last_time = dt
                last_event = event

        def format_timedelta(td):
            """Formats a timedelta into a human-readable string."""
            total_seconds = int(td.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours}h {minutes}m {seconds}s"

        # --- Build Readme Content ---
        lines = [
            f"User: {self.name.get()}",
            f"Company: {self.company.get()}",
            f"Note: {self.note.get() or 'N/A'}",
            f"Support Ticket ID: {self.ticket_id.get() or 'N/A'}",
            f"Support Ticket Link: {self.ticket_link.get() or 'N/A'}",
            "\n--- Session Summary ---",
            f"Total Duration:       {format_timedelta(total_duration)}",
            f"Active Capture Time:  {format_timedelta(active_duration)}",
            f"Paused Time:          {format_timedelta(paused_duration)}",
            "\n--- Session Timeline ---\n"
        ]
        for event, dt in self.time_log:
            lines.append(f"{dt.strftime('%Y-%m-%d %H:%M:%S')} - {event}")
        return "\n".join(lines)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScreenshotApp(root)
    root.mainloop()