import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiService from "../services/api";
import useItemPolling from "../hooks/useItemPolling";
import {
  ItemHeader,
  ItemImage,
  AnalysisLoading,
  Step1ComponentEditor,
  Step2Results,
  PhaseErrorCard,
  ItemStepTabs,
  ReasoningPanel,
  Top5DbMatches,
  PersonalizationMatches,
  PersonalizedDataCard,
} from "../components/item";

const ItemV2 = () => {
  const { recordId } = useParams();
  const navigate = useNavigate();
  const {
    item,
    loading,
    error,
    pollingStep1,
    pollingStep2,
    confirmedStep1Data,
    setConfirmedStep1Data,
    reload,
    startPollingStep1,
    startPollingStep2,
  } = useItemPolling(recordId);

  const [confirming, setConfirming] = useState(false);
  const [retryingStep2, setRetryingStep2] = useState(false);
  const [retryingStep1, setRetryingStep1] = useState(false);
  const [saving, setSaving] = useState(false);
  const [viewStep, setViewStep] = useState(null);

  const handleStep2Correction = async (payload) => {
    try {
      setSaving(true);
      await apiService.saveStep2Correction(recordId, payload);
      await reload();
    } catch (err) {
      console.error("Failed to save correction:", err);
      alert("Failed to save correction. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleStep1Confirmation = async (confirmationData) => {
    try {
      setConfirming(true);
      setConfirmedStep1Data(confirmationData);
      await apiService.confirmStep1(recordId, confirmationData);
      startPollingStep2();
      await reload();
    } catch (err) {
      // 409 = the server has already accepted a prior confirmation for this
      // record (e.g. a double-tapped Confirm). Phase 2 is already running, so
      // treat it as success: just resume polling and refetch state.
      if (err?.response?.status === 409) {
        startPollingStep2();
        await reload();
      } else {
        console.error("Failed to confirm Step 1:", err);
        alert("Failed to confirm Step 1. Please try again.");
      }
    } finally {
      setConfirming(false);
    }
  };

  const handleStep2Retry = async () => {
    try {
      setRetryingStep2(true);
      await apiService.retryStep2(recordId);
      startPollingStep2();
      await reload();
    } catch (err) {
      console.error("Failed to retry Step 2:", err);
      alert("Failed to retry. Please try again in a moment.");
    } finally {
      setRetryingStep2(false);
    }
  };

  const handleStep1Retry = async () => {
    try {
      setRetryingStep1(true);
      await apiService.retryStep1(recordId);
      startPollingStep1();
      await reload();
    } catch (err) {
      console.error("Failed to retry Step 1:", err);
      alert("Failed to retry. Please try again in a moment.");
    } finally {
      setRetryingStep1(false);
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
  const step1Error = resultGemini?.step1_error;
  const step2Data = resultGemini?.step2_data;
  const step2Corrected = resultGemini?.step2_corrected;
  const step2Error = resultGemini?.step2_error;
  const nutritionDbMatches = resultGemini?.nutrition_db_matches;
  const personalizedMatches = resultGemini?.personalized_matches;
  const flashCaption = resultGemini?.flash_caption;
  const referenceImage = resultGemini?.reference_image;
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

            {step1Error && !step1Data && viewStep === null && (
              <PhaseErrorCard
                headline="Component identification failed"
                error={step1Error}
                onRetry={handleStep1Retry}
                isRetrying={retryingStep1}
              />
            )}

            {((viewStep === 1 && step1Data) ||
              (viewStep === null &&
                currentStep === 1 &&
                step1Data &&
                !pollingStep1)) && (
              <>
                <PersonalizedDataCard
                  flashCaption={flashCaption}
                  referenceImage={referenceImage}
                />
                <Step1ComponentEditor
                  step1Data={step1Data}
                  confirmedData={confirmedStep1Data}
                  onConfirm={handleStep1Confirmation}
                  isConfirming={confirming}
                />
              </>
            )}

            {step1Confirmed &&
              pollingStep2 &&
              !step2Data &&
              !step2Error &&
              viewStep === null && (
                <AnalysisLoading message="Calculating nutritional values..." />
              )}

            {step2Error && !step2Data && viewStep === null && (
              <PhaseErrorCard
                headline="Nutritional analysis failed"
                error={step2Error}
                onRetry={handleStep2Retry}
                isRetrying={retryingStep2}
              />
            )}

            {((viewStep === 2 && step2Data) ||
              (viewStep === null && currentStep === 2 && step2Data)) && (
              <>
                <Step2Results
                  step2Data={step2Data}
                  step2Corrected={step2Corrected}
                  onEditSave={handleStep2Correction}
                  saving={saving}
                />
                <ReasoningPanel step2Data={step2Data} />
                <Top5DbMatches
                  matches={nutritionDbMatches?.nutrition_matches}
                />
                <PersonalizationMatches matches={personalizedMatches} />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ItemV2;
