from s2 import *

from pgoapi.protos.pogoprotos.map.weather.gameplay_weather_pb2 import GameplayWeather




def parse_weather(db_weathers):

    region_rect = S2LatLngRect(
        S2LatLng.FromDegrees(59.810996, 30.142188),
        S2LatLng.FromDegrees(60.072253, 30.554089)
    )
    coverer = S2RegionCoverer()
    coverer.set_min_level(10)
    coverer.set_max_level(10)
    coverer.set_max_cells(10)
    covering = coverer.GetCovering(region_rect)

    geoms = []
    for cellid in covering:
        new_cell = S2Cell(cellid)
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
            'vertices': vertices
            # 'weather': GameplayWeather.WeatherCondition.Name(weather['gameplay_weather'])
        })

    # for i in range(0, len(db_weathers)):
    #     weather = db_weathers[i]
    #     print weather['s2_cell_id']
    #
    #     new_cell = s2.FromS2CellId(weather['s2_cell_id'])
    #     vertices = []
    #     for i in xrange(0, 4):
    #         vertex = new_cell.GetVertex(i)
    #         latlng = s2.S2LatLng(vertex)
    #         vertices.append({
    #             'lat': latlng.lat().degrees(),
    #             'lng': latlng.lng().degrees()
    #         })
    #     # geo = Polygon(vertices)
    #     geoms.append({
    #         'vertices': vertices,
    #         'weather': GameplayWeather.WeatherCondition.Name(weather['gameplay_weather'])
    #     })
    return geoms
