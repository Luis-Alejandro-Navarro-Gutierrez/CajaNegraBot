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
    # En modo --onefile, sys.executable está en .../dist/CajaNegra_Studio.exe
    BASE_DIR = Path(sys.executable).resolve().parent.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

os.chdir(str(BASE_DIR))
os.environ["CAJANEGRA_ROOT"] = str(BASE_DIR)

HISTORIAL_FILE = BASE_DIR / "historial_temas.json"
load_dotenv(BASE_DIR / ".env")

# Módulos del pipeline actualizados
from generator import CIERRE_VIDEO_ES, CIERRE_VIDEO_EN, generar_guion, traducir_guion_a_ingles, guardar_guion
from tts import convertir_texto_a_voz
from images import generar_secuencia_imagenes
from video import montar_video_final
from subtitles import agregar_subtitulos_al_video
from metadata import generar_archivo_metadata

CATEGORIAS = [
    {
        "id": "ciberseguridad_hackeos",
        "nombre": "HACKEOS LEGENDARIOS Y FALLOS TECNOLÓGICOS",
        "descripcion": (
            "Sucesos donde un fallo de código, un error técnico diminuto o un ciberataque puso en jaque infraestructuras, "
            "bancos o corporaciones enteras. Abarca tanto los orígenes informáticos (bugs pioneros, phreaking) como "
            "incidentes contemporáneos de alto impacto del siglo XXI (BlackEnergy, Stuxnet, apagones masivos por parches fallidos)."
        ),
    },
    {
        "id": "absurdos_historicos_caos",
        "nombre": "ERRORES RIDÍCULOS QUE DESATARON EL CAOS",
        "descripcion": (
            "Momentos donde un malentendido infantil, una orden mal redactada o un descuido involuntario cambiaron la historia. "
            "Desde la antigüedad o la edad media hasta meteduras de pata del siglo XX y XXI con consecuencias geopolíticas, económicas o sociales grotescas."
        ),
    },
    {
        "id": "ciencia_limite_accidentes",
        "nombre": "CIENCIA EXTREMA, ACCIDENTES Y PARADOJAS",
        "descripcion": (
            "Experimentos al límite, incidentes en laboratorios documentados y fenómenos físicos desconcertantes. "
            "Desde radiación y reacciones críticas (Demon Core, SL-1) hasta eventos recientes en aceleradores de partículas contemporáneos, "
            "antimateria, o materiales que retan las leyes de la física cotidiana."
        ),
    },
    {
        "id": "supervivencia_inverosimil",
        "nombre": "SUPERVIVENCIA HUMANA CONTRA TODO PRONÓSTICO",
        "descripcion": (
            "Personas comunes que escaparon de la muerte cuando la estadística marcaba cero posibilidades: caídas libres extremas, "
            "encierros involuntarios en hábitats hostiles, aislamiento prolongado o naufragios documentados tanto históricos como de décadas recientes."
        ),
    },
    {
        "id": "robos_fugas_audaces",
        "nombre": "ATRACOS IMPOSIBLES Y FUGAS DE PELÍCULA",
        "descripcion": (
            "Golpes multimillonarios, robos de guante blanco y fugas donde la clave fue el ingenio técnico, la paciencia y la estrategia. "
            "Atracos clásicos de bóvedas blindadas, túneles de alta ingeniería contemporáneos o fugas carcelarias que burlaron sistemas de máxima seguridad."
        ),
    },
    {
        "id": "biologia_parasitos_zombis",
        "nombre": "BIOLOGÍA PERTURBADORA Y CRIATURAS AL LÍMITE",
        "descripcion": (
            "Parásitos, hongos, insectos y animales con adaptaciones evolutivas tan extremas o aterradoras que inspiraron el cine de terror. "
            "Manipulación de conducta de huéspedes, supervivencia en fosas abisales o defensas químicas 100% comprobadas por biólogos."
        ),
    },
    {
        "id": "inventos_accidentales_errores",
        "nombre": "ACCIDENTES Y EQUIVOCACIONES QUE CAMBIARON EL MUNDO",
        "descripcion": (
            "Herramientas, tecnologías, medicinas y productos de consumo universal que surgieron porque alguien arruinó un experimento "
            "o buscaba algo totalmente opuesto. La serendipia humana transformada en impacto global."
        ),
    },
    {
        "id": "enigmas_medicos_psicologia",
        "nombre": "ENIGMAS MÉDICOS Y LOCURA COLECTIVA",
        "descripcion": (
            "Casos clínicos desconcertantes documentados en la literatura médica, brotes de histeria o trastornos psicogénicos colectivos, "
            "y síndromes neuropsicológicos inexplicables tanto de épocas pasadas como registrados en hospitales contemporáneos."
        ),
    },
    {
        "id": "naturaleza_anomalias_tierra",
        "nombre": "ANOMALÍAS DE LA TIERRA Y NATURALEZA MORTAL",
        "descripcion": (
            "Lugares letales, fosas tóxicas, incendios subterráneos perpetuos y trampas geológicas activas en el planeta que parecen ficción "
            "pero existen hoy. El peligro oculto en la geología terrestre."
        ),
    },
    {
        "id": "misterios_enigmas_documentados",
        "nombre": "MISTERIOS Y ENIGMAS DOCUMENTADOS",
        "descripcion": (
            "Casos con expedientes policiales oficiales, bitácoras gubernamentales o registros científicos que desafían la lógica: "
            "desapariciones terrestres o aéreas inexplicadas, transmisiones de radio fantasma captadas por antenas internacionales, "
            "mensajes o manuscritos cifrados que nadie ha logrado romper, y expediciones oficiales donde el desenlace sigue sin respuesta documentada."
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
    Evalúa si la siguiente propuesta de video trata sobre EL MISMO evento, hecho, experimento o historia real que cualquiera de los casos en el historial.

    PROPUESTA A EVALUAR:
    "{nuevo_candidato}"

    HISTORIAL DE TEMAS YA TRATADOS:
    {temas_referencia}

    Criterios:
    - Responde DUPLICADO si es la misma historia (aunque cambien las palabras, idioma, o se use un nombre corto como 'Demon Core' frente a 'El Núcleo Demonio').
    - Responde NUEVO si es un evento, experimento o descubrimiento diferente, aunque pertenezca a la misma disciplina.

    Responde ÚNICAMENTE con una sola palabra: 'DUPLICADO' o 'NUEVO'.
    """

    try:
        verificacion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "Eres un árbitro editorial estricto. Respondes únicamente DUPLICADO o NUEVO."},
                {"role": "user", "content": prompt_juez},
            ],
            temperature=0.0,
            max_tokens=10,
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
    Actúa como editor jefe de curiosidades reales y divulgación en videos cortos virales.
    Tu objetivo es proponer UNA curiosidad o hecho histórico/científico real con alto factor de sorpresa ("¿Cómo es posible que esto haya ocurrido?").

    CATEGORÍA OBLIGATORIA PARA ESTE VIDEO:
    {categoria['nombre']}
    Descripción del enfoque: {categoria['descripcion']}

    REGLAS DE EQUILIBRIO TEMPORAL Y SELECCIÓN:
    - Alterna libremente entre hitos de la historia clásica y sucesos contemporáneos/actuales (décadas de 1990, 2000, 2010 y siglo XXI). No te limites únicamente al siglo XIX ni a la Guerra Fría.
    - NO menciones soldados en trincheras, frentes bélicos, aviones de combate bombarderos ni batallas de ejércitos.
    - EL TEMA DEBE SER COMPLETAMENTE INÉDITO Y DIFERENTE A ESTE HISTORIAL COMPLETO:
    {lista_historial_prompt}

    Criterios de calidad:
    1. 100% verídico, comprobado y documentado por fuentes oficiales o científicas.
    2. Debe contener un giro inesperado, un dilema técnico o una revelación impactante.
    3. Fácil de entender para un público amplio en menos de 90 segundos.
    4. Elige historias poco trilladas, evitando clichés desgastados en internet.

    Devuelve ÚNICAMENTE el nombre claro del caso o la curiosidad. Sin comillas, sin introducciones ni explicaciones.
    """

    tema_candidato_final = ""
    for intento in range(max_intentos):
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un editor de divulgación. Propones únicamente curiosidades documentadas inéditas, respetando los temas vetados.",
                },
                {"role": "user", "content": prompt_generador},
            ],
            temperature=0.85,
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

    return (tema_candidato_final if tema_candidato_final else "Curiosidad Inédita Documentada"), nuevo_indice


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

    # 1. Obtener tema con rotación fija de categoría y validación semántica inteligente
    print("\n[1/8] Consultando un nuevo tema inédito a Groq...")
    tema, indice_cat = obtener_tema_automatico()
    print(f'🎯 Tema seleccionado: "{tema}"')

    # 2. Generar Guiones (Español e Inglés)
    print("\n[2/8] Generando y adaptando guiones con Groq...")
    resultado_guion_es = generar_guion(tema, minimo=180, maximo=200)
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

    # Guardar ambos archivos JSON
    ruta_json_es = guardar_guion(resultado_guion_es, sufijo="_es")
    ruta_json_en = guardar_guion(resultado_guion_en, sufijo="_en")
    nombre_raiz = ruta_json_es.stem.removesuffix("_es")
    print(f"✔ Guion [ES]: {titulo_es}")
    print(f"✔ Script [EN]: {titulo_en}")

    # 3. Generar Secuencia de 12 Imágenes con ComfyUI (Compartidas)
    print("\n[3/8] Diseñando prompts visuales y renderizando 12 escenas compartidas en SDXL...")
    generar_secuencia_imagenes(narracion_visual, titulo_es, nombre_base=nombre_raiz, total_escenas=12)
    print("✔ Secuencia visual completada.")

    # 4. Sintetizar Audios (TTS Álvaro [ES] y Christopher [EN])
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

    # 5. Montar Videos Base
    print("\n[5/8] Montando videos base sincronizados con Ken Burns y música...")
    ruta_video_base_es = montar_video_final(f"{nombre_raiz}_es", duracion_es, idioma="es")
    ruta_video_base_en = montar_video_final(f"{nombre_raiz}_en", duracion_en, idioma="en")

    # 6. Quemar Subtítulos Dinámicos con Whisper
    print("\n[6/8] Transcribiendo y quemando subtítulos con Whisper...")
    ruta_final_es = agregar_subtitulos_al_video(ruta_video_base_es, ruta_audio_es, idioma="es")
    ruta_final_en = agregar_subtitulos_al_video(ruta_video_base_en, ruta_audio_en, idioma="en")

    eliminar_copias_base_subtituladas(ruta_final_es)
    eliminar_copias_base_subtituladas(ruta_final_en)

    # 7. Metadatos de Publicación
    print("\n[7/8] Generando metadatos para YouTube Shorts...")
    ruta_txt_es = generar_archivo_metadata(titulo_es, tema, f"{nombre_raiz}_es", idioma="es")
    ruta_txt_en = generar_archivo_metadata(titulo_en, tema, f"{nombre_raiz}_en", idioma="en")

    # 8. Registro en Historial
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