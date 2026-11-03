"""Módulo para generar el archivo de texto con títulos, descripciones y hashtags listos para copiar y pegar."""

import re
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent


def _obtener_hashtags_tematicos(tema: str, titulo: str) -> list[str]:
    """Genera hashtags específicos acordes al nicho del video."""
    texto_combinado = f"{tema} {titulo}".lower()

    hashtags = ["#Curiosidades", "#DatosCuriosos", "#Shorts"]

    # Diccionario de palabras clave por temática
    if any(k in texto_combinado for k in ["guerra", "batalla", "soldado", "militar", "urss", "ejército", "armas"]):
        hashtags.extend(["#HistoriaMilitar", "#Historia"])
    elif any(k in texto_combinado for k in ["hacker", "computadora", "virus", "código", "software", "bug", "internet"]):
        hashtags.extend(["#Tecnologia", "#Informatica"])
    elif any(k in texto_combinado for k in ["animal", "tiburon", "ave", "emu", "perro", "especie", "naturaleza"]):
        hashtags.extend(["#Naturaleza", "#Animales"])
    elif any(k in texto_combinado for k in ["espacio", "planeta", "astronauta", "nasa", "galaxia", "orbita"]):
        hashtags.extend(["#Espacio", "#Ciencia"])
    elif any(k in texto_combinado for k in ["accidente", "misterio", "secreto", "experimento", "radiactivo"]):
        hashtags.extend(["#Misterios", "#Ciencia"])
    else:
        hashtags.extend(["#Historia", "#AprendeEnTikTok"])

    return hashtags


def _construir_titulo_con_hashtags(titulo: str, hashtags: list[str], max_len: int = 100) -> str:
    """Combina el título con los hashtags más relevantes sin superar el límite de 100 caracteres de YouTube."""
    titulo_limpio = titulo.strip().rstrip(".!?")
    candidato = titulo_limpio

    # Probar añadir hashtags uno a uno respetando el límite de 100 caracteres
    for tag in hashtags:
        prueba = f"{candidato} {tag}"
        if len(prueba) <= max_len:
            candidato = prueba
        else:
            break

    return candidato


def generar_archivo_metadata(titulo: str, tema: str, nombre_base: str) -> Path:
    """Crea un archivo .txt en outputs/ con el título, descripción y hashtags listos para redes sociales."""
    output_dir = BASE_DIR / "outputs" / "metadata"
    output_dir.mkdir(parents=True, exist_ok=True)

    ruta_salida = output_dir / f"{nombre_base}_para_publicar.txt"

    # Obtener etiquetas dinámicas
    hashtags_lista = _obtener_hashtags_tematicos(tema, titulo)
    titulo_con_hashtags = _construir_titulo_con_hashtags(titulo, hashtags_lista, max_len=100)

    # Bloque de hashtags ampliado para la descripción
    hashtags_descripcion_set = set(hashtags_lista + ["#SabiasQue", "#AprendeAlgo", "#Reels", "#FYP", "#ParaTi"])
    hashtags_descripcion = " ".join(sorted(hashtags_descripcion_set))

    contenido_txt = f"""==================================================
  📱 METADATOS PARA PUBLICAR TU SHORT / REEL / TIKTOK
==================================================

📋 COPIAR Y PEGAR RÁPIDO (TÍTULO PARA YOUTUBE SHORTS):
{titulo_con_hashtags}

--------------------------------------------------

📌 TÍTULO ORIGINAL (SIN HASHTAGS):
{titulo}

--------------------------------------------------

📝 DESCRIPCIÓN COMPLETA:
¿Sabías que {tema}? Descubre la historia real detrás de este hecho fascinante explicado de forma breve y clara.

{hashtags_descripcion}

--------------------------------------------------

🏷️ HASHTAGS INDIVIDUALES RECOMENDADOS:
{" ".join(hashtags_lista)}

--------------------------------------------------
🎯 TEMA ORIGINAL:
{tema}
==================================================
"""

    ruta_salida.write_text(contenido_txt, encoding="utf-8")
    print(f"📄 Metadatos para redes listos en: {ruta_salida}")
    return ruta_salida