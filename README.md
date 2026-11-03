<p align="right">
  <b>English</b> | <a href="./README.es.md">Español</a>
</p>

# 🎬 CajaNegra Studio // Shorts Automation Suite

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-API-F55036?style=for-the-badge)](https://groq.com)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blue?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Whisper](https://img.shields.io/badge/Subtitles-OpenAI%20Whisper-412991?style=for-the-badge)](https://github.com/openai/whisper)
[![ComfyUI](https://img.shields.io/badge/ImageGen-ComfyUI-black?style=for-the-badge)](https://github.com/comfyanonymous/ComfyUI)

> **CajaNegra Studio** is a desktop workstation and automated pipeline designed to create vertical documentary videos (YouTube Shorts, Reels, TikTok) focused on real-world curiosities, science, and historical events.

The system integrates **Groq** for scriptwriting, **Edge-TTS** for neural voice synthesis, local comic-style generation via **ComfyUI (SDXL)**, cinematic composition through **MoviePy**, and word-by-word dynamic subtitles powered by **OpenAI Whisper** and **FFmpeg**.

---

## 🖥️ Graphical Interface (Studio Dashboard)

The desktop application features a three-column layout styled with an eye-comfort Charcoal/Slate palette:

* **Pipeline Control Panel:** Supports custom topics or automated cyclic rotation across 10 documentary niches, real-time progress tracking, and telemetry output console.
* **Publishing Center:** Dynamic title formatting with a character counter, ready-to-copy description templates, and schedule slot checkboxes.
* **Scene Monitor & Native Preview:** Live monitor tracking ComfyUI scene renders, along with an on-demand preview button with synchronized audio.
* **Storage Manager:** Dedicated action to safely purge intermediate files (JSON, audio, and scene images) while keeping the final rendered video intact.

---

## ⚙️ Pipeline Architecture

```text
[Topic Input / Cyclic Rotation] 
           │
           ▼
[Groq LLM] ──────────► Structured Script (~80s / 180-200 words)
           │
           ├─────────► [Edge-TTS] ──► Voiceover Synthesis (Spanish - Álvaro)
           │
           ├─────────► [Groq Prompts] ──► [Local ComfyUI] ──► 12 Comic Frames (SDXL)
           │
           ▼
[MoviePy Engine] ────► 9:16 Assembly + Ken Burns Zoom + Background Audio Loop
           │
           ▼
[Whisper + FFmpeg] ──► Word Timestamp Alignment & Burned ASS Subtitles
           │
           ▼
[Outputs / Videos] ──► Production-ready Short (.mp4)
```

---

## 📋 Prerequisites

1. **Python 3.12+** installed.
2. **FFmpeg** installed and accessible via system `PATH`.
3. **ComfyUI** running locally at `http://127.0.0.1:8188` with the `arthemyComicsXL_v20.safetensors` checkpoint.
4. An active **Groq Console** API Key.

---

## 🚀 Setup & Installation

### 1. Clone the repository
```bash
git clone [https://github.com/Luis-Alejandro-Navarro-Gutierrez/CajaNegraBot.git](https://github.com/Luis-Alejandro-Navarro-Gutierrez/CajaNegraBot.git)
cd CajaNegraBot
```

### 2. Set up a virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Create a `.env` file in the project root:
```ini
GROQ_API_KEY=your_groq_api_key_here
COMFYUI_URL=[http://127.0.0.1:8188](http://127.0.0.1:8188)
COMFYUI_CHECKPOINT=arthemyComicsXL_v20.safetensors
```

### 5. Launch the application
* **GUI Mode (Recommended):**
  ```bash
  python app_gui.py
  ```
* **CLI Mode (Batch execution):**
  ```bash
  python main.py
  ```

---

## 📦 Build Executable (.exe)

To bundle the application into a standalone binary:

```bash
pyinstaller --noconsole --onefile --clean --collect-data whisper --collect-data customtkinter --name "CajaNegra_Studio" app_gui.py
```

The compiled binary will be placed inside `dist/CajaNegra_Studio.exe`.

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.