if (process.env.NODE_ENV === 'test' || process.env.JEST_WORKER_ID) {
  module.exports = function () {};
  return;
}
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  app.use(
    '/api',
    createProxyMiddleware({
      target: 'http://localhost:8000',
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
      target: 'http://localhost:8000',
      changeOrigin: true,
    })
  );
};
