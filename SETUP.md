# Dish Healthiness Web App - Setup Guide

## Quick Start

This project has been scaffolded and backend is complete. Frontend needs page implementations.

### 1. Environment Setup

Create `.env` file in project root:
```bash
cp env_template.txt .env
# Edit .env with your actual values
```

Required environment variables:
- `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`, `DB_URL` - PostgreSQL database
- `OPENAI_API_KEY` - OpenAI API key
- `GEMINI_API_KEY` - Google Gemini API key  
- `JWT_SECRET_KEY` - Secret for JWT tokens

### 2. Database Setup

```bash
# Create database
createdb your_db_name

# Create test user (using psql or Python script)
# Username: Alan, Password: sunny (hashed with bcrypt)
```

### 3. Backend Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Mac/Linux

# Install dependencies
pip install -r backend/src/requirements.txt
```

### 4. Frontend Setup

```bash
cd frontend
npm install
```

### 5. Running the Application

Use the provided startup script:
```bash
bash start_app.sh
```

Or manually:

**Terminal 1 - Backend:**
```bash
source venv/bin/activate
eval $(grep -v '^#' .env | xargs -0 -L1 echo export)
cd backend
python run_uvicorn.py --port 2612 --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
PORT=2512 npm start
```

Access:
- Frontend: http://localhost:2512
- Backend API: http://localhost:2612
- API Docs: http://localhost:2612/api-docs

## Implementation Status

### ✅ Backend (Complete)
All backend functionality is implemented:
- Authentication system
- Database models and CRUD
- LLM services (OpenAI & Gemini)
- API endpoints (login, dashboard, date, item)
- Image upload and background analysis

### ✅ Frontend Infrastructure (Complete)
- React app setup
- Routing configuration
- Authentication context
- API service
- Login page

### 🚧 Frontend Pages (To Complete)

Refer to `frontend/README.md` for detailed instructions.

**Pages to implement:**
1. **Dashboard** - Monthly calendar view
2. **DateView** - Daily meal view with upload
3. **Item** - Analysis results (2 columns: OpenAI & Gemini)

**Copy from reference project:**
`/Volumes/wd/projects/food_healthiness_product/frontend`

## Key Implementation Details

### Simplified from Original
- Only Flow 2 (OpenAI) and Flow 3 (Gemini)
- No AI Agent consolidation
- No database retrieval
- No Settings page
- 2-column analysis view (vs 7 in original)

### Database Schema
```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    role VARCHAR
);

-- Dish image queries
CREATE TABLE dish_image_query_prod (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) NOT NULL,
    image_url VARCHAR,
    result_openai JSONB,
    result_gemini JSONB,
    meal_type VARCHAR NOT NULL,
    created_at TIMESTAMP NOT NULL,
    target_date TIMESTAMP
);
```

### API Endpoints
- `POST /api/login/` - Login
- `POST /api/login/logout` - Logout
- `GET /api/dashboard/` - Get calendar data
- `GET /api/date/{year}/{month}/{day}` - Get date data
- `POST /api/date/{year}/{month}/{day}/upload` - Upload image
- `GET /api/item/{id}` - Get item details

## Testing

1. Start both services
2. Navigate to http://localhost:2512
3. Login with Alan/sunny
4. Test flow:
   - View dashboard calendar
   - Click a date
   - Upload dish image
   - Wait for analysis (runs in background)
   - View analysis results (OpenAI & Gemini columns)

## Troubleshooting

**Port conflicts:**
```bash
# Kill processes on ports 2512 and 2612
lsof -ti:2512 | xargs kill
lsof -ti:2612 | xargs kill
```

**Database connection:**
- Verify PostgreSQL is running
- Check `.env` database credentials
- Ensure database exists

**API keys:**
- Verify OPENAI_API_KEY and GEMINI_API_KEY are set
- Test API access separately if needed

## Next Steps

1. Complete the three frontend pages (Dashboard, DateView, Item)
2. Test the complete flow
3. Deploy to production (update CORS, secrets, database)

For detailed frontend implementation instructions, see `frontend/README.md`.

