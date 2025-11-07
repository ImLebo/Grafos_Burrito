from models.star import Star

class Graph:
    def __init__(self, name):
        self.name = name
        self.vertices = {}

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
        return f"Constelación {self.name} con {len(self.vertices)} estrellas"

