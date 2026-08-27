if (process.env.NODE_ENV === 'test' || process.env.JEST_WORKER_ID) {
  module.exports = function () {};
  return;
}
const { createProxyMiddleware } = require('http-proxy-middleware');

const backendTarget = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

module.exports = function (app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: backendTarget,
      changeOrigin: true,
      ws: true,
      timeout: 30000,
      proxyTimeout: 30000,
      on: {
        error: (err, req, res) => {
          console.error('[Proxy Error]', err.message);
          if (res && res.writeHead) {
            res.writeHead(502, { 'Content-Type': 'application/json' });
            res.end(JSON.stringify({ error: 'Backend unavailable', detail: err.message }));
          }
        },
      },
    })
  );

  app.use(
    '/system',
    createProxyMiddleware({
      target: backendTarget,
      changeOrigin: true,
    })
  );
};
