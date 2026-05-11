import "@/App.css";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider } from "./contexts/AuthContext";
import { ThemeProvider } from "./contexts/ThemeContext";
import { WebSocketProvider } from "./contexts/WebSocketContext";
import { ParentActiveStudentProvider } from "./contexts/ParentActiveStudentContext";
import { NassaqAlertProvider } from "./components/ui/NassaqAlertDialog";
import { MfaStepUpProvider } from "./contexts/MfaStepUpContext";
import ErrorBoundary from "./components/ErrorBoundary";
import { GenericNameGuard } from "./components/GenericNameGuard";
import AppRoutes from "./routes/appRoutes";
import { BetaBanner } from "./components/BetaDisclaimer";

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <AuthProvider>
          <WebSocketProvider>
            <NassaqAlertProvider>
              <MfaStepUpProvider>
                <BrowserRouter>
                  {/* ParentActiveStudentProvider lives inside BrowserRouter
                      so it can read the current URL on mount and resolve
                      deep links before any page renders. */}
                  <ParentActiveStudentProvider>
                    <BetaBanner />
                    <GenericNameGuard>
                      <AppRoutes />
                    </GenericNameGuard>
                    <Toaster />
                  </ParentActiveStudentProvider>
                </BrowserRouter>
              </MfaStepUpProvider>
            </NassaqAlertProvider>
          </WebSocketProvider>
        </AuthProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
