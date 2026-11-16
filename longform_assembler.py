"""
Módulo de ensamblado final para documentales largos (8-10 min) usando FFmpeg.
Aplica Ken Burns cinemático suave, mezcla de audio y subtítulos sincronizados escena por escena.
Canal: La Caja Negra
"""
import os
import sys
import json
import shutil
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# ========================================================
# RUTAS PERSISTENTES
# ========================================================
if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _obtener_ultimo_expediente() -> Path:
    directorio = BASE_DIR / "outputs" / "produccion_largos"
    carpetas = [d for d in directorio.iterdir() if d.is_dir()]
    if not carpetas:
        raise FileNotFoundError("No hay carpetas en outputs/produccion_largos")
    return max(carpetas, key=lambda d: d.stat().st_mtime)


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


def _formatear_tiempo_srt(segundos: float) -> str:
    horas = int(segundos // 3600)
    minutos = int((segundos % 3600) // 60)
    segs = int(segundos % 60)
    milis = int(round((segundos - int(segundos)) * 1000))
    return f"{horas:02d}:{minutos:02d}:{segs:02d},{milis:03d}"


def generar_subtitulos_sincronizados_por_escena(guion_estructurado: list, duraciones: list[float], ruta_salida_srt: Path):
    """
    Genera subtítulos dinámicos de 3 a 5 palabras calculando el tiempo 
    relativo dentro de cada escena individual para evitar desfases acumulados.
    """
    entradas_srt = []
    tiempo_acumulado = 0.0
    indice_srt = 1

    for idx, bloque in enumerate(guion_estructurado):
        dur_escena = duraciones[idx] if idx < len(duraciones) else (duraciones[-1] if duraciones else 15.0)
        palabras = bloque["texto"].split()
        if not palabras:
            tiempo_acumulado += dur_escena
            continue

        palabras_por_corte = 4
        segmentos = []
        for i in range(0, len(palabras), palabras_por_corte):
            segmentos.append(" ".join(palabras[i:i + palabras_por_corte]))

        tiempo_por_segmento = dur_escena / len(segmentos)

        for s_idx, seg in enumerate(segmentos):
            t_ini = tiempo_acumulado + (s_idx * tiempo_por_segmento)
            t_fin = tiempo_acumulado + ((s_idx + 1) * tiempo_por_segmento)

            entradas_srt.append(
                f"{indice_srt}\n"
                f"{_formatear_tiempo_srt(t_ini)} --> {_formatear_tiempo_srt(t_fin)}\n"
                f"{seg.upper()}\n"
            )
            indice_srt += 1

        tiempo_acumulado += dur_escena

    ruta_salida_srt.write_text("\n".join(entradas_srt) + "\n", encoding="utf-8")
    print(f"  • Subtítulos calibrados por escena: {len(entradas_srt)} cambios de frase generados.")


def _renderizar_clip_ken_burns(ruta_img: Path, duracion_seg: float, salida_clip: Path, indice: int):
    fps = 30
    total_frames = int(duracion_seg * fps)

    if indice % 2 == 0:
        filtro = (
            "scale=2560:1440:force_original_aspect_ratio=increase,"
            "crop=2560:1440,"
            f"zoompan=z='min(zoom+0.00008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps={fps}"
        )
    else:
        filtro = (
            "scale=2560:1440:force_original_aspect_ratio=increase,"
            "crop=2560:1440,"
            f"zoompan=z='if(lte(zoom,1.0),1.08,max(1.0,zoom-0.00008))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=1920x1080:fps={fps}"
        )

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(ruta_img),
        "-vf", filtro,
        "-t", f"{duracion_seg:.3f}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(salida_clip),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def ensamblar_documental(carpeta_expediente: Path):
    ruta_audio = carpeta_expediente / "locucion_completa.mp3"
    carpeta_imagenes = carpeta_expediente / "imagenes_16_9"
    fondo_musica = BASE_DIR / "assets" / "fondo_loop.mp3"

    dir_docs = BASE_DIR / "outputs" / "documentales_largos"
    archivo_json = dir_docs / f"{carpeta_expediente.name}.json"
    datos_doc = {}
    if archivo_json.exists():
        datos_doc = json.loads(archivo_json.read_text(encoding="utf-8"))

    if not ruta_audio.exists():
        raise FileNotFoundError(f"No existe el archivo de audio: {ruta_audio}")
    if not carpeta_imagenes.exists():
        raise FileNotFoundError(f"No existe la carpeta de imágenes: {carpeta_imagenes}")

    imagenes = sorted(
        list(carpeta_imagenes.glob("escena_*.jpg")),
        key=lambda f: int(f.stem.split("_")[-1]) if f.stem.split("_")[-1].isdigit() else 0,
    )
    if not imagenes:
        raise FileNotFoundError("No se encontraron imágenes en la carpeta.")

    duracion_total = _obtener_duracion_audio(ruta_audio)
    total_imagenes = len(imagenes)

    # 1. Cargar duraciones medidas exactamente en la producción de TTS
    ruta_tiempos = carpeta_expediente / "tiempos_sincronizados.json"
    if ruta_tiempos.exists():
        try:
            tiempos = json.loads(ruta_tiempos.read_text(encoding="utf-8"))
            print(f"  • Mapa de tiempos cargado: {len(tiempos)} duraciones individuales.")
        except Exception:
            tiempos = [duracion_total / total_imagenes] * total_imagenes
    else:
        tiempos = [duracion_total / total_imagenes] * total_imagenes

    print("====================================================")
    print(" 🎬 CAJANEGRA STUDIOS // ENSAMBLADOR DE VIDEO (16:9)")
    print(f" 📁 Expediente: {carpeta_expediente.name}")
    print(f" ⏱️ Duración audio: {duracion_total:.2f} s (~{duracion_total / 60:.2f} min)")
    print(f" 🖼️ Escenas procesadas: {total_imagenes}")
    print("====================================================")

    # 2. Generar subtítulos sincronizados por escena
    ruta_srt = carpeta_expediente / "subtitulos.srt"
    print("\n[1/3] 📝 Generando subtítulos con calibración exacta por escena...")
    guion = datos_doc.get("guion_estructurado", [])
    generar_subtitulos_sincronizados_por_escena(guion, tiempos, ruta_srt)

    # 3. Renderizar videoclips con Ken Burns suave
    carpeta_clips_temp = carpeta_expediente / "temp_clips"
    if carpeta_clips_temp.exists():
        shutil.rmtree(carpeta_clips_temp)
    carpeta_clips_temp.mkdir(parents=True, exist_ok=True)

    print(f"\n[2/3] 🎞️ Renderizando {total_imagenes} tomas panorámicas...")
    archivo_concat = carpeta_expediente / "clips_concat.txt"
    with open(archivo_concat, "w", encoding="utf-8") as f_concat:
        for idx, img in enumerate(imagenes, start=1):
            dur_clip = tiempos[idx - 1] if idx - 1 < len(tiempos) else tiempos[-1]
            clip_path = carpeta_clips_temp / f"clip_{idx}.mp4"

            print(f"  • Toma suave {idx}/{total_imagenes} ({dur_clip:.1f}s)...")
            _renderizar_clip_ken_burns(img, dur_clip, clip_path, idx)
            f_concat.write(f"file '{clip_path.as_posix()}'\n")

    # 4. Enlace final de video, subtítulos flotantes y audio
    dir_salida_videos = BASE_DIR / "outputs" / "videos"
    dir_salida_videos.mkdir(parents=True, exist_ok=True)
    video_final = dir_salida_videos / f"{carpeta_expediente.name}.mp4"

    srt_escaped = str(ruta_srt).replace("\\", "/").replace(":", "\\:")

    filtro_subtitulos = (
        f"subtitles='{srt_escaped}':force_style='Fontname=Impact,Fontsize=18,Bold=1,"
        f"PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,"
        f"Shadow=1,Alignment=2,MarginV=42'"
    )

    print("\n[3/3] 🚀 Ensamblando master final en alta definición...")

    comando = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(archivo_concat),
        "-i", str(ruta_audio),
    ]

    if fondo_musica.exists():
        comando.extend([
            "-stream_loop", "-1", "-i", str(fondo_musica),
            "-filter_complex",
            f"[0:v]{filtro_subtitulos}[v];[2:a]volume=0.08[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "[v]",
            "-map", "[a]",
        ])
    else:
        comando.extend([
            "-vf", filtro_subtitulos,
            "-map", "0:v",
            "-map", "1:a",
        ])

    comando.extend([
        "-c:v", "libx264",
        "-preset", "faster",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(video_final),
    ])

    try:
        subprocess.run(comando, check=True)
        print(f"\n✔ Video exportado con éxito en:\n📁 {video_final}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error durante el ensamblado: {e}")
    finally:
        if archivo_concat.exists():
            archivo_concat.unlink(missing_ok=True)


if __name__ == "__main__":
    carpeta = _obtener_ultimo_expediente()
    ensamblar_documental(carpeta)