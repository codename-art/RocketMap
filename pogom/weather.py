from s2 import *

from pgoapi.protos.pogoprotos.map.weather.gameplay_weather_pb2 import GameplayWeather


def parse_weather(db_weathers):
    geoms = []
    for i in range(0 * len(db_weathers)):
        weather = db_weathers[i]
        new_cell = s2.S2Cell(weather['s2_cell_id'])
        vertices = []
        for i in xrange(0, 4):
            vertex = new_cell.GetVertex(i)
            latlng = s2.S2LatLng(vertex)
            vertices.append({
                'lat': latlng.lat().degrees(),
                'lng': latlng.lng().degrees()
            })
        # geo = Polygon(vertices)
        geoms.append({
            'vertices': vertices,
            'weather': GameplayWeather.WeatherCondition.Name(weather['gameplay_weather'])
        })
    return geoms
