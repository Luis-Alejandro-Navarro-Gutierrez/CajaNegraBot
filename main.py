"""Pipeline principal de CajaNegraBot para producción automatizada de Shorts bilingües.

Formato del canal: "¿Sabías que...?" (hackeos, robos, crímenes, ciencia, universo,
planeta, orígenes de las cosas, desastres, etc.).

Garantías de selección de tema:
  * Se consulta el 100% de historial_temas.json (filtro local + árbitro IA por lotes).
  * La categoría rota: nunca se repite una de las últimas categorías usadas.
  * Cada ejecución mezcla época, región y ángulo distintos para forzar variedad.
"""

import json
import os
import random
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

import moviepy.editor as mp
from dotenv import load_dotenv
from groq import Groq

from generator import generar_guion, traducir_guion_a_ingles
from images import generar_secuencia_imagenes
from metadata import generar_archivo_metadata
from subtitles import agregar_subtitulos_al_video
from tts import convertir_texto_a_voz
from video import montar_video_final

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
MODELO_GROQ = "openai/gpt-oss-120b"
TAMANO_LOTE_ARBITRO = 150  # títulos del historial por consulta al árbitro IA

# ========================================================
# DOMINIOS TEMÁTICOS DEL CANAL "¿SABÍAS QUE...?"
# ========================================================
DOMINIOS = [
    {
        "dominio": "HACKEOS Y CIBERDELITOS REALES",
        "guia": "hackeos históricos, virus y gusanos informáticos famosos, fraudes digitales, intrusiones a sistemas, estafas con tarjetas, fallos de software con consecuencias reales, phreakers y hackers adolescentes",
    },
    {
        "dominio": "ROBOS, ATRACOS Y GOLPES MAESTROS",
        "guia": "atracos a bancos y museos, robos de joyas, golpes con túneles, ladrones ingeniosos, robos de obras de arte, fugas carcelarias espectaculares",
    },
    {
        "dominio": "ASESINOS Y CASOS CRIMINALES DOCUMENTADOS",
        "guia": "asesinos en serie, envenenadores, enfermeros o médicos que mataron a pacientes, crímenes resueltos por ciencia forense, casos que cambiaron las leyes, detectives que atraparon a criminales por un detalle mínimo",
        "tono": "Enfoque informativo y forense, basado en hechos judicialmente documentados. Sin morbo ni detalles gráficos.",
    },
    {
        "dominio": "FRAUDES, ESTAFAS Y FARSANTES",
        "guia": "impostores famosos, estafadores de alto nivel, falsificadores, pirámides y burbujas especulativas, falsos médicos o nobles, engaños masivos que funcionaron",
    },
    {
        "dominio": "CIENCIA Y EXPERIMENTOS EXTRAÑOS",
        "guia": "descubrimientos accidentales, experimentos famosos que salieron mal o fueron polémicos, propiedades raras de materiales, científicos excéntricos, fenómenos físicos o químicos contraintuitivos",
    },
    {
        "dominio": "UNIVERSO Y ESPACIO",
        "guia": "misiones espaciales con fallos absurdos, objetos astronómicos extremos, señales misteriosas, astronautas en situaciones límite, descubrimientos cósmicos inesperados, basura espacial",
    },
    {
        "dominio": "PLANETA TIERRA Y FENÓMENOS NATURALES",
        "guia": "lugares extremos del planeta, fenómenos naturales raros, lagos o ríos que cambian de color, animales y plantas con capacidades insólitas, volcanes, cuevas y desiertos con historias increíbles",
    },
    {
        "dominio": "CÓMO SE CREARON LAS COSAS",
        "guia": "origen e invención de objetos cotidianos, inventos nacidos por error, cómo se fabrica algo sorprendente, historia de alimentos, juguetes, medicinas y tecnologías de uso diario",
    },
    {
        "dominio": "CÓMO SURGIERON LAS COSAS",
        "guia": "origen de costumbres, palabras, supersticiones, deportes, festividades, símbolos, profesiones y tradiciones; cómo empezó algo que hoy damos por normal",
    },
    {
        "dominio": "DESASTRES Y ACCIDENTES: CÓMO PASAN LAS COSAS",
        "guia": "accidentes industriales, explosiones, naufragios, fallos de ingeniería, errores humanos que provocaron catástrofes, cadenas de errores mínimos con consecuencias enormes",
    },
    {
        "dominio": "MEDICINA, CUERPO HUMANO Y MENTE",
        "guia": "tratamientos del pasado absurdos o peligrosos, casos médicos únicos, curiosidades del cuerpo humano, experimentos psicológicos famosos, enfermedades raras documentadas",
    },
    {
        "dominio": "GUERRA, ESPIONAJE Y ABSURDOS HISTÓRICOS",
        "guia": "espías y operaciones secretas reales, conflictos causados por motivos ridículos, armas y planes disparatados, expediciones desastrosas, decisiones políticas insólitas",
    },
]

# La época se elige en dos grupos equilibrados y se registra en el historial:
# así el modelo no puede quedarse sesgado hacia los siglos XVIII/XIX.
EPOCAS_HISTORICAS = [
    ("antes de 1800", 1, 1799),
    ("siglo XIX (1800-1899)", 1800, 1899),
    ("primera mitad del siglo XX (1900-1949)", 1900, 1949),
    ("segunda mitad del siglo XX (1950-1999)", 1950, 1999),
]
ANIO_ACTUAL = date.today().year
EPOCAS_SIGLO_XXI = [
    ("años 2000-2009", 2000, 2009),
    ("años 2010-2019", 2010, 2019),
    (f"años 2020-{ANIO_ACTUAL}", 2020, ANIO_ACTUAL),
]
REGIONES = [
    "Latinoamérica",
    "Asia",
    "Europa del Este",
    "África o Medio Oriente",
    "Estados Unidos",
    "Europa occidental",
    "Oceanía o regiones remotas",
    "cualquier lugar del mundo (prioriza el menos conocido)",
]
ANGULOS = [
    "un caso poco conocido pero con evidencia sólida",
    "un dato que parezca mentira pero sea comprobable",
    "una consecuencia absurda de un error pequeño",
    "el origen sorprendente de algo cotidiano",
    "un récord, un primero o un único en la historia",
    "un giro final inesperado",
]

STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "en", "que", "y", "o", "a",
    "por", "con", "para", "su", "sus", "como", "sobre", "se", "lo", "le", "les", "es", "fue", "era",
    "sin", "tras", "entre", "ante", "hasta", "desde", "cuando", "donde", "este", "esta", "esto",
    "mas", "pero", "sus", "hizo", "hacia", "cual", "quien", "todo", "toda", "muy",
}
# Palabras demasiado comunes en títulos: no cuentan como coincidencia por sí solas
GENERICAS = {
    "historia", "primero", "primera", "segundo", "primer", "ciudad", "mundo", "guerra", "hombre", "mujer",
    "banco", "robo", "muerte", "caso", "anos", "siglo", "real", "verdadera", "secreto", "increible",
    "insolito", "extrano", "famoso", "famosa", "gente", "personas", "persona", "dia", "noche", "vida",
    "tiempo", "lugar", "nunca", "mismo", "nuevo", "nueva", "gran", "grande", "murio", "mato", "logro",
    "descubrio", "conocido", "inventor", "cientifico", "ladron", "asesino", "hacker", "pais", "pueblo",
    "accidente", "error", "plan", "forma", "manera", "origen", "como", "porque", "cuando", "toda",
}


# ========================================================
# HISTORIAL
# ========================================================
def _cargar_datos_historial() -> dict:
    """Carga el historial completo. Si el archivo está corrupto NO lo sobrescribe: lo respalda y aborta."""
    if not ARCHIVO_HISTORIAL.exists():
        datos_iniciales = {"ultimo_indice_categoria": -1, "categorias_recientes": [], "temas": []}
        _escribir_json_atomico(datos_iniciales)
        return datos_iniciales

    try:
        raw = ARCHIVO_HISTORIAL.read_text(encoding="utf-8").replace("\u0000", "")
        data = json.loads(raw)
    except Exception as e:
        respaldo = ARCHIVO_HISTORIAL.with_suffix(".corrupto.bak")
        shutil.copy2(ARCHIVO_HISTORIAL, respaldo)
        raise RuntimeError(
            f"historial_temas.json está ilegible ({e}). Se guardó una copia en '{respaldo.name}'. "
            "Corrígelo antes de continuar para no perder el historial ni repetir temas."
        ) from e

    if not isinstance(data, dict):
        raise RuntimeError("historial_temas.json tiene un formato inesperado (se esperaba un objeto JSON).")

    temas_limpios, vistos = [], set()
    for t in data.get("temas", []):
        if isinstance(t, str) and t.strip() and t.strip().lower() not in vistos:
            vistos.add(t.strip().lower())
            temas_limpios.append(t.strip())
    data["temas"] = temas_limpios
    data.setdefault("ultimo_indice_categoria", -1)
    data.setdefault("categorias_recientes", [])
    data.setdefault("epocas_recientes", [])
    return data


def _escribir_json_atomico(datos: dict) -> None:
    """Escribe en un archivo temporal y lo reemplaza, para no dejar el historial a medias."""
    tmp = ARCHIVO_HISTORIAL.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, ARCHIVO_HISTORIAL)


def _guardar_tema_en_historial(tema: str, indice_categoria: int, epoca: str | None = None) -> None:
    """Registra el tema procesado, la categoría y, si es automático, la época."""
    datos = _cargar_datos_historial()
    if tema.strip().lower() not in {t.lower() for t in datos["temas"]}:
        datos["temas"].append(tema.strip())
    if epoca:
        datos["epocas_recientes"].append(epoca)
        datos["epocas_recientes"] = datos["epocas_recientes"][-20:]
    if 0 <= indice_categoria < len(DOMINIOS):
        datos["ultimo_indice_categoria"] = indice_categoria
        datos["categorias_recientes"].append(DOMINIOS[indice_categoria]["dominio"])
        datos["categorias_recientes"] = datos["categorias_recientes"][-60:]
    _escribir_json_atomico(datos)


# ========================================================
# DETECCIÓN DE DUPLICADOS
# ========================================================
def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _raiz(palabra: str) -> str:
    """Quita la 's' final para que 'robos' y 'robo' coincidan."""
    return palabra[:-1] if len(palabra) > 4 and palabra.endswith("s") else palabra


def _huella_tema(texto: str) -> dict:
    """Devuelve las palabras significativas y las posibles entidades (nombres propios) de un título."""
    palabras_orig = re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ]+", texto)
    significativas, entidades = set(), set()
    for i, p in enumerate(palabras_orig):
        norm = _raiz(_sin_acentos(p.lower()))
        if len(norm) <= 2 or norm in STOPWORDS:
            continue
        if norm not in GENERICAS:
            significativas.add(norm)
            if i > 0 and p[0].isupper() and len(norm) >= 5:
                entidades.add(norm)
    return {"sig": significativas, "ent": entidades}


def _construir_indice(historial: list[str]) -> list[tuple[str, dict]]:
    return [(h, _huella_tema(h)) for h in historial]


def _buscar_coincidencia_local(tema: str, indice: list[tuple[str, dict]]) -> str | None:
    """Compara el tema contra TODO el historial. Devuelve el título coincidente o None."""
    huella = _huella_tema(tema)
    for original, h in indice:
        comunes = huella["sig"] & h["sig"]
        entidades_comunes = huella["ent"] & h["ent"]
        union = huella["sig"] | h["sig"]
        jaccard = len(comunes) / len(union) if union else 0.0
        if len(comunes) >= 3 or entidades_comunes or (len(comunes) >= 2 and jaccard >= 0.4):
            print(f"🛑 Filtro local: '{tema}' ~ '{original}' (comunes: {comunes or entidades_comunes})")
            return original
    return None


def _arbitro_ia_duplicado(client: Groq, tema: str, historial: list[str]) -> bool:
    """Pregunta a la IA, por lotes, si el tema trata el mismo hecho que algo del historial COMPLETO."""
    for inicio in range(0, len(historial), TAMANO_LOTE_ARBITRO):
        lote = historial[inicio:inicio + TAMANO_LOTE_ARBITRO]
        prompt = f"""
Eres el editor en jefe del canal '¿Sabías que...?'.
Compara el TEMA PROPUESTO con este bloque del historial del canal.

TEMA PROPUESTO:
"{tema}"

HISTORIAL (bloque):
{json.dumps(lote, ensure_ascii=False)}

Responde DUPLICADO si el tema trata del mismo hecho real, personaje, lugar, caso u objeto
que algún título del bloque (aunque esté redactado distinto).
Responde NUEVO si es un hecho distinto.
Responde ÚNICAMENTE con la palabra DUPLICADO o NUEVO.
"""
        respuesta = None
        for _ in range(2):  # un reintento por lote
            try:
                completion = client.chat.completions.create(
                    model=MODELO_GROQ,
                    messages=[
                        {"role": "system", "content": "Responde estrictamente DUPLICADO o NUEVO."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.0,
                    max_completion_tokens=300,  # margen para el razonamiento interno del modelo
                    extra_body={"reasoning_effort": "low"},
                )
                respuesta = (completion.choices[0].message.content or "").strip().upper()
                if respuesta:
                    break
            except Exception as e:
                print(f"⚠️ Árbitro IA (lote {inicio // TAMANO_LOTE_ARBITRO + 1}): {e}")

        if respuesta is None or not respuesta:
            print(f"⚠️ Árbitro sin respuesta en el lote {inicio // TAMANO_LOTE_ARBITRO + 1}; "
                  "se confía en el filtro local para ese bloque.")
            continue

        if "DUPLICADO" in respuesta:
            print(f"🛑 Árbitro IA: '{tema}' rechazado por coincidencia con el historial.")
            return True
    return False


# ========================================================
# SELECCIÓN DE TEMA
# ========================================================
def _elegir_dominio(datos: dict, excluir: set[int] | None = None) -> int:
    """Rota las categorías: evita las usadas recientemente y prefiere las menos usadas."""
    excluir = excluir or set()
    recientes = datos.get("categorias_recientes", [])
    ventana = min(len(DOMINIOS) // 2, 5)
    bloqueados = set(recientes[-ventana:])
    uso = Counter(recientes[-len(DOMINIOS) * 3:])

    candidatos = [
        i for i, d in enumerate(DOMINIOS)
        if d["dominio"] not in bloqueados and i not in excluir
    ] or [i for i in range(len(DOMINIOS)) if i not in excluir]

    menor_uso = min(uso[DOMINIOS[i]["dominio"]] for i in candidatos)
    pool = [i for i in candidatos if uso[DOMINIOS[i]["dominio"]] == menor_uso]
    return random.choice(pool)


def _elegir_epoca(datos: dict) -> tuple[str, int, int]:
    """Equilibra los episodios históricos y los del siglo XXI según el historial."""
    recientes = datos.get("epocas_recientes", [])[-10:]
    modernas = sum(epoca in {e[0] for e in EPOCAS_SIGLO_XXI} for epoca in recientes)
    historicas = sum(epoca in {e[0] for e in EPOCAS_HISTORICAS} for epoca in recientes)

    if modernas < historicas:
        grupo = EPOCAS_SIGLO_XXI
    elif historicas < modernas:
        grupo = EPOCAS_HISTORICAS
    elif not recientes:
        # Empieza con un caso actual; las siguientes producciones compensan el balance.
        grupo = EPOCAS_SIGLO_XXI
    else:
        grupo = random.choice((EPOCAS_HISTORICAS, EPOCAS_SIGLO_XXI))
    return random.choice(grupo)


def _limpiar_titulo(linea: str) -> str:
    linea = re.sub(r"^[\-\*\u2022\d\.\)\s]+", "", linea.strip())
    return linea.replace('"', "").replace("'", "").replace("*", "").replace("«", "").replace("»", "").strip()


def obtener_tema_automatico(max_rondas: int = 9, candidatos_por_ronda: int = 6) -> tuple[str, int, str]:
    """Genera un hecho real nuevo comparándolo contra el 100% del historial."""
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    datos = _cargar_datos_historial()
    temas_previos = datos["temas"]
    indice = _construir_indice(temas_previos)
    print(f"📚 Historial cargado: {len(temas_previos)} temas ya producidos.")

    idx_dominio = _elegir_dominio(datos)
    epoca, anio_min, anio_max = _elegir_epoca(datos)
    print(f"🗓️ Periodo seleccionado: {epoca} ({anio_min}-{anio_max}).")
    usados = {idx_dominio}
    rondas_en_dominio = 0
    rechazados: list[str] = []

    for ronda in range(max_rondas):
        # Si un dominio no rinde después de 3 rondas, cambia a otro
        if rondas_en_dominio >= 3:
            idx_dominio = _elegir_dominio(datos, excluir=usados)
            usados.add(idx_dominio)
            if len(usados) >= len(DOMINIOS):
                usados = {idx_dominio}
            rondas_en_dominio = 0
        rondas_en_dominio += 1

        dominio = DOMINIOS[idx_dominio]
        region, angulo = random.choice(REGIONES), random.choice(ANGULOS)

        # Muestra para inspirar variedad: los más recientes + una muestra al azar del resto
        recientes = temas_previos[-30:]
        resto = temas_previos[:-30]
        muestra = recientes + random.sample(resto, min(30, len(resto)))
        texto_historial = "\n".join(f"- {t}" for t in muestra) or "Ninguno"
        texto_rechazados = "\n".join(f"✖ {r}" for r in rechazados[-25:]) or "Ninguno"

        prompt = f"""
Eres el investigador del canal de Shorts '¿Sabías que...?'. Cada video revela un hecho
real, verificable y sorprendente que deje al espectador pensando "no sabía eso".

CATEGORÍA DE ESTE VIDEO: {dominio['dominio']}
Pistas de estilo: {dominio['guia']}
{('Tono: ' + dominio['tono']) if dominio.get('tono') else ''}
PERIODO OBLIGATORIO: {epoca} (año del hecho entre {anio_min} y {anio_max}, inclusive).
No propongas hechos de otra época. En cada título, añade el año exacto entre paréntesis,
por ejemplo: "El caso de ... (2017)". Si no recuerdas con seguridad el año y el hecho,
no lo propongas.
Región sugerida: {region}
Ángulo sugerido: {angulo}

REGLAS OBLIGATORIAS:
1. Hecho 100% real y documentado. Nada de ficción, leyendas sin respaldo ni metáforas.
   Para casos recientes, evita noticias en desarrollo y no inventes nombres, fechas ni resultados.
2. Incluye en el título el nombre real de la persona, lugar, objeto o evento.
3. Evita los clichés más repetidos de internet; prefiere casos menos obvios.
4. Debe ser un hecho DISTINTO a todos los del historial y a los rechazados.

MUESTRA DEL HISTORIAL (hay más; un filtro automático revisa todos):
{texto_historial}

RECHAZADOS EN ESTA SESIÓN:
{texto_rechazados}

MISIÓN:
Entrega exactamente {candidatos_por_ronda} títulos DIFERENTES entre sí (hechos distintos), uno por línea,
máximo 12 palabras cada uno, llamativos y directos. Sin numeración, comillas ni explicaciones.
"""
        try:
            completion = client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un investigador riguroso. Solo propones hechos verídicos con nombres, fechas o lugares documentados.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.95,
                max_completion_tokens=600,
                extra_body={"reasoning_effort": "low"},
            )
        except Exception as e:
            print(f"⚠️ Error de Groq en la ronda {ronda + 1}: {e}")
            continue

        texto = completion.choices[0].message.content or ""
        candidatos = []
        for linea in texto.splitlines():
            titulo = _limpiar_titulo(linea)
            match_anio = re.search(r"\((\d{1,4})\)\s*$", titulo)
            if not match_anio:
                continue
            anio_candidato = int(match_anio.group(1))
            if not anio_min <= anio_candidato <= anio_max:
                continue
            if len(titulo) >= 12 and titulo not in candidatos and titulo not in rechazados:
                candidatos.append(titulo)

        for candidato in candidatos[:candidatos_por_ronda]:
            if _buscar_coincidencia_local(candidato, indice) or _arbitro_ia_duplicado(client, candidato, temas_previos):
                rechazados.append(candidato)
                continue
            print(f"🎯 Tema seleccionado [{epoca} | {dominio['dominio']}]: '{candidato}'")
            return candidato, idx_dominio, epoca

        print(f"⚠️ Ronda {ronda + 1}/{max_rondas} sin tema válido. Reintentando con otro enfoque...")

    raise RuntimeError(
        "No se encontró un tema nuevo tras varias rondas. Revisa la conexión con Groq o "
        "proporciona un tema manual: producir_short_bilingue('tu tema')."
    )


# ========================================================
# PRODUCCIÓN
# ========================================================
def producir_short_bilingue(tema: str = None) -> tuple[Path, Path]:
    """Ejecuta el ciclo de producción completo en Español e Inglés."""
    indice_categoria = -1
    epoca = None
    if not tema or not tema.strip():
        tema, indice_categoria, epoca = obtener_tema_automatico()
    else:
        tema = tema.strip()
        print(f"📌 Usando tema manual proporcionado: '{tema}'")
        similar = _buscar_coincidencia_local(tema, _construir_indice(_cargar_datos_historial()["temas"]))
        if similar:
            print(f"⚠️ Aviso: el tema manual se parece a uno ya producido: '{similar}'")

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
        total_escenas=12,
    )

    # 3. Síntesis de voz con captura de tiempos exactos
    print("\n[Paso 3/5] Sintetizando voz en off bilingüe y calculando marcas de tiempo...")
    ruta_audio_es = convertir_texto_a_voz(guion_es["narracion"], nombre_base=f"{nombre_base}_es", idioma="es")
    ruta_audio_en = convertir_texto_a_voz(guion_en["narracion"], nombre_base=f"{nombre_base}_en", idioma="en")

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
        idioma="es",
    )
    ruta_video_en = montar_video_final(
        nombre_base=f"{nombre_base}_en",
        duracion_voz=duracion_en,
        ruta_audio_personalizada=ruta_audio_en,
        idioma="en",
    )

    # 5. Subtítulos dinámicos sincronizados
    print("\n[Paso 5/5] Quemando subtítulos sincronizados...")
    video_final_es = agregar_subtitulos_al_video(
        ruta_video_es, ruta_audio_es, idioma="es", texto_referencia=guion_es["narracion"]
    )
    video_final_en = agregar_subtitulos_al_video(
        ruta_video_en, ruta_audio_en, idioma="en", texto_referencia=guion_en["narracion"]
    )

    # 6. Metadata de publicación y registro en historial
    generar_archivo_metadata(titulo=guion_es.get("titulo", tema), tema=tema, nombre_base=nombre_base, idioma="es")
    generar_archivo_metadata(titulo=guion_en.get("titulo", tema), tema=tema, nombre_base=nombre_base, idioma="en")
    _guardar_tema_en_historial(tema, indice_categoria, epoca)

    print("\n" + "=" * 60)
    print("✔ PRODUCCIÓN FINALIZADA CON ÉXITO")
    print(f"👉 Short Español: {video_final_es}")
    print(f"👉 Short Inglés:  {video_final_en}")
    print("=" * 60)

    return video_final_es, video_final_en


if __name__ == "__main__":
    producir_short_bilingue()
