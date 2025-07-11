import os
import json
import csv

def safe_get(d, keys, default=""):
    for key in keys:
        if isinstance(d, dict) and key in d:
            d = d[key]
        else:
            return default
    return d

def extract_genres(game_taxonomy):
    genres = set()
    subgenres = set()
    for taxonomy in game_taxonomy:
        if taxonomy.get("name", "") == "Genre":
            for dp in taxonomy.get("datapoints", []):
                if dp.get("name"):
                    genres.add(dp.get("name"))
                for sub_dp in dp.get("sub_datapoints", []):
                    if sub_dp.get("name"):
                        genres.add(sub_dp.get("name"))
    genre = ", ".join(sorted(g for g in genres if g))
    return genre

def extract_mechanics(game_taxonomy):
    mechanics = set()
    for taxonomy in game_taxonomy:
        name = taxonomy.get("name", "").lower()
        # We want "gameplay elements" and "descriptive genre"
        if name in ("gameplay elements"):
            for dp in taxonomy.get("datapoints", []):
                if dp.get("name"):
                    mechanics.add(dp.get("name"))
                for sub_dp in dp.get("sub_datapoints", []):
                    if sub_dp.get("name"):
                        mechanics.add(sub_dp.get("name"))
    # Return only up to 2 mechanics as comma separated string
    # mechanics_list = s
    return ", ".join(sorted(mechanics))

def extract_game_vibes(taxonomy_list):

    game_vibes_list = []

    for tax in taxonomy_list:
        if tax.get('name') == "Game Vibes":
            for dp in tax.get('datapoints', []):
                vibe_name = dp.get('name', 'Unknown Vibe')
                value_tags = dp.get('value_tags', [])
                tag_names = [tag.get('name') for tag in value_tags if tag.get('name')]

                if tag_names:
                    vibe_str = f"{vibe_name}({', '.join(tag_names)})"
                else:
                    vibe_str = vibe_name

                game_vibes_list.append(vibe_str)

    return ", ".join(game_vibes_list)

def extract_visual_style(taxonomy_list):
    styles = set()
    for category in taxonomy_list:
        name = category.get("name", "").lower()
        if "graphical style" in name or "art style" in name or "visual style" in name:
            for dp in category.get("datapoints", []):
                if dp.get("name"):
                    styles.add(dp.get("name"))
    return ", ".join(sorted(styles))

def extract_age_rating(taxonomy_list):
    for category in taxonomy_list:
        if category.get("name", "").lower() == "main demographic":
            for dp in category.get("datapoints", []):
                if dp.get("name", "").lower() == "age group":
                    for sub_dp in dp.get("sub_datapoints", []):
                        age = sub_dp.get("name", "")
                        if age:
                            return ''.join(filter(str.isdigit, age))  # 👈 only digits
    return ""
def extract_region(game):
    return game.get("region", "")

def is_story_game(taxonomy):
    story_keywords = {
        "Advancement": ["Story Driven"],
        "Linearity": ["Story - Linear", "Story - Non-linear"],
        "Story / Campaign Length": [],
        "Narrative / Story Tropes": []
    }

    for section in taxonomy:
        section_name = section.get("name", "")
        for dp in section.get("datapoints", []):
            # Check if this taxonomy section is story-related
            if section_name in story_keywords:
                # Case 1: The name matches our known story tags
                if dp.get("name") in story_keywords[section_name]:
                    return True

                # Case 2: It's a category like "Story / Campaign Length" or "Narrative / Story Tropes"
                if section_name in ["Story / Campaign Length", "Narrative / Story Tropes"]:
                    return True

    return False

def extract_official_website(game):
    # Iterate through the links to find the official website
    for link in game.get("links", []):
        if link.get("type") == "Official Website":
            return link.get("url", "")
    return ""
    
def flatten_game_for_csv(game):
    taxonomy = game.get("game_taxonomy", [])
    return {
        "game_id": str(game.get("game_id", "")),
        "title": game.get("title", ""),
        "description": safe_get(game, ["description", "text"]),
        "genre": extract_genres(taxonomy),
        "game_vibes": extract_game_vibes(taxonomy),
        # "mechanics": '',
        "mechanics": extract_mechanics(taxonomy),
        "distribution": game.get("distribution", ""),
        "platform": game.get("platform", ""),
        "visual_style": extract_visual_style(taxonomy),
        "age_rating": extract_age_rating(taxonomy),
        "region": extract_region(game),  
        "story_pref": is_story_game(taxonomy),
        "link": extract_official_website(game),
    }

def jsons_to_csv(folder, csv_path):
    games = []

    for root, dirs, files in os.walk(folder):
        print(f"Looking in folder: {root}, found files: {files}")
        for file in files:
            if file.endswith(".json"):
                print(f"  Attempting to load file: {file}")
                path = os.path.join(root, file)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            games.extend(data)
                        else:
                            games.append(data)
                    print(f"  Loaded {file}")
                except Exception as e:
                    print(f"  Error loading {file}: {e}")

    print(f"✅ Total games loaded (raw, including duplicates): {len(games)}")

    flat_games = [flatten_game_for_csv(g) for g in games]

    if not flat_games:
        print("⚠️ No games to write.")
        return

    keys = flat_games[0].keys()
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        for game in flat_games:
            writer.writerow(game)

    print(f"📁 CSV saved to: {csv_path}")


if __name__ == "__main__":
    json_folder = "./game_s_data/extracted"
    output_csv = "./games_data/games_custom.csv"
    jsons_to_csv(folder=json_folder, csv_path=output_csv)