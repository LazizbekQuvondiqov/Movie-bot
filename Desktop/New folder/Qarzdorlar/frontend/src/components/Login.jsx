import { useState } from 'react';
import axios from 'axios';

// "Ko'zcha" ikonkalari uchun kichik komponentlar
const EyeIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
);

const EyeSlashIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
    <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
    <path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
    <line x1="2" x2="22" y1="2" y2="22" />
  </svg>
);


export default function Login({ onLoginSuccess }) {
    const [name, setName] = useState('');
    const [phoneNumber, setPhoneNumber] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false); // Parolni ko'rsatish uchun state

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        setError('');
        try {
            const response = await axios.post(`${import.meta.env.VITE_API_URL}/login`, { name, phoneNumber });

            localStorage.setItem('authToken', response.data.token);
            localStorage.setItem('userName', response.data.userName);

            onLoginSuccess();
        } catch (error) {
            console.error("Login xatoligi:", error);
            setError('Ism yoki telefon raqami xato!');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="login-container">
            <form onSubmit={handleSubmit} className="login-form">
                <h2>Qarzdorlar Paneli</h2>
                <div className="form-group">
                    <label htmlFor="name">Ism</label>
                    <input
                        type="text"
                        id="name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                        autoComplete="username"
                    />
                </div>
                <div className="form-group password-group">
                    <label htmlFor="phone">Telefon raqam (parol)</label>
                    <input
                        type={showPassword ? 'text' : 'password'}
                        id="phone"
                        value={phoneNumber}
                        onChange={(e) => setPhoneNumber(e.target.value)}
                        required
                        autoComplete="current-password"
                    />
                    <button type="button" className="password-toggle-btn" onClick={() => setShowPassword(!showPassword)}>
                        {showPassword ? <EyeSlashIcon /> : <EyeIcon />}
                    </button>
                </div>
                {error && <p className="error-message">{error}</p>}
                <button type="submit" disabled={loading}>
                    {loading ? 'Tekshirilmoqda...' : 'Kirish'}
                </button>
            </form>
        </div>
    );
}
