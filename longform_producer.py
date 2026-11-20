"""
Módulo de producción de audio (TTS Edge) e imágenes sincronizadas (ComfyUI)
para documentales largos con estructura 1:1 de 36 escenas panorámicas 16:9.
Estilo visual: Animación 2D estilizada / Novela gráfica y cómic oscuro.
Canal: La Caja Negra
"""
import os
import sys
import json
import time
import uuid
import secrets
import asyncio
import subprocess
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
import requests
from PIL import Image
import edge_tts

# ========================================================
# RUTAS Y VARIABLES PERSISTENTES
# ========================================================
if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

VOZ_DOCUMENTAL = "es-ES-AlvaroNeural"

# Configuración de ComfyUI (16:9 Nativo SDXL)
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_CHECKPOINT = os.getenv("COMFYUI_CHECKPOINT", "arthemyComicsXL_v20.safetensors")
COMFYUI_WIDTH = 1344
COMFYUI_HEIGHT = 768
COMFYUI_OUTPUT_DIR = Path(os.getenv("COMFYUI_OUTPUT_DIR", str(BASE_DIR / "outputs" / "comfyui"))).expanduser().resolve()

# Modificadores de estilo consistentes para SDXL
# Modificadores para estilo Cómic Limpio / Novela Gráfica Iluminada
STYLE_SUFFIX = (
    ", modern comic book illustration, clear ink outlines, clean lineart, "
    "graphic novel art style, flat cel shading, vibrant soft colors, "
    "bright atmospheric lighting, detailed background, European comic aesthetic, 16:9 ratio"
)

NEGATIVE_PROMPT_CARTOON = (
    "dark, gritty, grim, heavy shadows, arcane style, 3d render, CGI, realism, photorealistic, "
    "real life photo, 35mm photograph, DSLR, blurry, deformed face, bad hands, missing fingers, "
    "extra fingers, text, watermark, signature, borders, split frame"
)


def _obtener_ultimo_expediente_json() -> Path:
    directorio = BASE_DIR / "outputs" / "documentales_largos"
    archivos = list(directorio.glob("*.json"))
    if not archivos:
        raise FileNotFoundError("No hay archivos JSON en outputs/documentales_largos")
    return max(archivos, key=lambda f: f.stat().st_mtime)


def _obtener_duracion_audio(ruta_audio: Path) -> float:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(ruta_audio),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())


# ========================================================
# COMUNICACIÓN DIRECTA CON COMFYUI (16:9)
# ========================================================
def _crear_workflow_comfy_16_9(prompt: str, negative_prompt: str, seed: int, prefijo: str) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": COMFYUI_CHECKPOINT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": COMFYUI_WIDTH, "height": COMFYUI_HEIGHT, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 28,
                "cfg": 6.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefijo, "images": ["6", 0]}},
    }


def renderizar_en_comfyui(prompt: str, ruta_salida: Path):
    prompt_con_estilo = f"{prompt.rstrip(' ,.')}{STYLE_SUFFIX}"

    workflow = _crear_workflow_comfy_16_9(
        prompt=prompt_con_estilo,
        negative_prompt=NEGATIVE_PROMPT_CARTOON,
        seed=secrets.randbelow(2**32 - 1),
        prefijo=f"CajaNegra_16_9_{ruta_salida.stem}",
    )

    try:
        resp = requests.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow, "client_id": str(uuid.uuid4())},
            timeout=30,
        )
    except requests.RequestException as err:
        raise RuntimeError(f"No se pudo conectar a ComfyUI en {COMFYUI_URL}. ¿Está abierto?") from err

    if not resp.ok:
        raise RuntimeError(f"ComfyUI rechazó la imagen (HTTP {resp.status_code}): {resp.text}")

    prompt_id = resp.json().get("prompt_id")
    limite = time.monotonic() + 600
    imagen_info = None

    while time.monotonic() < limite:
        hist_resp = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=30)
        hist_resp.raise_for_status()
        entrada = hist_resp.json().get(prompt_id)
        if entrada:
            salida = entrada.get("outputs", {}).get("7", {})
            imagenes = salida.get("images", [])
            if imagenes:
                imagen_info = imagenes[0]
                break
        time.sleep(1)

    if imagen_info is None:
        raise TimeoutError("ComfyUI tardó demasiado en responder.")

    img_resp = requests.get(
        f"{COMFYUI_URL}/view",
        params={
            "filename": imagen_info["filename"],
            "subfolder": imagen_info.get("subfolder", ""),
            "type": imagen_info.get("type", "output"),
        },
        timeout=120,
    )
    img_resp.raise_for_status()

    with Image.open(BytesIO(img_resp.content)) as im:
        im.convert("RGB").save(ruta_salida, format="JPEG", quality=95)

    nombre_png = Path(imagen_info["filename"])
    subc = Path(imagen_info.get("subfolder", ""))
    ruta_png = (COMFYUI_OUTPUT_DIR / subc / nombre_png).resolve()
    if ruta_png.exists() and ruta_png.suffix.lower() == ".png":
        try:
            ruta_png.unlink()
        except OSError:
            pass


# ========================================================
# GENERACIÓN DE AUDIO Y SECUENCIAS
# ========================================================
async def _comunicar_edge_tts(texto: str, ruta_salida: Path):
    comunicador = edge_tts.Communicate(texto, VOZ_DOCUMENTAL, rate="-3%", pitch="-2Hz")
    await comunicador.save(str(ruta_salida))


def sintetizar_bloque_tts(texto: str, ruta_salida: Path):
    """Ejecuta la síntesis de forma síncrona y segura en cualquier hilo."""
    asyncio.run(_comunicar_edge_tts(texto, ruta_salida))


def producir_locucion_sincronizada(guion_estructurado: list, carpeta_salida: Path) -> tuple[Path, list[float]]:
    carpeta_audios_temp = carpeta_salida / "temp_audios"
    carpeta_audios_temp.mkdir(parents=True, exist_ok=True)

    duraciones_escenas = []
    rutas_clips = []

    print("\n[1/3] 🎙️ Sintetizando narración escena por escena (36 bloques)...")

    for idx, bloque in enumerate(guion_estructurado, start=1):
        ruta_clip = carpeta_audios_temp / f"audio_escena_{idx}.mp3"
        texto = bloque["texto"]

        if not ruta_clip.exists():
            print(f"  • Locución escena {idx}/{len(guion_estructurado)}...")
            sintetizar_bloque_tts(texto, ruta_clip)
        else:
            print(f"  • Escena {idx} en caché.")

        dur = _obtener_duracion_audio(ruta_clip)
        duraciones_escenas.append(dur)
        rutas_clips.append(ruta_clip)

    archivo_concat_audio = carpeta_salida / "concat_audio.txt"
    with open(archivo_concat_audio, "w", encoding="utf-8") as f:
        for r in rutas_clips:
            f.write(f"file '{r.as_posix()}'\n")

    ruta_master_audio = carpeta_salida / "locucion_completa.mp3"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(archivo_concat_audio),
        "-c", "copy",
        str(ruta_master_audio),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    if archivo_concat_audio.exists():
        archivo_concat_audio.unlink(missing_ok=True)

    dur_total = sum(duraciones_escenas)
    print(f"✔ Audio master unificado: {dur_total:.2f} s (~{dur_total / 60:.2f} min)")
    return ruta_master_audio, duraciones_escenas


def producir_imagenes_comfyui(guion_estructurado: list, carpeta_salida: Path):
    carpeta_img = carpeta_salida / "imagenes_16_9"
    carpeta_img.mkdir(parents=True, exist_ok=True)

    print("\n[2/3] 🎨 Renderizando 36 ilustraciones animadas en ComfyUI (16:9 SDXL)...")
    total_escenas = len(guion_estructurado)

    for idx, bloque in enumerate(guion_estructurado, start=1):
        ruta_img = carpeta_img / f"escena_{idx}.jpg"

        if ruta_img.exists() and ruta_img.stat().st_size > 5000:
            print(f"  • Escena {idx}/{total_escenas} ya existe en disco.")
            continue

        prompt = bloque["prompt_visual"]
        print(f"  • [ComfyUI] Renderizando escena animada {idx}/{total_escenas}...")
        renderizar_en_comfyui(prompt, ruta_img)


def producir_miniatura_base(titulo: str, carpeta_salida: Path):
    ruta_miniatura = carpeta_salida / "miniatura_raw.jpg"
    if ruta_miniatura.exists() and ruta_miniatura.stat().st_size > 5000:
        print("  • Miniatura base ya existe en disco.")
        return

    print("\n[3/3] 🖼️ Generando arte animado para miniatura de YouTube (16:9)...")
    prompt_miniatura = (
        f"Modern comic book cover art for story titled '{titulo}', "
        "expressive character with clear reaction, clean ink outlines, "
        "vibrant warm colors, soft natural lighting, graphic novel illustration, "
        "clean composition without text, 16:9 aspect ratio"
    )
    renderizar_en_comfyui(prompt_miniatura, ruta_miniatura)
    print(f"✔ Miniatura base guardada en:\n  📁 {ruta_miniatura}")


def ejecutar_produccion():
    archivo_json = _obtener_ultimo_expediente_json()
    datos = json.loads(archivo_json.read_text(encoding="utf-8"))

    slug = archivo_json.stem
    carpeta_produccion = BASE_DIR / "outputs" / "produccion_largos" / slug
    carpeta_produccion.mkdir(parents=True, exist_ok=True)

    print("====================================================")
    print(f" 🎬 PRODUCCIÓN DE EXPEDIENTE: {datos['titulo']}")
    print(f" 📁 Directorio de trabajo: {carpeta_produccion}")
    print("====================================================")

    guion = datos["guion_estructurado"]

    # 1. Locución
    _, duraciones = producir_locucion_sincronizada(guion, carpeta_produccion)

    # Guardar mapa de tiempos
    mapa_tiempos = carpeta_produccion / "tiempos_sincronizados.json"
    mapa_tiempos.write_text(json.dumps(duraciones, indent=2), encoding="utf-8")

    # 2. Generación en ComfyUI
    producir_imagenes_comfyui(guion, carpeta_produccion)

    # 3. Miniatura base
    producir_miniatura_base(datos["titulo"], carpeta_produccion)

    print("\n🎉 Producción completa de audios e imágenes finalizada.")


if __name__ == "__main__":
    ejecutar_produccion()