import json
from models.graph import Graph
from models.star import Star

def cargar_grafo_desde_json(ruta_json):
    with open(ruta_json, "r", encoding="utf-8") as file:
        data = json.load(file)
    constelaciones = []
    global_star_map = {}
    graph_by_star_id = {}

    # Primera pasada: construir grafos y estrellas
    for constelacion in data.get("constellations", []):
        color = constelacion.get("color", [255, 255, 255])
        if isinstance(color, str) and color.startswith('#') and len(color) == 7:
            r = int(color[1:3], 16); g_c = int(color[3:5], 16); b = int(color[5:7], 16)
            color = (r, g_c, b)
        elif isinstance(color, list) and len(color) == 3:
            color = tuple(color)
        else:
            color = (255, 255, 255)

        g = Graph(constelacion.get("name", "Constelación"), color)
        for s in constelacion.get("stars", []):
            try:
                star = Star(
                    s["id"],
                    s.get("label", f"Star-{s['id']}"),
                    s["coordinates"]["x"],
                    s["coordinates"]["y"],
                    s.get("radius", 0.5),
                    s.get("timeToEat", 0),
                    s.get("amountOfEnergy", 0),
                    s.get("hypergiant", False)
                )
            except KeyError:
                # Si falta algún campo crítico, omitir la estrella
                continue
            g.add_star(star)
            global_star_map[star.id] = star
            graph_by_star_id[star.id] = g
        constelaciones.append(g)

    # Segunda pasada: enlaces internos y externos
    for constelacion in data.get("constellations", []):
        for s in constelacion.get("stars", []):
            from_id = s.get("id")
            if from_id not in global_star_map:
                continue
            for link in s.get("linkedTo", []):
                to_id = link.get("starId")
                dist = link.get("distance", 0)
                if to_id not in global_star_map:
                    continue
                from_graph = graph_by_star_id.get(from_id)
                to_graph = graph_by_star_id.get(to_id)
                if not from_graph or not to_graph:
                    continue
                if from_graph is to_graph:
                    from_graph.add_edge(from_id, to_id, dist)
                else:
                    from_graph.add_external_link(from_id, to_id, dist)
                    to_graph.add_external_link(to_id, from_id, dist)
                    global_star_map[from_id].add_connection(to_id, dist)
                    global_star_map[to_id].add_connection(from_id, dist)

    return constelaciones
