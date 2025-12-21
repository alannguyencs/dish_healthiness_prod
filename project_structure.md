# Project Structure Documentation

## Project Overview

**Dish Healthiness** is a fullstack web application that analyzes food images using AI to provide health and nutritional insights. The application uses OpenAI GPT-5 and Google Gemini models to analyze uploaded dish photos and provide detailed nutritional information, healthiness scores, and personalized serving size recommendations.

### Key Features
- User authentication with JWT sessions
- Calendar-based food diary interface
- AI-powered dish identification and nutritional analysis
- Multiple dish predictions with confidence scores
- Customizable serving sizes and portions
- Iterative re-analysis based on user feedback
- Dual LLM analysis (OpenAI GPT-5 and Google Gemini)

### Technology Stack

**Backend:**
- FastAPI (Python web framework)
- PostgreSQL (Database)
- SQLAlchemy (ORM)
- OpenAI API (GPT-5 for analysis)
- Google Gemini API (2.5-pro/flash for analysis)
- JWT for authentication
- Pydantic for data validation

**Frontend:**
- React 18
- React Router v6 (Client-side routing)
- Axios (HTTP client)
- Tailwind CSS (Styling)

---

## Backend

The backend is located in `/Users/alan/Documents/delta/dish_healthiness_prod/backend/` and follows a modular architecture with clear separation of concerns.

### Root Level (`/backend/src/`)

This folder contains the core application setup and configuration files.

#### `main.py`

Main FastAPI application entry point that orchestrates the entire backend.

- `configure_logging()`: Sets up application logging with console and file handlers
- `create_app()`: Creates and configures the FastAPI application instance with middleware, CORS, static files, and database initialization
- `root()`: Root endpoint returning API information
- `health()`: Health check endpoint for monitoring

#### `configs.py`

Configuration management and application settings.

- `Settings`: Pydantic settings class managing API versioning and project configuration
- `Settings.get_api_url()`: Returns the full API URL string
- `Settings.get_project_identifier()`: Returns lowercase project name identifier
- Module defines directory constants: `PROJECT_DIR`, `DATA_DIR`, `IMAGE_DIR`, `RESOURCE_DIR`, `LOG_DIR`
- Module defines authentication constant: `TOKEN_EXPIRATION_DAYS`

#### `database.py`

Database configuration and session management for PostgreSQL.

- `build_database_url()`: Constructs PostgreSQL connection URL from environment variables
- `get_db()`: Generator function providing database sessions for dependency injection
- Module creates SQLAlchemy engine and session factory
- Module defines `Base` declarative base for ORM models

#### `models.py`

SQLAlchemy ORM models defining database schema.

- `Users`: User authentication model with username, hashed password, and role
- `Users.__repr__()`: String representation of user object
- `Users.to_dict()`: Converts user to dictionary format
- `DishImageQuery`: Food analysis query model storing image URLs and AI analysis results
- `DishImageQuery.__repr__()`: String representation of query object
- `DishImageQuery.to_dict()`: Converts query to dictionary format

#### `schemas.py`

Pydantic schemas for request/response validation and serialization.

- `Token`: Authentication token response schema
- `UserBase`: Base user schema with common fields
- `UserCreate`: Schema for user registration with password
- `UserResponse`: User response schema excluding sensitive data
- `DishImageQueryBase`: Base schema for dish image queries
- `DishImageQueryCreate`: Schema for creating new dish queries
- `DishImageQueryResponse`: Schema for dish query responses
- `MetadataUpdate`: Schema for updating dish metadata (dish name, serving size, servings count)

#### `auth.py`

Authentication utilities for JWT and user verification.

- `authenticate_user()`: Authenticates user with username and password
- `create_access_token()`: Creates JWT access token with expiration
- `get_current_user_from_token()`: Validates JWT token and returns user object
- `authenticate_user_from_request()`: Authenticates user from HTTP request cookie
- Module defines password hashing context and OAuth2 scheme

#### `utils.py`

General utility functions for the application.

- `format_datetime()`: Formats datetime objects for display

---

### API Endpoints (`/backend/src/api/`)

This folder contains all REST API endpoint definitions organized by functionality.

#### `api_router.py`

Central API router aggregating all endpoint modules.

- Module includes routers from: login, dashboard, date, and item modules

#### `login.py`

User authentication endpoints with session management.

- `LoginRequest`: Pydantic model for login credentials
- `process_login()`: POST endpoint handling user login and creating session cookies
- `logout()`: POST endpoint handling user logout and clearing session

#### `dashboard.py`

Dashboard calendar view endpoints providing monthly overview.

- `dashboard()`: GET endpoint returning calendar data with user's food analyses for a specific month

#### `date.py`

Date-specific endpoints for viewing and uploading dishes.

- `analyze_image_background()`: Background task function for asynchronous Gemini image analysis
- `_serialize_query()`: Helper function to serialize query objects to dictionaries
- `get_date()`: GET endpoint returning all dishes for a specific date
- `upload_dish()`: POST endpoint handling image upload, processing, and scheduling background analysis

#### `item.py`

Individual dish detail and analysis endpoints.

- `item_detail()`: GET endpoint returning detailed analysis for a specific dish record
- `update_item_metadata()`: PATCH endpoint updating dish metadata (name, serving size, servings count)
- `reanalyze_item()`: POST endpoint triggering re-analysis with updated metadata using brief model

---

### CRUD Operations (`/backend/src/crud/`)

This folder contains database CRUD (Create, Read, Update, Delete) operations.

#### `crud_user.py`

User model CRUD operations.

- `get_db_session()`: Returns a new database session
- `get_user_by_username()`: Retrieves user by username
- `get_user_by_id()`: Retrieves user by ID
- `create_user()`: Creates new user with hashed password
- `update_user_password()`: Updates user password
- `delete_user()`: Deletes user by ID

#### `crud_food_image_query.py`

Dish image query CRUD operations with iteration management.

- `create_dish_image_query()`: Creates new dish image query record
- `get_dish_image_query_by_id()`: Retrieves query by ID
- `get_dish_image_queries_by_user()`: Gets all queries for a user
- `get_dish_image_queries_by_user_and_date()`: Gets queries for specific user and date
- `get_single_dish_by_user_date_position()`: Gets single dish by position for a date
- `update_dish_image_query_results()`: Updates analysis results (OpenAI/Gemini)
- `delete_dish_image_query_by_id()`: Deletes query by ID
- `get_calendar_data()`: Returns record counts per day for calendar view
- `initialize_iterations_structure()`: Creates iteration structure for first analysis
- `get_current_iteration()`: Retrieves current iteration from query result
- `add_metadata_reanalysis_iteration()`: Adds new iteration after metadata-based re-analysis
- `update_metadata()`: Updates metadata for current iteration
- `get_latest_iterations()`: Gets most recent iterations for display

---

### Service Layer (`/backend/src/service/llm/`)

This folder contains LLM (Large Language Model) integration services for food analysis.

#### `high_level_api.py`

High-level API for orchestrating dish analysis.

- `analyze_dish_parallel_async()`: Runs OpenAI and Gemini analyses in parallel (async)
- `analyze_dish_parallel()`: Synchronous wrapper for parallel dish analysis

#### `openai_analyzer.py`

OpenAI GPT integration for dish health analysis.

- `prepare_openai_model_and_reasoning()`: Extracts reasoning mode and model name for GPT-5 variants
- `enrich_result_with_metadata()`: Enriches analysis results with model, pricing, and timing metadata
- `analyze_with_openai_async()`: Analyzes dish image using OpenAI GPT with structured output

#### `gemini_analyzer.py`

Google Gemini integration for dish health analysis.

- `enrich_result_with_metadata()`: Enriches results with model, pricing, and timing metadata
- `analyze_with_gemini_async()`: Analyzes dish image using Gemini with full schema
- `analyze_with_gemini_brief_async()`: Re-analyzes dish using Gemini with brief schema (excludes dish predictions to save tokens)

#### `prompts.py`

Prompt loading and management utilities.

- `get_analysis_prompt()`: Loads default analysis prompt from food_analysis.md (with dish predictions)
- `get_brief_analysis_prompt()`: Loads brief analysis prompt from food_analysis_brief.md (without dish predictions)

#### `models.py`

Pydantic models defining LLM response schemas.

- `DishPrediction`: Single dish prediction with name, confidence, serving sizes, and predicted servings
- `FoodHealthAnalysis`: Full analysis model with dish predictions (for initial analysis)
- `FoodHealthAnalysisBrief`: Brief analysis model without dish predictions (for re-analysis)

#### `pricing.py`

LLM pricing and token usage calculation utilities.

- `normalize_model_key()`: Normalizes model string to pricing key
- `compute_price_usd()`: Calculates API cost based on token usage and model pricing
- `extract_token_usage()`: Extracts input and output token counts from API responses
- Module defines pricing table for OpenAI and Gemini models

---

## Frontend

The frontend is located in `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/` and is built with React following a component-based architecture.

### Root Level (`/frontend/src/`)

This folder contains the main application setup and entry points.

#### `index.js`

React application entry point.

- Renders the root `App` component with StrictMode enabled

#### `App.js`

Main application component with routing configuration.

- `RedirectToDashboard`: Component handling root path redirects based on authentication state
- `App`: Main app component configuring routes for login, dashboard, date view, and item detail pages

---

### Authentication (`/frontend/src/contexts/`)

This folder contains React context providers for global state management.

#### `AuthContext.js`

Authentication context provider managing user session state.

- `AuthProvider`: Context provider component managing authentication state
- `useAuth()`: Custom hook for accessing authentication context
- Login and logout functions for authentication flow

---

### API Services (`/frontend/src/services/`)

This folder contains HTTP client services for backend communication.

#### `api.js`

Axios-based API service with all backend endpoints.

- `login()`: Authenticates user and returns session data
- `logout()`: Logs out user and clears session
- `getDashboardData()`: Fetches calendar data for dashboard
- `getDateData()`: Fetches dish data for specific date
- `uploadDishImage()`: Uploads dish image with position and date
- `getItem()`: Fetches detailed analysis for specific record
- `updateItemMetadata()`: Updates dish metadata (name, serving size, count)
- `reanalyzeItem()`: Triggers re-analysis with updated metadata

---

### Pages (`/frontend/src/pages/`)

This folder contains top-level page components corresponding to routes.

#### `Login.jsx`

Login page component with authentication form.

- Renders login form with username and password inputs
- Handles form submission and authentication errors
- Redirects to dashboard on successful login

#### `Dashboard.jsx`

Main dashboard page displaying calendar view.

- Orchestrates dashboard sub-components (header, navigation, calendar grid)
- Loads calendar data with dish counts per day
- Handles month navigation and date selection
- Shows empty state when no records exist

#### `DateView.jsx`

Date-specific view page for managing daily meals.

- Displays upload slots for up to 5 dishes per date
- Handles file uploads and redirects to analysis page
- Shows navigation back to calendar

#### `Item.jsx`

Item detail page displaying dish analysis results.

- Polls for analysis completion after upload
- Displays image, metadata, and Gemini analysis results
- Manages user feedback system (dish selection, serving sizes, servings count)
- Handles metadata updates and re-analysis requests
- Shows analysis loading states and results

---

### Components (`/frontend/src/components/`)

This folder contains reusable React components organized by feature.

#### `ProtectedRoute.jsx`

Route wrapper component for authentication protection.

- `ProtectedRoute`: Wraps routes requiring authentication and redirects unauthenticated users to login

---

### Dashboard Components (`/frontend/src/components/dashboard/`)

This folder contains components specific to the dashboard calendar view.

#### `index.js`

Centralized exports for dashboard components.

- Exports: `DashboardHeader`, `MonthNavigation`, `CalendarGrid`, `CalendarDay`, `EmptyState`

#### `DashboardHeader.jsx`

Dashboard page header component.

- Displays application title and logout button

#### `MonthNavigation.jsx`

Month navigation controls component.

- Displays current month and year
- Provides previous/next month navigation buttons

#### `CalendarGrid.jsx`

Calendar grid component displaying month days.

- Renders weekday headers and calendar weeks
- Delegates day rendering to CalendarDay component

#### `CalendarDay.jsx`

Individual calendar day cell component.

- Displays day number and dish count badge
- Handles click events for date navigation
- Highlights current day and current month days

#### `EmptyState.jsx`

Empty state message component.

- Displays when user has no food records for the month

---

### Date View Components (`/frontend/src/components/dateview/`)

This folder contains components for the date-specific meal upload view.

#### `index.js`

Centralized exports for date view components.

- Exports: `DateViewNavigation`, `MealUploadSlot`, `MealUploadGrid`

#### `DateViewNavigation.jsx`

Navigation component for date view page.

- Displays formatted date and back button to calendar

#### `MealUploadSlot.jsx`

Individual meal upload slot component.

- Handles file input and preview for dish images
- Shows existing dish thumbnails or upload prompts
- Manages upload state and image selection

#### `MealUploadGrid.jsx`

Grid layout component organizing meal upload slots.

- Renders up to 5 meal slots per date
- Displays formatted date header
- Organizes slots in responsive grid

---

### Item Components (`/frontend/src/components/item/`)

This folder contains components for individual dish detail views.

#### `index.js`

Centralized exports for item components.

- Exports: `ItemHeader`, `ItemNavigation`, `ItemImage`, `ItemMetadata`, `AnalysisLoading`, `AnalysisResults`, `NoAnalysisAvailable`, `DishPredictions`, `ServingSizeSelector`, `ServingsCountInput`

#### `ItemHeader.jsx`

Item detail page header component.

- Displays record ID and logout button

#### `ItemNavigation.jsx`

Navigation component for item detail page.

- Provides back button to date view

#### `ItemImage.jsx`

Dish image display component.

- Shows uploaded dish image with responsive sizing

#### `ItemMetadata.jsx`

Metadata display component for dish records.

- Shows creation date and target consumption date

#### `AnalysisLoading.jsx`

Loading state component during analysis.

- Displays spinner and processing message while AI analyzes dish

#### `AnalysisResults.jsx`

Analysis results display component.

- Shows healthiness score with visual indicator
- Displays nutritional information (calories, macros, micronutrients)
- Shows healthiness rationale
- Supports multi-iteration display

#### `NoAnalysisAvailable.jsx`

Error state component when analysis fails.

- Displays message when no analysis results are available

#### `DishPredictions.jsx`

Dish prediction selection component.

- Displays AI-predicted dish options with confidence scores
- Allows user to select correct dish prediction
- Shows selected prediction state

#### `ServingSizeSelector.jsx`

Serving size selection component.

- Displays serving size options for selected dish
- Allows user to select or input custom serving size
- Updates based on dish selection

#### `ServingsCountInput.jsx`

Servings count input component.

- Number input for quantity of servings consumed
- Shows predicted servings from AI
- Validates input range (0.1-10.0)

---

## Project Configuration Files

### Root Level Configuration

- `.env`: Environment variables (database credentials, API keys, CORS settings)
- `.gitignore`: Git ignore patterns for dependencies and sensitive files
- `requirements.txt`: Python dependencies for backend
- `start_app.sh`: Shell script to start both backend and frontend services
- `env_template.txt`: Template for environment variables setup

### Backend Configuration

- `run_uvicorn.py`: Uvicorn server startup script for FastAPI

### Frontend Configuration

- `package.json`: Node.js dependencies and scripts
- `package-lock.json`: Locked dependency versions
- `tailwind.config.js`: Tailwind CSS configuration
- `postcss.config.js`: PostCSS configuration for Tailwind

---

## Key Architectural Patterns

### Backend Patterns

1. **Layered Architecture**: Clear separation between API routes, business logic (services), and data access (CRUD)
2. **Dependency Injection**: Database sessions injected via FastAPI dependencies
3. **Structured Responses**: Pydantic schemas ensure type safety and validation
4. **Background Tasks**: Long-running AI analysis executed as background tasks
5. **Iteration System**: Multi-iteration analysis allowing user feedback and refinement
6. **Dual LLM Strategy**: Parallel analysis with OpenAI and Gemini for comparison

### Frontend Patterns

1. **Component Composition**: Reusable components organized by feature
2. **Context API**: Global authentication state managed via React Context
3. **Protected Routes**: Authentication guards for secure pages
4. **Polling Pattern**: Client-side polling for async analysis completion
5. **Optimistic UI**: Immediate feedback while waiting for backend operations
6. **Modular Services**: API calls abstracted into service layer

### Data Flow

1. User uploads dish image → Background analysis triggered
2. Frontend polls for analysis completion
3. AI returns dish predictions with serving sizes
4. User can adjust dish/serving selections
5. Re-analysis uses brief model to save tokens
6. New iteration created with updated analysis
7. Results stored in iterations structure for history

---

## Database Schema

### Users Table
- `id`: Primary key
- `username`: Unique username
- `hashed_password`: Bcrypt hashed password
- `role`: User role (optional)

### DishImageQuery Table
- `id`: Primary key
- `user_id`: Foreign key to Users
- `image_url`: Path to uploaded image
- `result_openai`: JSON field for OpenAI analysis
- `result_gemini`: JSON field for Gemini analysis (with iterations)
- `dish_position`: Position slot (1-5) for the date
- `created_at`: Record creation timestamp
- `target_date`: Date when dish was consumed

### Iteration Structure (within result_gemini JSON)
```json
{
  "iterations": [
    {
      "iteration_number": 1,
      "created_at": "ISO timestamp",
      "user_feedback": null,
      "metadata": {
        "selected_dish": "dish name",
        "selected_serving_size": "serving size",
        "number_of_servings": 1.0,
        "metadata_modified": false
      },
      "analysis": { /* FoodHealthAnalysis or FoodHealthAnalysisBrief */ }
    }
  ],
  "current_iteration": 1
}
```

---

## API Endpoints

### Authentication
- `POST /api/login/` - User login
- `POST /api/login/logout` - User logout

### Dashboard
- `GET /api/dashboard/?year={year}&month={month}` - Get calendar data

### Date View
- `GET /api/date/{year}/{month}/{day}` - Get dishes for date
- `POST /api/date/{year}/{month}/{day}/upload` - Upload dish image

### Item Detail
- `GET /api/item/{record_id}` - Get analysis details
- `PATCH /api/item/{record_id}/metadata` - Update dish metadata
- `POST /api/item/{record_id}/reanalyze` - Trigger re-analysis

### System
- `GET /` - Root endpoint with API info
- `GET /health` - Health check endpoint

---

## Environment Variables

### Backend (.env)
- `DB_USERNAME`: PostgreSQL username
- `DB_PASSWORD`: PostgreSQL password
- `DB_NAME`: Database name
- `DB_URL`: Database host URL
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `OPENAI_API_KEY`: OpenAI API key
- `GEMINI_API_KEY`: Google Gemini API key
- `ALLOWED_ORIGINS`: CORS allowed origins (comma-separated or "*")

### Frontend
- `REACT_APP_API_URL`: Backend API base URL

---

## Development Workflow

### Starting the Application

1. **Backend**: `python backend/run_uvicorn.py` (starts on port 2612)
2. **Frontend**: `npm start` in frontend directory (starts on port 2512)
3. **Combined**: `./start_app.sh` (starts both services)

### Image Processing Flow

1. User uploads image → Saved to `/backend/data/images/`
2. Image resized to max 384px
3. Converted to RGB JPEG format
4. Background task analyzes with Gemini
5. Results stored in `result_gemini` JSON field

### AI Analysis Models

**Initial Analysis (Full):**
- Schema: `FoodHealthAnalysis`
- Includes: `dish_predictions` with serving sizes and predicted servings
- Used for: First-time analysis of uploaded images

**Re-Analysis (Brief):**
- Schema: `FoodHealthAnalysisBrief`
- Excludes: `dish_predictions` (saves 20-30% tokens)
- Used for: Updates after user feedback on serving size/dish

---

## Deployment

### Production Considerations

1. **Security**: Update JWT secret key in production
2. **CORS**: Configure ALLOWED_ORIGINS for production domain
3. **Database**: Use production PostgreSQL instance
4. **Static Files**: Serve frontend build via backend or CDN
5. **HTTPS**: Enable secure cookies and HTTPS
6. **API Keys**: Secure OpenAI and Gemini credentials
7. **Logging**: Configure production logging levels

### Build Process

**Frontend Build:**
```bash
cd frontend
npm run build
```
Creates optimized production build in `/frontend/build/`

**Backend Deployment:**
- Uvicorn server with Gunicorn for production
- Serve static frontend files from `/frontend/build/`

---

## Testing

### Backend Tests
- Test file: `/backend/test_new_features.py`
- Tests new features and API endpoints

### Frontend Tests
- Test file: `/frontend/test_analysis_results.js`
- Tests analysis result display components
