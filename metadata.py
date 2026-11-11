"""Módulo para generar el archivo de texto con títulos, descripciones y hashtags listos para redes (ES / EN)."""

import re
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent


def _obtener_hashtags_tematicos_es(tema: str, titulo: str) -> list[str]:
    """Genera hashtags en español específicos acordes al nicho del video."""
    texto = f"{tema} {titulo}".lower()
    hashtags = ["#Curiosidades", "#DatosCuriosos", "#Shorts"]

    if any(k in texto for k in ["hacker", "computadora", "virus", "código", "software", "stuxnet", "internet"]):
        hashtags.extend(["#Ciberseguridad", "#Tecnologia"])
    elif any(k in texto for k in ["robo", "bóveda", "fuga", "alcatraz", "atraco", "estafa", "diamantes"]):
        hashtags.extend(["#Atracos", "#CrimenReal"])
    elif any(k in texto for k in ["asesinato", "crimen", "policía", "forense", "misterio"]):
        hashtags.extend(["#CrimenReal", "#Misterios"])
    elif any(k in texto for k in ["accidente", "caja negra", "avión", "desastre", "naufragio", "chernóbil"]):
        hashtags.extend(["#Desastres", "#HistoriaReal"])
    elif any(k in texto for k in ["parásito", "zombi", "hongo", "animal", "naturaleza", "biología"]):
        hashtags.extend(["#Naturaleza", "#Biologia"])
    elif any(k in texto for k in ["espacio", "física", "paradoja", "ciencia", "demon core", "átomo"]):
        hashtags.extend(["#Ciencia", "#Fisica"])
    elif any(k in texto for k in ["supervivencia", "naufragio", "avión", "selva", "desierto"]):
        hashtags.extend(["#Supervivencia", "#Historia"])
    else:
        hashtags.extend(["#Historia", "#LaCajaNegra"])

    return hashtags


def _obtener_hashtags_tematicos_en(tema: str, titulo: str) -> list[str]:
    """Genera hashtags en inglés de alto volumen para audiencia anglosajona."""
    texto = f"{tema} {titulo}".lower()
    hashtags = ["#Shorts", "#DidYouKnow", "#History"]

    if any(k in texto for k in ["hacker", "cyber", "virus", "code", "software", "stuxnet", "bug"]):
        hashtags.extend(["#CyberSecurity", "#Technology"])
    elif any(k in texto for k in ["heist", "vault", "escape", "alcatraz", "robbery", "scam"]):
        hashtags.extend(["#Heist", "#TrueCrime"])
    elif any(k in texto for k in ["murder", "crime", "forensic", "mystery", "killer"]):
        hashtags.extend(["#TrueCrime", "#Mysteries"])
    elif any(k in texto for k in ["crash", "black box", "disaster", "plane", "chernobyl", "shipwreck"]):
        hashtags.extend(["#Disasters", "#TrueStory"])
    elif any(k in texto for k in ["parasite", "zombie", "fungus", "creature", "nature", "biology"]):
        hashtags.extend(["#WildLife", "#Nature"])
    elif any(k in texto for k in ["space", "physics", "paradox", "science", "demon core", "quantum"]):
        hashtags.extend(["#Science", "#Physics"])
    elif any(k in texto for k in ["survival", "lost", "ocean", "jungle", "desert"]):
        hashtags.extend(["#Survival", "#TrueStory"])
    else:
        hashtags.extend(["#Documentary", "#TheBlackBox"])

    return hashtags


def _construir_titulo_con_hashtags(titulo: str, hashtags: list[str], max_len: int = 100) -> str:
    """Combina el título con los hashtags más relevantes sin superar el límite de 100 caracteres."""
    titulo_limpio = titulo.strip().rstrip(".!?")
    candidato = titulo_limpio

    for tag in hashtags:
        prueba = f"{candidato} {tag}"
        if len(prueba) <= max_len:
            candidato = prueba
        else:
            break

    return candidato


def generar_archivo_metadata(titulo: str, tema: str, nombre_base: str, idioma: str = "es") -> Path:
    """
    Crea un archivo .txt en outputs/metadata/ con títulos, descripciones y hashtags.
    :param idioma: 'es' para La Caja Negra o 'en' para The Black Box Archives.
    """
    output_dir = BASE_DIR / "outputs" / "metadata"
    output_dir.mkdir(parents=True, exist_ok=True)

    idioma = idioma.lower().strip()
    sufijo_archivo = f"_{idioma}" if not nombre_base.endswith(f"_{idioma}") else ""
    ruta_salida = output_dir / f"{nombre_base}{sufijo_archivo}_para_publicar.txt"

    if idioma == "en":
        hashtags_lista = _obtener_hashtags_tematicos_en(tema, titulo)
        titulo_con_hashtags = _construir_titulo_con_hashtags(titulo, hashtags_lista, max_len=100)
        hashtags_desc_set = set(hashtags_lista + ["#Declassified", "#ViralShorts", "#TrueStory", "#TheBlackBox"])
        hashtags_descripcion = " ".join(sorted(hashtags_desc_set))

        descripcion_cuerpo = (
            f"Did you know that {tema}? Uncover the documented truth behind this unbelievable real-world event.\n\n"
            "Subscribe to The Black Box Archives and hit the bell for daily declassified stories.\n\n"
            f"{hashtags_descripcion}"
        )
        encabezado = "METADATA FOR YOUTUBE SHORTS (THE BLACK BOX ARCHIVES // EN)"
        txt_rapido = "QUICK COPY-PASTE (YOUTUBE SHORTS TITLE):"
        txt_orig = "ORIGINAL TITLE (WITHOUT HASHTAGS):"
        txt_desc = "FULL DESCRIPTION:"
        txt_tags = "RECOMMENDED TAGS:"
        txt_tema = "ORIGINAL TOPIC:"
    else:
        hashtags_lista = _obtener_hashtags_tematicos_es(tema, titulo)
        titulo_con_hashtags = _construir_titulo_con_hashtags(titulo, hashtags_lista, max_len=100)
        hashtags_desc_set = set(hashtags_lista + ["#SabiasQue", "#AprendeAlgo", "#Reels", "#ParaTi", "#LaCajaNegra"])
        hashtags_descripcion = " ".join(sorted(hashtags_desc_set))

        descripcion_cuerpo = (
            f"¿Sabías que {tema}? Descubre la historia real detrás de este hecho fascinante explicado de forma breve y clara.\n\n"
            "Suscríbete a La Caja Negra y activa las notificaciones para no perderte ninguna verdad desclasificada.\n\n"
            f"{hashtags_descripcion}"
        )
        encabezado = "METADATOS PARA YOUTUBE SHORTS (LA CAJA NEGRA // ES)"
        txt_rapido = "COPIAR Y PEGAR RÁPIDO (TÍTULO PARA YOUTUBE SHORTS):"
        txt_orig = "TÍTULO ORIGINAL (SIN HASHTAGS):"
        txt_desc = "DESCRIPCIÓN COMPLETA:"
        txt_tags = "HASHTAGS INDIVIDUALES RECOMENDADOS:"
        txt_tema = "TEMA ORIGINAL:"

    contenido_txt = f"""==================================================
  📱 {encabezado}
==================================================

📋 {txt_rapido}
{titulo_con_hashtags}

--------------------------------------------------

📌 {txt_orig}
{titulo}

--------------------------------------------------

📝 {txt_desc}
{descripcion_cuerpo}

--------------------------------------------------

🏷️ {txt_tags}
{" ".join(hashtags_lista)}

--------------------------------------------------
🎯 {txt_tema}
{tema}
==================================================
"""

    ruta_salida.write_text(contenido_txt, encoding="utf-8")
    print(f"📄 Metadatos [{idioma.upper()}] listos en: {ruta_salida}")
    return ruta_salida