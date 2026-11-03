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
        "id": "tech_hackeos",
        "nombre": "TECNOLOGÍA, CIBERSEGURIDAD Y HACKEOS HISTÓRICOS",
        "descripcion": "Ciberataques pioneros, virus míticos (Stuxnet, gusano Morris), phreaking telefónico con silbatos, bugs de software catastróficos o fallos de satélites y telecomunicaciones. Prohibido temas de guerras o tanques.",
    },
    {
        "id": "robos_fugas",
        "nombre": "ROBOS LEGENDARIOS, FUGAS Y FRAUDES INGENIOSOS",
        "descripcion": "Atracos a bóvedas impenetrables (como Amberes), escapes históricos imposibles (D.B. Cooper, fuga de Alcatraz), o estafadores audaces que engañaron a imperios enteros mediante pura ingeniería social.",
    },
    {
        "id": "ciencia_limite",
        "nombre": "CIENCIA EXTREMA, ACCIDENTES Y PARADOJAS FÍSICAS",
        "descripcion": "Incidentes con radiación, experimentos científicos al límite de la catástrofe, gotas del príncipe Rupert, el efecto Leidenfrost o descubrimientos de laboratorio con giros inesperados.",
    },
    {
        "id": "naturaleza_anomalias",
        "nombre": "NATURALEZA MORTAL Y FENÓMENOS GEOLÓGICOS EXTRAÑOS",
        "descripcion": "Lagos que asfixian pueblos con gases invisibles (Lago Nyos), la cueva de los cristales gigantes de Naica, fuegos subterráneos eternos (Centralia), o agujeros y anomalías geológicas terrestres.",
    },
    {
        "id": "biologia_parasitos",
        "nombre": "RAREZAS BIOLÓGICAS Y PARÁSITOS FASCINANTES",
        "descripcion": "Organismos zombificadores (Cordyceps), criaturas abisales con habilidades desconcertantes, defensas químicas extremas del reino animal o animales con adaptaciones que desafían la biología estándar.",
    },
    {
        "id": "psicologia_enigmas_medicos",
        "nombre": "PSICOLOGÍA COLECTIVA Y ENIGMAS MÉDICOS REALES",
        "descripcion": "Histerias colectivas documentadas (la epidemia de baile de 1518, la risa de Tanganica), personas inmunes a condiciones letales o casos clínicos y neurológicos que dejaron perpleja a la medicina.",
    },
    {
        "id": "misterios_expediciones",
        "nombre": "MISTERIOS DOCUMENTADOS Y EXPEDICIONES ENIGMÁTICAS",
        "descripcion": "Barcos hallados a la deriva sin tripulación (Mary Celeste), la lluvia biológica de Oakville, artefactos arqueológicos anacrónicos comprobados o expediciones de exploración con enigmas no resueltos.",
    },
    {
        "id": "supervivencia_humana",
        "nombre": "SUPERVIVENCIA EXTREMA CONTRA TODO PRONÓSTICO",
        "descripcion": "Hazañas inverosímiles de resistencia humana: náufragos que pasaron meses en altamar, personas que cayeron de aviones sin paracaídas y sobrevivieron, o rescates en cuevas y simas profundas.",
    },
    {
        "id": "absurdos_historicos",
        "nombre": "DECISIONES ABSURDAS Y PARADOJAS HISTÓRICAS",
        "descripcion": "Leyes extravagantes de imperios antiguos, disputas territoriales que se resolvieron de forma ridícula, impuestos insólitos o eventos históricos oficiales donde un malentendido minúsculo causó caos general.",
    },
    {
        "id": "inventos_accidentales",
        "nombre": "INVENTOS REVOLUCIONARIOS SURGIDOS POR ERROR",
        "descripcion": "Grandes inventos nacidos de accidentes y fallos de laboratorio (la penicilina, el horno microondas, el teflón, la dinamita, el marcapasos), donde un tropiezo cambió la vida moderna por completo.",
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