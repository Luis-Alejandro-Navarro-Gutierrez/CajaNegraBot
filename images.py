"""Genera ilustraciones de cómic para curiosidades reales ('¿Sabías que...?') con Groq y ComfyUI local.

Cubre hackeos, robos, casos criminales, ciencia, universo, planeta, orígenes de las cosas y desastres.
Cada escena recibe un rol de cámara (objeto, plano general, acción, personaje) calculado en código,
así que funciona con cualquier número de escenas y evita rostros repetidos.
"""

import json
import os
import re
import secrets
import shutil
import sys
import time
import uuid
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import requests
from PIL import Image

if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    # Si está dentro de dist (o subcarpeta de dist), sube hasta la raíz
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_CHECKPOINT = os.getenv("COMFYUI_CHECKPOINT", "arthemyComicsXL_v20.safetensors")
COMFYUI_WIDTH = 768
COMFYUI_HEIGHT = 1344
COMFYUI_OUTPUT_DIR = Path(os.getenv("COMFYUI_OUTPUT_DIR", str(BASE_DIR / "outputs" / "comfyui"))).expanduser().resolve()
PREFIJO_SALIDA_COMFY = "CajaNegraBot_"
MODELO_GROQ = "openai/gpt-oss-120b"

# Rol de cámara por escena (se repite en ciclo: con 12 escenas queda 1-5-9 objeto, 2-6-10 general, etc.)
ROLES_ESCENA = [
    (
        "OBJECT CLOSE-UP",
        "ONE meaningful object or piece of evidence in tight close-up (e.g. a vault door, circuit board, telescope, "
        "lab flask, old invention, newspaper clipping, evidence marker, ticking clock). NO people, NO faces.",
    ),
    (
        "WIDE ESTABLISHING SHOT",
        "A wide environment or landscape that places the story (e.g. a city street at dusk, a bank exterior, a server room, "
        "a volcano, a desert, a launch pad, a laboratory, a harbor). NO people in the foreground, NO faces.",
    ),
    (
        "ACTION / SITUATION",
        "A dynamic moment told through the environment: motion, vehicles, smoke, sparks, flashing lights, small silhouettes "
        "seen from far away or from behind. NO face close-ups.",
    ),
    (
        "CHARACTER REACTION",
        "ONE generic stylized character with a clear expressive face (shock, nervousness, irony, perplexity, determination). "
        "Prefer investigators, witnesses, scientists, workers or bystanders; never show injured people.",
    ),
]


def _limpiar_carpeta_comfyui() -> None:
    """Elimina los archivos temporales que genera este bot en la carpeta de salida de ComfyUI.

    Solo borra archivos con el prefijo del bot, para no tocar otras imágenes si COMFYUI_OUTPUT_DIR
    apunta a la carpeta de salida real de ComfyUI.
    """
    if not COMFYUI_OUTPUT_DIR.exists():
        return

    time.sleep(1.0)  # Pausa breve para garantizar que ComfyUI haya liberado descriptores de archivo en Windows
    print(f"🧹 Limpiando archivos temporales en ComfyUI ({COMFYUI_OUTPUT_DIR.name})...")

    for item in COMFYUI_OUTPUT_DIR.iterdir():
        if not item.name.startswith(PREFIJO_SALIDA_COMFY):
            continue
        for intento in range(3):
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                break
            except OSError:
                time.sleep(0.5)


def _crear_workflow_comfy(prompt: str, negative_prompt: str, seed: int, nombre_salida: str) -> dict:
    """Construye el workflow API con nodos estándar de ComfyUI."""
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": COMFYUI_CHECKPOINT}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "EmptyLatentImage", "inputs": {"width": COMFYUI_WIDTH, "height": COMFYUI_HEIGHT, "batch_size": 1}},
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 30,
                "cfg": 5.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": nombre_salida, "images": ["6", 0]}},
    }


def _generar_en_comfy(prompt: str, negative_prompt: str, escena: int, ruta_salida: Path) -> None:
    """Encola una imagen en ComfyUI, espera el resultado y lo convierte a JPG."""
    workflow = _crear_workflow_comfy(
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=secrets.randbelow(2**32 - 1),
        nombre_salida=f"{PREFIJO_SALIDA_COMFY}{ruta_salida.stem}",
    )
    try:
        respuesta = requests.post(
            f"{COMFYUI_URL}/prompt",
            json={"prompt": workflow, "client_id": str(uuid.uuid4())},
            timeout=30,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"No se pudo conectar a ComfyUI en {COMFYUI_URL}. Abre Comfy Desktop en modo Local y vuelve a intentar."
        ) from error

    if not respuesta.ok:
        raise RuntimeError(f"ComfyUI rechazó la escena {escena} (HTTP {respuesta.status_code}): {respuesta.text}")

    prompt_id = respuesta.json().get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI no devolvió prompt_id para la escena {escena}: {respuesta.text}")

    limite = time.monotonic() + 600
    imagen_info = None
    while time.monotonic() < limite:
        historial_respuesta = requests.get(f"{COMFYUI_URL}/history/{prompt_id}", timeout=30)
        historial_respuesta.raise_for_status()
        entrada = historial_respuesta.json().get(prompt_id)
        if entrada:
            salida = entrada.get("outputs", {}).get("7", {})
            imagenes = salida.get("images", [])
            if imagenes:
                imagen_info = imagenes[0]
                break
            estado = entrada.get("status", {})
            if estado.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI falló al generar la escena {escena}: {estado.get('messages', estado)}")
        time.sleep(1)

    if imagen_info is None:
        raise TimeoutError(f"ComfyUI no terminó la escena {escena} en 10 minutos.")

    imagen_respuesta = requests.get(
        f"{COMFYUI_URL}/view",
        params={
            "filename": imagen_info["filename"],
            "subfolder": imagen_info.get("subfolder", ""),
            "type": imagen_info.get("type", "output"),
        },
        timeout=120,
    )
    imagen_respuesta.raise_for_status()
    with Image.open(BytesIO(imagen_respuesta.content)) as imagen:
        imagen.convert("RGB").save(ruta_salida, format="JPEG", quality=95)


# Abreviaturas e iniciales cuyo punto NO termina una oración
_PATRON_ABREVIATURAS = re.compile(
    r"(?:\bEE\.\s*UU\.|\bU\.\s?S\.|\bU\.\s?K\.|"
    r"\b(?:Dra?|Sra?|Srta|Mr|Mrs|Ms|St|Jr|Lic|Ing|Prof|núm|aprox|etc)\."
    r"|\b[ap]\.\s?m\.|\b[ad]\.\s?C\."
    r"|\b[A-ZÁÉÍÓÚÑ]\.(?=\s+[A-ZÁÉÍÓÚÑ]))",
    flags=re.IGNORECASE,
)


def _segmentar_narracion(narracion: str, total_escenas: int) -> list[str]:
    """Divide la narración en fragmentos contiguos y equilibrados, sin pedirle a Groq que los invente."""
    if total_escenas < 1:
        raise ValueError("El número de escenas debe ser mayor que cero.")

    texto = re.sub(r"\s+", " ", narracion).strip()
    texto = re.sub(
        r"\s*Dale\s+Like\s+y\s+suscr[ií]bete\s+para\s+m[aá]s\s+contenido[.!?…]*\s*$",
        "",
        texto,
        flags=re.IGNORECASE,
    ).strip()
    if not texto:
        raise ValueError("La narración visual está vacía después de retirar el cierre.")

    # Protege abreviaturas con marcadores únicos y delimitados (evita choques tipo 1 vs 10)
    protegidos: list[str] = []

    def proteger(match):
        protegidos.append(match.group(0))
        return f"\x00{len(protegidos) - 1}\x00"

    texto_seguro = _PATRON_ABREVIATURAS.sub(proteger, texto)
    unidades = [parte.strip() for parte in re.split(r"(?<=[.!?])\s+", texto_seguro) if parte.strip()]

    while len(unidades) < total_escenas:
        indice = max(range(len(unidades)), key=lambda i: len(re.findall(r"\S+", unidades[i])))
        unidad = unidades.pop(indice)
        clausulas = re.split(r"(?<=[,;:])\s+", unidad)
        if len(clausulas) > 1:
            conteos = [len(re.findall(r"\S+", parte)) for parte in clausulas]
            total_palabras_unidad = sum(conteos)
            corte = min(range(1, len(clausulas)), key=lambda n: abs(sum(conteos[:n]) - total_palabras_unidad / 2))
            izquierda = " ".join(clausulas[:corte])
            derecha = " ".join(clausulas[corte:])
        else:
            palabras = unidad.split()
            if len(palabras) < 2:
                raise ValueError("No hay suficientes palabras para crear todos los fragmentos de escena.")
            corte = len(palabras) // 2
            izquierda = " ".join(palabras[:corte])
            derecha = " ".join(palabras[corte:])
        unidades[indice:indice] = [izquierda, derecha]

    for i, unidad in enumerate(unidades):
        unidades[i] = re.sub(r"\x00(\d+)\x00", lambda m: protegidos[int(m.group(1))], unidad)

    conteos = [len(re.findall(r"\S+", unidad)) for unidad in unidades]
    prefijos = [0]
    for conteo in conteos:
        prefijos.append(prefijos[-1] + conteo)

    cantidad = len(unidades)
    objetivo = prefijos[-1] / total_escenas
    infinito = float("inf")
    costo = [[infinito] * (cantidad + 1) for _ in range(total_escenas + 1)]
    anterior = [[-1] * (cantidad + 1) for _ in range(total_escenas + 1)]
    costo[0][0] = 0.0

    for escenas_usadas in range(1, total_escenas + 1):
        fin_maximo = cantidad - (total_escenas - escenas_usadas)
        for fin in range(escenas_usadas, fin_maximo + 1):
            for inicio in range(escenas_usadas - 1, fin):
                if costo[escenas_usadas - 1][inicio] == infinito:
                    continue
                palabras_grupo = prefijos[fin] - prefijos[inicio]
                candidato = costo[escenas_usadas - 1][inicio] + (palabras_grupo - objetivo) ** 2
                if candidato < costo[escenas_usadas][fin]:
                    costo[escenas_usadas][fin] = candidato
                    anterior[escenas_usadas][fin] = inicio

    grupos = []
    fin = cantidad
    for escenas_usadas in range(total_escenas, 0, -1):
        inicio = anterior[escenas_usadas][fin]
        if inicio < 0:
            raise ValueError("No pude repartir la narración en fragmentos contiguos.")
        grupos.append(" ".join(unidades[inicio:fin]))
        fin = inicio
    grupos.reverse()
    return grupos


def _generar_storyboard(client: Groq, prompt_analisis: str, total_escenas: int, intentos: int = 2) -> tuple[str, list[str]]:
    """Pide a Groq el contexto visual común y un prompt por escena. Reintenta si la respuesta no es válida."""
    ultimo_error = None
    for intento in range(1, intentos + 1):
        try:
            completion = client.chat.completions.create(
                model=MODELO_GROQ,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a professional comic storyboard director. You enforce strict camera variety, "
                            "factual accuracy and non-graphic imagery. Output only valid JSON."
                        ),
                    },
                    {"role": "user", "content": prompt_analisis},
                ],
                temperature=0.3,
                max_completion_tokens=4096,
                extra_body={"reasoning_effort": "low"},
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "storyboard_prompts",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "contexto_visual": {"type": "string"},
                                "prompts": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {"prompt_visual": {"type": "string"}},
                                        "required": ["prompt_visual"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": ["contexto_visual", "prompts"],
                            "additionalProperties": False,
                        },
                    },
                },
            )

            data = json.loads(completion.choices[0].message.content or "")
            escenas = data.get("prompts", [])
            if len(escenas) != total_escenas:
                raise ValueError(f"Se esperaban {total_escenas} prompts visuales, se recibieron {len(escenas)}.")
            if any(
                not isinstance(e, dict) or not isinstance(e.get("prompt_visual"), str) or not e["prompt_visual"].strip()
                for e in escenas
            ):
                raise ValueError("Cada escena debe incluir un prompt_visual no vacío.")

            contexto = str(data.get("contexto_visual", "")).strip().rstrip(".,")
            return contexto, [e["prompt_visual"].strip() for e in escenas]
        except Exception as e:
            ultimo_error = e
            if intento < intentos:
                print(f"  ⚠ Storyboard inválido (intento {intento}/{intentos}); reintentando: {e}")
                time.sleep(2)

    raise RuntimeError(f"Error al estructurar storyboard con Groq: {ultimo_error}")


def generar_secuencia_imagenes(guion_completo: str, titulo: str, nombre_base: str, total_escenas: int = 12) -> list[Path]:
    """
    Asocia cada fragmento de una curiosidad real con una ilustración de cómic a color y la renderiza en ComfyUI.
    Al finalizar la generación de todas las escenas, limpia los temporales del bot en la carpeta de ComfyUI.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    output_dir = BASE_DIR / "outputs" / "images"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analizando guion con Groq para ilustrar la curiosidad en {total_escenas} escenas con variedad cinematográfica...")

    fragmentos_guion = _segmentar_narracion(guion_completo, total_escenas)
    roles = [ROLES_ESCENA[(i - 1) % len(ROLES_ESCENA)] for i in range(1, total_escenas + 1)]

    fragmentos_formateados = "\n".join(
        f'{i}. [{roles[i - 1][0]}] {json.dumps(fragmento, ensure_ascii=False)}'
        for i, fragmento in enumerate(fragmentos_guion, 1)
    )
    descripcion_roles = "\n".join(f"- {nombre}: {descripcion}" for nombre, descripcion in ROLES_ESCENA)

    estilo_comic = (
        "Modern comic book illustration, vibrant balanced colors, clear black ink outlines, "
        "clean lineart, smooth flat cel shading, soft bright readable lighting, "
        "clear physical action, simple setting appropriate to the era, full-frame vertical 9:16 illustration"
    )

    prompt_analisis = f"""
You create accurate visual storyboard prompts for a factual curiosity comic short ("Did you know...?").
The story may be about a hack, a heist, a criminal case, science, space, the planet, the origin of an invention or custom, or a disaster.
The narration is in Spanish. Return exactly {total_escenas} image prompts, one for each fixed scene excerpt below, in the exact same order.

Full story context:
{guion_completo}

FIXED SCENE EXCERPTS (each tagged with its camera role). Do not rewrite, merge, skip, reorder, or repeat them:
{fragmentos_formateados}

CAMERA ROLES (follow the tag of each scene strictly; this avoids endless human faces):
{descripcion_roles}

FIELD "contexto_visual":
- At most 15 English words describing the era, country or location, and dominant color palette of the whole story.
- Do NOT describe any person in it. It is added automatically to every scene, so keep it generic.

RULES FOR EACH NUMBERED PROMPT (STRICT):
- Illustrate what the excerpt says, using the correct era: period-accurate clothing, vehicles, buildings and technology.
- Each prompt must be self-contained: image generation is independent per scene, so restate the key setting and subject.
- Choose EXACTLY ONE primary subject: either ONE object, ONE environment, or ONE character (only in CHARACTER REACTION scenes).
- Never depict real, identifiable people; use generic stylized characters. Never include real brands or logos.
- Keep every scene non-graphic: NO blood, gore, corpses, wounds, nudity or visible suffering. For crimes, imply events through
  evidence markers, police tape, empty rooms, shadows, newspaper clippings or reactions instead of showing violence.
- Hacks and technology: show abstract glowing code shapes, warning lights and hardware. NO readable words, letters or numbers on screens, papers or signs.
- ANTI-FUSION / ANTI-MUTATION: never draw anthropomorphic creatures, animal-human hybrids, or extra limbs. Animals only if the story is about them, anatomically accurate.
- POSE & PROPORTIONS: specify exact positions (e.g. "both hands resting on the control desk"). Never describe floating or ambiguous limbs.
- NO text, subtitles, speech bubbles, watermarks, comic panels, or collage frames in the image.
- Write 35-45 clear, concrete descriptive words in English per prompt.

Return ONLY valid JSON with exactly {total_escenas} prompts:
{{"contexto_visual":"era, place and palette","prompts":[{{"prompt_visual":"literal visual description for scene"}}]}}
"""
    contexto_visual, storyboard_prompts = _generar_storyboard(client, prompt_analisis, total_escenas)

    # Blindaje contra NSFW, contenido gráfico, quimeras, miembros extra y deformidades
    negative_prompt = (
        "nsfw, nude, nudity, topless, cleavage, bare breasts, nipples, underwear, lingerie, suggestive, exposed skin, "
        "blood, bloody, gore, corpse, dead body, wounds, mutilation, graphic violence, "
        "mutant, chimera, chimeric fusion, anthropomorphic insect, animal human hybrid, insect head on human body, "
        "extra arms, third arm, extra hands, extra legs, extra limbs, extra fins, duplicate tails, dorsal fin duplicate, "
        "fused limbs, deformed anatomy, distorted face, bad hands, missing fingers, extra fingers, malformed body, "
        "photorealistic, 3d render, anime, manga, dark shadows, gritty horror, monochrome, sketch, comic panels, collage, split screen, "
        "text, gibberish text, letters, numbers, watermark, logo"
    )

    prefijo_comun = f"{estilo_comic}, {contexto_visual}" if contexto_visual else estilo_comic

    prompts_dir = BASE_DIR / "outputs" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    ruta_prompts = prompts_dir / f"{nombre_base}_prompts.json"
    prompts_por_escena = [
        {
            "escena": i,
            "rol_camara": roles[i - 1][0],
            "fragmento_guion": fragmentos_guion[i - 1],
            "fragmento_coincide_literalmente": True,
            "prompt_storyboard": prompt_escena,
            "prompt_enviado_a_comfyui": f"{prefijo_comun}, {prompt_escena}",
        }
        for i, prompt_escena in enumerate(storyboard_prompts, 1)
    ]
    datos_prompts = {
        "titulo": titulo,
        "nombre_base": nombre_base,
        "total_escenas": total_escenas,
        "estilo_comun": estilo_comic,
        "contexto_visual": contexto_visual,
        "negative_prompt_comun": negative_prompt,
        "escenas": prompts_por_escena,
    }
    ruta_prompts.write_text(
        json.dumps(datos_prompts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Prompts guardados en: {ruta_prompts}")
    lista_rutas_imagenes = []
    print(f"Renderizando escenas con ComfyUI en {COMFYUI_URL} usando {COMFYUI_CHECKPOINT}...")

    for i in range(1, total_escenas + 1):
        ruta_salida = output_dir / f"{nombre_base}_escena_{i}.jpg"
        print(f"  -> Generando escena {i}/{total_escenas} en ComfyUI ({roles[i - 1][0].lower()})...")

        prompt_final = prompts_por_escena[i - 1]["prompt_enviado_a_comfyui"]

        for intento in range(1, 3):
            try:
                _generar_en_comfy(prompt_final, negative_prompt, i, ruta_salida)
                lista_rutas_imagenes.append(ruta_salida)
                break
            except Exception as e:
                if intento == 1:
                    print(f"  ⚠ Falló la escena {i}; reintentando una vez: {e}")
                    time.sleep(2)
                else:
                    raise RuntimeError(
                        f"No se pudo generar la escena {i} después de 2 intentos. "
                        "No se montará un video con escenas faltantes."
                    ) from e

    if len(lista_rutas_imagenes) != total_escenas:
        raise RuntimeError(
            f"Storyboard incompleto: se generaron {len(lista_rutas_imagenes)}/{total_escenas} imágenes."
        )

    # Limpieza final de los temporales del bot en la carpeta de ComfyUI una vez convertidos todos los JPGs
    _limpiar_carpeta_comfyui()

    print(f"✔ Generación completada. Guardadas {len(lista_rutas_imagenes)}/{total_escenas} imágenes.")
    return lista_rutas_imagenes