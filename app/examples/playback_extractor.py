# ------------< PLAYBACK / VIDEO RECORDING TESTS >-----------------

import os
import time
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from app.config.config import AppConfig
from app.hikvision_sdk_package.hikvision_sdk import HikvisionSDK
from app.hikvision_sdk_package.nvr_camera_channel_mapping import get_camera_channel


class HikvisionDownloaderGUI:

    def __init__(self, root):

        self.root = root
        self.root.title("Hikvision Recording Downloader")
        self.root.geometry("800x650")
        self.root.resizable(False, False)
        
        # Dark Teal Blue Theme Colors
        self.colors = {
            'bg': '#0a1e2b',
            'bg_light': '#123140',
            'bg_lighter': '#1a4054',
            'fg': '#e0f0f5',
            'fg_dim': '#8ab4c9',
            'accent_primary': '#00b4d8',
            'accent_secondary': '#0077b6',
            'accent_hover': '#48cae4',
            'button': '#1a4054',
            'button_hover': '#2a5a7a',
            'entry_bg': '#0d2a3d',
            'entry_fg': '#e0f0f5',
            'frame_bg': '#0a1e2b',
            'border': '#1a4054',
            'progress_bg': '#0d2a3d',
            'progress_fg': '#00b4d8',
            'title': '#00b4d8',
            'success': '#00d4a0',
            'error': '#ff6b6b'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # Set cursor for root window
        self.root.config(cursor="arrow")
        
        # Style configuration
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        # Configure styles with teal theme
        self.style.configure('TLabel', 
                           background=self.colors['bg'],
                           foreground=self.colors['fg'],
                           font=('Segoe UI', 10))
        
        self.style.configure('TFrame', 
                           background=self.colors['bg'])
        
        self.style.configure('TLabelframe', 
                           background=self.colors['bg'],
                           foreground=self.colors['fg'],
                           font=('Segoe UI', 10, 'bold'),
                           borderwidth=2,
                           relief='solid')
        
        self.style.configure('TLabelframe.Label',
                           background=self.colors['bg'],
                           foreground=self.colors['accent_primary'],
                           font=('Segoe UI', 10, 'bold'))
        
        self.style.configure('TButton',
                           background=self.colors['button'],
                           foreground=self.colors['fg'],
                           font=('Segoe UI', 10, 'bold'),
                           borderwidth=2,
                           focusthickness=3,
                           focuscolor=self.colors['accent_primary'],
                           padding=(15, 5),
                           cursor="hand2")
        
        self.style.map('TButton',
                      background=[('active', self.colors['button_hover'])],
                      foreground=[('active', self.colors['fg'])],
                      bordercolor=[('active', self.colors['accent_primary'])])
        
        self.style.configure('TEntry',
                           background=self.colors['entry_bg'],
                           foreground=self.colors['entry_fg'],
                           fieldbackground=self.colors['entry_bg'],
                           borderwidth=2,
                           font=('Segoe UI', 10),
                           padding=(5, 3),
                           cursor="xterm",
                           insertcolor=self.colors['accent_primary'],  # Blinking cursor color
                           insertwidth=2)  # Cursor width
        
        self.style.map('TEntry',
                      bordercolor=[('focus', self.colors['accent_primary'])])
        
        self.style.configure('TProgressbar',
                           background=self.colors['progress_fg'],
                           troughcolor=self.colors['progress_bg'],
                           borderwidth=2,
                           thickness=20)
        
        # Custom style for small entry boxes
        self.style.configure('Small.TEntry',
                           background=self.colors['entry_bg'],
                           foreground=self.colors['entry_fg'],
                           fieldbackground=self.colors['entry_bg'],
                           borderwidth=2,
                           font=('Segoe UI', 10),
                           padding=(3, 2),
                           width=8,
                           cursor="xterm",
                           insertcolor=self.colors['accent_primary'],  # Blinking cursor color
                           insertwidth=2)  # Cursor width

        cfg = AppConfig()

        self.nvr_ip = cfg.get("NVR", "IP")
        self.nvr_port = cfg.get("NVR", "PORT", cast=int)
        self.username = cfg.get("NVR", "USERNAME")
        self.password = cfg.get("NVR", "PASSWORD")
        self.default_root = cfg.get("PATHS", "ROOT")

        self.hik = None
        self.logged_in = False
        self.downloading = False
        self.stop_download = False

        self.build_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    ##############################################################
    
    def get_camera_ip(self):
        """Get camera IP from separate fields"""
        ip_parts = [
            self.camera_ip_1.get().strip(),
            self.camera_ip_2.get().strip(),
            self.camera_ip_3.get().strip(),
            self.camera_ip_4.get().strip()
        ]
        return '.'.join(ip_parts)
    
    def get_date(self):
        """Get date from separate fields in dd-mm-yyyy format"""
        day = self.date_day.get().strip().zfill(2)
        month = self.date_month.get().strip().zfill(2)
        year = self.date_year.get().strip()
        return f"{day}-{month}-{year}"
    
    def get_start_time(self):
        """Get start time in HH:MM format"""
        hour = self.start_hour.get().strip().zfill(2)
        minute = self.start_minute.get().strip().zfill(2)
        return f"{hour}:{minute}"
    
    def get_end_time(self):
        """Get end time in HH:MM format"""
        hour = self.end_hour.get().strip().zfill(2)
        minute = self.end_minute.get().strip().zfill(2)
        return f"{hour}:{minute}"
    
    def validate_ip_part(self, part):
        """Validate IP address part (0-255)"""
        if not part:
            return False
        try:
            num = int(part)
            return 0 <= num <= 255
        except ValueError:
            return False
    
    def validate_date_part(self, part, min_val, max_val):
        """Validate date part (day/month)"""
        if not part:
            return False
        try:
            num = int(part)
            return min_val <= num <= max_val
        except ValueError:
            return False
    
    def validate_time_part(self, part, min_val, max_val):
        """Validate time part (hour/minute)"""
        if not part:
            return False
        try:
            num = int(part)
            return min_val <= num <= max_val
        except ValueError:
            return False
    
    def validate_camera_ip(self):
        """Validate full camera IP"""
        parts = [
            self.camera_ip_1.get().strip(),
            self.camera_ip_2.get().strip(),
            self.camera_ip_3.get().strip(),
            self.camera_ip_4.get().strip()
        ]
        
        if not all(parts):
            return False, "All IP parts are required"
        
        for i, part in enumerate(parts):
            if not self.validate_ip_part(part):
                return False, f"Invalid IP part {i+1}: must be 0-255"
        
        return True, ""
    
    def validate_date_fields(self):
        """Validate date fields"""
        day = self.date_day.get().strip()
        month = self.date_month.get().strip()
        year = self.date_year.get().strip()
        
        if not day or not month or not year:
            return False, "All date fields are required"
        
        if not self.validate_date_part(day, 1, 31):
            return False, "Invalid day: must be 1-31"
        
        if not self.validate_date_part(month, 1, 12):
            return False, "Invalid month: must be 1-12"
        
        if len(year) != 4 or not year.isdigit():
            return False, "Invalid year: must be 4 digits"
        
        # Validate actual date
        try:
            datetime(int(year), int(month), int(day))
        except ValueError:
            return False, "Invalid date (e.g., 31-02-2026 is not valid)"
        
        return True, ""
    
    def validate_time_fields(self, hour_part, minute_part, field_name):
        """Validate time fields"""
        hour = hour_part.get().strip()
        minute = minute_part.get().strip()
        
        if not hour or not minute:
            return False, f"All {field_name} fields are required"
        
        if not self.validate_time_part(hour, 0, 23):
            return False, f"Invalid {field_name} hour: must be 0-23"
        
        if not self.validate_time_part(minute, 0, 59):
            return False, f"Invalid {field_name} minute: must be 0-59"
        
        return True, ""

    def login_nvr(self):
        
        # Change cursor to watch during login
        self.root.config(cursor="watch")
        
        if self.logged_in:
            messagebox.showinfo(
                "Already Logged In",
                "NVR session is already active."
            )
            self.root.config(cursor="arrow")
            return

        try:

            self.status.set("Connecting to NVR...")
            self.progress['value'] = 0

            self.hik = HikvisionSDK(
                nvrs=[
                    {
                        "ip": self.nvr_ip,
                        "port": self.nvr_port,
                        "username": self.username,
                        "password": self.password,
                    }
                ]
            )

            self.logged_in = True

            self.download_btn.config(state=tk.NORMAL)
            self.login_btn.config(state=tk.DISABLED)

            self.status.set("Connected to NVR ✓")
            self.status_label.configure(foreground=self.colors['success'])

            messagebox.showinfo(
                "Success",
                "Successfully logged into the NVR."
            )

        except Exception as e:

            self.status.set("Login Failed ✗")
            self.status_label.configure(foreground=self.colors['error'])

            messagebox.showerror(
                "Login Failed",
                str(e)
            )
        
        finally:
            # Restore cursor
            self.root.config(cursor="arrow")

    ##############################################################

    def build_ui(self):
        
        # Main container with padding
        main_container = ttk.Frame(self.root)
        main_container.pack(fill="both", expand=True, padx=25, pady=20)
        
        # Title with teal accent
        title_frame = ttk.Frame(main_container)
        title_frame.pack(fill="x", pady=(0, 20))
        
        title_label = tk.Label(title_frame, 
                               text="NVR Recording Downloader",
                               font=('Segoe UI', 18, 'bold'),
                               fg=self.colors['accent_primary'],
                               bg=self.colors['bg'],
                               cursor="xterm")
        title_label.pack()
        
        subtitle_label = tk.Label(title_frame, 
                                 text="Hikvision Video Playback & Recording Tool",
                                 font=('Segoe UI', 10),
                                 fg=self.colors['fg_dim'],
                                 bg=self.colors['bg'],
                                 cursor="xterm")
        subtitle_label.pack()

        # Recording Information Frame
        frame = ttk.LabelFrame(main_container, text="📹 Recording Information", padding=20)
        frame.pack(fill="x", pady=(0, 15))
        
        # Camera IP with separate boxes
        ip_frame = ttk.Frame(frame)
        ip_frame.pack(fill="x", pady=5)
        
        ip_label = tk.Label(ip_frame, 
                           text="Camera IP:",
                           font=('Segoe UI', 10),
                           fg=self.colors['fg'],
                           bg=self.colors['bg'],
                           cursor="xterm")
        ip_label.pack(side="left", padx=(0, 15))
        
        self.camera_ip_1 = ttk.Entry(ip_frame, style='Small.TEntry', width=5)
        self.camera_ip_1.pack(side="left", padx=2)
        self.camera_ip_1.insert(0, "192")
        self.camera_ip_1.focus_set()  # Set focus to first entry
        # Select all text on focus
        self.camera_ip_1.bind('<FocusIn>', lambda e: self.camera_ip_1.select_range(0, tk.END))
        
        dot_label1 = tk.Label(ip_frame, 
                             text=".", 
                             font=('Segoe UI', 14, 'bold'),
                             fg=self.colors['accent_primary'],
                             bg=self.colors['bg'],
                             cursor="xterm")
        dot_label1.pack(side="left")
        
        self.camera_ip_2 = ttk.Entry(ip_frame, style='Small.TEntry', width=5)
        self.camera_ip_2.pack(side="left", padx=2)
        self.camera_ip_2.insert(0, "168")
        self.camera_ip_2.bind('<FocusIn>', lambda e: self.camera_ip_2.select_range(0, tk.END))
        
        dot_label2 = tk.Label(ip_frame, 
                             text=".",
                             font=('Segoe UI', 14, 'bold'),
                             fg=self.colors['accent_primary'],
                             bg=self.colors['bg'],
                             cursor="xterm")
        dot_label2.pack(side="left")
        
        self.camera_ip_3 = ttk.Entry(ip_frame, style='Small.TEntry', width=5)
        self.camera_ip_3.pack(side="left", padx=2)
        self.camera_ip_3.insert(0, "1")
        self.camera_ip_3.bind('<FocusIn>', lambda e: self.camera_ip_3.select_range(0, tk.END))
        
        dot_label3 = tk.Label(ip_frame, 
                             text=".",
                             font=('Segoe UI', 14, 'bold'),
                             fg=self.colors['accent_primary'],
                             bg=self.colors['bg'],
                             cursor="xterm")
        dot_label3.pack(side="left")
        
        self.camera_ip_4 = ttk.Entry(ip_frame, style='Small.TEntry', width=5)
        self.camera_ip_4.pack(side="left", padx=2)
        self.camera_ip_4.insert(0, "101")
        self.camera_ip_4.bind('<FocusIn>', lambda e: self.camera_ip_4.select_range(0, tk.END))
        
        hint_label = tk.Label(ip_frame, 
                             text="(0-255 each)",
                             fg=self.colors['fg_dim'],
                             bg=self.colors['bg'],
                             font=('Segoe UI', 8),
                             cursor="xterm")
        hint_label.pack(side="left", padx=(10, 0))
        
        # Date with separate boxes
        date_frame = ttk.Frame(frame)
        date_frame.pack(fill="x", pady=8)
        
        date_label = tk.Label(date_frame, 
                             text="Date:",
                             font=('Segoe UI', 10),
                             fg=self.colors['fg'],
                             bg=self.colors['bg'],
                             cursor="xterm")
        date_label.pack(side="left", padx=(0, 15))
        
        self.date_day = ttk.Entry(date_frame, style='Small.TEntry', width=4)
        self.date_day.pack(side="left", padx=2)
        self.date_day.insert(0, "27")
        self.date_day.bind('<FocusIn>', lambda e: self.date_day.select_range(0, tk.END))
        
        dash_label1 = tk.Label(date_frame, 
                              text="−",
                              font=('Segoe UI', 14, 'bold'),
                              fg=self.colors['accent_primary'],
                              bg=self.colors['bg'],
                              cursor="xterm")
        dash_label1.pack(side="left")
        
        self.date_month = ttk.Entry(date_frame, style='Small.TEntry', width=4)
        self.date_month.pack(side="left", padx=2)
        self.date_month.insert(0, "07")
        self.date_month.bind('<FocusIn>', lambda e: self.date_month.select_range(0, tk.END))
        
        dash_label2 = tk.Label(date_frame, 
                              text="−",
                              font=('Segoe UI', 14, 'bold'),
                              fg=self.colors['accent_primary'],
                              bg=self.colors['bg'],
                              cursor="xterm")
        dash_label2.pack(side="left")
        
        self.date_year = ttk.Entry(date_frame, style='Small.TEntry', width=6)
        self.date_year.pack(side="left", padx=2)
        self.date_year.insert(0, "2026")
        self.date_year.bind('<FocusIn>', lambda e: self.date_year.select_range(0, tk.END))
        
        date_hint = tk.Label(date_frame, 
                            text="(DD-MM-YYYY)",
                            fg=self.colors['fg_dim'],
                            bg=self.colors['bg'],
                            font=('Segoe UI', 8),
                            cursor="xterm")
        date_hint.pack(side="left", padx=(10, 0))
        
        # Time with separate boxes
        time_frame = ttk.Frame(frame)
        time_frame.pack(fill="x", pady=8)
        
        # Start Time
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(side="left", padx=(0, 30))
        
        start_label = tk.Label(start_frame, 
                              text="Start:",
                              font=('Segoe UI', 10),
                              fg=self.colors['fg'],
                              bg=self.colors['bg'],
                              cursor="xterm")
        start_label.pack(side="left", padx=(0, 10))
        
        self.start_hour = ttk.Entry(start_frame, style='Small.TEntry', width=4)
        self.start_hour.pack(side="left", padx=2)
        self.start_hour.insert(0, "09")
        self.start_hour.bind('<FocusIn>', lambda e: self.start_hour.select_range(0, tk.END))
        
        colon_label1 = tk.Label(start_frame, 
                               text=":",
                               font=('Segoe UI', 14, 'bold'),
                               fg=self.colors['accent_primary'],
                               bg=self.colors['bg'],
                               cursor="xterm")
        colon_label1.pack(side="left")
        
        self.start_minute = ttk.Entry(start_frame, style='Small.TEntry', width=4)
        self.start_minute.pack(side="left", padx=2)
        self.start_minute.insert(0, "00")
        self.start_minute.bind('<FocusIn>', lambda e: self.start_minute.select_range(0, tk.END))
        
        time_hint = tk.Label(start_frame, 
                            text="(HH:MM)",
                            fg=self.colors['fg_dim'],
                            bg=self.colors['bg'],
                            font=('Segoe UI', 8),
                            cursor="xterm")
        time_hint.pack(side="left", padx=(5, 0))
        
        # End Time
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(side="left")
        
        end_label = tk.Label(end_frame, 
                            text="End:",
                            font=('Segoe UI', 10),
                            fg=self.colors['fg'],
                            bg=self.colors['bg'],
                            cursor="xterm")
        end_label.pack(side="left", padx=(0, 10))
        
        self.end_hour = ttk.Entry(end_frame, style='Small.TEntry', width=4)
        self.end_hour.pack(side="left", padx=2)
        self.end_hour.insert(0, "09")
        self.end_hour.bind('<FocusIn>', lambda e: self.end_hour.select_range(0, tk.END))
        
        colon_label2 = tk.Label(end_frame, 
                               text=":",
                               font=('Segoe UI', 14, 'bold'),
                               fg=self.colors['accent_primary'],
                               bg=self.colors['bg'],
                               cursor="xterm")
        colon_label2.pack(side="left")
        
        self.end_minute = ttk.Entry(end_frame, style='Small.TEntry', width=4)
        self.end_minute.pack(side="left", padx=2)
        self.end_minute.insert(0, "05")
        self.end_minute.bind('<FocusIn>', lambda e: self.end_minute.select_range(0, tk.END))
        
        time_hint2 = tk.Label(end_frame, 
                             text="(HH:MM)",
                             fg=self.colors['fg_dim'],
                             bg=self.colors['bg'],
                             font=('Segoe UI', 8),
                             cursor="xterm")
        time_hint2.pack(side="left", padx=(5, 0))

        # Output Frame
        out = ttk.LabelFrame(main_container, text="📁 Output Directory", padding=20)
        out.pack(fill="x", pady=(0, 15))
        
        out.columnconfigure(0, weight=1)
        
        self.output = ttk.Entry(out, width=55)
        self.output.insert(
            0,
            os.path.join(self.default_root, "nvr_downloads"),
        )
        self.output.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="ew")
        self.output.bind('<FocusIn>', lambda e: self.output.select_range(0, tk.END))
        
        browse_btn = ttk.Button(
            out,
            text="Browse",
            command=self.browse,
            width=10
        )
        browse_btn.grid(row=0, column=1, pady=5)

        # Button Frame
        button_frame = ttk.Frame(main_container)
        button_frame.pack(pady=15)
        
        self.login_btn = ttk.Button(
            button_frame,
            text="🔑 Login to NVR",
            width=18,
            command=self.login_nvr
        )
        self.login_btn.pack(side="left", padx=5)
        
        self.download_btn = ttk.Button(
            button_frame,
            text="⬇️ Download Recording",
            width=26,
            command=self.start_download,
            state=tk.DISABLED
        )
        self.download_btn.pack(side="left", padx=5)
        
        self.quit_btn = ttk.Button(
            button_frame,
            text="🚪 Quit & Logout",
            width=18,
            command=self.quit_application
        )
        self.quit_btn.pack(side="left", padx=5)
        
        # Progress Frame
        frame2 = ttk.LabelFrame(main_container, text="📊 Progress", padding=20)
        frame2.pack(fill="x", pady=(0, 10))
        
        self.progress = ttk.Progressbar(
            frame2,
            orient="horizontal",
            length=600,
            mode="determinate",
            style="TProgressbar"
        )
        self.progress.pack(fill="x", pady=(0, 10))
        
        # Add percentage label
        self.progress_label = tk.Label(frame2,
                                      text="0%",
                                      font=('Segoe UI', 10, 'bold'),
                                      fg=self.colors['accent_primary'],
                                      bg=self.colors['bg'],
                                      cursor="xterm")
        self.progress_label.pack(anchor="e", pady=(0, 5))
        
        self.status = tk.StringVar(value="🟢 Ready")
        self.status_label = tk.Label(frame2, 
                                    textvariable=self.status,
                                    font=('Segoe UI', 9),
                                    fg=self.colors['fg_dim'],
                                    bg=self.colors['bg'],
                                    cursor="xterm")
        self.status_label.pack(anchor="w")
        
        # Bind Tab key to navigate through entry fields
        self.bind_tab_navigation()

    ##############################################################
    
    def bind_tab_navigation(self):
        """Bind Tab key for navigation between entry fields"""
        entries = [
            self.camera_ip_1, self.camera_ip_2, self.camera_ip_3, self.camera_ip_4,
            self.date_day, self.date_month, self.date_year,
            self.start_hour, self.start_minute,
            self.end_hour, self.end_minute,
            self.output
        ]
        
        for i, entry in enumerate(entries):
            if i < len(entries) - 1:
                entry.bind('<Tab>', lambda e, next_entry=entries[i+1]: 
                          (next_entry.focus_set(), next_entry.select_range(0, tk.END), 'break'))
                entry.bind('<Return>', lambda e, next_entry=entries[i+1]: 
                          (next_entry.focus_set(), next_entry.select_range(0, tk.END), 'break'))
        
        # Last entry focuses on download button
        if entries:
            entries[-1].bind('<Tab>', lambda e: (self.download_btn.focus_set(), 'break'))
            entries[-1].bind('<Return>', lambda e: (self.download_btn.focus_set(), 'break'))

    ##############################################################

    def browse(self):
        
        # Change cursor to watch during directory browsing
        self.root.config(cursor="watch")
        
        folder = filedialog.askdirectory()

        if folder:
            self.output.delete(0, tk.END)
            self.output.insert(0, folder)
        
        # Restore cursor
        self.root.config(cursor="arrow")

    ##############################################################

    def start_download(self):
        
        # Validate Camera IP
        valid, msg = self.validate_camera_ip()
        if not valid:
            messagebox.showerror("Validation Error", msg)
            return
        
        # Validate Date
        valid, msg = self.validate_date_fields()
        if not valid:
            messagebox.showerror("Validation Error", msg)
            return
        
        # Validate Start Time
        valid, msg = self.validate_time_fields(self.start_hour, self.start_minute, "start")
        if not valid:
            messagebox.showerror("Validation Error", msg)
            return
        
        # Validate End Time
        valid, msg = self.validate_time_fields(self.end_hour, self.end_minute, "end")
        if not valid:
            messagebox.showerror("Validation Error", msg)
            return
        
        # Validate start time < end time
        start_hour = int(self.start_hour.get().strip())
        start_minute = int(self.start_minute.get().strip())
        end_hour = int(self.end_hour.get().strip())
        end_minute = int(self.end_minute.get().strip())
        
        if start_hour > end_hour or (start_hour == end_hour and start_minute >= end_minute):
            messagebox.showerror("Validation Error", "Start time must be before end time.")
            return

        # Disable download button during download
        self.download_btn.config(state=tk.DISABLED)
        self.downloading = True
        self.stop_download = False
        
        # Reset progress
        self.progress['value'] = 0
        self.progress_label.config(text="0%")
        
        # Change cursor to watch during download
        self.root.config(cursor="watch")
        
        threading.Thread(
            target=self.download_recording,
            daemon=True,
        ).start()

    ##############################################################

    def update_progress(self, percent, text):
        """Update progress bar and status text"""
        self.root.after(
            0,
            lambda: self._update_progress_safe(percent, text)
        )
    
    def _update_progress_safe(self, percent, text):
        """Safe progress update in main thread"""
        if percent < 0:
            percent = 0
        elif percent > 100:
            percent = 100
            
        self.progress.configure(value=percent)
        self.progress_label.config(text=f"{percent:.0f}%")
        self.status.set(text)
        
        # Update color based on progress
        if percent == 100:
            self.status_label.configure(foreground=self.colors['success'])
            # Restore cursor when download completes
            self.root.config(cursor="arrow")
        elif percent > 0:
            self.status_label.configure(foreground=self.colors['fg'])
        else:
            self.status_label.configure(foreground=self.colors['fg_dim'])

    ##############################################################

    def download_recording(self):

        try:
            if not self.logged_in:
                self.root.after(0, lambda: messagebox.showerror(
                    "Not Logged In",
                    "Please login to the NVR first."
                ))
                self.downloading = False
                self.download_btn.config(state=tk.NORMAL)
                self.root.config(cursor="arrow")
                return

            camera_ip = self.get_camera_ip()
            date = self.get_date()
            start = self.get_start_time()
            end = self.get_end_time()
            output_dir = self.output.get().strip()

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            channel = get_camera_channel(
                self.nvr_ip,
                camera_ip,
            )

            if channel is None:
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    "Camera channel not found.",
                ))
                self.downloading = False
                self.download_btn.config(state=tk.NORMAL)
                self.root.config(cursor="arrow")
                return

            current_time = datetime.now().strftime("%H%M%S")

            save_path = os.path.join(
                output_dir,
                f"{camera_ip}_{channel}_{date.replace('-', '')}_{current_time}.mp4",
            )

            self.update_progress(5, "⏳ Starting download...")

            handle = self.hik.get_recording(
                nvr_ip=self.nvr_ip,
                channel=channel,
                start_time=start,
                end_time=end,
                date=date,
                save_path=save_path,
            )

            if handle < 0:
                self.update_progress(0, "❌ Failed to start download.")
                self.downloading = False
                self.download_btn.config(state=tk.NORMAL)
                self.root.config(cursor="arrow")
                return

            last_percent = 0
            
            while not self.stop_download:

                percent, path = self.hik.get_download_progress(
                    self.nvr_ip,
                    channel,
                )

                if percent < 0:
                    self.update_progress(0, "❌ Download failed.")
                    break

                # Only update if percent changed (reduce UI updates)
                if abs(percent - last_percent) >= 1 or percent >= 100:
                    self.update_progress(percent, f"⏳ Downloading... {percent:.0f}%")
                    last_percent = percent

                if percent >= 100:
                    self.hik.stop_download(
                        self.nvr_ip,
                        channel,
                    )
                    self.update_progress(100, f"✅ Completed\n{path}")
                    break

                time.sleep(0.5)

            # Check if stopped by user
            if self.stop_download:
                self.hik.stop_download(self.nvr_ip, channel)
                self.update_progress(0, "⏹️ Download stopped by user.")
                self.root.config(cursor="arrow")

        except Exception as e:
            self.update_progress(0, f"❌ {str(e)}")
            self.root.config(cursor="arrow")
        
        finally:
            self.downloading = False
            self.download_btn.config(state=tk.NORMAL if self.logged_in else tk.DISABLED)
            self.root.config(cursor="arrow")

    ##############################################################
    
    def quit_application(self):
        """Quit application and logout from NVR"""
        if self.downloading:
            # Ask user if they want to stop the download
            if not messagebox.askyesno("Download in Progress", 
                                      "A download is currently in progress. Stop download and quit?"):
                return
            self.stop_download = True
            # Change cursor to watch during logout
            self.root.config(cursor="watch")
        
        # Logout from NVR
        if self.hik is not None:
            try:
                self.status.set("Logging out...")
                self.hik.close()
                self.logged_in = False
                self.status.set("Logged out ✓")
                messagebox.showinfo("Success", "Successfully logged out from NVR.")
            except Exception as e:
                messagebox.showerror("Logout Error", f"Error during logout: {e}")
        
        # Restore cursor
        self.root.config(cursor="arrow")
        
        # Destroy the window
        self.root.destroy()

    ##############################################################

    def on_close(self):
        """Handle window close event"""
        if self.downloading:
            if messagebox.askyesno("Download in Progress", 
                                  "A download is currently in progress. Stop download and exit?"):
                self.stop_download = True
                # Wait a moment for the download thread to stop
                time.sleep(0.5)
            else:
                return

        if self.hik is not None:
            try:
                self.hik.close()
                self.logged_in = False
            except Exception:
                pass

        self.root.destroy()

##############################################################

if __name__ == "__main__":

    root = tk.Tk()

    HikvisionDownloaderGUI(root)

    root.mainloop()