import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import apiService from '../services/api';
import {
    DashboardHeader,
    MonthNavigation,
    CalendarGrid,
    EmptyState
} from '../components/dashboard';

/**
 * Dashboard Page Component
 *
 * Main dashboard page that displays the dish healthiness calendar.
 * Orchestrates sub-components for header, navigation, and calendar display.
 */
const Dashboard = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const [calendarData, setCalendarData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    const currentYear = searchParams.get('year');
    const currentMonth = searchParams.get('month');

    useEffect(() => {
        // Set timezone cookie
        const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
        document.cookie = `timezone=${timezone};path=/;max-age=86400;samesite=Lax`;

        loadDashboardData();
    }, [currentYear, currentMonth]);

    const loadDashboardData = async () => {
        try {
            setLoading(true);
            const data = await apiService.getDashboardData(
                currentYear,
                currentMonth
            );
            setCalendarData(data);
            setError(null);
        } catch (err) {
            setError('Failed to load dashboard data');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const navigateToDate = (year, month, day) => {
        navigate(`/date/${year}/${month}/${day}`);
    };

    const navigateToMonth = (year, month) => {
        navigate(`/dashboard?year=${year}&month=${month}`);
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl">Loading...</div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="text-xl text-red-600">{error}</div>
            </div>
        );
    }

    if (!calendarData) return null;

    // Calculate total records
    const totalRecords = calendarData.calendar_data
        .flat()
        .reduce((sum, day) => sum + (day.count || 0), 0);

    return (
        <div className="min-h-screen bg-gray-100 p-4">
            <div className="max-w-7xl mx-auto bg-white rounded-lg shadow-lg p-6">
                {/* Header */}
                <DashboardHeader />

                {/* Month Navigation */}
                <MonthNavigation
                    monthName={calendarData.month_name}
                    displayYear={calendarData.display_year}
                    onPrevious={() => navigateToMonth(
                        calendarData.prev_year,
                        calendarData.prev_month
                    )}
                    onNext={() => navigateToMonth(
                        calendarData.next_year,
                        calendarData.next_month
                    )}
                />

                {/* Calendar Grid */}
                <CalendarGrid
                    weekdays={calendarData.weekdays}
                    calendarData={calendarData.calendar_data}
                    displayYear={calendarData.display_year}
                    displayMonth={calendarData.display_month}
                    onDayClick={navigateToDate}
                />

                {/* Empty State */}
                {totalRecords === 0 && <EmptyState />}
            </div>
        </div>
    );
};

export default Dashboard;
