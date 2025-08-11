import pandas as pd

# Load the CSV
df = pd.read_csv("./game_data/games_full_schema_extract.csv")

# Ensure age_rating is int, fill missing with 0
if 'age_rating' in df.columns:
    df['age_rating'] = pd.to_numeric(df['age_rating'], errors='coerce').fillna(0).astype(int)

# Function to merge grouped data for unique games
def merge_group(group, **kwargs):
    merged = group.iloc[0].copy()
    group = group.reset_index(drop=True)
    # Merge unique platforms as list
    merged['platforms'] = group['platforms'].dropna().unique().tolist()
    # Build a dict of platform to link
    platform_dict = {}
    distribution_dict = {}
    for _, row in group.iterrows():
        platform_name = row['platforms']
        platform_link = row['links'] if pd.notna(row['links']) else None
        if pd.notna(platform_name):
            # Only keep first non-null link per platform
            if platform_name not in platform_dict and platform_link is not None:
                platform_dict[platform_name] = platform_link
        distribution = row['distributions'] if pd.notna(row['distributions']) else None
        if pd.notna(platform_name):
            # Only keep first non-null link per platform
            if platform_name not in distribution_dict and distribution is not None:
                distribution_dict[platform_name] = distribution
            
    merged['platform_link'] = platform_dict
    merged['distribution'] = distribution_dict
    # Merge remaining fields, prefer longest unique string
    fields = ["release_date","region","editions","genre","subgenres","game_vibe","main_perspective","keywords","gameplay_elements","advancement","linearity","replay_value","graphical_visual_style","themes","complexity","age_rating","key_features","links","has_story","developers","publishers","related_games","discord_id","igdb_id","sku","story_setting_realism", "alternative_titles","description","ratings"]
    for field in fields:
        values = group[field].dropna().unique().tolist()
        if values:
            # Use max string or first non-string
            if all(isinstance(v, str) for v in values):
                merged[field] = max(values, key=len)
            else:
                merged[field] = values[0]
    return merged

# Apply group-by and merge logic
final_df = df.groupby('external_game_id').apply(merge_group, include_group=False).reset_index(drop=True)
# Save to new CSV
final_df.to_csv("./game_data/unique_games.csv", index=False)
