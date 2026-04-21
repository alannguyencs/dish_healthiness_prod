import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

export const MealUploadSlot = ({
  dishPosition,
  dishData,
  uploading,
  onFileUpload,
  onUrlUpload,
}) => {
  const fileInputRef = useRef(null);
  const navigate = useNavigate();
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [imageUrl, setImageUrl] = useState("");

  const handleClick = () => {
    if (dishData?.has_data && dishData?.record_id) {
      navigate(`/item/${dishData.record_id}`);
    } else if (!showUrlInput) {
      fileInputRef.current?.click();
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      onFileUpload(dishPosition, file);
    }
  };

  const handleUrlSubmit = (e) => {
    e.preventDefault();
    if (imageUrl.trim()) {
      onUrlUpload(dishPosition, imageUrl.trim());
    }
  };

  const isUploading = uploading === dishPosition;
  const displayImageUrl = dishData?.image_url
    ? `${process.env.REACT_APP_API_URL || "http://localhost:2612"}${dishData.image_url}`
    : null;

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold text-gray-700">
        Dish {dishPosition}
      </h3>

      <div
        onClick={handleClick}
        className={`
          relative w-full h-48 rounded-lg border-2 border-dashed
          flex items-center justify-center cursor-pointer
          transition-all duration-200
          ${
            dishData?.has_data
              ? "border-green-500 bg-green-50 hover:bg-green-100"
              : "border-gray-300 bg-gray-50 hover:bg-gray-100"
          }
          ${isUploading ? "opacity-50 cursor-wait" : ""}
        `}
      >
        {isUploading ? (
          <div className="flex flex-col items-center space-y-2">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="text-sm text-gray-600">Uploading...</p>
          </div>
        ) : displayImageUrl ? (
          <img
            src={displayImageUrl}
            alt={`Dish ${dishPosition}`}
            className="w-full h-full object-cover rounded-lg"
          />
        ) : (
          <div className="flex flex-col items-center space-y-2">
            <svg
              className="w-12 h-12 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 4v16m8-8H4"
              />
            </svg>
            <p className="text-sm text-gray-600">Click to upload</p>
          </div>
        )}
      </div>

      {!dishData?.has_data && !isUploading && (
        <div className="space-y-2">
          {!showUrlInput ? (
            <button
              type="button"
              onClick={() => setShowUrlInput(true)}
              className="w-full text-sm text-blue-600 hover:text-blue-700 py-1"
            >
              Or paste image URL
            </button>
          ) : (
            <form onSubmit={handleUrlSubmit} className="space-y-2">
              <input
                type="url"
                value={imageUrl}
                onChange={(e) => setImageUrl(e.target.value)}
                placeholder="https://example.com/image.jpg"
                className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={!imageUrl.trim()}
                  className="flex-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  Load
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowUrlInput(false);
                    setImageUrl("");
                  }}
                  className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileChange}
        className="hidden"
      />
    </div>
  );
};
