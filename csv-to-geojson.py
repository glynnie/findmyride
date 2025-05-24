import csv
import json
import sys
from collections import defaultdict

input_file = 'shapes.txt'
output_file = 'shapes.geojson'

shapes = defaultdict(list)
num_rows = 0
num_shapes = 0

print(f"Reading '{input_file}'...")

try:
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            num_rows += 1
            try:
                shape_id = row['shape_id']
                seq = int(row['shape_pt_sequence'])
                lon = float(row['shape_pt_lon'])
                lat = float(row['shape_pt_lat'])
                shapes[shape_id].append((seq, lon, lat))
            except Exception as e:
                print(f"Error parsing row {num_rows}: {e} -- {row}")
except FileNotFoundError:
    print(f"Error: File '{input_file}' not found.")
    sys.exit(1)
except Exception as e:
    print(f"Error reading '{input_file}': {e}")
    sys.exit(1)

print(f"Total rows processed: {num_rows}")
print(f"Unique shape_ids found: {len(shapes)}")
print("Converting to GeoJSON features...")

features = []
for shape_id, points in shapes.items():
    num_shapes += 1
    if len(points) < 2:
        print(f"Warning: shape_id '{shape_id}' has less than 2 points. Skipping.")
        continue
    points.sort()
    coords = [[lon, lat] for _, lon, lat in points]
    features.append({
        "type": "Feature",
        "properties": {"shape_id": shape_id},
        "geometry": {"type": "LineString", "coordinates": coords}
    })
    if num_shapes % 100 == 0:
        print(f"Processed {num_shapes} shapes...")

geojson = {"type": "FeatureCollection", "features": features}

try:
    with open(output_file, 'w', encoding='utf-8') as out:
        json.dump(geojson, out)
    print(f"GeoJSON successfully written to '{output_file}'.")
    print(f"Total shapes converted: {num_shapes}")
    print(f"Total features in GeoJSON: {len(features)}")
except Exception as e:
    print(f"Error writing GeoJSON: {e}")
    sys.exit(1)

print("Conversion complete!")
