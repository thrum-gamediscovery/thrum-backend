import pandas as pd
from sentence_transformers import SentenceTransformer
import ast

# Load the model
model = SentenceTransformer("all-MiniLM-L12-v2")

# Load the CSV file
df = pd.read_csv("./game_s_data/mood_related_words.csv")

# Generate embeddings for combined mood + related_mood (but don't store the combined text)
df['embedding'] = df.apply(lambda row: model.encode(f"{row['mood']} | {row['mood_description']} | {row['related_words']}").tolist(), axis=1)

# Save to new CSV without intermediate combined text
df.to_csv("./game_s_data/mood_with_embeddings.csv", index=False)

print("Saved: ./game_s_data/mood_with_embeddings.csv")



import pandas as pd
import openai
import time

# Set your OpenAI API key
client = openai.OpenAI(api_key="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")

# Load the mood CSV
df = pd.read_csv("mood_clusters_with_embeddings.csv")

def get_game_tag_from_mood(mood_name):
    prompt = f"""A user is currently feeling "{mood_name}".
From the list of predefined game tags below, select 3–5 that would be emotionally suitable for the user to play in this mood — either to comfort, energize, or rebalance their state.

Only choose from this list: action horror, action-adventure, action-oriented, action-packed, action-packed adventure, adrenaline, adventure, adventurous, calm, challenging, combat-focused, competitive, creative, dark, dark fantasy, dark humor, dramatic, dynamic, dynamic simulation, dystopian, energetic, engaging, epic, epic adventure, exciting, exploration, explorative, exploratory, fantasy, fun, horror, horror adventure, horror-comedy, immersive, immersive strategy, intense, intense action, joyful, light-hearted, lighthearted, playful, post-apocalyptic, relaxation, relaxing, serious, skill development, social exploration, sporting, strategic, survival, survival horror, suspense, suspenseful, tense, tension, warfare, whimsical, wholesome.

Only return a comma-separated list of game tags from the list above. No explanations."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error for mood '{mood_name}':", e)
        return ""
generated_game_tags = []
# Generate game_tag for each mood
for mood in df['mood_name']:
    tag_result = get_game_tag_from_mood(mood)
    print(f"Generated game tags for mood '{mood}': {tag_result}")
    generated_game_tags.append(tag_result)
    time.sleep(3) # to avoid hitting rate limits

# # Drop the mood_description column
# if "mood_description" in df.columns:
#     df = df.drop(columns=["mood_description"])

# Create an empty list to store game tags
game_tags = ['action horror', 'action-adventure', 'action-oriented', 'action-packed', 'action-packed adventure', 'adrenaline', 'adventure', 'adventurous', 'calm', 'challenging', 'combat-focused', 'competitive', 'creative', 'dark', 'dark fantasy', 'dark humor', 'dramatic', 'dynamic', 'dynamic simulation', 'dystopian', 'energetic', 'engaging', 'epic', 'epic adventure', 'exciting', 'exploration', 'explorative', 'exploratory', 'fantasy', 'fun', 'horror', 'horror adventure', 'horror-comedy', 'immersive', 'immersive strategy', 'intense', 'intense action', 'joyful', 'light-hearted', 'lighthearted', 'playful', 'post-apocalyptic', 'relaxation', 'relaxing', 'serious', 'skill development', 'social exploration', 'sporting', 'strategic', 'survival', 'survival horror', 'suspense', 'suspenseful', 'tense', 'tension', 'warfare', 'whimsical', 'wholesome']
df['game_tag'] = generated_game_tags
# Function to generate game_tag using OpenAI
# Updated Prompt Function