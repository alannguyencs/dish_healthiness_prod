# Dish Healthiness Frontend

React frontend for the Dish Healthiness application.

## Setup

```bash
# Install dependencies
npm install

# Start development server (runs on port 2512)
PORT=2512 npm start
```

## Pages

- **Login** (`/login`) - User authentication
- **Dashboard** (`/dashboard`) - Monthly calendar view
- **Date View** (`/date/:year/:month/:day`) - Daily meal view with upload
- **Item** (`/item/:id`) - Dish analysis details (Flow 2 & 3)

## API Configuration

Backend API URL is configured in `src/services/api.js` as:
```javascript
export const API_BASE_URL = 'http://localhost:2612';
```

## Test Credentials
- Username: Alan
- Password: sunny

## Development Status

### ✅ Completed
- Project structure and configuration
- Authentication context
- API service
- Login page

### 🚧 To Complete
Remaining pages need to be implemented based on the reference project at `/Volumes/wd/projects/food_healthiness_product/frontend`:

1. **Dashboard Page** - Copy and adapt from reference:
   - File: `src/pages/Dashboard.jsx`
   - Shows monthly calendar with record counts
   - Reference: `/Volumes/wd/projects/food_healthiness_product/frontend/src/pages/Dashboard.jsx`

2. **DateView Page** - Copy and adapt from reference:
   - File: `src/pages/DateView.jsx`
   - Shows daily meal slots with upload functionality
   - Reference: `/Volumes/wd/projects/food_healthiness_product/frontend/src/pages/DateView.jsx`
   - Simplify: Remove summary analysis feature

3. **Item Page** - Copy and simplify from reference:
   - File: `src/pages/Item.jsx`
   - Show only 2 columns: OpenAI (Flow 2) and Gemini (Flow 3)
   - Reference: `/Volumes/wd/projects/food_healthiness_product/frontend/src/pages/Item.jsx`
   - Simplify: Remove extra columns, show only result_openai and result_gemini

## Recommended Approach

1. Copy the reference Dashboard components:
   - `src/components/dashboard/CalendarGrid.jsx`
   - `src/components/dashboard/CalendarDay.jsx`
   - `src/components/dashboard/MonthNavigation.jsx`
   - `src/components/dashboard/DashboardHeader.jsx`

2. Copy the reference DateView components:
   - `src/components/dateview/MealUploadGrid.jsx`
   - `src/components/dateview/MealImagesGrid.jsx`
   - `src/components/dateview/DateViewNavigation.jsx`
   - Remove consolidation analysis components

3. Copy and simplify the Item components:
   - `src/components/item/ItemHeader.jsx`
   - `src/components/item/ItemImage.jsx`
   - `src/components/item/AnalysisResults.jsx` (simplify to 2 columns)
   - `src/components/item/AnalysisLoading.jsx`

## Notes

- The backend supports only Flow 2 (OpenAI) and Flow 3 (Gemini)
- No Settings page is needed in this project
- API endpoints match the simplified backend structure

