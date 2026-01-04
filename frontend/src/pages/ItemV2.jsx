import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiService from "../services/api";
import {
  ItemHeader,
  ItemNavigation,
  ItemImage,
  AnalysisLoading,
  Step1ComponentEditor,
  Step2Results,
} from "../components/item";

const ItemV2 = () => {
  const { recordId } = useParams();
  const navigate = useNavigate();
  const [item, setItem] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pollingStep1, setPollingStep1] = useState(false);
  const [pollingStep2, setPollingStep2] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [viewStep, setViewStep] = useState(null); // Track which step view to show (null = auto)
  const [confirmedStep1Data, setConfirmedStep1Data] = useState(null); // Store user's confirmed selections
  const pollingIntervalRef = useRef(null);

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

      // Determine current step and polling state
      const resultGemini = data.result_gemini;

      if (!resultGemini) {
        // No analysis yet - waiting for Step 1
        setPollingStep1(true);
        startPolling();
      } else if (resultGemini.step === 1 && !resultGemini.step1_confirmed) {
        // Step 1 complete, waiting for user confirmation
        setPollingStep1(false);
        setPollingStep2(false);
        stopPolling();
      } else if (
        resultGemini.step === 1 &&
        resultGemini.step1_confirmed &&
        !resultGemini.step2_data
      ) {
        // Step 1 confirmed, waiting for Step 2
        setPollingStep1(false);
        setPollingStep2(true);
        startPolling();
      } else if (resultGemini.step === 2 && resultGemini.step2_data) {
        // Step 2 complete - all done
        setPollingStep1(false);
        setPollingStep2(false);
        stopPolling();
      }
    } catch (err) {
      setError("Failed to load item details");
      console.error(err);
      setPollingStep1(false);
      setPollingStep2(false);
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

        const resultGemini = data.result_gemini;

        // Stop polling if Step 1 is complete (and awaiting confirmation)
        if (
          resultGemini &&
          resultGemini.step === 1 &&
          !resultGemini.step1_confirmed
        ) {
          setPollingStep1(false);
          setPollingStep2(false);
          stopPolling();
        }

        // Stop polling if Step 2 is complete
        if (
          resultGemini &&
          resultGemini.step === 2 &&
          resultGemini.step2_data
        ) {
          setPollingStep1(false);
          setPollingStep2(false);
          stopPolling();
        }
      } catch (err) {
        console.error("Polling error:", err);
      }
    }, 3000);
  };

  const stopPolling = () => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  };

  const handleStep1Confirmation = async (confirmationData) => {
    try {
      setConfirming(true);
      // Store the user's confirmed selections
      setConfirmedStep1Data(confirmationData);
      await apiService.confirmStep1(recordId, confirmationData);

      // Start polling for Step 2
      setPollingStep2(true);
      startPolling();

      // Reload item to get updated state
      await loadItem();
    } catch (err) {
      console.error("Failed to confirm Step 1:", err);
      alert("Failed to confirm Step 1. Please try again.");
    } finally {
      setConfirming(false);
    }
  };

  const handleBackToDashboard = () => {
    navigate("/dashboard");
  };

  if (loading && !item) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <p className="text-red-800 font-semibold">{error}</p>
          <button
            onClick={handleBackToDashboard}
            className="mt-4 w-full bg-red-600 hover:bg-red-700 text-white font-semibold py-2 px-4 rounded-lg"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  const resultGemini = item?.result_gemini;
  const step1Data = resultGemini?.step1_data;
  const step2Data = resultGemini?.step2_data;
  const currentStep = resultGemini?.step || 0;
  const step1Confirmed = resultGemini?.step1_confirmed || false;

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="max-w-7xl mx-auto p-4 space-y-6">
        {/* Header */}
        <ItemHeader
          onBackClick={handleBackToDashboard}
          targetDate={item?.target_date}
        />

        {/* Main Content: Image (1/3) + Analysis (2/3) */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left Column: Image (1/3 width) */}
          <div className="lg:w-1/3">
            {item && (
              <div className="sticky top-4">
                <ItemImage
                  imageUrl={item.image_url}
                  targetDate={item.target_date}
                  dishPosition={item.dish_position}
                />
              </div>
            )}
          </div>

          {/* Right Column: Analysis (2/3 width) */}
          <div className="lg:w-2/3 space-y-6">
            {/* Progress Indicator */}
            <div className="bg-white rounded-lg shadow-md p-4">
              <div className="flex items-center space-x-4">
                <button
                  onClick={() => setViewStep(1)}
                  disabled={!step1Data}
                  className={`flex-1 text-center p-3 rounded-lg transition-all ${
                    viewStep === 1 || (viewStep === null && currentStep === 1)
                      ? "bg-blue-100 border-2 border-blue-500"
                      : currentStep >= 1
                        ? "bg-blue-50 border-2 border-blue-300 hover:bg-blue-100 cursor-pointer"
                        : "bg-gray-100 cursor-not-allowed"
                  }`}
                >
                  <div className="font-semibold text-gray-800">Step 1</div>
                  <div className="text-xs text-gray-600">
                    Component Identification
                  </div>
                  {currentStep === 1 && !step1Confirmed && (
                    <div className="text-xs text-blue-600 font-medium mt-1">
                      Awaiting Confirmation
                    </div>
                  )}
                </button>
                <div className="text-gray-400">→</div>
                <button
                  onClick={() => setViewStep(2)}
                  disabled={!step2Data}
                  className={`flex-1 text-center p-3 rounded-lg transition-all ${
                    viewStep === 2 || (viewStep === null && currentStep === 2)
                      ? "bg-green-100 border-2 border-green-500"
                      : step2Data
                        ? "bg-green-50 border-2 border-green-300 hover:bg-green-100 cursor-pointer"
                        : "bg-gray-100 cursor-not-allowed"
                  }`}
                >
                  <div className="font-semibold text-gray-800">Step 2</div>
                  <div className="text-xs text-gray-600">
                    Nutritional Analysis
                  </div>
                  {step1Confirmed && !step2Data && (
                    <div className="text-xs text-blue-600 font-medium mt-1">
                      In Progress...
                    </div>
                  )}
                </button>
              </div>
            </div>

            {/* Content based on current step or user selection */}
            {pollingStep1 && viewStep === null && (
              <AnalysisLoading message="Analyzing dish components..." />
            )}

            {((viewStep === 1 && step1Data) ||
              (viewStep === null &&
                currentStep === 1 &&
                step1Data &&
                !pollingStep1)) && (
              <Step1ComponentEditor
                step1Data={step1Data}
                confirmedData={confirmedStep1Data}
                onConfirm={handleStep1Confirmation}
                isConfirming={confirming}
              />
            )}

            {step1Confirmed &&
              pollingStep2 &&
              !step2Data &&
              viewStep === null && (
                <AnalysisLoading message="Calculating nutritional values..." />
              )}

            {((viewStep === 2 && step2Data) ||
              (viewStep === null && currentStep === 2 && step2Data)) && (
              <Step2Results step2Data={step2Data} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ItemV2;
