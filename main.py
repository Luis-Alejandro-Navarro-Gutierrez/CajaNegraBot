"""Pipeline de CajaNegraBot para producir videos documentales breves bilingües (ES / EN)."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import moviepy.editor as mp

# ========================================================
# DETECCIÓN DE RUTA PERSISTENTE A LA RAÍZ DEL PROYECTO (--onefile)
# ========================================================
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

os.chdir(str(BASE_DIR))
os.environ["CAJANEGRA_ROOT"] = str(BASE_DIR)

HISTORIAL_FILE = BASE_DIR / "historial_temas.json"
load_dotenv(BASE_DIR / ".env")

# Módulos del pipeline
from generator import CIERRE_VIDEO_ES, CIERRE_VIDEO_EN, generar_guion, traducir_guion_a_ingles, guardar_guion
from tts import convertir_texto_a_voz
from images import generar_secuencia_imagenes
from video import montar_video_final
from subtitles import agregar_subtitulos_al_video
from metadata import generar_archivo_metadata

# 5 Pilares Temáticos Principales
CATEGORIAS = [
    {
        "id": "asesinatos_venganzas_fallidas",
        "nombre": "ASESINATOS Y VENGANZAS QUE SALIERON RIDÍCULAMENTE MAL",
        "descripcion": (
            "Criminales o conspiradores cuyos planes macabros terminaron en una comedia de enredos real, "
            "autotrampas grotescas o blancos que resultaron indestructibles (como Michael Malloy o sicarios que se hicieron amigos de su objetivo). "
            "Enfoque directo al absurdo, sin terminología forense densa."
        ),
    },
    {
        "id": "robos_arruinados_estupidez",
        "nombre": "ROBOS MILLONARIOS ARRUINADOS POR ESTUPIDECES",
        "descripcion": (
            "Golpes a bancos, joyerías o transporte de valores donde burlaron alarmas avanzadas, "
            "pero fueron atrapados por descuidos ridículos (dejar recibos con su nombre, puertas que decían jale, o pagar con billetes seriados)."
        ),
    },
    {
        "id": "hackeos_crimenes_digitales",
        "nombre": "HACKEOS Y CRÍMENES DIGITALES INSÓLITOS",
        "descripcion": (
            "Ataques informáticos millonarios y asaltos cibernéticos contados con lenguaje cotidiano. "
            "Robos frustrados por faltas ortográficas (banco de Bangladesh), reclusos que hackearon prisiones desde una sala común o fallos técnicos insólitos."
        ),
    },
    {
        "id": "errores_anomalias_monumentales",
        "nombre": "ERRORES TONTOS Y ANOMALÍAS CON EFECTOS MONUMENTALES",
        "descripcion": (
            "Sustancias de consumo global (como el origen accidental del Viagra en ensayos cardíacos), inventos nacidos de descuidos de laboratorio "
            "y accidentes científicos que crearon industrias multimillonarias por pura suerte."
        ),
    },
    {
        "id": "conflictos_leyes_absurdas",
        "nombre": "GUERRAS, LEYES Y CONFLICTOS POR MOTIVOS ABSURDOS",
        "descripcion": (
            "Conflictos bélicos y movilizaciones militares desatadas por animales o comida (la Guerra del Cerdo, la Guerra de los Pasteles), "
            "o litigios y normas legales tan disparatadas que parecen ficción pero ocurrieron de verdad."
        ),
    },
]


def _cargar_datos_historial() -> dict:
    """Carga el historial y el índice de la última categoría ejecutada."""
    if HISTORIAL_FILE.exists():
        try:
            datos = json.loads(HISTORIAL_FILE.read_text(encoding="utf-8"))
            if isinstance(datos, list):
                return {"temas": datos, "ultimo_indice_categoria": -1}
            if isinstance(datos, dict):
                return {
                    "temas": datos.get("temas", []),
                    "ultimo_indice_categoria": datos.get("ultimo_indice_categoria", -1),
                }
        except Exception:
            pass
    return {"temas": [], "ultimo_indice_categoria": -1}


def _guardar_datos_historial(temas: list[str], indice_categoria: int) -> None:
    """Almacena el listado de temas y la última categoría para rotación fija."""
    contenido = {
        "ultimo_indice_categoria": indice_categoria,
        "temas": temas,
    }
    HISTORIAL_FILE.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")


def es_tema_duplicado_con_ia(client: Groq, nuevo_candidato: str, historial_temas: list[str]) -> bool:
    """Árbitro IA estricto: determina si la propuesta repite un hecho o historia del historial."""
    if not historial_temas:
        return False

    candidato_limpio = nuevo_candidato.strip().lower()
    for t in historial_temas:
        if candidato_limpio == t.strip().lower():
            return True

    temas_referencia = "\n".join(f"- {t}" for t in historial_temas)

    prompt_juez = f"""
    Evalúa si la siguiente propuesta de video trata sobre EL MISMO evento, hecho o historia real que cualquiera de los casos en el historial.

    PROPUESTA A EVALUAR:
    "{nuevo_candidato}"

    HISTORIAL DE TEMAS YA TRATADOS:
    {temas_referencia}

    Criterios:
    - Responde DUPLICADO si es la misma historia (aunque cambien las palabras o el título).
    - Responde NUEVO si es un evento o historia diferente.

    Responde ÚNICAMENTE con una sola palabra: 'DUPLICADO' o 'NUEVO'.
    """

    try:
        verificacion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "Eres un árbitro editorial estricto. Respondes únicamente DUPLICADO o NUEVO."},
                {"role": "user", "content": prompt_juez},
            ],
            temperature=0.0,
            max_completion_tokens=250,
            extra_body={"reasoning_effort": "low"},
        )
        veredicto = verificacion.choices[0].message.content.strip().upper()
        return "DUPLICADO" in veredicto
    except Exception as e:
        print(f"⚠️ Error consultando árbitro IA: {e}")
        return False


def obtener_tema_automatico(max_intentos: int = 6) -> tuple[str, int]:
    """Consulta a Groq rotando ordenadamente y validando mediante IA contextual contra el historial."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    datos_historial = _cargar_datos_historial()
    temas_previos = datos_historial["temas"]

    nuevo_indice = (datos_historial["ultimo_indice_categoria"] + 1) % len(CATEGORIAS)
    categoria = CATEGORIAS[nuevo_indice]

    print(f"🔄 Rotación temática [{nuevo_indice + 1}/{len(CATEGORIAS)}]: {categoria['nombre']}")

    lista_historial_prompt = "\n".join(f"- {t}" for t in temas_previos) if temas_previos else "Ninguno"

    prompt_generador = f"""
    Actúa como productor de contenido viral enfocado en crímenes absurdos, hackeos y misterios reales insólitos.
    Tu objetivo es proponer UN caso real, específico y comprobado que genere curiosidad morbosa y asombro ("¿En serio ocurrió esto?").

    CATEGORÍA OBLIGATORIA:
    {categoria['nombre']}
    Descripción: {categoria['descripcion']}

    REGLAS DE SELECCIÓN:
    - El caso debe ser 100% verídico y comprobable.
    - Debe resaltar la torpeza, la ironía, el error tonto o la audacia del hecho.
    - Cero lenguaje académico denso; debe ser llamativo de inmediato.
    - EL TEMA DEBE SER COMPLETAMENTE INÉDITO Y NO FIGURAR EN ESTE HISTORIAL:
    {lista_historial_prompt}

    Devuelve ÚNICAMENTE el nombre descriptivo y con gancho del caso (ejemplos: 'El robo millonario arruinado por una caja de pizza', 'El sicario que terminó viviendo con la esposa de su víctima', 'El hackeo detenido por una falta de ortografía').
    Sin comillas, sin introducciones ni explicaciones.
    """

    tema_candidato_final = ""
    for intento in range(max_intentos):
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un editor de historias virales insólitas. Propones solo títulos directos de sucesos reales asombrosos y cómicos.",
                },
                {"role": "user", "content": prompt_generador},
            ],
            temperature=0.8,
            max_completion_tokens=400,
            extra_body={"reasoning_effort": "low"},
        )

        texto_respuesta = completion.choices[0].message.content.strip()
        lineas = [l.strip().replace('"', "").replace("'", "").replace("*", "") for l in texto_respuesta.splitlines() if l.strip()]
        tema_candidato = lineas[0] if lineas else ""

        if not tema_candidato:
            continue

        es_duplicado = es_tema_duplicado_con_ia(client, tema_candidato, temas_previos)

        if not es_duplicado:
            return tema_candidato, nuevo_indice

        print(f"⚠️ El árbitro IA detectó que '{tema_candidato}' ya fue tratado en el historial. Reintentando ({intento + 1}/{max_intentos})...")
        tema_candidato_final = tema_candidato

    return (tema_candidato_final if tema_candidato_final else "Robo Insólito del Siglo"), nuevo_indice


def registrar_tema_en_historial(tema: str, indice_categoria: int) -> None:
    """Registra el tema exitoso y consolida el índice de rotación."""
    datos = _cargar_datos_historial()
    temas = datos["temas"]
    if tema not in temas:
        temas.append(tema)
    _guardar_datos_historial(temas, indice_categoria)


def eliminar_copias_base_subtituladas(ruta_video_final: Path) -> None:
    """Elimina videos base solo cuando existe su versión subtitulada correspondiente."""
    for copia_base in ruta_video_final.parent.glob("*.mp4"):
        if copia_base == ruta_video_final or copia_base.stem.endswith("_subtitulado"):
            continue

        copia_subtitulada = copia_base.with_name(f"{copia_base.stem}_subtitulado{copia_base.suffix}")
        if copia_subtitulada.exists():
            copia_base.unlink(missing_ok=True)
            print(f"✔ Copia sin subtítulos eliminada: {copia_base.name}")


def main() -> int:
    print("====================================================")
    print("   🤖 CAJANEGRABOT - FÁBRICA BILINGÜE DE SHORTS    ")
    print("   [ES] La Caja Negra  |  [EN] The Black Box Archives")
    print("====================================================")

    # 1. Obtener tema
    print("\n[1/8] Consultando un nuevo tema inédito a Groq...")
    tema, indice_cat = obtener_tema_automatico()
    print(f'🎯 Tema seleccionado: "{tema}"')

    # 2. Generar Guiones (ES calibrado a 210-230 palabras para superar el minuto)
    print("\n[2/8] Generando y adaptando guiones con Groq...")
    resultado_guion_es = generar_guion(tema, minimo=210, maximo=230)
    resultado_guion_en = traducir_guion_a_ingles(resultado_guion_es)

    # Extraer datos ES
    guion_data_es = resultado_guion_es["guion"]
    titulo_es = guion_data_es["titulo"]
    narracion_es = guion_data_es["narracion"]
    narracion_visual = narracion_es.removesuffix(" " + CIERRE_VIDEO_ES).rstrip()

    # Extraer datos EN
    guion_data_en = resultado_guion_en["guion"]
    titulo_en = guion_data_en["titulo"]
    narracion_en = guion_data_en["narracion"]

    # Guardar JSONs
    ruta_json_es = guardar_guion(resultado_guion_es, sufijo="_es")
    ruta_json_en = guardar_guion(resultado_guion_en, sufijo="_en")
    nombre_raiz = ruta_json_es.stem.removesuffix("_es")
    print(f"✔ Guion [ES]: {titulo_es}")
    print(f"✔ Script [EN]: {titulo_en}")

    # 3. Imágenes SDXL
    print("\n[3/8] Diseñando prompts visuales y renderizando 12 escenas compartidas en SDXL...")
    generar_secuencia_imagenes(narracion_visual, titulo_es, nombre_base=nombre_raiz, total_escenas=12)
    print("✔ Secuencia visual completada.")

    # 4. Síntesis de voz
    print("\n[4/8] Sintetizando voces en off con Edge-TTS...")
    ruta_audio_es = convertir_texto_a_voz(narracion_es, nombre_base=f"{nombre_raiz}_es", idioma="es")
    ruta_audio_en = convertir_texto_a_voz(narracion_en, nombre_base=f"{nombre_raiz}_en", idioma="en")

    clip_es = mp.AudioFileClip(str(ruta_audio_es))
    duracion_es = clip_es.duration
    clip_es.close()

    clip_en = mp.AudioFileClip(str(ruta_audio_en))
    duracion_en = clip_en.duration
    clip_en.close()

    print(f"✔ Audio [ES] listo: {duracion_es:.2f}s")
    print(f"✔ Audio [EN] listo: {duracion_en:.2f}s")

    # 5. Montaje de video
    print("\n[5/8] Montando videos base sincronizados con Ken Burns y música...")
    ruta_video_base_es = montar_video_final(f"{nombre_raiz}_es", duracion_es, idioma="es")
    ruta_video_base_en = montar_video_final(f"{nombre_raiz}_en", duracion_en, idioma="en")

    # 6. Quemado de subtítulos
    print("\n[6/8] Transcribiendo y quemando subtítulos con Whisper...")
    ruta_final_es = agregar_subtitulos_al_video(ruta_video_base_es, ruta_audio_es, idioma="es")
    ruta_final_en = agregar_subtitulos_al_video(ruta_video_base_en, ruta_audio_en, idioma="en")

    eliminar_copias_base_subtituladas(ruta_final_es)
    eliminar_copias_base_subtituladas(ruta_final_en)

    # 7. Metadatos
    print("\n[7/8] Generando metadatos para YouTube Shorts...")
    ruta_txt_es = generar_archivo_metadata(titulo_es, tema, f"{nombre_raiz}_es", idioma="es")
    ruta_txt_en = generar_archivo_metadata(titulo_en, tema, f"{nombre_raiz}_en", idioma="en")

    # 8. Historial
    registrar_tema_en_historial(tema, indice_cat)

    print("\n====================================================")
    print("🎉 ¡PRODUCCIÓN BILINGÜE COMPLETADA EXITOSAMENTE!")
    print("====================================================")
    print(f"🎯 Tema trabajado:   {tema}")
    print("\n📦 LA CAJA NEGRA (ESPAÑOL):")
    print(f"   🎬 Video:      {ruta_final_es.name}")
    print(f"   📝 Metadatos:  {ruta_txt_es.name}")
    print("\n📦 THE BLACK BOX ARCHIVES (ENGLISH):")
    print(f"   🎬 Video:      {ruta_final_en.name}")
    print(f"   📝 Metadatos:  {ruta_txt_en.name}")
    print("====================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())