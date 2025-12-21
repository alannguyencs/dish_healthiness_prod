# Dish Healthiness Application - Project Structure Documentation

## Project Overview

The Dish Healthiness application is a full-stack web application that analyzes food images using AI (Google Gemini) to provide nutritional insights and healthiness scores. The application implements a two-step analysis workflow:

1. **Step 1: Component Identification** - Identifies dish names and individual food components with serving size predictions
2. **Step 2: Nutritional Analysis** - Calculates detailed nutritional values and healthiness scores after user confirmation

**Technology Stack:**
- **Backend**: Python/FastAPI with PostgreSQL database
- **Frontend**: React with Tailwind CSS
- **AI/ML**: Google Gemini 2.5 Pro for vision-based food analysis
- **Authentication**: JWT-based session management

---

## Backend

The backend is a FastAPI application that handles user authentication, image processing, database operations, and AI-powered food analysis.

### Root Files (`backend/src/`)

#### main.py

Application entry point and FastAPI configuration.

**Public Functions:**
- `configure_logging()` - Sets up application logging with console and file handlers
- `create_app()` - Creates and configures the FastAPI application instance with middleware, CORS, database setup, and routing
- `root()` - Root endpoint that returns API welcome message and documentation URL
- `health()` - Health check endpoint for monitoring application status

#### models.py

SQLAlchemy ORM models for database schema.

**Public Classes:**
- `Users` - User model for authentication with username, hashed password, and role
  - `to_dict()` - Converts user instance to dictionary representation
- `DishImageQuery` - Model for storing food image analysis requests and results
  - Fields: user_id, image_url, result_openai, result_gemini, dish_position, created_at, target_date
  - `to_dict()` - Converts query instance to dictionary representation

#### schemas.py

Pydantic models for request/response validation and serialization.

**Public Classes:**
- `Token` - Authentication token response schema with access_token and token_type
- `UserBase` - Base user schema with username and role fields
- `UserCreate` - User creation schema extending UserBase with password field
- `UserResponse` - User response schema for API responses (excludes sensitive data)
- `DishImageQueryBase` - Base schema for dish image queries
- `DishImageQueryCreate` - Schema for creating new dish image queries
- `DishImageQueryResponse` - Schema for dish image query API responses
- `MetadataUpdate` - Schema for updating dish metadata (selected_dish, selected_serving_size, number_of_servings)

#### database.py

Database configuration and session management using SQLAlchemy.

**Public Functions:**
- `build_database_url()` - Constructs PostgreSQL database URL from environment variables
- `get_db()` - Provides database session via dependency injection for FastAPI endpoints

**Public Variables:**
- `engine` - SQLAlchemy database engine instance
- `SessionLocal` - SQLAlchemy session factory for creating database sessions
- `Base` - Declarative base class for ORM models

#### configs.py

Application configuration settings and constants.

**Public Classes:**
- `Settings` - Pydantic settings class managing API versioning and project configuration
  - `get_api_url()` - Returns the full API URL string
  - `get_project_identifier()` - Returns lowercase project name as identifier

**Public Variables:**
- `PROJECT_DIR` - Root project directory path
- `DATA_DIR` - Directory for data storage
- `IMAGE_DIR` - Directory for uploaded dish images
- `RESOURCE_DIR` - Directory for resource files (prompts, templates)
- `LOG_DIR` - Directory for application logs
- `TOKEN_EXPIRATION_DAYS` - JWT token expiration duration (90 days)
- `settings` - Global settings instance

#### auth.py

Authentication utilities for JWT token generation and user verification.

**Public Functions:**
- `authenticate_user(username, password)` - Authenticates user with username and password, returns User object or False
- `create_access_token(data, expires_delta)` - Creates JWT access token with optional expiration delta
- `get_current_user_from_token(token)` - Validates JWT token and returns corresponding User object
- `authenticate_user_from_request(request)` - Authenticates user from HTTP request using session cookie

**Public Variables:**
- `oauth2_scheme` - OAuth2 password bearer instance for token extraction
- `bcrypt_context` - Password hashing context using bcrypt

#### utils.py

Utility functions for common operations.

**Public Functions:**
- `format_datetime(dt)` - Formats datetime object to display string (YYYY-MM-DD HH:MM:SS)

---

### API Module (`backend/src/api/`)

API route handlers and endpoint definitions organized by functionality.

#### api_router.py

Central API router aggregating all endpoint modules.

**Purpose:** Combines all API sub-routers (login, dashboard, date, item) into a single router for the FastAPI application.

#### login.py

Authentication endpoints for user login and logout.

**Public Classes:**
- `LoginRequest` - Pydantic model for login request with username and password

**Public Functions:**
- `process_login(login_data)` - POST /api/login/ - Handles user login, creates JWT token, sets session cookie
- `logout()` - POST /api/login/logout - Handles user logout, clears session cookie

#### dashboard.py

Dashboard API endpoints for calendar view data.

**Public Functions:**
- `dashboard(request, year, month)` - GET /api/dashboard/ - Returns calendar data with user's food analyses for specified month/year
  - Builds calendar grid structure with record counts per day
  - Provides navigation data for previous/next months

#### date.py

Date-specific endpoints for viewing and uploading dishes.

**Public Functions:**
- `analyze_image_background(query_id, file_path)` - Background task performing Step 1 analysis (component identification) using Gemini
- `get_date(request, year, month, day)` - GET /api/date/{year}/{month}/{day} - Returns dish data for specific date organized by dish positions (1-5)
- `upload_dish(background_tasks, request, year, month, day, dish_position, file)` - POST /api/date/{year}/{month}/{day}/upload - Handles image upload, processes image, creates database record, triggers Step 1 analysis in background

**Private Functions:**
- `_serialize_query(query)` - Serializes query object to dictionary for JSON response

#### item.py

Individual item detail view endpoints for analysis results.

**Public Functions:**
- `item_detail(record_id, request)` - GET /api/item/{record_id} - Returns detailed analysis information for specific dish image query with iteration support
- `update_item_metadata(record_id, request, metadata)` - PATCH /api/item/{record_id}/metadata - Updates metadata for current iteration (dish name, serving size, servings count)
- `confirm_step1_and_trigger_step2(record_id, request, background_tasks, confirmation)` - POST /api/item/{record_id}/confirm-step1 - Confirms Step 1 data and triggers Step 2 nutritional analysis in background

#### item_schemas.py

Request/response schemas for item API endpoints.

**Public Classes:**
- `ComponentConfirmation` - User-confirmed component with serving size and servings count
- `Step1ConfirmationRequest` - Request body for confirming Step 1 data with selected dish name and components list

#### item_tasks.py

Background tasks for item API operations.

**Public Functions:**
- `trigger_step2_analysis_background(query_id, image_path, dish_name, components)` - Async background task running Step 2 nutritional analysis using Gemini with confirmed component data

---

### CRUD Module (`backend/src/crud/`)

Database CRUD (Create, Read, Update, Delete) operations for models.

#### crud_user.py

CRUD operations for User model.

**Public Functions:**
- `get_db_session()` - Returns new database session for CRUD operations
- `get_user_by_username(username)` - Retrieves user by username
- `get_user_by_id(user_id)` - Retrieves user by ID
- `create_user(username, hashed_password, role)` - Creates new user record
- `update_user_password(user_id, new_hashed_password)` - Updates user password
- `delete_user(user_id)` - Deletes user by ID

#### crud_food_image_query.py

CRUD operations for DishImageQuery model with iteration support.

**Public Functions:**
- `create_dish_image_query(user_id, image_url, result_openai, result_gemini, dish_position, created_at, target_date)` - Creates new dish image query record
- `get_dish_image_query_by_id(query_id)` - Retrieves query by ID
- `get_dish_image_queries_by_user(user_id)` - Retrieves all queries for specific user ordered by creation date
- `get_dish_image_queries_by_user_and_date(user_id, query_date)` - Retrieves queries for user on specific date using target_date or created_at
- `get_single_dish_by_user_date_position(user_id, query_date, dish_position)` - Retrieves single dish for user, date, and position (1-5)
- `update_dish_image_query_results(query_id, result_openai, result_gemini)` - Updates analysis results for existing query
- `delete_dish_image_query_by_id(query_id)` - Deletes query by ID
- `get_calendar_data(user_id, year, month)` - Returns record count per day for calendar month display
- `initialize_iterations_structure(analysis_result, metadata)` - Initializes iteration structure for first analysis with metadata tracking
- `get_current_iteration(record)` - Extracts current iteration data from result_gemini, handles legacy format conversion
- `add_metadata_reanalysis_iteration(query_id, analysis_result, metadata)` - Adds new iteration after metadata-based re-analysis
- `update_metadata(query_id, selected_dish, selected_serving_size, number_of_servings)` - Updates metadata for current iteration
- `get_latest_iterations(record_id, limit)` - Returns most recent iterations for display (default: 3 most recent)

---

### Service Module (`backend/src/service/llm/`)

LLM (Large Language Model) service integration for AI-powered analysis.

#### gemini_analyzer.py

Gemini API integration for dish health analysis implementing two-step workflow.

**Public Functions:**
- `enrich_result_with_metadata(result, model, analysis_start_time)` - Enriches analysis result with model metadata, pricing, and timing information
- `analyze_step1_component_identification_async(image_path, analysis_prompt, gemini_model, thinking_budget)` - Async Step 1 analysis identifying dish predictions and components with serving sizes using Gemini vision model
- `analyze_step2_nutritional_analysis_async(image_path, analysis_prompt, gemini_model, thinking_budget)` - Async Step 2 analysis calculating nutritional values and healthiness score after user confirmation

#### models.py

Pydantic models for LLM analysis data structures.

**Public Classes:**
- `DishNamePrediction` - Single dish name prediction with confidence score (0.0-1.0)
- `ComponentServingPrediction` - Serving size predictions for individual dish component with name, serving sizes list (3-5 options), and predicted servings count
- `Step1ComponentIdentification` - Step 1 complete response model containing dish predictions (1-5) and components (1-10) for user confirmation
- `Step2NutritionalAnalysis` - Step 2 complete response model with dish name, healthiness score (0-100), healthiness rationale, calories, macronutrients (fiber, carbs, protein, fat), and micronutrients list

#### prompts.py

Prompt loading and formatting utilities for LLM analysis.

**Public Functions:**
- `get_step1_component_identification_prompt()` - Loads Step 1 prompt for component identification from resources/step1_component_identification.md
- `get_step2_nutritional_analysis_prompt(dish_name, components)` - Loads and formats Step 2 prompt for nutritional analysis, injecting user-confirmed dish name and components data

#### pricing.py

LLM pricing and token calculation utilities for cost tracking.

**Public Functions:**
- `normalize_model_key(model, vendor)` - Normalizes model string to standardized pricing key
- `compute_price_usd(model, vendor, input_tokens, output_tokens, cached_input_tokens)` - Computes API cost in USD based on model and token usage (per 1M tokens)
- `extract_token_usage(response, vendor)` - Extracts input and output token counts from OpenAI or Gemini API response

**Public Variables:**
- `PRICING` - Pricing table in USD per 1 million tokens for GPT-5 and Gemini models
- `DEFAULT_PRICING` - Default pricing for unknown models

---

## Frontend

The frontend is a React single-page application providing user interface for authentication, calendar navigation, image uploads, and two-step analysis workflow.

### Root Files (`frontend/src/`)

#### index.js

React application entry point.

**Purpose:** Renders the root App component into the DOM with React.StrictMode enabled.

#### App.js

Main application component with routing configuration.

**Public Components:**
- `RedirectToDashboard` - Redirect component routing to dashboard or login based on authentication status
- `App` - Main app component configuring React Router with protected routes for dashboard, date view, and item detail pages

#### contexts/AuthContext.js

Authentication context provider for global auth state management.

**Public Functions:**
- `AuthProvider` - Context provider component managing authentication state (user, authenticated status, loading)
  - `login(username, password)` - Logs in user via API, sets user state
  - `logout()` - Logs out user via API, clears user state
- `useAuth()` - Custom hook for accessing authentication context

#### services/api.js

API service layer for backend communication using Axios.

**Public Functions:**
- `login(username, password)` - POST /api/login/ - Authenticates user
- `logout()` - POST /api/login/logout - Logs out user
- `getDashboardData(year, month)` - GET /api/dashboard/ - Fetches calendar dashboard data
- `getDateData(year, month, day)` - GET /api/date/{year}/{month}/{day} - Fetches date-specific dish data
- `uploadDishImage(year, month, day, dishPosition, file)` - POST /api/date/{year}/{month}/{day}/upload - Uploads dish image
- `getItem(recordId)` - GET /api/item/{recordId} - Fetches item detail data
- `updateItemMetadata(recordId, metadata)` - PATCH /api/item/{recordId}/metadata - Updates item metadata
- `reanalyzeItem(recordId)` - POST /api/item/{recordId}/reanalyze - Triggers re-analysis (legacy)
- `confirmStep1(recordId, confirmationData)` - POST /api/item/{recordId}/confirm-step1 - Confirms Step 1 and triggers Step 2

**Public Variables:**
- `API_BASE_URL` - Base URL for API requests (from environment or localhost:2612)

#### components/ProtectedRoute.jsx

Route protection component for authenticated pages.

**Public Components:**
- `ProtectedRoute` - Wrapper component redirecting to login if user not authenticated, shows loading state during auth check

---

### Pages (`frontend/src/pages/`)

Top-level page components for main application routes.

#### Login.jsx

Login page component.

**Public Components:**
- `Login` - Login form page with username/password inputs, handles authentication, redirects to dashboard on success

#### Dashboard.jsx

Main dashboard page displaying calendar view.

**Public Components:**
- `Dashboard` - Dashboard page orchestrating header, month navigation, and calendar grid components
  - Loads calendar data with record counts
  - Handles month navigation
  - Navigates to date view on day click

#### DateView.jsx

Date-specific view for managing meals.

**Public Components:**
- `DateView` - Date view page for specific date showing meal upload slots (1-5 dishes)
  - Loads date-specific dish data
  - Handles image uploads with file processing
  - Redirects to item detail page after upload

#### ItemV2.jsx

Item detail page implementing two-step analysis workflow.

**Public Components:**
- `ItemV2` - Item detail page displaying Step 1 component editor and Step 2 results
  - Polls for Step 1 completion every 3 seconds
  - Shows Step 1 component editor when ready for user confirmation
  - Handles Step 1 confirmation triggering Step 2
  - Polls for Step 2 completion every 3 seconds
  - Displays Step 2 nutritional results when complete
  - Allows toggling between Step 1 and Step 2 views

---

### Dashboard Components (`frontend/src/components/dashboard/`)

Components for dashboard calendar interface.

#### index.js

Central export file for dashboard components.

**Purpose:** Exports DashboardHeader, MonthNavigation, CalendarGrid, CalendarDay, and EmptyState components.

#### DashboardHeader.jsx

Dashboard header with logout functionality.

**Public Components:**
- `DashboardHeader` - Header displaying page title, username, and logout button

#### MonthNavigation.jsx

Month navigation controls.

**Public Components:**
- `MonthNavigation` - Month/year display with previous/next navigation buttons

#### CalendarGrid.jsx

Calendar table grid layout.

**Public Components:**
- `CalendarGrid` - Calendar table rendering weekday headers and day cells using CalendarDay component

#### CalendarDay.jsx

Individual calendar day cell.

**Public Components:**
- `CalendarDay` - Single day cell displaying day number, record count badge, and click handler for date navigation

#### EmptyState.jsx

Empty state message for calendar.

**Public Components:**
- `EmptyState` - Empty state component shown when user has no dish records

---

### Date View Components (`frontend/src/components/dateview/`)

Components for date-specific meal upload interface.

#### index.js

Central export file for date view components.

**Purpose:** Exports DateViewNavigation, MealUploadSlot, and MealUploadGrid components.

#### DateViewNavigation.jsx

Navigation header for date view.

**Public Components:**
- `DateViewNavigation` - Back to calendar button navigation component

#### MealUploadGrid.jsx

Grid layout for meal upload slots.

**Public Components:**
- `MealUploadGrid` - Grid container rendering 5 MealUploadSlot components for dish positions with formatted date header

#### MealUploadSlot.jsx

Individual meal upload slot.

**Public Components:**
- `MealUploadSlot` - Upload slot for single dish position showing upload button or existing dish image
  - Handles file selection and upload
  - Navigates to item detail when dish exists
  - Shows uploading state during upload

---

### Item Components (`frontend/src/components/item/`)

Components for item detail view and two-step analysis workflow.

#### index.js

Central export file for item components.

**Purpose:** Exports ItemHeader, ItemNavigation, ItemImage, ItemMetadata, AnalysisLoading, NoAnalysisAvailable, DishPredictions, ServingSizeSelector, ServingsCountInput, Step1ComponentEditor, and Step2Results components.

#### ItemHeader.jsx

Item detail page header.

**Public Components:**
- `ItemHeader` - Header with back navigation to date view and page title

#### ItemNavigation.jsx

Item page navigation controls.

**Public Components:**
- `ItemNavigation` - Back to date view navigation button

#### ItemImage.jsx

Dish image display component.

**Public Components:**
- `ItemImage` - Displays uploaded dish image with fallback for missing images

#### ItemMetadata.jsx

Record metadata display.

**Public Components:**
- `ItemMetadata` - Displays dish position, created timestamp, and target date metadata

#### AnalysisLoading.jsx

Analysis loading indicator.

**Public Components:**
- `AnalysisLoading` - Loading spinner and message shown during Step 1 or Step 2 analysis

#### NoAnalysisAvailable.jsx

Empty analysis state.

**Public Components:**
- `NoAnalysisAvailable` - Message shown when no analysis results available

#### DishPredictions.jsx

Dish name prediction selector (legacy component).

**Public Components:**
- `DishPredictions` - Dropdown selector for AI-generated dish predictions with custom input
  - Shows top 5 predictions with confidence scores
  - Allows custom dish name input
  - Auto-selects top prediction initially

#### ServingSizeSelector.jsx

Serving size selector dropdown (legacy component).

**Public Components:**
- `ServingSizeSelector` - Dropdown for dish-specific serving sizes with custom input
  - Options update dynamically based on selected dish
  - Allows custom serving size input
  - Auto-selects first option

#### ServingsCountInput.jsx

Servings count number input (legacy component).

**Public Components:**
- `ServingsCountInput` - Number input with increment/decrement controls for servings consumed
  - Validates minimum (0.1), rounds to 1 decimal place
  - Shows AI prediction badge when using predicted servings
  - Supports keyboard arrow keys for adjustment

#### Step1ComponentEditor.jsx

Step 1 component identification editor (critical two-step workflow component).

**Public Components:**
- `Step1ComponentEditor` - Interactive editor for confirming Step 1 component identification results
  - Displays overall meal name predictions (top 1-5 with confidence scores)
  - Shows individual dish components with checkboxes for selection
  - Allows selecting/deselecting AI-predicted components
  - Enables custom dish name input via collapsible dropdown
  - Provides serving size dropdown and servings count input per component
  - Supports adding manual custom dishes with serving details
  - Validates at least one component selected before confirmation
  - Triggers Step 2 nutritional analysis on confirmation
  - Displays model, cost, and timing metadata from Step 1

#### Step2Results.jsx

Step 2 nutritional analysis results display (critical two-step workflow component).

**Public Components:**
- `Step2Results` - Displays Step 2 nutritional analysis results after user confirmation
  - Shows confirmed dish name
  - Displays healthiness score (0-100) with color-coded badge (Very Healthy, Healthy, Moderate, Unhealthy, Very Unhealthy)
  - Shows healthiness score rationale explanation
  - Presents nutritional information: calories (kcal), fiber (g), carbs (g), protein (g), fat (g)
  - Lists notable micronutrients with badges
  - Displays model, cost, and timing metadata from Step 2

---

## Two-Step Analysis Workflow

The application implements a sophisticated two-step workflow for dish analysis:

### Step 1: Component Identification

1. **User uploads image** - DateView.jsx handles upload, redirects to ItemV2.jsx
2. **Backend triggers Step 1** - date.py `analyze_image_background()` runs Gemini analysis
3. **Gemini identifies components** - gemini_analyzer.py `analyze_step1_component_identification_async()` using Step1ComponentIdentification model
4. **Results stored in database** - result_gemini field with step=1, step1_data, step1_confirmed=false
5. **Frontend polls for results** - ItemV2.jsx polls every 3 seconds until Step 1 complete
6. **User reviews and confirms** - Step1ComponentEditor.jsx displays predictions, allows editing
   - Select/modify overall meal name from predictions or enter custom
   - Enable/disable individual dish components with checkboxes
   - Adjust serving sizes and servings count per component
   - Add manual custom dishes not detected by AI
7. **User confirms selections** - Triggers POST /api/item/{id}/confirm-step1

### Step 2: Nutritional Analysis

1. **Backend receives confirmation** - item.py `confirm_step1_and_trigger_step2()` handles request
2. **Step 1 marked confirmed** - Updates result_gemini with step1_confirmed=true
3. **Backend triggers Step 2** - item_tasks.py `trigger_step2_analysis_background()` runs with confirmed data
4. **Gemini calculates nutrition** - gemini_analyzer.py `analyze_step2_nutritional_analysis_async()` using Step2NutritionalAnalysis model
5. **Results stored in database** - Updates result_gemini with step=2, step2_data
6. **Frontend polls for results** - ItemV2.jsx polls every 3 seconds until Step 2 complete
7. **Display final results** - Step2Results.jsx shows nutritional information and healthiness score

### Key Design Decisions

- **Components are independent of meal name** - Users can select different components than suggested by overall meal prediction
- **Checkbox-based component selection** - All AI-detected components shown, users select which to include
- **Custom component support** - Users can add dishes not detected by AI
- **Per-component serving customization** - Each component has own serving size and servings count
- **Polling mechanism** - Frontend polls backend every 3 seconds for async analysis completion
- **Step toggling** - Users can switch between Step 1 and Step 2 views after both complete
- **Metadata tracking** - Model, cost, and timing information tracked for both steps

---

## Configuration and Deployment

### Environment Variables

**Backend (.env):**
- `DB_USERNAME` - PostgreSQL database username
- `DB_PASSWORD` - PostgreSQL database password
- `DB_NAME` - PostgreSQL database name
- `DB_URL` - PostgreSQL database host URL
- `JWT_SECRET_KEY` - Secret key for JWT token signing
- `GEMINI_API_KEY` - Google Gemini API key
- `ALLOWED_ORIGINS` - CORS allowed origins (comma-separated or "*")

**Frontend (.env):**
- `REACT_APP_API_URL` - Backend API base URL (default: http://localhost:2612)

### Directory Structure

```
backend/
  src/
    api/           - API route handlers
    crud/          - Database CRUD operations
    service/llm/   - LLM service integration
  data/
    images/        - Uploaded dish images
  resources/       - Prompt templates (.md files)
  logs/            - Application logs

frontend/
  src/
    components/    - React components
      dashboard/   - Calendar view components
      dateview/    - Meal upload components
      item/        - Analysis detail components
    pages/         - Page-level components
    contexts/      - React context providers
    services/      - API service layer
```

### Key Features

- **JWT Authentication** - Session-based authentication with 90-day token expiration
- **Image Processing** - Automatic image resizing (max 384px), RGB conversion, JPEG compression
- **Background Tasks** - Async analysis processing with FastAPI BackgroundTasks
- **Polling Architecture** - Frontend polls backend every 3 seconds for analysis completion
- **CORS Configuration** - Configurable allowed origins for cross-origin requests
- **Database Migrations** - SQLAlchemy automatic table creation on startup
- **Error Handling** - Comprehensive error handling with logging throughout application
- **Iteration Support** - Multiple analysis iterations per dish with metadata tracking (legacy feature)

---

## Development Notes

- Backend runs on port 2612 (configurable)
- Frontend runs on port 2512 in development (configurable)
- Database uses PostgreSQL 5432 default port
- Images stored locally in backend/data/images/ directory
- Prompts stored in backend/resources/ as markdown files
- Step 1 and Step 2 use same Gemini model (gemini-2.5-pro) with thinking_budget=-1
- Token usage and pricing tracked per analysis step
- All timestamps stored in UTC timezone
- Dish positions limited to 1-5 per date
- Component serving sizes provided as list of 3-5 options
- Servings count validated between 0.1 and 10.0

---

Generated on 2025-12-21
