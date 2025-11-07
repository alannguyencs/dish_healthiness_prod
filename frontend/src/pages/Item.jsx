import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import apiService from '../services/api';
import {
    ItemHeader,
    ItemNavigation,
    ItemImage,
    ItemMetadata,
    AnalysisLoading,
    AnalysisResults,
    NoAnalysisAvailable
} from '../components/item';

/**
 * Item Page Component
 *
 * Main page for viewing detailed analysis of a single food record.
 * Handles polling for analysis completion and displays OpenAI and Gemini results.
 */
const Item = () => {
    const { recordId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [item, setItem] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [analyzing, setAnalyzing] = useState(false);
    const pollingIntervalRef = useRef(null);

    // Get uploaded image info from navigation state (if coming from upload)
    const uploadedData = location.state || {};

    useEffect(() => {
        loadItem();
        return () => {
            // Clean up polling on unmount
            if (pollingIntervalRef.current) {
                clearInterval(pollingIntervalRef.current);
            }
        };
    }, [recordId]);

    const loadItem = async () => {
        try {
            setLoading(true);
            const data = await apiService.getItem(recordId);
            setItem(data);
            setError(null);

            // If no analysis result yet, start polling
            if (!data.result_openai && !data.result_gemini) {
                setAnalyzing(true);
                startPolling();
            } else {
                setAnalyzing(false);
                stopPolling();
            }
        } catch (err) {
            setError('Failed to load item details');
            console.error(err);
            setAnalyzing(false);
            stopPolling();
        } finally {
            setLoading(false);
        }
    };

    const startPolling = () => {
        // Don't start if already polling
        if (pollingIntervalRef.current) return;

        // Poll every 3 seconds
        pollingIntervalRef.current = setInterval(async () => {
            try {
                const data = await apiService.getItem(recordId);
                setItem(data);

                // Stop polling if we have results
                if (data.result_openai || data.result_gemini) {
                    setAnalyzing(false);
                    stopPolling();
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 3000);
    };

    const stopPolling = () => {
        if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
    };

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl text-red-600">{error}</div>
            </div>
        );
    }

    // Show minimal loading only on very first load without any data
    if (loading && !item && !uploadedData.uploadedImage) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl">Loading...</div>
            </div>
        );
    }

    // If we have uploaded data but no item yet, create a temporary item object
    const displayItem = item || (uploadedData.uploadedImage ? {
        id: recordId,
        image_url: uploadedData.uploadedImage,
        dish_position: uploadedData.uploadedDishPosition,
        created_at: new Date().toISOString()
    } : null);

    if (!displayItem) return null;

    // Extract date from target_date or created_at
    const getDatePath = () => {
        const dateStr = item?.target_date || item?.created_at;
        if (!dateStr) return '/dashboard';

        const dateMatch = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/);
        if (!dateMatch) return '/dashboard';

        const year = parseInt(dateMatch[1], 10);
        const month = parseInt(dateMatch[2], 10);
        const day = parseInt(dateMatch[3], 10);

        return `/date/${year}/${month}/${day}`;
    };

    return (
        <div className="min-h-screen bg-gray-100 p-4">
            <div className="max-w-5xl mx-auto bg-white rounded-lg shadow-lg p-6">
                {/* Header */}
                <ItemHeader itemId={displayItem.id} />

                {/* Navigation */}
                <ItemNavigation
                    onBackToDate={() => navigate(getDatePath())}
                />

                {/* Record Details */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                    <ItemImage imageUrl={displayItem.image_url} />
                    <ItemMetadata item={displayItem} />
                </div>

                {/* Analysis Results */}
                {analyzing || !item ? (
                    <AnalysisLoading />
                ) : (displayItem.result_openai || displayItem.result_gemini) ? (
                    <AnalysisResults item={displayItem} />
                ) : (
                    <NoAnalysisAvailable />
                )}
            </div>
        </div>
    );
};

export default Item;
