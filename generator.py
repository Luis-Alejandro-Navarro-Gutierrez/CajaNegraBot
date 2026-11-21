"""Módulo para generar y traducir guiones estructurados con Groq (ES / EN).
Optimizado para openai/gpt-oss-120b con reasoning controlado para evitar respuestas vacías.
Calibrado para videos verticales de 1:10 a 1:20 min y variedad cinematográfica en cómic moderno.
Canal: La Caja Negra / The Black Box Archives.
"""

import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

MODELO_ACTIVO = "openai/gpt-oss-120b"

CIERRE_VIDEO_ES = "Dale Like y suscribete para mas contenido"
CIERRE_VIDEO_EN = "Like and subscribe for more documented truths"


def _asegurar_cierre_video(narracion: str, idioma: str = "es") -> str:
    """Garantiza que la narración termine con el CTA oficial según el idioma."""
    cierre = CIERRE_VIDEO_EN if idioma == "en" else CIERRE_VIDEO_ES
    patron = (
        r"[\s.!?…,:;—-]*like\s+and\s+subscribe[^\n]*$"
        if idioma == "en"
        else r"[\s.!?…,:;—-]*dale\s+like\s+y\s+suscr[ií]bete[^\n]*$"
    )
    narracion = re.sub(patron, "", narracion.strip(), flags=re.IGNORECASE).rstrip(" .!?…,:;—-")
    if not narracion:
        return cierre
    return f"{narracion}. {cierre}"


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("API Key de Groq no configurada en .env.")
    return Groq(api_key=api_key)


def _limpiar_y_parsear_json(texto: str) -> dict:
    """Extrae y decodifica el bloque JSON válido del texto generado por el LLM."""
    texto_limpio = texto.strip()
    if "```json" in texto_limpio:
        partes = texto_limpio.split("```json")
        texto_limpio = partes[1].split("```")[0].strip()
    elif "```" in texto_limpio:
        partes = texto_limpio.split("```")
        texto_limpio = partes[1].split("```")[0].strip()

    match = re.search(r"(\{.*\})", texto_limpio, re.DOTALL)
    if match:
        texto_limpio = match.group(1)

    return json.loads(texto_limpio)


def generar_guion(tema: str, minimo: int = 180, maximo: int = 205) -> dict:
    """Genera un guion entretenido, con malicia, directo y sin tecnicismos pesados.
    Calibrado a 180-205 palabras para lograr entre 1:10 y 1:20 minutos de locución real."""
    client = _get_groq_client()

    prompt = f"""
    Escribe un guion en español para un video vertical sobre este caso real: "{tema}".
    
    TONO Y ESTILO:
    - Habla como si le estuvieras contando a un amigo en una cafetería el chisme, crimen, robo o accidente más ridículo e insólito que jamás ha escuchado.
    - CERO lenguaje poético, CERO metáforas abstractas ("elegancia de un pulpo", "piscina de confeti", "destino implacable").
    - CERO tecnicismos aburridos y cero explicaciones académicas secas. Usa palabras directas, cotidianas y con ritmo rápido.
    - Cuenta HECHOS REALES de forma cronológica: quién lo hizo, qué plan maestro tenían, y cuál fue la metida de pata exacta que arruinó todo.
    
    REGLAS ESTRICTAS DE DURACIÓN:
    1. Longitud de narración: EXACTAMENTE entre {minimo} y {maximo} palabras totales. Esto es vital para que la locución dure entre 1:10 y 1:20 minutos. No entregues menos de {minimo} palabras.
    2. Comienza DIRECTO con un gancho frontal "¿Sabías que...?" exponiendo el dato verídico más disparatado del caso desde la primera línea.
    3. PROHIBIDO usar frases meta como "el giro llegó", "la sorpresa fue", "el clímax" o "la moraleja". El desenlace insólito debe entenderse solo por los hechos.
    4. Cierre obligatorio como última frase de la narración: "{CIERRE_VIDEO_ES}".
    5. Cero anotaciones de cámara, corchetes o efectos de sonido; entrega solo el texto limpio para locución.
    6. Asegúrate de cerrar la estructura JSON completamente.

    Responde ÚNICAMENTE un JSON válido con este formato:
    {{"guion": {{"titulo": "Título corto y con gancho irresistible", "narracion": "Texto completo de la locución"}}}}
    """

    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres el creador de historias virales para 'La Caja Negra'. Cuentas historias reales sobre robos insólitos, "
                "hackeos, crímenes absurdos y accidentes históricos con un tono dinámico, entretenido, irónico y directo al grano. "
                "Respondes únicamente con un objeto JSON válido y estrictamente cerrado."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        completion = client.chat.completions.create(
            model=MODELO_ACTIVO,
            messages=mensajes,
            temperature=0.6,
            max_completion_tokens=2048,
            extra_body={"reasoning_effort": "low"},
        )
        guion_json = _limpiar_y_parsear_json(completion.choices[0].message.content)
        guion_json["guion"]["narracion"] = _asegurar_cierre_video(guion_json["guion"]["narracion"], idioma="es")
        return guion_json
    except Exception as e:
        raise RuntimeError(f"Error generando guion ES con {MODELO_ACTIVO}: {e}")


def traducir_guion_a_ingles(guion_es: dict) -> dict:
    """Adapta el guion al inglés manteniendo el ritmo dinámico, los hechos concretos y la misma duración."""
    client = _get_groq_client()
    datos = guion_es["guion"]

    prompt = f"""
    Translate and adapt this Spanish script for 'The Black Box Archives' vertical video.
    Keep the same fast-paced, ironic, shocking, and casual storytelling tone (like sharing wild true events with friends).
    NO poetic metaphors, NO dry academic jargon, NO fictional filler. Stick to the actual facts and the ridiculous human error.
    
    Source Title: {datos['titulo']}
    Source Script: {datos['narracion']}
    
    Rules:
    1. Hook MUST start with "Did you know that...?"
    2. Maintain exact chronological progression, absurd real facts, and a word count of 175 to 200 words (matching 1:10 to 1:20 duration).
    3. NO meta-narrative announcements like "the twist came", "the funny part was", or "in conclusion".
    4. Mandatory final sentence: "{CIERRE_VIDEO_EN}".
    5. Ensure the JSON structure is strictly complete and closed.

    Return ONLY valid JSON:
    {{"guion": {{"titulo": "Punchy Viral English Title", "narracion": "Narration text"}}}}
    """

    mensajes = [
        {
            "role": "system",
            "content": (
                "You write viral, engaging true-story scripts for 'The Black Box Archives'. "
                "Tell absurd, crazy true crime, heist, and hacking stories casually without stiff academic jargon. "
                "Output strict, complete, and properly closed JSON only."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        completion = client.chat.completions.create(
            model=MODELO_ACTIVO,
            messages=mensajes,
            temperature=0.4,
            max_completion_tokens=2048,
            extra_body={"reasoning_effort": "low"},
        )
        guion_en = _limpiar_y_parsear_json(completion.choices[0].message.content)
        guion_en["guion"]["narracion"] = _asegurar_cierre_video(guion_en["guion"]["narracion"], idioma="en")
        return guion_en
    except Exception as e:
        raise RuntimeError(f"Error traduciendo guion EN con {MODELO_ACTIVO}: {e}")


def guardar_guion(guion_data: dict, sufijo: str = "", nombre_base_fijo: str = "") -> Path:
    """Guarda el JSON del guion en outputs/json/ vinculando el nombre base para sincronización y limpieza."""
    output_dir = BASE_DIR / "outputs" / "json"
    output_dir.mkdir(parents=True, exist_ok=True)

    if nombre_base_fijo:
        nombre_base = nombre_base_fijo
    else:
        titulo = guion_data["guion"]["titulo"]
        nombre_base = "".join(c if c.isalnum() else "_" for c in titulo).lower()
        nombre_base = "_".join(filter(None, nombre_base.split("_")))[:40]

    nombre_archivo = f"{nombre_base}{sufijo}.json" if sufijo else f"{nombre_base}.json"
    ruta_archivo = output_dir / nombre_archivo
    ruta_archivo.write_text(json.dumps(guion_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Guion guardado en: {ruta_archivo}")
    return ruta_archivo