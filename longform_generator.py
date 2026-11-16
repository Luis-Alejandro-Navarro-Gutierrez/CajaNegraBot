"""
Módulo de planificación y guionización modular para documentales largos (8-10 min).
Enfocado en Thrillers, Robos Maestros, Hackeos Históricos, Supervivencia Extrema y True Crime.
Genera guion estructurado con Gancho Inicial estilo '¿Sabías que...?', 36 escenas sincronizadas y Cierre con CTA.
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

# Modelos activos en Groq (cuotas independientes)
MODELOS_GROQ = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b"
]

RUTA_HISTORIAL_LARGOS = BASE_DIR / "historial_largos.json"
DIR_OUTPUT_LARGOS = BASE_DIR / "outputs" / "documentales_largos"
DIR_OUTPUT_LARGOS.mkdir(parents=True, exist_ok=True)

CATEGORIAS_LARGAS = [
    "1. GOLPES MAESTROS Y ROBOS DEL SIGLO: Bóvedas inexpugnables, túneles imposibles, disfraces, robos de diamantes, bancos centrales burlados por ingenio puro.",
    "2. CIBERATAQUES Y HACKERS FANTASMA: Asaltos a redes SWIFT interbancarias, armas digitales militares (Stuxnet), malware millonario, hackers solitarios burlando al Servicio Secreto.",
    "3. CÓDIGOS SECRETOS, ESPIONAJE Y OPERACIONES IMPOSIBLES: Máquinas indescifrables (Enigma), saboteadores infiltrados, estafadores legendarios, operaciones clandestinas de la Guerra Fría.",
    "4. SUPERVIVENCIA HUMANA EXTREMA: Desastres en aislamiento absoluto, caídas aéreas libres, rescates subacuáticos en cuevas oscuras, supervivencia al límite en montañas y océanos.",
    "5. DEPREDADORES HUMANOS Y CRÍMENES METÓDICOS: Cacerías criminales históricas, criptogramas sin resolver, crímenes a sangre fría, investigaciones forenses contrarreloj."
]


def _get_groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")
    return Groq(api_key=api_key)


def _limpiar_y_parsear_json(texto: str) -> dict:
    """Extrae y decodifica JSON válido aunque el modelo agregue bloques Markdown."""
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


def _completar_con_groq(messages: list, max_tokens: int = 4096, temp: float = 0.35) -> dict:
    client = _get_groq_client()
    ultimo_error = None

    for modelo in MODELOS_GROQ:
        try:
            params = {
                "model": modelo,
                "messages": messages,
                "temperature": temp,
                "max_tokens": max_tokens,
            }
            if "gemma" not in modelo.lower():
                params["response_format"] = {"type": "json_object"}

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
    RUTA_HISTORIAL_LARGOS.write_text(
        json.dumps(temas_usados, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def planificar_episodio_largo() -> dict:
    historial = _cargar_historial()
    ultimos_temas = historial[-30:] if len(historial) > 0 else []
    historial_str = json.dumps(ultimos_temas, ensure_ascii=False, indent=2)
    categorias_str = "\n".join(CATEGORIAS_LARGAS)

    prompt_plan = f"""
    Eres el showrunner y director creativo de thrillers documentales para 'La Caja Negra' en YouTube.
    Tu objetivo es diseñar un episodio largo (8 a 10 minutos) que atrape a la audiencia desde el primer segundo.
    
    El episodio debe conectar 3 CASOS REALES IMPACTANTES bajo un enigma de alta intriga.

    PILARES TEMÁTICOS PERMITIDOS:
    {categorias_str}

    TEMAS YA TRATADOS ANTERIORMENTE (PROHIBIDO REPETIR O DERIVAR DIRECTAMENTE DE ESTOS):
    {historial_str}

    REGLAS DE FORMATO:
    1. TÍTULO: Magnético, estilo YouTube de alto CTR, misterioso y cinematográfico.
    2. HILO CONDUCTOR: La tensión o enigma real que vincula a los tres casos.
    3. ESTRUCTURA EXACTA DE 36 ESCENAS:
       - INTRODUCCIÓN: 4 escenas (Hook frontal estilo '¿Sabías que...?', escalada y presentación de los 3 casos).
       - CASO 1: 9 escenas.
       - CASO 2: 9 escenas.
       - CASO 3: 10 escenas.
       - EPÍLOGO: 4 escenas (Reflexión y llamado a la acción orgánico).
       TOTAL = 36 escenas.

    Devuelve ÚNICAMENTE un JSON con esta estructura exacta:
    {{
      "titulo": "Título de alto impacto",
      "hilo_conductor": "Tesis o enigma central que conecta los 3 casos",
      "capitulos_meta": [
        {{"numero": 1, "titulo_caso": "Nombre exacto del caso 1", "enfoque": "La audacia o tensión central"}},
        {{"numero": 2, "titulo_caso": "Nombre exacto del caso 2", "enfoque": "La audacia o tensión central"}},
        {{"numero": 3, "titulo_caso": "Nombre exacto del caso 3", "enfoque": "La audacia o tensión central"}}
      ]
    }}
    """

    return _completar_con_groq(
        messages=[
            {"role": "system", "content": "Eres director de documentales criminales y de suspense. Devuelves únicamente JSON válido."},
            {"role": "user", "content": prompt_plan}
        ],
        max_tokens=2048,
        temp=0.4
    )


def escribir_seccion_sincronizada(plan: dict, seccion_nombre: str, n_escenas: int, contexto_anterior: str = "") -> list[dict]:
    casos_str = ", ".join([f"'{c['titulo_caso']}'" for c in plan.get("capitulos_meta", [])])
    directriz_especial = ""

    if "INTRODUCCIÓN" in seccion_nombre:
        directriz_especial = f"""
        REGLAS OBLIGATORIAS PARA EL HOOK DE INTRODUCCIÓN (4 ESCENAS):
        - ESCENA 1 (EL GANCHO FRONTAL): Debe iniciar OBLIGATORIAMENTE con un golpe directo de intriga usando la fórmula '¿Sabías que...' o una revelación impactante. Ejemplo: '¿Sabías que existe un documento militar que...' o '¿Sabías que en solo cuarenta segundos un error microscópico borró...'. PROHIBIDO arrancar con reflexiones filosóficas, conceptos abstractos o saludos.
        - ESCENA 2 (LA ESCALADA DEL PELIGRO): Explica por qué este suceso desafió toda lógica o cómo los gobiernos intentaron encubrirlo. Mantén la tensión al límite.
        - ESCENA 3 (EL MENÚ DE CASOS // QUÉ VERÁ HOY EL ESPECTADOR): Presenta de forma misteriosa y enérgica los tres casos que se analizarán en el video: {casos_str}. El espectador debe saber exactamente qué historias fascinantes va a escuchar hoy.
        - ESCENA 4 (EL DISPARADOR): Cierre del prólogo e invitación a iniciar el primer expediente. Ejemplo: 'Bienvenidos a las sombras de la historia. Apaga la luz, ponte los auriculares... y acompáñanos al primer expediente.'
        """
    elif "EPÍLOGO" in seccion_nombre:
        directriz_especial = """
        REGLAS DE CIERRE PARA EL EPÍLOGO:
        - Las primeras 3 escenas cierran la tesis y reflexionan sobre la delgada línea entre el orden y el caos.
        - La ESCENA 4 (Cierre definitivo) DEBE concluir con una frase contundente e invitar de forma natural a suscribirse a La Caja Negra y activar la campana para el próximo expediente.
        """

    prompt_guion = f"""
    Eres el guionista principal y director de suspense para 'La Caja Negra'.
    Estás redactando la sección: "{seccion_nombre}" para el documental: "{plan['titulo']}".
    HILO CONDUCTOR: {plan['hilo_conductor']}

    CONTEXTO PREVIO:
    {contexto_anterior[-600:] if contexto_anterior else "Inicio del documental."}

    {directriz_especial}

    REGLAS ESTRICTAS DE PRODUCCIÓN Y ESTILO:
    1. Genera EXACTAMENTE {n_escenas} bloques secuenciales.
    2. Cada bloque de texto debe contener entre 38 y 44 palabras en español neutro, ritmo pausado, cinematográfico y de suspenso puro (esto asegura que el video supere los 8 minutos de duración).
    3. Cada bloque DEBE incluir un "prompt_visual_16_9" en INGLÉS optimizado para SDXL con sujetos humanos reales:
       - PROHIBIDO fondos vacíos, pasillos solitarios o salas desiertas sin personas.
       - DEBE mostrar personas con rostros expresivos: testigos en shock, ladrones en acción, científicos angustiados, detectives revisando pruebas o siluetas amenazantes en primer plano.
       - Estilo visual: 'cinematic 35mm film still, intense human facial expression, chiaroscuro rim lighting, high contrast volumetric shadows, 16:9 ratio, depth of field, hyper-realistic, dark atmospheric mood, 8k'.

    Devuelve ÚNICAMENTE un JSON con esta estructura:
    {{
      "bloques": [
        {{
          "texto_locucion": "Párrafo en español de 38 a 44 palabras narrado con tensión y cadencia...",
          "prompt_visual_16_9": "Cinematic 35mm film still of [detailed person with intense expression and action], dramatic chiaroscuro rim lighting, dark moody background, 16:9 frame, highly detailed"
        }}
      ]
    }}
    """

    data = _completar_con_groq(
        messages=[
            {"role": "system", "content": "Eres guionista cinematográfico y director de documentales de misterio. Devuelves únicamente JSON válido."},
            {"role": "user", "content": prompt_guion}
        ],
        max_tokens=4096,
        temp=0.35
    )

    bloques = data.get("bloques", [])
    if len(bloques) != n_escenas:
        print(f"  ⚠ Ajustando bloques devueltos ({len(bloques)}) a {n_escenas}...")
    return bloques[:n_escenas]


def generar_documental_completo():
    print("====================================================")
    print(" 🎬 CAJANEGRA THRILLER GENERATOR // 36 ESCENAS      ")
    print(" (Robos, Ciberataques, Criptografía, Supervivencia) ")
    print("====================================================")

    # 1. Planificación
    print("\n[1/3] 🧠 Conceptualizando expediente de alto impacto...")
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
    print("\n[2/3] ✍️ Redactando guion de suspense sincronizado 1:1 con escenas...")
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