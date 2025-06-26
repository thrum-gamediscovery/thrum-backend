import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.db.models.unique_value import UniqueValue
from app.core.config import settings
from app.db.base import Base 
import ast

# Load CSV
df = pd.read_csv("./gameopedia/unique_fields_output.csv")

# Convert stringified list into actual list
df["unique_value"] = df["unique_value"].apply(ast.literal_eval)

# Setup DB connection
DATABASE_URL = settings.DATABASE_URL
engine = create_engine(DATABASE_URL)
Base.metadata.create_all(engine)
session = Session(bind=engine)

# Insert data
for _, row in df.iterrows():
    field = row["field"]
    values = row["unique_value"]  # list
    unique_entry = UniqueValue(field=field, unique_values=values)
    session.add(unique_entry)

session.commit()
session.close()

print("✅ UniqueValue data inserted successfully.")
