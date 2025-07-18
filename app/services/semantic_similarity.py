import openai
import os
from typing import List

# Set API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
model = os.getenv("GPT_MODEL")

client = openai.AsyncOpenAI()

async def check_semantic_similarity(existing_values: List[str], new_values: List[str]) -> List[str]:
    """
    Check if new values are semantically similar to existing values.
    Return only new values that are not semantically similar to any existing value.
    """
    if not existing_values or not new_values:
        return new_values
    
    prompt = f"""
    I have a list of existing values: {existing_values}
    And a list of new values: {new_values}
    
    For each new value, determine if it is semantically similar to any existing value.
    Return only the new values that are NOT semantically similar to any existing value.
    
    For example:
    - If existing values include "solo" and new values include "single-player", don't include "single-player" because it's semantically similar to "solo"
    - If existing values include "combat" and new values include "fighting", don't include "fighting" because it's semantically similar to "combat"
    
    Return the result as a JSON array of strings, with no explanation.
    """
    
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt}],
            temperature=0,
        )
        
        result = response.choices[0].message.content.strip()
        # Clean up the response to get a valid JSON array
        result = result.replace("```json", "").replace("```", "").strip()
        if result.startswith("[") and result.endswith("]"):
            import json
            try:
                unique_values = json.loads(result)
                return unique_values
            except:
                # If parsing fails, return all new values
                return new_values
        else:
            # If response is not a JSON array, return all new values
            return new_values
    except Exception as e:
        print(f"⚠️ Error checking semantic similarity: {e}")
        # In case of error, return all new values
        return new_values