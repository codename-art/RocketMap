/*global
 map, jsts
 */

const weatherImages = {
    1: 'weather_sunny.png',
    2: 'weather_rain.png',
    3: 'weather_partlycloudy_day.png',
    4: 'weather_cloudy.png',
    5: 'weather_windy.png',
    6: 'weather_snow.png',
    7: 'weather_fog.png',
    11: 'weather_clear_night.png',
    13: 'weather_partlycloudy_night.png',
    15: 'weather_moderate.png',
    16: 'weather_extreme.png'
}

const weatherNames = {
    1: 'Clear',
    2: 'Rain',
    3: 'Partly Cloudy',
    4: 'Cloudy',
    5: 'Windy',
    6: 'Snow',
    7: 'Fog'
}

const alertTexts = {
    1: 'Moderate',
    2: 'Extreme'
}


/**
 * Parses info about weather cell and draws icon
 * @param i index from $.each()
 * @param item weather cell data
 * @returns {boolean}
 */
function processWeather(i, item) { // eslint-disable-line no-unused-vars
    if (!Store.get('showWeatherCells') || item.gameplay_weather == null) {
        return false
    }

    var s2CellId = item.s2_cell_id
    var itemOld = mapData.weather[s2CellId]

    if (itemOld == null) { // add new marker to map and item to dict
        safeDelMarker(item)
        item.marker = setupWeatherMarker(item)
        mapData.weather[s2CellId] = item
    } else if (itemOld.gameplay_weather !== item.gameplay_weather ||
        itemOld.severity !== item.severity) { // if weather changed
        itemOld.marker.setMap(null)
        item.marker = setupWeatherMarker(item)
        mapData.weather[s2CellId] = item
    }
}


/**
 * Parses info about s2cell and draws polygon
 * @param i i index from $.each()
 * @param item s2cell data
 * @returns {boolean}
 */
function processS2Cell(i, item) { // eslint-disable-line no-unused-vars
    if (!Store.get('showS2Cells')) {
        return false
    }

    var s2CellId = item.s2_cell_id
    if (!(s2CellId in mapData.s2cells)) {
        safeDelMarker(item)
        item.marker = setupS2CellPolygon(item)
        mapData.s2cells[s2CellId] = item
    }
}


/**
 * Do main work with array of weather alerts
 * @param weatherAlerts
 */
function processWeatherAlerts(weatherAlerts) { // eslint-disable-line no-unused-vars
    deleteObsoleteWeatherAlerts(weatherAlerts)
    $.each(weatherAlerts, processWeatherAlert)
}


/**
 * Draws colored polygon for weather severity condition
 * @param i
 * @param item s2cell data
 * @returns {boolean}
 */
function processWeatherAlert(i, item) {
    if (!Store.get('showWeatherAlerts') || item.severity == null) {
        return false
    }

    var s2CellId = item.s2_cell_id
    var itemOld = mapData.weatherAlerts[s2CellId]
    if (itemOld == null) {
        safeDelMarker(item)
        item.marker = createCellAlert(item)
        mapData.weatherAlerts[s2CellId] = item
    } else if (itemOld.severity !== item.severity) {
        itemOld.marker.setMap(null)
        item.marker = createCellAlert(item)
        mapData.weatherAlerts[s2CellId] = item
    }
}


/**
 * If drawn cell not exist in new alert array, it should be removed
 * @param newAlerts
 */
function deleteObsoleteWeatherAlerts(newAlerts) {
    var toRemove = []
    $.each(mapData.weatherAlerts, function (i, item) {
        if (!(item['s2_cell_id'] in newAlerts)) {
            safeDelMarker(item)
            toRemove.push(i)
        }
    })
    $.each(toRemove, function (i, id) {
        delete mapData.weatherAlerts[id]
    })
}


/**
 * safe setMap(null)
 * @param item
 */
function safeDelMarker(item) {
    if (item.marker) {
        item.marker.setMap(null)
    }
}


/**
 * Creates path for weather icon based on gameplay_weather and world_time
 * @param item
 * @param dark dark or light version of image, default is dark
 * @returns {*}
 */
function getWeatherImageUrl(item, dark = true) {
    var weatherImageUrl = 'static/images/weather/'
    var image = null
    if (item.world_time === 2) { // night
        if (![1, 3].includes(item.gameplay_weather)) { // common icons for day and night
            image = weatherImages[item.gameplay_weather]
        } else { // clear and partly cloudy
            image = weatherImages[item.gameplay_weather + 10]
        }
    } else {
        image = weatherImages[item.gameplay_weather]
    }
    if (image == null) {
        image = 'weather_undefined.png'
    }
    if (!dark) {
        image = image.replace('weather_', 'weather_light_')
    }
    return weatherImageUrl + image
}

/**
 * Generates path for alert icon based on severity
 * @param item
 * @returns {*}
 */
function getalertImageUrl(item) {
    var alertimageUrl
    if (item.severity === 1) {
        alertimageUrl = 'static/images/weather/' + weatherImages[15]
    } else if (item.severity === 2) {
        alertimageUrl = 'static/images/weather/' + weatherImages[16]
    }
    return alertimageUrl
}

/**
 * Creates icon for current zoom level
 * @param weatherImageUrl
 * @returns icon with image and scaled size
 */
function createMarkerIcon(weatherImageUrl) {
    var size = 64 * map.getZoom() / 18
    console.log(size)
    return {
        url: weatherImageUrl,
        origin: new google.maps.Point(0, 0),
        anchor: new google.maps.Point(16, 16),
        size: new google.maps.Size(size, size),
        scaledSize: new google.maps.Size(size, size)
    }
}

/**
 * Creates marker with image
 * @param item
 * @returns {google.maps.Marker}
 */
function setupWeatherMarker(item) {
    var weatherImageUrl = getWeatherImageUrl(item)
    var marker = new google.maps.Marker({
        position: item.center,
        icon: createMarkerIcon(weatherImageUrl)
    })

    map.addListener('zoom_changed', function () {
        marker.setIcon(createMarkerIcon(marker.icon.url))
        marker.setMap(map)
    })
    return marker
}


/**
 * Creates Polygon for s2cell
 * @param item
 * @returns {google.maps.Polygon}
 */
function setupS2CellPolygon(item) {
    return new google.maps.Polygon({
        paths: item.vertices,
        strokeColor: '#000000',
        strokeOpacity: 0.8,
        strokeWeight: 1,
        fillOpacity: 0,
        fillColor: '#00ff00'
    })
}


/**
 * Adds fillColor for s2cell polygon
 * @param item
 * @returns {google.maps.Polygon}
 */
function createCellAlert(item) {
    var cell = setupS2CellPolygon(item)
    cell.strokeOpacity = 0
    if (item.severity === 0) {
        cell.fillOpacity = 0.0
    } else if (item.severity === 1) {
        cell.fillOpacity = 0.2
        cell.fillColor = '#ffff00'
    } else if (item.severity === 2) {
        cell.fillOpacity = 0.2
        cell.fillColor = '#ff0000'
    }
    return cell
}


/**
 * Calculates square bound for s2cell
 * @param s2Cell
 * @returns {google.maps.LatLngBounds}
 */
function getS2CellBounds(s2Cell) { // eslint-disable-line no-unused-vars
    var bounds = new google.maps.LatLngBounds()
    // iterate over the vertices
    $.each(s2Cell.vertices, function (i, latLng) {
        // extend the bounds
        bounds.extend(latLng)
    })
    return bounds
}


// Weather top icon.
var $weatherInfo = document.querySelector('#weatherInfo')

/**
 * Update weather icon on top bar if there is single cell on the screen
 */
function updateMainCellWeather() { // eslint-disable-line no-unused-vars
    if ($weatherInfo == null) {
        return // updating the top bar is not required if it does not exist
    }
    // remove old weather icon
    while ($weatherInfo.firstChild) {
        $weatherInfo.removeChild($weatherInfo.firstChild)
    }
    var s2Cell = getMainS2Cell()
    if (s2Cell != null) {
        // Weather Text
        var weatherText = document.createElement('span')
        weatherText.textContent = weatherNames[s2Cell.gameplay_weather] || 'unknown'
        weatherText.setAttribute('style', 'font-size: 10px; position: relative; left: -2px;')
        // Weather Icon
        var weatherIcon = document.createElement('img')
        weatherIcon.setAttribute('src', getWeatherImageUrl(s2Cell, false))
        weatherIcon.setAttribute('style', 'height: 25px; vertical-align: middle; margin: 2px;')
        // Wind Text
        var windText = document.createElement('span')
        windText.textContent = degreesToCardinal(s2Cell.wind_direction)
        windText.setAttribute('style', 'font-size: 10px; position: relative; left: -2px;')
        // Wind Icon
        var windIcon = document.createElement('img')
        windIcon.setAttribute('src', 'static/images/weather/wind_streaks.png')
        windIcon.setAttribute('style', 'height: 25px; vertical-align: middle; margin: 4px;')

        if (s2Cell.severity >= 1) {
            // Alert Text
            var alertText = document.createElement('span')
            alertText.textContent = alertTexts[s2Cell.severity]
            alertText.setAttribute('style', 'font-size: 10px; position: relative; left: -2px;')
            // Alert Icon
            var alertIcon = document.createElement('img')
            alertIcon.setAttribute('src', getalertImageUrl(s2Cell))
            alertIcon.setAttribute('style', 'height: 25px; vertical-align: middle;')
            $weatherInfo.appendChild(alertIcon)
            $weatherInfo.appendChild(alertText)
        }
        // Make It Happen
        $weatherInfo.appendChild(weatherIcon)
        $weatherInfo.appendChild(weatherText)
        $weatherInfo.appendChild(windIcon)
        $weatherInfo.appendChild(windText)
    }
}


function degreesToCardinal(d) {
    var dirs = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
        'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
    var ix = Math.floor((d + 11.25) / 22.5 - 0.02)
    return dirs[ix % 16]
}

/**
 * Finds weather data for s2cell, that covers more than a half of the screen
 * @returns {*}
 */
function getMainS2Cell() {
    if (typeof window.orientation !== 'undefined' || isMobileDevice()) {
        if (map.getZoom() < 12) { // viewport my contain many cells
            return
        }
    } else {
        if (map.getZoom() < 13) { // viewport my contain many cells
            return
        }
    }

    var geometryFactory = new jsts.geom.GeometryFactory()

    var bounds = map.getBounds()
    var viewportPath = [
        {'lat': bounds.getNorthEast().lat(), 'lng': bounds.getNorthEast().lng()},
        {'lat': bounds.getNorthEast().lat(), 'lng': bounds.getSouthWest().lng()},
        {'lat': bounds.getSouthWest().lat(), 'lng': bounds.getSouthWest().lng()},
        {'lat': bounds.getSouthWest().lat(), 'lng': bounds.getNorthEast().lng()}
    ]
    var jstsViewport = createJstsPolygon(geometryFactory, viewportPath)
    var viewportArea = jstsViewport.getArea()
    var maxCoverageData = null
    $.each(mapData.weather, function (i, s2cell) {
        var jstsS2cell = createJstsPolygon(geometryFactory, s2cell.vertices)
        var area = jstsViewport.intersection(jstsS2cell).getArea()
        if (viewportArea < area * 2) {  // more then a half of the screen covered by cell
            maxCoverageData = s2cell
        }
    })
    return maxCoverageData
}


/**
 * Creates jsts polygon from coordinates array
 * @param geometryFactory
 * @param path
 * @returns {*}
 */
function createJstsPolygon(geometryFactory, path) {
    var coordinates = path.map(function name(coord) {
        return new jsts.geom.Coordinate(coord.lat, coord.lng)
    })
    if (coordinates[0].compareTo(coordinates[coordinates.length - 1]) !== 0) {
        coordinates.push(coordinates[0])
    }
    var shell = geometryFactory.createLinearRing(coordinates)
    return geometryFactory.createPolygon(shell)
}
