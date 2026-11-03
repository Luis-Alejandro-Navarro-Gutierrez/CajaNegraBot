"""Genera ilustraciones de cómic para curiosidades reales con Groq y ComfyUI local."""

import json
import os
import re
import secrets
import sys
import time
import uuid
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
import requests
from PIL import Image

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
COMFYUI_CHECKPOINT = os.getenv("COMFYUI_CHECKPOINT", "arthemyComicsXL_v20.safetensors")
COMFYUI_WIDTH = 768
COMFYUI_HEIGHT = 1344
COMFYUI_OUTPUT_DIR = Path(os.getenv("COMFYUI_OUTPUT_DIR", str(BASE_DIR / "outputs" / "comfyui"))).expanduser().resolve()


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
        nombre_salida=f"CajaNegraBot_{ruta_salida.stem}",
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

    nombre_png = Path(imagen_info["filename"])
    subcarpeta = Path(imagen_info.get("subfolder", ""))
    ruta_png = (COMFYUI_OUTPUT_DIR / subcarpeta / nombre_png).resolve()
    try:
        ruta_png.relative_to(COMFYUI_OUTPUT_DIR)
    except ValueError:
        ruta_png = None
    if ruta_png and ruta_png.suffix.lower() == ".png" and ruta_png.is_file():
        try:
            ruta_png.unlink()
        except OSError as error:
            print(f"⚠ No pude borrar el PNG temporal de ComfyUI ({ruta_png.name}): {error}")


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

    abreviaturas = []
    def proteger_eeuu(match):
        marcador = f"EEUUMARCADOR{len(abreviaturas)}"
        abreviaturas.append((marcador, match.group(0)))
        return marcador

    texto_seguro = re.sub(r"\bEE\.\s*UU\.", proteger_eeuu, texto, flags=re.IGNORECASE)
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
        for marcador, abreviatura in abreviaturas:
            unidad = unidad.replace(marcador, abreviatura)
        unidades[i] = unidad

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


def generar_secuencia_imagenes(guion_completo: str, titulo: str, nombre_base: str, total_escenas: int = 12) -> list[Path]:
    """
    Asocia cada fragmento de una curiosidad real con una ilustración de cómic a color y la renderiza en ComfyUI.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY no encontrada en el archivo .env.")

    client = Groq(api_key=api_key)
    output_dir = BASE_DIR / "outputs" / "images"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Analizando guion con Groq para ilustrar la curiosidad en {total_escenas} escenas...")

    fragmentos_guion = _segmentar_narracion(guion_completo, total_escenas)
    fragmentos_formateados = "\n".join(
        f'{i}. {json.dumps(fragmento, ensure_ascii=False)}'
        for i, fragmento in enumerate(fragmentos_guion, 1)
    )

    estilo_comic = (
        "colorful 2D editorial comic cartoon, lively illustration, expressive faces, "
        "accurate standard anatomy, bold clean ink outlines, smooth cel shading, "
        "bright natural colors, exactly one dominant recognizable main subject, clear simple physical action, "
        "simple setting appropriate to the era, full-frame vertical illustration"
    )

    prompt_analisis = f"""
    You create accurate visual prompts for a short, factual curiosity comic. The narration is in Spanish and covers history, science, nature, technology, or real events. Return exactly {total_escenas} image prompts, one for each fixed scene excerpt below, in the same order.
    Full story context:
    {guion_completo}

    FIXED SCENE EXCERPTS — do not rewrite, merge, skip, reorder, or repeat them:
    {fragmentos_formateados}

    RULES FOR EACH NUMBERED PROMPT (STRICT):
    - Choose EXACTLY ONE primary subject: either ONE human, ONE animal, or ONE object.
    - ANTI-FUSION / ANTI-MUTATION RULE: If the scene mentions an animal or creature (e.g. shark, mantis shrimp, insect, dog), illustrate ONLY that creature in its natural environment. NEVER draw an animal wearing human clothes, lab coats, or having human hands. NEVER draw an anthropomorphic creature or hybrid chimera.
    - If illustrating a scientist, researcher, or person, show a regular human looking at an aquarium, screen, or workbench. The animal must be separate (e.g. inside a glass tank) or not in the shot.
    - ANATOMY & POSE RULE: Specify the exact position of both arms and hands (e.g., "both hands resting on the desk", "holding a notebook with both hands"). Never describe partial, floating, or ambiguous limbs. For animals (like sharks or fish), show the entire creature fully underwater or cleanly in motion, never split across reflection waterlines that duplicate fins or tails.
    - CLOTHING RULE: For any human, specify modest, casual, everyday attire covering their body (e.g. "wearing a lab coat over a blue shirt", "wearing a jacket and trousers"). Never describe bathroom mirrors or bedroom selfies.
    - Specify camera shot (close-up, medium shot, wide shot), 1 clear setting, 2–3 natural colors, and lighting.
    - No text, labels, captions, bubbles, split screens, collages, or floating diagrams in the image.
    - Write 40–55 clear, concrete words per prompt.

    Return ONLY valid JSON with exactly {total_escenas} prompts in the original order:
    {{"prompts":[{{"prompt_visual":"literal visual description for scene 1"}}]}}
    """
    try:
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional comic storyboard director. You produce clear, anatomically sound, concrete scene descriptions without metaphors or hybrid monsters. Output only valid JSON.",
                },
                {"role": "user", "content": prompt_analisis},
            ],
            temperature=0.3,
            reasoning_effort="low",
            max_completion_tokens=4096,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "storyboard_prompts",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "prompts": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"prompt_visual": {"type": "string"}},
                                    "required": ["prompt_visual"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["prompts"],
                        "additionalProperties": False,
                    },
                },
            },
        )

        data = json.loads(completion.choices[0].message.content)
        escenas_groq = data.get("prompts", [])
        if len(escenas_groq) != total_escenas:
            raise ValueError(f"Se esperaban {total_escenas} prompts visuales, se recibieron {len(escenas_groq)}.")
        if any(
            not isinstance(escena, dict)
            or not isinstance(escena.get("prompt_visual"), str)
            or not escena["prompt_visual"].strip()
            for escena in escenas_groq
        ):
            raise ValueError("Cada escena debe incluir un prompt_visual no vacío.")

        storyboard_prompts = [escena["prompt_visual"].strip() for escena in escenas_groq]
    except Exception as e:
        raise RuntimeError(f"Error al estructurar storyboard con Groq: {e}")

    # Blindaje contra NSFW, quimeras, miembros extra y deformidades
    negative_prompt = (
        "nsfw, nude, nudity, topless, cleavage, bare breasts, nipples, underwear, lingerie, suggestive, exposed skin, "
        "mutant, chimera, chimeric fusion, anthropomorphic insect, animal human hybrid, insect head on human body, "
        "extra arms, third arm, extra hands, extra legs, extra limbs, extra fins, duplicate tails, dorsal fin duplicate, "
        "fused limbs, deformed anatomy, distorted face, bad hands, missing fingers, extra fingers, malformed body, "
        "photorealistic, 3d render, anime, manga, monochrome, sketch, comic panels, collage, split screen, text, watermark, logo"
    )

    prompts_dir = BASE_DIR / "outputs" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    ruta_prompts = prompts_dir / f"{nombre_base}_prompts.json"
    prompts_por_escena = [
        {
            "escena": i,
            "fragmento_guion": fragmentos_guion[i - 1],
            "fragmento_coincide_literalmente": True,
            "prompt_storyboard": prompt_escena,
            "prompt_enviado_a_comfyui": f"{estilo_comic}, {prompt_escena}",
        }
        for i, prompt_escena in enumerate(storyboard_prompts, 1)
    ]
    datos_prompts = {
        "titulo": titulo,
        "nombre_base": nombre_base,
        "total_escenas": total_escenas,
        "estilo_comun": estilo_comic,
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

    for i, prompt_escena in enumerate(storyboard_prompts, 1):
        ruta_salida = output_dir / f"{nombre_base}_escena_{i}.jpg"
        print(f"  -> Generando escena {i}/{total_escenas} en ComfyUI...")

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
    print(f"✔ Generación completada. Guardadas {len(lista_rutas_imagenes)}/{total_escenas} imágenes.")
    return lista_rutas_imagenes