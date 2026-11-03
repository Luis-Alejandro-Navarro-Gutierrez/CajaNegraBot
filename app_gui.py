"""
CAJANEGRABOT // YOUTUBE SHORTS CREATOR STUDIO PRO
Tema Slate Charcoal profesional, reinicio seguro de buffers visuales y reproducción bajo demanda.
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

# Importaciones del pipeline
import main as pipeline_main
from generator import CIERRE_VIDEO, generar_guion, guardar_guion
from tts import convertir_texto_a_voz
from images import generar_secuencia_imagenes
from video import montar_video_final
from subtitles import agregar_subtitulos_al_video
from metadata import generar_archivo_metadata

# ========================================================
# PALETA HÍBRIDA: CHARCOAL & SLATE (DESCANSO VISUAL)
# ========================================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C_BG = "#0B0F19"             # Azul noche mate / Charcoal
C_SURFACE = "#111827"        # Pizarra oscura mate
C_CARD = "#1F2937"           # Gris carbón intermedio
C_INPUT = "#161F30"          # Fondo de campos de texto
C_BORDER = "#374151"         # Líneas sutiles sin encandilar

C_TEXT_MAIN = "#F9FAFB"      # Blanco hueso
C_TEXT_BODY = "#D1D5DB"      # Gris claro de lectura
C_TEXT_MUTED = "#9CA3AF"     # Gris atenuado secundario

C_PRIMARY = "#3B82F6"        # Azul sobrio
C_PRIMARY_HOVER = "#2563EB"
C_DANGER = "#EF4444"         # Rojo funcional
C_DANGER_HOVER = "#DC2626"
C_SUCCESS = "#10B981"        # Verde esmeralda

HORARIOS_SLOTS = [
    ("Slot 01", "08:30 AM", "Tráfico Matutino & Despertar"),
    ("Slot 02", "11:45 AM", "Hora Almuerzo / Break"),
    ("Slot 03", "02:45 PM", "Pausa Tarde / Desconexión"),
    ("Slot 04", "06:00 PM", "Regreso a Casa & Ocio"),
    ("Slot 05", "08:45 PM", "Prime Time Nocturno"),
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


class CajaNegraStudio(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CajaNegra Studio // Shorts Automation Suite")
        self.geometry("1480x860")
        self.minsize(1380, 800)
        self.configure(fg_color=C_BG)

        self.ultimo_nombre_base = None
        self.ultimo_video_path = None
        self.is_running = False

        self._construir_layout()

        sys.stdout = StreamRedirector(self._log_directo)
        sys.stderr = StreamRedirector(self._log_directo)

    def _construir_layout(self):
        self.grid_columnconfigure(0, weight=0, minsize=460)
        self.grid_columnconfigure(1, weight=1, minsize=520)
        self.grid_columnconfigure(2, weight=0, minsize=380)
        self.grid_rowconfigure(0, weight=1)

        # ========================================================
        # COLUMNA 1: PRODUCCIÓN Y TELEMETRÍA
        # ========================================================
        self.col1 = ctk.CTkFrame(
            self, width=460, fg_color=C_SURFACE, corner_radius=12, border_color=C_BORDER, border_width=1
        )
        self.col1.grid(row=0, column=0, padx=(16, 8), pady=16, sticky="nsew")
        self.col1.grid_propagate(False)

        hdr_1 = ctk.CTkFrame(self.col1, fg_color="transparent")
        hdr_1.pack(fill="x", padx=18, pady=(18, 6))

        ctk.CTkLabel(
            hdr_1,
            text="PIPELINE DE PRODUCCIÓN",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C_PRIMARY,
            fg_color="#1E3A8A",
            corner_radius=6,
            padx=8,
            pady=3,
        ).pack(anchor="w")

        ctk.CTkLabel(
            hdr_1,
            text="CajaNegra Studio",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=C_TEXT_MAIN,
        ).pack(anchor="w", pady=(6, 0))

        # Tarjeta Input
        card_in = ctk.CTkFrame(self.col1, fg_color=C_CARD, corner_radius=10, border_color=C_BORDER, border_width=1)
        card_in.pack(fill="x", padx=18, pady=8)

        ctk.CTkLabel(
            card_in,
            text="DIRECTRIZ DE TEMA",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=C_TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(10, 4))

        self.tema_entry = ctk.CTkEntry(
            card_in,
            placeholder_text="Dejar en blanco para rotación cíclica (10 categorías)...",
            height=38,
            fg_color=C_INPUT,
            border_color=C_BORDER,
            text_color=C_TEXT_MAIN,
            font=ctk.CTkFont(size=12),
        )
        self.tema_entry.pack(fill="x", padx=14, pady=(0, 10))

        self.btn_generar = ctk.CTkButton(
            card_in,
            text="Iniciar Producción",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            height=40,
            fg_color=C_PRIMARY,
            hover_color=C_PRIMARY_HOVER,
            command=self._iniciar_produccion_hilo,
        )
        self.btn_generar.pack(fill="x", padx=14, pady=(0, 14))

        # Estado y progreso
        stat_box = ctk.CTkFrame(self.col1, fg_color="transparent")
        stat_box.pack(fill="x", padx=18, pady=2)

        self.led_indicator = ctk.CTkLabel(
            stat_box, text="● EN ESPERA", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"), text_color=C_SUCCESS
        )
        self.led_indicator.pack(side="left")

        self.lbl_status_text = ctk.CTkLabel(
            stat_box, text="Listo", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=C_TEXT_MUTED, width=280, anchor="e"
        )
        self.lbl_status_text.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(self.col1, height=6, fg_color="#1E293B", progress_color=C_PRIMARY)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=18, pady=(4, 10))

        ctk.CTkLabel(
            self.col1,
            text="CONSOLA DE SALIDA Y TELEMETRÍA",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=C_TEXT_MUTED,
        ).pack(anchor="w", padx=18, pady=(4, 4))

        self.txt_logs = ctk.CTkTextbox(
            self.col1,
            fg_color="#0F172A",
            text_color="#93C5FD",
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=8,
            border_color=C_BORDER,
            border_width=1,
            wrap="char",
        )
        self.txt_logs.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        # ========================================================
        # COLUMNA 2: GESTIÓN DE PUBLICACIÓN & YOUTUBE
        # ========================================================
        self.col2 = ctk.CTkFrame(
            self, fg_color=C_SURFACE, corner_radius=12, border_color=C_BORDER, border_width=1
        )
        self.col2.grid(row=0, column=1, padx=8, pady=16, sticky="nsew")

        ctk.CTkLabel(
            self.col2,
            text="Centro de Publicación",
            font=ctk.CTkFont(family="Segoe UI", size=22, weight="bold"),
            text_color=C_TEXT_MAIN,
        ).pack(anchor="w", padx=18, pady=(18, 6))

        # Título
        card_t = ctk.CTkFrame(self.col2, fg_color=C_CARD, corner_radius=10, border_color=C_BORDER, border_width=1)
        card_t.pack(fill="x", padx=18, pady=4)

        t_head = ctk.CTkFrame(card_t, fg_color="transparent")
        t_head.pack(fill="x", padx=12, pady=(6, 2))
        ctk.CTkLabel(t_head, text="TÍTULO + HASHTAGS", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#60A5FA").pack(side="left")
        self.lbl_char_count = ctk.CTkLabel(t_head, text="0/100", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=C_TEXT_MUTED)
        self.lbl_char_count.pack(side="right")

        self.entry_titulo = ctk.CTkEntry(card_t, height=34, fg_color=C_INPUT, border_color=C_BORDER, text_color=C_TEXT_MAIN, font=ctk.CTkFont(size=11))
        self.entry_titulo.pack(fill="x", padx=12, pady=2)

        ctk.CTkButton(card_t, text="Copiar Título", height=24, fg_color="#374151", hover_color="#4B5563", text_color=C_TEXT_MAIN, command=self._copiar_titulo).pack(anchor="e", padx=12, pady=(2, 6))

        # Descripción
        card_d = ctk.CTkFrame(self.col2, fg_color=C_CARD, corner_radius=10, border_color=C_BORDER, border_width=1)
        card_d.pack(fill="both", expand=True, padx=18, pady=6)

        d_head = ctk.CTkFrame(card_d, fg_color="transparent")
        d_head.pack(fill="x", padx=12, pady=(8, 2))
        ctk.CTkLabel(d_head, text="DESCRIPCIÓN Y METADATOS", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#60A5FA").pack(side="left")

        self.txt_desc = ctk.CTkTextbox(card_d, fg_color=C_INPUT, border_color=C_BORDER, border_width=1, text_color=C_TEXT_MAIN, font=ctk.CTkFont(size=11), wrap="word")
        self.txt_desc.pack(fill="both", expand=True, padx=12, pady=4)

        ctk.CTkButton(card_d, text="Copiar Descripción", height=24, fg_color="#374151", hover_color="#4B5563", text_color=C_TEXT_MAIN, command=self._copiar_descripcion).pack(anchor="e", padx=12, pady=(2, 8))

        # Slots
        card_s = ctk.CTkFrame(self.col2, fg_color=C_CARD, corner_radius=10, border_color=C_BORDER, border_width=1)
        card_s.pack(fill="x", padx=18, pady=4)

        ctk.CTkLabel(card_s, text="HORARIOS PROGRAMADOS (A DÍA VENCIDO)", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color="#F59E0B").pack(anchor="w", padx=12, pady=(6, 2))

        self.slot_checkboxes = []
        for slot_tag, hora, contexto in HORARIOS_SLOTS:
            r_s = ctk.CTkFrame(card_s, fg_color=C_INPUT, corner_radius=6, border_color=C_BORDER, border_width=1)
            r_s.pack(fill="x", padx=12, pady=2)

            cb = ctk.CTkCheckBox(
                r_s, text=f"{hora} [{slot_tag}]", font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                checkbox_height=16, checkbox_width=16, border_color="#64748B", fg_color=C_PRIMARY, text_color=C_TEXT_MAIN
            )
            cb.pack(side="left", padx=8, pady=3)
            ctk.CTkLabel(r_s, text=f"— {contexto}", font=ctk.CTkFont(size=10), text_color=C_TEXT_MUTED).pack(side="left")
            self.slot_checkboxes.append(cb)

        # Botón de limpieza selectiva
        actions_row = ctk.CTkFrame(self.col2, fg_color="transparent")
        actions_row.pack(fill="x", padx=18, pady=(8, 18))
        actions_row.grid_columnconfigure(0, weight=1)

        self.btn_limpieza = ctk.CTkButton(
            actions_row,
            text="Liberar Espacio (Conservar Video Final)",
            height=36,
            fg_color=C_DANGER,
            hover_color=C_DANGER_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(family="Segoe UI", weight="bold", size=11),
            command=self._limpiar_archivos_disco,
        )
        self.btn_limpieza.grid(row=0, column=0, sticky="ew")

        # ========================================================
        # COLUMNA 3: PREVIEW EN VIVO Y MONITOR 9:16
        # ========================================================
        self.col3 = ctk.CTkFrame(
            self, width=380, fg_color=C_SURFACE, corner_radius=12, border_color=C_BORDER, border_width=1
        )
        self.col3.grid(row=0, column=2, padx=(8, 16), pady=16, sticky="nsew")
        self.col3.grid_propagate(False)

        hdr_3 = ctk.CTkFrame(self.col3, fg_color="transparent")
        hdr_3.pack(fill="x", padx=18, pady=(18, 6))

        self.lbl_media_title = ctk.CTkLabel(
            hdr_3, text="Monitor de Escenas", font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"), text_color=C_TEXT_MAIN
        )
        self.lbl_media_title.pack(anchor="w")

        self.lbl_media_badge = ctk.CTkLabel(
            hdr_3, text="EN ESPERA", font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"), text_color=C_TEXT_MUTED
        )
        self.lbl_media_badge.pack(anchor="w")

        # Marco vertical para la imagen
        self.preview_frame = ctk.CTkFrame(
            self.col3, fg_color="#0F172A", corner_radius=10, border_color=C_BORDER, border_width=1
        )
        self.preview_frame.pack(fill="both", expand=True, padx=18, pady=8)

        self.lbl_canvas_preview = ctk.CTkLabel(
            self.preview_frame, text="Esperando render de imágenes...", text_color=C_TEXT_MUTED, font=ctk.CTkFont(size=12)
        )
        self.lbl_canvas_preview.place(relx=0.5, rely=0.5, anchor="center")

        ctrl_box = ctk.CTkFrame(self.col3, fg_color="transparent")
        ctrl_box.pack(fill="x", padx=18, pady=(4, 18))

        self.btn_toggle_video = ctk.CTkButton(
            ctrl_box,
            text="Previsualizar Short",
            height=38,
            fg_color="#1E293B",
            hover_color="#1E293B",
            text_color="#64748B",
            font=ctk.CTkFont(family="Segoe UI", weight="bold"),
            state="disabled",
            command=self._abrir_video_reproductor,
        )
        self.btn_toggle_video.pack(fill="x", pady=2)

    # ========================================================
    # HELPER SEGURO PARA VACIAR EL CANVAS (EVITA TCLERROR)
    # ========================================================
    def _limpiar_monitor_preview(self, mensaje: str):
        """Resetea el widget de vista previa sin provocar fallos pyimage en Tkinter."""
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

    # ========================================================
    # TELEMETRÍA Y CONTROL DE PROGRESO
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
        resumen = texto_limpio[:39] + "..." if len(texto_limpio) > 42 else texto_limpio
        self.lbl_status_text.configure(text=resumen)

    def _actualizar_progreso_video(self, pct: int, frame: int, total: int):
        def ui_update():
            progreso_global = 0.75 + (pct / 100.0) * 0.13
            self.progress_bar.set(progreso_global)
            self.lbl_status_text.configure(text=f"Renderizando Video: {pct}% ({frame}/{total})")
        self.after(0, ui_update)

    def _iniciar_produccion_hilo(self):
        if self.is_running:
            return
        self.is_running = True

        # Reset seguro sin colisión de imágenes en Tcl
        self.ultimo_nombre_base = None
        self.ultimo_video_path = None
        self._limpiar_monitor_preview("Iniciando pipeline en ComfyUI...")

        self.btn_generar.configure(state="disabled", text="Procesando Pipeline...", fg_color="#334155")
        self.btn_toggle_video.configure(state="disabled", text="Generando Short...", fg_color="#1E293B", text_color="#64748B")
        self.led_indicator.configure(text="● GENERANDO", text_color=C_PRIMARY)
        self.lbl_media_badge.configure(text="PREPARANDO GUION Y VOZ", text_color=C_PRIMARY)
        self.progress_bar.set(0.05)

        hilo = threading.Thread(target=self._pipeline_worker, daemon=True)
        hilo.start()

    def _pipeline_worker(self):
        try:
            tema_manual = self.tema_entry.get().strip()

            if tema_manual:
                tema = tema_manual
                indice_cat = -1
                self.log(f"Tema manual: '{tema}'")
            else:
                self.log("Consultando Groq con rotación temática (10 categorías)...")
                tema, indice_cat = pipeline_main.obtener_tema_automatico()
                self.log(f"Tema seleccionado: '{tema}'")

            self.progress_bar.set(0.15)

            # 1. Guion
            self.log("Generando guion con Groq (~180-200 palabras)...")
            res_guion = generar_guion(tema, minimo=180, maximo=200)
            ruta_json = guardar_guion(res_guion)
            datos_g = res_guion["guion"]
            titulo = datos_g["titulo"]
            narracion = datos_g["narracion"]
            narracion_v = narracion.removesuffix(" " + CIERRE_VIDEO).rstrip()
            nombre_base = ruta_json.stem
            self.ultimo_nombre_base = nombre_base

            self.progress_bar.set(0.30)

            # 2. Audio
            self.log("Sintetizando voz en off con Álvaro (Edge-TTS)...")
            ruta_audio = convertir_texto_a_voz(narracion, nombre_base=nombre_base)
            clip = pipeline_main.mp.AudioFileClip(str(ruta_audio))
            duracion = clip.duration
            clip.close()

            self.progress_bar.set(0.45)

            # 3. ComfyUI con Live Feed
            self.lbl_media_badge.configure(text="RENDERIZANDO EN COMFYUI", text_color=C_PRIMARY)
            stop_watcher = threading.Event()
            watcher_thread = threading.Thread(
                target=self._vigilar_imagenes_en_directo, args=(nombre_base, stop_watcher), daemon=True
            )
            watcher_thread.start()

            self.log("Renderizando secuencia de 12 escenas en ComfyUI...")
            generar_secuencia_imagenes(narracion_v, titulo, nombre_base=nombre_base, total_escenas=12)
            stop_watcher.set()

            self.progress_bar.set(0.75)

            # 4. Montaje video base
            self.log("Montando video vertical con animación Ken Burns...")
            logger_moviepy = MoviePyCallbackLogger(self._actualizar_progreso_video)
            ruta_base = montar_video_final(nombre_base, duracion, custom_logger=logger_moviepy)

            self.progress_bar.set(0.88)

            # 5. Subtítulos
            self.log("Quemando subtítulos dinámicos con Whisper...")
            ruta_final = agregar_subtitulos_al_video(ruta_base, ruta_audio)
            pipeline_main.eliminar_copias_base_subtituladas(ruta_final)
            self.ultimo_video_path = ruta_final

            # 6. Metadatos
            self.log("Generando archivo de metadatos...")
            ruta_meta = generar_archivo_metadata(titulo, tema, nombre_base)
            if indice_cat != -1:
                pipeline_main.registrar_tema_en_historial(tema, indice_cat)

            self.progress_bar.set(1.0)
            self.led_indicator.configure(text="● COMPLETADO", text_color=C_SUCCESS)
            self.lbl_media_badge.configure(text="VIDEO PRODUCIDO CON ÉXITO", text_color=C_SUCCESS)
            self.log("✔ PROCESO FINALIZADO. Short listo para publicación.")

            self._actualizar_campos_metadata(ruta_meta)
            self.after(200, self._activar_reproduccion_completada)

        except Exception as e:
            self.led_indicator.configure(text="● ERROR", text_color=C_DANGER)
            self.lbl_media_badge.configure(text="ERROR EN PRODUCCIÓN", text_color=C_DANGER)
            self.log(f"❌ Fallo crítico en el proceso: {e}")
        finally:
            self.is_running = False
            self.btn_generar.configure(state="normal", text="Iniciar Producción", fg_color=C_PRIMARY)

    def _activar_reproduccion_completada(self):
        self.btn_toggle_video.configure(
            state="normal",
            text="▶ Reproducir Video Final (Con Audio)",
            fg_color=C_PRIMARY,
            hover_color=C_PRIMARY_HOVER,
            text_color="#FFFFFF"
        )

    # ========================================================
    # MONITOR EN VIVO DE IMÁGENES
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
                        num = img_path.stem.split("_escena_")[-1]
                        self.after(0, self._mostrar_imagen_en_canvas, img_path, f"Escena {num}/12 generada")
            time.sleep(0.8)

    def _mostrar_imagen_en_canvas(self, ruta_img: Path, subtexto: str = ""):
        try:
            pil_img = Image.open(ruta_img)
            w, h = 310, 550
            pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(w, h))

            self.lbl_canvas_preview.configure(image=ctk_img, text="")
            self.lbl_canvas_preview.image = ctk_img
            if subtexto:
                self.lbl_media_badge.configure(text=subtexto.upper(), text_color="#60A5FA")
        except Exception:
            pass

    # ========================================================
    # REPRODUCCIÓN NATIVA CON AUDIO (SOLO AL HACER CLIC)
    # ========================================================
    def _abrir_video_reproductor(self):
        if self.ultimo_video_path and self.ultimo_video_path.exists():
            try:
                os.startfile(str(self.ultimo_video_path))
                self.log(f"🎬 Abriendo reproductor: {self.ultimo_video_path.name}")
            except Exception as err:
                self.log(f"⚠️ Error al abrir reproductor de Windows: {err}")
        else:
            self.log("⚠️ No hay video activo para reproducir.")

    # ========================================================
    # METADATOS Y ACCIONES
    # ========================================================
    def _actualizar_campos_metadata(self, ruta_txt: Path):
        try:
            lineas = ruta_txt.read_text(encoding="utf-8").splitlines()
            tit = ""
            desc = []
            capturar = False

            for i, l in enumerate(lineas):
                if "📋 COPIAR Y PEGAR RÁPIDO" in l and i + 1 < len(lineas):
                    tit = lineas[i + 1].strip()
                if "📝 DESCRIPCIÓN COMPLETA:" in l:
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
            self.log("📋 Título copiado al portapapeles.")

    def _copiar_descripcion(self):
        d = self.txt_desc.get("1.0", "end").strip()
        if d:
            pyperclip.copy(d)
            self.log("📋 Descripción copiada al portapapeles.")

    # ========================================================
    # PURGA SELECTIVA (CONSERVACIÓN DEL VIDEO FINAL)
    # ========================================================
    def _limpiar_archivos_disco(self):
        """Elimina únicamente temporales (audio, json, metadata, prompts, imágenes) y CONSERVA el video final."""
        if not self.ultimo_nombre_base:
            self.log("⚠️ No hay elementos en buffer para limpiar.")
            return

        nb = self.ultimo_nombre_base

        rutas_temporales = [
            BASE_DIR / "outputs" / "audio" / f"{nb}.mp3",
            BASE_DIR / "outputs" / "json" / f"{nb}.json",
            BASE_DIR / "outputs" / "metadata" / f"{nb}_para_publicar.txt",
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

        ruta_vid = BASE_DIR / "outputs" / "videos" / f"{nb}_subtitulado.mp4"
        estado_vid = "conservado intacto" if ruta_vid.exists() else "no encontrado"

        self.log(f"🧹 Purgados {eliminados} archivos temporales. Video final {estado_vid} en outputs/videos.")
        self.entry_titulo.delete(0, "end")
        self.txt_desc.delete("1.0", "end")
        self.lbl_char_count.configure(text="0/100", text_color=C_TEXT_MUTED)
        self._limpiar_monitor_preview(f"Temporales purgados.\nVideo final guardado en:\noutputs/videos/{nb}_subtitulado.mp4")
        self.ultimo_nombre_base = None


if __name__ == "__main__":
    app = CajaNegraStudio()
    app.mainloop()