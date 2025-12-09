# User Feedback Feature Implementation Plan

**Project**: Dish Healthiness Production
**Plan ID**: 251209_2236_user_feedback_implementation
**Created**: December 9, 2025
**Target**: Gemini-only implementation with metadata-based feedback

---

## Executive Summary

This plan details the implementation of a comprehensive user feedback system for dish healthiness analysis, enabling users to:
1. Review and override AI-generated dish predictions with top 5 suggestions
2. Select or customize serving sizes specific to each dish
3. Specify number of servings consumed (0.1 - 10.0)
4. Trigger re-analysis with updated metadata using optimized two-model approach

The implementation follows the proven architecture from the `food_healthiness` reference project, adapted for the current `dish_healthiness_prod` codebase with Gemini-only support.

---

## Current State Analysis

### Existing Architecture

**Backend (`/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/`):**
- **Database Model**: `DishImageQuery` with `result_gemini` JSON field
- **LLM Service**: Gemini-only analyzer with `FoodHealthAnalysis` Pydantic model
- **CRUD Operations**: Basic create, read, update, delete for dish queries
- **API Endpoints**:
  - `GET /api/item/{record_id}` - Get item details
  - Limited to read-only operations, no feedback or re-analysis support
- **Current Analysis Model**:
  ```python
  class FoodHealthAnalysis(BaseModel):
      dish_name: str
      related_keywords: str
      healthiness_score: int
      healthiness_score_rationale: str
      calories_kcal: int
      fiber_g: int
      carbs_g: int
      protein_g: int
      fat_g: int
      micronutrients: List[str]
  ```

**Frontend (`/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/`):**
- **Item Page**: Basic display of analysis results with polling
- **Components**: `ItemHeader`, `ItemImage`, `ItemMetadata`, `AnalysisResults`, `AnalysisLoading`
- **API Service**: Limited to `getItem(recordId)` - no feedback endpoints
- **State Management**: Simple local state, no metadata tracking

### Gap Analysis

**Missing Backend Components:**
1. Extended Pydantic models for dish predictions and serving sizes
2. Two-model approach (`FoodHealthAnalysis` vs `FoodHealthAnalysisBrief`)
3. Iteration management system in `result_gemini` JSON structure
4. CRUD functions for metadata updates and iteration handling
5. API endpoints for metadata update and re-analysis
6. Enhanced prompt engineering for dish predictions and serving sizes

**Missing Frontend Components:**
1. `DishPredictions.jsx` - Dropdown with AI predictions and custom input
2. `ServingSizeSelector.jsx` - Dynamic serving size options
3. `ServingsCountInput.jsx` - Number input with +/- controls
4. Metadata state management in Item page
5. "Update Food Analysis" button and workflow
6. Iteration display and navigation UI

**Missing Integration:**
- Metadata flow from frontend to backend
- Re-analysis trigger mechanism
- Iteration persistence and recovery
- Two-model switching logic (full vs brief)

---

## Architecture Design

### Backend Changes

#### 1. Enhanced Pydantic Models

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/models.py`

**New Models**:
```python
from typing import List, Optional
from pydantic import BaseModel, Field

class DishPrediction(BaseModel):
    """Single dish prediction with confidence and serving sizes."""
    name: str = Field(..., description="Predicted dish name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    serving_sizes: List[str] = Field(
        default_factory=list,
        description="Top 3 serving size options for this dish"
    )

class FoodHealthAnalysis(BaseModel):
    """Full analysis model with dish predictions (initial analysis)."""
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
    dish_predictions: Optional[List[DishPrediction]] = None  # NEW

class FoodHealthAnalysisBrief(BaseModel):
    """Brief analysis model without predictions (re-analysis)."""
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
    # No dish_predictions - lighter model for re-analysis
```

#### 2. Iteration Data Structure

**Storage**: Within `result_gemini` JSON field in `DishImageQuery` table

**Structure**:
```json
{
  "iterations": [
    {
      "iteration_number": 1,
      "created_at": "2025-12-09T22:36:00Z",
      "user_feedback": null,
      "metadata": {
        "selected_dish": "Grilled Chicken Breast",
        "selected_serving_size": "1 piece (85g)",
        "number_of_servings": 1.0,
        "metadata_modified": false
      },
      "analysis": {
        "dish_name": "Grilled Chicken Breast",
        "healthiness_score": 8,
        "dish_predictions": [
          {
            "name": "Grilled Chicken Breast",
            "confidence": 0.95,
            "serving_sizes": ["1 piece (85g)", "100g", "1 cup (140g)"]
          },
          {
            "name": "Baked Chicken",
            "confidence": 0.85,
            "serving_sizes": ["1 piece (100g)", "150g", "1 serving"]
          }
        ],
        "calories_kcal": 165,
        "protein_g": 31,
        "fat_g": 3.6
      }
    }
  ],
  "current_iteration": 1
}
```

#### 3. Enhanced CRUD Operations

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/crud/crud_food_image_query.py`

**New Functions**:
```python
def initialize_iterations_structure(
    analysis_result: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Initialize iteration structure for first analysis."""

def get_current_iteration(record: DishImageQuery) -> Optional[Dict[str, Any]]:
    """Get the current iteration from result_gemini."""

def add_metadata_reanalysis_iteration(
    query_id: int,
    analysis_result: Dict[str, Any],
    metadata: Dict[str, Any]
) -> DishImageQuery:
    """Add new iteration after metadata-based re-analysis."""

def update_metadata(
    query_id: int,
    selected_dish: str,
    selected_serving_size: str,
    number_of_servings: float
) -> bool:
    """Update metadata for current iteration."""

def get_latest_iterations(
    record_id: int,
    limit: int = 3
) -> List[Dict[str, Any]]:
    """Get most recent iterations for display."""
```

#### 4. Enhanced Prompt Engineering

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/resources/food_analysis.md`

**Additions to Prompt**:
- Instructions for generating top 5 dish predictions with confidence scores
- Guidelines for providing 3 dish-specific serving sizes per prediction
- Output format requirements for `dish_predictions` array

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/resources/food_analysis_brief.md` (NEW)

- Simplified prompt for re-analysis without dish prediction generation
- Instructions to incorporate user-selected metadata in analysis
- Lighter output schema without `dish_predictions`

#### 5. Gemini Analyzer Enhancement

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/gemini_analyzer.py`

**New Function**:
```python
async def analyze_with_gemini_brief_async(
    image_path: Path,
    analysis_prompt: str,
    selected_dish: str,
    selected_serving_size: str,
    number_of_servings: float,
    gemini_model: str = "gemini-2.5-pro",
    thinking_budget: int = -1
) -> Dict[str, Any]:
    """
    Analyze with metadata context using FoodHealthAnalysisBrief schema.

    Constructs enhanced prompt incorporating user-selected metadata:

    [Original Prompt]

    USER-SELECTED METADATA:
    - Dish: {selected_dish}
    - Serving Size: {selected_serving_size}
    - Number of Servings: {number_of_servings}

    Please provide updated analysis based on this metadata.
    Use FoodHealthAnalysisBrief format (no dish_predictions).
    """
```

**Modifications to existing function**:
- Update `response_schema` to use `FoodHealthAnalysis` (with predictions)
- Ensure dish predictions are properly extracted and stored

#### 6. New API Endpoints

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/api/item.py`

**New Endpoints**:

```python
@router.patch("/{record_id}/metadata")
async def update_item_metadata(
    record_id: int,
    request: Request,
    metadata: MetadataUpdate
) -> JSONResponse:
    """
    Update metadata (dish, serving size, servings count) for current iteration.

    Request body:
    {
        "selected_dish": "Grilled Chicken Breast",
        "selected_serving_size": "1 piece (85g)",
        "number_of_servings": 1.5
    }

    Response:
    {
        "success": true,
        "message": "Metadata updated successfully",
        "metadata_modified": true
    }
    """

@router.post("/{record_id}/reanalyze")
async def reanalyze_item(
    record_id: int,
    request: Request
) -> JSONResponse:
    """
    Trigger re-analysis with current metadata using FoodHealthAnalysisBrief.

    Response:
    {
        "success": true,
        "iteration_id": 2,
        "iteration_number": 2,
        "analysis_data": {...},
        "created_at": "2025-12-09T22:40:00Z"
    }
    """
```

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/schemas.py`

**New Schema**:
```python
class MetadataUpdate(BaseModel):
    """Schema for metadata update request."""
    selected_dish: str
    selected_serving_size: str
    number_of_servings: float = Field(..., ge=0.1, le=10.0)
```

#### 7. Enhanced GET Item Endpoint

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/api/item.py`

**Modify existing endpoint**:
```python
@router.get("/{record_id}")
async def item_detail(record_id: int, request: Request) -> JSONResponse:
    """
    Enhanced response structure:
    {
        "id": 123,
        "image_url": "/images/...",
        "dish_position": 1,
        "created_at": "...",
        "target_date": "...",
        "current_iteration": 2,
        "total_iterations": 2,
        "iterations": [
            {
                "iteration_number": 1,
                "created_at": "...",
                "metadata": {...},
                "analysis": {...}
            },
            {
                "iteration_number": 2,
                "created_at": "...",
                "metadata": {...},
                "analysis": {...}
            }
        ],
        "has_gemini_result": true
    }
    """
```

### Frontend Changes

#### 1. New Components

**Component**: `DishPredictions.jsx`
**Location**: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/DishPredictions.jsx`

**Features**:
- Dropdown displaying current dish with confidence badge
- List of top 5 AI predictions with rankings and confidence bars
- "AI Top Choice" badge for highest confidence
- "User Selected" badge when user overrides
- Custom dish name input field
- Checkmark icon on selected option

**Props**:
```javascript
{
  predictions: Array,      // AI predictions [{name, confidence, serving_sizes}]
  selectedDish: string,    // Currently selected dish
  onDishSelect: Function,  // Callback(dishName)
  disabled: boolean        // Disable during re-analysis
}
```

**Component**: `ServingSizeSelector.jsx`
**Location**: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/ServingSizeSelector.jsx`

**Features**:
- Dynamic dropdown with dish-specific serving sizes
- Label showing context: "Portion sizes for {dishName}"
- Custom serving size input
- "Custom" badge for user-entered sizes
- Auto-update when dish selection changes

**Props**:
```javascript
{
  options: Array,          // Available serving sizes for selected dish
  selectedOption: string,  // Currently selected size
  onSelect: Function,      // Callback(servingSize)
  disabled: boolean,
  dishName: string         // For label context
}
```

**Component**: `ServingsCountInput.jsx`
**Location**: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/ServingsCountInput.jsx`

**Features**:
- Number input with increment/decrement buttons
- Step: 0.5, Min: 0.1, Max: 10.0
- Direct keyboard input with validation
- Auto-correction on blur
- Label: "Number of Servings"
- Helper text: "How many servings did you eat?"

**Props**:
```javascript
{
  value: number,           // Current count
  onChange: Function,      // Callback(count)
  disabled: boolean,
  min: number,            // Default: 0.1
  max: number,            // Default: 10.0
  step: number            // Default: 0.5
}
```

#### 2. Enhanced Item Page

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/pages/Item.jsx`

**New State**:
```javascript
const [metadata, setMetadata] = useState({
    selectedDish: null,
    selectedServingSize: null,
    numberOfServings: 1.0,
    servingOptions: [],
    metadataModified: false
});
const [savingMetadata, setSavingMetadata] = useState(false);
const [metadataSaved, setMetadataSaved] = useState(false);
const [reanalyzing, setReanalyzing] = useState(false);
const [iterations, setIterations] = useState([]);
const [currentIteration, setCurrentIteration] = useState(null);
```

**New Event Handlers**:
```javascript
const handleDishSelect = (dishName) => {
    // Find prediction, update serving options, set metadata_modified
}

const handleServingSizeSelect = (size) => {
    // Update metadata, set metadata_modified
}

const handleServingsCountChange = (count) => {
    // Update metadata, set metadata_modified
}

const handleUpdateAnalysis = async () => {
    // Save metadata via PATCH /api/item/{id}/metadata
    // Trigger re-analysis via POST /api/item/{id}/reanalyze
    // Reload item to get new iteration
}
```

**New UI Section**:
```jsx
{/* Metadata Panel - Only shown when predictions exist */}
{currentIteration?.analysis?.dish_predictions?.length > 0 && (
    <div className="metadata-panel bg-gray-50 p-6 rounded-lg mb-6">
        <h2 className="text-xl font-semibold mb-4">
            Adjust Dish Information
        </h2>

        <DishPredictions
            predictions={currentIteration.analysis.dish_predictions}
            selectedDish={metadata.selectedDish}
            onDishSelect={handleDishSelect}
            disabled={reanalyzing}
        />

        <ServingSizeSelector
            options={metadata.servingOptions}
            selectedOption={metadata.selectedServingSize}
            onSelect={handleServingSizeSelect}
            disabled={reanalyzing}
            dishName={metadata.selectedDish}
        />

        <ServingsCountInput
            value={metadata.numberOfServings}
            onChange={handleServingsCountChange}
            disabled={reanalyzing}
        />

        {metadata.metadataModified && (
            <button
                onClick={handleUpdateAnalysis}
                disabled={savingMetadata || reanalyzing}
                className="mt-4 w-full bg-blue-600 text-white py-3 px-4
                          rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
            >
                {reanalyzing ? 'Updating Analysis...' : 'Update Food Analysis'}
            </button>
        )}
    </div>
)}
```

#### 3. Enhanced API Service

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/services/api.js`

**New Methods**:
```javascript
// Update metadata
updateItemMetadata: async (recordId, metadata) => {
    const response = await api.patch(`/api/item/${recordId}/metadata`, metadata);
    return response.data;
},

// Trigger re-analysis
reanalyzeItem: async (recordId) => {
    const response = await api.post(`/api/item/${recordId}/reanalyze`);
    return response.data;
},
```

#### 4. Updated AnalysisResults Component

**File**: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/AnalysisResults.jsx`

**Modifications**:
- Add iteration navigation tabs if multiple iterations exist
- Display metadata context: "Analyzed with: {dish}, {serving} × {count}"
- Show "Initial Analysis" vs "Re-analysis #N" labels
- Highlight when metadata was modified in iteration

---

## Implementation Plan

### Section 1: Backend Foundation - Data Models and Iteration System

**Backend Implementation:**
- Extend `FoodHealthAnalysis` Pydantic model with `dish_predictions: Optional[List[DishPrediction]]`
- Create new `DishPrediction` Pydantic model with `name`, `confidence`, `serving_sizes` fields
- Create new `FoodHealthAnalysisBrief` Pydantic model (same fields minus `dish_predictions`)
- Add CRUD functions for iteration management:
  - `initialize_iterations_structure()` - Create initial iteration wrapper
  - `get_current_iteration()` - Extract current iteration from result_gemini
  - `add_metadata_reanalysis_iteration()` - Append new iteration
  - `update_metadata()` - Update metadata in current iteration
  - `get_latest_iterations()` - Get recent iterations for display
- Create `MetadataUpdate` Pydantic schema for API validation

**Files to Create/Modify:**
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/models.py`
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/crud/crud_food_image_query.py`
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/schemas.py`

**Validation & Testing:**

1. **Backend validation:**
   - Test Pydantic model validation:
     ```python
     # Test DishPrediction
     pred = DishPrediction(
         name="Grilled Chicken",
         confidence=0.95,
         serving_sizes=["1 piece (85g)", "100g"]
     )
     assert pred.confidence >= 0.0 and pred.confidence <= 1.0

     # Test FoodHealthAnalysis with predictions
     analysis = FoodHealthAnalysis(
         dish_name="Test",
         healthiness_score=8,
         dish_predictions=[pred],
         ...
     )
     assert analysis.dish_predictions is not None

     # Test FoodHealthAnalysisBrief (no predictions)
     brief = FoodHealthAnalysisBrief(
         dish_name="Test",
         healthiness_score=8,
         ...
     )
     assert not hasattr(brief, 'dish_predictions')
     ```

   - Test CRUD functions with mock data:
     ```python
     # Create test record
     record = create_dish_image_query(user_id=1)

     # Initialize iterations
     analysis = {"dish_name": "Test", "healthiness_score": 8}
     result = initialize_iterations_structure(analysis)
     assert "iterations" in result
     assert result["current_iteration"] == 1

     # Update metadata
     success = update_metadata(
         record.id,
         "Grilled Chicken",
         "1 piece (85g)",
         1.5
     )
     assert success == True

     # Get current iteration
     iteration = get_current_iteration(record)
     assert iteration["metadata"]["number_of_servings"] == 1.5
     ```

2. **Integration validation:**
   - Verify JSON structure in database matches expected format
   - Check that iterations array persists correctly
   - Confirm metadata updates don't corrupt existing data

**Section Complete When:**
- [ ] All Pydantic models validate correctly with test data
- [ ] CRUD functions create proper iteration structure in result_gemini
- [ ] Metadata updates persist to database without errors
- [ ] get_current_iteration() returns correct iteration object

---

### Section 2: Enhanced Prompt Engineering and LLM Integration

**Backend Implementation:**
- Update existing analysis prompt (`food_analysis.md`) to include:
  - Instructions for generating top 5 dish predictions
  - Confidence score calculation guidelines (0.0 - 1.0)
  - Requirements for 3 dish-specific serving sizes per prediction
  - Output format example showing dish_predictions array
- Create new brief analysis prompt (`food_analysis_brief.md`):
  - Same core analysis instructions
  - Explicit exclusion of dish prediction generation
  - Instructions to incorporate user metadata context
  - Lighter output requirements
- Modify `analyze_with_gemini_async()` in `gemini_analyzer.py`:
  - Update `response_schema` parameter to use `FoodHealthAnalysis`
  - Ensure dish_predictions are properly extracted from response
  - Validate that serving_sizes array is populated
- Create new function `analyze_with_gemini_brief_async()`:
  - Accept metadata parameters (selected_dish, serving_size, servings_count)
  - Construct enhanced prompt with metadata context section
  - Use `FoodHealthAnalysisBrief` as response_schema
  - Return analysis without predictions

**Files to Create/Modify:**
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/resources/food_analysis.md`
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/resources/food_analysis_brief.md` (NEW)
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/gemini_analyzer.py`
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/prompts.py`

**Validation & Testing:**

1. **Backend validation:**
   - Test full analysis prompt generates predictions:
     ```bash
     # Use test image
     python -m pytest tests/test_gemini_full_analysis.py
     # Expected: Response includes dish_predictions array with 5 items
     # Each prediction has name, confidence (0.0-1.0), and 3 serving_sizes
     ```

   - Test brief analysis prompt respects metadata:
     ```python
     result = await analyze_with_gemini_brief_async(
         image_path=test_image,
         analysis_prompt=get_brief_prompt(),
         selected_dish="Grilled Chicken Breast",
         selected_serving_size="1 piece (85g)",
         number_of_servings=1.5
     )
     assert "dish_predictions" not in result
     assert result["dish_name"] == "Grilled Chicken Breast"
     ```

   - Verify token usage difference:
     ```
     Full analysis: ~3500 input tokens, ~1200 output tokens
     Brief analysis: ~2800 input tokens, ~900 output tokens
     Expected savings: 20-30% per re-analysis
     ```

2. **Integration validation:**
   - Upload test dish image via existing upload endpoint
   - Verify analysis result includes dish_predictions array
   - Check that confidence scores are ranked (highest first)
   - Confirm serving_sizes are dish-appropriate (not generic)

**Section Complete When:**
- [ ] Full analysis returns 5 dish predictions with confidence scores
- [ ] Each prediction includes 3 dish-specific serving sizes
- [ ] Brief analysis excludes predictions and is 20-30% smaller
- [ ] Metadata context appears in brief analysis results

---

### Section 3: Backend API Endpoints - Metadata Update and Re-analysis

**Backend Implementation:**
- Add `PATCH /api/item/{record_id}/metadata` endpoint in `item.py`:
  - Authenticate user and verify record ownership
  - Validate metadata using `MetadataUpdate` schema
  - Call `update_metadata()` CRUD function
  - Set `metadata_modified: true` flag
  - Return success response with updated metadata state
- Add `POST /api/item/{record_id}/reanalyze` endpoint in `item.py`:
  - Authenticate user and verify record ownership
  - Get current iteration to extract metadata
  - Load original image from disk
  - Call `analyze_with_gemini_brief_async()` with metadata
  - Call `add_metadata_reanalysis_iteration()` to store new iteration
  - Return new iteration data with iteration_number
- Enhance existing `GET /api/item/{record_id}` endpoint:
  - Extract iterations array from result_gemini
  - Calculate current_iteration and total_iterations
  - Return structured response with iterations list
  - Include metadata for each iteration
- Add route registration in `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/api/api_router.py`

**Files to Create/Modify:**
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/api/item.py`
- Backend: `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/api/api_router.py`

**Validation & Testing:**

1. **Backend validation:**
   - Test metadata update endpoint:
     ```bash
     curl -X PATCH http://localhost:2612/api/item/123/metadata \
       -H "Content-Type: application/json" \
       -d '{
         "selected_dish": "Grilled Chicken Breast",
         "selected_serving_size": "1 piece (85g)",
         "number_of_servings": 1.5
       }'
     # Expected: {"success": true, "metadata_modified": true}
     ```

   - Test re-analysis endpoint:
     ```bash
     curl -X POST http://localhost:2612/api/item/123/reanalyze
     # Expected: {
     #   "success": true,
     #   "iteration_number": 2,
     #   "analysis_data": {...}
     # }
     ```

   - Test enhanced GET endpoint:
     ```bash
     curl http://localhost:2612/api/item/123
     # Expected response includes:
     # - iterations: [...]
     # - current_iteration: 2
     # - total_iterations: 2
     ```

   - Verify validation errors:
     ```bash
     # Invalid servings count
     curl -X PATCH http://localhost:2612/api/item/123/metadata \
       -d '{"number_of_servings": 15.0}'
     # Expected: 400 error "must be between 0.1 and 10.0"
     ```

2. **Integration validation:**
   - Complete workflow: Upload image → Get predictions → Update metadata → Re-analyze
   - Verify second iteration stored with correct iteration_number
   - Check that re-analysis uses brief model (no predictions in iteration 2)
   - Confirm metadata persists across requests

**Section Complete When:**
- [ ] PATCH /metadata endpoint updates metadata and sets modified flag
- [ ] POST /reanalyze endpoint creates new iteration with brief analysis
- [ ] GET /item endpoint returns iterations array with all metadata
- [ ] Validation errors return appropriate HTTP status codes
- [ ] Complete workflow from upload to re-analysis succeeds

---

### Section 4: Frontend Components - Dish Predictions Selector

**Frontend Implementation:**
- Create `DishPredictions.jsx` component:
  - Dropdown trigger showing selected dish with confidence badge
  - "AI Top Choice" badge for highest confidence prediction
  - "User Selected" badge when user overrides
  - Predictions list with rankings (#1, #2, etc.)
  - Confidence percentage and visual bar for each prediction
  - Checkmark icon on selected option
  - "Or Enter Custom Dish" section with text input
  - "Custom" badge for user-entered dishes
  - Keyboard navigation (Tab, Enter, Escape, Arrow keys)
  - Click-outside-to-close functionality
- Add component exports to `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/index.js`
- Create CSS module or Tailwind classes for styling:
  - Dropdown container with shadow and rounded corners
  - Confidence bar with gradient (blue for high, yellow for medium)
  - Badge styles for "AI Top Choice", "User Selected", "Custom"
  - Hover and active states for options

**Files to Create/Modify:**
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/DishPredictions.jsx`
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/index.js`
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/DishPredictions.module.css` (optional)

**Validation & Testing:**

1. **Frontend validation:**
   - Navigate to item page with mock data:
     ```javascript
     const mockPredictions = [
       {name: "Grilled Chicken", confidence: 0.95, serving_sizes: ["1 piece (85g)"]},
       {name: "Baked Chicken", confidence: 0.85, serving_sizes: ["100g"]},
       {name: "Chicken Breast", confidence: 0.75, serving_sizes: ["1 serving"]}
     ];
     ```

   - Test interactions:
     - Click dropdown → Opens predictions list
     - Click prediction option → Closes dropdown, updates selected dish
     - Type custom dish name → Enter key → Adds custom dish
     - Click outside → Closes dropdown
     - Press Escape → Closes dropdown

   - Verify badges display correctly:
     - Top prediction shows "AI Top Choice" badge
     - Selected prediction shows checkmark
     - Custom dish shows "Custom" badge
     - User-selected non-top prediction shows "User Selected"

2. **Integration validation:**
   - Integration with Item page:
     ```jsx
     <DishPredictions
       predictions={mockPredictions}
       selectedDish={metadata.selectedDish}
       onDishSelect={handleDishSelect}
       disabled={false}
     />
     ```
   - Verify onDishSelect callback fires with correct dish name
   - Check that disabled state prevents interactions

**Section Complete When:**
- [ ] Dropdown displays predictions list correctly
- [ ] Badges show appropriate labels (AI Top Choice, User Selected, Custom)
- [ ] Confidence bars render with correct percentages
- [ ] Custom dish input works and persists selection
- [ ] Component disabled state works during re-analysis
- [ ] Keyboard navigation works (Tab, Enter, Escape)

---

### Section 5: Frontend Components - Serving Size and Servings Count

**Frontend Implementation:**
- Create `ServingSizeSelector.jsx` component:
  - Dynamic dropdown with dish-specific serving sizes
  - Label: "Portion sizes for {dishName}"
  - Options change when parent updates options prop
  - Custom serving size input section
  - "Custom" badge for user-entered sizes
  - Checkmark on selected option
  - Keyboard navigation support
  - Auto-select first option when dish changes
- Create `ServingsCountInput.jsx` component:
  - Number input field with +/- buttons
  - Label: "Number of Servings"
  - Helper text: "How many servings did you eat?"
  - Increment button (step 0.5)
  - Decrement button (step 0.5, min 0.1)
  - Direct keyboard input with validation
  - Auto-correct on blur (clamp to 0.1 - 10.0)
  - Round to 1 decimal place
  - Disabled state styling
- Add component exports to `index.js`
- Create shared styles or Tailwind classes

**Files to Create/Modify:**
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/ServingSizeSelector.jsx`
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/ServingsCountInput.jsx`
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/index.js`

**Validation & Testing:**

1. **Frontend validation:**
   - Test ServingSizeSelector:
     ```javascript
     const mockOptions = ["1 piece (85g)", "100g", "1 cup (140g)"];
     <ServingSizeSelector
       options={mockOptions}
       selectedOption="1 piece (85g)"
       onSelect={(size) => console.log(size)}
       dishName="Grilled Chicken Breast"
     />
     ```
     - Verify dropdown shows all options
     - Click option → Fires onSelect callback
     - Add custom size → Shows "Custom" badge
     - Options update when prop changes

   - Test ServingsCountInput:
     ```javascript
     <ServingsCountInput
       value={1.5}
       onChange={(count) => console.log(count)}
       min={0.1}
       max={10.0}
       step={0.5}
     />
     ```
     - Click + button → Increases by 0.5
     - Click - button → Decreases by 0.5
     - Type "2.3" → Blur → Rounds to 2.3
     - Type "15" → Blur → Clamps to 10.0
     - Type "0" → Blur → Clamps to 0.1
     - Arrow Up key → Increases
     - Arrow Down key → Decreases

2. **Integration validation:**
   - Test together in Item page:
     - Select dish → Serving size options update automatically
     - Change serving size → onSelect callback fires
     - Change servings count → onChange callback fires
     - All components respect disabled state

**Section Complete When:**
- [ ] ServingSizeSelector displays dish-specific options correctly
- [ ] Options update dynamically when dish selection changes
- [ ] Custom serving size input works and shows "Custom" badge
- [ ] ServingsCountInput validates range (0.1 - 10.0)
- [ ] Increment/decrement buttons work with 0.5 step
- [ ] Direct input auto-corrects and rounds to 1 decimal
- [ ] Both components respect disabled state

---

### Section 6: Frontend Integration - Item Page State Management and Workflow

**Frontend Implementation:**
- Enhance `Item.jsx` page component:
  - Add metadata state object with all fields
  - Add reanalyzing, savingMetadata, metadataSaved state flags
  - Add iterations and currentIteration state
  - Implement handleDishSelect event handler:
    - Find selected prediction from predictions array
    - Extract serving_sizes for the selected dish
    - Update metadata state with new dish, serving options, first serving size
    - Set metadataModified to true
  - Implement handleServingSizeSelect event handler:
    - Update selectedServingSize in metadata
    - Set metadataModified to true
  - Implement handleServingsCountChange event handler:
    - Update numberOfServings in metadata
    - Set metadataModified to true
  - Implement handleUpdateAnalysis event handler:
    - Set savingMetadata and reanalyzing flags
    - Call apiService.updateItemMetadata(recordId, metadata)
    - Call apiService.reanalyzeItem(recordId)
    - Reload item to get new iteration
    - Reset metadataModified flag
    - Show success toast/notification
  - Enhance loadItem function:
    - Extract iterations array from response
    - Set currentIteration to latest iteration
    - Initialize metadata from current iteration
    - Auto-select top prediction on first load
- Add metadata panel UI section between ItemMetadata and AnalysisResults
- Render three feedback components with proper props
- Add "Update Food Analysis" button (conditional on metadataModified)
- Add loading states and disabled props during re-analysis

**Files to Create/Modify:**
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/pages/Item.jsx`

**Validation & Testing:**

1. **Frontend validation:**
   - Load item page with predictions:
     - Verify top prediction auto-selected
     - Check first serving size auto-selected
     - Confirm servings count defaults to 1.0

   - Test metadata selection flow:
     - Select different dish → Serving options update
     - Select different serving size → Metadata marked modified
     - Change servings count → Metadata marked modified
     - "Update Food Analysis" button appears

   - Test update analysis workflow:
     - Click "Update Food Analysis"
     - Button shows "Updating Analysis..." loading text
     - Components become disabled
     - After completion, new iteration appears
     - Button hides (metadataModified reset to false)

2. **Integration validation:**
   - End-to-end flow:
     ```
     1. Upload dish image → Navigate to item page
     2. Wait for analysis → Predictions appear
     3. Top prediction auto-selected
     4. Change dish to 2nd prediction
     5. Change serving size to "100g"
     6. Change servings count to 1.5
     7. Click "Update Food Analysis"
     8. Wait for re-analysis
     9. New iteration displays with updated values
     10. Compare iteration 1 vs iteration 2 results
     ```
   - Verify metadata persists in database
   - Check that re-analysis reflects metadata changes
   - Confirm iteration navigation works if multiple iterations exist

**Section Complete When:**
- [ ] Metadata state initializes correctly from current iteration
- [ ] Top prediction auto-selected on page load
- [ ] All three event handlers update state correctly
- [ ] metadataModified flag toggles "Update Food Analysis" button
- [ ] handleUpdateAnalysis completes full workflow without errors
- [ ] Loading states prevent user interaction during processing
- [ ] New iteration appears after successful re-analysis
- [ ] UI updates reflect new analysis data

---

### Section 7: Frontend API Integration and Enhanced Components

**Frontend Implementation:**
- Enhance `apiService` in `api.js`:
  - Add `updateItemMetadata(recordId, metadata)` method
  - Add `reanalyzeItem(recordId)` method
  - Add error handling and retry logic
- Update `AnalysisResults.jsx` component:
  - Add iteration navigation tabs (if multiple iterations)
  - Display iteration metadata context
  - Show "Analyzed with: {dish}, {serving} × {count}" label
  - Add "Initial Analysis" vs "Re-analysis #N" badges
  - Highlight when metadata was modified
  - Support switching between iterations
- Create iteration comparison view (optional enhancement):
  - Side-by-side comparison of iterations
  - Highlight differences in healthiness score, calories, macros
- Add error handling and user feedback:
  - Toast notifications for success/failure
  - Error messages for network failures
  - Validation error display
  - Retry button on failure

**Files to Create/Modify:**
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/services/api.js`
- Frontend: `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/AnalysisResults.jsx`

**Validation & Testing:**

1. **Frontend validation:**
   - Test API methods:
     ```javascript
     // Update metadata
     const result = await apiService.updateItemMetadata(123, {
       selected_dish: "Grilled Chicken",
       selected_serving_size: "1 piece (85g)",
       number_of_servings: 1.5
     });
     // Expected: {success: true, metadata_modified: true}

     // Re-analyze
     const reanalysis = await apiService.reanalyzeItem(123);
     // Expected: {success: true, iteration_number: 2, ...}
     ```

   - Test AnalysisResults enhancements:
     - Load item with multiple iterations
     - Click iteration tab → Switches to that iteration
     - Verify metadata context displays correctly
     - Check badges show correct labels
     - Confirm modified metadata highlighted

2. **Integration validation:**
   - Test error scenarios:
     - Network failure → Shows error toast
     - Invalid metadata → Shows validation error
     - Unauthorized access → Redirects to login
     - Server error → Shows retry button

   - Test complete user flow:
     ```
     1. Upload image → Initial analysis (iteration 1)
     2. Modify metadata → Update analysis (iteration 2)
     3. Modify again → Update analysis (iteration 3)
     4. Navigate between iterations using tabs
     5. Compare results across iterations
     6. Verify metadata context for each iteration
     ```

**Section Complete When:**
- [ ] API methods successfully call backend endpoints
- [ ] Error handling catches and displays failures appropriately
- [ ] AnalysisResults shows iteration navigation when multiple exist
- [ ] Metadata context displays for each iteration
- [ ] Iteration switching works smoothly
- [ ] Toast notifications appear for success/error states
- [ ] Retry mechanism works after failures

---

## Technical Considerations

### Performance Optimization

**Token Usage Strategy:**
- **Initial Analysis**: Full `FoodHealthAnalysis` model (~3500 input, ~1200 output tokens)
  - Generates dish predictions with confidence scores
  - Provides serving size options per dish
  - Higher cost but essential for feedback system
- **Re-Analysis**: Brief `FoodHealthAnalysisBrief` model (~2800 input, ~900 output tokens)
  - Excludes dish prediction generation
  - 20-30% token reduction per re-analysis
  - Sufficient for metadata-based updates

**Expected Savings**:
```
Example: User performs 3 re-analyses
Without optimization: 4 × 3500 = 14,000 input tokens
With optimization: 3500 + (3 × 2800) = 11,900 input tokens
Savings: ~15% total token usage
```

**Caching Strategy:**
- Store predictions in first iteration permanently
- Reuse predictions for all metadata changes
- No need to regenerate predictions after first analysis

**Frontend Performance:**
- Lazy load dropdown options only when opened
- Debounce servings count input (300ms)
- Memoize prediction rendering to prevent re-renders
- Conditional rendering of metadata panel (only when predictions exist)

### Security Considerations

**Authentication & Authorization:**
- All endpoints require authentication via `authenticate_user_from_request()`
- User ownership validation before metadata updates
- Record access restricted to owner only
- No cross-user data leakage

**Input Validation:**
- Pydantic schemas enforce type safety
- Servings count range validation (0.1 - 10.0)
- String length limits on dish names and serving sizes
- SQL injection prevention via SQLAlchemy ORM
- XSS prevention via React auto-escaping

**Data Integrity:**
- Iteration structure validation before storage
- JSON schema validation on read
- Graceful degradation for malformed legacy data
- Transaction rollback on errors

### Error Handling

**Backend Error Responses:**
- 401: Not authenticated
- 404: Record not found or unauthorized access
- 400: Validation error (invalid metadata)
- 500: Server error (LLM failure, database error)

**Frontend Error Handling:**
- Network errors: Show toast notification with retry button
- Validation errors: Display inline error messages
- Authentication failures: Redirect to login page
- Unexpected errors: Log to console, show generic error message

**Graceful Degradation:**
- If no predictions available: Allow custom dish input only
- If serving sizes missing: Provide generic options
- If re-analysis fails: Preserve previous iteration, show error
- If metadata update fails: Don't clear user input, allow retry

### Backward Compatibility

**Legacy Data Handling:**
- Existing records without iterations structure: Initialize on first access
- Records with old result_gemini format: Wrap in iterations array
- Missing metadata fields: Use sensible defaults (dish_name from analysis)
- No dish_predictions: Hide metadata panel, allow manual entry

**Migration Strategy:**
- No database schema changes required (JSON field only)
- Lazy migration: Convert to iterations structure on first access
- Preserve original analysis data in iteration 1
- Auto-initialize metadata from existing dish_name

### Testing Strategy

**Unit Tests:**
- Pydantic model validation (valid/invalid data)
- CRUD function behavior (create, read, update iterations)
- Prompt construction (full vs brief)
- Metadata validation (range checks)

**Integration Tests:**
- API endpoint workflows (metadata update → re-analysis)
- Full upload → analyze → feedback → re-analyze flow
- Iteration persistence and retrieval
- Error scenarios (invalid data, missing records)

**End-to-End Tests:**
- Complete user journey from upload to multiple re-analyses
- Metadata selection and analysis updates
- Iteration navigation and comparison
- Error recovery and retry mechanisms

---

## Deployment Considerations

### Database Migration

**No schema changes required** - iterations stored in existing `result_gemini` JSON field.

**Migration script** (optional, for proactive conversion):
```python
# scripts/migrate_to_iterations.py
"""
Convert existing result_gemini to iterations structure.
Run once after deployment to convert legacy data.
"""
def migrate_record_to_iterations(record):
    if not record.result_gemini:
        return

    # Check if already in iterations format
    if "iterations" in record.result_gemini:
        return

    # Wrap existing analysis in iteration 1
    iterations_structure = {
        "iterations": [
            {
                "iteration_number": 1,
                "created_at": record.created_at.isoformat(),
                "user_feedback": None,
                "metadata": {
                    "selected_dish": record.result_gemini.get("dish_name"),
                    "selected_serving_size": None,
                    "number_of_servings": 1.0,
                    "metadata_modified": False
                },
                "analysis": record.result_gemini
            }
        ],
        "current_iteration": 1
    }

    record.result_gemini = iterations_structure
    # Save to database
```

### Deployment Steps

1. **Backend Deployment:**
   - Deploy updated backend code with new models and endpoints
   - No database downtime required (JSON field changes only)
   - Run migration script to convert existing records (optional)
   - Monitor logs for errors during first analyses

2. **Frontend Deployment:**
   - Build frontend with new components
   - Deploy to production
   - Ensure API_BASE_URL environment variable is set correctly
   - Monitor for JavaScript errors in browser console

3. **Verification:**
   - Test upload and analysis with new code
   - Verify dish predictions appear in response
   - Test metadata update and re-analysis workflow
   - Check that legacy records still display correctly

### Monitoring & Metrics

**Key Metrics to Track:**
- Percentage of users using feedback features
- Average number of re-analyses per record
- Token usage before/after (verify savings)
- Error rates for metadata updates
- Re-analysis success rate
- Average time for re-analysis completion

**Logging:**
- Log all metadata updates with user_id and record_id
- Log re-analysis requests with metadata context
- Track token usage for full vs brief analyses
- Monitor LLM API errors and retry attempts

---

## Appendix

### File Structure Summary

**New Backend Files:**
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/resources/food_analysis_brief.md` - Brief analysis prompt

**Modified Backend Files:**
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/models.py` - Add DishPrediction, FoodHealthAnalysisBrief
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/gemini_analyzer.py` - Add analyze_with_gemini_brief_async()
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/service/llm/prompts.py` - Add get_brief_analysis_prompt()
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/crud/crud_food_image_query.py` - Add iteration management functions
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/api/item.py` - Add PATCH /metadata, POST /reanalyze endpoints
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/src/schemas.py` - Add MetadataUpdate schema
- `/Users/alan/Documents/delta/dish_healthiness_prod/backend/resources/food_analysis.md` - Update for dish predictions

**New Frontend Files:**
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/DishPredictions.jsx`
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/ServingSizeSelector.jsx`
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/ServingsCountInput.jsx`

**Modified Frontend Files:**
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/pages/Item.jsx` - Add metadata state and handlers
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/services/api.js` - Add metadata and reanalyze methods
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/AnalysisResults.jsx` - Add iteration navigation
- `/Users/alan/Documents/delta/dish_healthiness_prod/frontend/src/components/item/index.js` - Export new components

### API Endpoint Summary

| Method | Endpoint | Purpose | Request Body | Response |
|--------|----------|---------|--------------|----------|
| GET | `/api/item/{record_id}` | Get item with iterations | - | Item with iterations array |
| PATCH | `/api/item/{record_id}/metadata` | Update metadata | `{selected_dish, selected_serving_size, number_of_servings}` | `{success, metadata_modified}` |
| POST | `/api/item/{record_id}/reanalyze` | Trigger re-analysis | - | `{success, iteration_number, analysis_data}` |

### Component Props Reference

**DishPredictions.jsx:**
```typescript
interface DishPredictionsProps {
  predictions: Array<{
    name: string;
    confidence: number;
    serving_sizes: string[];
  }>;
  selectedDish: string;
  onDishSelect: (dishName: string) => void;
  disabled: boolean;
}
```

**ServingSizeSelector.jsx:**
```typescript
interface ServingSizeSelectorProps {
  options: string[];
  selectedOption: string;
  onSelect: (size: string) => void;
  disabled: boolean;
  dishName: string;
}
```

**ServingsCountInput.jsx:**
```typescript
interface ServingsCountInputProps {
  value: number;
  onChange: (count: number) => void;
  disabled: boolean;
  min?: number;  // default: 0.1
  max?: number;  // default: 10.0
  step?: number; // default: 0.5
}
```

---

**End of Implementation Plan**
