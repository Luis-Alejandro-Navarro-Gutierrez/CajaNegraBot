# 🎬 CajaNegra Studio // Shorts Automation Suite

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-API-F55036?style=for-the-badge)](https://groq.com)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter-blue?style=for-the-badge)](https://github.com/TomSchimansky/CustomTkinter)
[![Whisper](https://img.shields.io/badge/Subtitles-OpenAI%20Whisper-412991?style=for-the-badge)](https://github.com/openai/whisper)
[![ComfyUI](https://img.shields.io/badge/ImageGen-ComfyUI-black?style=for-the-badge)](https://github.com/comfyanonymous/ComfyUI)

> **CajaNegra Studio** es una estación de trabajo de escritorio y un pipeline automatizado para la creación de videos documentales en formato vertical (YouTube Shorts, Reels, TikTok) sobre curiosidades reales, ciencia y eventos históricos. 

El sistema integra modelos de lenguaje mediante **Groq**, síntesis neuronal de voz con **Edge-TTS**, generación visual local de cómic vía **ComfyUI**, composición cinemática mediante **MoviePy** y subtitulado dinámico palabra por palabra con **OpenAI Whisper** y **FFmpeg**.

---

## 🖥️ Interfaz Gráfica (Studio Dashboard)

La aplicación cuenta con una suite visual de tres columnas optimizada con descanso ocular (Charcoal/Slate):

* **Panel de Pipeline:** Selección de temas manuales o rotación automática en 10 categorías documentales (Ciberseguridad, Robos Legendarios, Ciencia Extrema, etc.), barra de progreso e indicador de telemetría en tiempo real.
* **Centro de Publicación:** Título dinámico optimizado con contador de caracteres, descripción para copiar y pegar y tracking de slots horarios programados.
* **Monitor de Escenas y Reproductor:** Vista previa en vivo de las escenas generadas por ComfyUI y botón de previsualización con audio nativo sincronizado.
* **Gestor de Almacenamiento:** Botón para purgar activos intermedios (JSONs, imágenes y audios temporales) protegiendo el video final renderizado.

---

## ⚙️ Arquitectura del Pipeline

```text
[Idea / Rotación Temática] 
           │
           ▼
[Groq LLM] ──────────► Guion estructurado (~80s / 180-200 palabras)
           │
           ├─────────► [Edge-TTS] ──► Síntesis de voz en off (Álvaro)
           │
           ├─────────► [Groq Prompts] ──► [ComfyUI Local] ──► 12 Ilustraciones Cómic (SDXL)
           │
           ▼
[MoviePy Engine] ────► Montaje 9:16 + Movimiento Ken Burns + Pista de Música
           │
           ▼
[Whisper + FFmpeg] ──► Transcripción temporal y quemado de subtítulos ASS
           │
           ▼
[Outputs / Videos] ──► Short definitivo listo para publicación (.mp4)
```

---

## 📋 Requisitos Previos

1. **Python 3.12+** instalado en el sistema.
2. **FFmpeg** instalado y registrado en las variables de entorno del sistema (`PATH`).
3. **ComfyUI** ejecutándose localmente (`http://127.0.0.1:8188`) con el checkpoint `arthemyComicsXL_v20.safetensors` (o tu modelo preferido).
4. Cuenta en **Groq Console** para obtener una API Key gratuita o de pago.

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone [https://github.com/tu-usuario/CajaNegraBot.git]
cd CajaNegraBot
```

### 2. Crear y activar el entorno virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crea un archivo `.env` en la raíz del proyecto a partir de la siguiente plantilla:
```ini
# API Key de Groq ([https://console.groq.com](https://console.groq.com))
GROQ_API_KEY=tu_groq_api_key_aqui

# Configuración de ComfyUI Local
COMFYUI_URL=[http://127.0.0.1:8188](http://127.0.0.1:8188)
COMFYUI_CHECKPOINT=arthemyComicsXL_v20.safetensors
```

### 5. Iniciar la aplicación
* **Modo GUI (Recomendado):**
  ```bash
  python app_gui.py
  ```
* **Modo CLI (Terminal por lotes):**
  ```bash
  python main.py
  ```

---

## 📦 Compilación a Ejecutable (.exe)

Para generar la versión portable sin consola externa:

```bash
pyinstaller --noconsole --onefile --clean --collect-data whisper --collect-data customtkinter --name "CajaNegra_Studio" app_gui.py
```

El ejecutable resultante se ubicará en `dist/CajaNegra_Studio.exe`.

---

## 📂 Estructura del Proyecto

```text
├── assets/                  # Fondos musicales y recursos estáticos
├── app_gui.py               # Interfaz gráfica de usuario (CustomTkinter)
├── generator.py             # Generación de guiones con Groq
├── images.py                # Cliente API para ComfyUI y generación de prompts
├── main.py                  # Orquestador del pipeline y rotación temática
├── metadata.py              # Exportación de títulos y descripciones optimizadas
├── subtitles.py             # Transcripción con Whisper y subtitulado FFmpeg
├── tts.py                   # Síntesis de voz neuronal (Edge-TTS)
├── video.py                 # Montaje de video con MoviePy y animación Ken Burns
├── requirements.txt         # Librerías necesarias del proyecto
├── .env.example             # Plantilla de variables de entorno
└── README.md                # Documentación del proyecto
```

---

## 📄 Licencia

Distribuido bajo la Licencia MIT. Consulta `LICENSE` para más información.