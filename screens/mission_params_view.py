import pygame
import json
from typing import Optional, Dict, Any, List, Tuple
from screens.view import View

class MissionParamsView(View):
    """Vista para editar parámetros de misión que afectan la simulación.

    Edita el bloque `missionParams` del JSON:
    - maxEatFraction (0..1)
    - kgPerSecondEat (kg/s)
    - energyPerKgPct: {Excelente, Regular, Malo} (porcentaje 0..100)
    - researchEnergyPerSecond (energía/s)
    - travelSpeedUnits (unidades de distancia / s)
    - routeObjective (min_cost | max_stars_min_cost)
    """
    def __init__(self, mission_params: Dict[str, Any], json_path: str = "data/constellations.json"):
        super().__init__()
        self.json_path = json_path
        # Copias
        import copy
        self.original: Dict[str, Any] = copy.deepcopy(mission_params or {})
        self.edit: Dict[str, Any] = copy.deepcopy(mission_params or {})
        self.font: Optional[pygame.font.Font] = None
        self.title_font: Optional[pygame.font.Font] = None
        # Orden de campos (clave, etiqueta, tipo)
        self.fields: List[Tuple[str, str, str]] = [
            ("maxEatFraction", "Fracción máxima para comer", "float"),
            ("kgPerSecondEat", "Kg/seg al comer", "float"),
            ("researchEnergyPerSecond", "Energía/s investigación", "float"),
            ("travelSpeedUnits", "Velocidad de viaje (unid/s)", "float"),
            ("routeObjective", "Objetivo de ruta (min_cost | max_stars_min_cost)", "str"),
        ]
        # Campos compuestos de energyPerKgPct
        self.sub_fields_pct: List[Tuple[str, str]] = [
            ("Excelente", "Pct energía/kg (Excelente)"),
            ("Regular", "Pct energía/kg (Regular)"),
            ("Malo", "Pct energía/kg (Malo)"),
        ]
        self.selected_index = 0
        self.input_active = False
        self.buffer = ""
        self.message: Optional[str] = None
        self.message_timer = 0.0

    def on_enter(self):
        if pygame.font:
            try:
                self.font = pygame.font.SysFont("Consolas", 18)
                self.title_font = pygame.font.SysFont("Consolas", 28)
            except Exception:
                self.font = None
                self.title_font = None

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                self.requested_view = "main_menu"
                return
            if event.key == pygame.K_F3:
                self.requested_view = "constellation"
                return
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected_index = max(0, self.selected_index - 1)
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                # +3 por los subcampos energyPerKgPct
                max_idx = len(self.fields) + len(self.sub_fields_pct) - 1
                self.selected_index = min(max_idx, self.selected_index + 1)
            elif event.key == pygame.K_RETURN:
                if not self.input_active:
                    self.input_active = True
                    self.buffer = self._get_selected_value_as_str()
                else:
                    self._commit_input()
            elif event.key == pygame.K_ESCAPE:
                if self.input_active:
                    self.input_active = False
                    self.buffer = ""
                else:
                    # descartar cambios y volver
                    self.edit = json.loads(json.dumps(self.original))
                    self.requested_view = "main_menu"
            elif event.key == pygame.K_s and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self._save_to_json()
            elif self.input_active:
                if event.key == pygame.K_BACKSPACE:
                    self.buffer = self.buffer[:-1]
                elif event.key == pygame.K_DELETE:
                    self.buffer = ""
                else:
                    if event.unicode:
                        self.buffer += event.unicode

    def update(self, dt: float):
        if self.message_timer > 0:
            self.message_timer -= dt
            if self.message_timer <= 0:
                self.message = None

    def render(self, surface: pygame.Surface):
        surface.fill((20, 26, 40))
        if not self.font:
            return
        w, h = surface.get_size()
        if self.title_font:
            title = self.title_font.render("Parámetros de misión", True, (240, 240, 250))
            surface.blit(title, (w//2 - title.get_width()//2, 40))
        # Lista de campos
        y = 120
        all_items: List[Tuple[str, str, str]] = list(self.fields)
        # expandir subcampos de energyPerKgPct
        for subk, label in self.sub_fields_pct:
            all_items.append((f"energyPerKgPct.{subk}", label, "int"))
        for idx, (key, label, _kind) in enumerate(all_items):
            is_sel = (idx == self.selected_index)
            color = (255, 230, 90) if is_sel else (210, 210, 220)
            value = self._get_value_by_key(key)
            val_str = str(value)
            text = f"{label}: {self.buffer if (self.input_active and is_sel) else val_str}"
            ts = self.font.render(text, True, color)
            surface.blit(ts, (60, y))
            y += 30
        # Ayuda
        help_txt = "↑/↓ seleccionar | ENTER editar | Ctrl+S guardar | TAB menú | F3 simulación"
        hs = self.font.render(help_txt, True, (190, 190, 200))
        surface.blit(hs, (60, h - 40))
        if self.message:
            ms = self.font.render(self.message, True, (200, 255, 200))
            surface.blit(ms, (w//2 - ms.get_width()//2, h - 70))

    # --- helpers ---
    def _get_selected_value_as_str(self) -> str:
        items: List[Tuple[str, str, str]] = list(self.fields) + [(f"energyPerKgPct.{k}", lbl, "int") for k, lbl in self.sub_fields_pct]
        key, _, _ = items[self.selected_index]
        return str(self._get_value_by_key(key))

    def _get_value_by_key(self, key: str):
        if key.startswith("energyPerKgPct."):
            subk = key.split(".", 1)[1]
            return (self.edit.get("energyPerKgPct") or {}).get(subk, 0)
        return self.edit.get(key)

    def _set_value_by_key(self, key: str, value):
        if key.startswith("energyPerKgPct."):
            subk = key.split(".", 1)[1]
            mp = self.edit.setdefault("energyPerKgPct", {})
            mp[subk] = value
        else:
            self.edit[key] = value

    def _commit_input(self):
        items: List[Tuple[str, str, str]] = list(self.fields) + [(f"energyPerKgPct.{k}", lbl, "int") for k, lbl in self.sub_fields_pct]
        key, _, kind = items[self.selected_index]
        raw = self.buffer.strip()
        try:
            if kind == "float":
                self._set_value_by_key(key, float(raw))
            elif kind == "int":
                self._set_value_by_key(key, int(float(raw)))
            else:
                self._set_value_by_key(key, raw)
            self.message = "✓ Valor actualizado"
        except Exception:
            self.message = "Valor inválido"
        self.message_timer = 2.0
        self.input_active = False
        self.buffer = ""

    def _save_to_json(self):
        # Abrir y actualizar bloque missionParams
        try:
            with open(self.json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {"constellations": [], "burro": {}}
        data["missionParams"] = self.edit
        with open(self.json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Aplicar como nuevos originales
        import copy
        self.original = copy.deepcopy(self.edit)
        self.message = "✓ Parámetros guardados"
        self.message_timer = 2.5
