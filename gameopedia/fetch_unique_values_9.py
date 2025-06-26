import pandas as pd
import ast

# Load CSV
df = pd.read_csv("games_with_embeddings.csv")

def extract_unique_from_column(df, column_name):
    unique_values = set()
    for val in df[column_name].dropna():
        try:
            # Handle list-like strings e.g., "['cozy', 'fun']"
            parsed = ast.literal_eval(val) if isinstance(val, str) and val.startswith("[") else [val]
            unique_values.update(map(str.strip, parsed))
        except Exception:
            unique_values.add(val.strip())
    return sorted(unique_values)

# Extract unique values
data = {
    "genre": extract_unique_from_column(df, "genre"),
    "platform": extract_unique_from_column(df, "platform"),
    "game_vibes": extract_unique_from_column(df, "game_vibes"),
}

# Format for CSV storage
records = [{"field": key, "unique_value": str(values)} for key, values in data.items()]
output_df = pd.DataFrame(records)

# Save to CSV
output_df.to_csv("./unique_fields_output.csv", index=False)

print("✅ Unique values stored in 'unique_fields_output.csv'")
