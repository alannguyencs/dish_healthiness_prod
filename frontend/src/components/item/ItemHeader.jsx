import React from "react";
import { useNavigate } from "react-router-dom";

export const ItemHeader = ({ itemId, onBackClick, targetDate }) => {
  const navigate = useNavigate();

  const handleBackToDate = () => {
    if (targetDate) {
      const date = new Date(targetDate);
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      navigate(`/date/${year}/${month}/${day}`);
    } else if (onBackClick) {
      onBackClick();
    }
  };

  return (
    <div className="border-b pb-4 mb-6">
      <div className="flex items-center gap-4">
        <button
          onClick={handleBackToDate}
          className="flex items-center gap-2 px-4 py-2 bg-gray-500 hover:bg-gray-600 text-white rounded-lg transition-colors"
        >
          <svg
            className="w-5 h-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M15 19l-7-7 7-7"
            />
          </svg>
          Back to Date
        </button>
        <h1 className="text-3xl font-bold text-gray-800">
          Dish Analysis Details
        </h1>
      </div>
    </div>
  );
};
