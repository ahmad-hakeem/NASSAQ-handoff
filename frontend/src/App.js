import "@/App.css";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import { NassaqAlertProvider } from "./components/ui/NassaqAlertDialog";
import ErrorBoundary from "./components/ErrorBoundary";
import { GenericNameGuard } from "./components/GenericNameGuard";
import AppRoutes from "./routes/appRoutes";

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <WebSocketProvider>
            <NassaqAlertProvider>
              <BrowserRouter>
                <GenericNameGuard>
                  <AppRoutes />
                </GenericNameGuard>
                <Toaster position="top-center" richColors />
              </BrowserRouter>
            </NassaqAlertProvider>
          </WebSocketProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
