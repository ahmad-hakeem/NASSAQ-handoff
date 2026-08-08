import "@/App.css";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "@/shared/components/ui/sonner";
import { AuthProvider } from "@/shared/contexts/AuthContext";
import { ThemeProvider } from "@/shared/contexts/ThemeContext";
import { WebSocketProvider } from "@/shared/contexts/WebSocketContext";
import { ParentActiveStudentProvider } from "@/shared/contexts/ParentActiveStudentContext";
import { NassaqAlertProvider } from "@/shared/components/ui/NassaqAlertDialog";
import { MfaStepUpProvider } from "@/shared/contexts/MfaStepUpContext";
import ErrorBoundary from "@/shared/components/ErrorBoundary";
import { GenericNameGuard } from "@/shared/components/GenericNameGuard";
import AppRoutes from "./routes/appRoutes";
import GlobalHakimMount from "@/features/hakim/components/hakim/GlobalHakimMount";
import { BetaBanner } from "@/shared/components/BetaDisclaimer";
import PerimeterGateBridge from "@/shared/components/PerimeterGateBridge";

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
