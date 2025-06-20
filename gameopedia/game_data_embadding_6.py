import pandas as pd
from sentence_transformers import SentenceTransformer
import ast
import sentence_transformers
print("sentence-transformers version:", sentence_transformers.__version__)


# Load CSV
df = pd.read_csv('./game_s_data/games_custom_with_emotion.csv')

# Fill NaNs with empty strings to avoid issues in concatenation
for col in ['title', 'description', 'genre', 'game_vibes', 'mechanics', 'visual_style', 'platform', 'emotional_fit', 'mood_tags']:
    df[col] = df[col].fillna('')

# Combine relevant columns into one text string per game for embedding
def combine_text_game(row):
    return " | ".join([
        row['title'],
        row['genre'],
        row['game_vibes'],
        row['mechanics'],
        row['visual_style']
    ])

def combine_text_mood(row):
    try:
        mood_dict = row['mood_tags']
        if isinstance(mood_dict, str):
            mood_dict = ast.literal_eval(mood_dict)

        mood_values = []
        for value in mood_dict.values():
            if isinstance(value, dict):
                nested_values = [str(v).replace(",", "|") for v in value.values()]
                mood_values.extend(nested_values)
            else:
                mood_values.append(str(value).replace(",", "|"))

        return f"{row['emotional_fit'].replace(',', '|')} | " + " | ".join(mood_values)
    except Exception as e:
        print("Error parsing mood_tags:", row['mood_tags'], e)
        return row['emotional_fit'].replace(",", "|")

df['combine_text_game'] = df.apply(combine_text_game, axis=1)
df['combine_text_mood'] = df.apply(combine_text_mood, axis=1)
# print(df['combine_text_mood'][0])

# Load embedding model
model = SentenceTransformer('all-MiniLM-L12-v2')

# Generate embeddings for combined text
embeddings_game = model.encode(df['combine_text_game'].tolist(), show_progress_bar=True)
embeddings_mood = model.encode(df['combine_text_mood'].tolist(), show_progress_bar=True)
print("Embedding dimension example:", len(embeddings_game[0]))
print("Embedding dimension example:", len(embeddings_mood[0]))

# Add embeddings as a new column (list format)
df['game_embedding'] = embeddings_game.tolist()
df['mood_embedding'] = embeddings_mood.tolist()

# Select only desired columns for output, including embedding
output_cols = ['title', 'description', 'genre', 'game_vibes', 'mechanics', 'visual_style', 'platform', 'emotional_fit', 'mood_tags', 'game_embedding', 'mood_embedding']
output_df = df[output_cols]

# Save to CSV (embedding stored as list string)
output_df.to_csv('./game_s_data/games_with_embeddings.csv', index=False)

print("Saved games with embeddings to 'games_with_embeddings.csv'")
