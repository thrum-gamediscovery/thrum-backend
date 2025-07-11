from sentence_transformers import SentenceTransformer, util

# Load model once
model = SentenceTransformer('all-MiniLM-L6-v2')

# Define tone categories with example phrases
tone_examples = {
    "positive": ["cool", "sounds fun", "excited", "love it", "let's go"],
    "vague": ["okay", "maybe", "not sure", "fine", "guess"],
    "cold": ["nah", "skip", "boring", "meh", "pass"]
}

# Precompute embeddings for each tone category
tone_embeddings = {
    tone: model.encode(samples, convert_to_tensor=True)
    for tone, samples in tone_examples.items()
}

def classify_tone(text: str) -> str:
    """
    Classify the tone of user input as positive, vague, or cold using MiniLM similarity.
    """
    input_embedding = model.encode(text, convert_to_tensor=True)
    scores = {}
    
    for tone, emb in tone_embeddings.items():
        similarities = util.cos_sim(input_embedding, emb)
        scores[tone] = similarities.max().item()
    
    return max(scores, key=scores.get)
