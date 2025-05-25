import csv
import json
import os
from collections import defaultdict

# File paths
TRIPS_FILE = 'trips.txt'
SHAPES_FILE = 'shapes.txt'
ROUTES_FILE = 'routes.txt'
STOP_TIMES_FILE = 'stop_times.txt'
STOPS_FILE = 'stops.txt'
OUTPUT_FILE = 'bus_routes_with_stops.geojson'

def file_exists(filepath):
    if not os.path.isfile(filepath):
        print(f"ERROR: File not found: {filepath}")
        return False
    return True

def safe_float(val, fallback=None):
    try:
        return float(val)
    except Exception:
        return fallback

def safe_int(val, fallback=None):
    try:
        return int(val)
    except Exception:
        return fallback

def main():
    # Check files
    for f in [TRIPS_FILE, SHAPES_FILE, ROUTES_FILE, STOP_TIMES_FILE, STOPS_FILE]:
        if not file_exists(f):
            print("Aborting due to missing file.")
            return

    # 1. Load shapes: shape_id -> ordered list of (lat, lon)
    shapes = defaultdict(list)
    print(f"Loading shapes from {SHAPES_FILE} ...")
    with open(SHAPES_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            shape_id = row.get('shape_id')
            lat = safe_float(row.get('shape_pt_lat'))
            lon = safe_float(row.get('shape_pt_lon'))
            seq = safe_int(row.get('shape_pt_sequence'))
            if not shape_id or lat is None or lon is None or seq is None:
                print(f"  WARNING: Skipping malformed shape row: {row}")
                continue
            shapes[shape_id].append((seq, lat, lon))
            count += 1
        print(f"  Loaded {count} shape points for {len(shapes)} shapes.")
    for shape_id in shapes:
        shapes[shape_id] = [ (lat, lon) for _, lat, lon in sorted(shapes[shape_id]) ]

    # 2. Load trips: trip_id -> (route_id, shape_id)
    trip_to_route_shape = {}
    shape_to_route = defaultdict(set)
    print(f"Loading trips from {TRIPS_FILE} ...")
    with open(TRIPS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            trip_id = row.get('trip_id')
            route_id = row.get('route_id')
            shape_id = row.get('shape_id')
            if not trip_id or not route_id or not shape_id:
                print(f"  WARNING: Skipping malformed trip row: {row}")
                continue
            trip_to_route_shape[trip_id] = (route_id, shape_id)
            shape_to_route[shape_id].add(route_id)
            count += 1
        print(f"  Loaded {count} trips, found {len(shape_to_route)} unique shapes used in trips.")

    # 3. Load routes: route_id -> route_short_name, route_long_name
    routes = {}
    print(f"Loading routes from {ROUTES_FILE} ...")
    with open(ROUTES_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            route_id = row.get('route_id')
            if not route_id:
                print(f"  WARNING: Skipping malformed route row: {row}")
                continue
            routes[route_id] = {
                "route_short_name": row.get('route_short_name', ''),
                "route_long_name": row.get('route_long_name', ''),
                "route_type": row.get('route_type', '')
            }
            count += 1
        print(f"  Loaded {count} routes.")

    # 4. Load stops: stop_id -> stop info
    stops = {}
    print(f"Loading stops from {STOPS_FILE} ...")
    with open(STOPS_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            stop_id = row.get('stop_id')
            if not stop_id:
                print(f"  WARNING: Skipping malformed stop row: {row}")
                continue
            stops[stop_id] = {
                "stop_id": stop_id,
                "stop_code": row.get('stop_code', ''),
                "stop_name": row.get('stop_name', ''),
                "stop_lat": safe_float(row.get('stop_lat')),
                "stop_lon": safe_float(row.get('stop_lon')),
                "wheelchair_boarding": row.get('wheelchair_boarding', ''),
                "location_type": row.get('location_type', ''),
                "parent_station": row.get('parent_station', ''),
                "platform_code": row.get('platform_code', '')
            }
            count += 1
        print(f"  Loaded {count} stops.")

    # 5. Load stop_times: trip_id -> ordered list of stop_ids
    trip_stop_sequences = defaultdict(list)
    print(f"Loading stop times from {STOP_TIMES_FILE} ...")
    with open(STOP_TIMES_FILE, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        count = 0
        for row in reader:
            trip_id = row.get('trip_id')
            stop_id = row.get('stop_id')
            seq = safe_int(row.get('stop_sequence'))
            if not trip_id or not stop_id or seq is None:
                print(f"  WARNING: Skipping malformed stop_times row: {row}")
                continue
            trip_stop_sequences[trip_id].append((seq, stop_id))
            count += 1
        print(f"  Loaded {count} stop times for {len(trip_stop_sequences)} trips.")
    for trip_id in trip_stop_sequences:
        trip_stop_sequences[trip_id] = [stop_id for _, stop_id in sorted(trip_stop_sequences[trip_id])]

    # 6. Build GeoJSON features: one per unique (route_id, shape_id)
    print("Building GeoJSON features with stops ...")
    features = []
    missing_shapes = 0
    for shape_id, route_ids in shape_to_route.items():
        coords = shapes.get(shape_id)
        if not coords:
            print(f"  WARNING: No coordinates found for shape_id {shape_id}, skipping.")
            missing_shapes += 1
            continue
        for route_id in route_ids:
            route_info = routes.get(route_id, {})
            # Find all trip_ids for this (route_id, shape_id)
            trip_ids = [tid for tid, (rid, sid) in trip_to_route_shape.items() if rid == route_id and sid == shape_id]
            # Use the first trip's stop sequence as representative
            stops_sequence = []
            for trip_id in trip_ids:
                stops_in_trip = trip_stop_sequences.get(trip_id)
                if stops_in_trip:
                    stops_sequence = stops_in_trip
                    break
            # Build stop info list
            stop_features = []
            for stop_id in stops_sequence:
                stop_info = stops.get(stop_id)
                if stop_info:
                    stop_features.append(stop_info)
                else:
                    print(f"    WARNING: Stop_id {stop_id} not found in stops.txt")
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [ [lon, lat] for lat, lon in coords ]
                },
                "properties": {
                    "route_id": route_id,
                    "shape_id": shape_id,
                    **route_info,
                    "stops": stop_features
                }
            }
            features.append(feature)
    print(f"  Built {len(features)} features. {missing_shapes} shapes were missing coordinates.")

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    # 7. Write to file
    print(f"Writing GeoJSON to {OUTPUT_FILE} ...")
    try:
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)
        print(f"GeoJSON successfully written to {OUTPUT_FILE}")
    except Exception as e:
        print(f"ERROR: Failed to write GeoJSON: {e}")

if __name__ == "__main__":
    main()
