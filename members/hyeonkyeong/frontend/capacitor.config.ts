import type { CapacitorConfig } from "@capacitor/cli";

// 서버가 http(노트북)라서 웹뷰도 http 스킴으로 띄워 혼합 콘텐츠 차단을 피한다.
const config: CapacitorConfig = {
  appId: "com.stockrulekeeper.app",
  appName: "StockRuleKeeper",
  webDir: "dist",
  server: { androidScheme: "http", cleartext: true },
};

export default config;
