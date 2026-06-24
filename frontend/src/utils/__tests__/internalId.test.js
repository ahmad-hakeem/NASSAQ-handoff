/**
 * Unit coverage for the centralized internal-identifier visibility helpers
 * (`utils/internalId.js`). These guard the platform rule that system-generated
 * UUIDs are only rendered for the Platform Admin; every other role gets a
 * neutral fallback while the underlying data stays untouched.
 */
import { looksLikeInternalId, maskInternalId } from '../internalId';

const SAMPLE_UUID = 'ac838e0a-1c2d-4e5f-8a9b-0c1d2e3f4a5b';
const SCREENSHOT_UUID = '16cf6b75-f53b-45c5-8a63-d3aa7ab8f7ec';

describe('looksLikeInternalId', () => {
  test('detects bare v4-style UUIDs', () => {
    expect(looksLikeInternalId(SAMPLE_UUID)).toBe(true);
    expect(looksLikeInternalId(SCREENSHOT_UUID)).toBe(true);
  });

  test('accepts uppercase hex and surrounding whitespace', () => {
    expect(looksLikeInternalId(SAMPLE_UUID.toUpperCase())).toBe(true);
    expect(looksLikeInternalId(`  ${SAMPLE_UUID}  `)).toBe(true);
  });

  test('rejects human-readable labels', () => {
    expect(looksLikeInternalId('الرياضيات')).toBe(false);
    expect(looksLikeInternalId('Mathematics')).toBe(false);
    expect(looksLikeInternalId('MATH101')).toBe(false);
  });

  test('rejects partial ids, embedded ids and non-strings', () => {
    expect(looksLikeInternalId('16cf6b75')).toBe(false);
    expect(looksLikeInternalId(`subject ${SAMPLE_UUID}`)).toBe(false);
    expect(looksLikeInternalId('')).toBe(false);
    expect(looksLikeInternalId(null)).toBe(false);
    expect(looksLikeInternalId(undefined)).toBe(false);
    expect(looksLikeInternalId(12345)).toBe(false);
  });
});

describe('maskInternalId', () => {
  test('passes everything through unchanged for viewers who may see ids', () => {
    expect(maskInternalId(SAMPLE_UUID, true)).toBe(SAMPLE_UUID);
    expect(maskInternalId('الرياضيات', true)).toBe('الرياضيات');
  });

  test('hides bare ids from non-admin viewers', () => {
    expect(maskInternalId(SAMPLE_UUID, false)).toBe('');
    expect(maskInternalId(SCREENSHOT_UUID, false)).toBe('');
  });

  test('honors a custom fallback when masking', () => {
    expect(maskInternalId(SAMPLE_UUID, false, '—')).toBe('—');
  });

  test('never masks real labels even for non-admin viewers', () => {
    expect(maskInternalId('الرياضيات', false)).toBe('الرياضيات');
    expect(maskInternalId('Mathematics', false)).toBe('Mathematics');
  });

  test('leaves non-id falsy/other values intact (no accidental fallback)', () => {
    expect(maskInternalId('', false)).toBe('');
    expect(maskInternalId(null, false)).toBeNull();
    expect(maskInternalId(undefined, false)).toBeUndefined();
    expect(maskInternalId(0, false)).toBe(0);
  });
});
