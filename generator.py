"""Módulo para generar y traducir guiones estructurados con Groq (ES / EN).

Optimizado para openai/gpt-oss-120b con reasoning controlado para evitar respuestas vacías.
Calibrado para videos verticales de 1:10 a 1:20 min en formato '¿Sabías que...?':
hackeos, robos, casos criminales, ciencia, universo, planeta, orígenes de las cosas y desastres.
Canal: La Caja Negra / The Black Box Archives.

Cambios clave:
  * El guion adapta su enfoque según el tipo de tema (crimen, hackeo, ciencia, origen, desastre).
  * La longitud se VALIDA por conteo real de palabras y se reintenta con corrección si se sale del rango.
  * El cierre (CTA) se cuenta dentro del total de palabras.
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

CIERRE_VIDEO_ES = "Dale Like y suscríbete para más contenido"
CIERRE_VIDEO_EN = "Like and subscribe for more documented truths"

# Rango objetivo de palabras (incluye el cierre) y tolerancia antes de forzar un reintento
RANGO_ES = (180, 205)
RANGO_EN = (175, 200)
TOLERANCIA_PALABRAS = 8
MAX_INTENTOS = 3


# ========================================================
# UTILIDADES
# ========================================================
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


def _limpiar_narracion(texto: str) -> str:
    """Quita restos de formato que no deben llegar a la locución ni a los subtítulos."""
    texto = re.sub(r"\[[^\]]*\]", " ", texto)  # anotaciones entre corchetes
    texto = re.sub(r"[*#_`]+", "", texto)       # restos de markdown
    return re.sub(r"\s+", " ", texto).strip()


def _contar_palabras(texto: str) -> int:
    return len(re.findall(r"\b[\wÁÉÍÓÚÜÑáéíóúüñ'’-]+\b", texto))


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("API Key de Groq no configurada en .env.")
    return Groq(api_key=api_key)


def _limpiar_y_parsear_json(texto: str) -> dict:
    """Extrae y decodifica el bloque JSON válido del texto generado por el LLM."""
    texto_limpio = (texto or "").strip()
    if not texto_limpio:
        raise ValueError("El modelo devolvió una respuesta vacía.")

    if "```json" in texto_limpio:
        texto_limpio = texto_limpio.split("```json")[1].split("```")[0].strip()
    elif "```" in texto_limpio:
        texto_limpio = texto_limpio.split("```")[1].split("```")[0].strip()

    match = re.search(r"(\{.*\})", texto_limpio, re.DOTALL)
    if match:
        texto_limpio = match.group(1)

    return json.loads(texto_limpio)


def _validar_guion(data: dict, rango: tuple[int, int], idioma: str) -> str | None:
    """Normaliza el guion in situ. Devuelve None si es válido o un mensaje con el problema."""
    try:
        guion = data["guion"]
        titulo = str(guion["titulo"]).strip()
        narracion = _limpiar_narracion(str(guion["narracion"]))
    except (KeyError, TypeError):
        return 'El JSON debe tener la forma {"guion": {"titulo": ..., "narracion": ...}}.'

    if not titulo or not narracion:
        return "El título o la narración están vacíos."

    narracion = _asegurar_cierre_video(narracion, idioma=idioma)
    palabras = _contar_palabras(narracion)
    minimo, maximo = rango
    if palabras < minimo - TOLERANCIA_PALABRAS:
        return f"La narración tiene {palabras} palabras (con el cierre); debe tener entre {minimo} y {maximo}. Amplía el desarrollo con hechos reales."
    if palabras > maximo + TOLERANCIA_PALABRAS:
        return f"La narración tiene {palabras} palabras (con el cierre); debe tener entre {minimo} y {maximo}. Recorta detalles secundarios."

    guion["titulo"] = titulo
    guion["narracion"] = narracion
    return None


def _generar_con_validacion(client: Groq, mensajes: list[dict], temperature: float, rango: tuple[int, int], idioma: str) -> dict:
    """Llama al modelo, valida estructura y longitud, y reintenta con retroalimentación concreta."""
    mejor_resultado = None
    ultimo_error = "sin intentos"

    for intento in range(1, MAX_INTENTOS + 1):
        contenido = ""
        try:
            completion = client.chat.completions.create(
                model=MODELO_ACTIVO,
                messages=mensajes,
                temperature=temperature,
                max_completion_tokens=3000,
                extra_body={"reasoning_effort": "low"},
            )
            contenido = completion.choices[0].message.content or ""
            data = _limpiar_y_parsear_json(contenido)
            problema = _validar_guion(data, rango, idioma)
            if problema is None:
                return data
            ultimo_error = problema
            # Si el JSON es usable pero se pasó de rango, lo guardamos por si agotamos los intentos
            if "guion" in data and isinstance(data["guion"], dict) and data["guion"].get("narracion"):
                data["guion"]["narracion"] = _asegurar_cierre_video(_limpiar_narracion(str(data["guion"]["narracion"])), idioma)
                mejor_resultado = data
        except Exception as e:
            ultimo_error = f"{type(e).__name__}: {e}"
            problema = f"Tu respuesta no fue un JSON válido y completo ({ultimo_error}). Devuelve solo el JSON, bien cerrado."

        print(f"⚠️ Guion {idioma.upper()} intento {intento}/{MAX_INTENTOS}: {ultimo_error}")
        if contenido:
            mensajes = mensajes + [
                {"role": "assistant", "content": contenido},
                {"role": "user", "content": f"Corrige esto y devuelve de nuevo SOLO el JSON completo: {problema}"},
            ]

    if mejor_resultado is not None:
        print(f"⚠️ Se usa el último guion generado aunque el conteo no es ideal ({ultimo_error}).")
        return mejor_resultado
    raise RuntimeError(f"No se pudo generar un guion {idioma.upper()} válido: {ultimo_error}")


# ========================================================
# GENERACIÓN EN ESPAÑOL
# ========================================================
def generar_guion(tema: str, minimo: int = RANGO_ES[0], maximo: int = RANGO_ES[1]) -> dict:
    """Genera un guion '¿Sabías que...?' directo, verídico y adictivo.

    Calibrado a 180-205 palabras (incluido el cierre) para 1:10 a 1:20 minutos de locución.
    """
    client = _get_groq_client()

    prompt = f"""
Escribe un guion en español para un video vertical (Short) del canal '¿Sabías que...?' sobre este tema: "{tema}".

TONO:
- Cuéntalo como si le revelaras a un amigo, en una cafetería, el dato más increíble que acabas de descubrir.
- Ritmo ágil, frases cortas, lenguaje cotidiano. CERO lenguaje poético, CERO metáforas vacías, CERO tecnicismos pesados.
- Mantén la tensión: cada frase debe dar ganas de escuchar la siguiente.

ADAPTA EL ENFOQUE SEGÚN EL TIPO DE TEMA:
- Hackeo, ciberdelito o robo: narra QUÉ pasó, QUIÉN lo hizo, CÓMO los descubrieron y qué consecuencias tuvo. Es una historia, NO un tutorial: no des pasos, herramientas ni instrucciones que se puedan replicar.
- Crimen, asesino o caso criminal: usa solo hechos documentados judicial o históricamente. Tono informativo y respetuoso con las víctimas, sin detalles gráficos ni morbo, sin glorificar al culpable. Destaca cómo se resolvió el caso o qué cambió después.
- Ciencia, universo o planeta: explica el 'POR QUÉ' de forma sencilla y visual, con causas reales y comparaciones cotidianas.
- Origen o invención ('cómo se creó' / 'cómo surgió'): cuenta el proceso real paso a paso, con el error, la casualidad o la persona que lo originó.
- Desastre o accidente: muestra la cadena de errores pequeños que terminó en algo enorme.

REGLAS ESTRICTAS:
1. Longitud: entre {minimo} y {maximo} palabras en total, CONTANDO la frase de cierre. No entregues menos de {minimo}.
2. Primera frase: gancho directo que empiece con "¿Sabías que...?" planteando el dato, la duda o el hecho insólito.
3. Todo debe ser real y verificable. NO inventes cifras, fechas, diálogos ni detalles. Si no estás seguro de un dato exacto, usa una referencia aproximada (por ejemplo "a finales de los noventa") o no lo menciones.
4. Cuenta los hechos en orden claro y deja que el desenlace fluya solo. PROHIBIDO usar frases como "el giro llegó", "la moraleja es", "en conclusión" o "la sorpresa fue".
5. Última frase obligatoria: "{CIERRE_VIDEO_ES}".
6. Sin anotaciones de cámara, corchetes, emojis ni efectos de sonido: solo el texto limpio de la locución.
7. Escribe los números y años de forma que se lean bien en voz alta.

Responde ÚNICAMENTE un JSON válido y cerrado con este formato:
{{"guion": {{"titulo": "Título corto con gancho irresistible", "narracion": "Texto completo de la locución"}}}}
"""

    mensajes = [
        {
            "role": "system",
            "content": (
                "Eres el guionista de '¿Sabías que...?' (La Caja Negra). Divulgas hechos reales y sorprendentes: "
                "hackeos, robos, casos criminales documentados, ciencia, universo, planeta, orígenes de las cosas y desastres. "
                "Eres riguroso con los hechos, dinámico y cercano. Respondes únicamente con un objeto JSON válido y cerrado."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    return _generar_con_validacion(client, mensajes, temperature=0.6, rango=(minimo, maximo), idioma="es")


# ========================================================
# TRADUCCIÓN AL INGLÉS
# ========================================================
def traducir_guion_a_ingles(guion_es: dict) -> dict:
    """Adapta el guion al inglés manteniendo el ritmo, la claridad y la duración."""
    client = _get_groq_client()
    datos = guion_es["guion"]
    minimo, maximo = RANGO_EN

    prompt = f"""
Translate and adapt this Spanish script for 'The Black Box Archives' vertical video (the English version of the "Did you know...?" channel).
Keep the same fast-paced, curious, casual storytelling tone, like sharing a mind-blowing fact with a friend.
If it explains why something happens, keep the explanation crystal clear without dry academic jargon.
Keep every fact exactly as in the source: do NOT add, change or invent names, dates, numbers or details.
If the source is about a crime or a hack, keep it informative and non-graphic, and never turn it into instructions.

Source Title: {datos['titulo']}
Source Script: {datos['narracion']}

Rules:
1. The first sentence MUST start with "Did you know that...?"
2. Keep the same order of events. Total length: {minimo} to {maximo} words INCLUDING the closing sentence.
3. NO meta-narrative announcements like "the surprise came", "in conclusion" or "unexpected twist".
4. The final sentence must be exactly: "{CIERRE_VIDEO_EN}".
5. No brackets, emojis or sound/camera notes. Write numbers and years so they read well aloud.
6. The JSON must be strictly complete and closed.

Return ONLY valid JSON:
{{"guion": {{"titulo": "Punchy viral English title", "narracion": "Narration text"}}}}
"""

    mensajes = [
        {
            "role": "system",
            "content": (
                "You write engaging, factually faithful curiosity scripts for 'The Black Box Archives'. "
                "You translate without altering facts and explain the 'why' casually and clearly. "
                "Output strict, complete, properly closed JSON only."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    return _generar_con_validacion(client, mensajes, temperature=0.4, rango=(minimo, maximo), idioma="en")


# ========================================================
# GUARDADO
# ========================================================
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