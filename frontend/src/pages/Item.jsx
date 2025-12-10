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
    NoAnalysisAvailable,
    DishPredictions,
    ServingSizeSelector,
    ServingsCountInput
} from '../components/item';

/**
 * Item Page Component
 *
 * Main page for viewing detailed analysis of a single food record.
 * Handles polling for analysis completion and displays Gemini results.
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

    // Metadata state for feedback system
    const [metadata, setMetadata] = useState({
        selectedDish: null,
        selectedServingSize: null,
        numberOfServings: 1.0,
        servingOptions: [],
        predictedServings: null, // AI predicted number of servings
        metadataModified: false
    });
    const [savingMetadata, setSavingMetadata] = useState(false);
    const [metadataSaved, setMetadataSaved] = useState(false);
    const [reanalyzing, setReanalyzing] = useState(false);

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

            // Initialize metadata from current iteration
            if (data.iterations && data.iterations.length > 0) {
                const currentIter = data.iterations[data.current_iteration - 1];
                if (currentIter && currentIter.analysis) {
                    const predictions = currentIter.analysis.dish_predictions || [];
                    const currentMetadata = currentIter.metadata || {};

                    // Auto-select top prediction if available
                    const topPrediction = predictions[0];
                    const selectedDish = currentMetadata.selected_dish || (topPrediction ? topPrediction.name : null);
                    const servingSizes = topPrediction ? topPrediction.serving_sizes : [];
                    const predictedServings = topPrediction ? topPrediction.predicted_servings : null;

                    setMetadata({
                        selectedDish: selectedDish,
                        selectedServingSize: currentMetadata.selected_serving_size || (servingSizes[0] || null),
                        numberOfServings: currentMetadata.number_of_servings || predictedServings || 1.0,
                        servingOptions: servingSizes,
                        predictedServings: predictedServings,
                        metadataModified: currentMetadata.metadata_modified || false
                    });
                }
            }

            // If no analysis result yet, start polling
            if (!data.result_gemini) {
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
                if (data.result_gemini) {
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

    // Event Handlers for Metadata
    const handleDishSelect = (dishName) => {
        // Find selected dish prediction
        if (!item || !item.iterations || item.iterations.length === 0) return;

        const currentIter = item.iterations[item.current_iteration - 1];
        const predictions = currentIter?.analysis?.dish_predictions || [];
        const selectedPrediction = predictions.find(p => p.name === dishName);
        const servingSizes = selectedPrediction?.serving_sizes || [];
        const predictedServings = selectedPrediction?.predicted_servings || null;

        setMetadata(prev => ({
            ...prev,
            selectedDish: dishName,
            selectedServingSize: servingSizes[0] || prev.selectedServingSize,
            numberOfServings: predictedServings || prev.numberOfServings,
            servingOptions: servingSizes,
            predictedServings: predictedServings,
            metadataModified: true
        }));
    };

    const handleServingSizeSelect = (size) => {
        setMetadata(prev => ({
            ...prev,
            selectedServingSize: size,
            metadataModified: true
        }));
    };

    const handleServingsCountChange = (count) => {
        setMetadata(prev => ({
            ...prev,
            numberOfServings: count,
            metadataModified: true
        }));
    };

    const handleUpdateAnalysis = async () => {
        try {
            setSavingMetadata(true);
            setReanalyzing(true);

            // Save metadata
            await apiService.updateItemMetadata(recordId, {
                selected_dish: metadata.selectedDish,
                selected_serving_size: metadata.selectedServingSize,
                number_of_servings: metadata.numberOfServings
            });

            // Trigger re-analysis
            await apiService.reanalyzeItem(recordId);

            // Reload item to get new iteration
            await loadItem();

            setMetadata(prev => ({ ...prev, metadataModified: false }));
            setMetadataSaved(true);
            setTimeout(() => setMetadataSaved(false), 3000);

        } catch (error) {
            console.error('Update analysis failed:', error);
            alert('Failed to update analysis. Please try again.');
        } finally {
            setSavingMetadata(false);
            setReanalyzing(false);
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

                {/* Metadata Panel - Only shown when predictions exist */}
                {item && item.iterations && item.iterations.length > 0 && (() => {
                    const currentIter = item.iterations[item.current_iteration - 1];
                    const predictions = currentIter?.analysis?.dish_predictions || [];

                    if (predictions.length > 0) {
                        return (
                            <div className="mb-6 bg-gray-50 p-6 rounded-lg border border-gray-200">
                                <h2 className="text-xl font-semibold text-gray-900 mb-4">
                                    Adjust Dish Information
                                </h2>
                                <p className="text-sm text-gray-600 mb-4">
                                    Review the AI's dish identification and adjust portion details if needed.
                                </p>

                                <DishPredictions
                                    predictions={predictions}
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
                                    predictedServings={metadata.predictedServings}
                                />

                                {metadata.metadataModified && (
                                    <button
                                        onClick={handleUpdateAnalysis}
                                        disabled={savingMetadata || reanalyzing}
                                        className="w-full mt-4 bg-blue-600 text-white py-3 px-4 rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed font-medium transition-colors"
                                    >
                                        {reanalyzing ? 'Updating Analysis...' : 'Update Food Analysis'}
                                    </button>
                                )}

                                {metadataSaved && (
                                    <div className="mt-3 p-3 bg-green-100 text-green-800 rounded-lg text-sm">
                                        Analysis updated successfully!
                                    </div>
                                )}
                            </div>
                        );
                    }
                    return null;
                })()}

                {/* Analysis Results */}
                {analyzing || !item ? (
                    <AnalysisLoading />
                ) : displayItem.result_gemini ? (
                    <AnalysisResults item={displayItem} />
                ) : (
                    <NoAnalysisAvailable />
                )}
            </div>
        </div>
    );
};

export default Item;
