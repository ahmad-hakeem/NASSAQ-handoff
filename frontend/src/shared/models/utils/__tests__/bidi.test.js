import { isRTLText, getTextDirection, bidiIsolate, formatBidiRange, bidiNumber } from '../bidi';

describe('bidi text utilities', () => {
  test('isRTLText detects Arabic and Hebrew characters', () => {
    expect(isRTLText('احمد المعلم')).toBe(true);
    expect(isRTLText('Mathematics')).toBe(false);
    expect(isRTLText('Math (الرياضيات)')).toBe(true);
    expect(isRTLText('12345')).toBe(false);
    expect(isRTLText('')).toBe(false);
    expect(isRTLText(null)).toBe(false);
  });

  test('getTextDirection identifies first strong directional character', () => {
    expect(getTextDirection('احمد')).toBe('rtl');
    expect(getTextDirection('Ahmed')).toBe('ltr');
    expect(getTextDirection('  #123 احمد')).toBe('rtl');
    expect(getTextDirection('  #123 Ahmed')).toBe('ltr');
    expect(getTextDirection('12345', 'rtl')).toBe('rtl');
    expect(getTextDirection('', 'ltr')).toBe('ltr');
  });

  test('bidiIsolate wraps text in unicode isolation characters', () => {
    expect(bidiIsolate('احمد')).toBe('\u2068احمد\u2069');
    expect(bidiIsolate('John')).toBe('\u2068John\u2069');
    expect(bidiIsolate('')).toBe('');
    expect(bidiIsolate(null)).toBe('');
  });

  test('formatBidiRange preserves LTR range format without hyphen flipping', () => {
    const range = formatBidiRange('08:00', '08:45', '-');
    expect(range).toBe('\u206608:00 - 08:45\u2069');
  });

  test('bidiNumber embeds LTR code or number', () => {
    expect(bidiNumber('A-2')).toBe('\u2066A-2\u2069');
    expect(bidiNumber(100)).toBe('\u2066100\u2069');
  });
});
