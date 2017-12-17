/**
 * Parses info about weather cell and draws icon
 * @param i index from $.each()
 * @param item weather cell data
 * @returns {boolean}
 */
function processWeather(i, item) {
    if (!Store.get('showWeatherCells') || item.gameplay_weather == null) {
        return false
    }

    var s2_cell_id = item.s2_cell_id
    var itemOld = mapData.weather[s2_cell_id]

    if (itemOld == null) { // add new marker to map and item to dict
        safeDelMarker(item);
        item.marker = setupWeatherMarker(item)
        mapData.weather[s2_cell_id] = item
    } else if (itemOld.gameplay_weather != item.gameplay_weather) { // if weather changed
        itemOld.marker.setMap(null)
        item.marker = setupWeatherMarker(item)
        mapData.weather[s2_cell_id] = item
    }
}


/**
 * Parses info about s2cell and draws polygon
 * @param i i index from $.each()
 * @param item s2cell data
 * @returns {boolean}
 */
function processS2Cell(i, item) {
    if (!Store.get('showS2Cells')) {
        return false
    }

    var s2_cell_id = item.s2_cell_id
    if (!(s2_cell_id in mapData.s2cells)) {
        safeDelMarker(item);
        item.marker = setupS2CellPolygon(item)
        mapData.s2cells[s2_cell_id] = item
    }
}


/**
 * Do main work with array of weather alerts
 * @param weatherAlerts
 */
function processWeatherAlerts(weatherAlerts) {
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

    var s2_cell_id = item.s2_cell_id

    var itemOld = mapData.weatherAlerts[s2_cell_id]
    if (itemOld == null) {
        safeDelMarker(item)
        item.marker = createCellAlert(item)
        mapData.weatherAlerts[s2_cell_id] = item
    } else if (itemOld.severity != item.severity) {
        itemOld.marker.setMap(null)
        item.marker = createCellAlert(item)
        mapData.weatherAlerts[s2_cell_id] = item
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
            safeDelMarker(item);
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
 * Creates marker with image
 * @param item
 * @returns {google.maps.Marker}
 */
function setupWeatherMarker(item) {
    var image = {
        url: "/static/images/weather/" + weatherImages[item.gameplay_weather],
        origin: new google.maps.Point(0, 0),
        anchor: new google.maps.Point(32, 32)
    };
    return new google.maps.Marker({
        position: item.center,
        icon: image
    });
}


/**
 * Creates Polygon for s2cell
 * @param item
 * @returns {google.maps.Polygon}
 */
function setupS2CellPolygon(item) {
    return new google.maps.Polygon({
        paths: item.vertices,
        strokeColor: "#000000",
        strokeOpacity: 0.8,
        strokeWeight: 1,
        fillOpacity: 0,
        fillColor: '#00ff00'
    });
}


/**
 * Adds fillColor for s2cell polygon
 * @param item
 * @returns {google.maps.Polygon}
 */
function createCellAlert(item) {
    var cell = setupS2CellPolygon(item);
    cell.fillOpacity = 0.1
    cell.strokeOpacity = 0
    if (item.severity == 1) {
        cell.fillColor = '#ffff00'
    } else if (item.severity == 2) {
        cell.fillColor = '#ff0000'
        console.log(cell.fillColor)
    }
    return cell
}


/**
 * Calculates square bound for s2cell
 * @param s2Cell
 * @returns {google.maps.LatLngBounds}
 */
function getS2CellBounds(s2Cell) {
    var bounds = new google.maps.LatLngBounds()
    //iterate over the vertices
    $.each(s2Cell.vertices, function (i, latLng) {
        //extend the bounds
        bounds.extend(latLng);
    })
    return bounds
}
