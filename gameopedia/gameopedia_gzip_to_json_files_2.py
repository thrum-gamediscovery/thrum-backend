import gzip
import zipfile
import json
import os
import io

def decompress_gzip_to_zip(gzip_path="games_data/package.gz", zip_path="games_data/package.zip"):
    print(f"Decompressing gzip file {gzip_path} to zip file {zip_path} ...")
    with gzip.open(gzip_path, "rb") as f_in:
        with open(zip_path, "wb") as f_out:
            f_out.write(f_in.read())
    print("Decompression complete.")

def extract_json_from_zip(zip_path="games_data/package.zip", extract_dir="games_data/extracted"):
    print(f"Extracting ZIP archive {zip_path} ...")
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print(f"Extraction complete. Files extracted to {extract_dir}")

    # Load all JSON files inside extract_dir
    games = []
    for root, dirs, files in os.walk(extract_dir):
        for file in files:
            if file.endswith(".json"):
                json_path = os.path.join(root, file)
                print(f"Loading JSON file: {json_path}")
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        games.extend(data)
                    else:
                        games.append(data)
    print(f"Loaded total {len(games)} game entries.")
    return games

if __name__ == "__main__":
    gzip_path = "games_data/package.gz"
    zip_path = "games_data/package.zip"
    extract_dir = "games_data/extracted"

    decompress_gzip_to_zip(gzip_path, zip_path)
    games = extract_json_from_zip(zip_path, extract_dir)
