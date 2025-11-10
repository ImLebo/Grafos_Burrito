import pygame
import os
from screens.view import View

class MainMenu(View):
    def __init__(self, background_path: str):
        super().__init__()
        self.background_path = background_path
        # Agregamos opción para editar a Burro antes de "Salir"
        self.options = ["Simulación", "Editor", "Burro", "Salir"]
        self.selected = 0
        self.font = None
        self.small_font = None
        self.bg_frames = []
        self.bg_frame_idx = 0
        self.bg_timer = 0.0
        self.bg_fps = 12
        self.screen_size = (1280, 800)
        self._loaded = False

    def on_enter(self):
        # inicializar fuentes y cargar gif sólo una vez
        if not self.font and pygame.font:
            try:
                self.font = pygame.font.SysFont("Consolas", 48)
                self.small_font = pygame.font.SysFont("Consolas", 28)
            except Exception:
                self.font = None
                self.small_font = None
        if not self._loaded:
            self._load_background_gif()
            self._loaded = True
        # Reset selección al entrar
        self.selected = 0

    def _load_background_gif(self):
        """Carga y prepara los frames del GIF. Si falla, deja lista una lista vacía para usar fondo de color.

        Razones comunes de fallo:
        - Librería `imageio` no instalada.
        - Ruta del GIF incorrecta.
        - GIF con canal alfa (se maneja aquí) o paleta.
        """
        gif_path = self.background_path
        if not os.path.exists(gif_path):
            print(f"[MainMenu] GIF no encontrado: {gif_path}")
            self.bg_frames = []
            return
        try:
            try:
                import imageio
            except ImportError:
                print("[MainMenu] 'imageio' no instalado. Instálalo (pip install imageio) para fondo animado.")
                self.bg_frames = []
                return
            raw_frames = imageio.mimread(gif_path)
            if not raw_frames:
                print(f"[MainMenu] GIF vacío o no leído: {gif_path}")
                self.bg_frames = []
                return
            for arr in raw_frames:
                # Asegurar formato esperado
                if arr.ndim == 2:  # escala de grises
                    import numpy as np
                    arr = np.stack([arr]*3, axis=-1)
                h, w = arr.shape[0], arr.shape[1]
                channels = arr.shape[2] if arr.ndim == 3 else 3
                mode = 'RGBA' if channels == 4 else 'RGB'
                surf = pygame.image.frombuffer(arr.tobytes(), (w, h), mode)
                if mode == 'RGBA':
                    surf = surf.convert_alpha()
                else:
                    surf = surf.convert()
                self.bg_frames.append(surf)
            print(f"[MainMenu] GIF cargado con {len(self.bg_frames)} frames.")
        except Exception as e:
            print(f"[MainMenu] Error cargando GIF: {e}")
            self.bg_frames = []

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % len(self.options)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % len(self.options)
            elif event.key == pygame.K_RETURN:
                if self.selected == 0:
                    self.requested_view = "constellation"
                elif self.selected == 1:
                    self.requested_view = "editor"
                elif self.selected == 2:
                    self.requested_view = "burro_editor"
                else:
                    pygame.event.post(pygame.event.Event(pygame.QUIT))

    def update(self, dt):
        if self.bg_frames:
            self.bg_timer += dt
            if self.bg_timer > 1.0 / self.bg_fps:
                self.bg_frame_idx = (self.bg_frame_idx + 1) % len(self.bg_frames)
                self.bg_timer = 0.0

    def render(self, surface):
        # Fondo animado
        if self.bg_frames:
            frame = self.bg_frames[self.bg_frame_idx]
            frame = pygame.transform.scale(frame, surface.get_size())
            surface.blit(frame, (0, 0))
        else:
            surface.fill((10, 10, 20))
        # Overlay semitransparente
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        surface.blit(overlay, (0, 0))
        if not self.font or not self.small_font:
            return
        # Título
        title = self.font.render("Grafos Burrito", True, (255, 220, 80))
        surface.blit(title, (surface.get_width() // 2 - title.get_width() // 2, 120))
        # Opciones
        for i, opt in enumerate(self.options):
            color = (255, 255, 255) if i == self.selected else (180, 180, 180)
            surf = self.small_font.render(opt, True, color)
            x = surface.get_width() // 2 - surf.get_width() // 2
            # Subimos un poco las cards para evitar que el texto de ayuda se monte encima
            y = 200 + i * 70
            surface.blit(surf, (x, y))
        # Instrucción
        hint = self.small_font.render("↑/↓ + Enter", True, (200, 200, 210))
        surface.blit(hint, (surface.get_width() // 2 - hint.get_width() // 2, 500))
