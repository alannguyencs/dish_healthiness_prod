import React, { useRef } from 'react';
import { useNavigate } from 'react-router-dom';

export const MealUploadSlot = ({ dishPosition, dishData, uploading, onFileUpload }) => {
    const fileInputRef = useRef(null);
    const navigate = useNavigate();
    
    const handleClick = () => {
        if (dishData?.has_data && dishData?.record_id) {
            // Navigate to item page if data exists
            navigate(`/item/${dishData.record_id}`);
        } else {
            // Open file picker if no data
            fileInputRef.current?.click();
        }
    };

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        if (file) {
            onFileUpload(dishPosition, file);
        }
    };

    const isUploading = uploading === dishPosition;
    const displayImageUrl = dishData?.image_url ? 
        `${process.env.REACT_APP_API_URL || 'http://localhost:2512'}${dishData.image_url}` 
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
                    ${dishData?.has_data 
                        ? 'border-green-500 bg-green-50 hover:bg-green-100' 
                        : 'border-gray-300 bg-gray-50 hover:bg-gray-100'
                    }
                    ${isUploading ? 'opacity-50 cursor-wait' : ''}
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

