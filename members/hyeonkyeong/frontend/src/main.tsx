import { TDSMobileAITProvider } from "@toss/tds-mobile-ait";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import config from "../apps-in-toss.config.ts";
import App from "./App.tsx";
import "./index.css";
import { AppProvider } from "./store/AppContext.tsx";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <TDSMobileAITProvider brandPrimaryColor={config.brand.primaryColor}>
      <BrowserRouter>
        <AppProvider>
          <App />
        </AppProvider>
      </BrowserRouter>
    </TDSMobileAITProvider>
  </StrictMode>,
);
