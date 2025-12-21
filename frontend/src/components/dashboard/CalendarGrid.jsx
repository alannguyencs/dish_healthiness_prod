import React from "react";
import CalendarDay from "./CalendarDay";

/**
 * Calendar Grid Component
 *
 * Displays the calendar table with weekdays and day cells.
 */
const CalendarGrid = ({
  weekdays,
  calendarData,
  displayYear,
  displayMonth,
  onDayClick,
}) => {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse bg-white rounded-lg shadow">
        <thead>
          <tr>
            {weekdays.map((day) => (
              <th
                key={day}
                className="bg-blue-600 text-white font-bold p-3 border border-blue-700 text-sm"
              >
                {day}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {calendarData.map((week, weekIdx) => (
            <tr key={weekIdx}>
              {week.map((dayInfo, dayIdx) => (
                <td
                  key={dayIdx}
                  className="border border-gray-300 p-0 h-32 align-top"
                >
                  <CalendarDay
                    dayInfo={dayInfo}
                    displayYear={displayYear}
                    displayMonth={displayMonth}
                    onDayClick={onDayClick}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default CalendarGrid;
