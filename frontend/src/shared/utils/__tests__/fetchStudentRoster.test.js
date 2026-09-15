import { fetchStudentRoster, StudentRosterFetchError } from '../fetchStudentRoster';

const page = (count, start = 0) => (
  Array.from({ length: count }, (_, index) => ({ id: `student-${start + index}` }))
);

const response = (data, headers = {}) => ({ data, headers });

describe('fetchStudentRoster', () => {
  test('combines a 1001-row roster and forwards params, headers, and signal', async () => {
    const api = {
      get: jest.fn()
        .mockResolvedValueOnce(response(page(1000), {
          'X-Total-Count': '1001',
          'X-Has-More': 'true',
          'X-Next-Offset': '1000',
        }))
        .mockResolvedValueOnce(response(page(1, 1000), {
          'X-Total-Count': '1001',
          'X-Has-More': 'false',
          'X-Next-Offset': '',
        })),
    };
    const signal = { aborted: false };
    const config = {
      headers: { 'X-School-Context': 'school-1' },
      params: { class_id: 'class-1' },
      signal,
    };

    const result = await fetchStudentRoster(api, '/classes/class-1/students', config);

    expect(result.data).toHaveLength(1001);
    expect(result.data.at(-1)).toEqual({ id: 'student-1000' });
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(api.get.mock.calls[0]).toEqual(['/classes/class-1/students', config]);
    expect(api.get.mock.calls[1]).toEqual([
      '/classes/class-1/students',
      {
        headers: config.headers,
        params: { class_id: 'class-1', offset: 1000, limit: 1000 },
        signal,
      },
    ]);
    expect(config.params).toEqual({ class_id: 'class-1' });
    expect(result.headers['x-total-count']).toBe('1001');
    expect(result.headers['x-has-more']).toBe('false');
  });

  test('combines 2300 rows in three pages without one request per student', async () => {
    const api = {
      get: jest.fn()
        .mockResolvedValueOnce(response(page(1000), {
          'X-Total-Count': '2300',
          'X-Has-More': 'true',
          'X-Next-Offset': '1000',
        }))
        .mockResolvedValueOnce(response(page(1000, 1000), {
          'X-Total-Count': '2300',
          'X-Has-More': 'true',
          'X-Next-Offset': '2000',
        }))
        .mockResolvedValueOnce(response(page(300, 2000), {
          'X-Total-Count': '2300',
          'X-Has-More': 'false',
          'X-Next-Offset': '',
        })),
    };

    const result = await fetchStudentRoster(api, '/students', {
      headers: { Authorization: 'Bearer token' },
    });

    expect(result.data).toHaveLength(2300);
    expect(result.data.at(-1)).toEqual({ id: 'student-2299' });
    expect(api.get).toHaveBeenCalledTimes(3);
    expect(api.get.mock.calls.slice(1).map(([, config]) => config.params)).toEqual([
      { offset: 1000, limit: 1000 },
      { offset: 2000, limit: 1000 },
    ]);
  });

  test('combines a wrapped 501-row options roster across two pages', async () => {
    const api = {
      get: jest.fn()
        .mockResolvedValueOnce(response({ students: page(500) }, {
          'X-Total-Count': '501',
          'X-Has-More': 'true',
          'X-Next-Offset': '500',
        }))
        .mockResolvedValueOnce(response({ students: page(1, 500) }, {
          'X-Total-Count': '501',
          'X-Has-More': 'false',
          'X-Next-Offset': '',
        })),
    };

    const result = await fetchStudentRoster(api, '/classes/options/students', {
      headers: { 'X-School-Context': 'school-1' },
      params: { include_inactive: false },
    });

    expect(result.data.students).toHaveLength(501);
    expect(result.data.students.at(-1)).toEqual({ id: 'student-500' });
    expect(api.get).toHaveBeenCalledTimes(2);
    expect(api.get.mock.calls[1][1]).toEqual({
      headers: { 'X-School-Context': 'school-1' },
      params: { include_inactive: false, offset: 500, limit: 1000 },
    });
  });

  test('keeps legacy bare-array responses to one request when pagination headers are absent', async () => {
    const api = { get: jest.fn().mockResolvedValue({ data: page(1000) }) };

    const result = await fetchStudentRoster(api, '/students', {});

    expect(result.data).toHaveLength(1000);
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(result.headers).toEqual({});
  });

  test.each([
    {
      name: 'a non-advancing cursor',
      headers: { 'X-Total-Count': '2000', 'X-Has-More': 'true', 'X-Next-Offset': '0' },
      code: 'STUDENT_ROSTER_NON_ADVANCING_CURSOR',
    },
    {
      name: 'a missing cursor',
      headers: { 'X-Total-Count': '2000', 'X-Has-More': 'true' },
      code: 'STUDENT_ROSTER_MISSING_CURSOR',
    },
    {
      name: 'an empty page before the advertised total',
      data: [],
      headers: { 'X-Total-Count': '1', 'X-Has-More': 'false', 'X-Next-Offset': '' },
      code: 'STUDENT_ROSTER_EMPTY_PAGE',
    },
  ])('throws an explicit error for $name', async ({ headers, data = page(1000), code }) => {
    const api = { get: jest.fn().mockResolvedValue(response(data, headers)) };

    await expect(fetchStudentRoster(api, '/students')).rejects.toMatchObject({
      name: 'StudentRosterFetchError',
      code,
    });
  });

  test('rejects malformed roster data and malformed pagination headers', async () => {
    const malformedDataApi = {
      get: jest.fn().mockResolvedValue(response({ students: 'not-an-array' }, {})),
    };
    await expect(fetchStudentRoster(malformedDataApi, '/students'))
      .rejects.toBeInstanceOf(StudentRosterFetchError);

    const malformedHeaderApi = {
      get: jest.fn().mockResolvedValue(response(page(1), {
        'X-Has-More': 'sometimes',
      })),
    };
    await expect(fetchStudentRoster(malformedHeaderApi, '/students'))
      .rejects.toMatchObject({ code: 'STUDENT_ROSTER_PAGINATION_ERROR' });
  });
});