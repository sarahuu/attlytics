import { Routes, Route } from "react-router-dom";

import { RequireAuth } from "./components/RequireAuth";
import { DeviceRegisterPage } from "./pages/DeviceRegisterPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/device/register"
        element={
          <RequireAuth>
            <DeviceRegisterPage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

function NotFound() {
  return <main className="card"><h1>404</h1><p>Page not found.</p></main>;
}
