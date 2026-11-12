"""Módulo para convertir guiones en voz en off (Text-to-Speech) usando Edge-TTS con soporte bilingüe (ES / EN) y reintentos ante fallos de conexión."""

import asyncio
import re
import sys
import os
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
    # Elimina puntos en años o números formateados
    texto = re.sub(r"\b([12])\.(\d{3})\b", r"\1\2", texto)

    if idioma == "es":
        # Convierte años comunes (de 1000 a 2099) a texto en español fluido
        texto = re.sub(r"\b(1\d{3}|20\d{2})\b", _convertir_anio_a_palabras_es, texto)

    # Limpia comillas y guiones que fuercen pausas innecesarias en ambos idiomas
    texto = texto.replace('"', '').replace('“', '').replace('”', '').replace("'", "")
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


async def _generar_audio_async(texto: str, ruta_salida: Path, voz: str, idioma: str, max_intentos: int = 3) -> None:
    """Función asíncrona interna para procesar la locución con reintentos automáticos ante timeouts de Bing."""
    texto_procesado = normalizar_texto_para_tts(texto, idioma=idioma)
    
    for intento in range(1, max_intentos + 1):
        try:
            # rate='+5%' aporta dinamismo sin distorsionar el tono
            communicate = edge_tts.Communicate(texto_procesado, voz, rate="+5%")
            await communicate.save(str(ruta_salida))
            return
        except Exception as e:
            if intento == max_intentos:
                raise RuntimeError(f"Fallo definitivo en Edge-TTS tras {max_intentos} intentos: {e}")
            espera = intento * 2
            print(f"⚠️ Reintento {intento}/{max_intentos} en Edge-TTS por timeout o red... esperando {espera}s")
            await asyncio.sleep(espera)


def convertir_texto_a_voz(texto_guion: str, nombre_base: str = "narracion", idioma: str = "es") -> Path:
    """
    Convierte el texto del guion en un archivo de audio MP3 guardado en outputs/audio/.
    :param idioma: 'es' para español (Álvaro) o 'en' para inglés (Christopher).
    """
    output_dir = BASE_DIR / "outputs" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    idioma = idioma.lower().strip()
    voz = VOICE_EN if idioma == "en" else VOICE_ES

    nombre_archivo = f"{Path(nombre_base).stem}.mp3"
    ruta_salida = output_dir / nombre_archivo

    print(f"Sintetizando voz en off [{idioma.upper()}] con '{voz}'...")
    asyncio.run(_generar_audio_async(texto_guion, ruta_salida, voz, idioma))

    print(f"✔ ¡Audio [{idioma.upper()}] generado con éxito! Guardado en: {ruta_salida}")
    return ruta_salida


if __name__ == "__main__":
    # Prueba en Español
    convertir_texto_a_voz("En 1957 ocurrió un misterio en los Urales.", "prueba_es", idioma="es")
    # Prueba en Inglés
    convertir_texto_a_voz("In 1957, a dark mystery began deep in the Ural Mountains.", "prueba_en", idioma="en")