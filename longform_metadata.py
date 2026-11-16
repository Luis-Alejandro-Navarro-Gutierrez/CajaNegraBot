"""
Módulo para generar metadata optimizada para YouTube (Título, Descripción con Timestamps y Tags)
para documentales largos de La Caja Negra.
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _obtener_duracion_audio(ruta_audio: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(ruta_audio),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())


def _formatear_timestamp(segundos: float) -> str:
    minutos = int(segundos // 60)
    segs = int(segundos % 60)
    return f"{minutos:02d}:{segs:02d}"


def generar_metadata_documental(carpeta_expediente: Path) -> Path:
    dir_docs = BASE_DIR / "outputs" / "documentales_largos"
    archivo_json = dir_docs / f"{carpeta_expediente.name}.json"
    if not archivo_json.exists():
        raise FileNotFoundError(f"No existe el JSON del expediente: {archivo_json}")

    datos_doc = json.loads(archivo_json.read_text(encoding="utf-8"))
    titulo_doc = datos_doc.get("titulo", "")
    hilo = datos_doc.get("hilo_conductor", "")
    casos = datos_doc.get("capitulos_meta", [])

    # Calcular timestamps reales usando tiempos_sincronizados.json
    ruta_tiempos = carpeta_expediente / "tiempos_sincronizados.json"
    tiempos = json.loads(ruta_tiempos.read_text(encoding="utf-8")) if ruta_tiempos.exists() else []

    # Intro (4 escenas), Cap 1 (9), Cap 2 (9), Cap 3 (10), Epílogo (4)
    corte_intro = 0.0
    corte_cap1 = sum(tiempos[:4]) if len(tiempos) >= 4 else 60.0
    corte_cap2 = sum(tiempos[:13]) if len(tiempos) >= 13 else 180.0
    corte_cap3 = sum(tiempos[:22]) if len(tiempos) >= 22 else 320.0
    corte_epilogo = sum(tiempos[:32]) if len(tiempos) >= 32 else 480.0

    marcas_tiempo = (
        f"{_formatear_timestamp(corte_intro)} Introducción: El Secreto\n"
        f"{_formatear_timestamp(corte_cap1)} {casos[0]['titulo_caso'] if len(casos) > 0 else 'Caso 1'}\n"
        f"{_formatear_timestamp(corte_cap2)} {casos[1]['titulo_caso'] if len(casos) > 1 else 'Caso 2'}\n"
        f"{_formatear_timestamp(corte_cap3)} {casos[2]['titulo_caso'] if len(casos) > 2 else 'Caso 3'}\n"
        f"{_formatear_timestamp(corte_epilogo)} Conclusiones y Epílogo"
    )

    client = Groq(api_key=os.getenv("GROQ_API_KEY", "").strip())

    prompt = f"""
    Eres estratega de contenido y SEO en YouTube para el canal 'La Caja Negra' (documentales serios de catástrofes, misterio y tecnología).
    
    EXPEDIENTE:
    - Título base: {titulo_doc}
    - Enigma central: {hilo}
    - Casos analizados: {json.dumps(casos, ensure_ascii=False)}

    TAREA:
    Genera metadata de alto rendimiento optimizada para algoritmo de YouTube en formato JSON estricto con:
    1. "titulo_youtube": Título con gancho psicológico, misterio o advertencia (máximo 75 caracteres).
    2. "descripcion": Texto envolvente de 2 a 3 párrafos explicando la gravedad de los hechos sin spoilear la conclusión.
    3. "tags": Lista de 15 tags específicos de búsqueda en YouTube en español.

    Devuelve ÚNICAMENTE un JSON con esa estructura.
    """

    res = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.35,
        response_format={"type": "json_object"},
    )
    meta_ia = json.loads(res.choices[0].message.content)

    descripcion_completa = (
        f"{meta_ia.get('descripcion', '')}\n\n"
        f"⏳ MARCAS DE TIEMPO (CAPÍTULOS):\n"
        f"{marcas_tiempo}\n\n"
        f"🔔 Suscríbete a La Caja Negra y activa la campanita para no perderte ningún expediente clasificado.\n"
        f"#LaCajaNegra #Documental #Misterio #Historia #Tecnologia"
    )

    salida_metadata = {
        "titulo_youtube": meta_ia.get("titulo_youtube", titulo_doc),
        "descripcion_completa": descripcion_completa,
        "tags": meta_ia.get("tags", []),
        "marcas_tiempo": marcas_tiempo,
    }

    dir_meta = BASE_DIR / "outputs" / "metadata"
    dir_meta.mkdir(parents=True, exist_ok=True)
    archivo_salida = dir_meta / f"{carpeta_expediente.name}_metadata.json"
    archivo_salida.write_text(json.dumps(salida_metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    # Copiar también en la carpeta del video final para tener todo a la mano
    ruta_txt_directa = carpeta_expediente / "METADATA_YOUTUBE.txt"
    with open(ruta_txt_directa, "w", encoding="utf-8") as f:
        f.write(f"=== TÍTULO SUGERIDO ===\n{salida_metadata['titulo_youtube']}\n\n")
        f.write(f"=== DESCRIPCIÓN ===\n{descripcion_completa}\n\n")
        f.write(f"=== ETIQUETAS (TAGS) ===\n{', '.join(salida_metadata['tags'])}\n")

    print(f"✔ Metadata de YouTube guardada en:\n  📁 {archivo_salida}\n  📁 {ruta_txt_directa}")
    return archivo_salida


if __name__ == "__main__":
    directorio = BASE_DIR / "outputs" / "produccion_largos"
    carpetas = [d for d in directorio.iterdir() if d.is_dir()]
    if carpetas:
        ult = max(carpetas, key=lambda d: d.stat().st_mtime)
        generar_metadata_documental(ult)