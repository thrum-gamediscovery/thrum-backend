import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Game, GamePlatform  # Replace with actual models for your tables
from app.core.config import settings

# Database connection (make sure to update with your actual credentials)
DATABASE_URI = settings.DATABASE_URL  # Update with actual DB URI
engine = create_engine(DATABASE_URI)
Session = sessionmaker(bind=engine)
session = Session()

# Load data from the JSON file
with open('./gameopedia/final_game_data_with_embeddings.json') as f:
    json_data = json.load(f)

def convert_to_boolean(value):
    if isinstance(value, str):
        return value.lower() == 'true'  # Convert 'True' or 'true' to True, 'False' to False
    return value  # Return the value as-is if it's already a boolean

# Update or Insert data into the 'game' table
for game in json_data:
    db_game = session.query(Game).filter(Game.title == game['title']).first()
    
    if db_game:
        # If the game exists, update the record
        # db_game.description = game.get('description', db_game.description)
        # db_game.genre = game.get('genre', db_game.genre)
        # db_game.game_vibes = game.get('game_vibes', db_game.game_vibes)
        db_game.complexity = game.get('complexity', db_game.complexity)
        # db_game.graphical_visual_style = game.get('graphical_visual_style', db_game.graphical_visual_style)
        # db_game.age_rating = game.get('age_rating', db_game.age_rating)
        # db_game.region = game.get('region', db_game.region)
        # db_game.has_story = convert_to_boolean(game.get('has_story', db_game.has_story))
        # db_game.emotional_fit = game.get('emotional_fit', db_game.emotional_fit)
        # db_game.mood_tag = game.get('mood_tags', db_game.mood_tag)
        # db_game.alternative_titles = game.get('alternative_titles', db_game.alternative_titles)
        # db_game.release_date = game.get('release_date', db_game.release_date)
        # db_game.editions = game.get('editions', db_game.editions)
        # db_game.subgenres = game.get('subgenres', db_game.subgenres)
        # db_game.story_setting_realism = game.get('story_setting_realism', db_game.story_setting_realism)
        # db_game.main_perspective = game.get('main_perspective', db_game.main_perspective)
        # db_game.keywords = game.get('keywords', db_game.keywords)
        db_game.gameplay_elements = game.get('gameplay_elements', db_game.gameplay_elements)
        # db_game.advancement = game.get('advancement', db_game.advancement)
        # db_game.linearity = game.get('linearity', db_game.linearity)
        # db_game.themes = game.get('themes', db_game.themes)
        # db_game.replay_value = game.get('replay_value', db_game.replay_value)
        # db_game.developers = game.get('developers', db_game.developers)
        # db_game.publishers = game.get('publishers', db_game.publishers)
        # db_game.discord_id = game.get('discord_id', db_game.discord_id)
        # db_game.igdb_id = game.get('igdb_id', db_game.igdb_id)
        # db_game.sku = game.get('sku', db_game.sku)
        db_game.gameplay_embedding = game.get('gameplay_embedding', db_game.gameplay_embedding)
        db_game.preference_embedding = game.get('preference_embedding', db_game.preference_embedding)
        # db_game.key_features = game.get('short_key_features', db_game.key_features)
        print(f"game : {Game.title}")
        session.commit()
        
        # # Update or insert platforms for this game
        # for platform in game.get('platforms', []):
        #     platform_link = game.get('platform_link', {}).get(platform)
        #     platform_distribution = game.get('distribution', {}).get(platform)
            
        #     db_platform = session.query(GamePlatform).filter(GamePlatform.game_id == db_game.game_id, GamePlatform.platform == platform).first()
            
        #     if db_platform:
        #         db_platform.link = platform_link  # Update the link field
        #         db_platform.distribution = platform_distribution  # Update the distribution field
        #     else:
        #         # If no db_platform is found, create a new one
        #         new_platform = GamePlatform(game_id=db_game.game_id, platform=platform, link=platform_link, distribution=platform_distribution)
        #         session.add(new_platform)  # Add the new platform entry

        # session.commit()  # Commit changes for all platforms at once
        
    # else:
    #     # If the game doesn't exist, insert a new record
    #     new_game = Game(
    #         title=game['title'],
    #         description=game.get('description'),
    #         genre=game.get('genre'),
    #         game_vibes=game.get('game_vibes'),
    #         mechanic=game.get('mechanics'),
    #         graphical_visual_style=game.get('graphical_visual_style'),
    #         age_rating=game.get('age_rating'),
    #         region=game.get('region'),
    #         has_story=convert_to_boolean(game.get('has_story', False)),  # Default to False if not provided
    #         emotional_fit=game.get('emotional_fit'),
    #         mood_tag=game.get('mood_tags'),
    #         alternative_titles=game.get('alternative_titles'),
    #         release_date=game.get('release_date'),
    #         editions=game.get('editions'),
    #         subgenres=game.get('subgenres'),
    #         story_setting_realism=game.get('story_setting_realism'),
    #         main_perspective=game.get('main_perspective'),
    #         keywords=game.get('keywords'),
    #         gameplay_elements=game.get('gameplay_elements'),
            # advancement=game.get('advancement'),
            # linearity=game.get('linearity'),
            # themes=game.get('themes'),
            # replay_value=game.get('replay_value'),
            # developers=game.get('developers'),
            # publishers=game.get('publishers'),
            # discord_id=game.get('discord_id'),
            # igdb_id=game.get('igdb_id'),
            # sku=game.get('sku'),
            # gameplay_embedding=game.get('gameplay_embedding'),
            # preference_embedding=game.get('preference_embedding'),
            # key_features=game.get('short_key_features'),
        # )
        # session.add(new_game)
        # session.commit()  # Commit the new game entry to the database
        
        # Now handle platforms related to this game
        # for platform in game.get('platforms', []):
        #     platform_link = game.get('platform_link', {}).get(platform)
        #     platform_distribution = game.get('distribution', {}).get(platform)
        #     new_platform = GamePlatform(game_id=new_game.game_id, platform=platform, link=platform_link, distribution=platform_distribution)
        #     session.add(new_platform)  # Add the new platform entry

        # session.commit()  # Commit all platform changes at once

# Close the session
session.close()
print("done")