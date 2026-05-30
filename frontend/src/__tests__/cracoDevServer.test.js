/**
 * Regression guard for the CRA <-> webpack-dev-server v5 compatibility shim in
 * `frontend/craco.config.js`.
 *
 * Why this test exists
 * --------------------
 * react-scripts 5.0.1 (Create React App) emits a webpack-dev-server *v4* config
 * (`onBeforeSetupMiddleware`, `onAfterSetupMiddleware`, top-level `https`). This
 * project pins webpack-dev-server to v5 via a security resolution. v5 removed
 * those keys and hard-fails schema validation when they are present. The shim in
 * craco.config.js translates the v4 keys into the v5 API.
 *
 * This is exactly the mismatch that silently broke the dev preview before. To
 * stop a future webpack-dev-server bump (or a CRA config change) from breaking
 * it again *silently*, this test:
 *   1. Feeds the shim a realistic CRA v4 dev-server config.
 *   2. Asserts the legacy keys are stripped and translated correctly.
 *   3. Validates the transformed config against webpack-dev-server's OWN
 *      `options.json` schema using `schema-utils` (the same validator wds uses
 *      internally). The schema has `additionalProperties: false`, so any stale
 *      key the shim fails to strip, or any v5 schema change, fails this test
 *      instead of crashing the dev server at runtime.
 */

const path = require('path');
const { validate } = require('schema-utils');
// eslint-disable-next-line import/no-extraneous-dependencies
const wdsSchema = require('webpack-dev-server/lib/options.json');

const cracoConfig = require(path.resolve(__dirname, '../../craco.config.js'));

// Mirrors what react-scripts/config/webpackDevServer.config.js produces for v4.
function makeCraV4Config() {
  return {
    allowedHosts: 'all',
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': '*',
      'Access-Control-Allow-Headers': '*',
    },
    compress: true,
    static: {
      directory: '/app/public',
      publicPath: ['/'],
      watch: { ignored: [] },
    },
    client: {
      webSocketURL: { hostname: '', pathname: '', port: '' },
      overlay: { errors: true, warnings: false },
    },
    devMiddleware: { publicPath: '' },
    https: false,
    host: '0.0.0.0',
    historyApiFallback: { disableDotRule: true, index: '/' },
    proxy: undefined,
    onBeforeSetupMiddleware(devServer) {
      devServer.__beforeCalled = true;
    },
    onAfterSetupMiddleware(devServer) {
      devServer.__afterCalled = true;
    },
  };
}

describe('craco dev-server v5 compatibility shim', () => {
  test('exposes a devServer transform function', () => {
    expect(typeof cracoConfig.devServer).toBe('function');
  });

  test('strips legacy v4 keys and translates them to the v5 API', () => {
    const out = cracoConfig.devServer(makeCraV4Config());

    expect(out).not.toHaveProperty('onBeforeSetupMiddleware');
    expect(out).not.toHaveProperty('onAfterSetupMiddleware');
    expect(out).not.toHaveProperty('https');

    expect(typeof out.setupMiddlewares).toBe('function');
    // https:false -> server:'http'
    expect(out.server).toBe('http');
  });

  test('translates an https object into the v5 server.type shape', () => {
    const cfg = makeCraV4Config();
    cfg.https = { key: 'k', cert: 'c' };
    const out = cracoConfig.devServer(cfg);
    expect(out.https).toBeUndefined();
    expect(out.server).toEqual({ type: 'https', options: { key: 'k', cert: 'c' } });
  });

  test('setupMiddlewares runs the legacy before/after hooks', () => {
    const out = cracoConfig.devServer(makeCraV4Config());
    const devServer = {};
    const middlewares = out.setupMiddlewares([], devServer);
    expect(Array.isArray(middlewares)).toBe(true);
    expect(devServer.__beforeCalled).toBe(true);
    expect(devServer.__afterCalled).toBe(true);
  });

  test('disables the HMR websocket client/server for the Replit proxy', () => {
    const out = cracoConfig.devServer(makeCraV4Config());
    expect(out.webSocketServer).toBe(false);
    expect(out.liveReload).toBe(false);
    expect(out.hot).toBe(false);
    expect(out.client).toBe(false);
  });

  test('emits the hardened security headers', () => {
    const out = cracoConfig.devServer(makeCraV4Config());
    expect(out.headers['X-Content-Type-Options']).toBe('nosniff');
    expect(out.headers['X-Frame-Options']).toBe('DENY');
    expect(out.headers['Content-Security-Policy']).toContain("frame-ancestors 'none'");
  });

  test('transformed config passes webpack-dev-server v5 schema validation', () => {
    const out = cracoConfig.devServer(makeCraV4Config());
    // schema-utils throws ValidationError if the config is invalid for v5.
    // additionalProperties:false means any un-stripped legacy key fails here.
    expect(() => validate(wdsSchema, out, { name: 'Dev Server' })).not.toThrow();
  });
});
