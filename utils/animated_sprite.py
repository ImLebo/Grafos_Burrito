"""Clase utilitaria para manejar sprites animados desde GIFs.

Permite cargar GIFs y reproducirlos como animaciones frame por frame.
Útil para personajes, efectos visuales, etc.
"""
import os
import pygame


class AnimatedSprite:
    """Sprite animado que carga frames de un GIF y los reproduce en bucle."""
    
    def __init__(self, gif_path: str, fps: int = 12, scale: tuple = None):
        """
        Args:
            gif_path: Ruta al archivo GIF.
            fps: Frames por segundo de la animación.
            scale: Tupla (width, height) para escalar frames; None = sin escalar.
        """
        self.gif_path = gif_path
        self.fps = fps
        self.scale = scale
        self.frames = []
        self.current_frame = 0
        self.timer = 0.0
        self.frame_duration = 1.0 / fps if fps > 0 else 0.1
        self._load_gif()
    
    def _load_gif(self):
        """Carga los frames del GIF usando imageio."""
        if not os.path.exists(self.gif_path):
            print(f"[AnimatedSprite] GIF no encontrado: {self.gif_path}")
            return
        
        try:
            import imageio
        except ImportError:
            print("[AnimatedSprite] imageio no está instalado. Usa: pip install imageio")
            return
        
        try:
            raw_frames = imageio.mimread(self.gif_path)
            if not raw_frames:
                print(f"[AnimatedSprite] GIF vacío: {self.gif_path}")
                return
            
            for arr in raw_frames:
                # Convertir array numpy a superficie pygame
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
                
                # Escalar si se especifica
                if self.scale:
                    surf = pygame.transform.scale(surf, self.scale)
                
                self.frames.append(surf)
            
            print(f"[AnimatedSprite] Cargado: {self.gif_path} ({len(self.frames)} frames)")
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
