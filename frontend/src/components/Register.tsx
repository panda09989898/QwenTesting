/** Register page component. */
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuthStore, useThemeStore } from '../../store';
import apiService from '../../services/api';

export default function Register() {
  const navigate = useNavigate();
  const { setUser, setToken } = useAuthStore();
  const { isDark, toggleTheme } = useThemeStore();
  
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await apiService.register(email, username, password);
      
      // Auto-login after registration
      const loginResponse = await apiService.login(email, password);
      if (loginResponse.access_token) {
        setToken(loginResponse.access_token);
        const user = await apiService.getCurrentUser();
        setUser(user);
        localStorage.setItem('user', JSON.stringify(user));
        navigate('/');
      }
    } catch (err: unknown) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      setError(errorObj.response?.data?.detail || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-dark-bg py-12 px-4">
      <div className="absolute top-4 right-4">
        <button onClick={toggleTheme} className="p-2 rounded-lg bg-gray-200 dark:bg-dark-surface">
          {isDark ? '☀️' : '🌙'}
        </button>
      </div>
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="text-center text-3xl font-extrabold text-gray-900 dark:text-white">
            Create your account
          </h2>
        </div>
        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="rounded-md bg-red-50 dark:bg-red-900/20 p-4">
              <p className="text-sm text-red-800 dark:text-red-200">{error}</p>
            </div>
          )}
          <div className="space-y-4">
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md dark:bg-dark-surface dark:text-white"
              placeholder="Email address"
            />
            <input
              type="text"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md dark:bg-dark-surface dark:text-white"
              placeholder="Username"
            />
            <input
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-dark-border rounded-md dark:bg-dark-surface dark:text-white"
              placeholder="Password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
          >
            {loading ? 'Creating account...' : 'Register'}
          </button>
          <div className="text-center">
            <Link to="/login" className="text-primary-600 dark:text-primary-400">
              Already have an account? Sign in
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
