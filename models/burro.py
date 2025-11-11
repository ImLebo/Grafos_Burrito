"""Modelo del Burro (personaje principal del juego).

Gestiona el estado, las animaciones y la lógica del burro que navega
por las constelaciones.
"""
import pygame
from utils.animated_sprite import AnimatedSprite
from typing import Dict, Optional


class Burro:
    """Representa al burro con sus estadísticas, estado y animaciones."""
    
    def __init__(self, data: dict, sprite_scale: tuple = (48, 48), sprite_rotation_degrees: int = 0, sprite_flip_x: bool = False, sprite_flip_y: bool = False):
        """
        Args:
            data: Diccionario con los datos del burro desde el JSON.
            sprite_scale: Tamaño (ancho, alto) para el sprite del burro.
        """
        # Atributos desde JSON
        self.nombre = data.get("nombre", "Burro")
        self.energia = data.get("energiaInicial", 100)
        self.energia_max = self.energia
        self.estado_salud = data.get("estadoSalud", "Normal")
        self.pasto_disponible = data.get("pastoDisponibleKg", 300)
        self.pasto_max = self.pasto_disponible
        self.edad = data.get("edadActual", 0)
        self.tiempo_vida = data.get("tiempoDeVidaAniosLuz", 0)
        self.nivel_experiencia = data.get("nivelExperiencia", "Principiante")
        self.nivel_investigacion = data.get("nivelInvestigacion", 0)
        self.consumo_energia = data.get("consumoEnergiaInvestigacion", 1)
        self.velocidad = data.get("velocidadDesplazamiento", 1.0)
        self.sonido_muerte = data.get("sonidoMuerte", "")
        
        # Animaciones disponibles
        self.animaciones_paths = data.get("animaciones", {})
        self.animaciones: Dict[str, AnimatedSprite] = {}
        self.current_animation = "principal"
        self.sprite_rotation_degrees = sprite_rotation_degrees % 360
        self.sprite_flip_x = sprite_flip_x
        self.sprite_flip_y = sprite_flip_y
        self._cargar_animaciones(sprite_scale)
        
        # Posición en pantalla (se actualiza externamente)
        self.position = (0, 0)
        
        # Estrella actual (ID de la estrella donde está el burro)
        self.current_star_id: Optional[int] = None
    
    def _cargar_animaciones(self, scale: tuple):
        """Carga todos los GIFs de animación especificados en el JSON.

        Se aplica rotación a la derecha (90°) y eliminación de fondo para mayor
        integración visual con el espacio.
        """
        for anim_name, path in self.animaciones_paths.items():
            try:
                sprite = AnimatedSprite(
                    path,
                    fps=12,
                    scale=scale,
                    rotation_degrees=self.sprite_rotation_degrees,  # rotación deseada
                    remove_background=True,        # intentar quitar fondo
                    bg_color=None,                 # autodetect
                    bg_tolerance=14,               # tolerancia un poco mayor
                    flip_x=self.sprite_flip_x,
                    flip_y=self.sprite_flip_y,
                )
                if sprite.has_frames():
                    self.animaciones[anim_name] = sprite
                    print(f"[Burro] Animación '{anim_name}' cargada correctamente (rotada+sin fondo).")
                else:
                    print(f"[Burro] Animación '{anim_name}' sin frames: {path}")
            except Exception as e:
                print(f"[Burro] Error cargando animación '{anim_name}': {e}")

        # Si no hay ninguna animación, crear placeholder
        if not self.animaciones:
            print("[Burro] No se cargaron animaciones. Usando placeholder.")
    
    def set_animation(self, anim_name: str):
        """Cambia la animación actual si existe."""
        if anim_name in self.animaciones:
            if self.current_animation != anim_name:
                self.current_animation = anim_name
                self.animaciones[anim_name].reset()
        else:
            print(f"[Burro] Animación '{anim_name}' no encontrada.")
    
    def update(self, dt: float):
        """Actualiza el estado y la animación del burro."""
        # Actualizar animación actual
        if self.current_animation in self.animaciones:
            self.animaciones[self.current_animation].update(dt)
        
        # Sin mecánica de hambre: mantener animación principal por defecto
    
    def render(self, surface: pygame.Surface, position: tuple):
        """Dibuja el burro en la posición especificada."""
        self.position = position
        if self.current_animation in self.animaciones:
            frame = self.animaciones[self.current_animation].get_current_frame()
            # Centrar el sprite en la posición
            rect = frame.get_rect(center=position)
            surface.blit(frame, rect.topleft)
        else:
            # Placeholder: círculo amarillo
            pygame.draw.circle(surface, (255, 200, 0), position, 16)
            pygame.draw.circle(surface, (100, 50, 0), position, 16, 2)
    
    def comer(self, cantidad: int = 0):
        """Comer manual (ya no se usa la mecánica de hambre)."""
        # La alimentación se procesa automáticamente al llegar a una estrella.
        # Este método queda como placeholder para compatibilidad.
        print("[Burro] La alimentación se gestiona automáticamente en cada estrella.")
    
    def moverse_a_estrella(self, star_id: int, position: tuple):
        """Mueve el burro a una nueva estrella."""
        self.current_star_id = star_id
        self.position = position
        # Consumir energía al moverse
        self.energia = max(0, self.energia - self.consumo_energia)
        print(f"[Burro] {self.nombre} se movió a estrella {star_id}. Energía: {self.energia}")
    
    def esta_vivo(self) -> bool:
        """Verifica si el burro sigue con vida."""
        return self.energia > 0
    
    def morir(self):
        """Ejecuta la lógica de muerte del burro."""
        self.set_animation("muerte")
        print(f"[Burro] {self.nombre} ha muerto.")
        # Reproducir el sonido de muerte si es posible
        try:
            import os
            import pygame
            path = self.sonido_muerte or ""
            if path.startswith("/"):
                # normalizar ruta relativa del repo
                path = path[1:]
            if os.path.exists(path):
                snd = pygame.mixer.Sound(path)
                snd.play()
        except Exception as e:
            # No bloquear por audio
            pass
    
    def __str__(self):
        return f"{self.nombre} ({self.estado_salud}) - Energía: {self.energia}/{self.energia_max}"
