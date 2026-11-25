<p align="right">
  <b>English</b> | <a href="./README.es.md">Español</a>
</p>

# 🎬 CajaNegra Studio

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-API-F55036?style=for-the-badge)](https://groq.com)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blue?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Whisper](https://img.shields.io/badge/Subtitles-OpenAI%20Whisper-412991?style=for-the-badge)](https://github.com/openai/whisper)
[![ComfyUI](https://img.shields.io/badge/ImageGen-ComfyUI-black?style=for-the-badge)](https://github.com/comfyanonymous/ComfyUI)

**CajaNegra Studio** is a desktop application and a set of pipelines for producing documentary videos about real curiosities, science, history, and unusual cases. It supports two formats: bilingual vertical Shorts and long-form documentaries in Spanish.

The graphical interface is built with CustomTkinter. Groq generates scripts and metadata; Edge-TTS synthesizes narration; ComfyUI generates illustrations locally; and MoviePy, FFmpeg, and Whisper handle video assembly and subtitles.

## Production formats

### Vertical Shorts

The Shorts workflow creates 9:16 videos for YouTube Shorts, Reels, and TikTok. It can use a manually supplied topic or choose one automatically, avoiding recent topics in the history and rotating across categories. It generates Spanish and English scripts, comic-style scene images, narration, word-by-word subtitles, an edit with Ken Burns motion, and metadata files.

```text
[Manual topic or topic rotation]
               ↓
       [Script with Groq]
        ↙             ↘
 [Edge-TTS voice]  [Prompts + ComfyUI]
        ↘             ↙
        [Vertical edit]
               ↓
 [Whisper + FFmpeg: subtitles]
               ↓
       [Short MP4 + metadata]
```

### Long-form documentaries

The long-form workflow creates narrated Spanish episodes of approximately 8–10 minutes, structured as 36 synchronized scenes. The script is saved as an episode record; voiceover and panoramic 16:9 illustrations are produced next. The pipeline creates a text-overlaid thumbnail, assembles the video with Ken Burns motion and scene-synchronized subtitles, and generates YouTube metadata with a description and timestamps.

```text
[Episode plan and 36-scene script]
                   ↓
       [Edge-TTS voice + timings]
                   +
       [36 panoramic ComfyUI images]
                   ↓
        [Thumbnail + assembly]
                   ↓
 [Video MP4 + metadata and timestamps]
```

The generator plans episodes around unusual cases and stories and keeps a topic history to reduce repetition. The final runtime depends on the generated narration.

## Graphical interface

Run `app_gui.py` to open CajaNegra Studio. The dashboard supports both Shorts and long-form documentaries, displays progress and production logs, and provides scene review and content preview. It also includes publishing utilities and cleanup for intermediate files.

Features include manual topic selection or automatic topic rotation, a ComfyUI scene monitor, audio preview, publishing utilities, and cleanup of intermediate assets.

## Requirements

1. Python 3.12 or later.
2. FFmpeg, with both `ffmpeg` and `ffprobe` available on `PATH`.
3. ComfyUI running locally, at `http://127.0.0.1:8188` by default, with an SDXL-compatible checkpoint installed. The configured default is `arthemyComicsXL_v20.safetensors`.
4. A Groq API key.

## Installation

```powershell
git clone https://github.com/Luis-Alejandro-Navarro-Gutierrez/CajaNegraBot.git
cd CajaNegraBot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```ini
GROQ_API_KEY=your_groq_api_key
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_CHECKPOINT=arthemyComicsXL_v20.safetensors
```

## Running

### Desktop application

```powershell
python app_gui.py
```

### Shorts pipeline from the terminal

```powershell
python main.py
```

### Full long-form documentary pipeline from the terminal

```powershell
python longform_pipeline.py
```

The long-form pipeline runs script generation, voice and image production, thumbnail creation, video assembly, and metadata generation in sequence. ComfyUI must be running before starting either workflow that generates images.

## Output files

Results are stored under `outputs/`:

| Path | Contents |
| --- | --- |
| `outputs/json/` | Shorts scripts in JSON format |
| `outputs/audio/` | Shorts narration and timing files |
| `outputs/images/` and `outputs/prompts/` | Shorts images and prompts |
| `outputs/videos/` | Final MP4 videos from both formats |
| `outputs/documentales_largos/` | Structured long-form documentary scripts |
| `outputs/produccion_largos/<episode>/` | Documentary audio, images, timings, and thumbnail |
| `outputs/metadata/` | Generated publishing metadata |

Topic histories are stored in `historial_temas.json` and `historial_largos.json` in the project root.

## Main modules

| File | Responsibility |
| --- | --- |
| `app_gui.py` | Desktop interface |
| `main.py` | Shorts orchestration and topic selection |
| `generator.py`, `images.py`, `tts.py` | Shorts scripts, images, and narration |
| `video.py`, `subtitles.py`, `metadata.py` | Shorts assembly, subtitles, and metadata |
| `longform_pipeline.py` | Long-form documentary orchestration |
| `longform_generator.py`, `longform_producer.py` | Documentary scripts, narration, and images |
| `crear_miniatura.py`, `longform_assembler.py`, `longform_metadata.py` | Documentary thumbnail, assembly, and metadata |
| `assets/` | Static resources such as music and logos |

## Building an executable

The project includes a PyInstaller specification (`CajaNegra_Studio.spec`). Packaging depends on the application's dependencies and required resources being available in the build environment. To package the GUI, run:

```powershell
pyinstaller --noconsole --onefile --clean --collect-data whisper --collect-data customtkinter --name "CajaNegra_Studio" app_gui.py
```

## License

The previous documentation declared an MIT license, but this checkout does not include a `LICENSE` file. Add the appropriate license file if you intend to distribute the project under those terms.
