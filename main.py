import sys
import os
import json
import webbrowser
import requests
from groq import Groq
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QWidget, QVBoxLayout, QTextEdit,
    QLineEdit, QPushButton, QStackedWidget, QLabel, QFileDialog, QHBoxLayout,
    QComboBox, QScrollArea, QCheckBox, QGridLayout, QDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest
from PyQt6.QtCore import QUrl

# ── Portable base directory (works with PyInstaller .exe) ──
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS   # ✅ PyInstaller temp folder
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def asset(*parts):
    """Return absolute path to a bundled asset relative to BASE_DIR."""
    return os.path.join(BASE_DIR, *parts)

# ── Config file stored in %APPDATA%/ArchScriptGen/ (or ~/.config/ on Linux) ──
def get_config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
    config_dir = os.path.join(base, "ArchScriptGen")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir

CONFIG_FILE = os.path.join(get_config_dir(), "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(data: dict):
    cfg = load_config()
    cfg.update(data)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

# ── Shared network manager ──
_network_manager = None
def get_network_manager():
    global _network_manager
    if _network_manager is None:
        _network_manager = QNetworkAccessManager()
    return _network_manager

# ── Groq client (initialised after we know the key) ──
client = None

def init_groq_client(api_key: str):
    global client
    client = Groq(api_key=api_key)

SYSTEM_PROMPT = (
    "You are an Arch Linux expert. The user will describe what they want configured. "
    "Return ONLY a bash script with no explanation, no markdown, no backticks. "
    "Just raw bash script starting with #!/bin/bash."
)

# ── Shared style constants ──
BTN_PRIMARY    = "background-color: #89b4fa; color: black; padding: 10px; font-size: 14px;"
BTN_SUCCESS    = "background-color: #a6e3a1; color: black; padding: 12px; font-size: 14px; font-weight: bold; border-radius: 6px;"
BTN_NEUTRAL    = "background-color: #45475a; color: white; padding: 8px 14px; font-size: 13px; border-radius: 6px;"
DROPDOWN_STYLE = "background-color: #313244; color: white; padding: 6px; font-size: 13px;"
INPUT_STYLE    = "background-color: #313244; color: white; padding: 8px;"
LABEL_STYLE    = "color: white; font-size: 14px;"
TITLE_STYLE    = "color: white; font-size: 20px; font-weight: bold;"
CHECKBOX_STYLE = """
    QCheckBox::indicator {
        width: 18px; height: 18px;
        border: 2px solid #89b4fa;
        border-radius: 4px;
        background-color: #313244;
    }
    QCheckBox::indicator:checked { background-color: #89b4fa; }
"""


# ─────────────────────────────────────────────────────────────
# API Key Dialog — shown on first launch (or when key is missing)
# ─────────────────────────────────────────────────────────────
class ApiKeyDialog(QDialog):
    def __init__(self, parent=None, invalid=False):
        super().__init__(parent)
        self.setWindowTitle("Groq API Key Required")
        self.setMinimumWidth(480)
        self.setStyleSheet("background-color: #1e1e2e; color: white;")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("🔑 Enter your Groq API Key")
        title.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        if invalid:
            err = QLabel("⚠  The key you entered was rejected by Groq. Please check it and try again.")
            err.setStyleSheet("color: #f38ba8; font-size: 13px;")
            err.setWordWrap(True)
            layout.addWidget(err)

        desc = QLabel(
            "Arch Script Generator uses the Groq API (llama-3.3-70b) to generate bash scripts.\n"
            "Your key is stored locally on this machine only — it is never uploaded anywhere."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #bac2de; font-size: 13px;")
        layout.addWidget(desc)

        get_key_btn = QPushButton("🌐  Get a free API key at console.groq.com")
        get_key_btn.setStyleSheet(
            "background-color: #313244; color: #89b4fa; padding: 8px;"
            "border: 1px solid #89b4fa; border-radius: 6px; font-size: 13px;"
        )
        get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_key_btn.clicked.connect(lambda: webbrowser.open("https://console.groq.com/keys"))
        layout.addWidget(get_key_btn)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("gsk_...")
        self.key_input.setStyleSheet(
            "background-color: #313244; color: white; padding: 10px;"
            "border: 1px solid #45475a; border-radius: 6px; font-size: 14px;"
        )
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.key_input)

        # show/hide toggle
        show_row = QHBoxLayout()
        show_cb  = QCheckBox("Show key")
        show_cb.setStyleSheet("color: #bac2de; font-size: 12px;" + CHECKBOX_STYLE)
        show_cb.stateChanged.connect(
            lambda s: self.key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if s else QLineEdit.EchoMode.Password
            )
        )
        show_row.addWidget(show_cb)
        show_row.addStretch()
        layout.addLayout(show_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.save_btn = QPushButton("Save and Continue")
        self.save_btn.setStyleSheet(BTN_SUCCESS)
        self.save_btn.clicked.connect(self._on_save)
        self.save_btn.setDefault(True)
        btn_row.addWidget(self.save_btn)

        quit_btn = QPushButton("Quit")
        quit_btn.setStyleSheet(BTN_NEUTRAL)
        quit_btn.clicked.connect(self.reject)
        btn_row.addWidget(quit_btn)

        layout.addLayout(btn_row)
        self.setLayout(layout)

    def _on_save(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Empty key", "Please paste your Groq API key first.")
            return
        if not key.startswith("gsk_"):
            QMessageBox.warning(
                self, "Unexpected format",
                "Groq keys normally start with 'gsk_'.\n"
                "Double-check you copied the full key."
            )
            return
        self._api_key = key
        self.accept()

    def get_key(self) -> str:
        return getattr(self, "_api_key", "")


# ─────────────────────────────────────────────
# Background workers
# ─────────────────────────────────────────────
class GroqWorker(QObject):
    finished = pyqtSignal(str)
    error    = pyqtSignal(str)

    def __init__(self, prompt, system=SYSTEM_PROMPT):
        super().__init__()
        self.prompt = prompt
        self.system = system

    def run(self):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.system},
                    {"role": "user",   "content": self.prompt},
                ]
            )
            self.finished.emit(response.choices[0].message.content)
        except Exception as e:
            self.error.emit(str(e))


class FetchWorker(QObject):
    finished = pyqtSignal(list)

    def __init__(self, query, page):
        super().__init__()
        self.query = query
        self.page  = page

    def run(self):
        url = f"https://archlinux.org/packages/search/json/?q={self.query}&page={self.page}"
        try:
            res     = requests.get(url, timeout=5)
            data    = res.json()
            results = [
                (pkg["pkgname"], pkg.get("pkgdesc", "No description"))
                for pkg in data.get("results", [])
            ]
            self.finished.emit(results)
        except Exception:
            self.finished.emit([])


class AppCard(QWidget):
    def __init__(self, name, desc):
        super().__init__()
        self.name     = name
        self.selected = False
        self._reply   = None

        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("""
            QWidget { background-color: #313244; border-radius: 10px; }
            QWidget:hover { background-color: #45475a; }
        """)

        self.icon = QLabel("📦")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon)

        icon_url = f"https://cdn.simpleicons.org/{name}" if name.isalpha() else None
        if icon_url:
            mgr         = get_network_manager()
            self._reply = mgr.get(QNetworkRequest(QUrl(icon_url)))
            self._reply.finished.connect(self._icon_loaded)

        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(name_label)

        desc_label = QLabel(desc[:60])
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #bac2de; font-size: 12px;")
        layout.addWidget(desc_label)

        self.btn = QPushButton("Install")
        self.btn.clicked.connect(self.toggle)
        self.btn.setStyleSheet("background: #89b4fa; color: black; padding: 5px;")
        layout.addWidget(self.btn)

        self.setLayout(layout)

    def _icon_loaded(self):
        if self._reply is None:
            return
        data   = self._reply.readAll()
        pixmap = QPixmap()
        if pixmap.loadFromData(data):
            self.icon.setPixmap(pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio))
        self._reply = None

    def toggle(self):
        self.selected = not self.selected
        self.btn.setText("✓ Added" if self.selected else "Install")


# ─────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Arch Script Generator")
        self.setMinimumSize(1150, 600)

        self.script_output = QTextEdit()
        self.script_output.setReadOnly(True)
        self.script_output.setStyleSheet(
            "color: #a6e3a1; background-color: #181825; border: none;"
            "font-family: Courier; font-size: 13px; padding: 10px;"
        )
        self.script_output.setPlaceholderText("Generated script will appear here...")

        # ── nav sidebar ──
        right_panel  = QWidget()
        right_panel.setStyleSheet("background-color: #313244;")
        right_layout = QVBoxLayout()
        right_layout.setSpacing(0)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_panel.setLayout(right_layout)

        nav_btn_style = """
            QPushButton {
                color: white; background-color: #313244;
                border: none; padding: 20px; font-size: 14px; text-align: left;
            }
            QPushButton:hover   { background-color: #45475a; }
            QPushButton:pressed { background-color: #727486; }
        """

        # ── chatbot panel ──
        left_panel  = QWidget()
        left_panel.setStyleSheet("background-color: #1e1e2e;")
        left_layout = QVBoxLayout()

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("color: white; border: none;")

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Describe what you want to configure...")
        self.chat_input.setStyleSheet("background-color: #313244; color: white; padding: 8px;")
        self.chat_input.returnPressed.connect(self.handle_send)

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.handle_send)
        self.send_button.setStyleSheet("background-color: #89b4fa; color: black; padding: 8px;")

        left_layout.addWidget(self.chat_display)
        left_layout.addWidget(self.chat_input)
        left_layout.addWidget(self.send_button)
        left_panel.setLayout(left_layout)

        # ── pages ──
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background-color: #181825;")
        self.pages = {}

        page_builders = {
            "🏠 Home":              self.make_home_page,
            "Background":           self.make_background_page,
            "Global Theme":         self.make_global_theme_page,
            "Drivers":              self.make_drivers_page,
            "Apps":                 self.make_apps_page,
            "Locales":              self.make_locales_preview,
            "Mouse Pointer Styles": self.make_mouse_page,
            "Desktop Environment":  self.make_desktop_environment_page,
            "Settings":             self.make_settings_page,
            "Dot Files":            self.make_dotFilesPage,
            "⚙ API Key":            self.make_api_key_page,
        }
        for i, (label, builder) in enumerate(page_builders.items()):
            self.stack.addWidget(builder())
            self.pages[label] = i

        for label, i in self.pages.items():
            btn = QPushButton(label)
            btn.setStyleSheet(nav_btn_style)
            btn.clicked.connect(lambda checked, idx=i: self.switch_page(idx))
            right_layout.addWidget(btn)
        right_layout.addStretch()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(self.stack)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 500, 250])
        self.setCentralWidget(splitter)

    # ─────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────
    def switch_page(self, index):
        self.stack.setCurrentIndex(index)

    def _set_busy(self, button, busy, idle_text):
        button.setEnabled(not busy)
        button.setText("Generating..." if busy else idle_text)

    def _make_link_row(self, layout, name, url):
        row        = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(name)
        label.setStyleSheet(LABEL_STYLE)
        btn = QPushButton("Open ↗")
        btn.setFixedWidth(80)
        btn.setStyleSheet(BTN_PRIMARY)
        btn.clicked.connect(lambda checked, u=url: webbrowser.open(u))
        row_layout.addWidget(label)
        row_layout.addStretch()
        row_layout.addWidget(btn)
        row.setLayout(row_layout)
        layout.addWidget(row)

    def _make_preview_label(self):
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("background-color: #11111b;")
        lbl.setMinimumHeight(300)
        return lbl

    def _load_preview(self, label, path):
        if path and os.path.exists(path):
            pixmap = QPixmap(path)
            if not pixmap.isNull():
                label.setPixmap(pixmap.scaled(
                    500, 400,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                ))

    # ─────────────────────────────────────────────
    # Groq calls (threaded)
    # ─────────────────────────────────────────────
    def _call_groq(self, prompt, on_done, on_error=None):
        self._groq_worker = GroqWorker(prompt)
        self._groq_thread = QThread()
        self._groq_worker.moveToThread(self._groq_thread)
        self._groq_thread.started.connect(self._groq_worker.run)
        self._groq_worker.finished.connect(on_done)
        self._groq_worker.finished.connect(self._groq_thread.quit)
        self._groq_worker.finished.connect(self._groq_worker.deleteLater)
        self._groq_worker.error.connect(self._groq_thread.quit)
        self._groq_worker.error.connect(self._groq_worker.deleteLater)
        if on_error:
            self._groq_worker.error.connect(on_error)
        self._groq_thread.finished.connect(self._groq_thread.deleteLater)
        self._groq_thread.start()

    def handle_send(self):
        user_text = self.chat_input.text().strip()
        if not user_text:
            return
        self.chat_display.append(f"You: {user_text}")
        self.chat_input.clear()
        self._set_busy(self.send_button, True, "Send")

        def on_done(result):
            self.script_output.setPlainText(result)
            self.chat_display.append("Script generated ✓\n")
            self._set_busy(self.send_button, False, "Send")

        def on_error(msg):
            self.chat_display.append(f"Error: {msg}\n")
            self._set_busy(self.send_button, False, "Send")

        self._call_groq(user_text, on_done, on_error)

    def generate_script_from_selections(self):
        items = self.collect_selections()
        if not items:
            self.script_output.setPlainText("")
            self.script_output.setPlaceholderText("Nothing selected yet.")
            return
        self._set_busy(self.generate_btn, True, "Generate Script")
        prompt = "Generate an Arch Linux bash install/config script for:\n" + "\n".join(items)

        def on_done(result):
            self.script_output.setPlainText(result)
            self._set_busy(self.generate_btn, False, "Generate Script")

        def on_error(msg):
            self.chat_display.append(f"Error: {msg}\n")
            self._set_busy(self.generate_btn, False, "Generate Script")

        self._call_groq(prompt, on_done, on_error)

    def save_script(self):
        script = self.script_output.toPlainText()
        if not script.strip():
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Script", "script.sh", "Shell Scripts (*.sh)")
        if path:
            with open(path, "w", newline="\n") as f:
                f.write(script)
            self.chat_display.append("Script saved ✓\n")

    # ─────────────────────────────────────────────
    # Home page
    # ─────────────────────────────────────────────
    def make_home_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        top_bar  = QHBoxLayout()
        title    = QLabel("🏠 Home")
        title.setStyleSheet(TITLE_STYLE)
        top_bar.addWidget(title)
        top_bar.addStretch()
        view_btn = QPushButton("⚙ View Selections")
        view_btn.setStyleSheet(BTN_NEUTRAL)
        view_btn.clicked.connect(self.show_selections_dialog)
        top_bar.addWidget(view_btn)
        layout.addLayout(top_bar)

        layout.addWidget(self.script_output, stretch=1)

        bottom_bar = QHBoxLayout()
        bottom_bar.setSpacing(10)
        self.generate_btn = QPushButton("Generate Script")
        self.generate_btn.setStyleSheet(
            "background-color: #89b4fa; color: black; padding: 12px;"
            "font-size: 14px; font-weight: bold; border-radius: 6px;"
        )
        self.generate_btn.clicked.connect(self.generate_script_from_selections)
        bottom_bar.addWidget(self.generate_btn)
        save_btn = QPushButton("💾 Save as .sh")
        save_btn.setStyleSheet(BTN_SUCCESS)
        save_btn.clicked.connect(self.save_script)
        bottom_bar.addWidget(save_btn)
        layout.addLayout(bottom_bar)

        page.setLayout(layout)
        return page

    def show_selections_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Current Selections")
        dialog.setMinimumSize(420, 360)
        dialog.setStyleSheet("background-color: #1e1e2e; color: white;")
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        title = QLabel("Your current selections:")
        title.setStyleSheet("color: #89b4fa; font-size: 15px; font-weight: bold;")
        layout.addWidget(title)
        items = self.collect_selections()
        if items:
            for item in items:
                lbl = QLabel("- " + item)
                lbl.setStyleSheet("color: white; font-size: 13px; padding: 2px 0;")
                layout.addWidget(lbl)
        else:
            lbl = QLabel("Nothing selected yet.")
            lbl.setWordWrap(True)
            lbl.setStyleSheet("color: #6c7086; font-size: 13px;")
            layout.addWidget(lbl)
        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("background-color: #313244; color: white; padding: 8px; border-radius: 4px;")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        dialog.setLayout(layout)
        dialog.exec()

    def collect_selections(self):
        items = []
        checks = [
            ("Theme",               lambda: self.theme_dropdown.currentText()),
            ("Desktop Environment", lambda: self.desktop_environment_dropdown.currentText()),
            ("GPU Driver",          lambda: self.gpu_dropdown.currentText()),
            ("Audio",               lambda: self.audio_dropdown.currentText()),
            ("Touchpad",            lambda: self.touchpad_dropdown.currentText()),
            ("Network",             lambda: self.network_dropdown.currentText()),
            ("Bluetooth",           lambda: "Yes" if self.bluetooth_dropdown.isChecked() else "No"),
            ("Printer",             lambda: "Yes" if self.printer_dropdown.isChecked() else "No"),
            ("Cursor",              lambda: self.mouse_dropdown.currentText()),
            ("Locale",              lambda: self.locale_dropdown.currentText()),
            ("Shell",               lambda: self.shell_dropdown.currentText()),
            ("Bootloader",          lambda: self.bootloader_dropdown.currentText()),
            ("Kernel",              lambda: self.kernel_dropdown.currentText()),
            ("Display Manager",     lambda: self.display_manager_dropdown.currentText()),
            ("Hostname",            lambda: self.hostname_input.text() or "archlinux"),
            ("Username",            lambda: self.username_input.text() or "user"),
        ]
        for label, getter in checks:
            try:
                items.append(f"{label}: {getter()}")
            except AttributeError:
                pass
        try:
            selected_apps = [c.name for c in self.app_cards if c.selected]
            if selected_apps:
                items.append("Apps: " + ", ".join(selected_apps))
        except AttributeError:
            pass
        try:
            if self.wallpaper_url.text():
                items.append("Wallpaper: " + self.wallpaper_url.text())
        except AttributeError:
            pass
        try:
            if self.dot_file_url.text():
                items.append("Dot Files URL: " + self.dot_file_url.text())
        except AttributeError:
            pass
        return items

    # ─────────────────────────────────────────────
    # Pages
    # ─────────────────────────────────────────────
    def make_background_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        title  = QLabel("Backgrounds")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        for name, url in {
            "Wallhaven":           "https://wallhaven.cc",
            "Unsplash":            "https://unsplash.com",
            "Reddit r/wallpapers": "https://reddit.com/r/wallpapers",
            "Reddit r/unixporn":   "https://reddit.com/r/unixporn",
        }.items():
            self._make_link_row(layout, name, url)

        lbl = QLabel("Paste wallpaper URL:")
        lbl.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl)

        self.wallpaper_url = QLineEdit()
        self.wallpaper_url.setPlaceholderText("https://example.com/wallpaper.jpg")
        self.wallpaper_url.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.wallpaper_url)

        add_btn = QPushButton("Add Background To Script")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self.add_background_to_script)
        layout.addWidget(add_btn)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def make_global_theme_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        title  = QLabel("Global Theme")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        self.theme_dropdown = QComboBox()
        self.theme_dropdown.setStyleSheet(DROPDOWN_STYLE)
        # asset() makes paths relative to the script/exe — portable on any machine
        self.themes = {
            "Catppuccin":  asset("themes", "catppuccin.webp"),
            "Dracula":     asset("themes", "dracula.webp"),
            "Gruvbox":     asset("themes", "gruvbox.webp"),
            "Rose Pine":   asset("themes", "rosepine.webp"),
            "Tokyo Night": asset("themes", "tokyo.webp"),
            "Everforest":  asset("themes", "everforest.webp"),
            "One Dark":    asset("themes", "onedark.webp"),
        }
        self.theme_dropdown.addItems(self.themes.keys())
        self.theme_dropdown.currentTextChanged.connect(self.update_theme_preview)
        layout.addWidget(self.theme_dropdown)

        self.theme_preview = self._make_preview_label()
        scroll = QScrollArea()
        scroll.setWidget(self.theme_preview)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        layout.addWidget(scroll)

        add_btn = QPushButton("Add To Script")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self.add_theme_to_script)
        layout.addWidget(add_btn)

        page.setLayout(layout)
        self.update_theme_preview(next(iter(self.themes)))
        return page

    def update_theme_preview(self, theme_name):
        self._load_preview(self.theme_preview, self.themes.get(theme_name))

    def add_theme_to_script(self):
        self.chat_display.append(f"✓ Theme added: {self.theme_dropdown.currentText()}\n")

    def make_drivers_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        title  = QLabel("Drivers")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        def driver_row(label_text, widget):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(LABEL_STYLE)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(widget)
            layout.addLayout(row)

        self.gpu_dropdown = QComboBox()
        self.gpu_dropdown.addItems(["AMD (amdgpu)", "Nvidia (proprietary)", "Nvidia (nouveau)", "Intel (i915)"])
        self.gpu_dropdown.setStyleSheet(DROPDOWN_STYLE)
        driver_row("GPU Driver", self.gpu_dropdown)

        self.audio_dropdown = QComboBox()
        self.audio_dropdown.addItems(["PipeWire", "PulseAudio", "ALSA"])
        self.audio_dropdown.setStyleSheet(DROPDOWN_STYLE)
        driver_row("Audio", self.audio_dropdown)

        self.touchpad_dropdown = QComboBox()
        self.touchpad_dropdown.addItems(["libinput", "synaptics"])
        self.touchpad_dropdown.setStyleSheet(DROPDOWN_STYLE)
        driver_row("Touchpad", self.touchpad_dropdown)

        self.network_dropdown = QComboBox()
        self.network_dropdown.addItems(["NetworkManager", "iwd", "dhcpcd"])
        self.network_dropdown.setStyleSheet(DROPDOWN_STYLE)
        driver_row("Network", self.network_dropdown)

        self.bluetooth_dropdown = QCheckBox()
        self.bluetooth_dropdown.setStyleSheet(CHECKBOX_STYLE)
        driver_row("Bluetooth", self.bluetooth_dropdown)

        self.printer_dropdown = QCheckBox()
        self.printer_dropdown.setStyleSheet(CHECKBOX_STYLE)
        driver_row("Printer", self.printer_dropdown)

        addbtn = QPushButton("Add To Script")
        addbtn.setStyleSheet(BTN_PRIMARY)
        addbtn.clicked.connect(self.add_drivers_to_script)
        layout.addWidget(addbtn)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def add_drivers_to_script(self):
        self.chat_display.append(
            f"✓ Drivers added: GPU={self.gpu_dropdown.currentText()}, "
            f"Audio={self.audio_dropdown.currentText()}, "
            f"Touchpad={self.touchpad_dropdown.currentText()}, "
            f"Network={self.network_dropdown.currentText()}, "
            f"Bluetooth={'Yes' if self.bluetooth_dropdown.isChecked() else 'No'}, "
            f"Printer={'Yes' if self.printer_dropdown.isChecked() else 'No'}\n"
        )

    def make_desktop_environment_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        title  = QLabel("Desktop Environment")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        self.desktop_environment_dropdown = QComboBox()
        self.desktop_environment_dropdown.setStyleSheet(DROPDOWN_STYLE)
        self.desktop_environments = {
            "GNOME":                   asset("DesktopEnvironment", "gnome.webp"),
            "KDE Plasma":              asset("DesktopEnvironment", "plasma.webp"),
            "i3":                      asset("DesktopEnvironment", "i3.webp"),
            "LXQt":                    asset("DesktopEnvironment", "LXQt.webp"),
            "Deepin":                  asset("DesktopEnvironment", "deepin.webp"),
            "Xfce":                    asset("DesktopEnvironment", "xfce.webp"),
            "UKUI":                    asset("DesktopEnvironment", "UKUI.webp"),
            "MATE":                    asset("DesktopEnvironment", "mate.webp"),
            "Cinnamon":                asset("DesktopEnvironment", "cinnamon.webp"),
            "Budgie":                  asset("DesktopEnvironment", "BUDGIE.webp"),
            "UnityX":                  asset("DesktopEnvironment", "Unity.webp"),
            "COSMIC":                  asset("DesktopEnvironment", "Cosmic.webp"),
            "Cutefish":                asset("DesktopEnvironment", "cutefish.webp"),
            "Enlightenment (E/DR17+)": asset("DesktopEnvironment", "enlightenment.webp"),
            "Trinity (TDE)":           asset("DesktopEnvironment", "tde.webp"),
        }
        self.desktop_environment_dropdown.addItems(self.desktop_environments.keys())
        self.desktop_environment_dropdown.currentTextChanged.connect(self.update_de_preview)
        layout.addWidget(self.desktop_environment_dropdown)

        self.de_preview = self._make_preview_label()
        scroll = QScrollArea()
        scroll.setWidget(self.de_preview)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        layout.addWidget(scroll)

        add_btn = QPushButton("Add To Script")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self.add_de_to_script)
        layout.addWidget(add_btn)

        page.setLayout(layout)
        self.update_de_preview(next(iter(self.desktop_environments)))
        return page

    def update_de_preview(self, name):
        self._load_preview(self.de_preview, self.desktop_environments.get(name))

    def add_de_to_script(self):
        self.chat_display.append(f"✓ Desktop Environment Added: {self.desktop_environment_dropdown.currentText()}\n")

    def make_mouse_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        title  = QLabel("Mouse Pointer Styles")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        self.mouse_dropdown = QComboBox()
        self.mouse_pointers = {
            "Bibata Modern": asset("cursors", "bibata.png"),
            "Breeze":        asset("cursors", "breeze-light.webp"),
            "Capitaine":     asset("cursors", "capitaine-cursors.png"),
            "DMZ":           asset("cursors", "dmz-cursor-theme.webp"),
            "Oreo":          asset("cursors", "oreocursors.webp"),
            "Vimix":         asset("cursors", "vimix-cursor.png"),
        }
        self.mouse_dropdown.addItems(self.mouse_pointers.keys())
        self.mouse_dropdown.setStyleSheet(DROPDOWN_STYLE)
        self.mouse_dropdown.currentTextChanged.connect(self.update_cursor_preview)
        layout.addWidget(self.mouse_dropdown)

        self.cursor_preview = self._make_preview_label()
        scroll = QScrollArea()
        scroll.setWidget(self.cursor_preview)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none;")
        layout.addWidget(scroll)

        add_btn = QPushButton("Add to Script")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self.add_mouse_to_script)
        layout.addWidget(add_btn)
        layout.addStretch()
        page.setLayout(layout)
        self.update_cursor_preview(next(iter(self.mouse_pointers)))
        return page

    def update_cursor_preview(self, name):
        self._load_preview(self.cursor_preview, self.mouse_pointers.get(name))

    def add_mouse_to_script(self):
        self.chat_display.append(f"✓ Cursor added: {self.mouse_dropdown.currentText()}\n")

    def make_locales_preview(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        title  = QLabel("Locales")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        self.locale_dropdown = QComboBox()
        self.locale_dropdown.addItems([
            "af_ZA","ak_GH","am_ET","ar_AE","ar_BH","ar_DZ","ar_EG","ar_IQ","ar_JO","ar_KW",
            "ar_LB","ar_LY","ar_MA","ar_OM","ar_QA","ar_SA","ar_SD","ar_SY","ar_TN","ar_YE",
            "as_IN","az_AZ","be_BY","bg_BG","bn_BD","bn_IN","bs_BA","ca_AD","ca_ES","ca_FR",
            "ca_IT","cs_CZ","cy_GB","da_DK","de_AT","de_BE","de_CH","de_DE","de_LI","de_LU",
            "el_CY","el_GR","en_AG","en_AU","en_BW","en_CA","en_DK","en_GB","en_HK","en_IE",
            "en_IL","en_IN","en_NG","en_NZ","en_PH","en_SG","en_US","en_ZA","en_ZM","en_ZW",
            "eo","es_AR","es_BO","es_CL","es_CO","es_CR","es_CU","es_DO","es_EC","es_ES",
            "es_GT","es_HN","es_MX","es_NI","es_PA","es_PE","es_PR","es_PY","es_SV","es_US",
            "es_UY","es_VE","et_EE","eu_ES","eu_FR","fa_IR","fi_FI","fil_PH","fr_BE","fr_CA",
            "fr_CH","fr_FR","fr_LU","ga_IE","gl_ES","gu_IN","he_IL","hi_IN","hr_HR","hu_HU",
            "hy_AM","id_ID","is_IS","it_CH","it_IT","ja_JP","ka_GE","kk_KZ","km_KH","kn_IN",
            "ko_KR","lt_LT","lv_LV","mk_MK","ml_IN","mn_MN","mr_IN","ms_MY","mt_MT","nb_NO",
            "ne_NP","nl_AW","nl_BE","nl_NL","nn_NO","or_IN","pa_IN","pa_PK","pl_PL","pt_BR",
            "pt_PT","ro_RO","ru_RU","ru_UA","si_LK","sk_SK","sl_SI","sq_AL","sq_MK","sr_ME",
            "sr_RS","sv_FI","sv_SE","ta_IN","ta_LK","te_IN","th_TH","tr_CY","tr_TR","uk_UA",
            "ur_IN","ur_PK","uz_UZ","vi_VN","zh_CN","zh_HK","zh_SG","zh_TW",
        ])
        self.locale_dropdown.setStyleSheet(DROPDOWN_STYLE)
        layout.addWidget(self.locale_dropdown)

        add_btn = QPushButton("Add to Script")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self.add_locale_to_script)
        layout.addWidget(add_btn)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def add_locale_to_script(self):
        self.chat_display.append(f"✓ Locale {self.locale_dropdown.currentText()} added\n")

    def make_settings_page(self):
        page        = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        title = QLabel("Settings")
        title.setStyleSheet(TITLE_STYLE)
        main_layout.addWidget(title)

        section_style = "color: #89b4fa; font-size: 15px; font-weight: bold; margin-top: 10px;"

        def make_row(label_text, widget):
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setStyleSheet(LABEL_STYLE)
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(widget)
            main_layout.addLayout(row)

        def make_section(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(section_style)
            main_layout.addWidget(lbl)

        def make_input(placeholder):
            w = QLineEdit()
            w.setPlaceholderText(placeholder)
            w.setStyleSheet(INPUT_STYLE)
            w.setFixedWidth(200)
            return w

        def make_dropdown(*items):
            w = QComboBox()
            w.addItems(items)
            w.setStyleSheet(DROPDOWN_STYLE)
            w.setFixedWidth(200)
            return w

        make_section("System")
        self.hostname_input = make_input("archlinux")
        make_row("Hostname", self.hostname_input)
        self.username_input = make_input("user")
        make_row("Username", self.username_input)
        self.password_input = make_input("password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        make_row("Password", self.password_input)
        self.root_password_input = make_input("root password")
        self.root_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        make_row("Root Password", self.root_password_input)
        self.timezone_dropdown = make_dropdown(
            "UTC","America/New_York","America/Los_Angeles","Europe/London",
            "Europe/Berlin","Asia/Tokyo","Asia/Kolkata","Asia/Shanghai","Australia/Sydney"
        )
        make_row("Timezone", self.timezone_dropdown)
        self.shell_dropdown = make_dropdown("bash", "zsh", "fish")
        make_row("Shell", self.shell_dropdown)

        make_section("Boot")
        self.bootloader_dropdown = make_dropdown("GRUB", "systemd-boot")
        make_row("Bootloader", self.bootloader_dropdown)
        self.kernel_dropdown = make_dropdown("linux", "linux-lts", "linux-zen")
        make_row("Kernel", self.kernel_dropdown)

        make_section("Display")
        self.autologin_check = QCheckBox()
        self.autologin_check.setStyleSheet(CHECKBOX_STYLE)
        make_row("Auto-login", self.autologin_check)
        self.display_manager_dropdown = make_dropdown("SDDM", "GDM", "LightDM")
        make_row("Display Manager", self.display_manager_dropdown)

        make_section("Security")
        self.firewall_check = QCheckBox()
        self.firewall_check.setStyleSheet(CHECKBOX_STYLE)
        make_row("Enable Firewall (ufw)", self.firewall_check)
        self.ssh_check = QCheckBox()
        self.ssh_check.setStyleSheet(CHECKBOX_STYLE)
        make_row("Enable SSH", self.ssh_check)

        make_section("Misc")
        self.flatpak_check = QCheckBox()
        self.flatpak_check.setStyleSheet(CHECKBOX_STYLE)
        make_row("Enable Flatpak", self.flatpak_check)
        self.multilib_check = QCheckBox()
        self.multilib_check.setStyleSheet(CHECKBOX_STYLE)
        make_row("Enable Multilib Repo", self.multilib_check)
        self.parallel_downloads = make_input("5")
        make_row("Parallel Downloads", self.parallel_downloads)

        add_btn = QPushButton("Add to Script")
        add_btn.setStyleSheet(BTN_PRIMARY)
        add_btn.clicked.connect(self.add_settings_to_script)
        main_layout.addWidget(add_btn)
        main_layout.addStretch()

        scroll    = QScrollArea()
        container = QWidget()
        container.setLayout(main_layout)
        scroll.setWidget(container)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: #181825;")

        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll)
        page.setLayout(page_layout)
        return page

    def add_settings_to_script(self):
        self.chat_display.append(
            f"✓ Settings added: Host={self.hostname_input.text() or 'archlinux'}, "
            f"User={self.username_input.text() or 'user'}, "
            f"Shell={self.shell_dropdown.currentText()}, "
            f"Bootloader={self.bootloader_dropdown.currentText()}, "
            f"Kernel={self.kernel_dropdown.currentText()}\n"
        )

    def make_dotFilesPage(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        title  = QLabel("Dot Files")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        for name, url in {
            "Chezmoi":  "https://chezmoi.io",
            "YADM":     "https://yadm.io",
            "GNU Stow": "https://gnu.org/software/stow",
        }.items():
            self._make_link_row(layout, name, url)

        lbl = QLabel("Paste the dot file's URL:")
        lbl.setStyleSheet(LABEL_STYLE)
        layout.addWidget(lbl)

        self.dot_file_url = QLineEdit()
        self.dot_file_url.setPlaceholderText("https://example.com/")
        self.dot_file_url.setStyleSheet(INPUT_STYLE)
        layout.addWidget(self.dot_file_url)

        dot_add_btn = QPushButton("Add To Script")
        dot_add_btn.setStyleSheet(BTN_PRIMARY)
        dot_add_btn.clicked.connect(self.add_dot_file_to_script)
        layout.addWidget(dot_add_btn)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def add_dot_file_to_script(self):
        self.chat_display.append("✓ Dot File Added\n")

    def add_background_to_script(self):
        self.chat_display.append("✓ Background added\n")

    # ── In-app API Key management page ──
    def make_api_key_page(self):
        page   = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        title = QLabel("⚙ API Key")
        title.setStyleSheet(TITLE_STYLE)
        layout.addWidget(title)

        cfg     = load_config()
        current = cfg.get("groq_api_key", "")
        masked  = f"gsk_...{current[-6:]}" if len(current) > 10 else "(not set)"
        self._key_status_lbl = QLabel(f"Current key: {masked}")
        self._key_status_lbl.setStyleSheet("color: #bac2de; font-size: 13px;")
        layout.addWidget(self._key_status_lbl)

        get_key_btn = QPushButton("🌐  Get a free API key at console.groq.com")
        get_key_btn.setStyleSheet(
            "background-color: #313244; color: #89b4fa; padding: 8px;"
            "border: 1px solid #89b4fa; border-radius: 6px; font-size: 13px;"
        )
        get_key_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_key_btn.clicked.connect(lambda: webbrowser.open("https://console.groq.com/keys"))
        layout.addWidget(get_key_btn)

        self._new_key_input = QLineEdit()
        self._new_key_input.setPlaceholderText("Paste new key here (gsk_...)")
        self._new_key_input.setStyleSheet(
            "background-color: #313244; color: white; padding: 10px;"
            "border: 1px solid #45475a; border-radius: 6px; font-size: 14px;"
        )
        self._new_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self._new_key_input)

        show_cb = QCheckBox("Show key")
        show_cb.setStyleSheet("color: #bac2de; font-size: 12px;" + CHECKBOX_STYLE)
        show_cb.stateChanged.connect(
            lambda s: self._new_key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if s else QLineEdit.EchoMode.Password
            )
        )
        layout.addWidget(show_cb)

        save_btn = QPushButton("Update Key")
        save_btn.setStyleSheet(BTN_SUCCESS)
        save_btn.clicked.connect(self._update_api_key)
        layout.addWidget(save_btn)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _update_api_key(self):
        new_key = self._new_key_input.text().strip()
        if not new_key:
            QMessageBox.warning(self, "Empty", "Paste a key first.")
            return
        if not new_key.startswith("gsk_"):
            QMessageBox.warning(self, "Bad format", "Groq keys start with 'gsk_'. Check the key.")
            return
        save_config({"groq_api_key": new_key})
        init_groq_client(new_key)
        masked = f"gsk_...{new_key[-6:]}"
        self._key_status_lbl.setText(f"Current key: {masked}")
        self._new_key_input.clear()
        QMessageBox.information(self, "Saved", "API key updated successfully.")

    def make_apps_page(self):
        page        = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("Discover Apps")
        title.setStyleSheet("color: white; font-size: 22px; font-weight: bold;")
        main_layout.addWidget(title)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search Arch packages...")
        self.search_bar.setStyleSheet("background: #313244; color: white; padding: 8px;")
        self.search_bar.returnPressed.connect(self.new_search)
        main_layout.addWidget(self.search_bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.verticalScrollBar().valueChanged.connect(self.handle_scroll)

        self.container = QWidget()
        self.grid = QGridLayout()
        self.grid.setSpacing(15)
        self.container.setLayout(self.grid)
        self.scroll.setWidget(self.container)
        main_layout.addWidget(self.scroll)

        add_btn = QPushButton("Add Selected Apps")
        add_btn.setStyleSheet("background: #89b4fa; color: black; padding: 10px;")
        add_btn.clicked.connect(self.add_apps_to_script)
        main_layout.addWidget(add_btn)

        self.app_cards     = []
        self.current_query = ""
        self.page_index    = 1
        self.loading       = False

        self.search_bar.setText("browser")
        QTimer.singleShot(0, self.new_search)

        page.setLayout(main_layout)
        return page

    def new_search(self):
        self.current_query = self.search_bar.text()
        self.page_index    = 1
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.setParent(None)
        self.app_cards.clear()
        self.load_more()

    def load_more(self):
        if self.loading or not self.current_query:
            return
        self.loading = True

        self._fetch_worker = FetchWorker(self.current_query, self.page_index)
        self._fetch_thread = QThread()
        self._fetch_worker.moveToThread(self._fetch_thread)
        self._fetch_thread.started.connect(self._fetch_worker.run)
        self._fetch_worker.finished.connect(self._on_packages_fetched)
        self._fetch_worker.finished.connect(self._fetch_thread.quit)
        self._fetch_worker.finished.connect(self._fetch_worker.deleteLater)
        self._fetch_thread.finished.connect(self._fetch_thread.deleteLater)
        self._fetch_thread.start()

    def _on_packages_fetched(self, results):
        row = self.grid.rowCount()
        col = 0
        for name, desc in results:
            card = AppCard(name, desc)
            self.grid.addWidget(card, row, col)
            self.app_cards.append(card)
            col += 1
            if col == 4:
                col  = 0
                row += 1
        self.page_index += 1
        self.loading = False

    def handle_scroll(self):
        bar = self.scroll.verticalScrollBar()
        if bar.value() > bar.maximum() - 100:
            self.load_more()

    def add_apps_to_script(self):
        selected = [c.name for c in self.app_cards if c.selected]
        if not selected:
            self.chat_display.append("⚠ No apps selected\n")
            return
        current = self.script_output.toPlainText()
        if "# Apps" not in current:
            current += "\n\n# Apps\n"
        current += f"sudo pacman -S --noconfirm {' '.join(selected)}\n"
        self.script_output.setPlainText(current)
        self.chat_display.append(f"✓ Apps added: {', '.join(selected)}\n")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────
def get_or_ask_api_key(app: QApplication) -> str | None:
    """
    Returns a valid API key string, or None if the user quits.
    Shows the dialog on first run; re-shows it if the saved key is empty.
    """
    cfg = load_config()
    key = cfg.get("groq_api_key", "").strip()

    if key:
        return key                         # already configured, skip dialog

    # First launch — show the dialog
    while True:
        dlg = ApiKeyDialog()
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None                    # user hit Quit
        key = dlg.get_key()
        if key:
            save_config({"groq_api_key": key})
            return key


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    key = get_or_ask_api_key(app)
    if not key:
        sys.exit(0)

    init_groq_client(key)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())