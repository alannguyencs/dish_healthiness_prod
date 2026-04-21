import React from "react";

export const ItemImage = ({ imageUrl }) => {
  const displayImageUrl = imageUrl
    ? `${process.env.REACT_APP_API_URL || "http://localhost:2612"}${imageUrl}`
    : null;

  return (
    <div className="space-y-2">
      <h3 className="text-lg font-semibold text-gray-700">Dish Image</h3>
      {displayImageUrl ? (
        <img
          src={displayImageUrl}
          alt="Dish"
          className="w-full h-auto rounded-lg shadow-md"
          onError={(e) => {
            e.target.onerror = null;
            e.target.src =
              'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect width="400" height="300" fill="%23f0f0f0"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="Arial" font-size="18" fill="%23999"%3EImage not available%3C/text%3E%3C/svg%3E';
          }}
        />
      ) : (
        <div className="w-full h-64 bg-gray-200 rounded-lg flex items-center justify-center">
          <p className="text-gray-500">No image available</p>
        </div>
      )}
    </div>
  );
};
