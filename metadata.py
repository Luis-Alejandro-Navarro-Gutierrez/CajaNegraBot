"""Módulo para generar el archivo de texto con títulos, descripciones y hashtags listos para redes (ES / EN).
Optimizado para nichos amplios de '¿Sabías que...?': explicaciones cotidianas, ciencia, historia, animales y misterios.
"""

import re
import os
import sys
from pathlib import Path

if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent


def _obtener_hashtags_tematicos_es(tema: str, titulo: str) -> list[str]:
    """Genera hashtags en español específicos acordes al nicho del video."""
    texto = f"{tema} {titulo}".lower()
    hashtags = ["#Curiosidades", "#DatosCuriosos", "#Shorts"]

    # 1. Curiosidades cotidianas y explicaciones del porqué
    if any(k in texto for k in ["por qué", "color", "hielo", "ojo", "cielo", "bostezo", "mezcla", "luz", "sombra", "espejo", "dormir", "cuerpo humano", "hipo"]):
        hashtags.extend(["#SabiasQue", "#AprendeEnTikTok", "#CienciaCotidiana"])
    # 2. Animales y naturaleza
    elif any(k in texto for k in ["animal", "perro", "oso", "gato", "pájaro", "especie", "plaga", "naturaleza", "biología", "marino", "selva"]):
        hashtags.extend(["#AnimalesFascinantes", "#MundoAnimal", "#Biologia"])
    # 3. Ciencia, medicina e inventos accidentales
    elif any(k in texto for k in ["invento", "accidental", "medicina", "laboratorio", "física", "química", "átomo", "experimento", "ciencia", "cura"]):
        hashtags.extend(["#Ciencia", "#Inventos", "#HistoriaCientifica"])
    # 4. Guerras, reyes, leyes y disputas absurdas
    elif any(k in texto for k in ["guerra", "batalla", "rey", "emperador", "ley", "tratado", "ejército", "militar", "conflicto", "disputa", "imperio"]):
        hashtags.extend(["#HistoriaReal", "#GuerrasAbsurdas", "#Historia"])
    # 5. Falsantes, impostores y engaños de alta sociedad
    elif any(k in texto for k in ["impostor", "farsante", "falso", "noble", "engaño", "arte", "museo", "estafador", "falsificación"]):
        hashtags.extend(["#GrandesEngaños", "#Impostores", "#HistoriasReales"])
    # 6. Enigmas, barcos fantasma e ingeniería
    elif any(k in texto for k in ["barco fantasma", "naufragio", "avión", "desaparición", "torre", "puente", "ingeniería", "enigma", "misterio"]):
        hashtags.extend(["#Enigmas", "#MisteriosReales", "#Ingenieria"])
    # 7. Hackeos, ciberseguridad y tecnología del siglo XXI
    elif any(k in texto for k in ["hacker", "computadora", "virus", "código", "software", "internet", "cripto", "bitcoin", "gps", "celular", "wifi", "ia"]):
        hashtags.extend(["#Ciberseguridad", "#Tecnologia", "#SigloXXI"])
    # 8. Robos, golpes y crímenes insólitos
    elif any(k in texto for k in ["robo", "bóveda", "fuga", "alcatraz", "atraco", "estafa", "banco", "joyería", "ladrón", "policía", "crimen"]):
        hashtags.extend(["#Atracos", "#CrimenReal"])
    else:
        hashtags.extend(["#SabiasQue", "#Historia", "#LaCajaNegra"])

    return hashtags


def _obtener_hashtags_tematicos_en(tema: str, titulo: str) -> list[str]:
    """Genera hashtags en inglés de alto volumen para audiencia anglosajona."""
    texto = f"{tema} {titulo}".lower()
    hashtags = ["#Shorts", "#DidYouKnow", "#Curiosity"]

    # 1. Everyday curiosities & 'Why' explanations
    if any(k in texto for k in ["why", "color", "ice", "eye", "sky", "yawn", "mix", "light", "shadow", "mirror", "sleep", "body", "hiccup"]):
        hashtags.extend(["#LearnOnTikTok", "#DailyScience", "#HowItWorks"])
    # 2. Animals and nature
    elif any(k in texto for k in ["animal", "dog", "bear", "cat", "bird", "species", "nature", "biology", "ocean", "wildlife", "creature"]):
        hashtags.extend(["#AnimalFacts", "#WildLife", "#Nature"])
    # 3. Science, medicine and accidental discoveries
    elif any(k in texto for k in ["invent", "accident", "medicine", "lab", "physics", "chemistry", "atom", "experiment", "science", "cure"]):
        hashtags.extend(["#Science", "#Discoveries", "#HistoryOfScience"])
    # 4. Wars, kings, laws and bizarre conflicts
    elif any(k in texto for k in ["war", "battle", "king", "emperor", "law", "treaty", "army", "military", "conflict", "dispute", "empire"]):
        hashtags.extend(["#HistoryFacts", "#BizarreHistory", "#History"])
    # 5. Impostors, fake nobles and art hoaxes
    elif any(k in texto for k in ["impostor", "fake", "con artist", "noble", "hoax", "art", "museum", "scam", "forgery"]):
        hashtags.extend(["#TrueScams", "#Impostors", "#RealStories"])
    # 6. Enigmas, ghost ships and engineering fails
    elif any(k in texto for k in ["ghost ship", "shipwreck", "plane", "disappearance", "tower", "bridge", "engineering", "enigma", "mystery"]):
        hashtags.extend(["#Enigmas", "#RealMysteries", "#Engineering"])
    # 7. Hacking, cybersecurity and modern tech
    elif any(k in texto for k in ["hacker", "cyber", "virus", "code", "software", "internet", "crypto", "bitcoin", "gps", "phone", "wifi", "ai"]):
        hashtags.extend(["#CyberSecurity", "#Technology", "#TechFacts"])
    # 8. Heists and botched crimes
    elif any(k in texto for k in ["heist", "vault", "escape", "alcatraz", "robbery", "scam", "bank", "jewelry", "thief", "crime"]):
        hashtags.extend(["#Heist", "#TrueCrime"])
    else:
        hashtags.extend(["#Documentary", "#History", "#TheBlackBox"])

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


def _generar_frase_descripcion(tema: str, idioma: str = "es") -> str:
    """Adapta la primera línea de la descripción para que suene natural tanto si es pregunta como si es hecho."""
    tema_limpio = tema.strip().rstrip(".!?")
    if idioma == "en":
        if re.match(r"^(why|how|what|did you know)\b", tema_limpio, flags=re.IGNORECASE):
            return f"Uncover the real facts behind: {tema_limpio}."
        return f"Did you know that {tema_limpio}? Uncover the documented truth behind this fascinating real event."
    else:
        if re.match(r"^(por qué|cómo|qué|sabías que)\b", tema_limpio, flags=re.IGNORECASE):
            return f"Descubre la explicación y los datos reales detrás de: {tema_limpio}."
        return f"¿Sabías que {tema_limpio}? Descubre la historia y los hechos reales explicados de forma breve y clara."


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
        hashtags_desc_set = set(hashtags_lista + ["#DidYouKnow", "#ViralShorts", "#TrueStory", "#TheBlackBox"])
        hashtags_descripcion = " ".join(sorted(hashtags_desc_set))

        frase_inicio = _generar_frase_descripcion(tema, idioma="en")
        descripcion_cuerpo = (
            f"{frase_inicio}\n\n"
            "Subscribe to The Black Box Archives and hit the bell for daily curiosity and history stories.\n\n"
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

        frase_inicio = _generar_frase_descripcion(tema, idioma="es")
        descripcion_cuerpo = (
            f"{frase_inicio}\n\n"
            "Suscríbete a La Caja Negra y activa las notificaciones para no perderte ninguna curiosidad explicada.\n\n"
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