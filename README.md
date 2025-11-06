# Dish Healthiness Web Application

A refactored web application for dish healthiness analysis using OpenAI and Gemini AI models.

## Overview

This project implements Flow 2 (OpenAI) and Flow 3 (Gemini) from the original `dish_healthiness` project as a modern web application with:
- **Backend**: FastAPI with PostgreSQL
- **Frontend**: React with Tailwind CSS
- **Analysis**: Parallel OpenAI and Gemini dish analysis

## Quick Start

1. **Setup Environment**
   ```bash
   cp env_template.txt .env
   # Edit .env with your credentials
   ```

2. **Install Dependencies**
   ```bash
   # Backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/src/requirements.txt
   
   # Frontend
   cd frontend
   npm install
   ```

3. **Run Application**
   ```bash
   bash start_app.sh
   ```

4. **Access**
   - Frontend: http://localhost:2512
   - Backend API: http://localhost:2612/api-docs
   - Login: Alan / sunny

## Documentation

- **[SETUP.md](./SETUP.md)** - Detailed setup instructions
- **[IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md)** - Implementation details
- **[frontend/README.md](./frontend/README.md)** - Frontend development guide

## Project Structure

```
dish_healthiness_prod/
├── backend/                 # FastAPI backend
│   ├── src/
│   │   ├── api/            # API endpoints
│   │   ├── crud/           # Database operations
│   │   ├── service/llm/    # OpenAI & Gemini services
│   │   ├── models.py       # Database models
│   │   └── main.py         # Application entry
│   ├── resources/          # Prompt templates
│   └── data/images/        # Uploaded images
├── frontend/               # React frontend
│   ├── src/
│   │   ├── pages/          # Page components
│   │   ├── components/     # Reusable components
│   │   ├── contexts/       # React contexts
│   │   └── services/       # API client
│   └── package.json
└── start_app.sh            # Startup script
```

## Implementation Status

### ✅ Complete
- Backend infrastructure (100%)
- LLM services (OpenAI & Gemini)
- API endpoints
- Authentication system
- Frontend infrastructure
- Login page

### 🚧 To Complete
Three frontend pages need implementation (copy from reference project):
1. **Dashboard** - Calendar view
2. **DateView** - Daily meal upload
3. **Item** - Analysis results (2 columns)

See `frontend/README.md` for detailed instructions.

## Key Features

- **Dual Analysis**: Parallel OpenAI (Flow 2) and Gemini (Flow 3) analysis
- **Calendar View**: Monthly overview of dish records
- **Daily View**: Meal-by-meal organization
- **Background Processing**: Async image analysis
- **Responsive UI**: Tailwind CSS styling

## API Endpoints

- `POST /api/login/` - User authentication
- `GET /api/dashboard/` - Calendar data
- `GET /api/date/{year}/{month}/{day}` - Date-specific data
- `POST /api/date/{year}/{month}/{day}/upload` - Image upload
- `GET /api/item/{id}` - Analysis results

## Technology Stack

**Backend:**
- FastAPI
- SQLAlchemy + PostgreSQL
- OpenAI API
- Google Gemini API
- Pillow (image processing)

**Frontend:**
- React 19
- React Router 7
- Axios
- Tailwind CSS

## Development

**Backend:**
```bash
cd backend
source ../venv/bin/activate
python run_uvicorn.py --port 2612 --reload
```

**Frontend:**
```bash
cd frontend
PORT=2512 npm start
```

## Configuration

**Ports:**
- Backend: 2612
- Frontend: 2512

**Environment Variables:**
- Database: `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME`, `DB_URL`
- API Keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`
- Security: `JWT_SECRET_KEY`

## Testing

1. Login with test credentials (Alan/sunny)
2. Navigate to dashboard
3. Select a date
4. Upload dish images
5. View analysis results (OpenAI & Gemini columns)

## Notes

- This is a simplified version focusing on Flow 2 & 3 only
- No AI Agent consolidation or database retrieval
- No Settings page (uses default model configurations)
- 2-column analysis view vs 7 in original project

## License

Private project

## Contact

See project documentation for details.

