"""
PIPELINE MAESTRO DE DOCUMENTALES LARGOS - LA CAJA NEGRA
Ejecuta todo el flujo de producción con 1 solo clic:
1. Guion con Hook y 36 escenas
2. TTS y renderizado de imágenes 16:9 en ComfyUI
3. Miniatura de alto impacto
4. Ensamblaje de video con Ken Burns suave y subtítulos
5. Generación de Metadata para YouTube (Título, Descripción, Timestamps, Tags)
"""
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

from longform_generator import generar_documental_completo
from longform_producer import ejecutar_produccion, _obtener_ultimo_expediente_json
from crear_miniatura import renderizar_miniatura_final
from longform_assembler import ensamblar_documental
from longform_metadata import generar_metadata_documental


def ejecutar_pipeline_completo():
    t_inicio = time.time()
    print("=" * 65)
    print(" 🚀 INICIANDO PIPELINE AUTOMÁTICO DE DOCUMENTAL LARGO (1-CLICK)")
    print("=" * 65)

    # 1. GENERACIÓN DE GUION
    print("\n>>> [PASO 1/5] GENERANDO GUION (36 ESCENAS + ABREBOCAS)...")
    generar_documental_completo()

    # Identificar la carpeta recién creada
    ultimo_json = _obtener_ultimo_expediente_json()
    slug = ultimo_json.stem
    carpeta_expediente = BASE_DIR / "outputs" / "produccion_largos" / slug

    # 2. PRODUCCIÓN DE AUDIO E IMÁGENES
    print("\n>>> [PASO 2/5] PRODUCIENDO AUDIO (EDGE TTS) E IMÁGENES (COMFYUI)...")
    ejecutar_produccion()

    # 3. MINIATURA
    print("\n>>> [PASO 3/5] COMPONIENDO MINIATURA FINAL CON TEXTO DE IMPACTO...")
    renderizar_miniatura_final(carpeta_expediente)

    # 4. MONTAJE DE VIDEO
    print("\n>>> [PASO 4/5] ENSAMBLANDO VIDEO MASTER (KEN BURNS + SUBTÍTULOS)...")
    ensamblar_documental(carpeta_expediente)

    # 5. METADATA DE YOUTUBE
    print("\n>>> [PASO 5/5] GENERANDO METADATA Y MARCAS DE TIEMPO...")
    generar_metadata_documental(carpeta_expediente)

    tiempo_total = (time.time() - t_inicio) / 60
    print("\n" + "=" * 65)
    print(f" 🎉 ¡EXPEDIENTE COMPLETADO EN {tiempo_total:.1f} MINUTOS!")
    print(f" 📂 Revisa tu material en: outputs/produccion_largos/{slug}/")
    print(f" 🎬 Video exportado en: outputs/videos/{slug}.mp4")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_pipeline_completo()