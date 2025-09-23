import { useState, useEffect } from 'react';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import './App.css';


import axios from 'axios';
axios.interceptors.request.use(config => {
    const token = localStorage.getItem('authToken');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

function App() {
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem('authToken');
        if (token) {
            setIsAuthenticated(true);
        }
        setIsLoading(false);
    }, []);

    const handleLoginSuccess = () => {
        setIsAuthenticated(true);
    };

    const handleLogout = () => {
        localStorage.removeItem('authToken');
        setIsAuthenticated(false);
    };

    if (isLoading) {
        return <div>Yuklanmoqda...</div>; // Token tekshirilayotganda
    }

    return (
        <div>
            {isAuthenticated ? (
                <Dashboard handleLogout={handleLogout} />
            ) : (
                <Login onLoginSuccess={handleLoginSuccess} />
            )}
        </div>
    );
}

export default App;
