<p align="right">
  <a href="./README.md">English</a> | <b>Español</b>
</p>

# 🎬 CajaNegra Studio

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-API-F55036?style=for-the-badge)](https://groq.com)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blue?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Whisper](https://img.shields.io/badge/Subtitles-OpenAI%20Whisper-412991?style=for-the-badge)](https://github.com/openai/whisper)
[![ComfyUI](https://img.shields.io/badge/ImageGen-ComfyUI-black?style=for-the-badge)](https://github.com/comfyanonymous/ComfyUI)

**CajaNegra Studio** es una aplicación de escritorio y un conjunto de pipelines para producir videos documentales sobre curiosidades reales, ciencia, historia y casos insólitos. Incluye dos formatos: Shorts verticales bilingües y documentales largos en español.

La interfaz gráfica está construida con CustomTkinter. La generación de guiones y metadata usa Groq; las voces se sintetizan con Edge-TTS; las ilustraciones se generan localmente mediante ComfyUI; y el montaje y subtitulado utilizan MoviePy, FFmpeg y Whisper.

## Formatos de producción

### Shorts verticales

El flujo de Shorts crea videos 9:16 para YouTube Shorts, Reels y TikTok. Puede partir de un tema manual o seleccionar uno automáticamente, evitando temas recientes del historial y rotando entre categorías. Genera guiones en español e inglés, imágenes de escenas en estilo cómic, locución, subtítulos palabra por palabra, montaje con movimiento Ken Burns y archivos de metadata.

```text
[Tema manual o rotación temática]
              ↓
       [Guion con Groq]
        ↙            ↘
[Voz Edge-TTS]   [Prompts + ComfyUI]
        ↘            ↙
       [Montaje vertical]
              ↓
 [Whisper + FFmpeg: subtítulos]
              ↓
     [Short MP4 + metadata]
```

### Documentales largos

El flujo de documentales crea episodios narrados en español, de aproximadamente 8–10 minutos, organizados en 36 escenas sincronizadas. El guion se guarda como expediente; después se producen la locución y las ilustraciones panorámicas 16:9. El pipeline compone una miniatura con texto, ensambla el video con movimiento Ken Burns y subtítulos sincronizados por escena, y genera metadata de YouTube con descripción y marcas de tiempo.

```text
[Plan del episodio y guion de 36 escenas]
                    ↓
       [Locución Edge-TTS + tiempos]
                    +
       [36 imágenes 16:9 en ComfyUI]
                    ↓
        [Miniatura + ensamblaje]
                    ↓
 [Video MP4 + metadata y timestamps]
```

El generador planifica episodios alrededor de casos e historias insólitas y mantiene un historial de temas para reducir repeticiones. La duración final depende de la narración generada.

## Interfaz gráfica

Inicia `app_gui.py` para abrir CajaNegra Studio. El panel permite trabajar con Shorts y documentales largos, ver el progreso y los registros de producción, revisar escenas y previsualizar contenido. También incluye utilidades de publicación y limpieza de archivos intermedios.

Entre sus funciones están la selección manual o rotación automática de temas, monitor de escenas de ComfyUI, previsualización con audio, utilidades para preparar la publicación y limpieza de activos intermedios.

## Requisitos

1. Python 3.12 o posterior.
2. FFmpeg, con `ffmpeg` y `ffprobe` disponibles en `PATH`.
3. ComfyUI ejecutándose localmente, por defecto en `http://127.0.0.1:8188`, con un checkpoint compatible con SDXL instalado. El valor predeterminado configurado es `arthemyComicsXL_v20.safetensors`.
4. Una API key de Groq.

## Instalación

```powershell
git clone https://github.com/Luis-Alejandro-Navarro-Gutierrez/CajaNegraBot.git
cd CajaNegraBot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Crea un archivo `.env` en la raíz del proyecto:

```ini
GROQ_API_KEY=tu_groq_api_key
COMFYUI_URL=http://127.0.0.1:8188
COMFYUI_CHECKPOINT=arthemyComicsXL_v20.safetensors
```

## Ejecución

### Aplicación gráfica

```powershell
python app_gui.py
```

### Pipeline de Shorts por terminal

```powershell
python main.py
```

### Pipeline completo de documental largo por terminal

```powershell
python longform_pipeline.py
```

El pipeline largo ejecuta, en orden, la generación del guion, la producción de voz e imágenes, la creación de miniatura, el ensamblaje y la generación de metadata. ComfyUI debe estar activo antes de iniciar cualquiera de los flujos que generen imágenes.

## Archivos de salida

Los resultados se guardan bajo `outputs/`:

| Ruta | Contenido |
| --- | --- |
| `outputs/json/` | Guiones de Shorts en JSON |
| `outputs/audio/` | Voces y tiempos de Shorts |
| `outputs/images/` y `outputs/prompts/` | Imágenes y prompts de Shorts |
| `outputs/videos/` | Videos finales MP4 de ambos formatos |
| `outputs/documentales_largos/` | Guiones estructurados de documentales largos |
| `outputs/produccion_largos/<episodio>/` | Voz, imágenes, tiempos y miniatura del documental |
| `outputs/metadata/` | Metadata generada para publicación |

Los historiales de temas se guardan en `historial_temas.json` y `historial_largos.json` en la raíz del proyecto.

## Módulos principales

| Archivo | Responsabilidad |
| --- | --- |
| `app_gui.py` | Interfaz gráfica |
| `main.py` | Orquestación de Shorts y selección de temas |
| `generator.py`, `images.py`, `tts.py` | Guiones, imágenes y voz para Shorts |
| `video.py`, `subtitles.py`, `metadata.py` | Montaje, subtítulos y metadata para Shorts |
| `longform_pipeline.py` | Orquestación de documentales largos |
| `longform_generator.py`, `longform_producer.py` | Guion, voz e imágenes de documentales |
| `crear_miniatura.py`, `longform_assembler.py`, `longform_metadata.py` | Miniatura, montaje y metadata de documentales |
| `assets/` | Recursos estáticos como música y logos |

## Compilar un ejecutable

El proyecto incluye una especificación de PyInstaller (`CajaNegra_Studio.spec`). La compilación depende de que las dependencias y recursos requeridos por la aplicación estén disponibles en el entorno. El comando de empaquetado de la GUI es:

```powershell
pyinstaller --noconsole --onefile --clean --collect-data whisper --collect-data customtkinter --name "CajaNegra_Studio" app_gui.py
```

## Licencia

La documentación anterior declara una licencia MIT, pero este checkout no incluye un archivo `LICENSE`. Añade el archivo de licencia correspondiente si quieres distribuir formalmente el proyecto bajo esos términos.
