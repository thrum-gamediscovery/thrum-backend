# import pandas as pd

# # Load your CSV file
# df = pd.read_csv("./game_s_data/games_custom.csv")

# # Function to merge duplicate rows for the same game_id
# def merge_group(group):
#     merged = group.iloc[0].copy()
    
#     # Combine all unique platforms into a list
#     merged['platform'] = group['platform'].dropna().unique().tolist()
    
#     # For each of the fields below, keep the longest non-null value
#     for field in ['description', 'genre', 'game_vibes', 'mechanics', 'visual_style']:
#         values = group[field].dropna().unique().tolist()
#         if values:
#             merged[field] = max(values, key=len)
    
#     return merged

# # Apply the group merging
# final_df = df.groupby('game_id').apply(merge_group).reset_index(drop=True)

# # Optional: save the result to a new CSV
# final_df.to_csv("./game_s_data/merged_games_custom.csv", index=False)

# # Display a few rows to verify
# print(final_df.head())


import pandas as pd
import re

# Load the CSV
df = pd.read_csv("./game_s_data/games_custom.csv")

# Function to clean and extract keywords from game_vibes (split by , or /)
def clean_game_vibes(vibes_str):
    if pd.isna(vibes_str):
        return []
    # Split by comma or slash
    raw_items = re.split(r'[,/]', vibes_str)
    return [re.sub(r'\(.*?\)', '', v.strip()).strip().lower() for v in raw_items if v.strip()]

# Function to split and clean genre string
def clean_genres(genre_str):
    if pd.isna(genre_str):
        return []
    return [g.strip().lower() for g in genre_str.split(',') if g.strip()]

# Merge logic for each group
def merge_group(group):
    merged = group.iloc[0].copy()
    merged['platform'] = group['platform'].dropna().unique().tolist()
    
    for field in ['description', 'mechanics', 'visual_style']:
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
    
    return merged

# Apply the merging logic
final_df = df.groupby('game_id').apply(merge_group).reset_index(drop=True)

# Save to a new CSV
final_df.to_csv("./game_s_data/merged_games_custom_cleaned.csv", index=False)

# Optional: print sample rows
print(final_df.head())
