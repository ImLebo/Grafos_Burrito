"""Gestor de vistas para una aplicación Pygame.

Permite registrar vistas por nombre y cambiar la vista actual. La variable
`current_view_name` es pública y podrá ser manejada por eventos en el futuro.
"""
from typing import Dict, Optional
import pygame

from screens.view import View


class ViewManager:
    def __init__(self):
        self.views: Dict[str, View] = {}
        self.current_view_name: Optional[str] = None
        self.current_view: Optional[View] = None

    def register_view(self, name: str, view: View):
        """Registrar una instancia de vista bajo un nombre.

        name: identificador de la vista (string)
        view: instancia que implementa la interfaz View
        """
        self.views[name] = view

    def set_view(self, name: str):
        """Cambiar la vista activa por nombre.

        Llama a on_exit/on_enter apropiadamente.
        """
        if name == self.current_view_name:
            return

        if self.current_view is not None:
            try:
                self.current_view.on_exit()
            except Exception:
                pass

        self.current_view_name = name
        self.current_view = self.views.get(name)

        if self.current_view is not None:
            try:
                self.current_view.on_enter()
            except Exception:
                pass

    def handle_event(self, event: pygame.event.Event):
        """Reenviar evento a la vista actual. Si la vista solicita un cambio
        (poniendo `view.requested_view`), el gestor lo procesará."""
        if self.current_view is None:
            return

        try:
            self.current_view.handle_event(event)
        except Exception:
            # No romper por errores en la vista; en el futuro loggear.
            pass

        # Comprobar si la vista solicitó un cambio
        if getattr(self.current_view, "requested_view", None):
            next_view = self.current_view.requested_view
            # resetear petición antes de cambiar
            self.current_view.requested_view = None
            if next_view in self.views:
                self.set_view(next_view)

    def update(self, dt: float):
        if self.current_view is None:
            return
        try:
            self.current_view.update(dt)
        except Exception:
            pass

    def render(self, surface):
        if self.current_view is None:
            return
        try:
            self.current_view.render(surface)
        except Exception:
            pass
