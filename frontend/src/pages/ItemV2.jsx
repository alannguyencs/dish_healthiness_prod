import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import apiService from "../services/api";
import useItemPolling from "../hooks/useItemPolling";
import {
  ItemHeader,
  ItemImage,
  AnalysisLoading,
  IdentificationComponentEditor,
  NutritionResults,
  PhaseErrorCard,
  ItemStepTabs,
  ReasoningPanel,
  Top5DbMatches,
  PersonalizationMatches,
  PersonalizedDataCard,
  ResearchOnlyGroup,
} from "../components/item";

const ItemV2 = () => {
  const { recordId } = useParams();
  const navigate = useNavigate();
  const {
    item,
    loading,
    error,
    pollingIdentification,
    pollingNutrition,
    confirmedIdentificationData,
    setConfirmedIdentificationData,
    reload,
    startPollingIdentification,
    startPollingNutrition,
  } = useItemPolling(recordId);

  const [confirming, setConfirming] = useState(false);
  const [retryingNutrition, setRetryingNutrition] = useState(false);
  const [retryingIdentification, setRetryingIdentification] = useState(false);
  const [saving, setSaving] = useState(false);
  const [aiAssisting, setAiAssisting] = useState(false);
  const [viewStep, setViewStep] = useState(null);

  const handleNutritionCorrection = async (payload) => {
    try {
      setSaving(true);
      await apiService.saveNutritionCorrection(recordId, payload);
      await reload();
    } catch (err) {
      console.error("Failed to save correction:", err);
      alert("Failed to save correction. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleAiAssistantCorrection = async (prompt) => {
    try {
      setAiAssisting(true);
      await apiService.saveAiAssistantCorrection(recordId, prompt);
      await reload();
    } catch (err) {
      console.error("Failed AI Assistant revision:", err);
      alert("AI revision failed. Please try again.");
    } finally {
      setAiAssisting(false);
    }
  };

  const handleIdentificationConfirmation = async (confirmationData) => {
    try {
      setConfirming(true);
      setConfirmedIdentificationData(confirmationData);
      await apiService.confirmIdentification(recordId, confirmationData);
      startPollingNutrition();
      await reload();
    } catch (err) {
      // 409 = the server has already accepted a prior confirmation for this
      // record (e.g. a double-tapped Confirm). Phase 2 is already running, so
      // treat it as success: just resume polling and refetch state.
      if (err?.response?.status === 409) {
        startPollingNutrition();
        await reload();
      } else {
        console.error("Failed to confirm identification:", err);
        alert("Failed to confirm identification. Please try again.");
      }
    } finally {
      setConfirming(false);
    }
  };

  const handleNutritionRetry = async () => {
    try {
      setRetryingNutrition(true);
      await apiService.retryNutrition(recordId);
      startPollingNutrition();
      await reload();
    } catch (err) {
      console.error("Failed to retry nutrition analysis:", err);
      alert("Failed to retry. Please try again in a moment.");
    } finally {
      setRetryingNutrition(false);
    }
  };

  const handleIdentificationRetry = async () => {
    try {
      setRetryingIdentification(true);
      await apiService.retryIdentification(recordId);
      startPollingIdentification();
      await reload();
    } catch (err) {
      console.error("Failed to retry identification:", err);
      alert("Failed to retry. Please try again in a moment.");
    } finally {
      setRetryingIdentification(false);
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
  const identificationData = resultGemini?.identification_data;
  const identificationError = resultGemini?.identification_error;
  const nutritionData = resultGemini?.nutrition_data;
  const nutritionCorrected = resultGemini?.nutrition_corrected;
  const nutritionError = resultGemini?.nutrition_error;
  const nutritionDbMatches = resultGemini?.nutrition_db_matches;
  const personalizedMatches = resultGemini?.personalized_matches;
  const flashCaption = resultGemini?.flash_caption;
  const referenceImage = resultGemini?.reference_image;
  const currentStep = resultGemini?.phase || 0;
  const identificationConfirmed =
    resultGemini?.identification_confirmed || false;

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
              identificationData={identificationData}
              nutritionData={nutritionData}
              currentStep={currentStep}
              identificationConfirmed={identificationConfirmed}
              viewStep={viewStep}
              onSelectStep={setViewStep}
            />

            {pollingIdentification && viewStep === null && (
              <AnalysisLoading message="Analyzing dish components..." />
            )}

            {identificationError && !identificationData && viewStep === null && (
              <PhaseErrorCard
                headline="Component identification failed"
                error={identificationError}
                onRetry={handleIdentificationRetry}
                isRetrying={retryingIdentification}
              />
            )}

            {((viewStep === 1 && identificationData) ||
              (viewStep === null &&
                currentStep === 1 &&
                identificationData &&
                !pollingIdentification)) && (
              <>
                <PersonalizedDataCard
                  flashCaption={flashCaption}
                  referenceImage={referenceImage}
                />
                <IdentificationComponentEditor
                  identificationData={identificationData}
                  confirmedData={confirmedIdentificationData}
                  onConfirm={handleIdentificationConfirmation}
                  isConfirming={confirming}
                />
              </>
            )}

            {identificationConfirmed &&
              pollingNutrition &&
              !nutritionData &&
              !nutritionError &&
              viewStep === null && (
                <AnalysisLoading message="Calculating nutritional values..." />
              )}

            {nutritionError && !nutritionData && viewStep === null && (
              <PhaseErrorCard
                headline="Nutritional analysis failed"
                error={nutritionError}
                onRetry={handleNutritionRetry}
                isRetrying={retryingNutrition}
              />
            )}

            {((viewStep === 2 && nutritionData) ||
              (viewStep === null && currentStep === 2 && nutritionData)) && (
              <>
                <ResearchOnlyGroup>
                  <ReasoningPanel nutritionData={nutritionData} />
                  <Top5DbMatches
                    matches={nutritionDbMatches?.nutrition_matches}
                  />
                  <PersonalizationMatches matches={personalizedMatches} />
                </ResearchOnlyGroup>
                <NutritionResults
                  nutritionData={nutritionData}
                  nutritionCorrected={nutritionCorrected}
                  onEditSave={handleNutritionCorrection}
                  saving={saving}
                  onAiAssistSubmit={handleAiAssistantCorrection}
                  aiAssisting={aiAssisting}
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default ItemV2;
