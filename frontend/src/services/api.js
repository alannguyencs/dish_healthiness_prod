import axios from 'axios';

// Base URL for API - use environment variable in production, fallback to localhost for development
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:2512';

// Configure axios instance
const api = axios.create({
    baseURL: API_BASE_URL,
    withCredentials: true,
    headers: {
        'Content-Type': 'application/json',
    },
});

// API methods
const apiService = {
    // Auth endpoints
    login: async (username, password) => {
        const response = await api.post('/api/login/', {
          username,
          password
        });
        return response.data;
    },

    logout: async () => {
        const response = await api.post('/api/login/logout');
        return response.data;
    },

    // Dashboard endpoints
    getDashboardData: async (year = null, month = null) => {
        const params = {};
        if (year) params.year = year;
        if (month) params.month = month;
        const response = await api.get('/api/dashboard/', { params });
        return response.data;
    },

    // Date endpoints
    getDateData: async (year, month, day) => {
        const response = await api.get(`/api/date/${year}/${month}/${day}`);
        return response.data;
    },

    uploadDishImage: async (year, month, day, dishPosition, file) => {
        const formData = new FormData();
        formData.append('dish_position', dishPosition);
        formData.append('file', file);

        const response = await api.post(
            `/api/date/${year}/${month}/${day}/upload`,
            formData,
            {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            }
        );
        return response.data;
    },

    // Item endpoints
    getItem: async (recordId) => {
        const response = await api.get(`/api/item/${recordId}`);
        return response.data;
    },
};

export default apiService;

