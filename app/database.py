import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()

def get_connection():
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        connection = psycopg2.connect(database_url)
    else:
        connection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD")
        )
    
    return connection