import json
from models.graph import Graph
from models.star import Star

def cargar_grafo_desde_json(ruta_json):
    with open(ruta_json, "r", encoding="utf-8") as file:
        data = json.load(file)

    constelaciones = []
    for constelacion in data["constellations"]:
        g = Graph(constelacion["name"])
        for s in constelacion["stars"]:
            star = Star(
                s["id"],
                s["label"],
                s["coordinates"]["x"],
                s["coordinates"]["y"],
                s["radius"],
                s["timeToEat"],
                s["amountOfEnergy"],
                s["hypergiant"]
            )
            g.add_star(star)

        for s in constelacion["stars"]:
            for link in s["linkedTo"]:
                g.add_edge(s["id"], link["starId"], link["distance"])
        constelaciones.append(g)
    return constelaciones
