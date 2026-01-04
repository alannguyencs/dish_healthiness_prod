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
};

export default apiService;
