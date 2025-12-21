import React from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../contexts/AuthContext";

/**
 * Dashboard Header Component
 *
 * Displays the page title and logout button.
 */
const DashboardHeader = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="text-center mb-6 border-b-2 border-gray-200 pb-4 relative">
      <h1 className="text-3xl font-bold text-gray-800 mb-2">
        Dish Healthiness Calendar
      </h1>
      <div className="absolute top-0 right-0 flex items-center gap-4">
        <span className="text-gray-700">Welcome, {user?.username}</span>
        <button
          onClick={handleLogout}
          className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded font-bold transition"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default DashboardHeader;
