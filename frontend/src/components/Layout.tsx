/** Layout component with navigation. */
import { Outlet, Link, useNavigate } from 'react-router-dom';
import { useAuthStore, useThemeStore } from '../store';
import apiService from '../services/api';

export default function Layout() {
  const navigate = useNavigate();
  const { user, logout, isAuthenticated } = useAuthStore();
  const { isDark, toggleTheme } = useThemeStore();

  const handleLogout = () => {
    logout();
    apiService.logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-dark-bg">
      <nav className="bg-white dark:bg-dark-surface shadow-sm border-b dark:border-dark-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="text-xl font-bold text-primary-600">
                CollabNotes
              </Link>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={toggleTheme}
                className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-dark-border"
              >
                {isDark ? '☀️' : '🌙'}
              </button>
              {isAuthenticated && (
                <>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    {user?.username || user?.email}
                  </span>
                  <button
                    onClick={handleLogout}
                    className="px-4 py-2 text-sm text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-md"
                  >
                    Logout
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>
      <main className="py-6">
        <Outlet />
      </main>
    </div>
  );
}
