import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiService from '../services/api';
import {
    DateViewNavigation,
    MealUploadGrid
} from '../components/dateview';

/**
 * Date View Page Component
 *
 * Main page for viewing and managing meals for a specific date.
 * Handles file uploads and meal analysis.
 */
const DateView = () => {
    const { year, month, day } = useParams();
    const navigate = useNavigate();
    const [dateData, setDateData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(null);

    useEffect(() => {
        loadDateData();
    }, [year, month, day]);

    const loadDateData = async () => {
        try {
            setLoading(true);
            const data = await apiService.getDateData(year, month, day);
            setDateData(data);
        } catch (error) {
            console.error('Error loading date data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleFileUpload = async (mealType, file) => {
        if (!file) return;

        setUploading(mealType);
        try {
            const response = await apiService.uploadMealImage(year, month, day, mealType, file);
            // Redirect to item page to show upload and wait for analysis
            if (response.query && response.query.id) {
                navigate(`/item/${response.query.id}`, {
                    state: {
                        uploadedImage: response.query.image_url,
                        uploadedMealType: mealType
                    }
                });
            }
        } catch (error) {
            console.error('Error uploading file:', error);
            alert('Failed to upload image');
            setUploading(null);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl">Loading...</div>
            </div>
        );
    }

    if (!dateData) return null;

    const hasAnyData = dateData.meal_types.some((mt) => dateData.meal_data[mt].has_data);

    return (
        <div className="min-h-screen bg-gray-100 p-4">
            <div className="max-w-6xl mx-auto bg-white rounded-lg shadow-lg p-6">
                {/* Navigation */}
                <DateViewNavigation
                    hasAnyData={hasAnyData}
                    onBackToCalendar={() => navigate('/dashboard')}
                />

                {/* Upload View */}
                <MealUploadGrid
                    dateData={dateData}
                    uploading={uploading}
                    onFileUpload={handleFileUpload}
                />
            </div>
        </div>
    );
};

export default DateView;
