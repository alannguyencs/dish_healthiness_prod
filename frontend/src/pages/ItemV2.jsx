import React, { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiService from "../services/api";
import {
  ItemHeader,
  ItemImage,
  AnalysisLoading,
  Step1ComponentEditor,
  Step2Results,
  Step2ErrorCard,
  ItemStepTabs,
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
  const [retryingStep2, setRetryingStep2] = useState(false);
  const [viewStep, setViewStep] = useState(null);
  const [confirmedStep1Data, setConfirmedStep1Data] = useState(null);
  const pollingIntervalRef = useRef(null);

  useEffect(() => {
    loadItem();
    return () => {
      if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId]);

  const loadItem = async () => {
    try {
      setLoading(true);
      const data = await apiService.getItem(recordId);
      setItem(data);
      setError(null);

      const resultGemini = data.result_gemini;
      if (
        resultGemini?.confirmed_components &&
        resultGemini?.confirmed_dish_name
      ) {
        setConfirmedStep1Data({
          selected_dish_name: resultGemini.confirmed_dish_name,
          components: resultGemini.confirmed_components,
        });
      }

      if (!resultGemini) {
        setPollingStep1(true);
        startPolling();
      } else if (resultGemini.step === 1 && !resultGemini.step1_confirmed) {
        setPollingStep1(false);
        setPollingStep2(false);
        stopPolling();
      } else if (
        resultGemini.step1_confirmed &&
        !resultGemini.step2_data &&
        !resultGemini.step2_error
      ) {
        setPollingStep1(false);
        setPollingStep2(true);
        startPolling();
      } else {
        // Step 2 either completed (step2_data) or failed (step2_error)
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
    if (pollingIntervalRef.current) return;
    pollingIntervalRef.current = setInterval(async () => {
      try {
        const data = await apiService.getItem(recordId);
        setItem(data);

        const resultGemini = data.result_gemini;
        if (!resultGemini) return;

        // Stop polling if Step 1 is complete and awaiting confirmation
        if (resultGemini.step === 1 && !resultGemini.step1_confirmed) {
          setPollingStep1(false);
          setPollingStep2(false);
          stopPolling();
        }

        // Stop polling if Step 2 succeeded OR failed (error surfaced)
        if (resultGemini.step2_data || resultGemini.step2_error) {
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
      setConfirmedStep1Data(confirmationData);
      await apiService.confirmStep1(recordId, confirmationData);
      setPollingStep2(true);
      startPolling();
      await loadItem();
    } catch (err) {
      console.error("Failed to confirm Step 1:", err);
      alert("Failed to confirm Step 1. Please try again.");
    } finally {
      setConfirming(false);
    }
  };

  const handleStep2Retry = async () => {
    try {
      setRetryingStep2(true);
      await apiService.retryStep2(recordId);
      setPollingStep2(true);
      startPolling();
      await loadItem();
    } catch (err) {
      console.error("Failed to retry Step 2:", err);
      alert("Failed to retry. Please try again in a moment.");
    } finally {
      setRetryingStep2(false);
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
  const step2Error = resultGemini?.step2_error;
  const currentStep = resultGemini?.step || 0;
  const step1Confirmed = resultGemini?.step1_confirmed || false;

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="max-w-7xl mx-auto p-4 space-y-6">
        <ItemHeader
          onBackClick={handleBackToDashboard}
          targetDate={item?.target_date}
        />

        <div className="flex flex-col lg:flex-row gap-6">
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

          <div className="lg:w-2/3 space-y-6">
            <ItemStepTabs
              step1Data={step1Data}
              step2Data={step2Data}
              currentStep={currentStep}
              step1Confirmed={step1Confirmed}
              viewStep={viewStep}
              onSelectStep={setViewStep}
            />

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
              !step2Error &&
              viewStep === null && (
                <AnalysisLoading message="Calculating nutritional values..." />
              )}

            {step2Error && !step2Data && viewStep === null && (
              <Step2ErrorCard
                error={step2Error}
                onRetry={handleStep2Retry}
                isRetrying={retryingStep2}
              />
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
