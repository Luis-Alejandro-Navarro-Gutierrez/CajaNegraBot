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

# Modelos disponibles con cuotas independientes
MODELOS_GROQ = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b"
]

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
    """Extrae y decodifica JSON válido aunque el modelo agregue bloques Markdown."""
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


def generar_guion(tema: str, minimo: int = 180, maximo: int = 200) -> dict:
    """Genera un guion documental estructurado en español con Groq usando rotación de modelos."""
    client = _get_groq_client()

    prompt = f"""
    Escribe un guion en español tipo "¿Sabías que...?" para Shorts sobre: "{tema}".
    Enfoque: misterio documental, hechos reales comprobados, tensión sostenida y revelaciones asombrosas sin tecnicismos densos.
    
    Reglas estrictas:
1. Longitud de narración: exactamente {minimo}-{maximo} palabras totales.
2. Comienza directo con un gancho potente "¿Sabías que...?".
3. Ritmo narrativo fluido: plantea el misterio o anomalía y revela lo inesperado mediante los propios hechos, SIN anunciar las partes de la historia.
4. PROHIBIDO terminantemente usar frases o muletillas de meta-narrativa como "el giro llegó", "el giro se dio", "el giro inesperado", "la sorpresa fue", "el clímax" o "la moraleja". El cambio de rumbo debe ser 100% implícito, orgánico y conducido por la acción (ejemplos: "Sin embargo, cuando abrieron...", "Pero los análisis revelaron algo aterrador...", "Todo cambió en un segundo cuando...").
5. Cierre obligatorio como última frase de la narración: "{CIERRE_VIDEO_ES}".
6. Cero anotaciones de cámara o efectos de sonido; solo texto limpio para locución.
7. Asegúrate de cerrar la estructura JSON completamente.

    Responde ÚNICAMENTE un JSON válido con este formato exacto:
    {{"guion": {{"titulo": "Título intrigante", "narracion": "Texto completo"}}}}
    """

    mensajes = [
        {
            "role": "system",
            "content": "Eres guionista documental de videos virales de alta retención. La narrativa es inmersiva y jamás anuncia los giros explícitamente. Devuelve solo un documento JSON válido y estrictamente cerrado.",
        },
        {"role": "user", "content": prompt},
    ]

    ultimo_error = None
    for modelo in MODELOS_GROQ:
        try:
            params = {
                "model": modelo,
                "messages": mensajes,
                "temperature": 0.45,
                "max_tokens": 1500,
            }
            if "gemma" not in modelo.lower():
                params["response_format"] = {"type": "json_object"}

            completion = client.chat.completions.create(**params)
            guion_json = _limpiar_y_parsear_json(completion.choices[0].message.content)
            guion_json["guion"]["narracion"] = _asegurar_cierre_video(guion_json["guion"]["narracion"], idioma="es")
            return guion_json
        except Exception as e:
            ultimo_error = e
            print(f"  ⚠ Modelo '{modelo}' falló al generar guion ES ({e}). Reintentando...")

    raise RuntimeError(f"Error generando guion ES tras agotar modelos: {ultimo_error}")


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
1. Hook must start with "Did you know that...?"
2. Maintain exact narrative progression, factual accuracy, and word count (~180-200 words).
3. STRICTLY FORBIDDEN meta-narrative announcements like "the twist came", "the twist happened", "the unexpected plot twist", or "the climax was". Reveal the turn of events purely through actions and facts (e.g., "However, upon closer inspection...", "What investigators actually discovered shook everyone...", "Everything collapsed when...").
4. Mandatory final sentence: "{CIERRE_VIDEO_EN}".
5. Ensure the JSON structure is strictly complete and properly closed.

    Return ONLY valid JSON with this exact structure:
    {{"guion": {{"titulo": "Captivating English Title", "narracion": "English narration text"}}}}
    """

    mensajes = [
        {
            "role": "system",
            "content": "You are an expert documentary scriptwriter. Deliver cinematic immersion without declaring plot transitions. Output strict, complete, and properly closed JSON only.",
        },
        {"role": "user", "content": prompt},
    ]

    ultimo_error = None
    for modelo in MODELOS_GROQ:
        try:
            params = {
                "model": modelo,
                "messages": mensajes,
                "temperature": 0.3,
                "max_tokens": 1500,
            }
            if "gemma" not in modelo.lower():
                params["response_format"] = {"type": "json_object"}

            completion = client.chat.completions.create(**params)
            guion_en = _limpiar_y_parsear_json(completion.choices[0].message.content)
            guion_en["guion"]["narracion"] = _asegurar_cierre_video(guion_en["guion"]["narracion"], idioma="en")
            return guion_en
        except Exception as e:
            ultimo_error = e
            print(f"  ⚠ Modelo '{modelo}' falló al traducir guion EN ({e}). Reintentando...")

    raise RuntimeError(f"Error traduciendo guion EN tras agotar modelos: {ultimo_error}")


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