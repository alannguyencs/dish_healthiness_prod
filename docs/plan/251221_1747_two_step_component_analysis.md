# Development Plan: Two-Step Component-Based Dish Analysis

**Created**: 2025-12-21 17:47
**Status**: Planning
**Estimated Complexity**: High
**Estimated Duration**: 3-5 days full-time development

---

## 1. Feature Overview

### Current System
The application currently performs a single-step analysis where:
- User uploads dish image
- Gemini AI analyzes the entire dish in one pass
- Returns dish predictions with dish-level serving sizes
- User can select dish and adjust dish-level serving sizes
- Re-analysis uses the same dish-level approach

### New Two-Step System

**STEP 1: Dish & Component Identification** (requires user verification)
1. **Dish Name Predictions**: Top 5 predicted dish names with confidence scores
   - User selects one OR provides custom dish name
2. **Major Nutrition Components**: Break dish into nutritional components
   - Example: "Beef Steak with Fries" → ["beef", "fries"]
   - Example: "Chicken Rice" → ["chicken", "rice", "vegetables"]
3. **Component-Level Serving Analysis**: FOR EACH component:
   - 3 predicted serving size options (e.g., "4 oz (113g)", "6 oz (170g)", "8 oz (227g)")
   - Predicted number of servings visible in image
   - User can select or customize per component

**STEP 2: Nutritional Analysis** (automated after Step 1 confirmation)
- Triggered automatically when user confirms Step 1 data
- Calculates nutritional values based on confirmed components and servings
- Returns: healthiness_score, healthiness_score_rationale, calories_kcal, macros, micronutrients

### User Flow
1. Upload image → Step 1 analysis begins in background
2. View Step 1 results: dish predictions + components + component serving sizes
3. User reviews and confirms/modifies:
   - Select dish (or enter custom name)
   - Review components (AI-suggested, user can add/remove/edit)
   - Adjust component serving sizes and quantities
4. Click "Confirm & Analyze Nutrition" → Step 2 triggers automatically
5. View nutritional analysis results

### Goals
- More granular control over portion estimation
- Better nutritional accuracy through component-based calculation
- Clear separation between identification and nutritional calculation
- Improved user feedback mechanism

---

## 2. Context Analysis

### Relevant Existing Components

**Backend:**
- `backend/src/service/llm/models.py` - Current `DishPrediction` and `FoodHealthAnalysis` models
- `backend/src/service/llm/gemini_analyzer.py` - Gemini API integration functions
- `backend/src/service/llm/prompts.py` - Prompt loading utilities
- `backend/src/api/date.py` - Upload endpoint with background analysis
- `backend/src/api/item.py` - Item detail, metadata update, re-analysis endpoints
- `backend/src/crud/crud_food_image_query.py` - Iteration system for tracking analysis history
- `backend/resources/food_analysis.md` - Current unified analysis prompt

**Frontend:**
- `frontend/src/pages/Item.jsx` - Main item detail page with analysis display
- `frontend/src/components/item/DishPredictions.jsx` - Dish selection component
- `frontend/src/components/item/ServingSizeSelector.jsx` - Serving size selection
- `frontend/src/components/item/ServingsCountInput.jsx` - Serving count input
- `frontend/src/services/api.js` - API service layer

**Database:**
- `DishImageQuery.result_gemini` - JSON field storing analysis results with iteration structure
- Iteration structure supports multiple analysis rounds with metadata

### How Feature Fits Architecture

The new feature extends the existing iteration system:
- **Step 1** creates iteration with `analysis_step: "component_identification"` and `step_completed: false`
- **Step 2** updates iteration with `analysis_step: "nutritional_analysis"` and `step_completed: true`
- Maintains backward compatibility - legacy data remains unchanged
- Leverages existing background task infrastructure
- Reuses iteration metadata system for component data

### Dependencies
- Existing Gemini API integration
- Current iteration system in CRUD operations
- Frontend component architecture
- Pydantic models for structured output

---

## 3. Architecture Design

### Backend Changes

#### New Pydantic Models (`backend/src/service/llm/models.py`)

```python
# Step 1: Component Identification Models

class ComponentServingSize(BaseModel):
    """Serving size option for a component"""
    serving_size: str = Field(..., description="Serving size description (e.g., '4 oz (113g)')")
    grams: int = Field(..., description="Weight in grams")

class NutritionComponent(BaseModel):
    """Individual nutrition component of a dish"""
    component_name: str = Field(..., description="Component name (e.g., 'beef', 'rice')")
    serving_sizes: List[ComponentServingSize] = Field(
        ..., min_items=3, max_items=3,
        description="3 serving size options for this component"
    )
    predicted_servings: float = Field(
        ..., gt=0,
        description="Estimated number of servings visible in image"
    )

class DishPredictionV2(BaseModel):
    """Enhanced dish prediction with confidence"""
    name: str = Field(..., description="Predicted dish name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")

class ComponentIdentificationAnalysis(BaseModel):
    """Step 1: Component identification results"""
    dish_predictions: List[DishPredictionV2] = Field(
        ..., min_items=5, max_items=5,
        description="Top 5 dish predictions"
    )
    nutrition_components: List[NutritionComponent] = Field(
        ..., min_items=1,
        description="Major nutrition components identified in dish"
    )

# Step 2: Nutritional Analysis Model

class NutritionalAnalysis(BaseModel):
    """Step 2: Nutritional analysis results"""
    dish_name: str
    related_keywords: str = ""
    healthiness_score: int
    healthiness_score_rationale: str
    calories_kcal: int
    fiber_g: int
    carbs_g: int
    protein_g: int
    fat_g: int
    micronutrients: List[str]
```

#### New LLM Prompts

**File**: `backend/resources/component_identification.md` (Step 1 prompt)
- Focuses on dish identification and component breakdown
- Requests component-level serving size analysis
- Excludes nutritional calculations

**File**: `backend/resources/nutritional_analysis.md` (Step 2 prompt)
- Takes confirmed components and serving sizes as input
- Calculates nutritional values based on components
- Excludes dish prediction tasks

#### Database Schema Updates

**No schema migration needed** - use existing JSON structure:

```python
# result_gemini JSON structure with two-step support
{
    "iterations": [
        {
            "iteration_number": 1,
            "created_at": "2025-12-21T17:47:00Z",
            "analysis_step": "component_identification",  # NEW
            "step_completed": False,                        # NEW
            "metadata": {
                "selected_dish": None,
                "components": [],  # Will be populated after user confirmation
                "metadata_modified": False
            },
            "analysis": {
                # ComponentIdentificationAnalysis data
                "dish_predictions": [...],
                "nutrition_components": [...]
            }
        },
        {
            "iteration_number": 1,  # Same iteration
            "created_at": "2025-12-21T17:48:00Z",
            "analysis_step": "nutritional_analysis",
            "step_completed": True,
            "metadata": {
                "selected_dish": "Beef Steak with Fries",
                "components": [
                    {
                        "component_name": "beef",
                        "selected_serving_size": "6 oz (170g)",
                        "number_of_servings": 1.0
                    },
                    {
                        "component_name": "fries",
                        "selected_serving_size": "1 cup (150g)",
                        "number_of_servings": 1.5
                    }
                ],
                "metadata_modified": True
            },
            "analysis": {
                # NutritionalAnalysis data
                "dish_name": "Beef Steak with Fries",
                "healthiness_score": 6,
                ...
            }
        }
    ],
    "current_iteration": 1,
    "current_step": "nutritional_analysis"  # NEW: tracks current step
}
```

#### API Endpoints

**Modified Endpoint**: `POST /api/date/{year}/{month}/{day}/upload`
- Change: Trigger Step 1 analysis instead of full analysis
- Use `ComponentIdentificationAnalysis` schema
- Set `analysis_step: "component_identification"`, `step_completed: False`

**New Endpoint**: `POST /api/item/{record_id}/confirm-step1`
```python
Request Body:
{
    "selected_dish": "Beef Steak with Fries",
    "components": [
        {
            "component_name": "beef",
            "selected_serving_size": "6 oz (170g)",
            "number_of_servings": 1.0
        },
        {
            "component_name": "fries",
            "selected_serving_size": "1 cup (150g)",
            "number_of_servings": 1.5
        }
    ]
}

Response:
{
    "success": true,
    "message": "Step 1 confirmed. Nutritional analysis in progress...",
    "iteration_number": 1
}
```

Actions:
1. Validate components data
2. Update iteration metadata with confirmed components
3. Trigger Step 2 analysis as background task
4. Return success immediately

**Modified Endpoint**: `GET /api/item/{record_id}`
- Change: Include `analysis_step` and `step_completed` in response
- Frontend uses this to determine which UI to show

**Modified Endpoint**: `POST /api/item/{record_id}/reanalyze`
- Change: Support re-running either step
- If metadata modified at Step 1 level → re-run Step 2 only
- If user requests full re-analysis → re-run both steps

### Frontend Changes

#### New Components

**File**: `frontend/src/components/item/ComponentIdentificationPanel.jsx`
```jsx
// Displays Step 1 results: dish predictions + components + serving sizes
// Props:
// - dishPredictions: array of {name, confidence}
// - components: array of {component_name, serving_sizes, predicted_servings}
// - selectedDish: string
// - selectedComponents: array of confirmed components with servings
// - onDishSelect: function
// - onComponentUpdate: function (add/remove/edit component)
// - onComponentServingChange: function
// - onConfirmStep1: function
```

**File**: `frontend/src/components/item/ComponentCard.jsx`
```jsx
// Individual component card showing:
// - Component name (editable)
// - Serving size selector (3 options)
// - Serving count input
// - Remove component button
```

**File**: `frontend/src/components/item/AddComponentButton.jsx`
```jsx
// Button to manually add custom components
// Opens modal with component name + serving size inputs
```

#### Modified Components

**File**: `frontend/src/pages/Item.jsx`
- Add state for tracking analysis step
- Conditional rendering based on `analysis_step`:
  - If Step 1 incomplete → show `ComponentIdentificationPanel`
  - If Step 2 complete → show `AnalysisResults`
  - If Step 2 in progress → show loading spinner
- Add handler for confirming Step 1
- Modify polling to check for Step 2 completion

**File**: `frontend/src/components/item/AnalysisLoading.jsx`
- Add prop to distinguish between Step 1 and Step 2 loading
- Show different messages:
  - Step 1: "Identifying dish components..."
  - Step 2: "Calculating nutritional values..."

#### API Service Updates

**File**: `frontend/src/services/api.js`
```javascript
// New method
confirmStep1: async (recordId, confirmationData) => {
    const response = await api.post(
        `/api/item/${recordId}/confirm-step1`,
        confirmationData
    );
    return response.data;
}
```

---

## 4. Implementation Plan (Full-Stack Sections)

### Section 1: Backend Data Models & Step 1 Analysis Infrastructure

**Backend Implementation:**
- Create new Pydantic models in `backend/src/service/llm/models.py`:
  - `ComponentServingSize`, `NutritionComponent`, `DishPredictionV2`, `ComponentIdentificationAnalysis`
- Create Step 1 prompt file: `backend/resources/component_identification.md`
  - Adapt from existing `food_analysis.md`
  - Focus on Step 0 (dish predictions) and component identification
  - Request component-level serving sizes
  - Remove nutritional calculation sections
- Add prompt loader in `backend/src/service/llm/prompts.py`:
  - `get_component_identification_prompt()` function
- Create Step 1 analyzer in `backend/src/service/llm/gemini_analyzer.py`:
  - `analyze_step1_component_identification_async()` function
  - Use `ComponentIdentificationAnalysis` schema for structured output
  - Similar to existing `analyze_with_gemini_async()` but different schema
- Add CRUD helper in `backend/src/crud/crud_food_image_query.py`:
  - `initialize_step1_iteration()` - creates iteration with Step 1 structure
  - `get_analysis_step()` - returns current step for an iteration

**Files to Create/Modify:**
- Backend: `backend/src/service/llm/models.py`, `backend/resources/component_identification.md`, `backend/src/service/llm/prompts.py`, `backend/src/service/llm/gemini_analyzer.py`, `backend/src/crud/crud_food_image_query.py`

**Validation & Testing:**

1. **Backend validation:**
   - Test Pydantic model serialization: Create sample `ComponentIdentificationAnalysis` objects and validate JSON output
   - Test prompt loading: Call `get_component_identification_prompt()` and verify content
   - Test Step 1 analyzer with sample image:
     ```python
     python -c "
     import asyncio
     from pathlib import Path
     from backend.src.service.llm.gemini_analyzer import analyze_step1_component_identification_async
     from backend.src.service.llm.prompts import get_component_identification_prompt

     async def test():
         result = await analyze_step1_component_identification_async(
             image_path=Path('backend/data/images/sample.jpg'),
             analysis_prompt=get_component_identification_prompt()
         )
         print(result)

     asyncio.run(test())
     "
     ```
   - Expected: JSON with 5 dish predictions and component list with serving sizes

2. **CRUD validation:**
   - Test iteration initialization with Step 1 structure
   - Verify `analysis_step` and `step_completed` fields are set correctly

**Pre-Commit Check:**
- Run `pre-commit run --all-files` to ensure code formatting and linting standards are met
- Fix any issues reported by pre-commit hooks before proceeding

**Section Complete When:**
- [ ] All Pydantic models validate correctly with sample data
- [ ] Step 1 prompt file exists and loads successfully
- [ ] Step 1 analyzer function returns valid `ComponentIdentificationAnalysis`
- [ ] CRUD functions create Step 1 iteration structure correctly
- [ ] Pre-commit checks pass without errors

---

### Section 2: Backend Step 2 Analysis & Confirmation Endpoint

**Backend Implementation:**
- Create new Pydantic model in `backend/src/service/llm/models.py`:
  - `NutritionalAnalysis` (similar to existing `FoodHealthAnalysisBrief`)
- Create Step 2 prompt file: `backend/resources/nutritional_analysis.md`
  - Adapt from existing `food_analysis.md`
  - Accept component list with servings as input context
  - Focus only on nutritional calculations (Steps 1-4 from original prompt)
  - Remove dish prediction and component identification
- Add prompt loader in `backend/src/service/llm/prompts.py`:
  - `get_nutritional_analysis_prompt()` function
- Create Step 2 analyzer in `backend/src/service/llm/gemini_analyzer.py`:
  - `analyze_step2_nutritional_async(components_data)` function
  - Takes confirmed components with serving sizes as input
  - Uses `NutritionalAnalysis` schema
  - Constructs enhanced prompt with component context
- Add CRUD helper in `backend/src/crud/crud_food_image_query.py`:
  - `update_step1_to_step2()` - updates iteration with Step 2 results
- Create new API endpoint in `backend/src/api/item.py`:
  - `POST /api/item/{record_id}/confirm-step1`
  - Request schema: `ComponentConfirmation` Pydantic model
  - Validates component data
  - Updates iteration metadata with confirmed components
  - Triggers Step 2 background task
  - Returns success immediately
- Create background task function in `backend/src/api/item.py`:
  - `analyze_step2_background(query_id, components_data)`
  - Calls `analyze_step2_nutritional_async()`
  - Updates iteration with Step 2 results

**Files to Create/Modify:**
- Backend: `backend/src/service/llm/models.py`, `backend/resources/nutritional_analysis.md`, `backend/src/service/llm/prompts.py`, `backend/src/service/llm/gemini_analyzer.py`, `backend/src/crud/crud_food_image_query.py`, `backend/src/api/item.py`, `backend/src/schemas.py`

**Validation & Testing:**

1. **Backend validation:**
   - Test Step 2 prompt generation with sample component data
   - Test Step 2 analyzer with mock components:
     ```python
     python -c "
     import asyncio
     from pathlib import Path
     from backend.src.service.llm.gemini_analyzer import analyze_step2_nutritional_async

     async def test():
         components = [
             {'component_name': 'beef', 'selected_serving_size': '6 oz (170g)', 'number_of_servings': 1.0},
             {'component_name': 'fries', 'selected_serving_size': '1 cup (150g)', 'number_of_servings': 1.5}
         ]
         result = await analyze_step2_nutritional_async(
             image_path=Path('backend/data/images/sample.jpg'),
             components_data=components,
             selected_dish='Beef Steak with Fries'
         )
         print(result)

     asyncio.run(test())
     "
     ```
   - Expected: JSON with nutritional values calculated from components

2. **API validation:**
   - Test confirm-step1 endpoint with curl:
     ```bash
     curl -X POST http://localhost:2612/api/item/123/confirm-step1 \
       -H "Content-Type: application/json" \
       -d '{
         "selected_dish": "Beef Steak with Fries",
         "components": [
           {"component_name": "beef", "selected_serving_size": "6 oz (170g)", "number_of_servings": 1.0},
           {"component_name": "fries", "selected_serving_size": "1 cup (150g)", "number_of_servings": 1.5}
         ]
       }'
     ```
   - Expected: `{"success": true, "message": "...", "iteration_number": 1}`
   - Check database to verify Step 2 background task completes

3. **Integration validation:**
   - Upload test image → verify Step 1 analysis completes
   - Confirm Step 1 via API → verify Step 2 triggers and completes
   - Check final iteration structure contains both steps

**Pre-Commit Check:**
- Run `pre-commit run --all-files` to ensure code formatting and linting standards are met
- Fix any issues reported by pre-commit hooks before proceeding

**Section Complete When:**
- [ ] Step 2 prompt generates correctly with component context
- [ ] Step 2 analyzer returns valid `NutritionalAnalysis`
- [ ] Confirm-step1 endpoint accepts requests and triggers Step 2
- [ ] Background task completes Step 2 analysis
- [ ] Database stores both Step 1 and Step 2 in iteration structure
- [ ] Pre-commit checks pass without errors

---

### Section 3: Modify Upload Flow for Step 1 Only

**Backend Implementation:**
- Modify `backend/src/api/date.py`:
  - Update `analyze_image_background()` function:
    - Call `analyze_step1_component_identification_async()` instead of full analysis
    - Use `initialize_step1_iteration()` to create Step 1 iteration
    - Set `analysis_step: "component_identification"`, `step_completed: False`
  - Keep upload endpoint logic unchanged (just triggers different background task)

**Frontend Implementation:**
- No changes needed yet (frontend already polls for analysis completion)

**Files to Create/Modify:**
- Backend: `backend/src/api/date.py`

**Validation & Testing:**

1. **Backend validation:**
   - Upload image via existing upload endpoint
   - Verify Step 1 analysis triggers in background
   - Check database record:
     ```bash
     # Check database for Step 1 structure
     psql -d dish_healthiness -c "SELECT result_gemini FROM dish_image_query_prod_dev WHERE id = <RECORD_ID>;"
     ```
   - Expected: `result_gemini` contains Step 1 iteration with `analysis_step: "component_identification"`

2. **Frontend validation:**
   - Navigate to: `http://localhost:2512/date/2025/12/21`
   - Upload test image
   - Redirects to item page
   - Expected: Loading spinner with "Identifying dish components..." message

3. **Integration validation:**
   - Complete upload flow from DateView → Item page
   - Polling should detect Step 1 completion
   - Data should show dish predictions and components (not yet nutritional values)

**Pre-Commit Check:**
- Run `pre-commit run --all-files` to ensure code formatting and linting standards are met
- Fix any issues reported by pre-commit hooks before proceeding

**Section Complete When:**
- [ ] Upload triggers Step 1 analysis (not full analysis)
- [ ] Database stores Step 1 results correctly
- [ ] Frontend polling detects Step 1 completion
- [ ] No Step 2 data exists until user confirms
- [ ] Pre-commit checks pass without errors

---

### Section 4: Frontend Component Identification UI

**Frontend Implementation:**
- Create `frontend/src/components/item/ComponentCard.jsx`:
  - Display component name (editable input)
  - Serving size selector (3 radio options)
  - Serving count number input (with +/- buttons)
  - Remove component button (red X icon)
  - Visual styling similar to existing `ServingSizeSelector`
- Create `frontend/src/components/item/AddComponentButton.jsx`:
  - "Add Component" button
  - Opens modal with:
    - Component name input
    - Serving size input (text)
    - Serving count input (number)
  - Validates and adds to component list
- Create `frontend/src/components/item/ComponentIdentificationPanel.jsx`:
  - Section header: "Step 1: Dish & Component Identification"
  - Dish predictions display (reuse existing `DishPredictions` component)
  - Components list header: "Major Nutrition Components"
  - Map components to `ComponentCard` components
  - `AddComponentButton` at bottom
  - "Confirm & Analyze Nutrition" button (disabled if no dish selected)
  - Shows "AI suggested components - please review and modify" hint
- Update `frontend/src/components/item/index.js`:
  - Export new components: `ComponentIdentificationPanel`, `ComponentCard`, `AddComponentButton`
- Add API service method in `frontend/src/services/api.js`:
  - `confirmStep1: async (recordId, confirmationData)` function

**Files to Create/Modify:**
- Frontend: `frontend/src/components/item/ComponentCard.jsx`, `frontend/src/components/item/AddComponentButton.jsx`, `frontend/src/components/item/ComponentIdentificationPanel.jsx`, `frontend/src/components/item/index.js`, `frontend/src/services/api.js`

**Validation & Testing:**

1. **Frontend validation:**
   - Start frontend dev server: `cd frontend && npm start`
   - Navigate to: `http://localhost:2512/item/123` (use existing record ID)
   - Manually modify data to simulate Step 1 state
   - Test component card interactions:
     - Edit component name
     - Select different serving sizes
     - Adjust serving counts
     - Remove components
   - Test add component modal:
     - Click "Add Component"
     - Enter custom component data
     - Verify added to list
   - Test confirm button:
     - Should be enabled when dish selected
     - Should be disabled without dish selection

2. **UI/UX validation:**
   - Verify responsive design on mobile/tablet/desktop
   - Check accessibility (keyboard navigation, screen readers)
   - Test error states (empty inputs, invalid numbers)

**Pre-Commit Check:**
- Run `pre-commit run --all-files` to ensure code formatting and linting standards are met
- Fix any issues reported by pre-commit hooks before proceeding

**Section Complete When:**
- [ ] ComponentCard renders correctly with all interactive elements
- [ ] AddComponentButton modal works for custom components
- [ ] ComponentIdentificationPanel displays Step 1 data properly
- [ ] All UI interactions work smoothly (edit, add, remove)
- [ ] Styling matches existing application design
- [ ] Pre-commit checks pass without errors

---

### Section 5: Frontend Item Page Integration & Step Flow

**Frontend Implementation:**
- Modify `frontend/src/pages/Item.jsx`:
  - Add state management for analysis steps:
    ```javascript
    const [analysisStep, setAnalysisStep] = useState(null); // 'component_identification' | 'nutritional_analysis'
    const [stepCompleted, setStepCompleted] = useState(false);
    const [componentsData, setComponentsData] = useState({ selectedDish: null, components: [] });
    ```
  - Update `loadItem()` function:
    - Extract `analysis_step` and `step_completed` from response
    - Populate `componentsData` if Step 1 exists
  - Add `handleConfirmStep1()` function:
    - Validates component data
    - Calls `apiService.confirmStep1(recordId, componentsData)`
    - Shows success message
    - Starts polling for Step 2 completion
  - Update conditional rendering logic:
    ```javascript
    if (analysisStep === 'component_identification' && !stepCompleted) {
        // Show ComponentIdentificationPanel
    } else if (analysisStep === 'nutritional_analysis' || stepCompleted) {
        // Show AnalysisResults
    }
    ```
  - Modify polling logic:
    - Poll for Step 1 completion after upload
    - Poll for Step 2 completion after Step 1 confirmation
- Modify `frontend/src/components/item/AnalysisLoading.jsx`:
  - Add `step` prop ('step1' | 'step2')
  - Show different messages based on step:
    - Step 1: "Identifying dish components and serving sizes..."
    - Step 2: "Calculating nutritional values based on your selections..."
- Update `frontend/src/components/item/AnalysisResults.jsx`:
  - No changes needed (already displays nutritional data)
  - Optionally: Add "Component Breakdown" section showing confirmed components

**Files to Create/Modify:**
- Frontend: `frontend/src/pages/Item.jsx`, `frontend/src/components/item/AnalysisLoading.jsx`, `frontend/src/components/item/AnalysisResults.jsx` (optional)

**Validation & Testing:**

1. **Frontend validation:**
   - Test full upload flow:
     - Navigate to: `http://localhost:2512/date/2025/12/21`
     - Upload test image
     - Wait for Step 1 analysis to complete
     - Expected: ComponentIdentificationPanel appears with dish predictions and components

2. **Step 1 to Step 2 flow:**
   - Review suggested components
   - Modify component serving sizes
   - Add custom component
   - Remove a component
   - Click "Confirm & Analyze Nutrition"
   - Expected: Loading spinner appears with "Calculating nutritional values..." message
   - Wait for Step 2 completion
   - Expected: AnalysisResults panel appears with nutritional data

3. **Integration validation:**
   - Complete entire user flow from upload to final results
   - Verify data persistence (refresh page mid-flow)
   - Test error handling (network failures, invalid data)
   - Verify polling stops after each step completes

**Pre-Commit Check:**
- Run `pre-commit run --all-files` to ensure code formatting and linting standards are met
- Fix any issues reported by pre-commit hooks before proceeding

**Section Complete When:**
- [ ] Item page correctly shows Step 1 UI after upload
- [ ] User can review and modify components
- [ ] Confirm button triggers Step 2 analysis
- [ ] Polling detects Step 2 completion
- [ ] Final nutritional results display correctly
- [ ] Full end-to-end flow works from upload to results
- [ ] Pre-commit checks pass without errors

---

### Section 6: Re-analysis Support & Backward Compatibility

**Backend Implementation:**
- Modify `backend/src/api/item.py`:
  - Update `reanalyze_item()` endpoint:
    - Add logic to determine which step to re-run:
      - If current step is Step 1 → re-run Step 1 only
      - If current step is Step 2 with modified metadata → re-run Step 2 only
      - If user requests full re-analysis → re-run both steps sequentially
    - Support `?full_reanalysis=true` query parameter for forcing both steps
- Add CRUD helper in `backend/src/crud/crud_food_image_query.py`:
  - `is_legacy_format()` - detects old single-step format
  - `convert_legacy_to_step2()` - converts old format to Step 2 format (for display only)
- Modify `backend/src/api/item.py`:
  - Update `item_detail()` endpoint:
    - Detect legacy format using `is_legacy_format()`
    - If legacy, convert on-the-fly to Step 2 format for consistent frontend rendering
    - Add `is_legacy: true` flag in response

**Frontend Implementation:**
- Modify `frontend/src/pages/Item.jsx`:
  - Add legacy format handling:
    - If `is_legacy: true`, skip Step 1 UI
    - Show "Legacy Analysis" badge
    - Display existing analysis results directly
    - Show "Upgrade to Component-Based Analysis" button (optional)
  - Update re-analysis button:
    - For legacy: "Re-analyze with Component Breakdown"
    - For new format: "Re-analyze Nutrition" (Step 2 only)
  - Add "Full Re-analysis" button (re-runs both steps)
- Modify `frontend/src/components/item/AnalysisResults.jsx`:
  - Add optional "Component Breakdown" section for new format
  - Shows confirmed components with serving sizes used for calculation
  - Displays both Step 1 and Step 2 data

**Files to Create/Modify:**
- Backend: `backend/src/api/item.py`, `backend/src/crud/crud_food_image_query.py`
- Frontend: `frontend/src/pages/Item.jsx`, `frontend/src/components/item/AnalysisResults.jsx`

**Validation & Testing:**

1. **Backend validation:**
   - Test with existing database record (legacy format):
     ```bash
     curl http://localhost:2612/api/item/<LEGACY_RECORD_ID>
     ```
   - Expected: Response includes `is_legacy: true` and converted data
   - Verify legacy data displays correctly in frontend

2. **Frontend validation:**
   - Navigate to legacy record: `http://localhost:2512/item/<LEGACY_RECORD_ID>`
   - Expected: Shows "Legacy Analysis" badge
   - Expected: Displays nutritional results (no Step 1 UI)
   - Click "Re-analyze with Component Breakdown"
   - Expected: Triggers full two-step analysis

3. **Re-analysis validation:**
   - For new format record:
     - Modify components in Step 1
     - Click "Re-analyze Nutrition"
     - Expected: Only Step 2 re-runs (faster, saves tokens)
   - Test "Full Re-analysis" button:
     - Expected: Both Step 1 and Step 2 re-run

4. **Integration validation:**
   - Verify legacy records display correctly
   - Verify new records use two-step flow
   - Test upgrading legacy record to new format
   - Ensure no data loss or corruption

**Pre-Commit Check:**
- Run `pre-commit run --all-files` to ensure code formatting and linting standards are met
- Fix any issues reported by pre-commit hooks before proceeding

**Section Complete When:**
- [ ] Legacy format detection works correctly
- [ ] Legacy records display without errors
- [ ] Re-analysis logic correctly determines which step(s) to run
- [ ] Frontend handles both legacy and new formats gracefully
- [ ] Component breakdown displays in analysis results
- [ ] No breaking changes to existing functionality
- [ ] Pre-commit checks pass without errors

---

## 5. Technical Considerations

### Potential Challenges

1. **Prompt Engineering Complexity**
   - **Challenge**: Splitting existing prompt into Step 1 and Step 2 while maintaining quality
   - **Mitigation**: Carefully preserve all relevant guidelines from original prompt, test extensively with diverse dish images

2. **Component Identification Accuracy**
   - **Challenge**: AI may not correctly identify all nutrition components
   - **Mitigation**: Allow users to add/remove/edit components freely, provide clear UI for component management

3. **Serving Size Standardization**
   - **Challenge**: Different components may use incompatible serving size units
   - **Mitigation**: Use Standard Serving Size Reference consistently, always include grams for calculations

4. **Two-Step Latency**
   - **Challenge**: Users must wait for two sequential AI calls
   - **Mitigation**:
     - Step 1 typically faster (no nutritional calculations)
     - Use background tasks for both steps
     - Show clear progress indicators
     - Consider caching component templates for common dishes

5. **Data Model Complexity**
   - **Challenge**: Iteration structure becomes more complex with two steps
   - **Mitigation**:
     - Clear documentation of data structure
     - Helper functions for common operations
     - Comprehensive validation

### Performance Implications

1. **Token Usage**
   - Step 1 only: ~60-70% of current full analysis tokens
   - Step 2 only (with component context): ~40-50% of current full analysis tokens
   - Total for both steps: ~10-20% more tokens than current single-step
   - Re-analysis savings: Step 2 only re-runs save ~60% tokens vs full re-analysis

2. **API Latency**
   - Step 1: 3-5 seconds (dish + component identification)
   - Step 2: 4-6 seconds (nutritional calculations)
   - Total time to complete results: 7-11 seconds (vs 6-8 seconds currently)
   - User perceives Step 1 completion faster (better UX despite total time increase)

3. **Database Storage**
   - Component data adds ~500-1000 bytes per record
   - Iteration structure adds ~200 bytes per step
   - Negligible impact on database size

### Security Considerations

1. **Input Validation**
   - Validate component names (prevent XSS, SQL injection)
   - Validate serving sizes (ensure numeric values, reasonable ranges)
   - Validate component counts (max 20 components per dish)
   - Sanitize user-entered custom data

2. **Authentication**
   - All new endpoints require authentication (reuse existing middleware)
   - Verify user owns record before allowing Step 1 confirmation

3. **Rate Limiting**
   - Consider rate limiting on confirm-step1 endpoint (prevent abuse)
   - Background task queue prevents overwhelming Gemini API

### Integration Points

1. **Existing Iteration System**
   - New two-step format extends iteration structure
   - Maintains compatibility with existing iteration methods
   - Re-uses metadata tracking for components

2. **Background Task Infrastructure**
   - Step 1 uses existing background task pattern from upload
   - Step 2 triggers via new background task after confirmation
   - Both leverage FastAPI BackgroundTasks

3. **Frontend Polling Mechanism**
   - Reuses existing polling logic for both steps
   - Polls detect `step_completed` flag to determine when to stop

4. **LLM Service Layer**
   - New analyzers follow same pattern as existing ones
   - Consistent error handling and retry logic
   - Pricing and token tracking for both steps

### Edge Cases

1. **Single Component Dishes**
   - Example: "Plain Rice" → only one component
   - UI handles gracefully, allows adding components if needed

2. **Complex Multi-Component Dishes**
   - Example: "Buddha Bowl" with 10+ components
   - UI supports scrolling list, add/remove works for any count
   - Consider pagination if more than 20 components

3. **User Adds All Custom Components**
   - AI suggests components, user removes all and adds own
   - System handles fully custom component lists

4. **User Refreshes During Step 1**
   - Step 1 data persisted to database immediately
   - Frontend reloads and shows Step 1 UI again
   - No data loss

5. **Network Failure During Step 2**
   - Background task fails, Step 2 not completed
   - User can retry via "Retry Analysis" button
   - Error logged for debugging

6. **Concurrent Step 1 Confirmations**
   - If user clicks "Confirm" multiple times rapidly
   - Backend uses transaction locks to prevent duplicate Step 2 tasks
   - Idempotency ensures safe retry

---

## 6. Data Structure Examples

### Step 1 Analysis Result (ComponentIdentificationAnalysis)

```json
{
  "dish_predictions": [
    {
      "name": "Beef Steak with French Fries",
      "confidence": 0.92
    },
    {
      "name": "Grilled Steak and Fries",
      "confidence": 0.85
    },
    {
      "name": "Steak Frites",
      "confidence": 0.78
    },
    {
      "name": "Sirloin Steak Dinner",
      "confidence": 0.65
    },
    {
      "name": "Beef Plate with Sides",
      "confidence": 0.58
    }
  ],
  "nutrition_components": [
    {
      "component_name": "beef steak",
      "serving_sizes": [
        {
          "serving_size": "4 oz (113g)",
          "grams": 113
        },
        {
          "serving_size": "6 oz (170g)",
          "grams": 170
        },
        {
          "serving_size": "8 oz (227g)",
          "grams": 227
        }
      ],
      "predicted_servings": 1.5
    },
    {
      "component_name": "french fries",
      "serving_sizes": [
        {
          "serving_size": "1/2 cup (75g)",
          "grams": 75
        },
        {
          "serving_size": "1 cup (150g)",
          "grams": 150
        },
        {
          "serving_size": "1.5 cups (225g)",
          "grams": 225
        }
      ],
      "predicted_servings": 1.0
    },
    {
      "component_name": "vegetables (broccoli)",
      "serving_sizes": [
        {
          "serving_size": "1/2 cup (50g)",
          "grams": 50
        },
        {
          "serving_size": "1 cup (100g)",
          "grams": 100
        },
        {
          "serving_size": "1.5 cups (150g)",
          "grams": 150
        }
      ],
      "predicted_servings": 0.5
    }
  ]
}
```

### User Confirmation Data (Request to confirm-step1)

```json
{
  "selected_dish": "Beef Steak with French Fries",
  "components": [
    {
      "component_name": "beef steak",
      "selected_serving_size": "6 oz (170g)",
      "number_of_servings": 1.0
    },
    {
      "component_name": "french fries",
      "selected_serving_size": "1 cup (150g)",
      "number_of_servings": 1.5
    },
    {
      "component_name": "vegetables (broccoli)",
      "selected_serving_size": "1 cup (100g)",
      "number_of_servings": 0.5
    }
  ]
}
```

### Step 2 Analysis Result (NutritionalAnalysis)

```json
{
  "dish_name": "Beef Steak with French Fries",
  "related_keywords": "beef, steak, protein, french fries, potatoes, carbs, broccoli, vegetables, grilled, fried, western, dinner",
  "healthiness_score": 6,
  "healthiness_score_rationale": "This dish provides a good source of protein from the beef steak and includes vegetables (broccoli), which adds fiber and micronutrients. However, the french fries are deep-fried and add significant calories and saturated fat. The portion of vegetables is relatively small compared to the steak and fries. The cooking method for the steak (grilled) is health-conscious, but the fries lower the overall healthiness. A more balanced plate would have more vegetables and fewer fried items.",
  "calories_kcal": 720,
  "fiber_g": 6,
  "carbs_g": 48,
  "protein_g": 52,
  "fat_g": 32,
  "micronutrients": [
    "Iron",
    "Zinc",
    "Vitamin B12",
    "Vitamin C",
    "Vitamin K",
    "Potassium"
  ]
}
```

### Complete Iteration Structure (Database)

```json
{
  "iterations": [
    {
      "iteration_number": 1,
      "created_at": "2025-12-21T17:47:30Z",
      "analysis_step": "component_identification",
      "step_completed": true,
      "metadata": {
        "selected_dish": "Beef Steak with French Fries",
        "components": [
          {
            "component_name": "beef steak",
            "selected_serving_size": "6 oz (170g)",
            "number_of_servings": 1.0
          },
          {
            "component_name": "french fries",
            "selected_serving_size": "1 cup (150g)",
            "number_of_servings": 1.5
          },
          {
            "component_name": "vegetables (broccoli)",
            "selected_serving_size": "1 cup (100g)",
            "number_of_servings": 0.5
          }
        ],
        "metadata_modified": true
      },
      "analysis": {
        "dish_predictions": [
          {
            "name": "Beef Steak with French Fries",
            "confidence": 0.92
          }
        ],
        "nutrition_components": [
          {
            "component_name": "beef steak",
            "serving_sizes": [
              {"serving_size": "4 oz (113g)", "grams": 113},
              {"serving_size": "6 oz (170g)", "grams": 170},
              {"serving_size": "8 oz (227g)", "grams": 227}
            ],
            "predicted_servings": 1.5
          }
        ]
      }
    },
    {
      "iteration_number": 1,
      "created_at": "2025-12-21T17:48:45Z",
      "analysis_step": "nutritional_analysis",
      "step_completed": true,
      "metadata": {
        "selected_dish": "Beef Steak with French Fries",
        "components": [
          {
            "component_name": "beef steak",
            "selected_serving_size": "6 oz (170g)",
            "number_of_servings": 1.0
          },
          {
            "component_name": "french fries",
            "selected_serving_size": "1 cup (150g)",
            "number_of_servings": 1.5
          },
          {
            "component_name": "vegetables (broccoli)",
            "selected_serving_size": "1 cup (100g)",
            "number_of_servings": 0.5
          }
        ],
        "metadata_modified": true
      },
      "analysis": {
        "dish_name": "Beef Steak with French Fries",
        "related_keywords": "beef, steak, protein, french fries, potatoes, carbs, broccoli, vegetables, grilled, fried, western, dinner",
        "healthiness_score": 6,
        "healthiness_score_rationale": "This dish provides a good source of protein...",
        "calories_kcal": 720,
        "fiber_g": 6,
        "carbs_g": 48,
        "protein_g": 52,
        "fat_g": 32,
        "micronutrients": ["Iron", "Zinc", "Vitamin B12", "Vitamin C", "Vitamin K", "Potassium"],
        "model": "gemini-2.5-pro",
        "input_token": 1250,
        "output_token": 420,
        "price_usd": 0.0042,
        "analysis_time": 4.523
      }
    }
  ],
  "current_iteration": 1,
  "current_step": "nutritional_analysis"
}
```

---

## 7. Migration Strategy

### No Database Schema Migration Needed

Per user requirements, **no migration of existing data is required**. The system will support both formats:

1. **Legacy Format** (existing records):
   - Single-step analysis with dish-level serving sizes
   - `result_gemini` contains direct `FoodHealthAnalysis` data
   - No `iterations` structure or `analysis_step` field

2. **New Format** (new uploads):
   - Two-step analysis with component-level serving sizes
   - `result_gemini` contains iterations with `analysis_step` and `step_completed`
   - Each iteration has either Step 1 or Step 2 data

### Backward Compatibility Strategy

**Backend:**
- `is_legacy_format(record)` helper function detects old format
- `convert_legacy_to_step2(record)` converts on-the-fly for display
- API responses include `is_legacy: true/false` flag
- Re-analysis of legacy records triggers full two-step flow (upgrades to new format)

**Frontend:**
- Conditional rendering based on `is_legacy` flag
- Legacy records show nutritional results directly (no Step 1 UI)
- "Upgrade to Component-Based Analysis" button for legacy records
- New records use full two-step UI

### Gradual Migration (Optional)

If user wants to gradually migrate legacy data:

1. Add "Upgrade" button to legacy records
2. User clicks → triggers full two-step re-analysis
3. Legacy data replaced with new format
4. User can review and confirm components before Step 2

This is **optional** and can be implemented post-launch.

---

## 8. API Endpoint Specifications

### Modified: Upload Dish Image

**Endpoint**: `POST /api/date/{year}/{month}/{day}/upload`

**Changes**:
- Background task calls `analyze_step1_component_identification_async()` instead of full analysis
- Creates Step 1 iteration with `analysis_step: "component_identification"`, `step_completed: False`

**Request**: (unchanged)
```
Content-Type: multipart/form-data
- dish_position: int (1-5)
- file: image file
```

**Response**: (unchanged)
```json
{
  "success": true,
  "message": "Image uploaded. Analysis in progress...",
  "query": {
    "id": 123,
    "image_url": "/images/251221_174730_dish1.jpg",
    "dish_position": 1,
    "created_at": "2025-12-21T17:47:30Z",
    "target_date": "2025-12-21T00:00:00Z",
    "result_gemini": null
  }
}
```

---

### New: Confirm Step 1 and Trigger Step 2

**Endpoint**: `POST /api/item/{record_id}/confirm-step1`

**Authentication**: Required (JWT cookie)

**Request Body**:
```json
{
  "selected_dish": "Beef Steak with French Fries",
  "components": [
    {
      "component_name": "beef steak",
      "selected_serving_size": "6 oz (170g)",
      "number_of_servings": 1.0
    },
    {
      "component_name": "french fries",
      "selected_serving_size": "1 cup (150g)",
      "number_of_servings": 1.5
    }
  ]
}
```

**Validation Rules**:
- `selected_dish`: required, non-empty string, max 200 chars
- `components`: required, array with 1-20 items
- Each component:
  - `component_name`: required, non-empty string, max 100 chars
  - `selected_serving_size`: required, non-empty string, max 50 chars
  - `number_of_servings`: required, float > 0, max 10.0

**Response** (success):
```json
{
  "success": true,
  "message": "Step 1 confirmed. Nutritional analysis in progress...",
  "iteration_number": 1
}
```

**Response** (error - validation failure):
```json
{
  "detail": "Invalid component data: number_of_servings must be greater than 0"
}
```
Status: 400

**Response** (error - not found):
```json
{
  "detail": "Record not found"
}
```
Status: 404

**Response** (error - unauthorized):
```json
{
  "detail": "Not authenticated"
}
```
Status: 401

**Side Effects**:
- Updates iteration metadata with confirmed components
- Marks Step 1 as completed
- Triggers Step 2 background task
- Returns immediately (doesn't wait for Step 2)

---

### Modified: Get Item Details

**Endpoint**: `GET /api/item/{record_id}`

**Changes**:
- Adds `analysis_step`, `step_completed`, `is_legacy` fields to response
- For legacy records, sets `is_legacy: true` and converts to Step 2 format

**Response** (new format - Step 1 in progress):
```json
{
  "id": 123,
  "image_url": "/images/251221_174730_dish1.jpg",
  "dish_position": 1,
  "created_at": "2025-12-21T17:47:30Z",
  "target_date": "2025-12-21T00:00:00Z",
  "result_gemini": {
    "iterations": [...],
    "current_iteration": 1,
    "current_step": "component_identification"
  },
  "has_gemini_result": true,
  "iterations": [...],
  "current_iteration": 1,
  "total_iterations": 1,
  "analysis_step": "component_identification",
  "step_completed": true,
  "is_legacy": false
}
```

**Response** (new format - Step 2 complete):
```json
{
  "id": 123,
  "image_url": "/images/251221_174730_dish1.jpg",
  "dish_position": 1,
  "created_at": "2025-12-21T17:47:30Z",
  "target_date": "2025-12-21T00:00:00Z",
  "result_gemini": {
    "iterations": [...],
    "current_iteration": 1,
    "current_step": "nutritional_analysis"
  },
  "has_gemini_result": true,
  "iterations": [...],
  "current_iteration": 1,
  "total_iterations": 2,
  "analysis_step": "nutritional_analysis",
  "step_completed": true,
  "is_legacy": false
}
```

**Response** (legacy format):
```json
{
  "id": 100,
  "image_url": "/images/older_upload.jpg",
  "dish_position": 1,
  "created_at": "2025-12-15T10:30:00Z",
  "target_date": "2025-12-15T00:00:00Z",
  "result_gemini": {
    "dish_name": "Chicken Rice",
    "healthiness_score": 7,
    ...
  },
  "has_gemini_result": true,
  "iterations": [
    {
      "iteration_number": 1,
      "created_at": "2025-12-15T10:30:00Z",
      "analysis_step": "nutritional_analysis",
      "step_completed": true,
      "metadata": {...},
      "analysis": {...}
    }
  ],
  "current_iteration": 1,
  "total_iterations": 1,
  "analysis_step": "nutritional_analysis",
  "step_completed": true,
  "is_legacy": true
}
```

---

### Modified: Re-analyze Item

**Endpoint**: `POST /api/item/{record_id}/reanalyze`

**Changes**:
- Supports `?full_reanalysis=true` query parameter
- For new format: default behavior re-runs Step 2 only
- For legacy format: triggers full two-step re-analysis

**Query Parameters**:
- `full_reanalysis` (optional, boolean): If true, re-runs both Step 1 and Step 2

**Request**: (no body)

**Response** (Step 2 only re-analysis):
```json
{
  "success": true,
  "iteration_id": 123,
  "iteration_number": 1,
  "analysis_data": {
    "dish_name": "Beef Steak with French Fries",
    "healthiness_score": 6,
    ...
  },
  "created_at": "2025-12-21T17:50:00Z"
}
```

**Response** (full re-analysis):
```json
{
  "success": true,
  "message": "Full re-analysis initiated. Step 1 in progress...",
  "iteration_number": 2
}
```

---

## 9. UI/UX Flow Description

### Upload Flow (New)

1. **DateView Page** (`/date/2025/12/21`)
   - User clicks upload slot
   - Selects image file
   - Image uploads → redirects to Item page

2. **Item Page - Step 1 Loading** (`/item/123`)
   - Shows uploaded image
   - Displays loading spinner: "Identifying dish components and serving sizes..."
   - Frontend polls every 3 seconds

3. **Item Page - Step 1 Results**
   - Loading spinner disappears
   - **ComponentIdentificationPanel** appears with:
     - Header: "Step 1: Dish & Component Identification"
     - **Dish Predictions Section**:
       - Shows 5 dish predictions with confidence scores
       - Radio buttons for selection
       - "Other (specify)" option with text input
     - **Components Section**:
       - Header: "Major Nutrition Components" with subtitle "AI suggested components - please review and modify"
       - List of **ComponentCard** items:
         - Component name (editable text input)
         - Serving size selector (3 radio options with descriptions)
         - Serving count input (number with +/- buttons)
         - Remove button (red X icon)
       - **AddComponentButton** at bottom ("+ Add Custom Component")
     - **Confirm Button**:
       - "Confirm & Analyze Nutrition" (blue, prominent)
       - Disabled if no dish selected
       - Shows validation errors if component data invalid

4. **User Interaction**
   - User reviews dish predictions → selects "Beef Steak with French Fries"
   - Reviews components:
     - "beef steak" → changes serving size from "4 oz" to "6 oz", keeps servings at 1.0
     - "french fries" → changes servings from 1.0 to 1.5
     - "vegetables (broccoli)" → keeps defaults
   - Clicks "Confirm & Analyze Nutrition"

5. **Item Page - Step 2 Loading**
   - ComponentIdentificationPanel fades out
   - Loading spinner appears: "Calculating nutritional values based on your selections..."
   - Shows selected components summary (read-only)
   - Frontend polls for Step 2 completion

6. **Item Page - Step 2 Results**
   - Loading spinner disappears
   - **AnalysisResults** panel appears:
     - Healthiness score with visual indicator
     - Nutritional information (calories, macros, micronutrients)
     - Healthiness rationale
     - **Component Breakdown** section (new):
       - Shows confirmed components with serving sizes
       - "Based on: 6 oz beef steak (1.0 serving), 1 cup french fries (1.5 servings), 1 cup broccoli (0.5 servings)"
   - "Re-analyze Nutrition" button (re-runs Step 2 only)
   - "Full Re-analysis" button (re-runs both steps)

### Legacy Record Flow

1. **Item Page - Legacy Record** (`/item/100`)
   - Shows uploaded image
   - "Legacy Analysis" badge in corner
   - **AnalysisResults** panel appears immediately (no Step 1 UI)
   - Shows existing nutritional data
   - "Upgrade to Component-Based Analysis" button
   - If clicked → triggers full two-step re-analysis

### Re-analysis Flow

1. **User Modifies Components**
   - From Step 2 results, user clicks "Edit Components" button
   - Returns to Step 1 UI (ComponentIdentificationPanel)
   - Shows previously confirmed components
   - User modifies component serving sizes
   - Clicks "Confirm & Analyze Nutrition"
   - Only Step 2 re-runs (faster, saves tokens)

2. **User Requests Full Re-analysis**
   - From Step 2 results, user clicks "Full Re-analysis" button
   - Both Step 1 and Step 2 re-run
   - Useful if dish identification was wrong

---

## 10. Testing & Validation Strategy

### Unit Tests

**Backend:**
- `test_component_identification_model.py`:
  - Test Pydantic model validation
  - Test serialization/deserialization
  - Test edge cases (empty components, invalid servings)

- `test_nutritional_analysis_model.py`:
  - Test Pydantic model validation
  - Test edge cases (negative values, missing fields)

- `test_crud_iterations.py`:
  - Test `initialize_step1_iteration()`
  - Test `update_step1_to_step2()`
  - Test `is_legacy_format()`
  - Test `convert_legacy_to_step2()`

**Frontend:**
- `ComponentCard.test.jsx`:
  - Test component rendering
  - Test serving size selection
  - Test serving count input
  - Test remove component

- `ComponentIdentificationPanel.test.jsx`:
  - Test dish prediction display
  - Test component list rendering
  - Test add component functionality
  - Test confirm button state

### Integration Tests

**Backend:**
- `test_upload_to_step1.py`:
  - Upload image → verify Step 1 analysis triggered
  - Poll endpoint → verify Step 1 results structure
  - Verify database contains Step 1 iteration

- `test_confirm_step1_to_step2.py`:
  - Confirm Step 1 → verify Step 2 triggered
  - Poll endpoint → verify Step 2 results structure
  - Verify database contains both Step 1 and Step 2

- `test_reanalysis_flow.py`:
  - Test Step 2 only re-analysis
  - Test full re-analysis (both steps)
  - Test legacy record upgrade

**Frontend:**
- `Item.integration.test.jsx`:
  - Test full upload flow from DateView to Item page
  - Test Step 1 UI display
  - Test Step 1 confirmation
  - Test Step 2 results display
  - Test re-analysis flows

### End-to-End Tests

**Scenarios:**

1. **Happy Path - New Upload**
   - Login → Dashboard → DateView
   - Upload beef steak image
   - Wait for Step 1 → review components
   - Confirm → wait for Step 2
   - Verify nutritional results

2. **Modify Components Path**
   - Upload chicken rice image
   - Step 1 completes with 3 components
   - User removes 1 component, adds custom component
   - Adjusts serving sizes
   - Confirms → Step 2 completes with modified data

3. **Legacy Record Path**
   - Navigate to old record
   - Verify displays correctly with "Legacy Analysis" badge
   - Click "Upgrade" → full re-analysis
   - Verify new two-step flow

4. **Re-analysis Path**
   - Complete analysis → Step 2 results shown
   - Click "Edit Components"
   - Modify serving sizes
   - Confirm → only Step 2 re-runs
   - Verify updated nutritional values

### Edge Case Tests

1. **Single Component Dish**
   - Upload plain rice image
   - Step 1 returns only 1 component
   - Verify UI handles gracefully
   - User can add more components if desired

2. **Many Components Dish**
   - Upload complex buddha bowl image
   - Step 1 returns 8+ components
   - Verify UI scrolls properly
   - All components selectable/editable

3. **User Adds All Custom Components**
   - Upload image → Step 1 completes
   - User removes all AI-suggested components
   - Adds 3 custom components manually
   - Confirms → Step 2 completes with custom data

4. **Network Failure During Step 2**
   - Confirm Step 1 → simulate network failure
   - Verify error message shown
   - "Retry Analysis" button appears
   - Retry succeeds

5. **Concurrent Confirmations**
   - Rapidly click "Confirm" button multiple times
   - Verify only one Step 2 task triggered
   - No duplicate results

### Performance Tests

1. **Token Usage Comparison**
   - Run 10 analyses with old single-step approach
   - Run 10 analyses with new two-step approach
   - Compare total token usage
   - Expected: ~10-20% increase for full flow, ~60% savings for re-analysis

2. **Latency Comparison**
   - Measure time from upload to Step 1 completion
   - Measure time from Step 1 confirmation to Step 2 completion
   - Total time vs old single-step time
   - Expected: Slightly longer total time, but better perceived UX

3. **Database Performance**
   - Insert 1000 records with new two-step format
   - Query performance for item detail endpoint
   - Verify no significant degradation

### User Acceptance Tests

1. **Usability Testing**
   - 5 users test upload flow
   - Measure time to complete Step 1 confirmation
   - Collect feedback on component editing UI
   - Identify pain points

2. **Accuracy Testing**
   - Upload 50 diverse dish images
   - Review Step 1 component identification accuracy
   - Adjust components as needed
   - Compare Step 2 nutritional results with reference values
   - Target: >80% component identification accuracy

---

## 11. Deployment Plan

### Pre-Deployment Checklist

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] End-to-end tests pass for critical flows
- [ ] Code review completed
- [ ] Documentation updated (API docs, user guide)
- [ ] Database backup created
- [ ] Rollback plan documented

### Deployment Steps

1. **Backend Deployment**
   - Deploy new backend code with two-step analysis
   - Verify new endpoints accessible
   - Test with curl/Postman
   - Monitor logs for errors

2. **Frontend Deployment**
   - Build frontend: `cd frontend && npm run build`
   - Deploy build to static server
   - Clear browser caches
   - Verify new UI loads

3. **Smoke Tests**
   - Upload test image → verify Step 1 completes
   - Confirm Step 1 → verify Step 2 completes
   - View legacy record → verify displays correctly

4. **Monitoring**
   - Monitor API error rates
   - Monitor Gemini API token usage
   - Monitor database query performance
   - Watch for user-reported issues

### Rollback Plan

If critical issues discovered:

1. **Immediate Actions**
   - Revert backend to previous version
   - Revert frontend to previous version
   - Notify users of temporary service disruption

2. **Data Preservation**
   - New two-step records remain in database (no data loss)
   - Users can still view legacy records
   - Re-deploy when issues resolved

### Post-Deployment

1. **Monitor for 24 hours**
   - Check error logs hourly
   - Monitor user feedback channels
   - Track API usage and costs

2. **Gradual Rollout** (optional)
   - Enable two-step flow for 10% of users first
   - Monitor for issues
   - Increase to 50%, then 100%

---

## 12. Estimated Timeline

### Section-by-Section Breakdown

| Section | Tasks | Estimated Time |
|---------|-------|----------------|
| Section 1 | Backend data models & Step 1 infrastructure | 6-8 hours |
| Section 2 | Backend Step 2 analysis & confirmation endpoint | 6-8 hours |
| Section 3 | Modify upload flow for Step 1 only | 2-3 hours |
| Section 4 | Frontend Component Identification UI | 8-10 hours |
| Section 5 | Frontend Item page integration & step flow | 6-8 hours |
| Section 6 | Re-analysis support & backward compatibility | 4-6 hours |
| **Testing** | Unit, integration, E2E tests | 8-10 hours |
| **Documentation** | API docs, user guide, code comments | 3-4 hours |
| **Total** | | **43-57 hours** |

### Recommended Schedule (3-5 days)

**Day 1**: Sections 1-2 (Backend infrastructure)
- Morning: Section 1 (models, prompts, Step 1 analyzer)
- Afternoon: Section 2 (Step 2 analyzer, confirmation endpoint)
- End of day: Backend validation tests pass

**Day 2**: Section 3 + Section 4 (Upload flow + Frontend UI)
- Morning: Section 3 (modify upload flow)
- Afternoon: Section 4 (Component Identification UI components)
- End of day: Step 1 UI renders correctly

**Day 3**: Section 5 (Frontend integration)
- Full day: Item page integration, step flow logic
- End of day: Full upload-to-results flow works

**Day 4**: Section 6 + Testing
- Morning: Section 6 (re-analysis, backward compatibility)
- Afternoon: Integration tests, E2E tests
- End of day: All tests pass

**Day 5**: Polish, documentation, deployment
- Morning: Code review, bug fixes
- Afternoon: Documentation, deployment
- End of day: Feature deployed to production

---

## 13. Success Metrics

### Functional Metrics

- [ ] 100% of new uploads use two-step analysis flow
- [ ] Step 1 completion rate >95% (users confirm/modify components)
- [ ] Step 2 completion rate >95% (successful nutritional analysis)
- [ ] Legacy records display without errors
- [ ] Re-analysis success rate >95%

### Performance Metrics

- [ ] Step 1 average latency <5 seconds
- [ ] Step 2 average latency <6 seconds
- [ ] Total token usage increase <20% vs old system
- [ ] Re-analysis token savings >50% (Step 2 only)
- [ ] Database query time <200ms for item detail

### User Experience Metrics

- [ ] User satisfaction score >4/5 for component editing UI
- [ ] >70% of users modify at least 1 component
- [ ] Average time to confirm Step 1 <60 seconds
- [ ] <5% users abandon during Step 1
- [ ] Component identification accuracy >80% (per user feedback)

### Quality Metrics

- [ ] Zero critical bugs in production
- [ ] <2% API error rate
- [ ] Code coverage >80% for new code
- [ ] All pre-commit checks pass
- [ ] No security vulnerabilities detected

---

## 14. Future Enhancements (Post-Launch)

### Phase 2 Features

1. **Component Templates**
   - Save common component combinations for quick selection
   - Example: "Chicken Rice Bowl" template = chicken + rice + vegetables
   - Reduces user effort for frequent dishes

2. **Smart Component Suggestions**
   - ML model learns user's component editing patterns
   - Suggests personalized components based on history
   - Improves accuracy over time

3. **Batch Component Editing**
   - Select multiple components at once
   - Apply same serving size adjustment to all
   - Useful for symmetric dishes

4. **Component Nutritional Breakdown**
   - Show per-component nutritional values
   - "Beef: 300 kcal, Fries: 350 kcal, Broccoli: 25 kcal"
   - Helps users understand contribution of each component

5. **Component-Level Micronutrients**
   - AI identifies micronutrients per component
   - "Beef provides Iron, B12; Broccoli provides Vitamin C, K"

### Phase 3 Features

1. **Legacy Data Migration Tool**
   - Admin panel to bulk-upgrade legacy records
   - User-initiated migration for individual records
   - Progress tracking and rollback

2. **Component Image Segmentation**
   - AI highlights each component in uploaded image
   - Visual confirmation of component identification
   - User can click regions to add/remove components

3. **Multi-Language Component Names**
   - Support for non-English component names
   - Localized serving size units
   - International cuisine support

---

## 15. Questions & Assumptions

### Assumptions Made

1. **User Behavior**:
   - Users will review and confirm components (not skip)
   - Most users will modify at least 1 component
   - Users prefer granular control over simplicity

2. **Technical**:
   - Gemini API can reliably identify 1-10 components per dish
   - Component serving sizes from Standard Reference are sufficient
   - Existing iteration system can support two-step structure

3. **Business**:
   - Token cost increase <20% is acceptable
   - Improved accuracy justifies additional user interaction
   - No strict deadline for deployment

### Open Questions

1. **Should we limit the number of components per dish?**
   - Current plan: no hard limit, but UI supports up to 20
   - Consideration: Very complex dishes may overwhelm users

2. **Should we auto-populate custom serving sizes from user input?**
   - If user types "200g", should we auto-convert to oz/cups?
   - Consideration: May reduce user effort but adds complexity

3. **Should we support component categories/tags?**
   - Example: Tag "beef" as "protein", "rice" as "carb"
   - Consideration: May help with nutritional balance visualization

---

## 16. Appendix

### Reference Links

- **FastAPI Background Tasks**: https://fastapi.tiangolo.com/tutorial/background-tasks/
- **Pydantic Models**: https://docs.pydantic.dev/latest/
- **Gemini API Structured Output**: https://ai.google.dev/gemini-api/docs/structured-output
- **React Component Patterns**: https://react.dev/learn/thinking-in-react
- **PostgreSQL JSON Functions**: https://www.postgresql.org/docs/current/functions-json.html

### Glossary

- **Component**: A visually or functionally separable part of a dish (e.g., "beef", "rice")
- **Step 1**: Component identification phase (dish predictions + component breakdown)
- **Step 2**: Nutritional analysis phase (calories, macros, healthiness score)
- **Legacy Format**: Old single-step analysis records without component structure
- **Iteration**: A version of analysis results (supports re-analysis history)
- **Serving Size**: Standardized unit for measuring food quantity (e.g., "4 oz", "1 cup")
- **Predicted Servings**: AI's estimate of how many standard servings are visible in image

### Code Examples

See data structure examples in Section 6 above.

---

**END OF DEVELOPMENT PLAN**
