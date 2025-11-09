"""Vista de editor para crear una nueva constelación de forma interactiva.

Controles:
- F1 / TAB: volver a la vista de constelaciones
- E: limpiar la constelación en edición
- L: cargar constelación existente para editar
- N: armar modo creación; el siguiente click dentro del tablero crea una estrella
- Click: seleccionar una estrella (si es hipergigante, solo selecciona)
- K: conectar las dos últimas estrellas seleccionadas (distancia euclidiana)
- H: si no es hipergigante, la marca; si ya es hipergigante, inicia enlace externo (seleccionar constelación y estrella hipergigante destino)
- +/-: cambia el radio de la estrella seleccionada
- T/G: aumenta/disminuye timeToEat de la estrella seleccionada
- U/J: aumenta/disminuye amountOfEnergy de la estrella seleccionada
- C: abrir selector de color para la constelación
- S: guarda la constelación nueva en data/constellations.json
"""
from __future__ import annotations
import json
import math
from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from screens.view import View
import random
from models.graph import Graph
from models.star import Star


class ConstellationEditorView(View):
    def __init__(self, existing_graphs: Sequence[Graph] | None = None, board_rect: Optional[pygame.Rect] = None):
        super().__init__()
        self.font = None
        self.board_rect: Optional[pygame.Rect] = board_rect
        self.graph = Graph("Nueva Constelación", color=(255, 255, 255))
        self.create_mode: bool = False  # tras presionar N, el próximo click crea una estrella
        self.selection_history: List[int] = []  # últimas selecciones para conectar con K
        self.hover_id: Optional[int] = None
        
        # Referencias a constelaciones existentes (para enlaces externos y edición)
        self.existing_graphs: List[Graph] = list(existing_graphs) if existing_graphs else []

        # IDs utilizados globalmente para evitar colisiones al guardar
        self.used_ids: set[int] = set()
        if existing_graphs:
            for g in existing_graphs:
                for s in g.get_all_stars():
                    self.used_ids.add(s.id)
        self.next_id: int = (max(self.used_ids) + 1) if self.used_ids else 1
        
        # Selector de color
        self.color_palette: List[Tuple[int, int, int]] = [
            (255, 255, 255),  # blanco
            (255, 255, 0),    # amarillo
            (255, 165, 0),    # naranja
            (255, 0, 0),      # rojo
            (255, 0, 255),    # magenta
            (128, 0, 255),    # púrpura
            (0, 0, 255),      # azul
            (0, 255, 255),    # cyan
            (0, 255, 0),      # verde
            (127, 255, 0),    # verde-amarillo
            (200, 200, 200),  # gris claro
            (100, 100, 100),  # gris
        ]
        self.color_selector_visible: bool = False
        self.color_rects: List[pygame.Rect] = []  # se calculan en render
        self.hover_color_idx: Optional[int] = None
        
        # Selector de constelaciones para editar
        self.constellation_selector_visible: bool = False
        self.constellation_rects: List[pygame.Rect] = []
        self.hover_constellation_idx: Optional[int] = None
        
        # Modo de enlace externo para hipergigantes
        self.link_mode: bool = False  # activado al clickear hipergigante
        self.link_source_id: Optional[int] = None  # id de la hipergigante origen
        self.link_target_constellation_idx: Optional[int] = None  # índice en existing_graphs
        self.link_step: str = "select_constellation"  # "select_constellation" o "select_star"
        
        # Seguimiento de constelación en edición (para actualizar en lugar de crear nueva)
        self.editing_constellation_idx: Optional[int] = None  # None = nueva, número = editando existente
        
        # Mensaje de guardado
        self.save_message: Optional[str] = None
        self.save_message_timer: float = 0.0
        self.save_message_duration: float = 3.0  # segundos
        
        # Sistema de coordenadas escaladas (similar a constellation_view)
        self.scaled_positions: Dict[int, Tuple[int, int]] = {}  # star_id -> (screen_x, screen_y)
        self.scale: float = 1.0
        self.offset_x: float = 0.0
        self.offset_y: float = 0.0
        
        # Edición de nombre de constelación
        self.editing_name: bool = False
        self.name_input: str = ""
        self.name_cursor_visible: bool = True
        self.name_cursor_timer: float = 0.0
        # Fondo de estrellas del panel de edición
        self._starfield_surf = None
        self._starfield_size = (0, 0)

    # -------------- Ciclo de vida --------------
    def on_enter(self):
        if pygame.font:
            try:
                self.font = pygame.font.SysFont("Consolas", 18)
            except Exception:
                self.font = None
        if self.board_rect is None:
            display_w, display_h = pygame.display.get_surface().get_size()
            board_h = int(display_h * 0.8)
            self.board_rect = pygame.Rect(0, 0, display_w, board_h)
        
        # Calcular escala inicial
        self._ensure_starfield()
        self._compute_scale()

    # -------------- Entrada --------------
    def handle_event(self, event):
        # Si estamos editando el nombre, capturar entrada de texto
        if self.editing_name:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                    # Confirmar el nombre
                    if self.name_input.strip():
                        self.graph.name = self.name_input.strip()
                    self.editing_name = False
                    self.name_input = ""
                elif event.key == pygame.K_ESCAPE:
                    # Cancelar edición
                    self.editing_name = False
                    self.name_input = ""
                elif event.key == pygame.K_BACKSPACE:
                    # Borrar carácter
                    self.name_input = self.name_input[:-1]
                else:
                    # Agregar carácter (solo letras, números, espacios y algunos símbolos)
                    if event.unicode and (event.unicode.isalnum() or event.unicode in " -_.,"):
                        if len(self.name_input) < 50:  # Límite de caracteres
                            self.name_input += event.unicode
            return  # No procesar otros eventos mientras se edita el nombre
        
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                # Volver al menú principal
                self.requested_view = "main_menu"
            elif event.key == pygame.K_F1:
                # Volver a la vista de constelaciones
                self.requested_view = "constellation"
            elif event.key == pygame.K_e:
                # limpiar
                self.graph = Graph("Nueva Constelación", color=(255, 255, 255))
                self.selection_history.clear()
                self.editing_constellation_idx = None
                self.link_mode = False
                self._compute_scale()  # Resetear escala
            elif event.key == pygame.K_l:
                # Abrir selector de constelaciones para editar
                self.constellation_selector_visible = True
            elif event.key == pygame.K_n:
                self.create_mode = True
            elif event.key == pygame.K_k:
                self._connect_last_two()
            elif event.key == pygame.K_j:
                self._handle_h_press()
            elif event.key in (pygame.K_PLUS, pygame.K_EQUALS):  # + (teclado)
                self._change_radius(0.1)
            elif event.key == pygame.K_MINUS:
                self._change_radius(-0.1)
            elif event.key == pygame.K_t:
                self._change_time_to_eat(1)
            elif event.key == pygame.K_g:
                self._change_time_to_eat(-1)
            elif event.key == pygame.K_u:
                self._change_energy(1)
            elif event.key == pygame.K_j:
                self._change_energy(-1)
            elif event.key == pygame.K_c:
                # Toggle selector de color
                self.color_selector_visible = not self.color_selector_visible
            elif event.key == pygame.K_r:
                # Renombrar constelación
                self.editing_name = True
                self.name_input = self.graph.name
            elif event.key == pygame.K_ESCAPE:
                # Cerrar cualquier modal o modo
                if self.color_selector_visible:
                    self.color_selector_visible = False
                elif self.constellation_selector_visible:
                    self.constellation_selector_visible = False
                elif self.link_mode:
                    self.link_mode = False
                    self.link_source_id = None
                    self.link_target_constellation_idx = None
                    self.link_step = "select_constellation"
            elif event.key == pygame.K_s:
                self._save_to_json("data/constellations.json")

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Click en selector de constelaciones
            if self.constellation_selector_visible and self.hover_constellation_idx is not None:
                self._load_constellation(self.hover_constellation_idx)
                self.constellation_selector_visible = False
                return
            
            # Click en selector de color
            if self.color_selector_visible and self.hover_color_idx is not None:
                self.graph.color = self.color_palette[self.hover_color_idx]
                self.color_selector_visible = False
                return
            
            # Modo de enlace externo
            if self.link_mode:
                self._handle_link_click(event.pos)
                return
            
            if not self.board_rect or not self.board_rect.collidepoint(event.pos):
                return
            if self.create_mode:
                self._create_star_at(event.pos)
                self.create_mode = False
            else:
                # Simplemente seleccionar (aunque sea hipergigante). El enlace externo ahora se inicia con H cuando ya es hipergigante.
                self._select_star_at(event.pos)

    def update(self, dt: float):
        # Actualizar temporizador de mensaje de guardado
        if self.save_message_timer > 0:
            self.save_message_timer -= dt
            if self.save_message_timer <= 0:
                self.save_message = None
        
        # detectar hover
        mouse = pygame.mouse.get_pos()
        
        # Si el selector de constelaciones está visible
        if self.constellation_selector_visible and self.constellation_rects:
            self.hover_constellation_idx = None
            for i, rect in enumerate(self.constellation_rects):
                if rect.collidepoint(mouse):
                    self.hover_constellation_idx = i
                    break
        # Si el selector de color está visible, detectar hover en colores
        elif self.color_selector_visible and self.color_rects:
            self.hover_color_idx = None
            for i, rect in enumerate(self.color_rects):
                if rect.collidepoint(mouse):
                    self.hover_color_idx = i
                    break
        else:
            self.hover_id = self._hit_test(mouse)
        
        # Animar cursor de entrada de texto
        if self.editing_name:
            self.name_cursor_timer += dt
            if self.name_cursor_timer >= 0.5:
                self.name_cursor_visible = not self.name_cursor_visible
                self.name_cursor_timer = 0.0

    # -------------- Helpers de edición --------------
    def _create_star_at(self, pos: Tuple[int, int]):
        # mapear a coords relativas del tablero
        if not self.board_rect:
            return
        # Convertir coordenadas de pantalla a coordenadas del mundo (JSON)
        world_x, world_y = self._screen_to_world(pos[0], pos[1])
        
        # crear star con valores por defecto
        new_id = self._next_free_id()
        label = f"New{new_id}"
        star = Star(new_id, label, world_x, world_y, radius=0.5, time_to_eat=1, energy=1, hypergiant=False)
        self.graph.add_star(star)
        self.used_ids.add(new_id)
        self.selection_history.append(new_id)
        self.selection_history = self.selection_history[-2:]
        
        # Recalcular escala para ajustar a las nuevas estrellas
        self._compute_scale()

    def _select_star_at(self, pos: Tuple[int, int]):
        sid = self._hit_test(pos)
        if sid is None:
            return
        # push a historial (guardamos las dos últimas)
        if not self.selection_history or self.selection_history[-1] != sid:
            self.selection_history.append(sid)
            self.selection_history = self.selection_history[-2:]

    def _hit_test(self, pos: Tuple[int, int]) -> Optional[int]:
        # radios de selección usando coordenadas de pantalla
        for s in self.graph.get_all_stars():
            sx, sy = self._world_to_screen(s.coordinates[0], s.coordinates[1])
            dx = pos[0] - sx
            dy = pos[1] - sy
            r = 12
            if dx * dx + dy * dy <= r * r:
                return s.id
        return None

    def _connect_last_two(self):
        if len(self.selection_history) < 2:
            return
        a, b = self.selection_history[-2], self.selection_history[-1]
        if a == b:
            return
        sa = self.graph.get_star(a)
        sb = self.graph.get_star(b)
        if not sa or not sb:
            return
        dist = math.hypot(sa.coordinates[0] - sb.coordinates[0], sa.coordinates[1] - sb.coordinates[1])
        self.graph.add_edge(a, b, float(int(dist)))  # simplificar a entero

    def _handle_h_press(self):
        """Gestiona la lógica de la tecla H:
        - Si no hay selección: no hace nada.
        - Si la estrella seleccionada NO es hipergigante: la convierte en hipergigante.
        - Si YA es hipergigante: inicia el modo de enlace externo.
        """
        if not self.selection_history:
            return
        sid = self.selection_history[-1]
        s = self.graph.get_star(sid)
        if not s:
            return
        if not s.hypergiant:
            s.hypergiant = True
        else:
            # Iniciar modo de enlace externo si aún no está activo
            if not self.link_mode:
                self.link_mode = True
                self.link_source_id = sid
                self.link_step = "select_constellation"
                self.link_target_constellation_idx = None

    def _change_radius(self, delta: float):
        if not self.selection_history:
            return
        s = self.graph.get_star(self.selection_history[-1])
        if not s:
            return
        s.radius = max(0.1, min(3.0, round(s.radius + delta, 2)))

    def _change_time_to_eat(self, delta: int):
        if not self.selection_history:
            return
        s = self.graph.get_star(self.selection_history[-1])
        if not s:
            return
        s.time_to_eat = max(0, s.time_to_eat + delta)

    def _change_energy(self, delta: int):
        if not self.selection_history:
            return
        s = self.graph.get_star(self.selection_history[-1])
        if not s:
            return
        s.energy = max(0, s.energy + delta)

    def _next_free_id(self) -> int:
        nid = self.next_id
        while nid in self.used_ids:
            nid += 1
        self.next_id = nid + 1
        return nid

    def _load_constellation(self, idx: int):
        """Cargar una constelación existente para editar."""
        if idx < 0 or idx >= len(self.existing_graphs):
            return
        
        source_graph = self.existing_graphs[idx]
        # Crear una copia del grafo para editar
        self.graph = Graph(source_graph.name, source_graph.color)
        
        # Copiar todas las estrellas
        for s in source_graph.get_all_stars():
            new_star = Star(
                s.id, s.label, 
                s.coordinates[0], s.coordinates[1],
                s.radius, s.time_to_eat, s.energy, s.hypergiant
            )
            self.graph.add_star(new_star)
        
        # Copiar conexiones internas
        for s in source_graph.get_all_stars():
            for neighbor_id, dist in s.connections.items():
                if neighbor_id in self.graph.vertices:
                    # Solo agregar una vez (add_edge lo hace bidireccional)
                    if s.id < neighbor_id:
                        self.graph.add_edge(s.id, neighbor_id, dist)
        
        # Copiar enlaces externos
        self.graph.external_links = list(source_graph.external_links)
        
        # Marcar que estamos editando esta constelación
        self.editing_constellation_idx = idx
        self.selection_history.clear()
        
        # Recalcular escala con las estrellas cargadas
        self._compute_scale()
    
    def _compute_scale(self):
        """Calcula la escala y offsets para transformar coordenadas del mundo a pantalla."""
        stars = self.graph.get_all_stars()
        if not stars or not self.board_rect:
            # Sin estrellas, usar escala por defecto centrada
            self.scale = 1.0
            self.offset_x = self.board_rect.x + self.board_rect.width / 2 if self.board_rect else 0
            self.offset_y = self.board_rect.y + self.board_rect.height / 2 if self.board_rect else 0
            self.scaled_positions.clear()
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
        self.scale = min((bw - 2 * margin) / range_x, (bh - 2 * margin) / range_y)
        remaining_w = bw - (range_x * self.scale)
        remaining_h = bh - (range_y * self.scale)
        self.offset_x = self.board_rect.x + remaining_w / 2 - min_x * self.scale
        self.offset_y = self.board_rect.y + remaining_h / 2 - min_y * self.scale
        
        # Actualizar posiciones escaladas
        self.scaled_positions.clear()
        for s in stars:
            sx = int(self.offset_x + s.coordinates[0] * self.scale)
            sy = int(self.offset_y + s.coordinates[1] * self.scale)
            self.scaled_positions[s.id] = (sx, sy)
    
    def _world_to_screen(self, world_x: float, world_y: float) -> Tuple[int, int]:
        """Convierte coordenadas del mundo (JSON) a coordenadas de pantalla."""
        sx = int(self.offset_x + world_x * self.scale)
        sy = int(self.offset_y + world_y * self.scale)
        return sx, sy
    
    def _screen_to_world(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """Convierte coordenadas de pantalla a coordenadas del mundo (JSON)."""
        if self.scale == 0:
            self.scale = 1.0
        world_x = (screen_x - self.offset_x) / self.scale
        world_y = (screen_y - self.offset_y) / self.scale
        return world_x, world_y
    
    def _handle_link_click(self, pos: Tuple[int, int]):
        """Maneja clicks durante el modo de enlace externo de hipergigante."""
        if self.link_step == "select_constellation":
            # Verificar si se hizo click en alguna constelación
            if hasattr(self, '_temp_link_constellation_rects'):
                for graph_idx, rect in self._temp_link_constellation_rects:
                    if rect.collidepoint(pos):
                        self.link_target_constellation_idx = graph_idx
                        self.link_step = "select_star"
                        return
        elif self.link_step == "select_star":
            # Verificar si se hizo click en alguna estrella hipergigante
            if hasattr(self, '_temp_link_star_rects'):
                for star_id, rect in self._temp_link_star_rects:
                    if rect.collidepoint(pos):
                        # Validar que ambos extremos sean hipergigantes
                        source_star = self.graph.get_star(self.link_source_id)
                        target_graph = self.existing_graphs[self.link_target_constellation_idx]
                        target_star = target_graph.get_star(star_id)
                        if source_star and target_star and source_star.hypergiant and target_star.hypergiant:
                            self._create_external_link(self.link_source_id, star_id)
                        # Salir del modo de enlace
                        self.link_mode = False
                        self.link_source_id = None
                        self.link_target_constellation_idx = None
                        self.link_step = "select_constellation"
                        return
    
    def _create_external_link(self, source_id: int, target_id: int):
        """Crea un enlace externo entre una hipergigante y una estrella de otra constelación."""
        source_star = self.graph.get_star(source_id)
        if not source_star:
            return
        
        # Buscar la estrella destino en las constelaciones existentes
        target_star = None
        for g in self.existing_graphs:
            target_star = g.get_star(target_id)
            if target_star:
                break
        
        if not target_star:
            return
        
        # Calcular distancia (arbitraria para enlaces externos, puede ser grande)
        dist = 500.0  # Distancia por defecto para enlaces externos
        
        # Agregar la conexión
        source_star.add_connection(target_id, dist)
        
        # Agregar a la lista de enlaces externos del grafo
        self.graph.add_external_link(source_id, target_id, dist)

    # -------------- Guardado --------------
    def _save_to_json(self, path: str):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"constellations": []}

        out_const = {
            "name": self.graph.name,
            "color": list(self.graph.color) if isinstance(self.graph.color, tuple) else self.graph.color,
            "stars": []
        }
        
        # Construir lista de todas las estrellas con sus conexiones
        for s in self.graph.get_all_stars():
            # Enlaces internos (dentro de esta constelación)
            linked = []
            for nid, dist in s.connections.items():
                linked.append({"starId": int(nid), "distance": float(dist)})
            
            out_const["stars"].append({
                "id": int(s.id),
                "label": s.label,
                "linkedTo": linked,
                "radius": float(s.radius),
                "timeToEat": int(s.time_to_eat),
                "amountOfEnergy": int(s.energy),
                "coordinates": {"x": int(s.coordinates[0]), "y": int(s.coordinates[1])},
                "hypergiant": bool(s.hypergiant)
            })

        # insertar manteniendo otras claves (como "burro")
        lst = data.get("constellations")
        if not isinstance(lst, list):
            data["constellations"] = lst = []
        
        # Si estamos editando, actualizar la existente; si no, agregar nueva
        was_editing = False
        if self.editing_constellation_idx is not None and 0 <= self.editing_constellation_idx < len(lst):
            lst[self.editing_constellation_idx] = out_const
            was_editing = True
        else:
            lst.append(out_const)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Mostrar mensaje de éxito
        if was_editing:
            self.save_message = f"✓ Constelación '{self.graph.name}' actualizada correctamente"
        else:
            self.save_message = f"✓ Constelación '{self.graph.name}' guardada correctamente"
        self.save_message_timer = self.save_message_duration
        
        # Reiniciar la vista después de guardar
        self.graph = Graph("Nueva Constelación", color=(255, 255, 255))
        self.selection_history.clear()
        self.editing_constellation_idx = None
        self.link_mode = False
        self.link_source_id = None
        self.link_target_constellation_idx = None
        self.link_step = "select_constellation"
        
        # Resetear sistema de coordenadas
        self._compute_scale()

    # -------------- Render --------------
    def render(self, surface):
        surface.fill((15, 20, 35))
        if self.board_rect:
            # Fondo espacial
            self._ensure_starfield()
            if self._starfield_surf:
                surface.blit(self._starfield_surf, self.board_rect.topleft)
            else:
                pygame.draw.rect(surface, (0,0,0), self.board_rect)
            pygame.draw.rect(surface, (80, 100, 140), self.board_rect, width=3, border_radius=12)

        # título con indicador de color actual
        if self.font:
            title = self.font.render(f"Editor - {self.graph.name}", True, (240, 240, 250))
            surface.blit(title, (self.board_rect.x + 20, self.board_rect.y + 20))
            
            # Mostrar cuadrito con el color actual de la constelación
            color_preview_rect = pygame.Rect(self.board_rect.x + 20, self.board_rect.y + 45, 30, 30)
            pygame.draw.rect(surface, self.graph.color, color_preview_rect, border_radius=4)
            pygame.draw.rect(surface, (150, 150, 150), color_preview_rect, width=2, border_radius=4)
            color_label = self.font.render("(presiona C para cambiar)", True, (180, 180, 190))
            surface.blit(color_label, (color_preview_rect.right + 10, color_preview_rect.y + 5))

        # edges
        drawn = set()
        for s in self.graph.get_all_stars():
            sx, sy = self._world_to_screen(s.coordinates[0], s.coordinates[1])
            for nid, dist in s.connections.items():
                key = tuple(sorted((s.id, nid)))
                if key in drawn:
                    continue
                drawn.add(key)
                nb = self.graph.get_star(nid)
                if not nb:
                    continue
                nx, ny = self._world_to_screen(nb.coordinates[0], nb.coordinates[1])
                pygame.draw.line(surface, (140, 140, 170), (sx, sy), (nx, ny), 2)

        # stars
        for s in self.graph.get_all_stars():
            sx, sy = self._world_to_screen(s.coordinates[0], s.coordinates[1])
            radius_px = 8 if not s.hypergiant else 14
            color = (255, 60, 60) if s.hypergiant else (230, 230, 240)
            pygame.draw.circle(surface, color, (sx, sy), radius_px)

            # selección
            if s.id in self.selection_history:
                pygame.draw.circle(surface, (255, 255, 255), (sx, sy), radius_px + 5, width=2)
            elif self.hover_id == s.id:
                pygame.draw.circle(surface, (120, 160, 220), (sx, sy), radius_px + 4, width=1)

            if self.font:
                info = f"{s.label} r={s.radius} t={s.time_to_eat} e={s.energy}"
                lbl = self.font.render(info, True, (220, 230, 240))
                surface.blit(lbl, (sx + radius_px + 4, sy - radius_px))

        # Selector de color modal
        if self.color_selector_visible:
            self._render_color_selector(surface)
        
        # Selector de constelaciones modal
        if self.constellation_selector_visible:
            self._render_constellation_selector(surface)
        
        # Selector de enlace externo para hipergigantes
        if self.link_mode:
            self._render_link_selector(surface)
        
        # Mensaje de guardado
        if self.save_message and self.save_message_timer > 0:
            self._render_save_message(surface)
        
        # Campo de entrada de nombre
        if self.editing_name:
            self._render_name_input(surface)

        # ayuda
        if self.font:
            help_lines = [
                "TAB: menú principal | F1: constelaciones | E: limpiar | L: cargar | N+Click: nueva estrella | C: color",
                "K: conectar 2 seleccionadas | H: hipergigante | J: enlace externo",
                "+/- radio | T/G tiempo | U/J energía | R: renombrar | S: guardar",
            ]
            base_y = self.board_rect.bottom + 10 if self.board_rect else 10
            x = 20
            for i, t in enumerate(help_lines):
                surf = self.font.render(t, True, (210, 210, 220))
                surface.blit(surf, (x, base_y + i * 22))

    # ---------- Starfield helpers ----------
    def _ensure_starfield(self):
        if not self.board_rect:
            return
        size = (self.board_rect.width, self.board_rect.height)
        if self._starfield_surf is None or self._starfield_size != size:
            self._starfield_surf = self._generate_starfield(size)
            self._starfield_size = size

    def _generate_starfield(self, size: tuple[int, int]) -> pygame.Surface:
        w, h = size
        surf = pygame.Surface((w, h))
        surf.fill((0, 0, 0))
        n_stars = max(150, min(1000, int(w * h * 0.0005)))
        rng = random.Random(84)  # determinístico
        for _ in range(n_stars):
            x = rng.randrange(0, w)
            y = rng.randrange(0, h)
            brightness = rng.randint(160, 255)
            color = (brightness, brightness, brightness)
            if rng.random() < 0.1:
                pygame.draw.rect(surf, color, pygame.Rect(x, y, 2, 2))
            else:
                surf.set_at((x, y), color)
        # Nebulosa tenue opcional
        if rng.random() < 0.5:
            for _ in range(3):
                cx = rng.randrange(0, w)
                cy = rng.randrange(0, h)
                radius = rng.randint(80, 160)
                color = (rng.randint(30, 70), rng.randint(30, 70), rng.randint(90, 140))
                for r in range(radius, 0, -4):
                    alpha = int(25 * (r / radius))
                    layer = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                    pygame.draw.circle(layer, (*color, alpha), (r, r), r)
                    surf.blit(layer, (cx - r, cy - r), special_flags=pygame.BLEND_ADD)
        return surf

    def _render_color_selector(self, surface):
        """Renderiza un panel modal con la paleta de colores."""
        # Fondo semitransparente
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Panel central
        panel_w, panel_h = 500, 300
        panel_x = (surface.get_width() - panel_w) // 2
        panel_y = (surface.get_height() - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, (40, 50, 70), panel_rect, border_radius=12)
        pygame.draw.rect(surface, (120, 140, 180), panel_rect, width=3, border_radius=12)
        
        # Título del panel
        if self.font:
            title = self.font.render("Selecciona un color para la constelación", True, (240, 240, 250))
            surface.blit(title, (panel_x + 20, panel_y + 20))
        
        # Dibujar cuadrados de colores
        self.color_rects.clear()
        cols = 4
        rows = (len(self.color_palette) + cols - 1) // cols
        swatch_size = 50
        spacing = 20
        start_x = panel_x + (panel_w - (cols * swatch_size + (cols - 1) * spacing)) // 2
        start_y = panel_y + 70
        
        for i, color in enumerate(self.color_palette):
            row = i // cols
            col = i % cols
            x = start_x + col * (swatch_size + spacing)
            y = start_y + row * (swatch_size + spacing)
            rect = pygame.Rect(x, y, swatch_size, swatch_size)
            self.color_rects.append(rect)
            
            # Dibujar cuadrado de color
            pygame.draw.rect(surface, color, rect, border_radius=8)
            
            # Borde destacado si está en hover o seleccionado
            border_color = (255, 255, 255)
            border_width = 2
            if self.hover_color_idx == i:
                border_color = (255, 255, 100)
                border_width = 4
            elif color == self.graph.color:
                border_color = (100, 255, 100)
                border_width = 3
            
            pygame.draw.rect(surface, border_color, rect, width=border_width, border_radius=8)
        
        # Instrucción
        if self.font:
            instruction = self.font.render("Click para seleccionar | C o ESC para cerrar", True, (200, 200, 210))
            surface.blit(instruction, (panel_x + 20, panel_rect.bottom - 40))
    
    def _render_constellation_selector(self, surface):
        """Renderiza un panel modal para seleccionar constelación existente para editar."""
        # Fondo semitransparente
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Panel central
        panel_w, panel_h = 600, 500
        panel_x = (surface.get_width() - panel_w) // 2
        panel_y = (surface.get_height() - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, (40, 50, 70), panel_rect, border_radius=12)
        pygame.draw.rect(surface, (120, 140, 180), panel_rect, width=3, border_radius=12)
        
        # Título
        if self.font:
            title = self.font.render("Selecciona una constelación para editar", True, (240, 240, 250))
            surface.blit(title, (panel_x + 20, panel_y + 20))
        
        # Lista de constelaciones
        self.constellation_rects.clear()
        start_y = panel_y + 70
        item_height = 50
        padding = 10
        
        for i, graph in enumerate(self.existing_graphs):
            if start_y + (i * (item_height + padding)) > panel_rect.bottom - 80:
                break  # No mostrar más si no cabe
            
            y = start_y + i * (item_height + padding)
            rect = pygame.Rect(panel_x + 20, y, panel_w - 40, item_height)
            self.constellation_rects.append(rect)
            
            # Fondo del item
            bg_color = (60, 70, 90) if self.hover_constellation_idx != i else (80, 100, 130)
            pygame.draw.rect(surface, bg_color, rect, border_radius=8)
            
            # Borde
            border_color = (100, 120, 150)
            if self.hover_constellation_idx == i:
                border_color = (255, 255, 100)
            pygame.draw.rect(surface, border_color, rect, width=2, border_radius=8)
            
            # Color preview
            color_preview = pygame.Rect(rect.x + 10, rect.y + 10, 30, 30)
            pygame.draw.rect(surface, graph.color, color_preview, border_radius=4)
            pygame.draw.rect(surface, (150, 150, 150), color_preview, width=1, border_radius=4)
            
            # Texto
            if self.font:
                name_surf = self.font.render(graph.name, True, (240, 240, 250))
                surface.blit(name_surf, (color_preview.right + 15, rect.y + 5))
                
                info = f"{len(graph.get_all_stars())} estrellas"
                info_surf = self.font.render(info, True, (180, 180, 190))
                surface.blit(info_surf, (color_preview.right + 15, rect.y + 28))
        
        # Instrucción
        if self.font:
            instruction = self.font.render("Click para editar | ESC para cerrar", True, (200, 200, 210))
            surface.blit(instruction, (panel_x + 20, panel_rect.bottom - 40))
    
    def _render_link_selector(self, surface):
        """Renderiza el selector de enlace externo para hipergigantes."""
        # Fondo semitransparente
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        source_star = self.graph.get_star(self.link_source_id) if self.link_source_id else None
        if not source_star:
            return
        
        # Panel
        panel_w, panel_h = 600, 450
        panel_x = (surface.get_width() - panel_w) // 2
        panel_y = (surface.get_height() - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, (40, 50, 70), panel_rect, border_radius=12)
        pygame.draw.rect(surface, (255, 100, 100), panel_rect, width=3, border_radius=12)
        
        if not self.font:
            return
        
        # Título
        title = self.font.render(f"Enlace externo desde: {source_star.label}", True, (255, 240, 240))
        surface.blit(title, (panel_x + 20, panel_y + 20))
        
        # Paso 1: Seleccionar constelación destino
        if self.link_step == "select_constellation":
            subtitle = self.font.render("Paso 1: Selecciona la constelación destino", True, (220, 220, 230))
            surface.blit(subtitle, (panel_x + 20, panel_y + 55))
            
            # Listar constelaciones (excluyendo la actual en edición)
            start_y = panel_y + 95
            item_height = 45
            padding = 8
            constellation_rects = []
            
            for i, graph in enumerate(self.existing_graphs):
                # No permitir enlace a la misma constelación
                if self.editing_constellation_idx == i:
                    continue
                
                idx = len(constellation_rects)
                y = start_y + idx * (item_height + padding)
                if y + item_height > panel_rect.bottom - 60:
                    break
                
                rect = pygame.Rect(panel_x + 30, y, panel_w - 60, item_height)
                constellation_rects.append((i, rect))
                
                # Detectar hover
                mouse = pygame.mouse.get_pos()
                is_hover = rect.collidepoint(mouse)
                
                bg_color = (60, 70, 90) if not is_hover else (80, 100, 130)
                pygame.draw.rect(surface, bg_color, rect, border_radius=6)
                
                border_color = (100, 120, 150) if not is_hover else (255, 255, 100)
                pygame.draw.rect(surface, border_color, rect, width=2, border_radius=6)
                
                # Color preview
                color_prev = pygame.Rect(rect.x + 8, rect.y + 7, 28, 28)
                pygame.draw.rect(surface, graph.color, color_prev, border_radius=4)
                pygame.draw.rect(surface, (150, 150, 150), color_prev, width=1, border_radius=4)
                
                name_surf = self.font.render(graph.name, True, (240, 240, 250))
                surface.blit(name_surf, (color_prev.right + 10, rect.y + 12))
                
                # Click handler
                if is_hover and pygame.mouse.get_pressed()[0]:
                    # Detectado click (aunque esto se maneja mejor en handle_event)
                    pass
            
            # Guardar rects temporales para detección de click
            self._temp_link_constellation_rects = constellation_rects
        
        # Paso 2: Seleccionar estrella destino
        elif self.link_step == "select_star" and self.link_target_constellation_idx is not None:
            target_graph = self.existing_graphs[self.link_target_constellation_idx]
            subtitle = self.font.render(f"Paso 2: Selecciona la estrella destino en {target_graph.name}", True, (220, 220, 230))
            surface.blit(subtitle, (panel_x + 20, panel_y + 55))
            # Listar solo estrellas hipergigantes
            start_y = panel_y + 95
            item_height = 40
            padding = 6
            star_rects = []
            for star in target_graph.get_all_stars():
                if not star.hypergiant:
                    continue
                idx = len(star_rects)
                y = start_y + idx * (item_height + padding)
                if y + item_height > panel_rect.bottom - 60:
                    break
                rect = pygame.Rect(panel_x + 30, y, panel_w - 60, item_height)
                star_rects.append((star.id, rect))
                mouse = pygame.mouse.get_pos()
                is_hover = rect.collidepoint(mouse)
                bg_color = (60, 70, 90) if not is_hover else (80, 100, 130)
                pygame.draw.rect(surface, bg_color, rect, border_radius=6)
                border_color = (255, 100, 100) if is_hover else (100, 120, 150)
                pygame.draw.rect(surface, border_color, rect, width=2, border_radius=6)
                label_text = f"{star.label} (ID: {star.id}) [HIPERGIGANTE]"
                label_surf = self.font.render(label_text, True, (240, 240, 250))
                surface.blit(label_surf, (rect.x + 12, rect.y + 10))
            self._temp_link_star_rects = star_rects
            # Instrucción
            instruction = self.font.render("Click para seleccionar | ESC para cancelar", True, (200, 200, 210))
            surface.blit(instruction, (panel_x + 20, panel_rect.bottom - 35))

    def _render_save_message(self, surface):
        """Renderiza el mensaje de guardado exitoso."""
        if not self.font:
            return
        
        # Calcular alpha basado en el tiempo restante (fadeout suave al final)
        alpha = 255
        if self.save_message_timer < 0.5:
            alpha = int(255 * (self.save_message_timer / 0.5))
        
        # Panel semi-transparente en la parte superior central
        panel_w = 600
        panel_h = 80
        panel_x = (surface.get_width() - panel_w) // 2
        panel_y = 50
        
        # Crear superficie con alpha
        message_surface = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        
        # Fondo del panel
        bg_color = (40, 120, 60, min(220, alpha))
        pygame.draw.rect(message_surface, bg_color, (0, 0, panel_w, panel_h), border_radius=12)
        
        # Borde
        border_color = (80, 200, 100, alpha)
        pygame.draw.rect(message_surface, border_color, (0, 0, panel_w, panel_h), width=3, border_radius=12)
        
        # Texto del mensaje
        text_color = (255, 255, 255, alpha) if alpha == 255 else (255, 255, 255)
        msg_surf = self.font.render(self.save_message, True, text_color)
        text_x = (panel_w - msg_surf.get_width()) // 2
        text_y = (panel_h - msg_surf.get_height()) // 2
        
        # Si alpha < 255, aplicar alpha a la superficie de texto
        if alpha < 255:
            msg_surf.set_alpha(alpha)
        
        message_surface.blit(msg_surf, (text_x, text_y))
        
        # Blit a la pantalla principal
        surface.blit(message_surface, (panel_x, panel_y))
    
    def _render_name_input(self, surface):
        """Renderiza un campo de entrada de texto para editar el nombre."""
        # Fondo semitransparente
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Panel central
        panel_w, panel_h = 500, 150
        panel_x = (surface.get_width() - panel_w) // 2
        panel_y = (surface.get_height() - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(surface, (40, 50, 70), panel_rect, border_radius=12)
        pygame.draw.rect(surface, (120, 140, 180), panel_rect, width=3, border_radius=12)
        
        if self.font:
            # Título
            title = self.font.render("Editar nombre de constelación", True, (240, 240, 250))
            title_x = panel_x + (panel_w - title.get_width()) // 2
            surface.blit(title, (title_x, panel_y + 20))
            
            # Campo de texto
            input_w = 400
            input_h = 40
            input_x = panel_x + (panel_w - input_w) // 2
            input_y = panel_y + 60
            input_rect = pygame.Rect(input_x, input_y, input_w, input_h)
            pygame.draw.rect(surface, (60, 70, 90), input_rect, border_radius=6)
            pygame.draw.rect(surface, (100, 120, 150), input_rect, width=2, border_radius=6)
            
            # Texto ingresado
            text_surf = self.font.render(self.name_input, True, (255, 255, 255))
            text_x = input_x + 10
            text_y = input_y + (input_h - text_surf.get_height()) // 2
            surface.blit(text_surf, (text_x, text_y))
            
            # Cursor parpadeante
            if self.name_cursor_visible:
                cursor_x = text_x + text_surf.get_width() + 2
                cursor_y1 = input_y + 8
                cursor_y2 = input_y + input_h - 8
                pygame.draw.line(surface, (255, 255, 255), (cursor_x, cursor_y1), (cursor_x, cursor_y2), 2)
            
            # Instrucciones
            hint = self.font.render("Enter: confirmar | Esc: cancelar", True, (180, 180, 190))
            hint_x = panel_x + (panel_w - hint.get_width()) // 2
            surface.blit(hint, (hint_x, panel_y + panel_h - 35))
