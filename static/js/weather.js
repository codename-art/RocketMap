initMap();
new google.maps.Polygon({
    paths: data.vertices,
    strokeColor: '#FF0000',
    strokeOpacity: 0.8,
    strokeWeight: 2,
    fillColor: '#FF0000',
    fillOpacity: 0.35
});
bermudaTriangle.setMap(map);
