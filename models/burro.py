class Burro:
    def __init__(self, nombre, energia_inicial, estado_salud, pasto_disponible, edad_actual,
                 tiempo_vida, nivel_experiencia, hambre, nivel_investigacion,
                 consumo_energia_investigacion, velocidad, sonido_muerte):
        self.nombre = nombre
        self.energia_inicial = energia_inicial
        self.estado_salud = estado_salud
        self.pasto_disponible = pasto_disponible
        self.edad_actual = edad_actual
        self.tiempo_vida = tiempo_vida
        self.nivel_experiencia = nivel_experiencia
        self.hambre = hambre
        self.nivel_investigacion = nivel_investigacion
        self.consumo_energia_investigacion = consumo_energia_investigacion
        self.velocidad = velocidad
        self.sonido_muerte = sonido_muerte

    def __str__(self):
        return f"{self.nombre} ({self.estado_salud}) - Energía: {self.energia_inicial}%"
