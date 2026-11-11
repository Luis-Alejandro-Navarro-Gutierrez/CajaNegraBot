"""Pipeline de CajaNegraBot para producir videos documentales breves con Groq."""

import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import moviepy.editor as mp

# Módulos del pipeline
from generator import CIERRE_VIDEO, generar_guion, guardar_guion
from tts import convertir_texto_a_voz
from images import generar_secuencia_imagenes
from video import montar_video_final
from subtitles import agregar_subtitulos_al_video
from metadata import generar_archivo_metadata

# ========================================================
# DETECCIÓN DE RUTA PERSISTENTE (COMPATIBLE CON .EXE)
# ========================================================
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

HISTORIAL_FILE = BASE_DIR / "historial_temas.json"
load_dotenv(BASE_DIR / ".env")

CATEGORIAS = [
    {
        "id": "ciberseguridad_hackeos",
        "nombre": "HACKEOS LEGENDARIOS Y FALLOS TECNOLÓGICOS",
        "descripcion": (
            "Historias reales donde una sola persona o un código diminuto puso en jaque al mundo entero: "
            "adolescentes que burlaron al Pentágono desde su habitación, el virus que apagó centrifugadoras nucleares (Stuxnet), "
            "un silbato de cereal que permitía llamadas gratis infinitas o el bug de una línea que casi detiene satélites. "
            "El espectador debe pensar: '¿Cómo algo tan simple causó semejante caos?'."
        ),
    },
    {
        "id": "robos_fugas_audaces",
        "nombre": "ATRACOS IMPOSIBLES Y FUGAS DE PELÍCULA",
        "descripcion": (
            "Robos multimillonarios y escapes donde no se disparó una bala, sino pura astucia e ingenio: "
            "ladrones que vaciaron la bóveda de diamantes más blindada del mundo usando cinta y laca para cabello, "
            "hombres que se esfumaron de Alcatraz en balsas hechas de impermeables, o estafadores que vendieron "
            "la Torre Eiffel dos veces. El gancho debe ser la audacia del plan y el detalle absurdo que casi los delata."
        ),
    },
    {
        "id": "ciencia_limite_accidentes",
        "nombre": "CIENCIA EXTREMA, ACCIDENTES Y PARADOJAS",
        "descripcion": (
            "Experimentos reales que salieron terriblemente mal o fenómenos físicos que desafían el sentido común: "
            "el núcleo de plutonio ('Demon Core') manipulado con un simple destornillador plano, "
            "gotas de vidrio capaces de resistir un balazo pero que explotan si les tocas la cola, "
            "o qué le ocurre al cuerpo si tocas una gota de antimateria. Conceptos científicos complejos explicados "
            "para que cualquiera diga: '¿Cómo es físicamente posible que esto exista?'."
        ),
    },
    {
        "id": "naturaleza_anomalias_tierra",
        "nombre": "ANOMALÍAS DE LA TIERRA Y NATURALEZA MORTAL",
        "descripcion": (
            "Lugares y fenómenos geológicos tan extraños que parecen de ciencia ficción pero existen hoy en la Tierra: "
            "un lago que una noche liberó una nube invisible de gas y asfixió a pueblos enteros mientras dormían (Lago Nyos), "
            "un pueblo fantasma que lleva más de 60 años ardiendo bajo tierra (Centralia), o una cueva donde el calor "
            "y los cristales te cocinarían los pulmones en 15 minutos. El misterio de las trampas ocultas del planeta."
        ),
    },
    {
        "id": "biologia_parasitos_zombis",
        "nombre": "BIOLOGÍA PERTURBADORA Y CRIATURAS AL LÍMITE",
        "descripcion": (
            "Animales, hongos y parásitos reales con comportamientos tan aterradores que inspiraron películas: "
            "hongos que secuestran el cerebro de insectos y los convierten en zombis, ranas que se congelan por completo "
            "y resucitan semanas después, o peces abisales ciegos que devoran presas tres veces más grandes que ellos. "
            "Hechos biológicos 100% verídicos que provocan escalofríos y asombro inmediato."
        ),
    },
    {
        "id": "enigmas_medicos_psicologia",
        "nombre": "ENIGMAS MÉDICOS Y LOCURA COLECTIVA",
        "descripcion": (
            "Casos clínicos desconcertantes y eventos psicológicos documentados que la ciencia apenas pudo explicar: "
            "ciudades donde la gente empezó a bailar sin parar hasta colapsar, una escuela entera atrapada por un ataque "
            "incontrolable de risa que duró meses, o personas que tras un golpe despertaron hablando idiomas fluidos o "
            "tocando el piano sin haber tomado una sola clase. El cerebro humano fallando de formas inexplicables."
        ),
    },
    {
        "id": "expediciones_misterios_mar",
        "nombre": "MISTERIOS DOCUMENTADOS Y NAVÍOS FANTASMA",
        "descripcion": (
            "Casos con registros oficiales y bitácoras reales donde la tripulación se desvaneció en el aire: "
            "barcos encontrados a toda vela con la comida servida en la mesa y ni un solo tripulante a bordo (Mary Celeste), "
            "expediciones al Ártico donde hombres curtidos empezaron a perder el juicio por latas de comida contaminadas, "
            "o el último mensaje transmitido antes de que una embarcación desapareciera sin dejar rastro en el radar."
        ),
    },
    {
        "id": "supervivencia_inverosimil",
        "nombre": "SUPERVIVENCIA HUMANA CONTRA TODO PRONÓSTICO",
        "descripcion": (
            "Personas comunes que desafiaron a la muerte cuando la estadística decía que era imposible vivir: "
            "la mujer que cayó de un avión a 3.000 metros de altura atada a su asiento, cayó en la selva y caminó sola 10 días; "
            "el hombre que sobrevivió dentro de una burbuja de aire en un barco hundido a 30 metros bajo el mar por tres días; "
            "o náufragos que bebieron agua de lluvia y comieron tortugas para vencer al océano. Tensión pura de resistencia humana."
        ),
    },
    {
        "id": "absurdos_historicos_caos",
        "nombre": "ERRORES RIDÍCULOS QUE DESATARON EL CAOS",
        "descripcion": (
            "Momentos de la historia donde un malentendido infantil o una orden estúpida cambiaron el rumbo de países enteros: "
            "ejércitos enteros que entraron en pánico y se dispararon a sí mismos en la oscuridad por barriles de licor (Karánsebes), "
            "guerras oficiales declaradas por cerdos o cubos de madera, o la respuesta confusa de un funcionario en rueda de prensa "
            "que derribó el Muro de Berlín en una noche. Hechos cómicos pero con consecuencias gigantescas."
        ),
    },
    {
        "id": "inventos_accidentales_errores",
        "nombre": "ACCIDENTES Y EQUIVOCACIONES QUE CAMBIARON EL MUNDO",
        "descripcion": (
            "Las cosas que usas todos los días y que nacieron porque alguien arruinó un experimento: "
            "el científico que olvidó lavar un plato de bacterias y salvó millones de vidas con la penicilina; "
            "un chocolate derretido en el bolsillo que dio origen al horno microondas; o el químico que buscaba veneno "
            "y creó accidentalmente cerillas de fuego. El poder del error humano transformado en genialidad cotidiana."
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


def obtener_tema_automatico() -> tuple[str, int]:
    """Consulta a Groq rotando ordenadamente entre las 10 categorías."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    datos_historial = _cargar_datos_historial()
    temas_previos = datos_historial["temas"]

    # Rueda cíclica: pasa a la siguiente categoría obligatoria (0 a 9)
    nuevo_indice = (datos_historial["ultimo_indice_categoria"] + 1) % len(CATEGORIAS)
    categoria = CATEGORIAS[nuevo_indice]

    print(f"🔄 Rotación temática [{nuevo_indice + 1}/{len(CATEGORIAS)}]: {categoria['nombre']}")

    prompt = f"""
    Actúa como editor jefe de curiosidades reales y divulgación en videos cortos virales.
    Tu objetivo es proponer UNA curiosidad o hecho histórico/científico real con alto factor de sorpresa ("¿Cómo es posible que esto haya pasado?").

    CATEGORÍA OBLIGATORIA PARA ESTE VIDEO:
    {categoria['nombre']}
    Descripción del enfoque: {categoria['descripcion']}

    REGLAS DE EXCLUSIÓN TOTAL:
    - NO menciones soldados en trincheras, frentes de guerra, aviones bombarderos ni batallas de ejércitos.
    - El tema debe pertenecer estrictamente a la categoría asignada.

    Criterios de calidad:
    1. 100% verídico, comprobado y documentado (sin rumores ni leyendas urbanas).
    2. Debe contener un giro inesperado, un dilema o una revelación concreta.
    3. Fácil de entender para un público amplio en menos de 90 segundos.
    4. Prohibido repetir temas que ya estén en este historial:
    {json.dumps(temas_previos, ensure_ascii=False)}

    Devuelve ÚNICAMENTE el nombre claro del caso o la curiosidad. Sin comillas, sin introducciones ni explicaciones.
    """

    completion = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {
                "role": "system",
                "content": "Eres un editor jefe de contenido de divulgación especializado en curiosidades reales de ciencia, tecnología, atracos ingeniosos y naturaleza. Devuelves únicamente el título solicitado.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.6,
    )

    tema_propuesto = completion.choices[0].message.content.strip().replace('"', "").replace("'", "")
    return tema_propuesto, nuevo_indice


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
            copia_base.unlink()
            print(f"✔ Copia sin subtítulos eliminada: {copia_base.name}")


def main() -> int:
    print("==========================================")
    print("   🤖 CAJANEGRABOT - FÁBRICA DE SHORTS    ")
    print("==========================================")

    # 1. Obtener tema con rotación fija de categoría
    print("\n[1/7] Consultando un nuevo tema a Groq...")
    tema, indice_cat = obtener_tema_automatico()
    print(f'🎯 Tema seleccionado: "{tema}"')

    # 2. Generar Guion (~80 segundos: 180 - 200 palabras)
    print("\n[2/7] Generando guion oficial con Groq...")
    resultado_guion = generar_guion(tema, minimo=180, maximo=200)
    ruta_json = guardar_guion(resultado_guion)
    guion_data = resultado_guion["guion"]
    titulo_oficial = guion_data["titulo"]
    narracion_completa = guion_data["narracion"]
    narracion_visual = narracion_completa.removesuffix(" " + CIERRE_VIDEO).rstrip()
    print(f"✔ Guion listo: {titulo_oficial}")

    # 3. Sintetizar Audio (TTS)
    print("\n[3/7] Sintetizando voz en off con Álvaro...")
    nombre_base = ruta_json.stem
    ruta_audio = convertir_texto_a_voz(narracion_completa, nombre_base=nombre_base)

    audio_clip = mp.AudioFileClip(str(ruta_audio))
    duracion_voz = audio_clip.duration
    audio_clip.close()
    print(f"✔ Voz lista (Duración: {duracion_voz:.2f}s)")

    # 4. Generar Secuencia de 12 Imágenes con ComfyUI Local
    print("\n[4/7] Diseñando prompts con Groq y renderizando con ComfyUI...")
    generar_secuencia_imagenes(narracion_visual, titulo_oficial, nombre_base=nombre_base, total_escenas=12)
    print("✔ Secuencia de imágenes completada.")

    # 5. Montar Video Base con Animación Ken Burns
    print("\n[5/7] Montando video base sincronizado...")
    ruta_video_base = montar_video_final(nombre_base, duracion_voz)
    print("✔ Video base generado.")

    # 6. Quemar Subtítulos Automáticos con Whisper
    print("\n[6/7] Generando y quemando subtítulos dinámicos...")
    ruta_video_final = agregar_subtitulos_al_video(ruta_video_base, ruta_audio)
    if not ruta_video_final.exists():
        raise FileNotFoundError(f"No se generó el video final esperado: {ruta_video_final}")
    eliminar_copias_base_subtituladas(ruta_video_final)
    print("✔ Subtítulos quemados.")

    # 7. Metadatos y Registro
    print("\n[7/7] Generando archivo de metadatos y guardando historial...")
    ruta_txt = generar_archivo_metadata(titulo_oficial, tema, nombre_base)
    registrar_tema_en_historial(tema, indice_cat)

    print("\n==========================================")
    print("🎉 ¡PROCESO COMPLETADO EXITOSAMENTE!")
    print("==========================================")
    print(f"📌 Tema:         {tema}")
    print(f"⏱ Duración voz: {duracion_voz:.2f}s")
    print(f"📄 Guion JSON:   {ruta_json}")
    print(f"🎧 Audio:        {ruta_audio}")
    print(f"🎬 Video Final:  {ruta_video_final}")
    print(f"📝 Metadatos:    {ruta_txt}")
    print("==========================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())