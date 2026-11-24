"""Pipeline principal de CajaNegraBot para producción automatizada de Shorts bilingües.
Integra rotación por dominios históricos aislados, ComfyUI, Edge-TTS con marcas 
de tiempo nativas y quemado de subtítulos dinámicos sin desfasajes.
"""

import json
import os
import random
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import moviepy.editor as mp

from generator import generar_guion, traducir_guion_a_ingles
from images import generar_secuencia_imagenes
from tts import convertir_texto_a_voz
from video import montar_video_final
from subtitles import agregar_subtitulos_al_video
from metadata import generar_archivo_metadata

# ========================================================
# DETECCIÓN DE RUTA PERSISTENTE (COMPATIBLE CON .EXE)
# ========================================================
if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

ARCHIVO_HISTORIAL = BASE_DIR / "historial_temas.json"

# ========================================================
# DOMINIOS HISTÓRICOS Y CIENTÍFICOS AISLADOS (ANTI-REDUNDANCIA)
# ========================================================
DOMINIOS_HISTORICOS = [
    {
        "dominio": "DESASTRES DE LA NATURALEZA Y ERRORES GEOLÓGICOS",
        "ejemplos": "lagos drenados por error minero (Lago Peigneur), lluvias de animales reales, incendios subterráneos perpetuos (Centralia), cuevas letales o árboles tóxicos",
        "evitar": "computadoras, software, hackers, robots, circuitos, bugs informáticos"
    },
    {
        "dominio": "CRIMEN INGENIOSO, ROBOS Y FARSANTES DE ALTO NIVEL",
        "ejemplos": "el robo del banco de Niza por alcantarillas, falsificadores de arte magistrales, impostores en monarquías, fugas carcelarias surrealistas",
        "evitar": "chips, tecnología digital moderna, programación, bugs, satélites"
    },
    {
        "dominio": "MEDICINA ARCAICA, CIRUGÍA SALVAJE Y BOTICA TÓXICA",
        "ejemplos": "elixires victorianos con radio (Radithor), cirugías apresuradas del siglo XIX (Robert Liston), dentaduras de Waterloo, fósforo blanco",
        "evitar": "cibernética, computadoras, internet, virus de software, robots"
    },
    {
        "dominio": "ABSURDOS BÉLICOS, EXPEDICIONES Y DIPLOMACIA DISPARATADA",
        "ejemplos": "la guerra del perro de 1925, barcos camuflados de islas tropicales, expediciones al Ártico con ropa inadecuada, tratados olvidados",
        "evitar": "código informático, programación, bugs, Silicon Valley, robots"
    },
    {
        "dominio": "CIENCIA COTIDIANA Y FENÓMENOS FÍSICOS EXTRAÑOS",
        "ejemplos": "por qué el cristal de seguridad se descubrió con celuloide seco, el efecto triboluminiscente del azúcar, el olor de la lluvia (petricor)",
        "evitar": "guerra fría, espionaje militar, robots, ciberseguridad"
    },
    {
        "dominio": "EPISODIOS BIZARROS DE LA CULTURA POP, ALIMENTOS Y COMERCIO",
        "ejemplos": "la fiebre de los tulipanes en 1637, la catástrofe de la melaza de Boston de 1919, el invento de los cereales por desvelo puritano",
        "evitar": "software, microchips, robótica, cibernética"
    }
]


def _cargar_datos_historial() -> dict:
    """Carga los temas abordados para no repetirlos."""
    if not ARCHIVO_HISTORIAL.exists():
        datos_iniciales = {"ultimo_indice_categoria": -1, "temas": []}
        ARCHIVO_HISTORIAL.write_text(json.dumps(datos_iniciales, ensure_ascii=False, indent=2), encoding="utf-8")
        return datos_iniciales
    try:
        return json.loads(ARCHIVO_HISTORIAL.read_text(encoding="utf-8"))
    except Exception:
        return {"ultimo_indice_categoria": -1, "temas": []}


def _guardar_tema_en_historial(tema: str, nuevo_indice: int) -> None:
    """Registra el tema procesado."""
    datos = _cargar_datos_historial()
    datos["ultimo_indice_categoria"] = nuevo_indice
    datos["temas"].append(tema.strip())
    ARCHIVO_HISTORIAL.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def es_tema_duplicado_con_ia(client: Groq, tema_propuesto: str, historial: list[str]) -> bool:
    """Valida semánticamente si el tema ya fue cubierto en el canal."""
    if not historial:
        return False

    tema_norm = re.sub(r"[^\w\s]", "", tema_propuesto).strip().lower()
    for h in historial:
        h_norm = re.sub(r"[^\w\s]", "", h).strip().lower()
        if tema_norm in h_norm or h_norm in tema_norm:
            print(f"Coincidencia textual directa detectada con: '{h}'")
            return True

    muestra = historial[-60:]
    prompt_arbitro = f"""
    Eres el editor en jefe del canal 'La Caja Negra'.
    Determina si el TEMA PROPUESTO trata sobre el MISMO hecho histórico, descubrimiento, invento o personaje que alguno de los TEMAS PREVIOS.
    Si habla del mismo hecho de fondo (aunque use otras palabras o enfoque), responde DUPLICADO.
    Si es un hecho nuevo o diferente, responde NUEVO.

    TEMA PROPUESTO:
    "{tema_propuesto}"

    HISTORIAL RECIENTE:
    {json.dumps(muestra, ensure_ascii=False)}

    Responde ÚNICAMENTE con la palabra "DUPLICADO" o "NUEVO".
    """

    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "Eres un árbitro editorial estricto. Responde solo DUPLICADO o NUEVO."},
                {"role": "user", "content": prompt_arbitro},
            ],
            temperature=0.0,
            max_completion_tokens=20,
        )
        resp = completion.choices[0].message.content.strip().upper()
        es_duplicado = "DUPLICADO" in resp
        if es_duplicado:
            print(f"Árbitro IA: '{tema_propuesto}' trata un hecho ya existente en el historial.")
        return es_duplicado
    except Exception as e:
        print(f"Advertencia en árbitro IA: {e}. Se permite continuar.")
        return False


def obtener_tema_automatico(max_intentos: int = 8) -> tuple[str, int]:
    """Genera hechos reales no redundantes rotando dominios temáticos aislados."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    datos_historial = _cargar_datos_historial()
    temas_previos = datos_historial["temas"]

    # Selección aleatoria obligatoria de un dominio distinto
    dominio = random.choice(DOMINIOS_HISTORICOS)

    muestra_reciente = temas_previos[-30:] if len(temas_previos) > 30 else temas_previos
    lista_recientes_str = "\n".join(f"- {t}" for t in muestra_reciente) if muestra_reciente else "Ninguno"

    rechazados_en_esta_sesion = []
    tema_candidato_final = ""

    for intento in range(max_intentos):
        texto_rechazados = ""
        if rechazados_en_esta_sesion:
            texto_rechazados = "TEMAS RECIÉN RECHAZADOS (CAMBIA RADICALMENTE):\n" + "\n".join(f"✖ {r}" for r in rechazados_en_esta_sesion)

        prompt_generador = f"""
        Eres el investigador del canal 'La Caja Negra'.
        Propones curiosidades históricas y científicas reales, inteligentes e irónicas sobre la torpeza y genialidad humana.

        DOMINIO ASIGNADO PARA ESTE VIDEO:
        👉 {dominio['dominio']}
        Pistas / Línea: {dominio['ejemplos']}
        TERMINANTEMENTE PROHIBIDO EN ESTE TURNO: {dominio['evitar']}, 'bug', 'software', 'cibernético', 'robot'.

        REGLAS DE ORO OBLIGATORIAS:
        1. DEBE SER UN HECHO 100% REAL Y DOCUMENTADO. No inventes híbridos ficticios.
        2. Menciona a la persona, el lugar o el objeto verídico (ej. Robert Liston, Lago Peigneur, Radithor, Boston 1919).
        3. Prohibidos los clichés de internet (nada de microondas con chocolate, penicilina, Silly Putty, ni guerra de los emúes).
        {texto_rechazados}

        HISTORIAL RECIENTE A EVITAR:
        {lista_recientes_str}

        MISIÓN:
        Entrega ÚNICAMENTE el título llamativo y directo (máximo 12 palabras). Sin explicaciones, comillas ni adornos.
        """

        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un historiador implacable. Solo propones eventos verídicos con nombres, fechas o lugares documentados.",
                },
                {"role": "user", "content": prompt_generador},
            ],
            temperature=0.88,
            max_completion_tokens=80,
            extra_body={"reasoning_effort": "low"},
        )

        texto_respuesta = completion.choices[0].message.content.strip()
        lineas = [l.strip().replace('"', "").replace("'", "").replace("*", "") for l in texto_respuesta.splitlines() if l.strip()]
        tema_candidato = lineas[0] if lineas else ""

        if not tema_candidato:
            continue

        es_duplicado = es_tema_duplicado_con_ia(client, tema_candidato, temas_previos)

        if not es_duplicado:
            print(f"🎯 Tema seleccionado [{dominio['dominio']}]: '{tema_candidato}'")
            return tema_candidato, 0

        rechazados_en_esta_sesion.append(tema_candidato)
        print(f"⚠️ Tema repetido ({tema_candidato}). Buscando otra alternativa ({intento + 1}/{max_intentos})...")
        tema_candidato_final = tema_candidato

    return (tema_candidato_final if tema_candidato_final else "El insólito incidente que transformó la historia moderna"), 0


def producir_short_bilingue(tema: str = None) -> tuple[Path, Path]:
    """Ejecuta el ciclo de producción completo en Español e Inglés."""
    indice_categoria = 0
    if not tema or not tema.strip():
        tema, indice_categoria = obtener_tema_automatico()
    else:
        tema = tema.strip()
        print(f"📌 Usando tema manual proporcionado: '{tema}'")

    print("\n" + "=" * 60)
    print(f"🎬 INICIANDO PRODUCCIÓN DE SHORTS BILINGÜES: {tema.upper()}")
    print("=" * 60)

    # 1. Estructuración del guion bilingüe
    print("\n[Paso 1/5] Generando guiones sincronizados (ES + EN)...")
    guion_es_data = generar_guion(tema)
    guion_en_data = traducir_guion_a_ingles(guion_es_data)
    guion_es = guion_es_data["guion"]
    guion_en = guion_en_data["guion"]

    nombre_base = re.sub(r"[^\w\s-]", "", tema.lower())
    nombre_base = re.sub(r"[\s_-]+", "_", nombre_base).strip("_")[:50]

    dir_json = BASE_DIR / "outputs" / "json"
    dir_json.mkdir(parents=True, exist_ok=True)
    ruta_json_es = dir_json / f"{nombre_base}_es.json"
    ruta_json_en = dir_json / f"{nombre_base}_en.json"

    ruta_json_es.write_text(json.dumps({"guion": guion_es}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_json_en.write_text(json.dumps({"guion": guion_en}, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. Generación visual con ComfyUI (12 escenas compartidas)
    print("\n[Paso 2/5] Generando 12 ilustraciones de cómic en ComfyUI...")
    generar_secuencia_imagenes(
        guion_completo=guion_es["narracion"],
        titulo=guion_es.get("titulo", tema),
        nombre_base=nombre_base,
        total_escenas=12
    )

    # 3. Síntesis de voz con captura de tiempos exactos
    print("\n[Paso 3/5] Sintetizando voz en off bilingüe y calculando marcas de tiempo...")
    ruta_audio_es = convertir_texto_a_voz(guion_es["narracion"], nombre_base=f"{nombre_base}_es", idioma="es")
    ruta_audio_en = convertir_texto_a_voz(guion_en["narracion"], nombre_base=f"{nombre_base}_en", idioma="en")

    # Medir duración exacta del audio para sincronizar el corte de video
    clip_a_es = mp.AudioFileClip(str(ruta_audio_es))
    duracion_es = clip_a_es.duration
    clip_a_es.close()

    clip_a_en = mp.AudioFileClip(str(ruta_audio_en))
    duracion_en = clip_a_en.duration
    clip_a_en.close()

    # 4. Montaje de video base vertical con Ken Burns y música
    print("\n[Paso 4/5] Ensamblando videos verticales en MoviePy / FFmpeg...")
    ruta_video_es = montar_video_final(
        nombre_base=f"{nombre_base}_es",
        duracion_voz=duracion_es,
        ruta_audio_personalizada=ruta_audio_es,
        idioma="es"
    )
    ruta_video_en = montar_video_final(
        nombre_base=f"{nombre_base}_en",
        duracion_voz=duracion_en,
        ruta_audio_personalizada=ruta_audio_en,
        idioma="en"
    )

    # 5. Subtítulos dinámicos sincronizados
    print("\n[Paso 5/5] Quemando subtítulos sincronizados...")
    video_final_es = agregar_subtitulos_al_video(ruta_video_es, ruta_audio_es, idioma="es", texto_referencia=guion_es["narracion"])
    video_final_en = agregar_subtitulos_al_video(ruta_video_en, ruta_audio_en, idioma="en", texto_referencia=guion_en["narracion"])

    # 6. Metadata de publicación y registro en historial
    generar_archivo_metadata(titulo=guion_es.get("titulo", tema), tema=tema, nombre_base=nombre_base, idioma="es")
    generar_archivo_metadata(titulo=guion_en.get("titulo", tema), tema=tema, nombre_base=nombre_base, idioma="en")
    _guardar_tema_en_historial(tema, indice_categoria)

    print("\n" + "=" * 60)
    print("✔ PRODUCCIÓN FINALIZADA CON ÉXITO")
    print(f"👉 Short Español: {video_final_es}")
    print(f"👉 Short Inglés:  {video_final_en}")
    print("=" * 60)

    return video_final_es, video_final_en


if __name__ == "__main__":
    producir_short_bilingue()