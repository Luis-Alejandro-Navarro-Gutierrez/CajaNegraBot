"""
Módulo de planificación y guionización modular para documentales largos (8-10 min).
Enfocado en Casos Absurdos, Robos Arruinados por Estupideces, Hackeos Insólitos y Crímenes con Giros Cómicos.
Genera guion estructurado con Gancho Inicial estilo '¿Sabías que...?', 36 escenas sincronizadas y Cierre con CTA.
Estilo visual: Cómic moderno limpio, novela gráfica europea con variedad de planos (paisajes, objetos, acción y reacciones).
Canal: La Caja Negra
"""
import os
import sys
import json
import re
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

# ========================================================
# RUTAS PERSISTENTES
# ========================================================
if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

MODELOS_GROQ = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b"
]

RUTA_HISTORIAL_LARGOS = BASE_DIR / "historial_largos.json"
DIR_OUTPUT_LARGOS = BASE_DIR / "outputs" / "documentales_largos"
DIR_OUTPUT_LARGOS.mkdir(parents=True, exist_ok=True)

CATEGORIAS_LARGAS = [
    "1. ASESINATOS Y VENGANZAS QUE SALIERON RIDÍCULAMENTE MAL: Conspiradores, criminales o planes macabros reales que terminaron en una comedia de enredos, autotrampas involuntarias o giros cómicos insólitos.",
    "2. ROBOS MILLONARIOS ARRUINADOS POR ESTUPIDECES: Asaltos millonarios a bancos, museos, joyerías o transportes blindados que burlaron seguridad de punta pero colapsaron por descuidos absurdos de sentido común.",
    "3. HACKEOS Y CRÍMENES DIGITALES INSÓLITOS: Ataques informáticos multimillonarios, robos digitales y estafas en línea desbaratados por descuidos cotidianos, fallos ortográficos o negligencias técnicas insólitas.",
    "4. ERRORES TONTOS Y ANOMALÍAS CON EFECTOS MONUMENTALES: Descuidos en laboratorios, fallos de traducción o accidentes comerciales que crearon imperios multimillonarios o cambiaron la historia por pura casualidad.",
    "5. GUERRAS, LEYES Y CONFLICTOS POR MOTIVOS ABSURDOS: Movilizaciones militares, disputas diplomáticas o litigios judiciales de enorme escala originados por incidentes ridículos, animales, comida o motivos triviales."
]


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")
    return Groq(api_key=api_key)


def _limpiar_y_parsear_json(texto: str) -> dict:
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


def _completar_con_groq(messages: list, max_tokens: int = 4096, temp: float = 0.5) -> dict:
    client = _get_groq_client()
    ultimo_error = None

    for modelo in MODELOS_GROQ:
        try:
            params = {
                "model": modelo,
                "messages": messages,
                "temperature": temp,
                "max_completion_tokens": max_tokens,
            }
            if "openai" in modelo.lower():
                params["extra_body"] = {"reasoning_effort": "low"}

            res = client.chat.completions.create(**params)
            contenido = res.choices[0].message.content
            return _limpiar_y_parsear_json(contenido)
        except Exception as e:
            ultimo_error = e
            print(f"  ⚠ Modelo '{modelo}' falló ({e}). Probando alternativa...")

    raise RuntimeError(f"Ningún modelo de Groq pudo procesar la solicitud: {ultimo_error}")


def _cargar_historial() -> list:
    if RUTA_HISTORIAL_LARGOS.exists():
        try:
            datos = json.loads(RUTA_HISTORIAL_LARGOS.read_text(encoding="utf-8"))
            if isinstance(datos, list):
                return datos
            elif isinstance(datos, dict):
                elementos = []
                for k, v in datos.items():
                    if isinstance(v, str):
                        elementos.append(v)
                    elif isinstance(v, list):
                        elementos.extend([str(item) for item in v if isinstance(item, str)])
                    else:
                        elementos.append(str(k))
                return elementos
        except Exception:
            return []
    return []


def _guardar_historial(temas_usados: list) -> None:
    temas_unicos = []
    for t in temas_usados:
        if t not in temas_unicos:
            temas_unicos.append(t)

    RUTA_HISTORIAL_LARGOS.write_text(
        json.dumps(temas_unicos, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def es_caso_duplicado_con_ia(client: Groq, caso_propuesto: str, historial: list[str]) -> bool:
    if not historial:
        return False

    caso_limpio = caso_propuesto.strip().lower()
    for h in historial:
        if caso_limpio == h.strip().lower():
            return True

    casos_referencia = "\n".join(f"- {h}" for h in historial[-40:])

    prompt_juez = f"""
    Eres un árbitro editorial y verificador histórico estricto para un canal de documentales.
    Evalúa si la siguiente propuesta relata EL MISMO evento o suceso histórico que cualquiera de los ya tratados en el canal.

    CASO PROPUESTO A EVALUAR:
    "{caso_propuesto}"

    HISTORIAL DE CASOS YA CONTADOS EN EL CANAL:
    {casos_referencia}

    CRITERIOS DE DESCARTE:
    - Responde DUPLICADO si es el mismo hecho real, incluso si cambia la redacción, el país citado por error o los adjetivos.
    - Responde NUEVO si es un evento o hecho histórico completamente diferente y nunca antes contado en la lista.

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
        print(f"  ⚠ Advertencia en árbitro IA ({e}), continuando validación estándar...")
        return False


def planificar_episodio_largo(max_intentos: int = 6) -> dict:
    client = _get_groq_client()
    historial = _cargar_historial()
    historial_str = "\n".join(f"- {t}" for t in historial[-35:]) if historial else "Ninguno"

    indice_cat = len(historial) % len(CATEGORIAS_LARGAS)
    cat_elegida = CATEGORIAS_LARGAS[indice_cat]

    prompt_plan = f"""
    Eres el showrunner y director creativo de documentales para 'La Caja Negra' en YouTube.
    Diseña un episodio largo (8 a 10 min) conectando 3 CASOS REALES IMPACTANTES bajo un enigma de torpeza, ironía o mala suerte insólita.

    CATEGORÍA OBLIGATORIA PARA ESTE EPISODIO:
    {cat_elegida}

    CASOS Y TEMAS YA TRATADOS (TOTALMENTE PROHIBIDO REPETIR O REESCRIBIR ESTOS CASOS):
    {historial_str}

    REGLAS DE SELECCIÓN:
    1. TONO: Muy entretenido, ágil, curioso, irónico y directo. CERO terminología abstracta, cero aburrimiento.
    2. TÍTULO: Magnético, estilo YouTube de alto CTR, con gancho irresistible y enfoque en lo absurdo del suceso real.
    3. TRES CASOS: Deben ser eventos verídicos y documentados en la historia real, pero 100% nuevos e inéditos respecto al historial.
    4. ESTRUCTURA EXACTA DE 36 ESCENAS:
       - INTRODUCCIÓN: 4 escenas (Hook frontal estilo '¿Sabías que...?', escalada y presentación de los 3 casos).
       - CASO 1: 9 escenas.
       - CASO 2: 9 escenas.
       - CASO 3: 10 escenas.
       - EPÍLOGO: 4 escenas (Reflexión irónica sobre la estupidez humana y llamado a la acción orgánico).
       TOTAL = 36 escenas.

    Devuelve ÚNICAMENTE un JSON con esta estructura exacta:
    {{
      "titulo": "Título de alto impacto y curiosidad",
      "hilo_conductor": "Tesis o tema central que conecta los 3 casos",
      "capitulos_meta": [
        {{"numero": 1, "titulo_caso": "Nombre histórico y descriptivo del caso 1", "enfoque": "El plan maestro y el fallo ridículo exacto"}},
        {{"numero": 2, "titulo_caso": "Nombre histórico y descriptivo del caso 2", "enfoque": "El plan maestro y el fallo ridículo exacto"}},
        {{"numero": 3, "titulo_caso": "Nombre histórico y descriptivo del caso 3", "enfoque": "El plan maestro y el fallo ridículo exacto"}}
      ]
    }}
    """

    for intento in range(max_intentos):
        plan = _completar_con_groq(
            messages=[
                {"role": "system", "content": "Eres director de documentales virales sobre sucesos históricos insólitos. Devuelves únicamente JSON válido."},
                {"role": "user", "content": prompt_plan}
            ],
            max_tokens=2048,
            temp=0.65 + (intento * 0.05)
        )

        casos_propuestos = [c.get("titulo_caso", "").strip() for c in plan.get("capitulos_meta", [])]

        hay_duplicado = False
        for caso in casos_propuestos:
            if es_caso_duplicado_con_ia(client, caso, historial):
                print(f"  ⚠ El árbitro IA detectó que el caso '{caso}' ya fue tratado. Descartando propuesta...")
                hay_duplicado = True
                break

        if not hay_duplicado and len(casos_propuestos) == 3:
            return plan

        print(f"  🔄 Regenerando propuesta de 3 casos inéditos ({intento + 1}/{max_intentos})...")

    return plan


def escribir_seccion_sincronizada(plan: dict, seccion_nombre: str, n_escenas: int, contexto_anterior: str = "") -> list[dict]:
    casos_str = ", ".join([f"'{c['titulo_caso']}'" for c in plan.get("capitulos_meta", [])])
    directriz_especial = ""

    if "INTRODUCCIÓN" in seccion_nombre:
        directriz_especial = f"""
        REGLAS OBLIGATORIAS PARA EL HOOK DE INTRODUCCIÓN (4 ESCENAS):
        - ESCENA 1 (EL GANCHO FRONTAL): Inicia OBLIGATORIAMENTE con un golpe directo de intriga usando la fórmula '¿Sabías que...?' con el hecho verídico más disparatado de este documental. Cita datos reales desde la primera línea. PROHIBIDO arrancar con reflexiones poéticas o saludos.
        - ESCENA 2 (LA ESCALADA DEL ABSURDO): Explica cómo criminales profesionales o líderes planearon durante meses un golpe perfecto y cómo todo se vino abajo por una distracción inverosímil.
        - ESCENA 3 (EL MENÚ DE CASOS): Presenta con ritmo rápido y nombres claros los tres casos reales de hoy: {casos_str}. El espectador debe saber exactamente qué historias fascinantes va a escuchar.
        - ESCENA 4 (EL DISPARADOR): Cierre del prólogo e invitación a iniciar el primer caso. Ejemplo: 'Ponte cómodo, porque hoy en La Caja Negra vas a ver que la realidad supera cualquier ficción absurda. Vamos con el primer expediente.'
        """
    elif "EPÍLOGO" in seccion_nombre:
        directriz_especial = """
        REGLAS DE CIERRE PARA EL EPÍLOGO:
        - Las primeras 3 escenas analizan con humor negro y sarcasmo cómo el exceso de confianza y la falta de sentido común pueden arruinar millones de dólares o planes gigantescos.
        - La ESCENA 4 (Cierre definitivo) concluye con un remate ingenioso e invita de forma natural a dejar su Like, suscribirse a La Caja Negra y activar la campana para el próximo expediente insólito.
        """

    prompt_guion = f"""
    Eres el guionista principal y narrador de 'La Caja Negra'.
    Estás redactando la sección: "{seccion_nombre}" para el documental: "{plan['titulo']}".
    HILO CONDUCTOR: {plan['hilo_conductor']}

    CONTEXTO PREVIO:
    {contexto_anterior[-600:] if contexto_anterior else "Inicio del documental."}

    {directriz_especial}

    REGLAS ESTRICTAS DE LOCUCIÓN (CHISME HISTÓRICO REAL, ÁGIL Y DIRECTO AL GRANO):
    1. Genera EXACTAMENTE {n_escenas} bloques secuenciales.
    2. Cada bloque de texto debe contener entre 38 y 44 palabras en español dinámico, narrativo y entretenido.
    3. CERO METÁFORAS Y POESÍA:
       - PROHIBIDO usar analogías vacías ("la elegancia de un pulpo", "piscina de confeti", "zen sin café", "marioneta desarmada").
       - PROHIBIDO inventar consecuencias falsas (cajeros que imprimen palabras extrañas, entrevistas inventadas en TV).
       - PROHIBIDO repetir palabras de relleno como 'arrogancia', 'confeti', 'película muda' o 'tragedia cómica'.
    4. CÓMO CONTAR LA HISTORIA:
       - Cuenta los HECHOS REALES de forma cronológica: quiénes eran los involucrados, qué planearon, cuánto dinero u objetivo perseguían, y cuál fue el error exacto y comprobable por el que fueron descubiertos.
       - Tono: Como un creador de contenido contándole a sus amigos una historia real tan ridícula y genial que cuesta creer que ocurrió.

    REGLAS VISUALES OBLIGATORIAS (VARIEDAD CINEMATOGRÁFICA EN CÓMIC MODERNO / NOVELA GRÁFICA):
    Cada bloque DEBE incluir un "prompt_visual_16_9" en INGLÉS optimizado para SDXL.

    ¡ESTRICTAMENTE PROHIBIDO PONER CARAS DE PERSONAS EN TODAS LAS ESCENAS!
    Debes alternar de manera equilibrada entre estos 4 tipos de encuadre:
    1. PLANOS GENERALES Y PAISAJES (Wide angle scenes): Exteriores de bancos, calles nocturnas iluminadas, hangares, oficinas corporativas, puertos marítimos o fachadas vistas desde la distancia.
    2. OBJETOS Y DETALLES EN PRIMER PLANO (Close-up / Still life): Maletines abiertos con dinero, herramientas de cerrajería, planos con rutas, monitores con código de error, candados rotos, contratos sellados o archivos policiales.
    3. ACCIÓN Y SITUACIONES AMBIENTALES: Vehículos de escape doblando esquinas, siluetas corriendo bajo la lluvia, patrullas con balizas encendidas o puertas de seguridad abiertas.
    4. PERSONAS Y REACCIONES (Solo cuando el momento clave lo requiera): Personajes estilizados con gestos claros de desconcierto, sorpresa cómica o tensión.

    ESTILO ARTÍSTICO (CÓMIC MODERNO LIMPIO Y BRILLANTE):
    - Estilo: 'Modern comic book illustration, clear black ink outlines, clean lineart, flat cel shading, graphic novel style, vibrant balanced colors, soft bright readable lighting, 16:9 aspect ratio'.
    - PROHIBIDO: Estilos oscuros o sucios, sombras densas tipo terror, estilo Arcane y fotorrealismo.

    Devuelve ÚNICAMENTE un JSON con esta estructura:
    {{
      "bloques": [
        {{
          "texto_locucion": "Párrafo en español de 38 a 44 palabras narrado con ritmo ágil, datos concretos y gracia...",
          "prompt_visual_16_9": "Modern comic book illustration of [scenic wide landscape, important object close-up, action situation, or expressive character], clean ink outlines, flat cel shading, soft bright lighting, graphic novel art, 16:9 aspect ratio"
        }}
      ]
    }}
    """

    data = _completar_con_groq(
        messages=[
            {"role": "system", "content": "Eres guionista y director creativo de animación y documentales reales. Devuelves únicamente JSON válido."},
            {"role": "user", "content": prompt_guion}
        ],
        max_tokens=4096,
        temp=0.45
    )

    bloques = data.get("bloques", [])
    if len(bloques) != n_escenas:
        print(f"  ⚠ Ajustando bloques devueltos ({len(bloques)}) a {n_escenas}...")
    return bloques[:n_escenas]


def generar_documental_completo():
    print("====================================================")
    print(" 🎬 CAJANEGRA THRILLER GENERATOR // 36 ESCENAS      ")
    print(" (Crímenes Absurdos, Robos Cómicos y Animación 2D) ")
    print("====================================================")

    # 1. Planificación
    print("\n[1/3] 🧠 Conceptualizando expediente inédito con árbitro IA...")
    plan = planificar_episodio_largo()
    print(f"  • Título: {plan['titulo']}")
    print(f"  • Enigma: {plan['hilo_conductor']}")
    print(f"  • Casos: {', '.join([c['titulo_caso'] for c in plan['capitulos_meta']])}")

    # Estructura de 36 escenas:
    config_secciones = [
        ("INTRODUCCIÓN", 4),
        (f"CAPÍTULO 1: {plan['capitulos_meta'][0]['titulo_caso']}", 9),
        (f"CAPÍTULO 2: {plan['capitulos_meta'][1]['titulo_caso']}", 9),
        (f"CAPÍTULO 3: {plan['capitulos_meta'][2]['titulo_caso']}", 10),
        ("EPÍLOGO Y CONCLUSIÓN", 4),
    ]

    # 2. Redacción
    print("\n[2/3] ✍️ Redactando guion ágil con datos reales sincronizado 1:1 con escenas...")
    guion_estructurado = []
    prompts_visuales = []
    contexto_acumulado = ""

    for nombre_sec, n_escenas in config_secciones:
        print(f"  • Redactando: {nombre_sec} ({n_escenas} escenas)...")
        bloques = escribir_seccion_sincronizada(plan, nombre_sec, n_escenas, contexto_acumulado)

        for b in bloques:
            texto = b.get("texto_locucion", "").strip()
            prompt_vis = b.get("prompt_visual_16_9", "").strip()

            guion_estructurado.append({
                "seccion": nombre_sec,
                "texto": texto,
                "prompt_visual": prompt_vis
            })
            prompts_visuales.append(prompt_vis)
            contexto_acumulado += f" {texto}"

    total_palabras = sum(len(b["texto"].split()) for b in guion_estructurado)
    print(f"\n✔ Guion completado: {len(guion_estructurado)} escenas | {total_palabras} palabras (~{total_palabras / 150:.2f} min reales en locución)")

    # 3. Guardar archivo final
    slug_nombre = re.sub(r"[^a-zA-Z0-9]+", "_", plan["titulo"].lower()).strip("_")[:50]
    ruta_guardado = DIR_OUTPUT_LARGOS / f"{slug_nombre}.json"

    datos_finales = {
        "titulo": plan["titulo"],
        "hilo_conductor": plan["hilo_conductor"],
        "capitulos_meta": plan["capitulos_meta"],
        "total_escenas": len(guion_estructurado),
        "total_palabras": total_palabras,
        "guion_estructurado": guion_estructurado,
        "prompts_visuales_16_9": prompts_visuales
    }

    ruta_guardado.write_text(json.dumps(datos_finales, ensure_ascii=False, indent=2), encoding="utf-8")

    # Actualizar historial
    historial = _cargar_historial()
    historial.append(plan["titulo"])
    for c in plan["capitulos_meta"]:
        historial.append(c["titulo_caso"])
    _guardar_historial(historial)

    print(f"\n[3/3] 📁 Expediente guardado exitosamente en:\n{ruta_guardado}")


if __name__ == "__main__":
    generar_documental_completo()