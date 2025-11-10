"""Clase utilitaria para manejar sprites animados desde GIFs.

Permite cargar GIFs y reproducirlos como animaciones frame por frame.
Funciones añadidas:
 - Rotación hacia la derecha (clockwise) indicando grados.
 - Eliminación opcional de fondo sólido haciendo transparente el color de fondo.

Uso rápido:
    sprite = AnimatedSprite("assets/images/burro/burro.gif",
                            fps=14,
                            scale=(64,64),
                            rotation_degrees=90,          # rota 90° a la derecha
                            remove_background=True,       # intenta quitar fondo
                            bg_color=None,                # None = detecta esquina
                            bg_tolerance=12)              # tolerancia para matices

Eliminación de fondo: se toma el color indicado (o el de la esquina superior izquierda
del primer frame si bg_color es None) y se vuelve transparente cualquier pixel cuya
distancia euclídea al color esté por debajo de bg_tolerance.
"""
import os
import pygame
from typing import Tuple, Optional


class AnimatedSprite:
    """Sprite animado que carga frames de un GIF y los reproduce en bucle.

    Parámetros nuevos:
        rotation_degrees: rotación clockwise aplicada a cada frame al cargar.
        remove_background: si True, intenta hacer transparente un color sólido.
        bg_color: color base (R,G,B) a transparentar; None => detecta esquina (0,0).
        bg_tolerance: tolerancia para considerar un pixel como fondo.
    """

    def __init__(
        self,
        gif_path: str,
        fps: int = 12,
        scale: tuple | None = None,
        rotation_degrees: int = 0,
        remove_background: bool = False,
        bg_color: Optional[Tuple[int, int, int]] = None,
        bg_tolerance: int = 8,
        flip_x: bool = False,
        flip_y: bool = False,
    ):
        """Inicializa el sprite animado.

        Args:
            gif_path: Ruta al archivo GIF.
            fps: Frames por segundo.
            scale: (w,h) para escalar; None = sin escalar.
            rotation_degrees: rotación clockwise (90, 180, 270, etc.).
            remove_background: activar eliminación de fondo sólido.
            bg_color: color (R,G,B) del fondo; None => auto-detect (primer frame esquina).
            bg_tolerance: tolerancia (0-255 aprox) para variaciones leves del fondo.
        """
        self.gif_path = gif_path
        self.fps = fps
        self.scale = scale
        self.rotation_degrees = rotation_degrees % 360
        self.remove_background = remove_background
        self.bg_color = bg_color
        self.bg_tolerance = max(0, bg_tolerance)
        self.flip_x = flip_x
        self.flip_y = flip_y

        self.frames: list[pygame.Surface] = []
        self.current_frame = 0
        self.timer = 0.0
        self.frame_duration = 1.0 / fps if fps > 0 else 0.1
        self._load_gif()
    
    def _load_gif(self):
        """Carga los frames del GIF usando imageio y aplica transformaciones opcionales."""
        if not os.path.exists(self.gif_path):
            print(f"[AnimatedSprite] GIF no encontrado: {self.gif_path}")
            return

        try:
            import imageio
            import numpy as np
        except ImportError:
            print("[AnimatedSprite] imageio no está instalado. Usa: pip install imageio")
            return

        try:
            raw_frames = imageio.mimread(self.gif_path)
            if not raw_frames:
                print(f"[AnimatedSprite] GIF vacío: {self.gif_path}")
                return

            # Determinar bg_color si hace falta (usar esquina primer frame)
            auto_bg_color = None
            if self.remove_background and self.bg_color is None:
                first = raw_frames[0]
                if first.ndim == 3:
                    auto_bg_color = tuple(int(c) for c in first[0, 0, :3])
                elif first.ndim == 2:
                    val = int(first[0, 0])
                    auto_bg_color = (val, val, val)
            bgc = self.bg_color if self.bg_color is not None else auto_bg_color

            for arr in raw_frames:
                # Asegurar RGB mínimo
                if arr.ndim == 2:  # escala de grises
                    arr = np.stack([arr] * 3, axis=-1)
                h, w = arr.shape[0], arr.shape[1]
                channels = arr.shape[2] if arr.ndim == 3 else 3
                has_alpha = channels == 4

                # Eliminar fondo si procede
                if self.remove_background and bgc is not None:
                    # Asegurar tener al menos RGB
                    if channels < 3:
                        # redundante por conversión arriba
                        pass
                    # Separar RGB
                    rgb = arr[:, :, :3]
                    # Distancia euclídea al color fondo
                    diff = rgb.astype(float) - np.array(bgc, dtype=float)
                    dist = np.sqrt(np.sum(diff * diff, axis=2))
                    mask = dist <= self.bg_tolerance
                    if has_alpha:
                        alpha = arr[:, :, 3]
                    else:
                        alpha = np.full((h, w), 255, dtype=np.uint8)
                    alpha = np.where(mask, 0, alpha).astype(np.uint8)
                    # Reconstruir RGBA
                    arr = np.dstack((rgb, alpha))
                    has_alpha = True
                    channels = 4

                mode = 'RGBA' if has_alpha else 'RGB'
                surf = pygame.image.frombuffer(arr.tobytes(), (w, h), mode)

                if has_alpha:
                    surf = surf.convert_alpha()
                else:
                    surf = surf.convert()

                # Rotación (pygame rota CCW; para clockwise usamos ángulo negativo)
                if self.rotation_degrees:
                    surf = pygame.transform.rotate(surf, -self.rotation_degrees)

                # Flip espejo
                if self.flip_x or self.flip_y:
                    surf = pygame.transform.flip(surf, self.flip_x, self.flip_y)

                # Escalar si se especifica (aplicar después de rotar para tamaño uniforme final)
                if self.scale:
                    surf = pygame.transform.scale(surf, self.scale)

                self.frames.append(surf)

            print(f"[AnimatedSprite] Cargado: {self.gif_path} ({len(self.frames)} frames)" + (f" | fondo transparente {bgc}" if self.remove_background and bgc else ""))
        except Exception as e:
            print(f"[AnimatedSprite] Error cargando GIF {self.gif_path}: {e}")
    
    def update(self, dt: float):
        """Actualiza la animación según el tiempo transcurrido."""
        if not self.frames:
            return
        
        self.timer += dt
        if self.timer >= self.frame_duration:
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.timer = 0.0
    
    def get_current_frame(self) -> pygame.Surface:
        """Retorna el frame actual de la animación."""
        if not self.frames:
            # Superficie de placeholder si no hay frames
            surf = pygame.Surface((32, 32))
            surf.fill((255, 0, 255))  # magenta para indicar error
            return surf
        return self.frames[self.current_frame]
    
    def reset(self):
        """Reinicia la animación al primer frame."""
        self.current_frame = 0
        self.timer = 0.0
    
    def has_frames(self) -> bool:
        """Indica si el sprite tiene frames cargados."""
        return len(self.frames) > 0

    # ---------------- Métodos auxiliares -----------------
    def rotate_right(self, degrees: int = 90):
        """Rota todos los frames 'degrees' a la derecha (clockwise) después de haber cargado.

        Nota: Esto cambia el tamaño de los frames; si 'scale' estaba definido y quieres
        mantener ese tamaño, vuelve a aplicar scale tras la rotación.
        """
        if not self.frames:
            return
        deg = degrees % 360
        if deg == 0:
            return
        self.frames = [pygame.transform.rotate(f, -deg) for f in self.frames]
        if self.scale:
            self.frames = [pygame.transform.scale(f, self.scale) for f in self.frames]

    def current_size(self) -> Tuple[int, int] | None:
        """Retorna el tamaño (w,h) del frame actual o None si vacío."""
        if not self.frames:
            return None
        surf = self.frames[self.current_frame]
        return surf.get_width(), surf.get_height()
