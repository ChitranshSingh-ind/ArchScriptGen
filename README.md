![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

# 🚀 ArchScriptGen

**ArchScriptGen** is a GUI-based tool that helps you generate complete Arch Linux installation and configuration scripts using AI.

Built with **PyQt6 + Groq API**, this app makes it easy to create customized Arch setups without manually writing complex bash scripts.

---

## ✨ Features

* 🖥️ Modern GUI (PyQt6)
* 🤖 AI-powered script generation (Groq - LLaMA 3.3)
* 🎨 Theme selection with preview
* 🧩 Desktop Environment chooser (GNOME, KDE, i3, XFCE, etc.)
* 📦 Search and add apps from Arch repositories
* 🖱️ Cursor theme selection
* ⚙️ System configuration options:

  * Bootloader
  * Kernel
  * Users & passwords
  * Networking
* 🌐 Wallpaper & dotfiles integration
* 💾 Export generated scripts as `.sh` files

---

## 📦 Download

Go to the **Releases** section and download the latest version:

👉 `ArchScriptGen.zip`

---

## ▶️ How to Run

1. Download and extract the zip file
2. Open the folder
3. Double-click:

```bash
ArchScriptGen.exe
```

---

## 🔑 API Key Setup

On first launch, the app will ask for a **Groq API key**.

Get a free key here:
👉 https://console.groq.com/keys

✔ Your key is stored locally
✔ Never uploaded or shared

---

## ⚠️ Requirements

* Windows OS
* Internet connection (required for API + package search)

---

## 🧠 How It Works

1. Select your preferences (DE, apps, drivers, etc.)
2. The app sends your request to Groq AI
3. AI generates a full Arch Linux bash script
4. You can review and export it

---

## ⚠️ Disclaimer

* This tool **generates scripts only**, it does NOT install Arch Linux automatically
* Always review scripts before running them
* Use at your own risk

---

## 🛠️ Tech Stack

* Python
* PyQt6
* Groq API
* Requests
* PyInstaller

---

## 🐞 Known Issues

* First launch may be slow (PyInstaller extraction)
* Large file size due to PyQt6 bundling

---

## 🚀 Future Plans

* Full automated Arch installer scripts
* Disk partitioning UI
* ISO builder integration (archiso)
* Plugin system
* Performance improvements

---

## 🤝 Contributing

Contributions are welcome!

Feel free to:

* Open issues
* Submit pull requests
* Suggest new features

---

## ⭐ Support

If you like this project:

👉 Give it a star ⭐ on GitHub

---

## 📜 License

MIT License

---
