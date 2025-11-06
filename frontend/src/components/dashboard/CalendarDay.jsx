import React from 'react';

/**
 * Calendar Day Component
 *
 * Displays a single day cell in the calendar with record count.
 */
const CalendarDay = ({ dayInfo, displayYear, displayMonth, onDayClick }) => {
    if (!dayInfo.is_current_month) {
        return (
            <div className="h-full p-2 bg-gray-50">
                {dayInfo.day !== 0 && (
                    <div className="text-gray-400">{dayInfo.day}</div>
                )}
            </div>
        );
    }

    const hasRecords = dayInfo.count > 0;

    return (
        <div
            className={`h-full p-2 cursor-pointer transition ${
                dayInfo.is_today
                    ? 'bg-blue-50 border-2 border-blue-500'
                    : ''
            } hover:bg-gray-50`}
            onClick={() => onDayClick(displayYear, displayMonth, dayInfo.day)}
        >
            <div
                className={`font-bold mb-1 ${
                    dayInfo.is_today
                        ? 'text-blue-600'
                        : 'text-gray-800'
                }`}
            >
                {dayInfo.day}
            </div>
            {hasRecords && (
                <div className="flex flex-col items-center justify-center mt-2">
                    <div className="text-3xl">🥘</div>
                    <div className="text-xs text-gray-600 mt-1">
                        {dayInfo.count} {dayInfo.count === 1 ? 'dish' : 'dishes'}
                    </div>
                </div>
            )}
        </div>
    );
};

export default CalendarDay;

