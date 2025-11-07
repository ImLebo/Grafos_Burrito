"""Runner mínimo usando Pygame y el ViewManager.

Este `main.py` crea una ventana Pygame, registra dos vistas de ejemplo
(`constellation` y `other`) y arranca el bucle principal. Presionar ESC o
cerrar la ventana terminará la aplicación. Presionar TAB en la vista
`ConstellationView` solicitará el cambio a la vista `other` (demostración).
"""
import sys
import pygame

from screens.manager import ViewManager
from screens.constellation_view import ConstellationView
from config.loader import cargar_grafo_desde_json


def main():
    pygame.init()
    # Intentar inicializar módulos que puedan fallar en entornos sin display
    try:
        pygame.font.init()
    except Exception:
        pass

    # Aumentar tamaño de ventana para mejorar visibilidad
    size = (1280, 800)
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Grafos - Vistas (Pygame)")

    clock = pygame.time.Clock()

    manager = ViewManager()

    # Cargar grafos reales desde el JSON
    graphs = cargar_grafo_desde_json("data/constellations.json")

    # Registrar vistas (constellation con datos reales; other es placeholder reutilizando la clase)
    const_view = ConstellationView("Constelaciones", graphs)
    other_view = ConstellationView("Otra Vista (placeholder)", graphs)

    manager.register_view("constellation", const_view)
    manager.register_view("other", other_view)

    manager.set_view("constellation")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

            # Enviar evento al gestor (gestiona cambio de vistas si se solicita)
            manager.handle_event(event)

        manager.update(dt)
        manager.render(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
