import {
  isIdempotentWriteRetry,
  normalizeRequestPath,
  IDEMPOTENT_WRITE_RETRY_RULES,
} from '../retryableWrite';

describe('normalizeRequestPath', () => {
  test('returns the bare path unchanged', () => {
    expect(normalizeRequestPath('/students/abc')).toBe('/students/abc');
  });

  test('strips a query string and hash', () => {
    expect(normalizeRequestPath('/auth/preferences?lang=ar#x')).toBe('/auth/preferences');
  });

  test('strips an absolute origin', () => {
    expect(normalizeRequestPath('https://app.example.com/api/students/abc')).toBe('/students/abc');
  });

  test('strips a leading /api prefix', () => {
    expect(normalizeRequestPath('/api/settings/general')).toBe('/settings/general');
  });

  test('trims a trailing slash', () => {
    expect(normalizeRequestPath('/students/abc/')).toBe('/students/abc');
  });

  test('empty / nullish urls resolve to empty string', () => {
    expect(normalizeRequestPath('')).toBe('');
    expect(normalizeRequestPath(undefined)).toBe('');
    expect(normalizeRequestPath(null)).toBe('');
  });
});

describe('isIdempotentWriteRetry', () => {
  test('allow-lists per-resource PUT updates', () => {
    expect(isIdempotentWriteRetry({ method: 'put', url: '/students/123' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'PUT', url: '/teachers/t-1' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/classes/c9' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/subjects/s9' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/assessments/a9' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/schools/sch1' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/product-hub/issues/i1' })).toBe(true);
  });

  test('allow-lists settings / preference saves', () => {
    expect(isIdempotentWriteRetry({ method: 'put', url: '/auth/preferences' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/auth/preferences?lang=ar' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/settings/general' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/settings/contact' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/settings/security' })).toBe(true);
  });

  test('allow-lists notification read-state writes', () => {
    expect(isIdempotentWriteRetry({ method: 'put', url: '/notifications/n1/read' })).toBe(true);
    expect(isIdempotentWriteRetry({ method: 'put', url: '/notifications/mark-all-read' })).toBe(true);
  });

  test('accepts PATCH as well as PUT for the same paths', () => {
    expect(isIdempotentWriteRetry({ method: 'patch', url: '/students/123' })).toBe(true);
  });

  test('NEVER retries POST creates', () => {
    expect(isIdempotentWriteRetry({ method: 'post', url: '/students' })).toBe(false);
    expect(isIdempotentWriteRetry({ method: 'post', url: '/teachers' })).toBe(false);
    expect(isIdempotentWriteRetry({ method: 'post', url: '/classes' })).toBe(false);
    // Even a POST whose path happens to look like an update target is excluded.
    expect(isIdempotentWriteRetry({ method: 'post', url: '/students/123' })).toBe(false);
    // The idempotent-but-handler-managed transfer POST is deliberately NOT here
    // (it owns its own retry loop), so the interceptor must not double-retry it.
    expect(isIdempotentWriteRetry({ method: 'post', url: '/students/transfer-class' })).toBe(false);
  });

  test('does not match deeper sub-resources of an allow-listed prefix', () => {
    expect(isIdempotentWriteRetry({ method: 'put', url: '/students/123/grades' })).toBe(false);
    expect(isIdempotentWriteRetry({ method: 'post', url: '/product-hub/issues/i1/comments' })).toBe(false);
  });

  test('GET and DELETE are not treated as idempotent-write retries here', () => {
    // GET retry is handled by its own branch in the interceptor.
    expect(isIdempotentWriteRetry({ method: 'get', url: '/students/123' })).toBe(false);
    // DELETE is intentionally out of the allow-list (a re-applied delete can
    // 404 and surface a confusing "already gone" error).
    expect(isIdempotentWriteRetry({ method: 'delete', url: '/students/123' })).toBe(false);
  });

  test('handles missing config / method / url defensively', () => {
    expect(isIdempotentWriteRetry(undefined)).toBe(false);
    expect(isIdempotentWriteRetry({})).toBe(false);
    expect(isIdempotentWriteRetry({ method: 'put' })).toBe(false);
    expect(isIdempotentWriteRetry({ url: '/students/123' })).toBe(false);
  });

  test('every rule is restricted to idempotent methods only (no bare POST creates)', () => {
    IDEMPOTENT_WRITE_RETRY_RULES.forEach((rule) => {
      expect(rule.methods).not.toContain('POST');
      expect(rule.methods).not.toContain('DELETE');
    });
  });
});
