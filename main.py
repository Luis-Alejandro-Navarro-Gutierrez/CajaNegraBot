"""Pipeline de CajaNegraBot para producir videos documentales breves bilingües (ES / EN)."""

import json
import os
import random
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

# ========================================================
# BANCO DE DISPARADORES HISTÓRICOS Y MODERNOS (SIGLOS XIX, XX Y XXI)
# ========================================================
ANGULOS_DISPARADORES = [
    # Época moderna y Siglo XXI
    "un delito o estafa millonaria con criptomonedas, NFTs o billeteras digitales arruinado por perder la clave o alardear en redes",
    "un criminal o ladrón moderno del siglo XXI delatado por el GPS de su celular, un reloj inteligente o una aspiradora robot",
    "un fraude corporativo reciente o robo informático en una startup tecnológica descubierto por una negligencia insólita",
    "un robo o asalto moderno frustrado porque el atacante no supo usar la tecnología (sensores biométricos, cerraduras electrónicas)",
    "un intento de hackeo, filtración o ciberataque reciente donde el atacante usó redes Wi-Fi públicas o cometió un descuido doméstico",
    "un creador de contenido, falso influencer o estafador digital moderno cuya mentira colapsó en vivo o por un descuido en un post",
    
    # Siglo XX e hitos históricos
    "un caso judicial o policial insólito ocurrido en Europa Occidental, Asia o Latinoamérica",
    "un suceso de espionaje o misión encubierta en la Guerra Fría arruinado por un malentendido ridículo",
    "un atraco a transportes blindados, trenes, barcos o aduanas con un plan maestro que falló en los últimos metros",
    "un error garrafal de falsificadores de arte, documentos o dinero que pasaron por alto un detalle infantil",
    "un intento de fuga de prisión de alta seguridad frustrado por un imprevisto doméstico o torpeza física",
    "un descubrimiento científico, médico o tecnológico accidental nacido de un error de laboratorio con final millonario",
    "un conflicto diplomático o movilización militar gigantesca desatada por comida, animales o motivos triviales"
]

# 7 Pilares Temáticos Reestructurados
CATEGORIAS = [
    {
        "id": "asesinatos_venganzas_fallidas",
        "nombre": "PLANES MACABROS Y VENGANZAS QUE SALIERON RIDÍCULAMENTE MAL",
        "descripcion": (
            "Criminales o conspiradores cuyos planes terminaron en comedia de enredos, autotrampas involuntarias, "
            "o blancos que resultaron imposibles de vencer por pura suerte o torpeza del atacante."
        ),
    },
    {
        "id": "robos_arruinados_estupidez",
        "nombre": "ROBOS MILLONARIOS ARRUINADOS POR DETALLES ABSURDOS",
        "descripcion": (
            "Asaltos a bancos, joyerías, museos, trenes o transporte blindado donde se burló la alta seguridad, "
            "pero los ladrones fueron atrapados por descuidos ridículos de sentido común o pistas tontas."
        ),
    },
    {
        "id": "hackeos_crimenes_digitales",
        "nombre": "HACKEOS, FRAUDES Y CRÍMENES TECNOLÓGICOS INSÓLITOS",
        "descripcion": (
            "Golpes cibernéticos y estafas informáticas desbaratadas por fallos ortográficos, contraseñas ridículas, "
            "descuidos domésticos de los hackers o registros de red insólitos."
        ),
    },
    {
        "id": "errores_anomalias_monumentales",
        "nombre": "ERRORES TONTOS Y ANOMALÍAS CON EFECTOS MONUMENTALES",
        "descripcion": (
            "Descuidos de laboratorio, fallos de traducción o accidentes de diseño que cambiaron la historia, "
            "crearon imperios comerciales o salvaron vidas de forma completamente imprevista."
        ),
    },
    {
        "id": "conflictos_leyes_absurdas",
        "nombre": "CONFLICTOS BÉLICOS, CRISIS Y LEYES POR MOTIVOS ABSURDOS",
        "descripcion": (
            "Movilizaciones militares, disputas diplomáticas o normas legales desmedidas desatadas por comida, "
            "animales, discusiones menores o incidentes territoriales ridículos."
        ),
    },
    {
        "id": "impostores_farsantes_alta_sociedad",
        "nombre": "IMPOSTORES Y FALSOS NOBLES QUE ENGAÑARON AL MUNDO",
        "descripcion": (
            "Sujetos sin un centavo que fingieron ser médicos, diplomáticos, aristócratas o generales, viviendo con lujos "
            "hasta que un detalle trivial o un encuentro fortuito reveló toda la farsa."
        ),
    },
    {
        "id": "fugas_prision_ridiculas",
        "nombre": "FUGAS DE PRISIÓN MILIMÉTRICAS QUE SE DERRUMBARON AL FINAL",
        "descripcion": (
            "Reclusos que planearon fugas ingeniosas y complejas por meses, pero terminaron atrapados en la puerta de salida "
            "por detalles absurdos como quedar atascados, tomar el transporte equivocado o festejar antes de tiempo."
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
    """Árbitro IA estricto: evalúa contra el 100% del historial sin recortes."""
    if not historial_temas:
        return False

    candidato_limpio = nuevo_candidato.strip().lower()
    for t in historial_temas:
        if candidato_limpio == t.strip().lower():
            return True

    # SE EVALÚA TODO EL HISTORIAL COMPLETO
    temas_referencia = "\n".join(f"- {t}" for t in historial_temas)

    prompt_juez = f"""
    Eres un árbitro editorial y verificador estricto para 'La Caja Negra'.
    Determina si la propuesta relata EL MISMO evento, hecho real o historia histórica/moderna que cualquiera de los casos ya tratados.

    PROPUESTA A EVALUAR:
    "{nuevo_candidato}"

    HISTORIAL COMPLETO DE CASOS YA TRATADOS:
    {temas_referencia}

    CRITERIOS DE DESCARTE:
    - Responde DUPLICADO si es la misma historia real (incluso si cambia el título, los nombres de los adjetivos o el enfoque).
    - Responde NUEVO si es un hecho, protagonista o evento completamente diferente que nunca antes ha sido tratado en el historial.

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
            max_completion_tokens=20,
            extra_body={"reasoning_effort": "low"},
        )
        veredicto = verificacion.choices[0].message.content.strip().upper()
        return "DUPLICADO" in veredicto
    except Exception as e:
        print(f"⚠️ Error consultando árbitro IA: {e}")
        return False


def obtener_tema_automatico(max_intentos: int = 6) -> tuple[str, int]:
    """Consulta a Groq rotando ordenadamente y usando disparadores dinámicos contra TODO el historial."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    datos_historial = _cargar_datos_historial()
    temas_previos = datos_historial["temas"]

    nuevo_indice = (datos_historial["ultimo_indice_categoria"] + 1) % len(CATEGORIAS)
    categoria = CATEGORIAS[nuevo_indice]

    print(f"🔄 Rotación temática [{nuevo_indice + 1}/{len(CATEGORIAS)}]: {categoria['nombre']}")
    print(f"📚 Verificando contra {len(temas_previos)} casos históricos registrados (100% del historial)...")

    # TODO EL HISTORIAL COMPLETO
    lista_historial_prompt = "\n".join(f"- {t}" for t in temas_previos) if temas_previos else "Ninguno"

    tema_candidato_final = ""
    for intento in range(max_intentos):
        angulo_elegido = random.choice(ANGULOS_DISPARADORES)

        prompt_generador = f"""
        Actúa como investigador y productor de historias virales para el canal 'La Caja Negra'.
        Tu misión es proponer UN caso real, específico y comprobado que despierte asombro inmediato ("¿Cómo pudieron hacer semejante tontería?").

        CATEGORÍA OBLIGATORIA:
        {categoria['nombre']}
        Contexto: {categoria['descripcion']}

        ENFOQUE ESPECÍFICO REQUERIDO:
        Busca un caso verídico relacionado con: {angulo_elegido}.

        REGLAS DE SELECCIÓN:
        1. El caso debe ser 100% REAL y documentado (con personas, lugares y hechos comprobables). Tanto casos del siglo XXI como históricos son válidos.
        2. Evita los casos más trillados de internet (ej. el robo de Amberes, la pizza bomba, el typo de Bangladesh, Michael Malloy). Ve por sucesos increíbles pero poco explotados.
        3. Resalta la ironía o la torpeza: qué planearon y la estupidez exacta por la que todo se fue al traste.
        4. ESTRICTAMENTE PROHIBIDO REPETIR O PARAFRASEAR CUALQUIERA DE ESTOS CASOS YA TRATADOS:
        {lista_historial_prompt}

        Devuelve ÚNICAMENTE un título corto, directo y con gancho magnético (estilo YouTube / TikTok).
        Sin comillas, sin introducciones ni notas.
        """

        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un editor de historias virales insólitas. Propones solo títulos directos de sucesos reales asombrosos y cómicos.",
                },
                {"role": "user", "content": prompt_generador},
            ],
            temperature=0.8 + (intento * 0.04),
            max_completion_tokens=150,
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

        print(f"⚠️ El árbitro IA detectó que '{tema_candidato}' ya existe en el historial completo. Explorando otro ángulo ({intento + 1}/{max_intentos})...")
        tema_candidato_final = tema_candidato

    return (tema_candidato_final if tema_candidato_final else "El robo arruinado por una alarma Bluetooth"), nuevo_indice


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
    print("\n[1/8] Consultando un nuevo tema inédito con disparadores dinámicos...")
    tema, indice_cat = obtener_tema_automatico()
    print(f'🎯 Tema seleccionado: "{tema}"')

    # 2. Generar Guiones (Calibrados en generator.py a 180-205 palabras para durar 1:10 - 1:20 min)
    print("\n[2/8] Generando y adaptando guiones con Groq...")
    resultado_guion_es = generar_guion(tema, minimo=180, maximo=205)
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
    print("\n[3/8] Diseñando prompts visuales con esquema 3-3-3-3 y renderizando 12 escenas...")
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