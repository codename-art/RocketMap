# from s2 import *
import s2sphere

from pgoapi.protos.pogoprotos.map.weather.gameplay_weather_pb2 import GameplayWeather




def parse_weather(db_weathers):

    # region_rect = S2LatLngRect(
    #     S2LatLng.FromDegrees(59.810996, 30.142188),
    #     S2LatLng.FromDegrees(60.072253, 30.554089)
    # )
    # coverer = S2RegionCoverer()
    # coverer.set_min_level(10)
    # coverer.set_max_level(10)
    # coverer.set_max_cells(10)
    # covering = coverer.GetCovering(region_rect)
    geoms = []

    r = s2sphere.RegionCoverer()
    r.min_level = 10
    r.max_level = 10
    r.max_cells = 20
    p1 = s2sphere.LatLng.from_degrees(59.810996, 30.142188)
    p2 = s2sphere.LatLng.from_degrees(60.072253, 30.554089)
    covering = r.get_covering(s2sphere.LatLngRect.from_point_pair(p1, p2))
    for cellid in covering:
        cell_to_render = {}
        rect_bound = s2sphere.Cell(cellid)
        center = s2sphere.LatLng.from_point(rect_bound.get_center())
        cell_to_render['center'] = { 'lat': center.lat().degrees, 'lng': center.lng().degrees }
        cell_to_render['vertices'] = []
        for i in range(0, 4):
            vertex = s2sphere.LatLng.from_point(rect_bound.get_vertex(i))
            cell_to_render['vertices'].append({ 'lat': vertex.lat().degrees, 'lng': vertex.lng().degrees})

        del rect_bound

        for weather in db_weathers:
            if str(cellid.id()) == weather['s2_cell_id']:
                cell_to_render['weather'] = weather['gameplay_weather']
                break
        geoms.append(cell_to_render)






    del r, p1, p2
    return geoms
