import React from "react";

/**
 * ItemStepTabs
 *
 * Two-button progress row that lets the user toggle between the
 * identification editor view and the nutrition results view once both
 * phases have data. Disabled until the corresponding phase's data is
 * available.
 */
const ItemStepTabs = ({
  identificationData,
  nutritionData,
  currentStep,
  identificationConfirmed,
  viewStep,
  onSelectStep,
}) => {
  const step1Active =
    viewStep === 1 || (viewStep === null && currentStep === 1);
  const step2Active =
    viewStep === 2 || (viewStep === null && currentStep === 2);

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex items-center space-x-4">
        <button
          onClick={() => onSelectStep(1)}
          disabled={!identificationData}
          className={`flex-1 text-center p-3 rounded-lg transition-all ${
            step1Active
              ? "bg-blue-100 border-2 border-blue-500"
              : currentStep >= 1
                ? "bg-blue-50 border-2 border-blue-300 hover:bg-blue-100 cursor-pointer"
                : "bg-gray-100 cursor-not-allowed"
          }`}
        >
          <div className="font-semibold text-gray-800">Step 1</div>
          <div className="text-xs text-gray-600">Component Identification</div>
          {currentStep === 1 && !identificationConfirmed && (
            <div className="text-xs text-blue-600 font-medium mt-1">
              Awaiting Confirmation
            </div>
          )}
        </button>
        <div className="text-gray-400">→</div>
        <button
          onClick={() => onSelectStep(2)}
          disabled={!nutritionData}
          className={`flex-1 text-center p-3 rounded-lg transition-all ${
            step2Active
              ? "bg-green-100 border-2 border-green-500"
              : nutritionData
                ? "bg-green-50 border-2 border-green-300 hover:bg-green-100 cursor-pointer"
                : "bg-gray-100 cursor-not-allowed"
          }`}
        >
          <div className="font-semibold text-gray-800">Step 2</div>
          <div className="text-xs text-gray-600">Nutritional Analysis</div>
          {identificationConfirmed && !nutritionData && (
            <div className="text-xs text-blue-600 font-medium mt-1">
              In Progress...
            </div>
          )}
        </button>
      </div>
    </div>
  );
};

export default ItemStepTabs;
