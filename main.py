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
from screens.editor_view import ConstellationEditorView
from screens.main_menu import MainMenu
from config.loader import cargar_grafo_desde_json



def main():
    pygame.init()
    try:
        pygame.font.init()
    except Exception:
        pass
    size = (1280, 800)
    screen = pygame.display.set_mode(size)
    pygame.display.set_caption("Grafos Burrito")
    clock = pygame.time.Clock()

    # Fondo animado del menú: asegúrate que el archivo exista en esta ruta
    # (en este repo se llama "background.gif").
    bg_path = "assets/images/background/background.gif"

    # Cargar grafos reales desde el JSON
    graphs, burro_data = cargar_grafo_desde_json("data/constellations.json")
    manager = ViewManager()
    const_view = ConstellationView("Constelaciones", graphs, burro_data)
    editor_view = ConstellationEditorView(existing_graphs=graphs)
    menu_view = MainMenu(bg_path)
    manager.register_view("main_menu", menu_view)
    manager.register_view("constellation", const_view)
    manager.register_view("editor", editor_view)
    manager.set_view("main_menu")

    running = True
    while running:
        dt = clock.tick(60) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F2:
                manager.set_view("editor")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F3:
                manager.set_view("constellation")
            manager.handle_event(event)
        manager.update(dt)
        manager.render(screen)
        pygame.display.flip()
    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
