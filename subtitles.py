"""Módulo para transcribir voz y quemar subtítulos dinámicos con Whisper y FFmpeg de forma silenciosa."""

import os
import re
import subprocess
import sys
from pathlib import Path
import whisper

# ========================================================
# DETECCIÓN DE RUTA PERSISTENTE (COMPATIBLE CON .EXE)
# ========================================================
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent


def _formatear_tiempo_ass(segundos: float) -> str:
    """Convierte segundos a formato de tiempo ASS (H:MM:SS.cs)."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    centisegundos = int(round((segundos - int(segundos)) * 100))
    if centisegundos >= 100:
        centisegundos = 99
    return f"{horas}:{minutos:02d}:{segs:02d}.{centisegundos:02d}"


def _escapar_texto_ass(texto: str) -> str:
    """Limpia caracteres problemáticos para formato ASS."""
    texto = texto.replace("\\", "\\\\")
    texto = texto.replace("{", "\\{").replace("}", "\\}")
    return texto.strip().upper()


def _generar_archivo_ass(palabras_alineadas: list[dict], ruta_salida_ass: Path) -> Path:
    """Genera archivo de subtítulos estilo Short vertical dinámico."""
    encabezado_ass = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,74,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,6,3,2,60,60,650,1
Style: Highlight,Arial Black,80,&H0000FFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,105,105,2,0,1,7,4,2,60,60,650,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    eventos = []
    # Agrupar de 2 a 3 palabras por pantalla para formato Shorts rápido
    tamano_grupo = 3
    for i in range(0, len(palabras_alineadas), tamano_grupo):
        grupo = palabras_alineadas[i : i + tamano_grupo]
        if not grupo:
            continue

        t_inicio_grupo = grupo[0]["start"]
        t_fin_grupo = grupo[-1]["end"]

        # Mostrar cada palabra destacada secuencialmente
        for idx_actual, p_act in enumerate(grupo):
            t_ini_palabra = p_act["start"]
            t_fin_palabra = p_act["end"]

            partes = []
            for idx_otra, p_otra in enumerate(grupo):
                txt = _escapar_texto_ass(p_otra["word"])
                if idx_otra == idx_actual:
                    partes.append(f"{{\\rHighlight}}{txt}{{\\rDefault}}")
                else:
                    partes.append(txt)

            linea_dialogo = " ".join(partes)
            str_ini = _formatear_tiempo_ass(t_ini_palabra)
            str_fin = _formatear_tiempo_ass(t_fin_palabra)
            eventos.append(f"Dialogue: 0,{str_ini},{str_fin},Default,,0,0,0,,{linea_dialogo}")

    contenido_final = encabezado_ass + "\n".join(eventos) + "\n"
    ruta_salida_ass.write_text(contenido_final, encoding="utf-8")
    return ruta_salida_ass


def agregar_subtitulos_al_video(ruta_video: Path, ruta_audio: Path) -> Path:
    """Extrae palabras con Whisper y las quema en el video con FFmpeg de forma silenciosa."""
    ruta_video = Path(ruta_video).resolve()
    ruta_audio = Path(ruta_audio).resolve()

    print("Transcribiendo audio con Whisper (modelo base)...")
    modelo = whisper.load_model("base")
    resultado = modelo.transcribe(str(ruta_audio), language="es", word_timestamps=True)

    palabras = []
    for segmento in resultado.get("segments", []):
        for w in segmento.get("words", []):
            palabras.append({
                "word": w["word"].strip(),
                "start": max(0.0, float(w["start"])),
                "end": max(0.0, float(w["end"])),
            })

    if not palabras:
        raise ValueError("Whisper no detectó palabras en el audio.")

    dir_salida = BASE_DIR / "outputs" / "videos"
    dir_salida.mkdir(parents=True, exist_ok=True)
    nombre_base = ruta_video.stem.replace("_base", "")
    ruta_salida_ass = dir_salida / f"{nombre_base}_subtitulos.ass"
    ruta_video_subtitulado = dir_salida / f"{nombre_base}_subtitulado.mp4"

    _generar_archivo_ass(palabras, ruta_salida_ass)

    print("Quemando subtítulos alineados con FFmpeg...")

    # Rutas escapadas para el filtro ass en Windows
    ruta_ass_escapada = str(ruta_salida_ass).replace("\\", "/").replace(":", "\\:")
    filtro_vf = f"ass='{ruta_ass_escapada}'"

    comando = [
        "ffmpeg",
        "-y",
        "-i", str(ruta_video),
        "-vf", filtro_vf,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "18",
        "-c:a", "copy",
        str(ruta_video_subtitulado)
    ]

    # ========================================================
    # SUPRESIÓN TOTAL DE VENTANA DE CONSOLA NEGRA EN WINDOWS
    # ========================================================
    startupinfo = None
    creationflags = 0
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE
        creationflags = subprocess.CREATE_NO_WINDOW

    proceso = subprocess.run(
        comando,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        startupinfo=startupinfo,
        creationflags=creationflags
    )

    if proceso.returncode != 0:
        raise RuntimeError(f"Error de FFmpeg al quemar subtítulos:\n{proceso.stderr}")

    # Limpiar archivo temporal .ass
    ruta_salida_ass.unlink(missing_ok=True)
    return ruta_video_subtitulado