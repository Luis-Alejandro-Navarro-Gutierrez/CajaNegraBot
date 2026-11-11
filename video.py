"""Módulo para montar videos verticales con escenas sincronizadas, movimiento Ken Burns y música de fondo (ES / EN)."""

import json
import re
import sys
from pathlib import Path

import moviepy.editor as mp
import numpy as np
from PIL import Image

# ========================================================
# DETECCIÓN DE RUTA PERSISTENTE (COMPATIBLE CON .EXE)
# ========================================================
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
DURACION_TRANSICION = 0.25


def _obtener_nombre_raiz(nombre_base: str) -> str:
    """Extrae el nombre base raíz quitando los sufijos de idioma (_es, _en) para reutilizar imágenes y prompts."""
    stem = Path(nombre_base).stem
    if stem.endswith("_es") or stem.endswith("_en"):
        return stem[:-3]
    return stem


def _peso_palabras_escena(nombre_base: str, numero_escena: int, idioma: str = "es") -> int:
    """Usa el fragmento narrado de cada prompt para estimar su tiempo en pantalla."""
    nombre_raiz = _obtener_nombre_raiz(nombre_base)
    ruta_prompts = BASE_DIR / "outputs" / "prompts" / f"{nombre_raiz}_prompts.json"
    
    try:
        datos = json.loads(ruta_prompts.read_text(encoding="utf-8"))
        escenas = datos.get("escenas", [])
        escena = next((item for item in escenas if item.get("escena") == numero_escena), None)
        fragmento = escena.get("fragmento_guion", "") if escena else ""
        palabras = re.findall(r"[\w’'-]+", fragmento, flags=re.UNICODE)
        
        # Ajuste de palabras de cierre en la última escena según el idioma
        if escena and numero_escena == max((x.get("escena", 0) for x in escenas), default=0):
            if idioma == "en":
                palabras.extend(["Like", "and", "subscribe", "for", "more", "documented", "truths"])
            else:
                palabras.extend(["Dale", "Like", "y", "suscribete", "para", "mas", "contenido"])
        return max(1, len(palabras))
    except (OSError, ValueError, TypeError, AttributeError):
        return 1


def montar_video_final(
    nombre_base: str, 
    duracion_voz: float, 
    custom_logger=None, 
    ruta_audio_personalizada: Path = None,
    idioma: str = "es"
) -> Path:
    """
    Crea un video vertical con animación Ken Burns, narración sincronizada y música de fondo en loop.
    Reutiliza las mismas imágenes generadas para ambas versiones lingüísticas.
    """
    output_dir = BASE_DIR / "outputs" / "videos"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determinar ruta de audio
    if ruta_audio_personalizada and Path(ruta_audio_personalizada).exists():
        ruta_audio = Path(ruta_audio_personalizada)
    else:
        ruta_audio = BASE_DIR / "outputs" / "audio" / f"{nombre_base}.mp3"
        
    ruta_video_salida = output_dir / f"{nombre_base}.mp4"

    if not ruta_audio.exists():
        raise FileNotFoundError(f"No se encontró el audio en: {ruta_audio}")

    # Reutilizar las 12 imágenes del nombre raíz
    nombre_raiz = _obtener_nombre_raiz(nombre_base)
    img_dir = BASE_DIR / "outputs" / "images"
    lista_imagenes = sorted(
        img_dir.glob(f"{nombre_raiz}_escena_*.jpg"),
        key=lambda p: int(p.stem.split("_escena_")[-1]) if "_escena_" in p.stem else 0,
    )
    
    if not lista_imagenes:
        raise RuntimeError(f"No se encontraron imágenes en '{img_dir}' con el patrón '{nombre_raiz}_escena_*.jpg'.")
    if duracion_voz <= 0:
        raise ValueError("La duración de la voz debe ser mayor que cero.")

    numeros = [int(p.stem.split("_escena_")[-1]) for p in lista_imagenes]
    pesos = [_peso_palabras_escena(nombre_base, numero, idioma=idioma) for numero in numeros]
    huecos_transicion = DURACION_TRANSICION * (len(lista_imagenes) - 1)
    duracion_clips_total = duracion_voz + huecos_transicion
    suma_pesos = sum(pesos)
    duraciones = [duracion_clips_total * peso / suma_pesos for peso in pesos]

    promedio = sum(duraciones) / len(duraciones)
    resumen = ", ".join(f"{d:.1f}s" for d in duraciones)
    print(f"[{idioma.upper()}] Montando {len(lista_imagenes)} escenas con tiempos de narración ({resumen}; promedio {promedio:.1f}s)...")

    clips_animados = []
    for i, (img_path, duracion_clip) in enumerate(zip(lista_imagenes, duraciones)):
        clip_base = mp.ImageClip(str(img_path)).resize((VIDEO_WIDTH, VIDEO_HEIGHT)).set_duration(duracion_clip)
        zoom_in = i % 2 == 0

        def aplicar_ken_burns(get_frame, t, zoom_in=zoom_in, duracion_clip=duracion_clip):
            frame = get_frame(t)
            progreso = min(max(t / duracion_clip, 0.0), 1.0)
            escala = 1.0 + 0.05 * progreso if zoom_in else 1.05 - 0.05 * progreso
            ancho_recorte = max(1, min(VIDEO_WIDTH, round(VIDEO_WIDTH / escala)))
            alto_recorte = max(1, min(VIDEO_HEIGHT, round(VIDEO_HEIGHT / escala)))
            x1 = (frame.shape[1] - ancho_recorte) // 2
            y1 = (frame.shape[0] - alto_recorte) // 2
            recorte = frame[y1 : y1 + alto_recorte, x1 : x1 + ancho_recorte]
            imagen = Image.fromarray(recorte).resize((VIDEO_WIDTH, VIDEO_HEIGHT), resample=Image.Resampling.LANCZOS)
            return np.asarray(imagen)

        clip_animado = clip_base.fl(aplicar_ken_burns, apply_to=[])
        if i > 0:
            clip_animado = clip_animado.crossfadein(DURACION_TRANSICION)
        clips_animados.append(clip_animado)

    video_secuencia = mp.concatenate_videoclips(
        clips_animados, method="compose", padding=-DURACION_TRANSICION
    )

    # 1. Pista de narración en off
    audio_voz = mp.AudioFileClip(str(ruta_audio))

    # 2. Pista de música de fondo (loop ajustado a duracion_voz)
    ruta_musica = BASE_DIR / "assets" / "fondo_loop.mp3"
    clip_musica = None

    if ruta_musica.exists():
        clip_musica = (
            mp.AudioFileClip(str(ruta_musica))
            .fx(mp.afx.audio_loop, duration=duracion_voz)
            .volumex(0.12)
        )
        audio_final = mp.CompositeAudioClip([audio_voz, clip_musica])
    else:
        audio_final = audio_voz

    video_completo = video_secuencia.set_audio(audio_final).set_duration(duracion_voz)

    print(f"Renderizando video base [{idioma.upper()}] en: {ruta_video_salida}...")
    video_completo.write_videofile(
        str(ruta_video_salida),
        fps=30,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        threads=4,
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        logger=custom_logger,
        verbose=False,
    )

    # Liberación de descriptores
    audio_voz.close()
    if clip_musica is not None:
        clip_musica.close()
    audio_final.close()
    video_completo.close()
    video_secuencia.close()
    for clip in clips_animados:
        clip.close()

    print(f"✔ Video base [{idioma.upper()}] montado exitosamente en: {ruta_video_salida}")
    return ruta_video_salida