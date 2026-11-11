"""
CAJANEGRABOT // YOUTUBE SHORTS CREATOR STUDIO PRO
- Paleta Slate / Dark Graphite Mate con alto contraste de blancos y grises (anti-fatiga).
- Icono/favicon automático generado desde assets/Logo.jfif.
- Tarjeta de producción con rotación automática y visor HD integrado.
- Sistema Bilingüe Nativo: [ES] La Caja Negra  |  [EN] The Black Box Archives.
"""

import os
import sys
import json
import threading
import time
from pathlib import Path
from PIL import Image
from proglog import ProgressBarLogger

# ========================================================
# FIX PARA MODO NOCONSOLE / PYINSTALLER
# ========================================================
class StreamRedirector:
    def __init__(self, callback=None):
        self.callback = callback

    def write(self, text):
        if self.callback and text.strip():
            self.callback(text.strip())

    def flush(self):
        pass

if sys.stdout is None:
    sys.stdout = StreamRedirector()
if sys.stderr is None:
    sys.stderr = StreamRedirector()

from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
    if BASE_DIR.name.lower() == "dist":
        BASE_DIR = BASE_DIR.parent
else:
    BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

import customtkinter as ctk
import pyperclip

# Importaciones del pipeline bilingüe
import main as pipeline_main
from generator import (
    CIERRE_VIDEO_ES,
    CIERRE_VIDEO_EN,
    generar_guion,
    traducir_guion_a_ingles,
    guardar_guion,
)
from tts import convertir_texto_a_voz
from images import generar_secuencia_imagenes
from video import montar_video_final
from subtitles import agregar_subtitulos_al_video
from metadata import generar_archivo_metadata

# ========================================================
# PALETA SLATE / GRAPHITE MATE (INSPIRADA EN EL DASHBOARD)
# ========================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# Fondos neutros mate (antifatiga, sin negro absoluto)
C_BG = "#15171C"              # Gris carbón base
C_SURFACE = "#1E222B"         # Contenedores principales
C_CARD = "#272C38"            # Tarjetas elevadas
C_CARD_HOVER = "#323846"      # Hover interactivo
C_INPUT = "#181B22"           # Campos y áreas de texto
C_BORDER = "#333A4A"          # Bordes suaves delimitadores
C_BORDER_ACCENT = "#2DD4BF"   # Borde acento turquesa sutil

# Textos limpios de alto contraste
C_TEXT_MAIN = "#FFFFFF"       # Blanco nítido
C_TEXT_BODY = "#E2E8F0"       # Blanco hueso / gris suave
C_TEXT_MUTED = "#94A3B8"      # Gris medio legible

# Acentos selectivos (Dashboard Analytics)
C_TEAL = "#2DD4BF"            # Turquesa / Menta
C_TEAL_DARK = "#134E48"       # Contenedor de badge turquesa
C_PURPLE = "#C084FC"          # Púrpura pastel
C_AMBER = "#FBBF24"           # Amarillo / Dorado suave
C_EMERALD = "#34D399"         # Verde estatus
C_DANGER = "#F87171"          # Rojo coral
C_DANGER_HOVER = "#EF4444"

HORARIOS_INFO = [
    ("Slot 01", "08:30 AM", "Matutino"),
    ("Slot 02", "11:45 AM", "Almuerzo"),
    ("Slot 03", "02:45 PM", "Pausa Tarde"),
    ("Slot 04", "06:00 PM", "Regreso"),
    ("Slot 05", "08:45 PM", "Prime Time"),
]


class MoviePyCallbackLogger(ProgressBarLogger):
    """Captura el progreso frame a frame de MoviePy para la interfaz."""
    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback

    def callback(self, **changes):
        for bar_name, state in self.state.get("bars", {}).items():
            total = state.get("total", 0)
            index = state.get("index", 0)
            if total > 0:
                pct = int((index / total) * 100)
                self.update_callback(pct, index, total)


class VisorFullResolucion(ctk.CTkToplevel):
    """Ventana modal en alta definición con navegación de imágenes."""
    def __init__(self, parent, lista_rutas: list[Path], indice_inicial: int = 0):
        super().__init__(parent)
        self.lista_rutas = lista_rutas
        self.indice = indice_inicial

        self.title("Visor de Escenas HD // Full Resolution")
        self.geometry("860x980")
        self.minsize(640, 780)
        self.configure(fg_color=C_BG)

        # Header
        hdr = ctk.CTkFrame(self, fg_color=C_SURFACE, height=56, corner_radius=0, border_color=C_BORDER, border_width=1)
        hdr.pack(fill="x", side="top")

        self.btn_prev = ctk.CTkButton(
            hdr, text="◀ Anterior", width=110, height=34,
            fg_color=C_CARD, hover_color=C_CARD_HOVER, border_color=C_BORDER, border_width=1,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._anterior
        )
        self.btn_prev.pack(side="left", padx=16, pady=10)

        self.lbl_titulo = ctk.CTkLabel(
            hdr, text="", font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"), text_color=C_TEXT_MAIN
        )
        self.lbl_titulo.pack(side="left", expand=True)

        self.btn_next = ctk.CTkButton(
            hdr, text="Siguiente ▶", width=110, height=34,
            fg_color=C_CARD, hover_color=C_CARD_HOVER, border_color=C_BORDER, border_width=1,
            text_color=C_TEXT_MAIN, font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=self._siguiente
        )
        self.btn_next.pack(side="right", padx=16, pady=10)

        # Contenedor central
        self.img_container = ctk.CTkFrame(self, fg_color="#101216", corner_radius=0)
        self.img_container.pack(fill="both", expand=True)

        self.lbl_imagen = ctk.CTkLabel(self.img_container, text="")
        self.lbl_imagen.place(relx=0.5, rely=0.5, anchor="center")

        self.bind("<Left>", lambda e: self._anterior())
        self.bind("<Right>", lambda e: self._siguiente())
        self.bind("<Escape>", lambda e: self.destroy())

        self._renderizar_escena()

    def _renderizar_escena(self):
        if not self.lista_rutas or self.indice >= len(self.lista_rutas):
            return

        ruta = self.lista_rutas[self.indice]
        self.lbl_titulo.configure(text=f"Escena {self.indice + 1} de {len(self.lista_rutas)}  •  {ruta.name}")

        try:
            pil_img = Image.open(ruta)
            orig_w, orig_h = pil_img.size

            max_w, max_h = 780, 860
            ratio = min(max_w / orig_w, max_h / orig_h)
            display_w = int(orig_w * ratio)
            display_h = int(orig_h * ratio)

            pil_resized = pil_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_resized, dark_image=pil_resized, size=(display_w, display_h))

            self.lbl_imagen.configure(image=ctk_img, text="")
            self.lbl_imagen.image = ctk_img
        except Exception as e:
            self.lbl_imagen.configure(text=f"Error cargando imagen: {e}")

        self.btn_prev.configure(state="normal" if self.indice > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.indice < len(self.lista_rutas) - 1 else "disabled")

    def _anterior(self):
        if self.indice > 0:
            self.indice -= 1
            self._renderizar_escena()

    def _siguiente(self):
        if self.indice < len(self.lista_rutas) - 1:
            self.indice += 1
            self._renderizar_escena()


class CajaNegraStudio(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CajaNegra Studio // Executive Automation Suite (Dual Language)")
        self.geometry("1620x940")
        self.minsize(1440, 860)
        self.configure(fg_color=C_BG)

        self.ultimo_nombre_raiz = None
        self.ultimo_video_path_es = None
        self.ultimo_video_path_en = None
        self.canal_activo = "es"  # "es" o "en"
        self.is_running = False

        self.imagenes_generadas: list[Path] = []
        self.indice_imagen_activa = 0

        self._establecer_icono_aplicacion()
        self._construir_layout()

        sys.stdout = StreamRedirector(self._log_directo)
        sys.stderr = StreamRedirector(self._log_directo)

    def _establecer_icono_aplicacion(self):
        """Convierte y asigna el favicon nativo de la ventana desde el archivo en assets/."""
        posibles_logos = [
            BASE_DIR / "assets" / "Logo.jfif",
            BASE_DIR / "assets" / "logo.jfif",
            BASE_DIR / "assets" / "logo.png",
            BASE_DIR / "assets" / "Logo.png",
            BASE_DIR / "assets" / "logo.jpg",
        ]
        ruta_logo = next((p for p in posibles_logos if p.exists()), None)
        if ruta_logo:
            try:
                ico_path = BASE_DIR / "assets" / "temp_favicon.ico"
                if not ico_path.exists():
                    img = Image.open(ruta_logo).convert("RGBA")
                    img.save(ico_path, format="ICO", sizes=[(32, 32), (48, 48), (64, 64)])
                self.iconbitmap(str(ico_path))
            except Exception:
                pass

    def _construir_layout(self):
        self.grid_columnconfigure(0, weight=0, minsize=510)
        self.grid_columnconfigure(1, weight=1, minsize=480)
        self.grid_columnconfigure(2, weight=0, minsize=470)
        self.grid_rowconfigure(0, weight=1)

        # ========================================================
        # COLUMNA 1: CONTROL & TELEMETRÍA (SLATE MATE)
        # ========================================================
        self.col1 = ctk.CTkFrame(
            self, width=510, fg_color=C_SURFACE, corner_radius=18, border_color=C_BORDER, border_width=1
        )
        self.col1.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        self.col1.grid_propagate(False)

        # Header con Logo
        hdr_1 = ctk.CTkFrame(self.col1, fg_color="transparent")
        hdr_1.pack(fill="x", padx=22, pady=(20, 8))

        logo_box = ctk.CTkFrame(hdr_1, fg_color="transparent")
        logo_box.pack(fill="x")

        posibles_logos = [
            BASE_DIR / "assets" / "Logo.jfif",
            BASE_DIR / "assets" / "logo.jfif",
            BASE_DIR / "assets" / "logo.png",
            BASE_DIR / "assets" / "Logo.png",
            BASE_DIR / "assets" / "logo.jpg",
        ]
        ruta_logo = next((p for p in posibles_logos if p.exists()), None)
        if ruta_logo:
            try:
                pil_logo = Image.open(ruta_logo).convert("RGBA").resize((52, 52), Image.Resampling.LANCZOS)
                self.ctk_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(52, 52))
                lbl_logo = ctk.CTkLabel(logo_box, image=self.ctk_logo, text="")
                lbl_logo.pack(side="left", padx=(0, 14))
            except Exception:
                pass

        title_texts = ctk.CTkFrame(logo_box, fg_color="transparent")
        title_texts.pack(side="left", fill="both")

        tag_badge = ctk.CTkLabel(
            title_texts,
            text="⚡ DUAL-LANGUAGE PIPELINE",
            font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
            text_color=C_TEAL,
            fg_color=C_TEAL_DARK,
            corner_radius=6,
            padx=8,
            pady=2,
        )
        tag_badge.pack(anchor="w")

        ctk.CTkLabel(
            title_texts,
            text="CajaNegra Studio",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=C_TEXT_MAIN,
        ).pack(anchor="w", pady=(2, 0))

        # Tarjeta Descriptiva del Motor
        card_desc = ctk.CTkFrame(
            self.col1, fg_color=C_CARD, corner_radius=14, border_color=C_BORDER, border_width=1
        )
        card_desc.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            card_desc,
            text="PRODUCCIÓN SIMULTÁNEA [ES 🇪🇸 & EN 🇺🇸]",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C_TEAL,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        desc_pipeline_texto = (
            "Motor bilingüe automatizado: genera un concepto rotando entre 10 categorías, "
            "produce 12 imágenes SDXL de alta fidelidad compartidas y renderiza dos videos finales "
            "completos: 'La Caja Negra' (Voz Álvaro / ES) y 'The Black Box Archives' "
            "(Voz Christopher / EN), cada uno con subtítulos Whisper dinámicos."
        )
        ctk.CTkLabel(
            card_desc,
            text=desc_pipeline_texto,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=C_TEXT_BODY,
            justify="left",
            wraplength=430,
        ).pack(anchor="w", padx=16, pady=(0, 12))

        self.btn_generar = ctk.CTkButton(
            card_desc,
            text="⚡ Iniciar Producción Cíclica (ES + EN)",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=42,
            fg_color="#0F766E",
            hover_color="#115E59",
            text_color="#FFFFFF",
            corner_radius=8,
            command=self._iniciar_produccion_hilo,
        )
        self.btn_generar.pack(fill="x", padx=16, pady=(0, 16))

        # Indicador de Estado y Barra de Progreso
        stat_box = ctk.CTkFrame(self.col1, fg_color=C_CARD, corner_radius=10, border_color=C_BORDER, border_width=1)
        stat_box.pack(fill="x", padx=20, pady=4)

        stat_inner = ctk.CTkFrame(stat_box, fg_color="transparent")
        stat_inner.pack(fill="x", padx=14, pady=10)

        self.led_indicator = ctk.CTkLabel(
            stat_inner, text="● EN ESPERA", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=C_EMERALD
        )
        self.led_indicator.pack(side="left")

        self.lbl_status_text = ctk.CTkLabel(
            stat_inner, text="Listo para procesar", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=C_TEXT_MUTED, anchor="e"
        )
        self.lbl_status_text.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self.col1, height=6, fg_color="#181B22", progress_color=C_TEAL, corner_radius=3
        )
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=22, pady=(4, 10))

        # Consola de Telemetría
        ctk.CTkLabel(
            self.col1,
            text="TELEMETRÍA & LOGS DE EJECUCIÓN",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C_TEXT_MUTED,
        ).pack(anchor="w", padx=22, pady=(4, 4))

        self.txt_logs = ctk.CTkTextbox(
            self.col1,
            fg_color=C_INPUT,
            text_color="#93C5FD",
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=10,
            border_color=C_BORDER,
            border_width=1,
            wrap="char",
        )
        self.txt_logs.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # ========================================================
        # COLUMNA 2: GESTIÓN DE PUBLICACIÓN & YOUTUBE
        # ========================================================
        self.col2 = ctk.CTkFrame(
            self, fg_color=C_SURFACE, corner_radius=18, border_color=C_BORDER, border_width=1
        )
        self.col2.grid(row=0, column=1, padx=8, pady=16, sticky="nsew")

        top_col2 = ctk.CTkFrame(self.col2, fg_color="transparent")
        top_col2.pack(fill="x", padx=22, pady=(20, 10))

        ctk.CTkLabel(
            top_col2,
            text="Centro de Publicación",
            font=ctk.CTkFont(family="Segoe UI", size=24, weight="bold"),
            text_color=C_TEXT_MAIN,
        ).pack(side="left")

        # Selector de canal / idioma
        self.tabs_lang = ctk.CTkSegmentedButton(
            top_col2,
            values=["🇪🇸 ES (La Caja Negra)", "🇺🇸 EN (Black Box)"],
            command=self._cambiar_pestana_idioma,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            selected_color="#0F766E",
            selected_hover_color="#115E59",
            unselected_color=C_CARD,
            unselected_hover_color=C_CARD_HOVER,
            text_color=C_TEXT_MAIN,
        )
        self.tabs_lang.set("🇪🇸 ES (La Caja Negra)")
        self.tabs_lang.pack(side="right")

        # Tarjeta Título
        card_t = ctk.CTkFrame(self.col2, fg_color=C_CARD, corner_radius=12, border_color=C_BORDER, border_width=1)
        card_t.pack(fill="x", padx=20, pady=4)

        t_head = ctk.CTkFrame(card_t, fg_color="transparent")
        t_head.pack(fill="x", padx=16, pady=(10, 4))
        self.lbl_titulo_header = ctk.CTkLabel(
            t_head, text="TÍTULO + HASHTAGS [ES]", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C_PURPLE
        )
        self.lbl_titulo_header.pack(side="left")
        self.lbl_char_count = ctk.CTkLabel(
            t_head, text="0/100", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C_TEXT_MUTED
        )
        self.lbl_char_count.pack(side="right")

        self.entry_titulo = ctk.CTkEntry(
            card_t, height=38, fg_color=C_INPUT, border_color=C_BORDER, text_color=C_TEXT_MAIN, font=ctk.CTkFont(size=12), corner_radius=8
        )
        self.entry_titulo.pack(fill="x", padx=16, pady=4)

        ctk.CTkButton(
            card_t, text="Copiar Título", height=28, width=120, fg_color="#333A4A", hover_color="#3F475A",
            text_color=C_TEXT_MAIN, corner_radius=6, command=self._copiar_titulo
        ).pack(anchor="e", padx=16, pady=(2, 10))

        # Tarjeta Descripción
        card_d = ctk.CTkFrame(self.col2, fg_color=C_CARD, corner_radius=12, border_color=C_BORDER, border_width=1)
        card_d.pack(fill="both", expand=True, padx=20, pady=6)

        d_head = ctk.CTkFrame(card_d, fg_color="transparent")
        d_head.pack(fill="x", padx=16, pady=(10, 4))
        self.lbl_desc_header = ctk.CTkLabel(
            d_head, text="DESCRIPCIÓN Y METADATOS [ES]", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C_PURPLE
        )
        self.lbl_desc_header.pack(side="left")

        self.txt_desc = ctk.CTkTextbox(
            card_d, fg_color=C_INPUT, border_color=C_BORDER, border_width=1, text_color=C_TEXT_MAIN, font=ctk.CTkFont(size=11), wrap="word", corner_radius=8
        )
        self.txt_desc.pack(fill="both", expand=True, padx=16, pady=4)

        ctk.CTkButton(
            card_d, text="Copiar Descripción", height=28, width=140, fg_color="#333A4A", hover_color="#3F475A",
            text_color=C_TEXT_MAIN, corner_radius=6, command=self._copiar_descripcion
        ).pack(anchor="e", padx=16, pady=(2, 10))

        # Tarjeta de Horarios Informativa
        note_card = ctk.CTkFrame(
            self.col2, fg_color=C_CARD, corner_radius=12, border_color=C_BORDER, border_width=1
        )
        note_card.pack(fill="x", padx=20, pady=4)

        note_head = ctk.CTkFrame(note_card, fg_color="transparent")
        note_head.pack(fill="x", padx=16, pady=(8, 4))
        ctk.CTkLabel(
            note_head, text="SCHEDULE & SLOTS RECOMENDADOS", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C_AMBER
        )
        note_head.pack(anchor="w")

        slots_grid = ctk.CTkFrame(note_card, fg_color="transparent")
        slots_grid.pack(fill="x", padx=12, pady=(0, 10))

        for tag, hora, contexto in HORARIOS_INFO:
            b_frame = ctk.CTkFrame(
                slots_grid, fg_color=C_INPUT, corner_radius=8, border_color=C_BORDER, border_width=1
            )
            b_frame.pack(side="left", expand=True, fill="x", padx=4, pady=2)
            ctk.CTkLabel(
                b_frame, text=hora, font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=C_TEXT_MAIN
            ).pack(pady=(4, 0))
            ctk.CTkLabel(
                b_frame, text=contexto, font=ctk.CTkFont(size=9), text_color=C_TEXT_MUTED
            ).pack(pady=(0, 4))

        # Botón Limpieza
        self.btn_limpieza = ctk.CTkButton(
            self.col2,
            text="Liberar Espacio (Conservar Ambos Videos Finales)",
            height=38,
            fg_color=C_DANGER,
            hover_color=C_DANGER_HOVER,
            text_color="#FFFFFF",
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", weight="bold", size=12),
            command=self._limpiar_archivos_disco,
        )
        self.btn_limpieza.pack(fill="x", padx=20, pady=(8, 20))

        # ========================================================
        # COLUMNA 3: MONITOR & ÁLBUM DE ESCENAS
        # ========================================================
        self.col3 = ctk.CTkFrame(
            self, width=470, fg_color=C_SURFACE, corner_radius=18, border_color=C_BORDER, border_width=1
        )
        self.col3.grid(row=0, column=2, padx=(8, 16), pady=16, sticky="nsew")
        self.col3.grid_propagate(False)

        hdr_3 = ctk.CTkFrame(self.col3, fg_color="transparent")
        hdr_3.pack(fill="x", padx=20, pady=(20, 6))

        self.lbl_media_title = ctk.CTkLabel(
            hdr_3, text="Monitor & Álbum HD", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color=C_TEXT_MAIN
        )
        self.lbl_media_title.pack(anchor="w")

        self.lbl_media_badge = ctk.CTkLabel(
            hdr_3, text="● EN ESPERA", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C_TEXT_MUTED
        )
        self.lbl_media_badge.pack(anchor="w")

        # Visor 9:16
        self.preview_frame = ctk.CTkFrame(
            self.col3, fg_color=C_INPUT, corner_radius=14, border_color=C_BORDER, border_width=1, height=440
        )
        self.preview_frame.pack(fill="x", padx=20, pady=(6, 6))
        self.preview_frame.pack_propagate(False)

        self.lbl_canvas_preview = ctk.CTkLabel(
            self.preview_frame, text="Esperando render de imágenes...", text_color=C_TEXT_MUTED, font=ctk.CTkFont(size=12)
        )
        self.lbl_canvas_preview.place(relx=0.5, rely=0.5, anchor="center")

        # Botón para Full Resolución
        self.btn_ver_full = ctk.CTkButton(
            self.col3,
            text="🔍 Ver a Resolución Completa (1024x1792)",
            height=32,
            fg_color=C_CARD,
            hover_color=C_CARD_HOVER,
            border_color=C_BORDER,
            border_width=1,
            text_color=C_TEXT_MAIN,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            state="disabled",
            command=self._abrir_visor_hd,
        )
        self.btn_ver_full.pack(fill="x", padx=20, pady=(2, 6))

        # Tira / Álbum Horizontal de Miniaturas
        ctk.CTkLabel(
            self.col3,
            text="GALERÍA DE ESCENAS GENERADAS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C_TEXT_MUTED,
        ).pack(anchor="w", padx=20, pady=(6, 2))

        self.album_scroll = ctk.CTkScrollableFrame(
            self.col3, fg_color=C_INPUT, corner_radius=10, border_color=C_BORDER, border_width=1, height=135, orientation="horizontal"
        )
        self.album_scroll.pack(fill="x", padx=20, pady=(2, 8))

        self.botones_miniaturas: list[ctk.CTkButton] = []

        # Botón de reproducción de video
        ctrl_box = ctk.CTkFrame(self.col3, fg_color="transparent")
        ctrl_box.pack(fill="x", padx=20, pady=(4, 20), side="bottom")

        self.btn_toggle_video = ctk.CTkButton(
            ctrl_box,
            text="Previsualizar Short Activo",
            height=42,
            fg_color=C_CARD,
            hover_color=C_CARD_HOVER,
            text_color=C_TEXT_MUTED,
            corner_radius=8,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            state="disabled",
            command=self._abrir_video_reproductor,
        )
        self.btn_toggle_video.pack(fill="x")

    # ========================================================
    # HELPER DE LIMPIEZA SEGURO (EVITA TCLERROR)
    # ========================================================
    def _limpiar_monitor_preview(self, mensaje: str):
        try:
            img_vacia = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
            ctk_vacia = ctk.CTkImage(light_image=img_vacia, dark_image=img_vacia, size=(1, 1))
            self.lbl_canvas_preview.configure(image=ctk_vacia, text=mensaje)
            self.lbl_canvas_preview.image = ctk_vacia
        except Exception:
            try:
                self.lbl_canvas_preview.configure(text=mensaje)
            except Exception:
                pass

        for btn in self.botones_miniaturas:
            btn.destroy()
        self.botones_miniaturas.clear()
        self.imagenes_generadas.clear()
        self.btn_ver_full.configure(state="disabled")

    # ========================================================
    # TELEMETRÍA Y CONTROL
    # ========================================================
    def _log_directo(self, texto: str):
        try:
            self.after(0, lambda: self.log(texto))
        except Exception:
            pass

    def log(self, texto: str):
        self.txt_logs.insert("end", f"> {texto}\n")
        self.txt_logs.see("end")

        texto_limpio = texto.strip()
        resumen = texto_limpio[:42] + "..." if len(texto_limpio) > 45 else texto_limpio
        self.lbl_status_text.configure(text=resumen)

    def _actualizar_progreso_video(self, pct: int, frame: int, total: int):
        def ui_update():
            progreso_global = 0.70 + (pct / 100.0) * 0.15
            self.progress_bar.set(progreso_global)
            self.lbl_status_text.configure(text=f"Render Video: {pct}% ({frame}/{total})")
        self.after(0, ui_update)

    def _cambiar_pestana_idioma(self, valor: str):
        self.canal_activo = "en" if "EN" in valor else "es"
        idioma_tag = "[EN 🇺🇸 - The Black Box Archives]" if self.canal_activo == "en" else "[ES 🇪🇸 - La Caja Negra]"
        self.lbl_titulo_header.configure(text=f"TÍTULO + HASHTAGS {idioma_tag}")
        self.lbl_desc_header.configure(text=f"DESCRIPCIÓN Y METADATOS {idioma_tag}")

        if self.ultimo_nombre_raiz:
            self._cargar_metadata_canal(self.canal_activo)

    def _cargar_metadata_canal(self, canal: str):
        if not self.ultimo_nombre_raiz:
            return
        ruta_meta = BASE_DIR / "outputs" / "metadata" / f"{self.ultimo_nombre_raiz}_{canal}_para_publicar.txt"
        self._actualizar_campos_metadata(ruta_meta)

        video_path = self.ultimo_video_path_en if canal == "en" else self.ultimo_video_path_es
        if video_path and video_path.exists():
            nombre_label = "The Black Box Archives (EN)" if canal == "en" else "La Caja Negra (ES)"
            self.btn_toggle_video.configure(
                state="normal",
                text=f"▶ Reproducir Short: {nombre_label}",
                fg_color="#059669",
                hover_color="#047857",
                text_color="#FFFFFF",
            )
        else:
            self.btn_toggle_video.configure(state="disabled", text="Video no disponible", fg_color=C_CARD, text_color=C_TEXT_MUTED)

    def _iniciar_produccion_hilo(self):
        if self.is_running:
            return
        self.is_running = True

        self.ultimo_nombre_raiz = None
        self.ultimo_video_path_es = None
        self.ultimo_video_path_en = None
        self._limpiar_monitor_preview("Iniciando pipeline bilingüe...")

        self.btn_generar.configure(state="disabled", text="Procesando Pipeline Bilingüe...", fg_color="#1F2937")
        self.btn_toggle_video.configure(state="disabled", text="Generando Shorts...", fg_color=C_CARD, text_color=C_TEXT_MUTED)
        self.led_indicator.configure(text="● GENERANDO", text_color=C_TEAL)
        self.lbl_media_badge.configure(text="PREPARANDO GUIONES BILINGÜES", text_color=C_TEAL)
        self.progress_bar.set(0.05)

        hilo = threading.Thread(target=self._pipeline_worker, daemon=True)
        hilo.start()

    def _pipeline_worker(self):
        try:
            self.log("Consultando Groq con rotación temática (10 categorías)...")
            tema, indice_cat = pipeline_main.obtener_tema_automatico()
            self.log(f"Tema seleccionado: '{tema}'")

            self.progress_bar.set(0.12)

            # 1. Guiones ES y EN
            self.log("Generando guion [ES] con Groq (~180-200 palabras)...")
            res_guion_es = generar_guion(tema, minimo=180, maximo=200)
            self.log("Adaptando guion [EN] para 'The Black Box Archives'...")
            res_guion_en = traducir_guion_a_ingles(res_guion_es)

            ruta_json_es = guardar_guion(res_guion_es, sufijo="_es")
            ruta_json_en = guardar_guion(res_guion_en, sufijo="_en")

            nombre_raiz = ruta_json_es.stem.removesuffix("_es")
            self.ultimo_nombre_raiz = nombre_raiz

            datos_g_es = res_guion_es["guion"]
            titulo_es = datos_g_es["titulo"]
            narracion_es = datos_g_es["narracion"]
            narracion_v_es = narracion_es.removesuffix(" " + CIERRE_VIDEO_ES).rstrip()

            datos_g_en = res_guion_en["guion"]
            titulo_en = datos_g_en["titulo"]
            narracion_en = datos_g_en["narracion"]

            self.progress_bar.set(0.25)

            # 2. Generar 12 Imágenes con ComfyUI (Reutilizadas para ambos idiomas)
            self.lbl_media_badge.configure(text="RENDERIZANDO EN COMFYUI", text_color=C_PURPLE)
            stop_watcher = threading.Event()
            watcher_thread = threading.Thread(
                target=self._vigilar_imagenes_en_directo, args=(nombre_raiz, stop_watcher), daemon=True
            )
            watcher_thread.start()

            self.log("Renderizando secuencia compartida de 12 escenas en ComfyUI SDXL...")
            generar_secuencia_imagenes(narracion_v_es, titulo_es, nombre_base=nombre_raiz, total_escenas=12)
            stop_watcher.set()

            self.progress_bar.set(0.55)

            # 3. Síntesis de Audio Bilingüe
            self.log("Sintetizando voz en off [ES] con Álvaro...")
            ruta_audio_es = convertir_texto_a_voz(narracion_es, nombre_base=f"{nombre_raiz}_es", idioma="es")
            clip_es = pipeline_main.mp.AudioFileClip(str(ruta_audio_es))
            duracion_es = clip_es.duration
            clip_es.close()

            self.log("Sintetizando voz en off [EN] con Christopher...")
            ruta_audio_en = convertir_texto_a_voz(narracion_en, nombre_base=f"{nombre_raiz}_en", idioma="en")
            clip_en = pipeline_main.mp.AudioFileClip(str(ruta_audio_en))
            duracion_en = clip_en.duration
            clip_en.close()

            self.progress_bar.set(0.70)

            # 4. Montaje de Videos Base
            self.log("Montando video base [ES]...")
            logger_moviepy = MoviePyCallbackLogger(self._actualizar_progreso_video)
            ruta_base_es = montar_video_final(f"{nombre_raiz}_es", duracion_es, custom_logger=logger_moviepy, idioma="es")

            self.log("Montando video base [EN]...")
            ruta_base_en = montar_video_final(f"{nombre_raiz}_en", duracion_en, custom_logger=logger_moviepy, idioma="en")

            self.progress_bar.set(0.85)

            # 5. Quemado de Subtítulos con Whisper
            self.log("Quemando subtítulos en español con Whisper...")
            ruta_final_es = agregar_subtitulos_al_video(ruta_base_es, ruta_audio_es, idioma="es")

            self.log("Quemando subtítulos en inglés con Whisper...")
            ruta_final_en = agregar_subtitulos_al_video(ruta_base_en, ruta_audio_en, idioma="en")

            pipeline_main.eliminar_copias_base_subtituladas(ruta_final_es)
            pipeline_main.eliminar_copias_base_subtituladas(ruta_final_en)

            self.ultimo_video_path_es = ruta_final_es
            self.ultimo_video_path_en = ruta_final_en

            # 6. Metadatos Bilingües y Registro
            self.log("Generando archivos de metadatos independientes (ES & EN)...")
            generar_archivo_metadata(titulo_es, tema, f"{nombre_raiz}_es", idioma="es")
            generar_archivo_metadata(titulo_en, tema, f"{nombre_raiz}_en", idioma="en")

            if indice_cat != -1:
                pipeline_main.registrar_tema_en_historial(tema, indice_cat)

            self.progress_bar.set(1.0)
            self.led_indicator.configure(text="● COMPLETADO", text_color=C_EMERALD)
            self.lbl_media_badge.configure(text="2 VIDEOS PRODUCIDOS CON ÉXITO", text_color=C_EMERALD)
            self.log("✔ PROCESO BILINGÜE FINALIZADO. Ambos Shorts listos para publicación.")

            self.after(100, lambda: self._cargar_metadata_canal(self.canal_activo))

        except Exception as e:
            self.led_indicator.configure(text="● ERROR", text_color=C_DANGER)
            self.lbl_media_badge.configure(text="ERROR EN PRODUCCIÓN", text_color=C_DANGER)
            self.log(f"❌ Fallo crítico en el proceso: {e}")
        finally:
            self.is_running = False
            self.btn_generar.configure(state="normal", text="⚡ Iniciar Producción Cíclica (ES + EN)", fg_color="#0F766E")

    # ========================================================
    # MONITOR Y ÁLBUM DE ESCENAS
    # ========================================================
    def _vigilar_imagenes_en_directo(self, nombre_base: str, stop_event: threading.Event):
        img_dir = BASE_DIR / "outputs" / "images"
        imagenes_mostradas = set()

        while not stop_event.is_set():
            if img_dir.exists():
                encontradas = sorted(
                    img_dir.glob(f"{nombre_base}_escena_*.jpg"),
                    key=lambda p: int(p.stem.split("_escena_")[-1]) if "_escena_" in p.stem else 0,
                )
                for img_path in encontradas:
                    if img_path not in imagenes_mostradas:
                        imagenes_mostradas.add(img_path)
                        num = int(img_path.stem.split("_escena_")[-1]) if "_escena_" in img_path.stem else len(imagenes_mostradas)
                        self.after(0, self._agregar_imagen_a_album, img_path, num)
            time.sleep(0.8)

    def _agregar_imagen_a_album(self, ruta_img: Path, num_escena: int):
        if ruta_img not in self.imagenes_generadas:
            self.imagenes_generadas.append(ruta_img)

        idx = len(self.imagenes_generadas) - 1
        self.indice_imagen_activa = idx

        self._mostrar_imagen_en_canvas(ruta_img, f"Escena {num_escena}/12 generada")
        self.btn_ver_full.configure(state="normal")

        try:
            pil_thumb = Image.open(ruta_img)
            pil_thumb = pil_thumb.resize((65, 115), Image.Resampling.LANCZOS)
            ctk_thumb = ctk.CTkImage(light_image=pil_thumb, dark_image=pil_thumb, size=(65, 115))

            btn_thumb = ctk.CTkButton(
                self.album_scroll,
                image=ctk_thumb,
                text=f"E{num_escena}",
                compound="top",
                width=70,
                height=125,
                fg_color=C_CARD,
                hover_color=C_CARD_HOVER,
                border_color=C_BORDER,
                border_width=1,
                corner_radius=8,
                font=ctk.CTkFont(size=9, weight="bold"),
                command=lambda i=idx, r=ruta_img, n=num_escena: self._seleccionar_desde_album(i, r, n)
            )
            btn_thumb.pack(side="left", padx=4, pady=2)
            self.botones_miniaturas.append(btn_thumb)
        except Exception:
            pass

    def _seleccionar_desde_album(self, indice: int, ruta_img: Path, num_escena: int):
        self.indice_imagen_activa = indice
        self._mostrar_imagen_en_canvas(ruta_img, f"Escena {num_escena}/12 seleccionada")

    def _mostrar_imagen_en_canvas(self, ruta_img: Path, subtexto: str = ""):
        try:
            pil_img = Image.open(ruta_img)
            w, h = 240, 426
            pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))

            self.lbl_canvas_preview.configure(image=ctk_img, text="")
            self.lbl_canvas_preview.image = ctk_img
            if subtexto:
                self.lbl_media_badge.configure(text=subtexto.upper(), text_color=C_TEAL)
        except Exception:
            pass

    def _abrir_visor_hd(self):
        if not self.imagenes_generadas:
            return
        VisorFullResolucion(self, self.imagenes_generadas, self.indice_imagen_activa)

    def _abrir_video_reproductor(self):
        video_actual = self.ultimo_video_path_en if self.canal_activo == "en" else self.ultimo_video_path_es
        if video_actual and video_actual.exists():
            try:
                os.startfile(str(video_actual))
                self.log(f"🎬 Abriendo reproductor: {video_actual.name}")
            except Exception as err:
                self.log(f"⚠️ Error al abrir reproductor de Windows: {err}")
        else:
            self.log("⚠️ No hay video activo para reproducir en este canal.")

    # ========================================================
    # METADATOS Y ACCIONES
    # ========================================================
    def _actualizar_campos_metadata(self, ruta_txt: Path):
        try:
            if not ruta_txt.exists():
                return
            lineas = ruta_txt.read_text(encoding="utf-8").splitlines()
            tit = ""
            desc = []
            capturar = False

            for i, l in enumerate(lineas):
                if ("📋 COPIAR Y PEGAR RÁPIDO" in l or "QUICK COPY-PASTE" in l) and i + 1 < len(lineas):
                    tit = lineas[i + 1].strip()
                if "📝 DESCRIPCIÓN COMPLETA:" in l or "FULL DESCRIPTION:" in l:
                    capturar = True
                    continue
                if capturar:
                    if "--------------------------------------------------" in l:
                        capturar = False
                        continue
                    desc.append(l)

            self.entry_titulo.delete(0, "end")
            self.entry_titulo.insert(0, tit)
            caracteres = len(tit)
            self.lbl_char_count.configure(
                text=f"{caracteres}/100",
                text_color=C_DANGER if caracteres > 100 else C_TEXT_MUTED,
            )

            self.txt_desc.delete("1.0", "end")
            self.txt_desc.insert("1.0", "\n".join(desc).strip())
        except Exception as err:
            self.log(f"⚠️ Error cargando metadata: {err}")

    def _copiar_titulo(self):
        t = self.entry_titulo.get().strip()
        if t:
            pyperclip.copy(t)
            self.log(f"📋 Título [{self.canal_activo.upper()}] copiado al portapapeles.")

    def _copiar_descripcion(self):
        d = self.txt_desc.get("1.0", "end").strip()
        if d:
            pyperclip.copy(d)
            self.log(f"📋 Descripción [{self.canal_activo.upper()}] copiada al portapapeles.")

    def _limpiar_archivos_disco(self):
        if not self.ultimo_nombre_raiz:
            self.log("⚠️ No hay elementos en buffer para limpiar.")
            return

        nb = self.ultimo_nombre_raiz

        rutas_temporales = [
            BASE_DIR / "outputs" / "audio" / f"{nb}_es.mp3",
            BASE_DIR / "outputs" / "audio" / f"{nb}_en.mp3",
            BASE_DIR / "outputs" / "json" / f"{nb}_es.json",
            BASE_DIR / "outputs" / "json" / f"{nb}_en.json",
            BASE_DIR / "outputs" / "metadata" / f"{nb}_es_para_publicar.txt",
            BASE_DIR / "outputs" / "metadata" / f"{nb}_en_para_publicar.txt",
            BASE_DIR / "outputs" / "prompts" / f"{nb}_prompts.json",
        ]

        eliminados = 0
        for f in rutas_temporales:
            if f.exists():
                f.unlink(missing_ok=True)
                eliminados += 1

        img_dir = BASE_DIR / "outputs" / "images"
        if img_dir.exists():
            for img in img_dir.glob(f"{nb}_escena_*.jpg"):
                img.unlink(missing_ok=True)
                eliminados += 1

        self.log(f"🧹 Purgados {eliminados} archivos temporales. Ambos videos finales conservados en outputs/videos.")
        self.entry_titulo.delete(0, "end")
        self.txt_desc.delete("1.0", "end")
        self.lbl_char_count.configure(text="0/100", text_color=C_TEXT_MUTED)
        self._limpiar_monitor_preview(f"Temporales purgados.\nVideos conservados:\noutputs/videos/{nb}_es_subtitulado.mp4\noutputs/videos/{nb}_en_subtitulado.mp4")
        self.ultimo_nombre_raiz = None


if __name__ == "__main__":
    app = CajaNegraStudio()
    app.mainloop()