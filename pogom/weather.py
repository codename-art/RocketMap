# from s2 import *
import s2sphere

from pogom.models import Weather


def get_weather_cells():
    return get_weather_cels(Weather.get_weathers())


def get_weather_alerts():
    return get_weather_cels(Weather.get_weather_alerts())


def get_weather_cels(db_weathers):
    for i in range(0, len(db_weathers)):
        cell_id = s2sphere.CellId(long(db_weathers[i]['s2_cell_id']))
        cell = s2sphere.Cell(cell_id)
        center = s2sphere.LatLng.from_point(cell.get_center())
        db_weathers[i]['center'] = {'lat': center.lat().degrees, 'lng': center.lng().degrees}
        db_weathers[i]['vertices'] = get_vertices_from_s2cell(cell)

    return db_weathers


def get_s2_coverage(swLat, swLng, neLat, neLng):
    geoms = []

    r = s2sphere.RegionCoverer()
    r.min_level = 10
    r.max_level = 10
    r.max_cells = 40
    p1 = s2sphere.LatLng.from_degrees(float(swLat), float(swLng))
    p2 = s2sphere.LatLng.from_degrees(float(neLat), float(neLng))
    covering = r.get_covering(s2sphere.LatLngRect.from_point_pair(p1, p2))
    for cell_id in covering:
        cell_to_render = {}
        rect_bound = s2sphere.Cell(cell_id)
        center = s2sphere.LatLng.from_point(rect_bound.get_center())
        cell_to_render['s2_cell_id'] = str(cell_id.id())
        cell_to_render['center'] = {'lat': center.lat().degrees, 'lng': center.lng().degrees}
        cell_to_render['vertices'] = get_vertices_from_s2cell(rect_bound)

        del rect_bound
        geoms.append(cell_to_render)

    return geoms

# convert s2cell vertices to google map api format
def get_vertices_from_s2cell(rect_bound):
    vertices = []
    for i in range(0, 4):
        vertex = s2sphere.LatLng.from_point(rect_bound.get_vertex(i))
        vertices.append({'lat': vertex.lat().degrees, 'lng': vertex.lng().degrees})
    return vertices
