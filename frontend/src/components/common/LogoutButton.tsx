import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

interface LogoutButtonProps {
  className?: string;
}

export default function LogoutButton({ className = "" }: LogoutButtonProps) {
  const navigate = useNavigate();
  const { signOut } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);

  const handleLogout = async () => {
    setIsLoggingOut(true);
    setLogoutError(null);
    try {
      await signOut();
      navigate("/login");
    } catch (error) {
      console.error("Logout failed", error);
      setLogoutError("Sign out failed. Please try again.");
    } finally {
      setIsLoggingOut(false);
    }
  };

  return (
    <>
      <button className={`btn-outline ${className}`} onClick={handleLogout} disabled={isLoggingOut}>
        {isLoggingOut ? "Signing out..." : "Sign out"}
      </button>
      {logoutError ? <p className="error">{logoutError}</p> : null}
    </>
  );
}
