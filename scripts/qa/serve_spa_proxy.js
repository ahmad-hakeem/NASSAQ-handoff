/**
 * Serve frontend/build as a SPA with /api requests proxied to the backend.
 * Usage: node scripts/qa/serve_spa_proxy.js [port]
 */
const http = require('http');
const fs = require('fs');
const path = require('path');

const BUILD_DIR = path.join(__dirname, '../../frontend/build');
const BACKEND_PORT = 8000;
const PORT = Number(process.argv[2]) || 5050;

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
};

function proxyToBackend(req, res) {
  const opts = {
    hostname: '127.0.0.1',
    port: BACKEND_PORT,
    path: req.url,
    method: req.method,
    headers: { ...req.headers, host: `127.0.0.1:${BACKEND_PORT}` },
  };
  const pr = http.request(opts, (backRes) => {
    res.writeHead(backRes.statusCode, backRes.headers);
    backRes.pipe(res);
  });
  pr.on('error', (e) => {
    res.writeHead(502);
    res.end(`Proxy error: ${e.message}`);
  });
  req.pipe(pr);
}

const server = http.createServer((req, res) => {
  // Proxy all /api/* and /healthz to the backend
  if (req.url.startsWith('/api/') || req.url === '/healthz' || req.url === '/readyz') {
    return proxyToBackend(req, res);
  }

  // Serve static files from build dir; fall back to index.html for SPA routing
  const urlPath = req.url.split('?')[0].split('#')[0];
  let filePath = path.join(BUILD_DIR, urlPath);

  // Security: prevent path traversal
  if (!filePath.startsWith(BUILD_DIR)) {
    res.writeHead(403);
    return res.end('Forbidden');
  }

  if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    filePath = path.join(BUILD_DIR, 'index.html');
  }

  const ext = path.extname(filePath);
  const contentType = MIME[ext] || 'application/octet-stream';
  res.writeHead(200, { 'Content-Type': contentType });
  fs.createReadStream(filePath).pipe(res);
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`SPA proxy server listening on http://127.0.0.1:${PORT}`);
  console.log(`Serving: ${BUILD_DIR}`);
  console.log(`Backend: http://127.0.0.1:${BACKEND_PORT}`);
});

server.on('error', (e) => {
  console.error('Server error:', e.message);
  process.exit(1);
});
