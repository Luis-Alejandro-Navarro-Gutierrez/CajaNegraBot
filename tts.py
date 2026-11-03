"""Módulo para convertir guiones en voz en off (Text-to-Speech) usando Edge-TTS con normalización fonética."""

import asyncio
import re
import sys
from pathlib import Path
import edge_tts

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

# Voz oficial de Álvaro
VOICE = "es-ES-AlvaroNeural"


def _convertir_anio_a_palabras(match: re.Match) -> str:
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


def normalizar_texto_para_tts(texto: str) -> str:
    """Prepara el texto para evitar pausas artificiales al leer años, siglas o signos."""
    # Elimina puntos en años formateados como 1.945 o 2.024
    texto = re.sub(r"\b([12])\.(\d{3})\b", r"\1\2", texto)

    # Convierte años comunes (de 1000 a 2099) a texto en español fluido
    texto = re.sub(r"\b(1\d{3}|20\d{2})\b", _convertir_anio_a_palabras, texto)

    # Limpia comillas y guiones dobles que puedan forzar silencios innecesarios
    texto = texto.replace('"', '').replace('“', '').replace('”', '')
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


async def _generar_audio_async(texto: str, ruta_salida: Path) -> None:
    """Función asíncrona interna para procesar la locución con edge-tts."""
    texto_procesado = normalizar_texto_para_tts(texto)
    # rate='+5%' aporta un ritmo más ágil y moderno sin sonar acelerado
    communicate = edge_tts.Communicate(texto_procesado, VOICE, rate="+5%")
    await communicate.save(str(ruta_salida))


def convertir_texto_a_voz(texto_guion: str, nombre_base: str = "narracion") -> Path:
    """Convierte el texto del guion en un archivo de audio MP3 guardado en outputs/audio/."""
    output_dir = BASE_DIR / "outputs" / "audio"
    output_dir.mkdir(parents=True, exist_ok=True)

    nombre_archivo = f"{Path(nombre_base).stem}.mp3"
    ruta_salida = output_dir / nombre_archivo

    print(f"Sintetizando voz en off con '{VOICE}' (años normalizados a texto)...")
    asyncio.run(_generar_audio_async(texto_guion, ruta_salida))

    print(f"✔ ¡Audio generado con éxito! Guardado en: {ruta_salida}")
    return ruta_salida


if __name__ == "__main__":
    texto_prueba = (
        "En 1945 terminó la guerra, pero en 1957 un nuevo misterio comenzó en los Urales. "
        "Todo cambió en el año 2024."
    )
    convertir_texto_a_voz(texto_prueba, "prueba_voz_anios")