import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';
import {
  convertGregorianToHijri,
  convertHijriToGregorian,
} from '../teacherBirthDate';
import { TEACHER_UMM_AL_QURA_MONTH_STARTS } from '../teacherUmmAlQuraData';

const python = path.resolve(process.cwd(), '../.pythonlibs/bin/python');
const pythonTable = path.resolve(
  process.cwd(),
  '../.pythonlibs/lib/python3.12/site-packages/hijri_converter/ummalqura.py'
);
const describeWithPython = fs.existsSync(python) && fs.existsSync(pythonTable)
  ? describe
  : describe.skip;

describeWithPython('teacher Umm al-Qura parity with backend Python package', () => {
  test('generated frontend month starts exactly match hijri-converter 2.3.2.post1', () => {
    const source = fs.readFileSync(pythonTable, 'utf8');
    const body = source.match(/MONTH_STARTS:[\s\S]*?= \(([\s\S]*?)\)\n"""Ordered list/)[1];
    const pythonValues = body.match(/\d+/g).map(Number);
    expect(TEACHER_UMM_AL_QURA_MONTH_STARTS).toEqual(pythonValues);
  });

  test('every supported Hijri day converts identically in both directions', () => {
    const script = [
      'from hijri_converter import Hijri',
      'for year in range(1343, 1501):',
      '  for month in range(1, 13):',
      '    first = Hijri(year, month, 1)',
      '    for day in range(1, first.month_length() + 1):',
      '      gregorian = Hijri(year, month, day).to_gregorian()',
      '      print(f"{day:02}/{month:02}/{year}\\t{gregorian.isoformat()}")',
    ].join('\n');
    const rows = execFileSync(python, ['-W', 'ignore::DeprecationWarning', '-c', script], {
      encoding: 'utf8',
      maxBuffer: 8 * 1024 * 1024,
    }).trim().split('\n');

    for (const row of rows) {
      const [hijri, gregorian] = row.split('\t');
      const toGregorian = convertHijriToGregorian(hijri);
      if (toGregorian.status !== 'converted' || toGregorian.iso !== gregorian) {
        throw new Error(`Hijri parity mismatch: ${hijri} -> ${JSON.stringify(toGregorian)}, expected ${gregorian}`);
      }
      const toHijri = convertGregorianToHijri(gregorian);
      const [day, month, year] = hijri.split('/');
      const expectedIso = `${year}-${month}-${day}`;
      if (toHijri.status !== 'converted' || toHijri.iso !== expectedIso) {
        throw new Error(`Gregorian parity mismatch: ${gregorian} -> ${JSON.stringify(toHijri)}, expected ${expectedIso}`);
      }
    }
    expect(rows).toHaveLength(55991);
  });
});