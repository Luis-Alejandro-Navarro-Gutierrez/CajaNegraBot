"""Módulo para convertir guiones en voz en off (Text-to-Speech) usando Edge-TTS con soporte bilingüe (ES / EN),
reintentos ante fallos de conexión y captura de marcas de tiempo exactas por palabra (WordBoundary) para subtítulos.
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
import edge_tts

if "CAJANEGRA_ROOT" in os.environ:
    BASE_DIR = Path(os.environ["CAJANEGRA_ROOT"])
elif getattr(sys, "frozen", False):
    exe_path = Path(sys.executable).resolve()
    # Si está dentro de dist (o subcarpeta de dist), sube hasta la raíz
    BASE_DIR = exe_path.parent.parent if exe_path.parent.name.lower() == "dist" else exe_path.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Voces oficiales para cada canal
VOICE_ES = "es-ES-AlvaroNeural"         # La Caja Negra (Español)
VOICE_EN = "en-US-ChristopherNeural"    # The Black Box Archives (Inglés - Documental Profundo)


def _convertir_anio_a_palabras_es(match: re.Match) -> str:
    """Convierte números de 4 dígitos típicos de años (1000-2099) a texto continuo en español."""
    numero_str = match.group(0)
    num = int(numero_str)

    unidades = {
        0: "", 1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
        6: "seis", 7: "siete", 8: "ocho", 9: "nueve"
    }
    especiales = {
        10: "diez", 11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "quince",
        16: "dieciséis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve", 20: "veinte",
        21: "veintiuno", 22: "veintidós", 23: "veintitrés", 24: "veinticuatro", 25: "veinticinco",
        26: "veintiséis", 27: "veintisiete", 28: "veintiocho", 29: "veintinueve"
    }
    decenas = {
        3: "treinta", 4: "cuarenta", 5: "cincuenta", 6: "sesenta",
        7: "setenta", 8: "ochenta", 9: "noventa"
    }
    centenas = {
        1: "ciento", 2: "doscientos", 3: "trescientos", 4: "cuatrocientos",
        5: "quinientos", 6: "seiscientos", 7: "setecientos", 8: "ochocientos", 9: "novecientos"
    }

    # Caso años 2000 a 2099
    if 2000 <= num <= 2099:
        resto = num - 2000
        if resto == 0:
            return "dos mil"
        if resto in especiales:
            return f"dos mil {especiales[resto]}"
        if resto < 10:
            return f"dos mil {unidades[resto]}"
        dec = resto // 10
        uni = resto % 10
        texto_dec = decenas[dec]
        return f"dos mil {texto_dec} y {unidades[uni]}" if uni else f"dos mil {texto_dec}"

    # Caso años 1000 a 1999
    if 1000 <= num <= 1999:
        resto = num - 1000
        if resto == 0:
            return "mil"
        c = resto // 100
        resto_c = resto % 100

        prefijo = f"mil {centenas[c]}" if c else "mil"
        if resto_c == 0:
            return "mil cien" if c == 1 else prefijo

        if resto_c in especiales:
            return f"{prefijo} {especiales[resto_c]}"
        if resto_c < 10:
            return f"{prefijo} {unidades[resto_c]}"

        dec = resto_c // 10
        uni = resto_c % 10
        texto_dec = decenas[dec]
        return f"{prefijo} {texto_dec} y {unidades[uni]}" if uni else f"{prefijo} {texto_dec}"

    return numero_str


def normalizar_texto_para_tts(texto: str, idioma: str = "es") -> str:
    """Prepara el texto para evitar pausas artificiales al leer años, siglas o signos."""
    texto = re.sub(r"\b([12])\.(\d{3})\b", r"\1\2", texto)

    if idioma == "es":
        texto = re.sub(r"\b(1\d{3}|20\d{2})\b", _convertir_anio_a_palabras_es, texto)

    texto = texto.replace('"', '').replace('“', '').replace('”', '').replace("'", "")
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


async def _generar_audio_con_tiempos_async(
    texto: str,
    ruta_salida: Path,
    ruta_tiempos: Path,
    voz: str,
    idioma: str,
    max_intentos: int = 3
) -> None:
    """Genera audio MP3 y captura marcas de tiempo por palabra vía WordBoundary con reintentos."""
    texto_procesado = normalizar_texto_para_tts(texto, idioma=idioma)

    for intento in range(1, max_intentos + 1):
        try:
            communicate = edge_tts.Communicate(texto_procesado, voz, rate="+5%")
            palabras_tiempos = []

            with open(ruta_salida, "wb") as archivo_audio:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        archivo_audio.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        # offset y duration vienen en unidades de 100ns (1s = 10,000,000 unidades)
                        offset_seg = chunk["offset"] / 10_000_000.0
                        duracion_seg = chunk["duration"] / 10_000_000.0
                        palabras_tiempos.append({
                            "word": chunk["text"],
                            "start": offset_seg,
                            "end": offset_seg + duracion_seg
                        })

            ruta_tiempos.write_text(json.dumps(palabras_tiempos, ensure_ascii=False, indent=2), encoding="utf-8")
            return
        except Exception as e:
            if intento == max_intentos:
                raise RuntimeError(f"Fallo definitivo en Edge-TTS tras {max_intentos} intentos: {e}")
            espera = intento * 2
            print(f"⚠️ Reintento {intento}/{max_intentos} en Edge-TTS por timeout o red... esperando {espera}s")
            await asyncio.sleep(espera)


def convertir_texto_a_voz(texto_guion: str, nombre_base: str = "narracion", idioma: str = "es") -> Path:
    """Convierte el texto del guion en un archivo de audio MP3 y genera su JSON de marcas de tiempo."""
    output_dir = BASE_DIR / "outputs" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    idioma = idioma.lower().strip()
    voz = VOICE_EN if idioma == "en" else VOICE_ES

    nombre_raiz = Path(nombre_base).stem
    ruta_salida = output_dir / f"{nombre_raiz}.mp3"
    ruta_tiempos = output_dir / f"{nombre_raiz}_tiempos.json"

    print(f"Sintetizando voz en off [{idioma.upper()}] con '{voz}' y extrayendo marcas de tiempo exactas...")
    asyncio.run(_generar_audio_con_tiempos_async(texto_guion, ruta_salida, ruta_tiempos, voz, idioma))

    print(f"✔ Audio [{idioma.upper()}] generado: {ruta_salida.name}")
    print(f"✔ Tiempos exactos guardados: {ruta_tiempos.name}")
    return ruta_salida


if __name__ == "__main__":
    convertir_texto_a_voz("En 1957 ocurrió un misterio en los Urales.", "prueba_es", idioma="es")
    convertir_texto_a_voz("In 1957, a dark mystery began deep in the Ural Mountains.", "prueba_en", idioma="en")