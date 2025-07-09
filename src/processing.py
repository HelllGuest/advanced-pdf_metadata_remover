import os
import shutil
import time
import pikepdf
import subprocess
import platform
import urllib.request
import zipfile
import tkinter.messagebox as messagebox
from typing import Any, Dict, Optional

class PDFProcessor:
    def __init__(self, config: Optional[Dict[str, Any]], log_callback=None, status_callback=None) -> None:
        """PDFProcessor handles all PDF and metadata operations."""
        self.config = config or {}
        self.log_callback = log_callback  # function(message, level)
        self.status_callback = status_callback  # function(message)
        self.qpdf_path = None
        self._qpdf_prompted = False  # Track if QPDF prompt has been shown

    def log(self, message: str, level: str = "info") -> None:
        if self.log_callback:
            self.log_callback(message, level)

    def update_status(self, message: str) -> None:
        if self.status_callback:
            self.status_callback(message)

    def get_qpdf_path(self) -> Optional[str]:
        # First, check bin/qpdf.exe in the project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..'))
        bin_dir = os.path.join(project_root, 'bin')
        bin_qpdf = os.path.join(bin_dir, 'qpdf.exe')
        if os.path.exists(bin_qpdf):
            self.qpdf_path = bin_qpdf
            return bin_qpdf
        from shutil import which
        if platform.system() == 'Windows':
            qpdf_exe = 'qpdf.exe'
        else:
            qpdf_exe = 'qpdf'
        if which(qpdf_exe):
            self.qpdf_path = qpdf_exe
            return qpdf_exe
        # If compression is requested and QPDF is missing, prompt the user (only once)
        if not self._qpdf_prompted and hasattr(self, 'status_callback') and self.status_callback:
            self._qpdf_prompted = True
            try:
                # Only prompt if running in GUI
                root = None
                if hasattr(self.status_callback, '__self__'):
                    root = getattr(self.status_callback.__self__, 'root', None)
                if root:
                    res = messagebox.askyesno(
                        "QPDF Not Found",
                        "QPDF is missing. If you want compression support, click Yes to download QPDF automatically.",
                        parent=root
                    )
                    if not res:
                        self.log("QPDF not downloaded. Compression will be skipped.", level="warning")
                        return None
            except Exception:
                pass
        elif self._qpdf_prompted:
            return None
        # Download QPDF if not found and user agreed
        latest_version = '12.2.0'
        base_url = f'https://github.com/qpdf/qpdf/releases/download/v{latest_version}/'
        if platform.system() == 'Windows':
            arch = platform.architecture()[0]
            if arch == '64bit':
                asset = f'qpdf-{latest_version}-msvc64.zip'
                exe_name = f'qpdf-{latest_version}-msvc64/bin/qpdf.exe'
            else:
                asset = f'qpdf-{latest_version}-msvc32.zip'
                exe_name = f'qpdf-{latest_version}-msvc32/bin/qpdf.exe'
        elif platform.system() == 'Darwin':
            asset = f'qpdf-{latest_version}-bin-mac-x86_64.zip'
            exe_name = f'qpdf-{latest_version}-bin-mac-x86_64/bin/qpdf'
        else:
            asset = f'qpdf-{latest_version}-bin-linux-x86_64.zip'
            exe_name = f'qpdf-{latest_version}-bin-linux-x86_64/bin/qpdf'
        zip_path = os.path.join(bin_dir, asset)
        exe_path = os.path.join(bin_dir, os.path.basename(exe_name))
        # Download and extract directly to bin/
        if not os.path.exists(exe_path):
            url = base_url + asset
            try:
                self.update_status(f"Downloading QPDF from {url} ...")
                if not os.path.exists(bin_dir):
                    os.makedirs(bin_dir)
                urllib.request.urlretrieve(url, zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Extract only the bin/ files from the archive to bin_dir
                    for member in zip_ref.namelist():
                        if '/bin/' in member and (member.endswith('.exe') or member.endswith('.dll')):
                            filename = os.path.basename(member)
                            source = zip_ref.open(member)
                            target = open(os.path.join(bin_dir, filename), "wb")
                            with source, target:
                                target.write(source.read())
                if not os.path.exists(exe_path):
                    raise RuntimeError("QPDF binary not found after extraction.")
                if platform.system() != 'Windows':
                    os.chmod(exe_path, 0o755)
                try:
                    os.remove(zip_path)
                except Exception:
                    pass
            except Exception as e:
                self.log(f"QPDF Download Error: {e}", level="error")
                return None
        self.qpdf_path = exe_path
        return exe_path

    def process_single_file(self, pdf_path: str, output_path: str, metadata_remove_vars: Dict[str, Any], metadata_edit_vars: Dict[str, Any], custom_metadata: Any, compression_level: str) -> Any:
        """Process a single PDF file: remove/edit metadata, save, and optionally compress."""
        try:
            norm_pdf_path = os.path.normpath(pdf_path).replace('\\', '/')
            # Backup logic
            if self.config.get('backup', False) and self.config.get('overwrite', False) and os.path.abspath(norm_pdf_path) == os.path.abspath(output_path):
                base_backup = f"{norm_pdf_path}.bak_{int(time.time())}"
                backup_path = base_backup
                counter = 1
                while os.path.exists(backup_path):
                    backup_path = f"{base_backup}_{counter}"
                    counter += 1
                shutil.copy2(norm_pdf_path, backup_path)
            # Open PDF
            if os.path.abspath(norm_pdf_path) == os.path.abspath(output_path):
                pdf = pikepdf.open(norm_pdf_path, allow_overwriting_input=True)
            else:
                pdf = pikepdf.open(norm_pdf_path)
            with pdf:
                for key, remove_var in metadata_remove_vars.items():
                    edit_var = metadata_edit_vars[key]
                    if remove_var.get():
                        pdf.docinfo[key] = ""
                    if edit_var.get().strip():
                        pdf.docinfo[key] = edit_var.get().strip()
                for remove_var, key, value_var in custom_metadata:
                    if remove_var.get():
                        pdf.docinfo[key] = ""
                    if value_var.get().strip():
                        pdf.docinfo[key] = value_var.get().strip()
                pdf.save(output_path)
            orig_size = os.path.getsize(norm_pdf_path)
            compression_increased = False
            if compression_level and compression_level != "None":
                qpdf_path = self.get_qpdf_path()
                if not qpdf_path:
                    return False
                compression_flag = self.get_compression_flag(compression_level)
                try:
                    result = subprocess.run([
                        qpdf_path, *compression_flag, '--replace-input', output_path
                    ], capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"QPDF compression failed: {result.stderr.strip()}")
                except Exception as e:
                    self.log(f"QPDF Compression Error: {e}", level="error")
                    return False
                out_size = os.path.getsize(output_path)
                if out_size > orig_size:
                    self.log(f"Warning: Output file is larger after compression ({os.path.basename(output_path)}: {out_size} bytes > {orig_size} bytes)", level="warning")
                    compression_increased = True
            if compression_increased:
                return "compression_increase"
            return True
        except Exception as e:
            self.log(f"Processing Error: {e}", level="error")
            return False

    def get_compression_flag(self, level: str) -> Any:
        if level == "Low":
            return ["--compression-level=1", "--stream-data=compress"]
        elif level == "Medium":
            return ["--compression-level=5", "--stream-data=compress"]
        elif level == "High":
            return ["--compression-level=7", "--stream-data=compress"]
        elif level == "Maximum":
            return ["--compression-level=9", "--stream-data=compress"]
        else:
            return []

    # ... (move all PDF processing, metadata, compression, and QPDF logic here)
    pass 