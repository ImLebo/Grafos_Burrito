"""Vista para dibujar constelaciones (grafos) basadas en los datos cargados.

Características:
 - Dibuja cada arista sólo una vez evitando duplicados (arista bidireccional).
 - Estrellas hipergigantes: color rojo y radio mayor.
 - Estrellas normales: color base configurable (por defecto blanco).
 - Muestra nombre de la constelación arriba.
 - Permite TAB para solicitar cambio a la vista 'other' (placeholder).
"""
import pygame
import math
import random
from screens.view import View
from typing import List, Sequence, Dict, Tuple, Optional
from models.graph import Graph
from models.burro import Burro


class ConstellationView(View):
    def __init__(self, name: str, graphs: Sequence[Graph], base_color=(255, 255, 255), board_rect: pygame.Rect | None = None, burro_data: dict = None):
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
        # Variables para animación
        self.hover_star_id: int | None = None
        self.pulse_time: float = 0.0
        self.hover_alpha: float = 0.0
        # Zoom dinámico anclado al mouse (sólo dentro del tablero)
        self.zoom: float = 1.0
        self.zoom_target: float = 1.0
        self.zoom_focus: Tuple[int, int] = (0, 0)
        self.zoom_in_factor: float = 1.06  # zoom pequeño y elegante
        self.zoom_speed: float = 3.0       # rapidez de transición
        # Fondo de estrellas del panel
        self._starfield_surf = None
        self._starfield_size = (0, 0)
        self._starfield_padding = 100  # padding alrededor para parallax
        
        # Burro (personaje)
        self._burro_data = burro_data  # Guardar datos originales para reinicios
        self.burro: Optional[Burro] = None
        if self._burro_data:
            # Efecto espejo horizontal para que mire a la derecha manteniendo orientación
            self.burro = Burro(self._burro_data, sprite_scale=(64, 64), sprite_rotation_degrees=0, sprite_flip_x=True)
        self.burro_initial_star_selected = False  # Flag para selección inicial

    def on_enter(self):
        if pygame.font:
            try:
                self.font = pygame.font.SysFont("Consolas", 18)
            except Exception:
                self.font = None
        # Reiniciar burro al entrar (reseteo de parámetros pedido por el usuario)
        if self._burro_data:
            self.burro = Burro(self._burro_data, sprite_scale=(64, 64), sprite_rotation_degrees=0, sprite_flip_x=True)
        self.burro_initial_star_selected = False
        if self.burro:
            self.burro.current_star_id = None
        # Ajustar tablero si no existe: ocupar 80% de alto comenzando en y=0
        if self.board_rect is None:
            display_w, display_h = pygame.display.get_surface().get_size()
            board_h = int(display_h * 0.8)
            self.board_rect = pygame.Rect(0, 0, display_w, board_h)
        # Calcular posiciones escaladas
        self._ensure_starfield()
        self._compute_scaled_positions()
        # Índice global de star_id -> (graph_index)
        self._build_global_index()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                # Volver al menú principal
                self.requested_view = "main_menu"
            elif event.key == pygame.K_e:
                # Atajo para abrir el editor
                self.requested_view = "editor"
            elif event.key == pygame.K_SPACE and self.burro:
                # Comer con espacio
                self.burro.comer(20)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click izquierdo
            if not self.burro_initial_star_selected and self.burro:
                # Primera vez: seleccionar estrella inicial para el burro
                self._select_initial_star(event.pos)
            else:
                # Click normal: intentar seleccionar estrella y navegar si es hipergigante con enlace externo
                self._handle_click(event.pos)

    def update(self, dt: float):
        # Actualizar tiempo de pulso para hipergigantes
        self.pulse_time = (self.pulse_time + dt) % 2.0  # Ciclo de 2 segundos
        
        # Actualizar burro
        if self.burro:
            self.burro.update(dt)
        
        # Detectar estrella bajo el cursor
        mouse_pos = pygame.mouse.get_pos()
        # Actualizar objetivo de zoom si el cursor está dentro del tablero
        if self.board_rect and self.board_rect.collidepoint(mouse_pos):
            self.zoom_target = self.zoom_in_factor
            self.zoom_focus = mouse_pos
        else:
            self.zoom_target = 1.0
        # Interpolación suave hacia el objetivo de zoom
        if self.zoom < self.zoom_target:
            self.zoom = min(self.zoom_target, self.zoom + dt * self.zoom_speed)
        elif self.zoom > self.zoom_target:
            self.zoom = max(self.zoom_target, self.zoom - dt * self.zoom_speed)
        gi = self.current_index
        pos_map = self.scaled_positions.get(gi, {})
        hover_found = False
        
        for star_id, (x, y) in pos_map.items():
            tx, ty = self._apply_zoom(x, y)
            dx = mouse_pos[0] - tx
            dy = mouse_pos[1] - ty
            if (dx * dx + dy * dy) <= (20 * 20):  # Radio de detección un poco mayor
                self.hover_star_id = star_id
                hover_found = True
                break
        
        if not hover_found:
            self.hover_star_id = None
        
        # Actualizar alpha de hover (transición suave)
        target_alpha = 1.0 if self.hover_star_id is not None else 0.0
        if target_alpha > self.hover_alpha:
            self.hover_alpha = min(1.0, self.hover_alpha + dt * 4)  # Fadeín más rápido
        else:
            self.hover_alpha = max(0.0, self.hover_alpha - dt * 2)  # Fadeout más suave

    def _apply_zoom(self, x: int | float, y: int | float) -> Tuple[int, int]:
        """Aplica el zoom actual alrededor del foco (mouse) y retorna coordenadas enteras."""
        if not self.board_rect or abs(self.zoom - 1.0) < 1e-3:
            return int(x), int(y)
        ax, ay = self.zoom_focus
        zx = ax + (x - ax) * self.zoom
        zy = ay + (y - ay) * self.zoom
        return int(zx), int(zy)

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
            tx, ty = self._apply_zoom(x, y)
            dx = mouse_pos[0] - tx
            dy = mouse_pos[1] - ty
            if (dx * dx + dy * dy) <= (18 * 18):
                clicked_id = star_id
                break
        self.selected_star_id = clicked_id
        if clicked_id is None:
            return
        
        # Si el burro está en juego, moverlo a la estrella clickeada (si son vecinas)
        if self.burro and self.burro.current_star_id is not None:
            current_star = self.graphs[gi].get_star(self.burro.current_star_id)
            if current_star and clicked_id in current_star.connections:
                # Mover burro a la nueva estrella
                new_pos = pos_map.get(clicked_id, (0, 0))
                self.burro.moverse_a_estrella(clicked_id, new_pos)
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
                    # Trasladar al burro a la estrella enlazada en la constelación destino
                    if self.burro:
                        new_pos = self.scaled_positions.get(target_gi, {}).get(b, (0, 0))
                        self.burro.moverse_a_estrella(b, new_pos)
                        self.burro_initial_star_selected = True
                    break
    
    def _select_initial_star(self, mouse_pos):
        """Selecciona la estrella inicial donde aparecerá el burro."""
        gi = self.current_index
        pos_map = self.scaled_positions.get(gi, {})
        for star_id, (x, y) in pos_map.items():
            tx, ty = self._apply_zoom(x, y)
            dx = mouse_pos[0] - tx
            dy = mouse_pos[1] - ty
            if (dx * dx + dy * dy) <= (18 * 18):
                # Colocar burro en esta estrella
                if self.burro:
                    self.burro.moverse_a_estrella(star_id, (x, y))
                    self.burro_initial_star_selected = True
                    print(f"[ConstellationView] Burro colocado en estrella {star_id}")
                break

    def _draw_graph(self, surface, graph: Graph, color, gi: int):
        drawn_edges = set()
        pos_map = self.scaled_positions.get(gi, {})
        # Aristas
        for star in graph.get_all_stars():
            x, y = pos_map.get(star.id, star.coordinates)
            x, y = self._apply_zoom(x, y)
            for neighbor_id, dist in star.connections.items():
                key = tuple(sorted((star.id, neighbor_id)))
                if key in drawn_edges:
                    continue
                drawn_edges.add(key)
                neighbor = graph.get_star(neighbor_id)
                if neighbor:
                    nx, ny = pos_map.get(neighbor.id, neighbor.coordinates)
                    nx, ny = self._apply_zoom(nx, ny)
                    # Línea levemente más gruesa
                    pygame.draw.line(surface, (140, 140, 170), (x, y), (nx, ny), 2)

        # Estrellas
        for star in graph.get_all_stars():
            x, y = pos_map.get(star.id, star.coordinates)
            x, y = self._apply_zoom(x, y)
            if star.hypergiant:
                radius = 14
                fill_color = (255, 60, 60)
                # Halo externo base
                pygame.draw.circle(surface, (180, 30, 30), (x, y), radius + 6, width=2)
                # Pulso para hipergigantes
                pulse_radius = radius + 8 + int(4 * abs(math.sin(self.pulse_time * math.pi)))
                pulse_alpha = int(127 + 64 * abs(math.sin(self.pulse_time * math.pi)))
                pulse_surface = pygame.Surface((pulse_radius * 2 + 2, pulse_radius * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(pulse_surface, (*fill_color, pulse_alpha), (pulse_radius + 1, pulse_radius + 1), pulse_radius)
                surface.blit(pulse_surface, (x - pulse_radius - 1, y - pulse_radius - 1))
            else:
                radius = 8
                fill_color = color
            
            # Dibujar estrella base
            pygame.draw.circle(surface, fill_color, (x, y), radius)
            
            # Efecto hover
            if star.id == self.hover_star_id:
                hover_radius = radius + 4
                hover_color = (255, 255, 255, int(100 * self.hover_alpha))
                hover_surface = pygame.Surface((hover_radius * 2 + 2, hover_radius * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(hover_surface, hover_color, (hover_radius + 1, hover_radius + 1), hover_radius)
                surface.blit(hover_surface, (x - hover_radius - 1, y - hover_radius - 1))
            
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
            # Fondo espacial dentro del panel con parallax sutil
            self._ensure_starfield()
            if self._starfield_surf is not None:
                bw, bh = self.board_rect.size
                pad = self._starfield_padding
                # Intensidad del parallax (px máximos de desplazamiento)
                parallax_strength = 30
                # Normalizar desplazamiento respecto al centro del panel
                cx, cy = self.board_rect.center
                fx, fy = self.zoom_focus
                dx = 0.0 if bw == 0 else (fx - cx) / bw
                dy = 0.0 if bh == 0 else (fy - cy) / bh
                # Magnitud según nivel de zoom actual
                denom = max(1e-6, (self.zoom_in_factor - 1.0))
                mag = max(0.0, min(1.0, (self.zoom - 1.0) / denom))
                offx = int(-dx * parallax_strength * mag)
                offy = int(-dy * parallax_strength * mag)
                # Área del source dentro del starfield con padding
                src_x = pad + offx
                src_y = pad + offy
                # Asegurar que el área esté dentro de los límites del source
                sw, sh = self._starfield_surf.get_size()
                src_x = max(0, min(sw - bw, src_x))
                src_y = max(0, min(sh - bh, src_y))
                area = pygame.Rect(src_x, src_y, bw, bh)
                surface.blit(self._starfield_surf, self.board_rect.topleft, area)
            else:
                pygame.draw.rect(surface, (0, 0, 0), self.board_rect)
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

        # Dibujar burro si está posicionado
        if self.burro and self.burro.current_star_id is not None:
            pos_map = self.scaled_positions.get(gi, {})
            burro_pos = pos_map.get(self.burro.current_star_id)
            if burro_pos:
                bx, by = burro_pos
                bx, by = self._apply_zoom(bx, by)
                self.burro.render(surface, (bx, by))

        # UI inferior (fuera del tablero): ayuda breve y estadísticas del burro
        if self.font:
            if not self.burro_initial_star_selected and self.burro:
                # Mensaje de selección inicial
                help_lines = [
                    "Click en una estrella para colocar a " + self.burro.nombre,
                ]
            else:
                help_lines = [
                    "TAB: volver al menú principal | E: abrir editor | ESPACIO: comer",
                    "Click en hipergigante enlazada para navegar entre constelaciones"
                ]
            base_y = self.board_rect.bottom + 10 if self.board_rect else surface.get_height() - 50
            x = 20
            for i, t in enumerate(help_lines):
                surf = self.font.render(t, True, (210, 210, 220))
                surface.blit(surf, (x, base_y + i * 22))
            
            # Renderizar estadísticas del burro
            if self.burro and self.burro_initial_star_selected:
                self._render_burro_stats(surface)

    # ----------- Fondo espacial -----------
    def _ensure_starfield(self):
        if not self.board_rect:
            return
        # Generar con padding para permitir recorte con parallax
        size = (self.board_rect.width + 2 * self._starfield_padding,
                self.board_rect.height + 2 * self._starfield_padding)
        if self._starfield_surf is None or self._starfield_size != size:
            self._starfield_surf = self._generate_starfield(size)
            self._starfield_size = size

    def _generate_starfield(self, size: tuple[int, int]) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface((w, h))
        surf.fill((0, 0, 0))
        # Densidad de estrellas: proporcional al área
        n_stars = max(150, min(1000, int(w * h * 0.0005)))
        rng = random.Random(42)  # determinístico por sesión
        for _ in range(n_stars):
            x = rng.randrange(0, w)
            y = rng.randrange(0, h)
            brightness = rng.randint(180, 255)
            color = (brightness, brightness, brightness)
            # Tamaño 1px con posibilidad de 2px ocasional
            if rng.random() < 0.12:
                # pequeño destello 2x2
                pygame.draw.rect(surf, color, pygame.Rect(x, y, 2, 2))
            else:
                surf.set_at((x, y), color)
        return surf

    # ----------- UI de estadísticas del burro -----------
    def _render_burro_stats(self, surface):
        """Renderiza las estadísticas del burro en el área UI inferior."""
        if not self.burro or not self.font:
            return
        
        # Área de estadísticas: esquina inferior derecha
        stats_x = surface.get_width() - 420
        stats_y = self.board_rect.bottom + 15 if self.board_rect else surface.get_height() - 80
        
        # Fondo semitransparente para las estadísticas
        stats_panel = pygame.Surface((400, 70), pygame.SRCALPHA)
        stats_panel.fill((20, 30, 50, 200))
        pygame.draw.rect(stats_panel, (80, 100, 140), (0, 0, 400, 70), width=2, border_radius=8)
        surface.blit(stats_panel, (stats_x, stats_y))
        
        # Nombre del burro
        nombre_surf = self.font.render(f"{self.burro.nombre}", True, (255, 220, 80))
        surface.blit(nombre_surf, (stats_x + 10, stats_y + 8))
        
        # Nivel y experiencia
        nivel_surf = self.font.render(f"Nv.{self.burro.nivel_investigacion} - {self.burro.nivel_experiencia}", True, (200, 200, 220))
        surface.blit(nivel_surf, (stats_x + 200, stats_y + 8))
        
        # Barra de energía (vida)
        self._render_bar(surface, stats_x + 10, stats_y + 32, 180, 12, 
                        self.burro.energia, self.burro.energia_max, 
                        (80, 200, 80), (30, 80, 30), "Energía")
        
        # Barra de hambre (comida)
        self._render_bar(surface, stats_x + 210, stats_y + 32, 180, 12, 
                        self.burro.pasto_disponible, self.burro.pasto_max, 
                        (200, 180, 80), (80, 70, 30), "Pasto")
        
        # Indicador de hambre del burro
        hambre_color = (100, 200, 100) if self.burro.hambre < 50 else ((200, 150, 50) if self.burro.hambre < 80 else (200, 50, 50))
        hambre_text = self.font.render(f"Hambre: {int(self.burro.hambre)}", True, hambre_color)
        surface.blit(hambre_text, (stats_x + 10, stats_y + 50))
    
    def _render_bar(self, surface, x, y, width, height, value, max_value, fill_color, bg_color, label=None):
        """Renderiza una barra de progreso (vida, comida, etc.)."""
        # Fondo
        pygame.draw.rect(surface, bg_color, (x, y, width, height), border_radius=4)
        
        # Relleno
        if max_value > 0:
            fill_width = int((value / max_value) * width)
            if fill_width > 0:
                pygame.draw.rect(surface, fill_color, (x, y, fill_width, height), border_radius=4)
        
        # Borde
        pygame.draw.rect(surface, (150, 150, 170), (x, y, width, height), width=1, border_radius=4)
        
        # Texto de valor
        if self.font:
            value_text = self.font.render(f"{int(value)}/{int(max_value)}", True, (240, 240, 250))
            text_x = x + (width - value_text.get_width()) // 2
            text_y = y + (height - value_text.get_height()) // 2
            surface.blit(value_text, (text_x, text_y - 1))


