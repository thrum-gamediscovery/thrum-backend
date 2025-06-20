from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cosine
# Load model globally (you can move this outside function)
model = SentenceTransformer("all-MiniLM-L12-v2")
VALID_GENRES = [
    'driving', 'fighting', 'puzzle', 'shooter', 'adventure', 'platform', 'action',
    'flying', 'mmo', 'role-playing', 'strategy', 'music', 'racing', 'simulation',
    'sports', 'real-world game', 'virtual life', 'party', 'other', 'trivia'
]
# Precompute genre embeddings once
VALID_GENRE_EMBEDDINGS = {genre: model.encode(genre) for genre in VALID_GENRES}
def get_best_genre_match(input_genre: str) -> str | None:
    input_vec = model.encode(input_genre)
    best_match = None
    best_score = -1
    for genre, vec in VALID_GENRE_EMBEDDINGS.items():
        score = 1 - cosine(input_vec, vec)
        if score > best_score:
            best_score = score
            best_match = genre
    return best_match if best_score >= 0.3 else None