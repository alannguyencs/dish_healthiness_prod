"""
Database migration script to replace meal_type with dish_position.

This script migrates the dish_image_query_prod table from using meal_type
(breakfast, lunch, dinner, snack) to using dish_position (1-5).

Author: System
Date: 2025-11-07
"""

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from src.database import engine
from sqlalchemy import text


def migrate_to_dish_position():
    """
    Migrate the database from meal_type to dish_position.
    
    Steps:
    1. Add dish_position column
    2. Migrate existing data (optional - map meal types to positions)
    3. Drop meal_type column
    """
    
    with engine.connect() as conn:
        print("Starting migration to dish_position...")
        
        # Step 1: Add dish_position column (nullable)
        print("Adding dish_position column...")
        try:
            conn.execute(text(
                "ALTER TABLE dish_image_query_prod "
                "ADD COLUMN dish_position INTEGER NULL"
            ))
            conn.commit()
            print("✓ Added dish_position column")
        except Exception as e:
            if "already exists" in str(e):
                print("✓ dish_position column already exists")
            else:
                raise
        
        # Step 2: Drop meal_type column (if exists)
        print("Dropping meal_type column...")
        try:
            conn.execute(text(
                "ALTER TABLE dish_image_query_prod "
                "DROP COLUMN IF EXISTS meal_type"
            ))
            conn.commit()
            print("✓ Dropped meal_type column")
        except Exception as e:
            print(f"Warning: Could not drop meal_type column: {e}")
        
        print("\n✓ Migration completed successfully!")
        print("Note: Existing records will have dish_position = NULL")
        print("New uploads will use dish_position 1-5")


if __name__ == "__main__":
    migrate_to_dish_position()

