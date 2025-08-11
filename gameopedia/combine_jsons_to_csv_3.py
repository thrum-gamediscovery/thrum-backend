import os
import json
import csv

def extract_game_fields(data):
    extracted = {}
    # Basic IDs & Info
    extracted["external_game_id"] = data.get("game_id")
    extracted["title"] = data.get("title")
    extracted["alternative_titles"] = data.get("alternative_titles", [])
    extracted["description"] = data.get("description", {}).get("text", "") if isinstance(data.get("description"), dict) else data.get("description", "")
    extracted["release_date"] = data.get("release_date")
    extracted["region"] = data.get("region")
    extracted["editions"] = data.get("edition")
    extracted["platforms"] = data.get("platform", "")
    extracted["distributions"] = data.get("distribution", [])

    # Taxonomy helpers
    taxonomy = data.get("game_taxonomy", [])
    def get_taxonomy(name):
        for t in taxonomy:
            if t.get("name") == name:
                return [dp["name"] for dp in t.get("datapoints", [])]
        return []
    
    def extract_gameplay_elements(game_taxonomy):
        gameplay_elements = []
        for taxonomy in game_taxonomy:
            name = taxonomy.get("name", "").lower()
            # Only want "gameplay elements"
            if name == "gameplay elements":
                for dp in taxonomy.get("datapoints", []):
                    if dp.get("name"):
                        element = dp.get("name")
                    for sub_dp in dp.get("sub_datapoints", []):
                        if sub_dp.get("name"):
                            sub = sub_dp.get("name")
                            gameplay_elements.append(f'{element}-{sub}')
        return gameplay_elements

    def extract_complexity(game_taxonomy):
        complexity_list = []

        for taxonomy in game_taxonomy:
            name = taxonomy.get("name", "").lower()
            
            # Check for the "Complexity" taxonomy
            if name == "complexity":
                for datapoint in taxonomy.get('datapoints', []):  # Loop through datapoints
                    for sub_datapoint in datapoint.get('sub_datapoints', []):  # Loop through sub-datapoints
                        c=sub_datapoint.get('name') # Add the name of the sub-datapoint
                        for item in sub_datapoint.get('sub_datapoints', []):
                            comp = item.get('name')
                            complexity_list.append(f"{c}-{comp}")

        return complexity_list
        
    def extract_visual_style(taxonomy_list):
        styles = []
        for category in taxonomy_list:
            name = category.get("name", "").lower()
            if "graphical style" in name or "art style" in name or "visual style" in name or "Physics Realism" in name:
                for dp in category.get("datapoints", []):
                    if dp.get("name"):
                        styles.append(dp.get("name"))
        return styles

    # Extracting all required taxonomy fields
    extracted["genre"] = get_taxonomy("Genre")
    extracted["subgenres"] = get_taxonomy("Sub-genre") + get_taxonomy("Movie-like genres")
    extracted["main_perspective"] = get_taxonomy("Main Perspective")
    extracted["themes"] = get_taxonomy("Theme")
    extracted["game_vibe"] = get_taxonomy("Game Vibes")
    extracted["keywords"] = get_taxonomy("Keywords")
    extracted["gameplay_elements"] = extract_gameplay_elements(taxonomy)
    extracted["advancement"] = get_taxonomy("Advancement")
    extracted["linearity"] = get_taxonomy("Linearity")
    extracted["replay_value"] = get_taxonomy("Replay Value")
    extracted["graphical_visual_style"] = extract_visual_style(taxonomy)
    extracted["complexity"] = extract_complexity(taxonomy)

    def parse_story_setting_realism(tag_list):
        realism_dict = {}
        if not isinstance(tag_list, list):
            return realism_dict

        for tag in tag_list:
            if tag.startswith("[") and "]" in tag:
                key = tag[1:tag.index("]")]
                value = tag[tag.index("]")+1:].strip()
                # Add to list of values for this key
                realism_dict.setdefault(key, []).append(value)
        return realism_dict
    
    extracted["story_setting_realism"] = parse_story_setting_realism(get_taxonomy("Story/Setting Realism"))
    def extract_age_rating(taxonomy_list):
        for category in taxonomy_list:
            if category.get("name", "").lower() == "main demographic":
                for dp in category.get("datapoints", []):
                    if dp.get("name", "").lower() == "age group":
                        for sub_dp in dp.get("sub_datapoints", []):
                            age = sub_dp.get("name", "")
                            if age:
                                return ''.join(filter(str.isdigit, age))
        return ""
    extracted["age_rating"] = extract_age_rating(taxonomy)

    def extract_official_website(game):
        # Iterate through the links to find the official website
        for link in game.get("links", []):
            if link.get("type") == "Official Website":
                return link.get("url", "")
        return ""

    # Media, links, etc.
    extracted["links"] = extract_official_website(data)
    extracted["features"] = data.get("features")
    extracted["key_features"] = data.get("key_features", {}).get("text", "") if isinstance(data.get("key_features"), dict) else data.get("key_features", "")
    extracted["sku"] = data.get("sku")

    # Story/narrative
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
                if section_name in story_keywords:
                    if dp.get("name") in story_keywords[section_name]:
                        return True
                    if section_name in ["Story / Campaign Length", "Narrative / Story Tropes"]:
                        return True
        return False
    extracted["has_story"] = is_story_game(taxonomy)

    def get_developer_names(developers):
        if not isinstance(developers, list):
            return []
        return [entry.get("name") for entry in developers if entry.get("type") == "Developer" and entry.get("name")]
    
    def get_publisher_names(publishers):
        if not isinstance(publishers, list):
            return []
        return [entry.get("name") for entry in publishers if entry.get("name")]

    # Advanced (for future/AI use)
    extracted["related_games"] = data.get("related_games")
    extracted["developers"] = get_developer_names(data.get("developers"))
    extracted["publishers"] = get_publisher_names(data.get("publishers"))
    discord_id_list = data.get("discord_id", {}).get("id", [])
    igdb_id_list = data.get("igdb_id", {}).get("id", [])
    extracted["discord_id"] = discord_id_list
    extracted["igdb_id"] = igdb_id_list

    # ------------ ADDED: ratings extraction ------------
    def extract_ratings_block(game: dict):
        r = (game or {}).get("ratings") or {}

        def pick(branch: str):
            b = r.get(branch) or {}
            overall = b.get("overall_rating")
            try:
                overall = round(float(overall), 2) if overall is not None else None
            except Exception:
                overall = None

            count = b.get("no_of_ratings")
            try:
                count = int(count) if count not in (None, "") else None
            except Exception:
                count = None

            return {"no_of_ratings": count, "overall_rating": overall}

        return {
            "user_ratings": pick("user_ratings"),
            "critic_ratings": pick("critic_ratings"),
        }

    extracted["ratings"] = extract_ratings_block(data)
    # ------------ END ADDED ------------

    return extracted

# Update with your directory
json_dir = "./game_data/extracted"
output_csv = "./game_data/games_full_schema_extract.csv"
output_json = "./game_data/games_full_schema_extract.json"

all_data = []

for fname in os.listdir(json_dir):
    if fname.endswith(".json"):
        try:
            with open(os.path.join(json_dir, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
                extracted = extract_game_fields(data)
                all_data.append(extracted)
        except Exception as e:
            print(f"Failed to process {fname}: {e}")

# Set your column order
csv_fields = [
    "external_game_id","title","alternative_titles","description","release_date","region",
    "editions","platforms","distributions","genre","subgenres","game_vibe","main_perspective",
    "keywords","gameplay_elements","advancement","linearity","replay_value",
    "graphical_visual_style","themes","complexity","age_rating","key_features","links","has_story",
    "developers","publishers","related_games",
    "discord_id","igdb_id","sku",
    "story_setting_realism"
]

# ------------ ADDED: include ratings in CSV ------------
csv_fields.append("ratings")
# ------------ END ADDED ------------

def convert_sets(obj):
    """Recursively convert all sets to lists in the given data structure."""
    if isinstance(obj, set):
        return list(obj)
    elif isinstance(obj, dict):
        return {k: convert_sets(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_sets(v) for v in obj]
    else:
        return obj
    
with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=csv_fields)
    writer.writeheader()
    for row in all_data:
        filtered_row = {k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in row.items() if k in csv_fields}
        writer.writerow(filtered_row)

# Save as JSON as well (optional)
with open(output_json, "w", encoding="utf-8") as f:
    json.dump(convert_sets(all_data), f, indent=2, ensure_ascii=False)

print(f"Extracted {len(all_data)} files into {output_csv} and {output_json}")
