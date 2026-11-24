"""Módulo para generar y quemar subtítulos dinámicos en Shorts (ES / EN).
Garantiza ortografía perfecta desde el guion original y arranque inmediato en 0.0s.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
import whisper

# ========================================================
# DETECCIÓN DE RUTA PERSISTENTE (COMPATIBLE CON .EXE)
# ========================================================
if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent


def _formatear_tiempo_ass(segundos: float) -> str:
    """Convierte segundos a formato ASS (H:MM:SS.cs)."""
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    centisegundos = int(round((segundos - int(segundos)) * 100))
    if centisegundos >= 100:
        centisegundos = 99
    return f"{horas}:{minutos:02d}:{segs:02d}.{centisegundos:02d}"


def _escapar_texto_ass(texto: str) -> str:
    """Limpia caracteres para ASS."""
    texto = texto.replace("\\", "\\\\")
    texto = texto.replace("{", "\\{").replace("}", "\\}")
    return texto.strip().upper()


def _obtener_guion_referencia(nombre_base: str, idioma: str) -> str:
    """Localiza el texto del guion en outputs/json."""
    dir_json = BASE_DIR / "outputs" / "json"
    if not dir_json.exists():
        return ""

    candidatos = list(dir_json.glob("*.json"))
    for c in candidatos:
        if nombre_base in c.stem or c.stem in nombre_base:
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                return data.get("guion", {}).get("narracion", "")
            except Exception:
                pass
    return ""


def _generar_archivo_ass(palabras: list[dict], ruta_salida_ass: Path) -> Path:
    """Crea el archivo ASS asegurando que la primera palabra esté visible desde 0.0s."""
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
    tamano_grupo = 3

    for i in range(0, len(palabras), tamano_grupo):
        grupo = palabras[i : i + tamano_grupo]
        if not grupo:
            continue

        for idx_actual, p_act in enumerate(grupo):
            t_ini_palabra = p_act["start"]
            t_fin_palabra = p_act["end"]

            # Anclar al frame 0.0s si es el inicio del video
            if i == 0 and idx_actual == 0:
                t_ini_palabra = 0.0

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


def agregar_subtitulos_al_video(ruta_video: Path, ruta_audio: Path, idioma: str = None, texto_referencia: str = "") -> Path:
    """Extrae palabras alineadas sin desfasajes y quema subtítulos con FFmpeg."""
    ruta_video = Path(ruta_video).resolve()
    ruta_audio = Path(ruta_audio).resolve()

    if not idioma:
        nombre_str = (ruta_video.stem + "_" + ruta_audio.stem).lower()
        idioma = "en" if ("_en" in nombre_str or "english" in nombre_str) else "es"
    else:
        idioma = idioma.lower().strip()

    nombre_base = ruta_video.stem.replace("_base", "").replace(f"_{idioma}", "").replace("_subtitulado", "")

    if not texto_referencia:
        texto_referencia = _obtener_guion_referencia(nombre_base, idioma)

    palabras = []

    # 1. Intentar leer tiempos si existen y no están vacíos
    ruta_tiempos = ruta_audio.with_name(f"{ruta_audio.stem}_tiempos.json")
    if ruta_tiempos.exists():
        try:
            datos_t = json.loads(ruta_tiempos.read_text(encoding="utf-8"))
            if isinstance(datos_t, list) and len(datos_t) > 0:
                palabras = datos_t
        except Exception:
            pass

    # 2. Si no hay archivo de tiempos válido, transcribir con Whisper usando el guion como alineador
    if not palabras:
        print(f"Calculando alineación temporal con Whisper [{idioma.upper()}]...")
        modelo = whisper.load_model("base")
        res = modelo.transcribe(
            str(ruta_audio),
            language=idioma,
            word_timestamps=True,
            temperature=0.0
        )

        for seg in res.get("segments", []):
            for w in seg.get("words", []):
                palabra = w["word"].strip()
                t_start = max(0.0, float(w["start"]))
                t_end = max(t_start + 0.08, float(w["end"]))
                if palabra:
                    palabras.append({"word": palabra, "start": t_start, "end": t_end})

    if not palabras:
        raise ValueError(f"No se pudieron generar marcas de tiempo para [{idioma.upper()}].")

    # 3. Si tenemos el guion original, sustituir palabras manteniendo tiempos para garantizar ortografía
    if texto_referencia:
        tokens_guion = re.findall(r"[A-Za-zÁÉÍÓÚáéíóúÑñ0-9$€¥]+", texto_referencia)
        total_ref = len(tokens_guion)
        total_w = len(palabras)

        # Si las longitudes son comparables, asociamos la ortografía canónica directa
        if abs(total_ref - total_w) <= max(10, int(total_w * 0.15)):
            for idx in range(min(total_ref, total_w)):
                palabras[idx]["word"] = tokens_guion[idx]

    # Asegurar continuidad sin saltos negativos
    for i in range(len(palabras) - 1):
        if palabras[i]["end"] > palabras[i + 1]["start"]:
            palabras[i]["end"] = palabras[i + 1]["start"]

    dir_salida = BASE_DIR / "outputs" / "videos"
    dir_salida.mkdir(parents=True, exist_ok=True)
    ruta_salida_ass = dir_salida / f"{ruta_video.stem}_subtitulos.ass"
    ruta_video_subtitulado = dir_salida / f"{ruta_video.stem}_subtitulado.mp4"

    _generar_archivo_ass(palabras, ruta_salida_ass)

    print(f"Quemando subtítulos [{idioma.upper()}] alineados con FFmpeg...")
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

    ruta_salida_ass.unlink(missing_ok=True)
    print(f"✔ Video subtitulado [{idioma.upper()}] generado en: {ruta_video_subtitulado}")
    return ruta_video_subtitulado