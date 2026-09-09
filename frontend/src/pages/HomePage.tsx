import { Link, useNavigate } from "react-router-dom";

import { useAuthStore } from "../store/auth";

export function HomePage() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated());
  const clear = useAuthStore((state) => state.clear);
  const navigate = useNavigate();

  function logout() {
    clear();
    navigate("/login", { replace: true });
  }

  return (
    <main className="card">
      <h1>Attlytics</h1>
      <p className="subtitle">
        {isAuthenticated
          ? "You are logged in."
          : "Log in to view your activity."}
      </p>

      {isAuthenticated ? (
        <button onClick={logout}>Log out</button>
      ) : (
        <div className="row" style={{ justifyContent: "space-between" }}>
          <Link to="/login">Log in</Link>
          <Link to="/register">Create account</Link>
        </div>
      )}
    </main>
  );
}
