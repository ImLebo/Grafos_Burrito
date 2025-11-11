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
import time
from screens.view import View
from typing import List, Sequence, Dict, Tuple, Optional
from models.graph import Graph
from models.burro import Burro


class ConstellationView(View):
    def __init__(self, name: str, graphs: Sequence[Graph], base_color=(255, 255, 255), board_rect: pygame.Rect | None = None, burro_data: dict = None, mission_params: dict | None = None):
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
        # Parámetros de misión
        self.mission_params = mission_params or {
            "maxEatFraction": 0.5,
            "kgPerSecondEat": 5.0,
            "energyPerKgPct": {"Excelente": 5, "Regular": 3, "Malo": 2},
            "researchEnergyPerSecond": 2.0,
            "travelSpeedUnits": 100.0,
            # Nuevo objetivo por defecto: recorrer la mayor cantidad de estrellas antes de llegar al destino
            "routeObjective": "max_stars",
        }
        # Planificación y estados de viaje
        self.blocked_edges: set[tuple[int, int, int]] = set()  # (gi, a, b) con a<b
        self.planned_path: list[int] = []
        self.current_travel: tuple[int, int] | None = None  # (from_id, to_id)
        self.current_travel_time = 0.0
        self.current_travel_duration = 0.0
        self.visited_stars: set[int] = set()
        self.travel_log: list[dict] = []
        self.show_report: bool = False
        self.block_mode: bool = False  # modo de bloqueo de aristas
        self.await_next_step: bool = False  # esperar tecla para avanzar siguiente tramo
        # Recordar último destino para recomputar ruta al cambiar objetivo
        self.last_route_target_id: Optional[int] = None

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
            # Reservar un pie de página para controles y estadísticas para evitar solapamientos
            ui_footer_h = 140
            board_h = max(200, display_h - ui_footer_h)
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
            elif event.key == pygame.K_m:
                # Editar parámetros de misión
                self.requested_view = "mission_params"
            elif event.key == pygame.K_n:
                # Avanzar siguiente tramo de la ruta
                if self.burro and not self.current_travel and self.planned_path:
                    self._advance_to_next_edge()
                    self.await_next_step = False
            elif event.key == pygame.K_r:
                # Mostrar/ocultar reporte
                self.show_report = not self.show_report
            elif event.key == pygame.K_b:
                # Alternar modo bloquear aristas
                self.block_mode = not self.block_mode
            elif event.key == pygame.K_o:
                # Conmutar objetivo de ruta entre max_stars y min_cost
                obj = str(self.mission_params.get("routeObjective", "max_stars")).lower()
                new_obj = "min_cost" if obj == "max_stars" else "max_stars"
                self.mission_params["routeObjective"] = new_obj
                # Recalcular ruta si es posible y no estamos en medio de un tramo
                if self.burro and self.burro_initial_star_selected and self.burro.current_star_id is not None and not self.current_travel and self.last_route_target_id is not None:
                    gi = self.current_index
                    path = self._compute_route(gi, self.burro.current_star_id, self.last_route_target_id)
                    if path and len(path) >= 2:
                        self._start_path(path)
                        self.await_next_step = True
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click izquierdo
            if self.block_mode:
                self._toggle_edge_at_point(event.pos)
            elif not self.burro_initial_star_selected and self.burro:
                # Primera vez: seleccionar estrella inicial para el burro
                self._select_initial_star(event.pos)
            else:
                # Click normal: intentar seleccionar estrella y navegar si es hipergigante con enlace externo
                self._handle_click(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            # Click derecho: definir destino y calcular ruta usando Dijkstra dentro de la constelación actual
            if self.burro and self.burro_initial_star_selected and self.burro.current_star_id is not None:
                gi = self.current_index
                pos_map = self.scaled_positions.get(gi, {})
                target_id = None
                for star_id, (x, y) in pos_map.items():
                    tx, ty = self._apply_zoom(x, y)
                    dx = event.pos[0] - tx
                    dy = event.pos[1] - ty
                    if (dx*dx + dy*dy) <= (18*18):
                        target_id = star_id
                        break
                if target_id is not None and target_id != self.burro.current_star_id:
                    self.last_route_target_id = target_id
                    path = self._compute_route(gi, self.burro.current_star_id, target_id)
                    if path and len(path) >= 2:
                        self._start_path(path)
                        self.await_next_step = True

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

        # Avance del viaje paso a paso
        if self.burro and self.current_travel:
            self.current_travel_time += dt
            if self.current_travel_duration <= 0:
                self.current_travel_duration = 0.001
            if self.current_travel_time >= self.current_travel_duration:
                # Llegamos a la siguiente estrella
                _from, _to = self.current_travel
                self.current_travel = None
                self.current_travel_time = 0.0
                self.current_travel_duration = 0.0
                # Reducir vida por distancia
                dist = self.graphs[gi].get_star(_from).connections.get(_to, 0)
                if self.burro:
                    self.burro.tiempo_vida = max(0, self.burro.tiempo_vida - float(dist))
                # Mover burro y procesar llegada
                pos_map = self.scaled_positions.get(gi, {})
                new_pos = pos_map.get(_to, (0, 0))
                self.burro.moverse_a_estrella(_to, new_pos)
                # Cambiar animación a principal (o hambre si energía baja) al llegar
                try:
                    if self.burro.energia <= 0:
                        self.burro.set_animation("muerte")
                    elif self.burro.energia < 0.2 * self.burro.energia_max and "hambre" in getattr(self.burro, 'animaciones', {}):
                        self.burro.set_animation("hambre")
                    else:
                        self.burro.set_animation("principal")
                except Exception:
                    pass
                self._process_arrival(_to)
                # Si hay más en la ruta, continuar
                if self.planned_path and self.burro and self.burro.esta_vivo() and self.burro.tiempo_vida > 0:
                    # Esperar a que el usuario presione N para continuar
                    self.await_next_step = True
                else:
                    self.planned_path = []
            # Comprobar muerte por vida <= 0
            if self.burro and self.burro.tiempo_vida <= 0 and self.burro.esta_vivo():
                self.burro.morir()

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
        
        # Si el burro está en juego y la estrella es vecina, iniciar animación de movimiento
        if self.burro and self.burro.current_star_id is not None:
            current_star = self.graphs[gi].get_star(self.burro.current_star_id)
            if current_star and clicked_id in current_star.connections:
                # Iniciar viaje inmediato hacia la estrella clickeada
                self.planned_path = [self.burro.current_star_id, clicked_id]
                self._advance_to_next_edge()
                self.await_next_step = False
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
                    # Visualizar arista bloqueada
                    if (gi, key[0], key[1]) in self.blocked_edges:
                        pygame.draw.line(surface, (200, 80, 80), (x, y), (nx, ny), 3)
                        edge_blocked = True
                    else:
                        # Línea base
                        pygame.draw.line(surface, (140, 140, 170), (x, y), (nx, ny), 2)
                        edge_blocked = False

                    # Etiquetar costo (distancia) en el punto medio para validar Dijkstra
                    if self.font:
                        try:
                            weight_val = float(dist)
                        except Exception:
                            weight_val = 0.0
                        if abs(weight_val - int(weight_val)) < 1e-6:
                            text = str(int(weight_val))
                        else:
                            text = f"{weight_val:.1f}"

                        text_color = (235, 240, 250) if not edge_blocked else (240, 110, 110)
                        ts = self.font.render(text, True, text_color)
                        # Fondo semitransparente para legibilidad
                        pad_w, pad_h = 6, 4
                        bg_w, bg_h = ts.get_width() + pad_w * 2, ts.get_height() + pad_h * 2
                        bg = pygame.Surface((bg_w, bg_h), pygame.SRCALPHA)
                        bg_color = (10, 15, 25, 190) if not edge_blocked else (40, 10, 10, 190)
                        bg.fill(bg_color)

                        # Centro de la arista con leve desplazamiento perpendicular
                        mx = (x + nx) / 2.0
                        my = (y + ny) / 2.0
                        dx = nx - x
                        dy = ny - y
                        length = math.hypot(dx, dy)
                        if length > 1e-3:
                            off = 10
                            px = -dy / length
                            py = dx / length
                            mx += px * off
                            my += py * off
                        blit_x = int(mx - bg_w / 2)
                        blit_y = int(my - bg_h / 2)
                        surface.blit(bg, (blit_x, blit_y))
                        surface.blit(ts, (blit_x + pad_w, blit_y + pad_h))

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
            
            # Dibujar estrella base (visitadas resaltadas)
            base_col = fill_color
            if star.id in self.visited_stars:
                base_col = (base_col[0], min(255, base_col[1] + 40), min(255, base_col[2] + 40))
            pygame.draw.circle(surface, base_col, (x, y), radius)
            
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

        # Ruta planeada resaltada
        if self.planned_path and len(self.planned_path) >= 2:
            route_color = (60, 220, 255)
            for i in range(len(self.planned_path) - 1):
                a = self.planned_path[i]
                b = self.planned_path[i + 1]
                if (a not in pos_map) or (b not in pos_map):
                    continue
                ax, ay = self._apply_zoom(*pos_map[a])
                bx, by = self._apply_zoom(*pos_map[b])
                pygame.draw.line(surface, route_color, (ax, ay), (bx, by), 4)
                # nodos en ruta
                pygame.draw.circle(surface, (60, 220, 255), (ax, ay), 5)
            bx, by = self._apply_zoom(*pos_map[self.planned_path[-1]])
            pygame.draw.circle(surface, (60, 220, 255), (bx, by), 6)

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

        # Dibujar burro: si está viajando, interpolar entre estrellas; si no, dibujar en estrella actual
        if self.burro and (self.burro.current_star_id is not None or self.current_travel):
            pos_map = self.scaled_positions.get(gi, {})
            draw_pos = None
            if self.current_travel:
                a, b = self.current_travel
                a_pos = pos_map.get(a)
                b_pos = pos_map.get(b)
                if a_pos and b_pos and self.current_travel_duration > 1e-6:
                    t = max(0.0, min(1.0, self.current_travel_time / self.current_travel_duration))
                    # Interpolación lineal
                    ix = a_pos[0] + (b_pos[0] - a_pos[0]) * t
                    iy = a_pos[1] + (b_pos[1] - a_pos[1]) * t
                    draw_pos = (int(ix), int(iy))
            if draw_pos is None and self.burro.current_star_id is not None:
                draw_pos = pos_map.get(self.burro.current_star_id)
            if draw_pos:
                bx, by = self._apply_zoom(draw_pos[0], draw_pos[1])
                self.burro.render(surface, (bx, by))

        # UI inferior (fuera del tablero): ayuda breve y estadísticas del burro
        if self.font:
            # Primero, renderizar estadísticas (panel a la derecha)
            if self.burro and self.burro_initial_star_selected:
                self._render_burro_stats(surface)

            # Luego, ayuda/controles, posicionada para no interferir con el panel
            if not self.burro_initial_star_selected and self.burro:
                # Mensaje de selección inicial
                help_lines = [
                    "Click en una estrella para colocar a " + self.burro.nombre,
                ]
                base_y = self.board_rect.bottom + 10 if self.board_rect else surface.get_height() - 50
            else:
                obj = str(self.mission_params.get("routeObjective", "max_stars")).lower()
                obj_label = "Objetivo: Max estrellas" if obj == "max_stars" else "Objetivo: Menor costo"
                help_lines = [
                    f"TAB: menú | E: editor grafos | M: parámetros | R: reporte | B: bloquear arista | N: siguiente tramo | O: cambiar objetivo",
                    f"{obj_label} | Click en hipergigante enlazada para navegar | Click derecho: fijar destino"
                ]
                # Altura adicional para que no quede 'metido' dentro del panel de estadísticas (70px alto + margen)
                extra_offset = 78 if (self.burro and self.burro_initial_star_selected) else 0
                base_y = (self.board_rect.bottom + 10 + extra_offset) if self.board_rect else surface.get_height() - 50

            x = 20
            # Evitar salir por la parte inferior si la ventana es muy baja
            max_y = surface.get_height() - 10
            for i, t in enumerate(help_lines):
                y = min(max_y - 22, base_y + i * 22)
                surf = self.font.render(t, True, (210, 210, 220))
                surface.blit(surf, (x, y))

        # Overlay reporte simple
        if self.show_report and self.font:
            self._render_report(surface)

    # ----------- Ruta y Dijkstra -----------
    def _edge_blocked(self, gi: int, a: int, b: int) -> bool:
        x, y = (a, b) if a < b else (b, a)
        return (gi, x, y) in self.blocked_edges

    def _dijkstra_path(self, gi: int, start_id: int, target_id: int) -> list[int]:
        import heapq
        g = self.graphs[gi]
        dist: Dict[int, float] = {start_id: 0.0}
        prev: Dict[int, Optional[int]] = {start_id: None}
        pq = [(0.0, start_id)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == target_id:
                break
            if d > dist.get(u, float('inf')):
                continue
            u_star = g.get_star(u)
            if not u_star:
                continue
            for v, w in u_star.connections.items():
                a, b = (u, v) if u < v else (v, u)
                if self._edge_blocked(gi, a, b):
                    continue
                nd = d + float(w)
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(pq, (nd, v))
        if target_id not in prev and target_id != start_id:
            return []
        # Reconstruir
        path = []
        cur = target_id
        path.append(cur)
        while prev.get(cur) is not None:
            cur = prev[cur]
            path.append(cur)
        path.reverse()
        return path

    # ---------------- Algoritmo alternativo: maximizar estrellas visitadas ----------------
    def _max_stars_path(self, gi: int, start_id: int, target_id: int, life_budget: float, time_limit: float = 0.45) -> list[int]:
        """Devuelve una ruta que alcanza target_id desde start_id visitando la mayor cantidad
        posible de estrellas únicas sin exceder el 'life_budget' (tiempo_vida disponible).

        Nota: Este problema se parece a un 'longest path' con restricción de costo (NP-difícil).
        Se implementa un DFS con poda por tiempo y por vida restante. Si el grafo crece, se corta.
        """
        g = self.graphs[gi]
        if start_id == target_id:
            return [start_id]
        # Preparar índice compacto para bitmask (solo estrellas del grafo actual)
        stars = g.get_all_stars()
        id_list = [s.id for s in stars]
        id_to_idx = {sid: i for i, sid in enumerate(id_list)}
        n = len(id_list)
        start_time = time.time()
        best_path: list[int] = []
        best_count: int = -1
        best_dist: float = float('inf')

        # Preprocesar adyacencias considerando aristas bloqueadas
        adj: Dict[int, list[tuple[int, float]]] = {}
        for s in stars:
            lst = []
            for nb, w in s.connections.items():
                a, b = (s.id, nb) if s.id < nb else (nb, s.id)
                if self._edge_blocked(gi, a, b):
                    continue
                lst.append((nb, float(w)))
            adj[s.id] = lst

        # DFS con poda
        def dfs(node: int, remaining: float, visited_mask: int, path: list[int], dist_acc: float):
            nonlocal best_path, best_count, best_dist
            # Corte por tiempo
            if time.time() - start_time > time_limit:
                return
            # Si alcanzamos destino, evaluar
            if node == target_id:
                count = bin(visited_mask).count('1')
                if (count > best_count) or (count == best_count and dist_acc < best_dist):
                    best_count = count
                    best_dist = dist_acc
                    best_path = path[:]
                # No seguir expandiendo desde el destino (para evitar loops que regresen)
                return
            # Poda optimista: máximo adicional serían todas las no visitadas restantes
            visited_count = bin(visited_mask).count('1')
            remaining_possible = n - visited_count
            if visited_count + remaining_possible < best_count:
                return
            # Expandir vecinos no visitados
            for nb, w in adj.get(node, []):
                idx = id_to_idx.get(nb)
                if idx is None:
                    continue
                bit = 1 << idx
                if visited_mask & bit:
                    continue  # evitar revisitar para maximizar únicas
                if w > remaining:
                    continue
                path.append(nb)
                dfs(nb, remaining - w, visited_mask | bit, path, dist_acc + w)
                path.pop()

        # Inicializar máscara con start
        start_mask = 1 << id_to_idx[start_id]
        dfs(start_id, life_budget, start_mask, [start_id], 0.0)
        return best_path

    # ---------------- Versión mejorada para maximizar estrellas ----------------
    def _max_stars_path_v2(self, gi: int, start_id: int, target_id: int, life_budget: float) -> list[int]:
        """Mejora del algoritmo de maximización de estrellas:
        - Sin límite de tiempo para grafos pequeños (n <= 18).
        - DFS con poda por memoización: (node, visited_mask, remaining_rounded) -> mejor_conteo_restante.
        - Orden de exploración de vecinos por menor costo para permitir más expansiones tempranas.
        - Control de profundidad cuando n grande: fallback a versión original si n > 26.
        - Criterio: maximizar num. de estrellas únicas; en empate, menor distancia total.
        """
        g = self.graphs[gi]
        if start_id == target_id:
            return [start_id]
        stars = g.get_all_stars()
        if not stars:
            return []
        n = len(stars)
        # Si el grafo es muy grande, usar la versión original con límite de tiempo más amplio
        if n > 26:
            return self._max_stars_path(gi, start_id, target_id, life_budget, time_limit=0.8)
        id_list = [s.id for s in stars]
        id_to_idx = {sid: i for i, sid in enumerate(id_list)}
        # Preprocesar adyacencias (filtra aristas bloqueadas)
        adj: Dict[int, list[tuple[int, float]]] = {}
        for s in stars:
            vecs = []
            for nb, w in s.connections.items():
                a, b = (s.id, nb) if s.id < nb else (nb, s.id)
                if self._edge_blocked(gi, a, b):
                    continue
                vecs.append((nb, float(w)))
            # Ordenar por peso ascendente para liberar más potencial de expansión
            vecs.sort(key=lambda t: t[1])
            adj[s.id] = vecs
        start_mask = 1 << id_to_idx[start_id]
        best_path: list[int] = []
        best_count = -1
        best_dist = float('inf')
        # Memo para poda: guarda el máximo conteo alcanzado observado para estado y si futuro no puede superar best_count => cortar
        memo: Dict[tuple[int, int, int], int] = {}
        # Distancia acumulada para debug/prioridad
        def dfs(node: int, remaining: float, visited_mask: int, path: list[int], dist_acc: float):
            nonlocal best_path, best_count, best_dist
            # Si alcanzamos destino evaluamos y no expandimos más
            if node == target_id:
                count = path.__len__()
                if (count > best_count) or (count == best_count and dist_acc < best_dist):
                    best_count = count
                    best_dist = dist_acc
                    best_path = path[:]
                return
            visited_count = path.__len__()
            remaining_possible = n - visited_count
            # Poda optimista global
            if visited_count + remaining_possible < best_count:
                return
            # Memo key (redondeo del restante para reducir estados)
            rem_key = int(remaining * 100)  # centésimas
            key = (node, visited_mask, rem_key)
            prev_best = memo.get(key)
            # Conteo máximo teórico partiendo de este estado
            theoretical_max = visited_count + remaining_possible
            if prev_best is not None and theoretical_max <= prev_best:
                return
            memo[key] = theoretical_max
            # Expandir vecinos no visitados
            for nb, w in adj.get(node, []):
                if w > remaining:
                    continue
                idx = id_to_idx.get(nb)
                if idx is None:
                    continue
                bit = 1 << idx
                if visited_mask & bit:
                    continue  # no revisitar, no aporta al conteo
                path.append(nb)
                dfs(nb, remaining - w, visited_mask | bit, path, dist_acc + w)
                path.pop()
        dfs(start_id, life_budget, start_mask, [start_id], 0.0)
        # Si no encontró nada (por ejemplo target inalcanzable), fallback a Dijkstra
        if not best_path:
            return self._dijkstra_path(gi, start_id, target_id)
        return best_path

    def _compute_route(self, gi: int, start_id: int, target_id: int) -> list[int]:
        """Selecciona el algoritmo de ruta según mission_params['routeObjective']."""
        objective = str(self.mission_params.get("routeObjective", "max_stars")).lower()
        life_budget = 0.0
        if self.burro and self.burro.tiempo_vida is not None:
            try:
                life_budget = float(self.burro.tiempo_vida)
            except Exception:
                life_budget = 0.0
        if objective == "min_cost":
            return self._dijkstra_path(gi, start_id, target_id)
        # max_stars (por defecto) - usar versión mejorada
        path = self._max_stars_path_v2(gi, start_id, target_id, life_budget)
        if not path:
            # Fallback a dijkstra si no se encontró ruta
            return self._dijkstra_path(gi, start_id, target_id)
        return path

    def _start_path(self, path: list[int]):
        self.planned_path = path[:]
        # No iniciar automáticamente: esperar tecla N del usuario
        self.current_travel = None
        self.current_travel_time = 0.0
        self.current_travel_duration = 0.0

    def _advance_to_next_edge(self):
        if not self.burro or not self.planned_path or self.burro.current_star_id is None:
            self.current_travel = None
            return
        # Encontrar índice actual en la ruta
        try:
            idx = self.planned_path.index(self.burro.current_star_id)
        except ValueError:
            idx = -1
        if idx == -1 and self.planned_path[0] == self.burro.current_star_id:
            idx = 0
        if idx < 0:
            # arrancar desde el primer nodo como origen
            if len(self.planned_path) >= 2:
                a, b = self.planned_path[0], self.planned_path[1]
            else:
                self.current_travel = None
                return
        else:
            if idx + 1 >= len(self.planned_path):
                self.current_travel = None
                return
            a, b = self.planned_path[idx], self.planned_path[idx + 1]
        self.current_travel = (a, b)
        # Duración proporcional a la distancia y velocidad
        speed = max(1e-3, float(self.mission_params.get("travelSpeedUnits", 100.0)))
        dist = float(self.graphs[self.current_index].get_star(a).connections.get(b, 0.0))
        self.current_travel_duration = max(0.2, dist / speed)
        self.current_travel_time = 0.0
        # Animación de navegación durante el tramo
        try:
            self.burro.set_animation("navegacion")
        except Exception:
            pass

    # ----------- Llegada / lógica de parada -----------
    def _process_arrival(self, star_id: int):
        gi = self.current_index
        g = self.graphs[gi]
        star = g.get_star(star_id)
        if not (self.burro and star):
            return
        self.visited_stars.add(star_id)
        # Bonificación por hipergigante al LLEGAR
        if star.hypergiant:
            # +50% de energía actual (cap a max) y duplicar pasto
            add = 0.5 * self.burro.energia
            self.burro.energia = min(self.burro.energia_max, self.burro.energia + add)
            # duplicar bodega (clamp a 2x del máximo inicial)
            new_pasto = self.burro.pasto_disponible * 2
            cap = max(self.burro.pasto_max, self.burro.pasto_disponible * 2)
            self.burro.pasto_disponible = min(cap, int(new_pasto))
            self.burro.pasto_max = max(self.burro.pasto_max, self.burro.pasto_disponible)
        # Estancia: comer y luego investigar
        max_eat_frac = float(self.mission_params.get("maxEatFraction", 0.5))
        kg_per_s = float(self.mission_params.get("kgPerSecondEat", 5.0))
        research_rate = float(self.mission_params.get("researchEnergyPerSecond", 2.0))
        salud = str(getattr(self.burro, "estado_salud", "Excelente"))
        pct_map = self.mission_params.get("energyPerKgPct", {"Excelente": 5, "Regular": 3, "Malo": 2})
        pct = float(pct_map.get(salud, pct_map.get("Excelente", 5)))
        eat_time = max(0.0, float(star.time_to_eat) * max_eat_frac)
        research_time = max(0.0, float(star.time_to_research) - eat_time)
        # Comer
        max_kg = kg_per_s * eat_time
        kg_eaten = min(self.burro.pasto_disponible, max_kg)
        self.burro.pasto_disponible -= int(kg_eaten)
        # Energía ganada es % de energia_max por kg
        energia_gain = (pct / 100.0) * self.burro.energia_max * kg_eaten
        self.burro.energia = min(self.burro.energia_max, self.burro.energia + energia_gain)
        # Investigación consume energía
        energia_lost = research_rate * research_time
        self.burro.energia = max(0.0, self.burro.energia - energia_lost)
        # Registrar
        self.travel_log.append({
            "graph": g.name,
            "star": star.label,
            "star_id": star.id,
            "kg_eaten": float(int(kg_eaten)),
            "energia_gain": int(energia_gain),
            "energia_lost": int(energia_lost),
            "eat_time": round(eat_time, 2),
            "research_time": round(research_time, 2),
            "hypergiant": bool(star.hypergiant),
            "vida_restante": round(float(self.burro.tiempo_vida), 2),
            "energia": int(self.burro.energia),
        })
        # Muerte si energía cae a 0
        if self.burro.energia <= 0 and self.burro.esta_vivo():
            self.burro.morir()

    # ----------- Reporte -----------
    def _render_report(self, surface: pygame.Surface):
        w, h = surface.get_size()
        panel_w, panel_h = min(900, w - 80), min(360, h - 80)
        x, y = (w - panel_w) // 2, h - panel_h - 10
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((15, 25, 45, 220))
        pygame.draw.rect(panel, (90, 110, 150), panel.get_rect(), width=2, border_radius=10)
        if not self.font:
            return
        title = self.font.render("Reporte del viaje (últimas 10 paradas)", True, (240, 240, 250))
        panel.blit(title, (16, 10))
        start_y = 40
        for item in self.travel_log[-10:]:
            line = f"{item['graph']} - {item['star']} | kg:{item['kg_eaten']} +E:{item['energia_gain']} -E:{item['energia_lost']} tInvest:{item['research_time']}s vida:{item['vida_restante']}"
            ls = self.font.render(line, True, (210, 220, 230))
            panel.blit(ls, (16, start_y))
            start_y += 20
        surface.blit(panel, (x, y))

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

    # ----------- Bloqueo de aristas -----------
    def _toggle_edge_at_point(self, pos: tuple[int, int]):
        gi = self.current_index
        g = self.graphs[gi]
        pos_map = self.scaled_positions.get(gi, {})
        # Buscar la arista más cercana al click
        closest = None
        best_d2 = 9999999
        for star in g.get_all_stars():
            x1, y1 = self._apply_zoom(*pos_map.get(star.id, star.coordinates))
            for nb, dist in star.connections.items():
                if nb <= star.id:
                    continue  # evitar duplicados
                x2, y2 = self._apply_zoom(*pos_map.get(nb, g.get_star(nb).coordinates))
                d2 = self._point_segment_distance_squared(pos, (x1, y1), (x2, y2))
                if d2 < best_d2:
                    best_d2 = d2
                    closest = (star.id, nb)
        if closest and best_d2 <= 22*22:  # umbral
            a, b = closest
            key = (gi, min(a, b), max(a, b))
            if key in self.blocked_edges:
                self.blocked_edges.remove(key)
            else:
                self.blocked_edges.add(key)

    def _point_segment_distance_squared(self, p: tuple[int, int], a: tuple[int, int], b: tuple[int, int]) -> float:
        # Distancia punto-segmento (cuadrada) para selección de arista
        import math
        px, py = p
        ax, ay = a
        bx, by = b
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        v_len2 = vx*vx + vy*vy
        if v_len2 <= 1e-6:
            return (px-ax)**2 + (py-ay)**2
        t = (wx*vx + wy*vy) / v_len2
        if t < 0: t = 0
        elif t > 1: t = 1
        cx, cy = ax + t*vx, ay + t*vy
        dx, dy = px - cx, py - cy
        return dx*dx + dy*dy

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
        
        # Barra de pasto (bodega)
        self._render_bar(surface, stats_x + 210, stats_y + 32, 180, 12,
                         self.burro.pasto_disponible, self.burro.pasto_max,
                         (200, 180, 80), (80, 70, 30), "Pasto")
        # Vida restante mostrada como texto
        vida_text = self.font.render(f"Vida: {int(self.burro.tiempo_vida)} al", True, (200, 210, 230))
        surface.blit(vida_text, (stats_x + 10, stats_y + 50))
    
    def _render_bar(self, surface, x, y, width, height, value, max_value, fill_color, bg_color, label=None):
        """Renderiza una barra de progreso (vida, comida, etc.)."""
        # Etiqueta (si existe), colocada por encima para no quedar dentro de la barra
        if self.font and label:
            label_surf = self.font.render(str(label), True, (220, 225, 235))
            surface.blit(label_surf, (x, y - 14))

        # Sombras sutiles bajo la barra para sensación de profundidad
        shadow_rect = pygame.Rect(x, y + 2, width, height)
        shadow = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 70), shadow.get_rect(), border_radius=6)
        surface.blit(shadow, shadow_rect.topleft)

        # Fondo con leve degradado
        bg_rect = pygame.Rect(x, y, width, height)
        bg_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        # Degradado vertical del fondo (más claro arriba)
        r, g, b = bg_color
        for i in range(height):
            t = i / max(1, height - 1)
            lr = min(255, int(r * (0.9 + 0.1 * (1 - t))))
            lg = min(255, int(g * (0.9 + 0.1 * (1 - t))))
            lb = min(255, int(b * (0.9 + 0.1 * (1 - t))))
            pygame.draw.line(bg_surf, (lr, lg, lb), (0, i), (width, i))
        # Redondear el fondo
        rounded_bg = pygame.Surface((width, height), pygame.SRCALPHA)
        pygame.draw.rect(rounded_bg, (255, 255, 255, 255), (0, 0, width, height), border_radius=6)
        bg_surf.blit(rounded_bg, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        surface.blit(bg_surf, bg_rect.topleft)
        
        # Relleno
        if max_value > 0:
            fill_width = int((value / max_value) * width)
            if fill_width > 0:
                # Degradado del relleno (más brillante arriba)
                fr, fg, fb = fill_color
                fill_surf = pygame.Surface((fill_width, height), pygame.SRCALPHA)
                for i in range(height):
                    t = i / max(1, height - 1)
                    # Ligeramente más brillante en la parte superior
                    br = min(255, int(fr * (1.05 - 0.15 * t)))
                    bgc = min(255, int(fg * (1.05 - 0.15 * t)))
                    bb = min(255, int(fb * (1.05 - 0.15 * t)))
                    pygame.draw.line(fill_surf, (br, bgc, bb), (0, i), (fill_width, i))
                # Redondear el relleno
                rounded_fill = pygame.Surface((fill_width, height), pygame.SRCALPHA)
                pygame.draw.rect(rounded_fill, (255, 255, 255, 255), (0, 0, fill_width, height), border_radius=6)
                fill_surf.blit(rounded_fill, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                surface.blit(fill_surf, (x, y))

                # Brillo/gloss superior
                gloss_h = max(2, height // 2)
                gloss = pygame.Surface((fill_width, gloss_h), pygame.SRCALPHA)
                pygame.draw.rect(gloss, (255, 255, 255, 40), (0, 0, fill_width, gloss_h), border_radius=6)
                surface.blit(gloss, (x, y))
        
        # Borde doble (externo e interno) para detalle
        pygame.draw.rect(surface, (150, 150, 170), (x, y, width, height), width=1, border_radius=6)
        pygame.draw.rect(surface, (60, 70, 100), (x+1, y+1, width-2, height-2), width=1, border_radius=5)

        # Indicador de estado bajo (pulso sutil)
        try:
            ratio = (value / max_value) if max_value > 0 else 0
            if ratio <= 0.2 and fill_width > 0:
                pulse = 0.5 + 0.5 * abs(math.sin(self.pulse_time * math.pi))
                pulse_alpha = int(60 + 80 * pulse)
                warn = pygame.Surface((fill_width, height), pygame.SRCALPHA)
                pygame.draw.rect(warn, (255, 80, 80, pulse_alpha), (0, 0, fill_width, height), border_radius=6)
                surface.blit(warn, (x, y))
        except Exception:
            pass
        
        # Texto de valor: fuera de la barra para mejor legibilidad
        if self.font:
            value_text = self.font.render(f"{int(value)}/{int(max_value)}", True, (240, 240, 250))
            text_x = x + width + 8
            text_y = y + (height - value_text.get_height()) // 2 - 1
            surface.blit(value_text, (text_x, text_y))


