class Star:
    def __init__(self, id, label, x, y, radius, time_to_eat, energy, hypergiant):
        self.id = id
        self.label = label
        self.coordinates = (x, y)
        self.radius = radius
        self.time_to_eat = time_to_eat
        self.energy = energy
        self.hypergiant = hypergiant
        self.connections = {}

    def add_connection(self, star_id, distance):
        self.connections[star_id] = distance

    def __str__(self):
        return f"⭐ {self.label} ({self.id}) - Hypergiant: {self.hypergiant}"
