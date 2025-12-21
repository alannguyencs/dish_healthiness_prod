"""
CRUD operations for dish image queries.

This module provides Create, Read, Update, Delete operations for
DishImageQuery model. Functions are organized into separate modules:
- dish_query_basic: Basic CRUD operations
- dish_query_filters: Query and filter operations
- dish_query_iterations: Iteration management

This file serves as a facade to maintain backward compatibility.
"""

# Import all functions from submodules
from src.crud.dish_query_basic import (
    create_dish_image_query,
    get_dish_image_query_by_id,
    get_dish_image_queries_by_user,
    update_dish_image_query_results,
    delete_dish_image_query_by_id,
)

from src.crud.dish_query_filters import (
    get_dish_image_queries_by_user_and_date,
    get_single_dish_by_user_date_position,
    get_calendar_data,
)

from src.crud.dish_query_iterations import (
    initialize_iterations_structure,
    get_current_iteration,
    add_metadata_reanalysis_iteration,
    update_metadata,
    get_latest_iterations,
)

# Re-export all functions
__all__ = [
    # Basic CRUD
    "create_dish_image_query",
    "get_dish_image_query_by_id",
    "get_dish_image_queries_by_user",
    "update_dish_image_query_results",
    "delete_dish_image_query_by_id",
    # Filters and queries
    "get_dish_image_queries_by_user_and_date",
    "get_single_dish_by_user_date_position",
    "get_calendar_data",
    # Iterations
    "initialize_iterations_structure",
    "get_current_iteration",
    "add_metadata_reanalysis_iteration",
    "update_metadata",
    "get_latest_iterations",
]
