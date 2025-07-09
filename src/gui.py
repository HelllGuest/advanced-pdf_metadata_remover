import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
try:
    from .processing import PDFProcessor
    from .utils import load_config, save_config
except ImportError:
    from processing import PDFProcessor
    from utils import load_config, save_config
import random

class Tooltip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0,0,0,0)
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", 8, "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class AdvancedPDFMetadataRemover:
    def __init__(self) -> None:
        """Initialize the main GUI and state."""
        self.root = tk.Tk()
        self.config_file = "pdf_remover_config.json"
        self.config = load_config(self.config_file)
        self.processor = PDFProcessor(self.config, log_callback=self.log_message, status_callback=self.update_status)
        self.cancel_flag = False
        self.file_paths_to_process = []
        self.current_file_index = 0
        self.total_files = 0
        self.progress_bar = None
        self.status_label = None
        self.file_listbox = None
        self.advanced_controls_window = None
        self.backup_var = tk.BooleanVar(master=self.root, value=self.config.get('backup', True))
        self.overwrite_var = tk.BooleanVar(master=self.root, value=self.config.get('overwrite', False))
        self.recursive_var = tk.BooleanVar(master=self.root, value=self.config.get('recursive', True))
        self.show_errors_var = tk.BooleanVar(master=self.root, value=self.config.get('show_errors', False))
        self.output_path_var = tk.StringVar(master=self.root, value=self.config.get('output_path', ''))
        self.max_depth_var = tk.StringVar(master=self.root, value=str(self.config.get('max_depth', 3)))
        self.metadata_remove_vars = {}
        self.metadata_edit_vars = {}
        self.custom_metadata = []
        self.file_action_frame = None
        self.process_frame = None
        self.settings_frame = None
        self.setup_gui()
        self.root.report_callback_exception = self.global_error_handler

    def setup_gui(self):
        self.root.title("Advanced PDF Metadata Remover")
        self.root.geometry("800x600")
        self.root.minsize(700, 500)
        self.setup_menu()

        # --- Menubar ---
        menubar = tk.Menu(self.root)
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Add Files", command=self.browse_files, accelerator="Ctrl+O")
        file_menu.add_command(label="Add Folder", command=self.browse_folder, accelerator="Ctrl+Shift+O")
        file_menu.add_command(label="Reset", command=self.reset_everything)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)
        # Process menu
        process_menu = tk.Menu(menubar, tearoff=0)
        process_menu.add_command(label="Start Processing", command=self.start_processing, accelerator="F5")
        process_menu.add_command(label="Stop Processing", command=self.stop_processing, accelerator="F6")
        process_menu.add_separator()
        process_menu.add_command(label="Show Advanced Controls", command=self.toggle_advanced_controls)
        menubar.add_cascade(label="Process", menu=process_menu)
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Help", command=self.show_help)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)
        # Keyboard shortcuts
        self.root.bind('<Control-o>', lambda e: self.browse_files())
        self.root.bind('<Control-O>', lambda e: self.browse_folder())
        self.root.bind('<F5>', lambda e: self.start_processing())
        self.root.bind('<F6>', lambda e: self.stop_processing())
        self.root.bind('<Control-q>', lambda e: self.on_closing())

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- File Actions ---
        file_action_frame = ttk.LabelFrame(main_frame, text="File Actions", padding=10)
        file_action_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(file_action_frame, text="Add Files", command=self.browse_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(file_action_frame, text="Add Folder", command=self.browse_folder).pack(side=tk.LEFT, padx=5)
        reset_btn = ttk.Button(file_action_frame, text="Reset", command=self.reset_everything)
        reset_btn.pack(side=tk.LEFT, padx=5)
        self.file_count_label = ttk.Label(file_action_frame, text="0 files ready for processing")
        self.file_count_label.pack(side=tk.LEFT, padx=20)

        # --- Output Directory ---
        output_frame = ttk.LabelFrame(main_frame, text="Output Directory", padding=10)
        output_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(output_frame, text="Directory:").pack(side=tk.LEFT)
        ttk.Entry(output_frame, textvariable=self.output_path_var, width=50).pack(side=tk.LEFT, padx=5)
        ttk.Button(output_frame, text="Browse", command=self.browse_output_dir).pack(side=tk.LEFT, padx=5)
        ttk.Label(output_frame, text="Max Recursion Depth:").pack(side=tk.LEFT, padx=(20,2))
        ttk.Spinbox(output_frame, from_=1, to=10, textvariable=self.max_depth_var, width=10).pack(side=tk.LEFT, padx=2)

        # --- Processing Options ---
        options_frame = ttk.LabelFrame(main_frame, text="Processing Options", padding=10)
        options_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Checkbutton(options_frame, text="Backup Original", variable=self.backup_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(options_frame, text="Overwrite Original", variable=self.overwrite_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(options_frame, text="Recursive", variable=self.recursive_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(options_frame, text="Show Errors", variable=self.show_errors_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(options_frame, text="Compression Level:").pack(side=tk.LEFT, padx=(20,2))
        self.compression_level_var = tk.StringVar(value="None")
        compression_levels = ["None", "Low", "Medium", "High", "Maximum"]
        self.compression_level_combo = ttk.Combobox(options_frame, values=compression_levels, textvariable=self.compression_level_var, state="readonly", width=10)
        self.compression_level_combo.pack(side=tk.LEFT, padx=2)
        self.compression_level_combo.bind("<<ComboboxSelected>>", self.on_compression_level_change)

        # --- Processing Actions ---
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X, pady=(0, 5))
        self.start_btn = ttk.Button(action_frame, text="Start Processing", command=self.start_processing)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn = ttk.Button(action_frame, text="Stop", command=self.stop_processing, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        self.advanced_controls_btn = ttk.Button(action_frame, text="Show Advanced Controls", command=self.toggle_advanced_controls)
        self.advanced_controls_btn.pack(side=tk.LEFT, padx=5)
        clear_log_btn = ttk.Button(action_frame, text="Clear Log", command=self.clear_log)
        clear_log_btn.pack(side=tk.LEFT, padx=5)

        # --- Progress ---
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 5))
        self.progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=2)
        self.status_label = ttk.Label(progress_frame, text="Ready")
        self.status_label.pack(pady=2)

        # --- Log ---
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.log_box = scrolledtext.ScrolledText(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD)
        self.log_box.pack(fill=tk.BOTH, expand=True, padx=0, pady=(0,5))
        self.log_box.tag_configure('INFO', foreground='black')
        self.log_box.tag_configure('WARNING', foreground='orange')
        self.log_box.tag_configure('ERROR', foreground='red')

        # Welcome/info message
        self.log_message("Advanced PDF Metadata Remover v2.0.0", "info")
        self.log_message("Ready. Use 'Add Files' or 'Add Folder' to begin.", "info")

        # Tooltips (update to new widgets)
        Tooltip(self.compression_level_combo, "Select PDF compression level (QPDF).")
        Tooltip(self.start_btn, "Start processing all files in the list.")
        Tooltip(self.stop_btn, "Stop processing.")
        Tooltip(self.progress_bar, "Shows progress of batch processing.")
        Tooltip(self.status_label, "Current status.")
        Tooltip(reset_btn, "Reset all files, settings, and log to default state.")
        for child in options_frame.winfo_children():
            if isinstance(child, ttk.Checkbutton):
                text = child.cget('text')
                if 'Backup' in text:
                    Tooltip(child, "Create a backup before overwriting original files.")
                elif 'Overwrite' in text:
                    Tooltip(child, "Overwrite the original PDF files.")
                elif 'Recursive' in text:
                    Tooltip(child, "Recursively process PDFs in subfolders.")
                elif 'Show Errors' in text:
                    Tooltip(child, "Show error dialogs for failed files.")
        for child in output_frame.winfo_children():
            if isinstance(child, ttk.Entry):
                Tooltip(child, "Directory to save processed files.")
            if isinstance(child, ttk.Spinbox):
                Tooltip(child, "Maximum folder recursion depth.")

        self.file_action_frame = file_action_frame
        self.process_frame = action_frame
        self.settings_frame = output_frame
        # Remove file_listbox and related references
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_menu(self):
        pass
    def browse_files(self):
        files = filedialog.askopenfilenames(
            title="Select PDF Files",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            parent=self.root
        )
        if files:
            self.add_files(files)

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select Folder", parent=self.root)
        if folder:
            self.add_files([folder])

    def browse_output_dir(self):
        directory = filedialog.askdirectory(title="Select Output Directory", parent=self.root)
        if directory:
            if self.output_path_var is not None:
                self.output_path_var.set(directory)

    def add_files(self, paths):
        pdfs_to_add = []
        for path in paths:
            if not os.path.exists(path):
                self.log_message(f"Warning: File or folder does not exist: {path.replace('\\', '/')}" , "warning")
                messagebox.showwarning("File Not Found", f"File or folder does not exist: {path.replace('\\', '/')}" , parent=self.root)
                continue
            if os.path.isdir(path):
                pdfs = self.collect_pdf_files([path])
                for pdf in pdfs:
                    if pdf not in self.file_paths_to_process:
                        pdfs_to_add.append(pdf)
            elif os.path.isfile(path) and self.is_valid_pdf(path):
                if path not in self.file_paths_to_process:
                    pdfs_to_add.append(path)
        self.file_paths_to_process.extend(pdfs_to_add)
        if pdfs_to_add:
            self.log_message("Added files:", "info")
            for f in pdfs_to_add:
                self.log_message(f"  {f.replace('\\', '/')}" , "info")
        self.update_file_count()
        self.update_status()
        # If you have update_extra_metadata_fields, call it here if needed

    def reset_everything(self):
        """Reset everything to default state."""
        # Clear file list
        self.file_paths_to_process.clear()
        
        # Reset all configuration variables to defaults
        self.backup_var.set(True)
        self.overwrite_var.set(False)
        self.recursive_var.set(True)
        self.show_errors_var.set(False)
        self.output_path_var.set("")
        self.max_depth_var.set("3")
        self.compression_level_var.set("None")
        
        # Clear metadata settings
        self.metadata_remove_vars.clear()
        self.metadata_edit_vars.clear()
        self.custom_metadata.clear()
        
        # Clear log
        if hasattr(self, 'log_box') and self.log_box is not None:
            self.log_box.config(state=tk.NORMAL)
            self.log_box.delete(1.0, tk.END)
            self.log_box.config(state=tk.DISABLED)
        
        # Reset progress and status
        if hasattr(self, 'progress_bar') and self.progress_bar is not None:
            self.progress_bar['value'] = 0
        
        # Update UI
        self.update_file_count()
        self.update_status("Ready")
        
        # Log reset message
        self.log_message("Advanced PDF Metadata Remover v2.0.0", "info")
        self.log_message("Application reset to default state. Ready to begin.", "info")

    def collect_pdf_files(self, paths):
        pdfs = []
        recursive = self.recursive_var.get() if self.recursive_var is not None else True
        max_depth = int(self.max_depth_var.get()) if (self.max_depth_var is not None and recursive) else 0
        for path in paths:
            if os.path.isfile(path) and self.is_valid_pdf(path):
                pdfs.append(path)
            elif os.path.isdir(path):
                for root, dirs, files in os.walk(path):
                    if max_depth > 0:
                        depth = root.replace(path, '').count(os.sep)
                        if depth > max_depth:
                            continue
                    for file in files:
                        if self.is_valid_pdf(os.path.join(root, file)):
                            pdfs.append(os.path.join(root, file))
        return list(set(pdfs))

    def is_valid_pdf(self, file_path):
        try:
            if not file_path.lower().endswith('.pdf'):
                return False
            with open(file_path, 'rb') as f:
                return f.read(4) == b'%PDF'
        except Exception:
            return False

    def preview_selected_file(self):
        # No-op: file list UI removed
        pass

    def toggle_advanced_controls(self):
        # Always open the advanced controls window when button is clicked
        if self.advanced_controls_window is None or not tk.Toplevel.winfo_exists(self.advanced_controls_window):
            self.open_advanced_controls_window()
        else:
            self.advanced_controls_window.lift()

    def open_advanced_controls_window(self):
        self.advanced_controls_window = tk.Toplevel(self.root)
        self.advanced_controls_window.title("Advanced Metadata Controls")
        self.advanced_controls_window.geometry("500x700")
        self.advanced_controls_window.protocol("WM_DELETE_WINDOW", self.close_advanced_controls_window)
        self.center_window(self.advanced_controls_window, 500, 700)
        meta_frame = ttk.LabelFrame(self.advanced_controls_window, text="Metadata Control", padding=10)
        meta_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        all_metadata_fields = [
            ("Title", "/Title"),
            ("Author", "/Author"),
            ("Subject", "/Subject"),
            ("Keywords", "/Keywords"),
            ("Creator", "/Creator"),
            ("Producer", "/Producer"),
            ("CreationDate", "/CreationDate"),
            ("ModDate", "/ModDate"),
            ("Trapped", "/Trapped"),
            ("Company", "/Company"),
            ("Manager", "/Manager"),
            ("Category", "/Category"),
            ("Format", "/Format"),
            ("Source", "/Source"),
            ("Language", "/Language"),
            ("Version", "/Version"),
            ("Custom1", "/Custom1"),
            ("Custom2", "/Custom2"),
            ("Custom3", "/Custom3"),
        ]
        self.metadata_field_rows = {}
        for idx, (label, key) in enumerate(all_metadata_fields):
            row = ttk.Frame(meta_frame)
            row.pack(fill=tk.X, pady=2)
            remove_var = tk.BooleanVar(value=True)
            edit_var = tk.StringVar()
            self.metadata_remove_vars[key] = remove_var
            self.metadata_edit_vars[key] = edit_var
            self.metadata_field_rows[key] = row
            ttk.Checkbutton(row, text=f"Remove {label}", variable=remove_var).pack(side=tk.LEFT)
            ttk.Label(row, text=f"Set {label}:").pack(side=tk.LEFT, padx=(10,2))
            ttk.Entry(row, textvariable=edit_var, width=30).pack(side=tk.LEFT)
        # Dynamically add any extra fields found in the first selected PDF
        self.extra_metadata_keys = set()
        self.meta_frame = meta_frame
        self.update_extra_metadata_fields()
        # Custom metadata controls
        custom_frame = ttk.Frame(meta_frame)
        custom_frame.pack(fill=tk.X, pady=2)
        self.custom_key_var = tk.StringVar()
        self.custom_value_var = tk.StringVar()
        ttk.Label(custom_frame, text="Custom Field:").pack(side=tk.LEFT)
        ttk.Entry(custom_frame, textvariable=self.custom_key_var, width=15).pack(side=tk.LEFT, padx=2)
        ttk.Entry(custom_frame, textvariable=self.custom_value_var, width=20).pack(side=tk.LEFT, padx=2)
        ttk.Button(custom_frame, text="Add", command=self.add_custom_metadata_field).pack(side=tk.LEFT, padx=2)
        self.custom_fields_frame = ttk.Frame(meta_frame)
        self.custom_fields_frame.pack(fill=tk.X, pady=2)
        # --- Bottom Buttons ---
        btn_frame = ttk.Frame(self.advanced_controls_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(btn_frame, text="Fill Random Data", command=self.fill_random_metadata).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Reset", command=self.reset_metadata_fields).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="OK", command=self.close_advanced_controls_window).pack(side=tk.RIGHT, padx=5)

    def add_custom_metadata_field(self):
        key = self.custom_key_var.get().strip()
        value = self.custom_value_var.get().strip()
        if not key:
            return
        remove_var = tk.BooleanVar(value=True)
        value_var = tk.StringVar(value=value)
        row = ttk.Frame(self.custom_fields_frame)
        row.pack(fill=tk.X, pady=1)
        ttk.Checkbutton(row, text="Remove", variable=remove_var).pack(side=tk.LEFT)
        ttk.Label(row, text=key).pack(side=tk.LEFT, padx=(5,2))
        ttk.Entry(row, textvariable=value_var, width=20).pack(side=tk.LEFT, padx=2)
        ttk.Button(row, text="Remove Field", command=lambda: self.remove_custom_metadata_field(row, (remove_var, key, value_var))).pack(side=tk.LEFT, padx=2)
        self.custom_metadata.append((remove_var, key, value_var))
        self.custom_key_var.set("")
        self.custom_value_var.set("")

    def remove_custom_metadata_field(self, row, field_tuple):
        row.destroy()
        if field_tuple in self.custom_metadata:
            self.custom_metadata.remove(field_tuple)

    def update_extra_metadata_fields(self):
        if self.file_paths_to_process:
            first_file = self.file_paths_to_process[0]
            try:
                import pikepdf
                with pikepdf.open(os.path.normpath(first_file).replace('\\', '/')) as pdf:
                    for key in pdf.docinfo.keys():
                        if key not in self.metadata_remove_vars:
                            row = ttk.Frame(self.meta_frame)
                            row.pack(fill=tk.X, pady=2)
                            remove_var = tk.BooleanVar(value=True)
                            edit_var = tk.StringVar()
                            self.metadata_remove_vars[key] = remove_var
                            self.metadata_edit_vars[key] = edit_var
                            self.metadata_field_rows[key] = row
                            ttk.Checkbutton(row, text=f"Remove {key}", variable=remove_var).pack(side=tk.LEFT)
                            ttk.Label(row, text=f"Set {key}:").pack(side=tk.LEFT, padx=(10,2))
                            ttk.Entry(row, textvariable=edit_var, width=30).pack(side=tk.LEFT)
                            self.extra_metadata_keys.add(key)
            except Exception:
                pass

    def fill_random_metadata(self):
        neutral_map = {
            '/Author': 'Anonymous',
            '/Title': 'Document',
            '/Subject': 'Redacted',
            '/Keywords': 'Redacted',
        }
        for key, edit_var in self.metadata_edit_vars.items():
            if key in neutral_map:
                edit_var.set(neutral_map[key])
            else:
                edit_var.set('Redacted')
        for _, _, value_var in self.custom_metadata:
            value_var.set('Redacted')

    def reset_metadata_fields(self):
        for key, edit_var in self.metadata_edit_vars.items():
            edit_var.set("")
        for _, _, value_var in self.custom_metadata:
            value_var.set("")

    def close_advanced_controls_window(self):
        if self.advanced_controls_window is not None:
            self.advanced_controls_window.destroy()
            self.advanced_controls_window = None

    def center_window(self, window, width, height):
        if self.root is not None:
            self.root.update_idletasks()
            x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
            y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)
        else:
            x = 0
            y = 0
        window.geometry(f"{width}x{height}+{x}+{y}")

    def start_processing(self):
        if not self.file_paths_to_process:
            messagebox.showwarning("No Files", "Please add files to process.", parent=self.root)
            return
        self.log_message("Files to process:", "info")
        for f in self.file_paths_to_process:
            self.log_message(f"  {f.replace('\\', '/')}" , "info")
        print("Files to process:")
        for f in self.file_paths_to_process:
            print(f.replace('\\', '/'))
        self.cancel_flag = False
        self.set_controls_state('disabled')
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        if self.progress_bar is not None:
            self.progress_bar["value"] = 0
        threading.Thread(target=self._process_files, daemon=True).start()

    def stop_processing(self):
        self.cancel_flag = True
        self.log_message("Processing stopped by user.", "warning")

    def _process_files(self):
        try:
            pdf_files = self.collect_pdf_files(self.file_paths_to_process)
            self.total_files = len(pdf_files)
            if self.total_files == 0:
                self.log_message("No valid PDF files found.", "warning")
                return
            self.log_message(f"Found {self.total_files} PDF file(s) to process.", "info")
            if self.progress_bar is not None:
                self.progress_bar["maximum"] = self.total_files
                self.progress_bar["value"] = 0
            success_count = 0
            error_count = 0
            compression_increase_count = 0
            for i, pdf_path in enumerate(pdf_files):
                if self.cancel_flag:
                    break
                self.current_file_index = i + 1
                self.update_status(f"Processing {self.current_file_index}/{self.total_files}: {os.path.basename(pdf_path)}")
                self.log_message(f"Processing: {pdf_path.replace('\\', '/')}" , "info")
                # Compute output_path as in the original logic
                norm_pdf_path = os.path.normpath(pdf_path).replace('\\', '/')
                if self.overwrite_var.get():
                    output_path = norm_pdf_path
                elif self.output_path_var.get():
                    if os.path.isdir(self.output_path_var.get()):
                        filename = os.path.basename(norm_pdf_path)
                        output_path = os.path.join(self.output_path_var.get(), filename)
                    else:
                        output_path = self.output_path_var.get()
                else:
                    base, ext = os.path.splitext(norm_pdf_path)
                    output_path = f"{base}_clean{ext}"
                result = self.processor.process_single_file(
                    pdf_path,
                    output_path,
                    self.metadata_remove_vars,
                    self.metadata_edit_vars,
                    self.custom_metadata,
                    self.compression_level_var.get()
                )
                if result is True:
                    success_count += 1
                elif result == "compression_increase":
                    success_count += 1
                    compression_increase_count += 1
                else:
                    error_count += 1
                if self.progress_bar is not None:
                    self.progress_bar["value"] = i + 1
                if self.root is not None:
                    self.root.update_idletasks()
            if self.cancel_flag:
                self.log_message("Processing cancelled by user.", "warning")
            else:
                summary = (f"Processing complete. Success: {success_count}, Errors: {error_count}, "
                           f"Files with increased size after compression: {compression_increase_count}")
                self.log_message(summary, "info")
                messagebox.showinfo("Summary", summary, parent=self.root)
        except Exception as e:
            self.log_message(f"Processing error: {str(e)}", "error")
        finally:
            if self.start_btn is not None:
                self.start_btn.config(state=tk.NORMAL)
            if self.stop_btn is not None:
                self.stop_btn.config(state=tk.DISABLED)
            self.set_controls_state('normal')
            self.update_status("Ready")

    def on_closing(self):
        if hasattr(self, 'cancel_flag'):
            self.cancel_flag = True
        self.save_config()
        if self.root is not None:
            self.root.destroy()

    def save_config(self) -> None:
        """Save current configuration to JSON file using utils.save_config."""
        config = {
            'backup': self.backup_var.get() if self.backup_var is not None else self.config.get('backup', True),
            'overwrite': self.overwrite_var.get() if self.overwrite_var is not None else self.config.get('overwrite', False),
            'recursive': self.recursive_var.get() if self.recursive_var is not None else self.config.get('recursive', True),
            'show_errors': self.show_errors_var.get() if self.show_errors_var is not None else self.config.get('show_errors', False),
            'output_path': self.output_path_var.get() if self.output_path_var is not None else self.config.get('output_path', ''),
            'max_depth': int(self.max_depth_var.get()) if self.max_depth_var is not None else int(self.config.get('max_depth', 3))
        }
        save_config(self.config_file, config)



    def run(self):
        self.root.mainloop()

    def log_message(self, message, level="info"):
        if hasattr(self, 'log_box') and self.log_box is not None:
            self.log_box.config(state=tk.NORMAL)
            tag = level.upper()
            self.log_box.insert(tk.END, f"[{tag}] {message}\n", tag)
            self.log_box.see(tk.END)
            self.log_box.config(state=tk.DISABLED)

    def update_status(self, message="Ready"):
        if hasattr(self, 'status_label') and self.status_label is not None:
            self.status_label.config(text=message)

    def clear_log(self) -> None:
        """Clear the log box."""
        if hasattr(self, 'log_box') and self.log_box is not None:
            self.log_box.config(state=tk.NORMAL)
            self.log_box.delete(1.0, tk.END)
            self.log_box.config(state=tk.DISABLED)

    def remove_selected_files(self) -> None:
        """Remove selected files from the file list."""
        # No-op: file list UI removed
        pass

    def set_controls_state(self, state: str) -> None:
        """Enable or disable all main controls."""
        widgets = [
            self.file_action_frame,
            self.process_frame,
            self.settings_frame,
            self.compression_level_combo,
            self.start_btn,
            self.stop_btn,
            self.advanced_controls_btn
        ]
        for w in widgets:
            try:
                w.config(state=state)
            except Exception:
                try:
                    w['state'] = state
                except Exception:
                    pass

    def global_error_handler(self, exc, val, tb):
        """Handle uncaught exceptions in the GUI."""
        import traceback
        msg = ''.join(traceback.format_exception(exc, val, tb))
        self.log_message(f"Uncaught exception:\n{msg}", level="error")
        messagebox.showerror("Unexpected Error", f"An unexpected error occurred:\n{val}\n\nSee log for details.", parent=self.root)

    def _random_string(self, length):
        return ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789') for _ in range(length))

    def on_compression_level_change(self, event=None):
        level = self.compression_level_var.get()
        if level != "None":
            self.check_qpdf_available()

    def check_qpdf_available(self):
        # Try to get QPDF path, which will trigger the prompt if missing
        if hasattr(self, 'processor') and self.processor:
            qpdf_path = self.processor.get_qpdf_path()
            if not qpdf_path:
                self.log_message("QPDF not available. Compression will be skipped unless QPDF is installed.", "warning")

    def update_file_count(self):
        if hasattr(self, 'file_count_label') and self.file_count_label is not None:
            n = len(self.file_paths_to_process)
            self.file_count_label.config(text=f"{n} file{'s' if n != 1 else ''} ready for processing")

    def show_help(self):
        help_window = tk.Toplevel(self.root)
        help_window.title("Help & Instructions")
        help_window.geometry("600x500")
        help_window.transient(self.root)
        help_window.grab_set()
        self.center_window(help_window, 600, 500)
        # Instructions text
        help_text = (
            "Advanced PDF Metadata Remover - Help\n\n"
            "1. Add Files or Folders:\n"
            "   - Click 'Add Files' to select one or more PDF files.\n"
            "   - Click 'Add Folder' to select a folder (all PDFs inside will be added).\n"
            "   - The number of files ready for processing is shown at the top.\n"
            "   - Click 'Reset' to clear all files and reset all settings to defaults.\n\n"
            "2. Output Directory:\n"
            "   - Set the directory where processed files will be saved.\n"
            "   - Use 'Max Recursion Depth' to limit folder scanning depth.\n\n"
            "3. Processing Options:\n"
            "   - Backup Original: Save a backup before overwriting.\n"
            "   - Overwrite Original: Replace the original PDF.\n"
            "   - Recursive: Process PDFs in subfolders.\n"
            "   - Show Errors: Show error dialogs for failed files.\n"
            "   - Compression Level: Compress output PDFs (requires QPDF).\n\n"
            "4. Start Processing:\n"
            "   - Click 'Start Processing' to begin. Progress and status will be shown.\n"
            "   - Click 'Stop' to cancel processing.\n\n"
            "5. Advanced Controls:\n"
            "   - Click 'Show Advanced Controls' to open advanced metadata options.\n"
            "   - Remove or edit standard/custom metadata fields.\n"
            "   - Use 'Fill Random Data' or 'Reset' as needed.\n\n"
            "6. Log:\n"
            "   - The log box shows info, warnings, and errors.\n"
            "   - Click 'Clear Log' to clear the log.\n\n"
            "7. Menu Shortcuts:\n"
            "   - File, Process, and Help menus provide quick access to all actions.\n"
            "   - Keyboard shortcuts: Ctrl+O (Add Files), Ctrl+Shift+O (Add Folder), F5 (Start), F6 (Stop), Ctrl+Q (Exit).\n\n"
            "8. Reset Functionality:\n"
            "   - The 'Reset' button clears all files and resets all settings to defaults.\n"
            "   - This includes: file list, backup/overwrite settings, recursion depth, compression level, output directory, and log.\n"
            "   - Perfect for starting fresh with a new batch of files.\n\n"
            "For more details, visit the Project Home Page from the About dialog."
        )
        text_widget = scrolledtext.ScrolledText(help_window, wrap=tk.WORD, padx=10, pady=10)
        text_widget.pack(fill=tk.BOTH, expand=True)
        text_widget.insert(1.0, help_text)
        text_widget.config(state=tk.DISABLED)
        ttk.Button(help_window, text="Close", command=help_window.destroy).pack(pady=10)

    def show_about(self):
        about_window = tk.Toplevel(self.root)
        about_window.title("About")
        about_window.resizable(False, False)
        about_window.transient(self.root)
        about_window.grab_set()
        self.center_window(about_window, 500, 560)
        # Main frame (no scrollable logic)
        main_frame = ttk.Frame(about_window, padding=24)
        main_frame.pack(fill=tk.BOTH, expand=True)
        # App name and version (header)
        app_name = tk.Label(main_frame, text="Advanced PDF Metadata Remover", font=("Segoe UI", 15, "bold"), anchor="center", justify="center")
        app_name.pack(anchor="center", pady=(0,2))
        version = tk.Label(main_frame, text="v1.0.0", font=("Segoe UI", 11), fg="#666666", anchor="center", justify="center")
        version.pack(anchor="center", pady=(0,8))
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(0, 8))
        purpose = tk.Label(main_frame, text="Remove, edit, or randomize PDF metadata to protect your privacy before sharing documents. Optionally compress output files.", font=("Segoe UI", 10), anchor="center", justify="center", wraplength=440)
        purpose.pack(anchor="center", pady=(0, 8))
        tools_label = tk.Label(main_frame, text="Tools Used:", font=("Segoe UI", 10, "bold"), anchor="w", justify="left")
        tools_label.pack(anchor="w", pady=(0, 1), padx=(10,0))
        tools_list = tk.Label(main_frame, text="\u2022 pikepdf (PDF editing)\n\u2022 QPDF (compression)\n\u2022 tkinter (GUI)", font=("Segoe UI", 10), anchor="w", justify="left")
        tools_list.pack(anchor="w", padx=(24,0), pady=(0, 7))
        logic_label = tk.Label(main_frame, text="How it works:", font=("Segoe UI", 10, "bold"), anchor="w", justify="left")
        logic_label.pack(anchor="w", pady=(0, 1), padx=(10,0))
        logic_list = tk.Label(main_frame, text="\u2022 Batch process PDFs (files and folders)\n\u2022 Remove, edit, or randomize metadata fields\n\u2022 Optionally compress output with QPDF", font=("Segoe UI", 10), anchor="w", justify="left", wraplength=440)
        logic_list.pack(anchor="w", padx=(24,0), pady=(0, 7))
        author_label = tk.Label(main_frame, text="Author: Anoop Kumar", font=("Segoe UI", 10), anchor="center", justify="center")
        author_label.pack(anchor="center", pady=(6,0))
        links_frame = ttk.Frame(main_frame)
        links_frame.pack(anchor="center", pady=(0,6))
        def open_homepage(event=None):
            import webbrowser
            webbrowser.open_new("https://github.com/HelllGuest/advanced-pdf_metadata_remover")
        homepage = tk.Label(links_frame, text="Project Home Page", font=("Segoe UI", 10, "underline"), fg="#0066cc", cursor="hand2", anchor="center", justify="center")
        homepage.pack(side="left", padx=(0, 16))
        homepage.bind("<Button-1>", open_homepage)
        def open_qpdf(event=None):
            import webbrowser
            webbrowser.open_new("https://qpdf.sourceforge.io/")
        qpdf_credit = tk.Label(links_frame, text="QPDF by Jay Berkenbilt", font=("Segoe UI", 9, "underline"), anchor="center", justify="center", fg="#0066cc", cursor="hand2")
        qpdf_credit.pack(side="left")
        qpdf_credit.bind("<Button-1>", open_qpdf)
        ttk.Separator(main_frame, orient='horizontal').pack(fill=tk.X, pady=(6, 6))
        legal_label = tk.Label(main_frame, text="MIT License. Uses qpdf (Apache License 2.0) for PDF processing.\n Copyright © qpdf authors.", font=("Segoe UI", 9), anchor="center", justify="center", wraplength=440, fg="#444444")
        legal_label.pack(anchor="center", pady=(0, 2))
        # Close button at the bottom
        close_btn = ttk.Button(about_window, text="Close", command=about_window.destroy)
        close_btn.pack(side="bottom", pady=(0, 10))

def run_app():
    app = AdvancedPDFMetadataRemover()
    app.run() 