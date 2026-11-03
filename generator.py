"""Módulo para generar guiones claros y atractivos sobre hechos reales con Groq."""

import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

CIERRE_VIDEO = "Dale Like y suscribete para mas contenido"


def _asegurar_cierre_video(narracion: str) -> str:
    """Garantiza que la narración termine con el CTA acordado, una sola vez."""
    narracion = re.sub(
        r"[\s.!?…,:;—-]*dale\s+like\s+y\s+suscr[ií]bete\s+para\s+m[aá]s\s+contenido[.!?…]*\s*$",
        "",
        narracion.strip(),
        flags=re.IGNORECASE,
    ).rstrip(" .!?…,:;—-")
    if not narracion:
        return CIERRE_VIDEO
    return f"{narracion}. {CIERRE_VIDEO}"


def generar_guion(tema: str, minimo: int = 180, maximo: int = 200) -> dict:
    """Envía un prompt a la API de Groq para obtener un guion estructurado en formato JSON."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("API Key de Groq no encontrada en las variables de entorno (.env).")

    client = Groq(api_key=api_key)

    prompt = f"""
    Escribe en español un guion fascinante tipo "¿Sabías que...?" para TikTok y YouTube Shorts sobre esta curiosidad real: "{tema}".
    El público busca quedar intrigado y sorprendido con un dato que parezca salido de una película pero que sea 100% verídico. Explícalo con total claridad, ritmo ágil y sencillez.

    Enfoque y Tono del Canal:
    - Buscamos un balance perfecto entre misterio histórico, enigmas de la ciencia, tecnología pionera y rarezas biológicas de la naturaleza que tengan un giro inesperado o perturbador (factor "¡No puedo creer que esto pasó!").
    - Ejemplos del tono buscado: el accidente del "Demon Core" con un simple destornillador, cómo el código Enigma se descifró en secreto, parásitos reales de la naturaleza que controlan la mente, o incidentes de la Guerra Fría evitados por una sola persona.
    - No uses tecnicismos densos, fechas amontonadas ni lenguaje aburrido. Cada frase debe avanzar la historia con tensión y dinamismo.

    Reglas estrictas:
    1. La narración completa, incluido el cierre obligatorio, debe tener entre {minimo} y {maximo} palabras. Antes del cierre, escribe entre {max(1, minimo - 7)} y {max(1, maximo - 7)} palabras.
    2. Basa el relato en hechos reales verificados. Plantea el dato con rigor pero destacando su lado más asombroso, insólito o dramático.
    3. Empieza directamente con un gancho potente que inicie con "¿Sabías que...?" y revele una paradoja o contradicción fascinante para detener el scroll de inmediato.
    4. Estructura de retención:
       - Gancho (0-3 seg): La afirmación chocante inicial.
       - Contexto y nudo: Cómo comenzó la situación, el dilema o la anomalía.
       - La revelación o giro: El detalle concreto que genera la reacción de asombro ("OMG").
       - Desenlace: Qué ocurrió al final o cómo impactó hasta el día de hoy.
    5. Usa frases cortas, lenguaje conversacional y voz activa. Si mencionas un término técnico, defínelo en 4 palabras cotidianas.
    6. La última frase hablada debe ser exactamente: "{CIERRE_VIDEO}". No agregues nada después. Debe quedar dentro del conteo de palabras.
    7. No incluyas acotaciones de audio, corchetes, notas de producción ni música; solo el texto que será leído por el locutor.

    Devuelve ÚNICAMENTE JSON válido con esta estructura exacta:
    {{
      "guion": {{
        "titulo": "Título intrigante y directo con gancho, sin caer en engaños",
        "narracion": "Texto completo de la narración"
      }}
    }}
    """
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un narrador y guionista de videos virales de alta retención especializado en curiosidades reales, misterios científicos y hechos históricos asombrosos. Entregas solo JSON estricto.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.45,
            reasoning_effort="low",
            max_completion_tokens=4096,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "video_script",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "guion": {
                                "type": "object",
                                "properties": {
                                    "titulo": {"type": "string"},
                                    "narracion": {"type": "string"},
                                },
                                "required": ["titulo", "narracion"],
                                "additionalProperties": False,
                            }
                        },
                        "required": ["guion"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        texto_respuesta = completion.choices[0].message.content
        guion_json = json.loads(texto_respuesta)
        guion_json["guion"]["narracion"] = _asegurar_cierre_video(guion_json["guion"]["narracion"])
        return guion_json

    except Exception as e:
        raise RuntimeError(f"Error al generar el guion con Groq: {e}")


def guardar_guion(guion_data: dict) -> Path:
    """Guarda el guion estructurado en un archivo JSON dentro de outputs/json/."""
    output_dir = BASE_DIR / "outputs" / "json"
    output_dir.mkdir(parents=True, exist_ok=True)

    titulo = guion_data["guion"]["titulo"]
    nombre_base = "".join(c if c.isalnum() else "_" for c in titulo).lower()
    nombre_base = "_".join(filter(None, nombre_base.split("_")))[:40]

    ruta_archivo = output_dir / f"{nombre_base}.json"
    ruta_archivo.write_text(json.dumps(guion_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Guion guardado en: {ruta_archivo}")
    return ruta_archivo