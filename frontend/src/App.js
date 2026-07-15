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
import GlobalHakimMount from "./components/hakim/GlobalHakimMount";
import { BetaBanner } from "./components/BetaDisclaimer";
import PerimeterGateBridge from "./components/PerimeterGateBridge";

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
                    <PerimeterGateBridge />
                    <BetaBanner />
                    <GenericNameGuard>
                      <AppRoutes />
                    </GenericNameGuard>
                    {/* Hakim is mounted ONCE globally (route/role rules live
                        inside GlobalHakimMount) — never mount HakimAssistant
                        or HakimChatWidget from individual pages. */}
                    <GlobalHakimMount />
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
