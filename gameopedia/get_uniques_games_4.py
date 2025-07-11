import pandas as pd
import re

# Load the CSV
df = pd.read_csv("./games_data/games_custom.csv")

 # Step 1: Extract all words/phrases BEFORE any parenthesisif 'age_rating' in df.columns:if 'age_rating' in df.columns:
if 'age_rating' in df.columns:
    df['age_rating'] = pd.to_numeric(df['age_rating'], errors='coerce').fillna(0).astype(int)

# Function to clean and extract keywords from game_vibes (split by , or /)
def clean_game_vibes(vibes_str):
    if pd.isna(vibes_str):
        return []
    # This avoids splitting inside (Major, All or Most)
    raw_items = re.findall(r'([^,/(]+)\s*(?:\([^)]*\))?', vibes_str)

    # Step 2: Normalize and clean
    cleaned = []
    for item in raw_items:
        item = item.strip().lower()
        if item and item not in ['all or most', 'major']:  # explicitly filter unwanted tags
            cleaned.append(item)
    return list(set(cleaned))

# Function to split and clean genre string
def clean_genres(genre_str):
    if pd.isna(genre_str):
        return []
    return [g.strip().lower() for g in genre_str.split(',') if g.strip()]

# Merge logic for each group
def merge_group(group):
    merged = group.iloc[0].copy()
    merged['platform'] = group['platform'].dropna().unique().tolist()
    platform_dict = {}
    for _, row in group.iterrows():
        game_id = row['game_id']
        platform_name = row['platform'] 
        platform_link = row['link'] if pd.notna(row['link']) else None
        print(f"platform_link ------------- {game_id} -> {platform_name} -> {platform_link}")
        # Store the platform with its corresponding link or None
        if pd.notna(platform_name):
            if platform_name not in platform_dict or (platform_name is platform_dict and platform_link is not None):
                platform_dict[platform_name] = platform_link
                print(f"platform_link +++++++++++++ {game_id} -> {platform_name} -> {platform_link}")
                # Store the platform-link dictionary in the merged row
    merged['platform_link'] = platform_dict
    print(merged['platform_link'])
    for field in ['description', 'mechanics', 'visual_style','region']:
        values = group[field].dropna().unique().tolist()
        if values:
            merged[field] = max(values, key=len)
    
    genre_list = []
    vibes_list = []
    for _, row in group.iterrows():
        genre_list.extend(clean_genres(row.get('genre', '')))
        vibes_list.extend(clean_game_vibes(row.get('game_vibes', '')))
    
    merged['genre'] = list(set(genre_list))
    merged['game_vibes'] = list(set(vibes_list))
    print(merged['game_vibes'])
    return merged

# Apply the merging logic
final_df = df.groupby('game_id').apply(merge_group).reset_index(drop=True)

# Save to a new CSV
final_df.to_csv("./games_data/merged_games_custom.csv", index=False)

