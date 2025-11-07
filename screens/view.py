"""Clase base para vistas de Pygame.

Define la interfaz mínima que cualquier vista debe implementar.
"""
from abc import ABC, abstractmethod
from typing import Optional

class View(ABC):
    """Interfaz base para una vista en Pygame.

    Métodos:
    - handle_event(event): procesar eventos de pygame (puede devolver un nombre de vista a cambiar)
    - update(dt): actualizar estado
    - render(surface): dibujar en la superficie suministrada
    - on_enter(): llamado cuando la vista se activa
    - on_exit(): llamado cuando la vista se desactiva
    """

    def __init__(self):
        # campo opcional que las vistas pueden usar para solicitar un cambio de vista
        self.requested_view: Optional[str] = None

    @abstractmethod
    def handle_event(self, event):
        """Procesa un evento de pygame.

        Puede opcionalmente establecer `self.requested_view = '<view_name>'` para pedir
        al gestor un cambio de vista.
        """
        raise NotImplementedError()

    @abstractmethod
    def update(self, dt: float):
        """Actualizar estado de la vista.

        dt: tiempo en segundos desde la última actualización.
        """
        raise NotImplementedError()

    @abstractmethod
    def render(self, surface):
        """Dibujar la vista en la superficie proporcionada."""
        raise NotImplementedError()

    def on_enter(self):
        """Llamado cuando la vista es activada por el gestor."""
        pass

    def on_exit(self):
        """Llamado cuando la vista es desactivada por el gestor."""
        pass
