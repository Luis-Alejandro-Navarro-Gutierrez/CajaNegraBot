"""Módulo para generar y traducir guiones estructurados con Groq (ES / EN)."""

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
    # Si está dentro de dist (o subcarpeta de dist), sube hasta la raíz
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

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


def generar_guion(tema: str, minimo: int = 180, maximo: int = 200) -> dict:
    """Genera un guion documental estructurado en español con Groq."""
    client = _get_groq_client()

    prompt = f"""
    Escribe un guion en español tipo "¿Sabías que...?" para Shorts sobre: "{tema}".
    Enfoque: misterio documental, hechos reales, tensión y giros asombrosos sin tecnicismos densos.
    
    Reglas:
    1. Duración: {minimo}-{maximo} palabras totales.
    2. Comienza directo con un gancho "¿Sabías que...?".
    3. Retención: Gancho impactante, nudo con anomalía, giro revelador y resolución.
    4. Cierre obligatorio como última frase: "{CIERRE_VIDEO_ES}".
    5. Cero anotaciones técnicas; solo texto para locución.

    Responde ÚNICAMENTE un JSON válido:
    {{"guion": {{"titulo": "Título intrigante", "narracion": "Texto completo"}}}}
    """

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "Eres guionista documental de videos virales de alta retención. Devuelve solo JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.45,
            response_format={"type": "json_object"},
        )
        guion_json = json.loads(completion.choices[0].message.content)
        guion_json["guion"]["narracion"] = _asegurar_cierre_video(guion_json["guion"]["narracion"], idioma="es")
        return guion_json
    except Exception as e:
        raise RuntimeError(f"Error generando guion ES: {e}")


def traducir_guion_a_ingles(guion_es: dict) -> dict:
    """Adapta el guion al inglés manteniendo tensión, ritmo y longitud narrativa."""
    client = _get_groq_client()
    datos = guion_es["guion"]

    prompt = f"""
    Translate and adapt this Spanish short documentary script for 'The Black Box Archives'.
    Keep high retention, sharp dramatic hooks, and natural American English narration.
    
    Source Title: {datos['titulo']}
    Source Script: {datos['narracion']}
    
    Rules:
    1. Hook start with "Did you know that...?"
    2. Maintain exact narrative progression and factual accuracy.
    3. Mandatory final sentence: "{CIERRE_VIDEO_EN}".
    4. Return ONLY valid JSON:
    {{"guion": {{"titulo": "Captivating English Title", "narracion": "English narration text"}}}}
    """

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are a professional documentary scriptwriter. Output strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        guion_en = json.loads(completion.choices[0].message.content)
        guion_en["guion"]["narracion"] = _asegurar_cierre_video(guion_en["guion"]["narracion"], idioma="en")
        return guion_en
    except Exception as e:
        raise RuntimeError(f"Error traduciendo guion EN: {e}")


def guardar_guion(guion_data: dict, sufijo: str = "") -> Path:
    """Guarda el JSON del guion en outputs/json/ con sufijo de idioma opcional."""
    output_dir = BASE_DIR / "outputs" / "json"
    output_dir.mkdir(parents=True, exist_ok=True)

    titulo = guion_data["guion"]["titulo"]
    nombre_base = "".join(c if c.isalnum() else "_" for c in titulo).lower()
    nombre_base = "_".join(filter(None, nombre_base.split("_")))[:40]

    nombre_archivo = f"{nombre_base}{sufijo}.json" if sufijo else f"{nombre_base}.json"
    ruta_archivo = output_dir / nombre_archivo
    ruta_archivo.write_text(json.dumps(guion_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Guion guardado en: {ruta_archivo}")
    return ruta_archivo