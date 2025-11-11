class Star:
    def __init__(self, id, label, x, y, radius, time_to_eat, energy, hypergiant, time_to_research=None):
        self.id = id
        self.label = label
        self.coordinates = (x, y)
        self.radius = radius
        # Tiempo máximo que puede dedicar en esta estrella a comer (X)
        self.time_to_eat = time_to_eat
        # Tiempo de investigación sugerido; si no viene, usar el mismo X
        self.time_to_research = time_to_research if time_to_research is not None else time_to_eat
        # Campo original del JSON (no usado directamente en esta versión)
        self.energy = energy
        self.hypergiant = hypergiant
        self.connections = {}

    def add_connection(self, star_id, distance):
        self.connections[star_id] = distance

    def __str__(self):
        return f"⭐ {self.label} ({self.id}) - Hypergiant: {self.hypergiant}"
