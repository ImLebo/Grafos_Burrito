import pygame
import json
from typing import Optional, Dict
from screens.view import View
from models.burro import Burro
from utils.animated_sprite import AnimatedSprite

class BurroEditorView(View):
    """Vista para editar los datos del burro (Galaxito).

    Características:
    - Muestra animación de navegacion grande al centro-arriba.
    - Lista de atributos editables a la izquierda.
    - Panel de edición/detalle a la derecha.
    - Modales para confirmar guardado o cancelar cambios.
    - Guarda en constellations.json el bloque 'burro'.
    """
    def __init__(self, burro_data: dict, json_path: str = "data/constellations.json"):
        super().__init__()
        self.json_path = json_path
        self.original_data = json.loads(json.dumps(burro_data))  # copia profunda
        self.edit_data = json.loads(json.dumps(burro_data))
        self.font: Optional[pygame.font.Font] = None
        self.title_font: Optional[pygame.font.Font] = None
        self.large_anim: Optional[AnimatedSprite] = None
        self.large_scale = (160, 160)
        self.fields_order = [
            ("nombre", "Nombre"),
            ("energiaInicial", "Energía Inicial"),
            ("estadoSalud", "Estado de Salud"),
            ("pastoDisponibleKg", "Pasto Disponible (Kg)"),
            ("edadActual", "Edad Actual"),
            ("tiempoDeVidaAniosLuz", "Tiempo de Vida (Años Luz)"),
            ("nivelExperiencia", "Nivel de Experiencia"),
            ("hambre", "Hambre"),
            ("nivelInvestigacion", "Nivel Investigación"),
            ("consumoEnergiaInvestigacion", "Consumo Energía Investigación"),
            ("velocidadDesplazamiento", "Velocidad Desplazamiento"),
        ]
        self.selected_field_index: int = 0
        self.input_active: bool = False
        self.input_buffer: str = ""
        self.message: Optional[str] = None
        self.message_timer: float = 0.0
        self.message_duration: float = 3.0
        self.modal_visible: bool = False
        self.modal_type: Optional[str] = None  # 'save' | 'discard'
        self.scroll_offset: int = 0
        self.max_visible_fields: int = 10

    def on_enter(self):
        if pygame.font:
            try:
                self.font = pygame.font.SysFont("Consolas", 18)
                self.title_font = pygame.font.SysFont("Consolas", 28)
            except Exception:
                self.font = None
                self.title_font = None
        # Cargar animación grande
        nav_path = self.edit_data.get("animaciones", {}).get("navegacion") or self.edit_data.get("animaciones", {}).get("principal")
        if nav_path:
            try:
                self.large_anim = AnimatedSprite(nav_path, fps=10, scale=self.large_scale)
            except Exception:
                self.large_anim = None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if self.modal_visible:
                if event.key == pygame.K_ESCAPE:
                    self.modal_visible = False
                    self.modal_type = None
                elif event.key == pygame.K_RETURN:
                    if self.modal_type == 'save':
                        self._commit_save()
                    elif self.modal_type == 'discard':
                        self._discard_changes()
                    self.modal_visible = False
                    self.modal_type = None
                return
            # Navegación general
            if event.key == pygame.K_TAB:
                self.requested_view = "main_menu"
                return
            if event.key == pygame.K_F3:  # volver a simulación
                self.requested_view = "constellation"
                return
            if event.key == pygame.K_DOWN:
                self.selected_field_index = min(len(self.fields_order)-1, self.selected_field_index+1)
                self._adjust_scroll()
            elif event.key == pygame.K_UP:
                self.selected_field_index = max(0, self.selected_field_index-1)
                self._adjust_scroll()
            elif event.key == pygame.K_RETURN:
                if not self.input_active:
                    # activar edición del campo
                    field_key, _ = self.fields_order[self.selected_field_index]
                    current_val = self.edit_data.get(field_key, "")
                    self.input_buffer = str(current_val)
                    self.input_active = True
                else:
                    # confirmar edición
                    self._apply_input_buffer()
            elif event.key == pygame.K_ESCAPE:
                if self.input_active:
                    self.input_active = False
                    self.input_buffer = ""
                else:
                    # abrir modal descartar
                    self.modal_visible = True
                    self.modal_type = 'discard'
            elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                # Ctrl+S para guardar
                self.modal_visible = True
                self.modal_type = 'save'
            elif self.input_active:
                # Entrada de texto
                if event.key == pygame.K_BACKSPACE:
                    self.input_buffer = self.input_buffer[:-1]
                elif event.key == pygame.K_DELETE:
                    self.input_buffer = ""
                elif event.key == pygame.K_SPACE:
                    self.input_buffer += ' '
                else:
                    if event.unicode and len(event.unicode) == 1:
                        self.input_buffer += event.unicode

    def update(self, dt: float):
        if self.large_anim:
            self.large_anim.update(dt)
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = None

    def render(self, surface: pygame.Surface):
        surface.fill((25, 30, 45))
        w, h = surface.get_size()
        # Animación grande arriba centro
        if self.large_anim and self.large_anim.has_frames():
            frame = self.large_anim.get_current_frame()
            rect = frame.get_rect(midtop=(w//2, 20))
            surface.blit(frame, rect.topleft)
        if self.title_font:
            title = self.title_font.render("Editor del Burro", True, (240, 240, 250))
            surface.blit(title, (w//2 - title.get_width()//2, 200))
        # Panel izquierda (lista de campos)
        list_x = 40
        list_y = 250
        list_w = 380
        list_h = h - list_y - 40
        pygame.draw.rect(surface, (40, 50, 70), (list_x, list_y, list_w, list_h), border_radius=12)
        pygame.draw.rect(surface, (90, 110, 150), (list_x, list_y, list_w, list_h), width=2, border_radius=12)
        if self.font:
            visible_fields = self.fields_order[self.scroll_offset:self.scroll_offset+self.max_visible_fields]
            for i, (fkey, flabel) in enumerate(visible_fields):
                idx = self.scroll_offset + i
                y = list_y + 15 + i*32
                color = (255, 230, 90) if idx == self.selected_field_index else (210, 210, 220)
                txt = self.font.render(f"{flabel}", True, color)
                surface.blit(txt, (list_x + 15, y))
        # Panel derecha (detalle / edición)
        detail_x = list_x + list_w + 30
        detail_y = list_y
        detail_w = w - detail_x - 40
        detail_h = list_h
        pygame.draw.rect(surface, (40, 50, 70), (detail_x, detail_y, detail_w, detail_h), border_radius=12)
        pygame.draw.rect(surface, (90, 110, 150), (detail_x, detail_y, detail_w, detail_h), width=2, border_radius=12)
        if self.font:
            fkey, flabel = self.fields_order[self.selected_field_index]
            current_val = self.edit_data.get(fkey, "")
            label_surf = self.font.render(f"{flabel}:", True, (230, 230, 240))
            surface.blit(label_surf, (detail_x + 20, detail_y + 20))
            val_color = (255, 255, 255) if not self.input_active else (130, 230, 130)
            val_text = self.input_buffer if self.input_active else str(current_val)
            value_surf = self.font.render(val_text, True, val_color)
            surface.blit(value_surf, (detail_x + 20, detail_y + 55))
            hint = "ENTER para editar / ESC para cancelar / Ctrl+S guardar"
            hint_surf = self.font.render(hint, True, (180, 180, 190))
            surface.blit(hint_surf, (detail_x + 20, detail_y + 90))
        # Mensaje temporal
        if self.message and self.font:
            msg_surf = self.font.render(self.message, True, (200, 255, 200))
            surface.blit(msg_surf, (w//2 - msg_surf.get_width()//2, h - 40))
        # Modal
        if self.modal_visible:
            self._render_modal(surface)
        # Ayuda inferior
        if self.font:
            help_txt = "TAB: menú | F3: simulación | ↑↓ seleccionar campo | ENTER editar | Ctrl+S guardar | ESC cancelar"
            hs = self.font.render(help_txt, True, (210, 210, 220))
            # Bajar la ayuda para que no se superponga con los paneles (cards)
            surface.blit(hs, (40, h - 30))

    def _adjust_scroll(self):
        if self.selected_field_index < self.scroll_offset:
            self.scroll_offset = self.selected_field_index
        elif self.selected_field_index >= self.scroll_offset + self.max_visible_fields:
            self.scroll_offset = self.selected_field_index - self.max_visible_fields + 1

    def _apply_input_buffer(self):
        fkey, _ = self.fields_order[self.selected_field_index]
        raw = self.input_buffer
        # Intentar convertir numéricos donde corresponde
        if fkey in ["energiaInicial","pastoDisponibleKg","edadActual","tiempoDeVidaAniosLuz","hambre","nivelInvestigacion","consumoEnergiaInvestigacion"]:
            try:
                self.edit_data[fkey] = int(raw)
            except ValueError:
                # intentar float -> int
                try:
                    self.edit_data[fkey] = int(float(raw))
                except ValueError:
                    pass
        elif fkey == "velocidadDesplazamiento":
            try:
                self.edit_data[fkey] = float(raw)
            except ValueError:
                pass
        else:
            self.edit_data[fkey] = raw
        self.input_active = False
        self.input_buffer = ""

    def _render_modal(self, surface: pygame.Surface):
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0,0,0,180))
        surface.blit(overlay,(0,0))
        w,h = surface.get_size()
        mw,mh = 500,220
        mx,my = (w-mw)//2,(h-mh)//2
        panel = pygame.Rect(mx,my,mw,mh)
        pygame.draw.rect(surface,(50,60,80),panel,border_radius=12)
        pygame.draw.rect(surface,(120,140,180),panel,width=3,border_radius=12)
        if not self.font:
            return
        title = "Guardar cambios" if self.modal_type=='save' else "Descartar cambios" if self.modal_type=='discard' else "Modal"
        ts = self.font.render(title,True,(240,240,250))
        surface.blit(ts,(mx+20,my+20))
        msg = "ENTER confirma / ESC cancela"
        ms = self.font.render(msg,True,(200,200,210))
        surface.blit(ms,(mx+20,my+60))
        # Mostrar diff simple
        diff_y = my+100
        shown = 0
        for fkey,_ in self.fields_order:
            if self.original_data.get(fkey) != self.edit_data.get(fkey):
                line = f"{fkey}: {self.original_data.get(fkey)} -> {self.edit_data.get(fkey)}"
                ls = self.font.render(line,True,(255,220,140))
                surface.blit(ls,(mx+20,diff_y))
                diff_y += 24
                shown += 1
                if shown >= 3:
                    break
        if shown == 0:
            none_msg = self.font.render("Sin cambios",True,(180,180,190))
            surface.blit(none_msg,(mx+20,diff_y))

    def _commit_save(self):
        # Cargar JSON
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"constellations": [], "burro": {}}
        data['burro'] = self.edit_data
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        self.original_data = json.loads(json.dumps(self.edit_data))
        self.message = "✓ Cambios guardados"
        self.message_timer = self.message_duration

    def _discard_changes(self):
        self.edit_data = json.loads(json.dumps(self.original_data))
        self.message = "Cambios descartados"
        self.message_timer = self.message_duration

    def on_exit(self):
        # Si salimos sin guardar, los cambios no persisten (edit_data se descarta en próxima entrada si se desea)
        pass
