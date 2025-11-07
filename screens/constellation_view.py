"""Vista para dibujar constelaciones (grafos) basadas en los datos cargados.

Características:
 - Dibuja cada arista sólo una vez evitando duplicados (arista bidireccional).
 - Estrellas hipergigantes: color rojo y radio mayor.
 - Estrellas normales: color base configurable (por defecto blanco).
 - Muestra nombre de la constelación arriba.
 - Permite TAB para solicitar cambio a la vista 'other' (placeholder).
"""
import pygame
from screens.view import View
from typing import List, Sequence, Dict, Tuple
from models.graph import Graph


class ConstellationView(View):
    def __init__(self, name: str, graphs: Sequence[Graph], base_color=(255, 255, 255), board_rect: pygame.Rect | None = None):
        super().__init__()
        self.name = name
        self.graphs: List[Graph] = list(graphs)
        self.font = None
        self.base_color = base_color
        # Tablero donde se dibuja el grafo (se puede pasar desde fuera). Si no, se ajustará en on_enter.
        self.board_rect: pygame.Rect | None = board_rect
        # Posiciones escaladas cacheadas: { graph: { star_id: (x,y) } }
        self.scaled_positions: Dict[int, Dict[int, Tuple[int, int]]] = {}
        # Paleta para múltiples constelaciones (cicla si hay más):
        self.palette = [
            (255, 255, 0),   # amarillo
            (0, 255, 255),   # cyan
            (255, 0, 255),   # magenta
            (255, 165, 0),   # orange
            (0, 255, 0),     # lime
            (200, 200, 200)  # gris claro
        ]
        # Índice de constelación actual (mostrar sólo una)
        self.current_index: int = 0
        # Estrella seleccionada por click
        self.selected_star_id: int | None = None

    def on_enter(self):
        if pygame.font:
            try:
                self.font = pygame.font.SysFont("Consolas", 18)
            except Exception:
                self.font = None
        # Ajustar tablero si no existe: ocupar 80% de alto comenzando en y=0
        if self.board_rect is None:
            display_w, display_h = pygame.display.get_surface().get_size()
            board_h = int(display_h * 0.8)
            self.board_rect = pygame.Rect(0, 0, display_w, board_h)
        # Calcular posiciones escaladas
        self._compute_scaled_positions()
        # Índice global de star_id -> (graph_index)
        self._build_global_index()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.requested_view = "other"
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click izquierdo: intentar seleccionar estrella y navegar si es hipergigante con enlace externo
            self._handle_click(event.pos)

    def update(self, dt: float):
        # Ejemplo: animación simple de pulso para hipergigantes usando tiempo acumulado
        # Podría ampliarse; por ahora no se requiere lógica compleja.
        pass

    def _compute_scaled_positions(self):
        # Calcular bounding box sólo de la constelación actual
        gi = self.current_index
        if gi < 0 or gi >= len(self.graphs):
            return
        g = self.graphs[gi]
        stars = g.get_all_stars()
        if not stars:
            return
        xs = [s.coordinates[0] for s in stars]
        ys = [s.coordinates[1] for s in stars]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)

        bw = self.board_rect.width
        bh = self.board_rect.height
        margin = 60
        range_x = max_x - min_x if (max_x - min_x) != 0 else 1
        range_y = max_y - min_y if (max_y - min_y) != 0 else 1
        scale = min((bw - 2 * margin) / range_x, (bh - 2 * margin) / range_y)
        remaining_w = bw - (range_x * scale)
        remaining_h = bh - (range_y * scale)
        offset_x = self.board_rect.x + remaining_w / 2 - min_x * scale
        offset_y = self.board_rect.y + remaining_h / 2 - min_y * scale

        self.scaled_positions.clear()
        self.scaled_positions[gi] = {}
        for s in stars:
            sx = int(offset_x + s.coordinates[0] * scale)
            sy = int(offset_y + s.coordinates[1] * scale)
            self.scaled_positions[gi][s.id] = (sx, sy)

    def _build_global_index(self):
        self.id_to_gi = {}
        for gi, g in enumerate(self.graphs):
            for s in g.get_all_stars():
                self.id_to_gi[s.id] = gi

    def _handle_click(self, mouse_pos):
        gi = self.current_index
        pos_map = self.scaled_positions.get(gi, {})
        clicked_id = None
        for star_id, (x, y) in pos_map.items():
            dx = mouse_pos[0] - x
            dy = mouse_pos[1] - y
            if (dx * dx + dy * dy) <= (18 * 18):
                clicked_id = star_id
                break
        self.selected_star_id = clicked_id
        if clicked_id is None:
            return
        # Navegar sólo si la estrella es hipergigante y tiene enlace externo
        current_graph = self.graphs[gi]
        star_obj = current_graph.get_star(clicked_id)
        if not star_obj or not star_obj.hypergiant:
            return
        # Buscar enlace externo saliente desde esta hipergigante
        for a, b, dist in getattr(current_graph, 'external_links', []):
            if a == clicked_id:
                target_gi = self.id_to_gi.get(b)
                if target_gi is not None and target_gi != gi:
                    self.current_index = target_gi
                    self._compute_scaled_positions()
                    # Mantener índice global (no cambia estructura)
                    self.selected_star_id = None
                    break

    def _draw_graph(self, surface, graph: Graph, color, gi: int):
        drawn_edges = set()
        pos_map = self.scaled_positions.get(gi, {})
        # Aristas
        for star in graph.get_all_stars():
            x, y = pos_map.get(star.id, star.coordinates)
            for neighbor_id, dist in star.connections.items():
                key = tuple(sorted((star.id, neighbor_id)))
                if key in drawn_edges:
                    continue
                drawn_edges.add(key)
                neighbor = graph.get_star(neighbor_id)
                if neighbor:
                    nx, ny = pos_map.get(neighbor.id, neighbor.coordinates)
                    # Línea levemente más gruesa
                    pygame.draw.line(surface, (140, 140, 170), (x, y), (nx, ny), 2)

        # Estrellas
        for star in graph.get_all_stars():
            x, y = pos_map.get(star.id, star.coordinates)
            if star.hypergiant:
                radius = 14
                fill_color = (255, 60, 60)
                # Halo externo
                pygame.draw.circle(surface, (180, 30, 30), (x, y), radius + 6, width=2)
            else:
                radius = 8
                fill_color = color
            pygame.draw.circle(surface, fill_color, (x, y), radius)
            if self.font:
                label_surf = self.font.render(star.label, True, (230, 230, 240))
                surface.blit(label_surf, (x + radius + 4, y - radius))

    def _draw_external_links(self, surface):
        # Dibuja conexiones entre constelaciones (hipergigantes enlazadas)
        # Ahora no se dibujan por defecto para no mostrar otras constelaciones.
        # Se deja el método por si en el futuro se quiere mostrar una pista visual.
        return

    def render(self, surface):
        surface.fill((15, 20, 35))

        # Tablero (fondo con borde)
        if self.board_rect:
            pygame.draw.rect(surface, (30, 40, 65), self.board_rect, border_radius=12)
            pygame.draw.rect(surface, (80, 100, 140), self.board_rect, width=3, border_radius=12)

        if self.font:
            current_name = self.graphs[self.current_index].name if self.graphs else self.name
            title = self.font.render(current_name, True, (240, 240, 250))
            surface.blit(title, (self.board_rect.x + 20, self.board_rect.y + 20))

        # Dibujar sólo la constelación actual
        gi = self.current_index
        g = self.graphs[gi]
        graph_color = getattr(g, 'color', None)
        if graph_color and isinstance(graph_color, (tuple, list)) and len(graph_color) == 3:
            color = graph_color
        else:
            color = self.palette[gi % len(self.palette)]
        self._draw_graph(surface, g, color, gi)


