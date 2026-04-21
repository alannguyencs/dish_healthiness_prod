import axios from "axios";

// Base URL for API - use environment variable in production, fallback to localhost for development
export const API_BASE_URL =
  process.env.REACT_APP_API_URL || "http://localhost:2612";

// Configure axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// API methods
const apiService = {
  // Auth endpoints
  login: async (username, password) => {
    const response = await api.post("/api/login/", {
      username,
      password,
    });
    return response.data;
  },

  logout: async () => {
    const response = await api.post("/api/login/logout");
    return response.data;
  },

  getSession: async () => {
    const response = await api.get("/api/login/session");
    return response.data;
  },

  // Dashboard endpoints
  getDashboardData: async (year = null, month = null) => {
    const params = {};
    if (year) params.year = year;
    if (month) params.month = month;
    const response = await api.get("/api/dashboard/", { params });
    return response.data;
  },

  // Date endpoints
  getDateData: async (year, month, day) => {
    const response = await api.get(`/api/date/${year}/${month}/${day}`);
    return response.data;
  },

  uploadDishImage: async (year, month, day, dishPosition, file) => {
    const formData = new FormData();
    formData.append("dish_position", dishPosition);
    formData.append("file", file);

    const response = await api.post(
      `/api/date/${year}/${month}/${day}/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      },
    );
    return response.data;
  },

  uploadDishImageFromUrl: async (year, month, day, dishPosition, imageUrl) => {
    const response = await api.post(
      `/api/date/${year}/${month}/${day}/upload-url`,
      {
        dish_position: dishPosition,
        image_url: imageUrl,
      },
    );
    return response.data;
  },

  // Item endpoints
  getItem: async (recordId) => {
    const response = await api.get(`/api/item/${recordId}`);
    return response.data;
  },

  // Metadata update endpoint
  updateItemMetadata: async (recordId, metadata) => {
    const response = await api.patch(
      `/api/item/${recordId}/metadata`,
      metadata,
    );
    return response.data;
  },

  // Re-analysis endpoint (legacy)
  reanalyzeItem: async (recordId) => {
    const response = await api.post(`/api/item/${recordId}/reanalyze`);
    return response.data;
  },

  // NEW: Step 1 confirmation endpoint (triggers Step 2)
  confirmStep1: async (recordId, confirmationData) => {
    // confirmationData should have:
    // {
    //   selected_dish_name: string,
    //   components: [
    //     { component_name: string, selected_serving_size: string, number_of_servings: float }
    //   ]
    // }
    const response = await api.post(
      `/api/item/${recordId}/confirm-step1`,
      confirmationData,
    );
    return response.data;
  },

  // Retry Step 2 nutritional analysis after a prior failure
  retryStep2: async (recordId) => {
    const response = await api.post(`/api/item/${recordId}/retry-step2`);
    return response.data;
  },

  // Retry Step 1 component identification after a prior failure
  retryStep1: async (recordId) => {
    const response = await api.post(`/api/item/${recordId}/retry-step1`);
    return response.data;
  },

  // Stage 8: save a user correction of the Step 2 nutritional analysis
  saveStep2Correction: async (recordId, payload) => {
    // payload should have:
    // {
    //   healthiness_score: int,             // 0-100
    //   healthiness_score_rationale: string,
    //   calories_kcal: float,
    //   fiber_g: float,
    //   carbs_g: float,
    //   protein_g: float,
    //   fat_g: float,
    //   micronutrients: string[],
    // }
    const response = await api.post(
      `/api/item/${recordId}/correction`,
      payload,
    );
    return response.data;
  },

  // Stage 10: prompt-driven AI Assistant revision of the Step 2 analysis.
  // Backend calls Gemini 2.5 Pro with the query image + current effective
  // Step 2 payload + user hint, commits the revised payload directly.
  saveAiAssistantCorrection: async (recordId, prompt) => {
    const response = await api.post(
      `/api/item/${recordId}/ai-assistant-correction`,
      { prompt },
    );
    return response.data;
  },
};

export default apiService;
