from models.star import Star

class Graph:
    def __init__(self, name, color=(255, 255, 255)):
        self.name = name
        self.color = color  # color RGB asignado desde el JSON
        self.vertices = {}
        # Enlaces a estrellas fuera de este grafo (entre constelaciones)
        # Lista de tuplas: (from_id, to_id, distance)
        self.external_links = []

    def add_star(self, star: Star):
        self.vertices[star.id] = star

    def add_edge(self, from_id, to_id, distance):
        if from_id in self.vertices and to_id in self.vertices:
            self.vertices[from_id].add_connection(to_id, distance)
            self.vertices[to_id].add_connection(from_id, distance)

    def get_star(self, id):
        return self.vertices.get(id)

    def get_all_stars(self):
        return list(self.vertices.values())

    def __str__(self):
        return f"Constelación {self.name} con {len(self.vertices)} estrellas (color={self.color})"

    # Gestión de enlaces externos (entre constelaciones)
    def add_external_link(self, from_id: int, to_id: int, distance: float):
        self.external_links.append((from_id, to_id, distance))

