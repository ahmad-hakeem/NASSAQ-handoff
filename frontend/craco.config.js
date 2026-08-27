// craco.config.js
const path = require("path");
require("dotenv").config();

// SECURITY (audit M-3): production builds must never honour
// DANGEROUSLY_DISABLE_HOST_CHECK. CRA only consumes the flag in the dev
// server, but defense-in-depth: hard-fail any production build that has it
// set to true.
if (process.env.NODE_ENV === "production" && String(process.env.DANGEROUSLY_DISABLE_HOST_CHECK).toLowerCase() === "true") {
  console.error(
    "REFUSING TO BUILD: DANGEROUSLY_DISABLE_HOST_CHECK=true is forbidden in production builds. " +
    "Unset it in the deployment environment before retrying."
  );
  process.exit(1);
}

// Environment variable overrides
const config = {
  enableHealthCheck: process.env.ENABLE_HEALTH_CHECK === "true",
};

// Conditionally load health check modules only if enabled
let WebpackHealthPlugin;
let setupHealthEndpoints;
let healthPluginInstance;

if (config.enableHealthCheck) {
  WebpackHealthPlugin = require("./plugins/health-check/webpack-health-plugin");
  setupHealthEndpoints = require("./plugins/health-check/health-endpoints");
  healthPluginInstance = new WebpackHealthPlugin();
}

let webpackConfig = {
  eslint: {
    enable: false,
  },
  jest: {
    configure: (jestConfig) => {
      // react-router-dom v7 ships a broken `main` ("./dist/main.js" does
      // not exist) and relies on the `exports` map, which CRA's jest 27
      // resolver does not read. Map the bare specifier to the real CJS
      // entry so unmocked imports resolve in tests.
      jestConfig.moduleNameMapper = {
        '^react-router-dom$': path.resolve(
          __dirname,
          'node_modules/react-router-dom/dist/index.js',
        ),
        '.*http-proxy-agent.*': path.resolve(
          __dirname,
          'src/testUtils/httpProxyAgentMock.js',
        ),
        '.*@tootallnate/once.*': path.resolve(
          __dirname,
          'src/testUtils/onceMock.js',
        ),
        ...(jestConfig.moduleNameMapper || {}),
      };
      jestConfig.transformIgnorePatterns = [
        '[/\\\\]node_modules[/\\\\](?!(@tootallnate/once|http-proxy-agent)/).+\\.(js|jsx|mjs|cjs|ts|tsx)$',
      ];
      return jestConfig;
    },
  },
  webpack: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
    configure: (webpackConfig) => {

      // Add ignored patterns to reduce watched directories
        webpackConfig.watchOptions = {
          ...webpackConfig.watchOptions,
          ignored: [
            '**/node_modules/**',
            '**/.git/**',
            '**/build/**',
            '**/dist/**',
            '**/coverage/**',
            '**/public/**',
        ],
      };

      // Add health check plugin to webpack if enabled
      if (config.enableHealthCheck && healthPluginInstance) {
        webpackConfig.plugins.push(healthPluginInstance);
      }
      return webpackConfig;
    },
  },
};

webpackConfig.devServer = (devServerConfig) => {
  devServerConfig.host = "0.0.0.0";
  devServerConfig.port = 5000;
  devServerConfig.allowedHosts = "all";

  // COMPAT: react-scripts 5.0.1 emits a webpack-dev-server v4 config that uses
  // the `onBeforeSetupMiddleware` / `onAfterSetupMiddleware` hooks. This project
  // pins webpack-dev-server to v5 (security resolution), which removed those
  // hooks in favour of a single `setupMiddlewares(middlewares, devServer)` and
  // hard-fails schema validation if the old keys are present:
  //   "options has an unknown property 'onAfterSetupMiddleware'".
  // We translate the two legacy hooks into the v5 API and strip the old keys so
  // CRA's dev middleware (eval-source-map, proxy setup, served-path redirect,
  // no-op service worker) keeps working without downgrading webpack-dev-server.
  //
  // This shim is the documented stabilization of the CRA/wds-v5 mismatch — see
  // docs/frontend-toolchain.md. webpack-dev-server is pinned to an EXACT version
  // in package.json (resolutions + overrides) so the schema this shim targets
  // cannot drift silently on a fresh install. The transform below is covered by
  // src/__tests__/cracoDevServer.test.js, which validates the result against
  // webpack-dev-server's own options schema; run that test before bumping wds.
  const legacyBefore = devServerConfig.onBeforeSetupMiddleware;
  const legacyAfter = devServerConfig.onAfterSetupMiddleware;
  delete devServerConfig.onBeforeSetupMiddleware;
  delete devServerConfig.onAfterSetupMiddleware;

  // COMPAT: webpack-dev-server v5 dropped the top-level `https` option in favour
  // of `server: { type: 'https', options }`. react-scripts 5.0.1 still emits
  // `https`, which v5 rejects as an unknown property. Translate it and strip the
  // legacy key. The Replit preview terminates TLS upstream, so the dev server
  // itself runs plain HTTP unless HTTPS is explicitly requested.
  if ("https" in devServerConfig) {
    const httpsValue = devServerConfig.https;
    delete devServerConfig.https;
    if (httpsValue && typeof httpsValue === "object") {
      devServerConfig.server = { type: "https", options: httpsValue };
    } else if (httpsValue === true) {
      devServerConfig.server = "https";
    } else {
      devServerConfig.server = "http";
    }
  }

  if (legacyBefore || legacyAfter) {
    const craSetupMiddlewares = devServerConfig.setupMiddlewares;
    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      if (devServer && !devServer.close && typeof devServer.stop === "function") {
        devServer.close = function (cb) {
          devServer.stop().then(() => { if (cb) cb(); }).catch(() => { if (cb) cb(); });
        };
      }
      if (typeof legacyBefore === "function") {
        legacyBefore(devServer);
      }
      if (typeof craSetupMiddlewares === "function") {
        middlewares = craSetupMiddlewares(middlewares, devServer);
      }
      if (typeof legacyAfter === "function") {
        legacyAfter(devServer);
      }
      return middlewares;
    };
  }

  // Replit preview is an iframe-proxied (mTLS) tunnel that does not relay
  // WebSocket upgrade frames on custom paths reliably — webpack-dev-server's
  // HMR client errored with "Invalid frame header" on every reconnect and
  // spammed the browser console. We disable the HMR client/server entirely:
  // the dev bundle still compiles on file change, and a manual page refresh
  // picks up the new build. This is a Replit-environment trade-off, not a
  // product change.
  devServerConfig.webSocketServer = false;
  devServerConfig.liveReload = false;
  devServerConfig.hot = false;
  devServerConfig.client = false;

  devServerConfig.headers = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Content-Security-Policy":
      "default-src 'self'; " +
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
      "font-src 'self' https://fonts.gstatic.com data:; " +
      "img-src 'self' data: blob: https:; " +
      "media-src 'self' https:; " +
      "connect-src 'self' wss: ws: http://localhost:8000 http://localhost:5000 https://uat.nassaqapp.com https://*.nassaqapp.com wss://*.nassaqapp.com; " +
      "frame-ancestors 'none';",
    "Cache-Control": "public, max-age=0, must-revalidate",
  };

  // Add health check endpoints if enabled
  if (config.enableHealthCheck && setupHealthEndpoints && healthPluginInstance) {
    const originalSetupMiddlewares = devServerConfig.setupMiddlewares;

    devServerConfig.setupMiddlewares = (middlewares, devServer) => {
      // Call original setup if exists
      if (originalSetupMiddlewares) {
        middlewares = originalSetupMiddlewares(middlewares, devServer);
      }

      // Setup health endpoints
      setupHealthEndpoints(devServer, healthPluginInstance);

      return middlewares;
    };
  }

  return devServerConfig;
};

module.exports = webpackConfig;
