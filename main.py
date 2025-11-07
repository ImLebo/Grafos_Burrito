import tkinter as tk
from config.loader import cargar_grafo_desde_json

# Colores por constelación
COLORES = ["yellow", "cyan", "magenta", "orange", "lime", "white"]

def dibujar_constelacion(canvas, graph, color):
    for star in graph.get_all_stars():
        x, y = star.coordinates
        # Dibujar conexiones
        for neighbor_id in star.connections:
            neighbor = graph.get_star(neighbor_id)
            if neighbor:
                nx, ny = neighbor.coordinates
                canvas.create_line(x, y, nx, ny, fill=color)
        # Dibujar estrella
        r = 4 if not star.hypergiant else 6
        canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")
        canvas.create_text(x + 10, y, text=star.label, fill=color, font=("Arial", 8))

def main():
    root = tk.Tk()
    root.title("Visualización de Constelaciones - Grafos TKINTER")
    root.configure(bg="black")

    canvas = tk.Canvas(root, width=400, height=400, bg="black")
    canvas.pack(padx=10, pady=10)

    constelaciones = cargar_grafo_desde_json("data/constellations.json")

    for i, g in enumerate(constelaciones):
        color = COLORES[i % len(COLORES)]
        dibujar_constelacion(canvas, g, color)

    root.mainloop()

if __name__ == "__main__":
    main()
