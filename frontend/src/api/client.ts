import axios from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send auth cookie automatically
});

// Redirect to /login on 401
api.interceptors.response.use(
  (r) => r,
  (error) => {
    const pathname = (window.location.pathname || "").replace(/\/+$/, "") || "/";
    const isLoginRoute = pathname === "/login" || pathname.startsWith("/login/");
    if (error.response?.status === 401 && !isLoginRoute) {
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);
