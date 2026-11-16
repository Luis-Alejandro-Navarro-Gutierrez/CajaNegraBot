"""
Módulo para componer texto de alto impacto sobre miniatura_raw.jpg usando FFmpeg nativo.
Canal: La Caja Negra
"""
import os
import sys
import json
import subprocess
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

# Modelos activos en tu cuenta para evitar límites de cuota (429)
MODELOS_MINIATURA = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b"
]


def _obtener_ultimo_expediente() -> Path:
    directorio = BASE_DIR / "outputs" / "produccion_largos"
    carpetas = [d for d in directorio.iterdir() if d.is_dir()]
    if not carpetas:
        raise FileNotFoundError("No hay carpetas en produccion_largos")
    return max(carpetas, key=lambda d: d.stat().st_mtime)


def _obtener_datos_documental(nombre_carpeta: str) -> dict:
    """Busca el JSON original del documental para extraer contexto real."""
    dir_docs = BASE_DIR / "outputs" / "documentales_largos"
    archivo_json = dir_docs / f"{nombre_carpeta}.json"
    if archivo_json.exists():
        try:
            return json.loads(archivo_json.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def generar_texto_impacto(nombre_expediente: str) -> str:
    """Diseña una frase de 2 a 4 palabras de intriga, shock o revelación conectada al caso."""
    datos_doc = _obtener_datos_documental(nombre_expediente)
    titulo = datos_doc.get("titulo", nombre_expediente.replace("_", " "))
    hilo = datos_doc.get("hilo_conductor", "")
    casos = [c.get("titulo_caso", "") for c in datos_doc.get("capitulos_meta", [])]
    casos_str = ", ".join(casos) if casos else "Crímenes y misterios sin resolver"

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    client = Groq(api_key=api_key)

    prompt = f"""
    Eres el director de arte y miniaturas de YouTube para 'La Caja Negra' (documentales serios de misterio, crímenes y tecnología).

    EXPEDIENTE:
    - Título: {titulo}
    - Casos reales tratados: {casos_str}
    - Tesis o enigma central: {hilo}

    CONTEXTO VISUAL:
    La portada muestra una escena tensa con un sujeto en primer plano que refleja shock, temor o el descubrimiento de algo que debía permanecer oculto.

    TAREA:
    Escribe una frase magnética y narrativa de EXACTAMENTE 2, 3 O 4 PALABRAS en ESPAÑOL, en MAYÚSCULAS.
    Debe despertar intriga inmediata, tensión o una pregunta no resuelta en la mente del espectador.

    EJEMPLOS DE ALTO IMPACTO (MISTERIO Y SHOCK):
    - "VIO LO IMPOSIBLE"
    - "NUNCA DEBIÓ ENTRAR"
    - "NO FUE UN ERROR"
    - "¿QUIÉN DIO LA ORDEN?"
    - "SABÍAN LA VERDAD"
    - "ESTABA VIVO"
    - "BORRARON LA PRUEBA"
    - "EL MINUTO FINAL"

    REGLAS ESTRICTAS:
    - PROHIBIDO usar palabras cliché como "ERROR FATAL", "VERDAD SILENCIADA", "PELIGRO" o "CASO CERRADO".
    - NO exceder 4 palabras.
    - Responde ÚNICAMENTE las palabras elegidas, sin comillas, sin explicaciones, sin puntos finales.
    """

    texto_final = "NO FUE UN ERROR"
    for modelo in MODELOS_MINIATURA:
        try:
            completion = client.chat.completions.create(
                model=modelo,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.65,
                max_tokens=50,
            )
            resultado = completion.choices[0].message.content.strip()
            lineas = [l.strip() for l in resultado.splitlines() if l.strip()]
            if lineas:
                texto_final = lineas[-1]
                break
        except Exception:
            continue

    # Limpieza estricta de caracteres conflictivos para filtros FFmpeg
    for char in ['"', "'", ":", "\\", "%", "[", "]", ";", ",", ".", "¡", "!"]:
        texto_final = texto_final.replace(char, "")

    palabras = texto_final.split()
    if len(palabras) > 4:
        texto_final = " ".join(palabras[:4])

    return texto_final.upper()


def renderizar_miniatura_final(carpeta_expediente: Path):
    ruta_raw = carpeta_expediente / "miniatura_raw.jpg"
    ruta_salida = carpeta_expediente / "miniatura_final.jpg"

    if not ruta_raw.exists():
        print(f"❌ No se encontró miniatura_raw.jpg en {carpeta_expediente}")
        return

    # 1. Obtener texto de impacto contextualizado
    texto_hook = generar_texto_impacto(carpeta_expediente.name)
    print(f"📌 Texto de alto impacto para miniatura: '{texto_hook}'")

    # 2. Escapar caracteres para FFmpeg drawtext
    texto_ffmpeg = texto_hook.replace(" ", "\\ ").replace("¿", "\\¿").replace("?", "\\?")

    # 3. Filtro cinematográfico:
    # - Sin caja negra plana que opaque la imagen (box=0)
    # - Letras grandes (fontsize=h*0.16)
    # - Amarillo de contraste (#FFE600)
    # - Trazo negro exterior ancho (borderw=10) para máxima legibilidad
    # - Sombra profunda para despegar el texto del fondo
    # - Posición en el tercio superior izquierdo (x=w*0.06, y=h*0.16)
    filtro_drawtext = (
        f"drawtext=text='{texto_ffmpeg}':"
        f"font='Impact':"
        f"fontsize=h*0.16:"
        f"fontcolor=0xFFE600:"
        f"borderw=10:"
        f"bordercolor=black:"
        f"shadowcolor=black@0.9:"
        f"shadowx=7:"
        f"shadowy=7:"
        f"box=0:"
        f"x=w*0.06:"
        f"y=h*0.16"
    )

    comando = [
        "ffmpeg",
        "-y",
        "-i", str(ruta_raw),
        "-vf", filtro_drawtext,
        "-q:v", "2",
        str(ruta_salida),
    ]

    try:
        subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        print(f"✔ Miniatura final generada exitosamente en:\n📁 {ruta_salida}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando FFmpeg para la miniatura:\n{e.stderr}")
    except FileNotFoundError:
        print("❌ Error: No se encontró el comando 'ffmpeg' en el PATH del sistema.")


if __name__ == "__main__":
    carpeta = _obtener_ultimo_expediente()
    renderizar_miniatura_final(carpeta)