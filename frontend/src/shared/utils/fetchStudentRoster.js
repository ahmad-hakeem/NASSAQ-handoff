const PAGE_SIZE = 1000;

/**
 * Error raised when a roster response advertises pagination that cannot be
 * followed safely. Failing loudly is preferable to silently showing a
 * truncated school/class roster.
 */
export class StudentRosterFetchError extends Error {
  constructor(message, code = 'STUDENT_ROSTER_PAGINATION_ERROR') {
    super(message);
    this.name = 'StudentRosterFetchError';
    this.code = code;
  }
}

const headerValue = (headers, name) => {
  if (!headers) return undefined;
  if (typeof headers.get === 'function') {
    const value = headers.get(name);
    return value === null ? undefined : value;
  }
  const key = Object.keys(headers).find(
    (candidate) => candidate.toLowerCase() === name.toLowerCase(),
  );
  return key === undefined ? undefined : headers[key];
};

const copyHeaders = (headers) => {
  if (!headers) return {};
  if (typeof headers.toJSON === 'function') return { ...headers.toJSON() };
  if (typeof headers.forEach === 'function') {
    const copied = {};
    headers.forEach((value, key) => {
      copied[key] = value;
    });
    return copied;
  }
  return { ...headers };
};

const setHeaderValue = (headers, name, value) => {
  headers[name] = value;
  const existingKey = Object.keys(headers).find(
    (candidate) => candidate.toLowerCase() === name.toLowerCase() && candidate !== name,
  );
  if (existingKey) headers[existingKey] = value;
};

const parseInteger = (value, label, { allowEmpty = false } = {}) => {
  if (allowEmpty && (value === undefined || value === null || value === '')) return undefined;
  if (typeof value === 'number' && Number.isInteger(value)) {
    if (Number.isSafeInteger(value)) return value;
    throw new StudentRosterFetchError(`Malformed ${label} header`);
  }
  if (typeof value === 'string' && /^\d+$/.test(value.trim())) {
    const parsed = Number(value.trim());
    if (Number.isSafeInteger(parsed)) return parsed;
  }
  throw new StudentRosterFetchError(`Malformed ${label} header`);
};

const parseBoolean = (value, label) => {
  if (value === undefined || value === null || value === '') return undefined;
  if (value === true || value === 1 || value === '1' || String(value).toLowerCase() === 'true') {
    return true;
  }
  if (value === false || value === 0 || value === '0' || String(value).toLowerCase() === 'false') {
    return false;
  }
  throw new StudentRosterFetchError(`Malformed ${label} header`);
};

const readRosterPage = (response, pageNumber, expectedShape) => {
  const payload = response?.data;
  const shape = Array.isArray(payload)
    ? 'array'
    : (Array.isArray(payload?.students) ? 'students-envelope' : null);
  if (!shape || (expectedShape && shape !== expectedShape)) {
    throw new StudentRosterFetchError(
      `Student roster page ${pageNumber} did not contain a supported roster response`,
      'STUDENT_ROSTER_INVALID_RESPONSE',
    );
  }
  return {
    rows: shape === 'array' ? payload : payload.students,
    shape,
    payload,
  };
};

const paramsOffset = (config) => {
  const rawOffset = config?.params?.offset;
  if (rawOffset === undefined || rawOffset === null || rawOffset === '') return 0;
  const offset = parseInteger(rawOffset, 'offset');
  if (offset < 0) {
    throw new StudentRosterFetchError('Roster offset cannot be negative', 'STUDENT_ROSTER_INVALID_OFFSET');
  }
  return offset;
};

/**
 * Read a roster endpoint which returns a bare array and, when available,
 * follows its offset pagination until the complete roster is assembled.
 *
 * The first request deliberately receives the exact config object supplied by
 * the caller. This keeps existing axios mocks and auth/header behavior
 * unchanged. Follow-up requests clone the config, preserve headers/signal and
 * caller params, and only add offset/limit.
 */
export const fetchStudentRoster = async (api, url, config = {}) => {
  if (!api || typeof api.get !== 'function') {
    throw new StudentRosterFetchError('A roster API client with get() is required', 'STUDENT_ROSTER_INVALID_CLIENT');
  }

  const firstResponse = await api.get(url, config);
  const firstPageResult = readRosterPage(firstResponse, 1);
  const firstPage = firstPageResult.rows;
  const rosterShape = firstPageResult.shape;
  const firstHeaders = firstResponse?.headers;
  const totalRaw = headerValue(firstHeaders, 'X-Total-Count');
  const hasMoreRaw = headerValue(firstHeaders, 'X-Has-More');
  const nextOffsetRaw = headerValue(firstHeaders, 'X-Next-Offset');

  // Older/test endpoints do not expose pagination headers and intentionally
  // remain single-page compatible, even when their array happens to contain
  // PAGE_SIZE records.
  if (totalRaw === undefined && hasMoreRaw === undefined && nextOffsetRaw === undefined) {
    return {
      ...firstResponse,
      data: firstPageResult.payload,
      headers: copyHeaders(firstResponse?.headers),
    };
  }

  const startOffset = paramsOffset(config);
  const total = totalRaw === undefined
    ? undefined
    : parseInteger(totalRaw, 'X-Total-Count');
  if (total !== undefined && total < 0) {
    throw new StudentRosterFetchError('X-Total-Count cannot be negative');
  }

  let hasMore = parseBoolean(hasMoreRaw, 'X-Has-More');
  if (hasMore === undefined && total !== undefined) {
    hasMore = startOffset + firstPage.length < total;
  }
  if (hasMore === undefined) hasMore = false;

  const combined = [...firstPage];
  let currentOffset = startOffset;
  let nextOffset = nextOffsetRaw === undefined || nextOffsetRaw === ''
    ? undefined
    : parseInteger(nextOffsetRaw, 'X-Next-Offset');

  if (firstPage.length === 0 && total !== undefined && startOffset < total) {
    throw new StudentRosterFetchError(
      'Roster pagination returned an empty page before X-Total-Count was reached',
      'STUDENT_ROSTER_EMPTY_PAGE',
    );
  }
  if (hasMore && firstPage.length === 0) {
    throw new StudentRosterFetchError(
      'Roster pagination returned an empty page before X-Total-Count was reached',
      'STUDENT_ROSTER_EMPTY_PAGE',
    );
  }
  if (hasMore && nextOffset === undefined) {
    throw new StudentRosterFetchError(
      'Roster pagination advertised another page without X-Next-Offset',
      'STUDENT_ROSTER_MISSING_CURSOR',
    );
  }

  let pageNumber = 1;
  while (hasMore) {
    if (nextOffset <= currentOffset) {
      throw new StudentRosterFetchError(
        'Roster pagination returned a non-advancing X-Next-Offset',
        'STUDENT_ROSTER_NON_ADVANCING_CURSOR',
      );
    }

    const pageConfig = {
      ...config,
      params: {
        ...(config.params || {}),
        offset: nextOffset,
        limit: PAGE_SIZE,
      },
    };
    const response = await api.get(url, pageConfig);
    pageNumber += 1;
    const page = readRosterPage(response, pageNumber, rosterShape).rows;
    if (page.length === 0) {
      throw new StudentRosterFetchError(
        'Roster pagination returned an empty page before X-Total-Count was reached',
        'STUDENT_ROSTER_EMPTY_PAGE',
      );
    }
    combined.push(...page);

    const pageHeaders = response?.headers;
    const pageHasMoreRaw = headerValue(pageHeaders, 'X-Has-More');
    const pageTotalRaw = headerValue(pageHeaders, 'X-Total-Count');
    const pageNextRaw = headerValue(pageHeaders, 'X-Next-Offset');
    if (pageTotalRaw !== undefined) {
      const pageTotal = parseInteger(pageTotalRaw, 'X-Total-Count');
      if (total !== undefined && pageTotal !== total) {
        throw new StudentRosterFetchError('Roster pagination changed X-Total-Count between pages');
      }
    }

    hasMore = parseBoolean(pageHasMoreRaw, 'X-Has-More');
    if (hasMore === undefined && total !== undefined) {
      hasMore = nextOffset + page.length < total;
    }
    if (hasMore === undefined) hasMore = false;

    currentOffset = nextOffset;
    nextOffset = pageNextRaw === undefined || pageNextRaw === ''
      ? undefined
      : parseInteger(pageNextRaw, 'X-Next-Offset');
    if (hasMore && nextOffset === undefined) {
      throw new StudentRosterFetchError(
        'Roster pagination advertised another page without X-Next-Offset',
        'STUDENT_ROSTER_MISSING_CURSOR',
      );
    }
  }

  if (total !== undefined && combined.length !== total) {
    throw new StudentRosterFetchError(
      `Roster pagination ended with ${combined.length} rows; expected ${total}`,
      'STUDENT_ROSTER_TOTAL_MISMATCH',
    );
  }

  const headers = copyHeaders(firstResponse?.headers);
  if (total !== undefined) setHeaderValue(headers, 'x-total-count', String(total));
  setHeaderValue(headers, 'x-has-more', 'false');
  setHeaderValue(headers, 'x-next-offset', '');
  const combinedData = rosterShape === 'array'
    ? combined
    : { ...firstPageResult.payload, students: combined };
  return { ...firstResponse, data: combinedData, headers };
};

export default fetchStudentRoster;