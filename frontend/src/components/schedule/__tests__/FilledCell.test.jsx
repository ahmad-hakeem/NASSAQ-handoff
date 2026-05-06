/**
 * Task #126 — FilledCell relocation overlay regression guard.
 *
 * يرسم FilledCell الخلية الواحدة في مصفوفة "إدارة الجداول الذكية" بأربع
 * حالات أساسية: عادية، شاغرة (معلم غائب)، مُستبدلة (الخانة الأصلية بعد
 * إسناد بديل)، وبديل (الخانة المُضافة لصف المعلم البديل). لكلٍّ من هذه
 * الحالات يجب أن تُضاف طبقة "نُقل إلى …" عند ضبط `is_relocated` مع
 * `alternative_location`:
 *
 *   - في الحالة العادية: تُلوَّن الخلية بصبغة برتقالية (bg-orange-50)
 *     ويظهر النص "نُقل إلى: …" وعلامة التحذير AlertTriangle، وتُكشف
 *     عبر `data-testid="cell-relocated"`.
 *   - في الحالات الخاصة: يبقى لون الخلية الأصلي (أحمر/أخضر/بنفسجي) ولا
 *     يُكتب نص "نُقل إلى" داخل الخلية حتى لا يُخفي الاستبدال أو الشغور،
 *     لكن tooltip (سمة `title`) يجب أن يُلحق "• نُقل إلى: …" بنهايته.
 *
 * كسر أي من هذه السلوكيات يعني أن المدير لن يرى أن الفصل قد نُقل، فهذا
 * هو الاختبار الذي يحرس واجهة الـrelocation overlay.
 */
import React from 'react';
import { render as rtlRender, screen } from '@testing-library/react';
import FilledCell from '../FilledCell';
import { ThemeProvider } from '../../../contexts/ThemeContext';

// FilledCell يستدعي useTranslation()/useTheme()، فيلزم تغليفه بـ ThemeProvider
// ضمن الاختبارات. نلفّ render حتى يبقى توقيع الاختبارات الأصلي كما هو
// (`render(<FilledCell …/>)`).
const render = (ui, options) =>
  rtlRender(ui, { wrapper: ({ children }) => <ThemeProvider>{children}</ThemeProvider>, ...options });

const ALT_LOC = 'المعمل';

// أداة مطابقة تتعامل مع النص الموزَّع على عدة عقد. مكوّن visual-edits
// يحقن `<span>` حول التعابير الديناميكية مما يُفكّك "بديل: أ. خالد" إلى
// عدة عُقد نصية. نستخدم matcher دالة تفحص textContent المُجمَّع لكل عنصر
// (تجاهل أحفاده) ليبقى الاختبار صامداً سواء جرى wrapping أم لا.
function makeTextMatcher(expected) {
  return (_content, node) => {
    if (!node) return false;
    const flat = (node.textContent || '').replace(/\s+/g, ' ').trim();
    if (flat !== expected) return false;
    // طابِق فقط أعمق عنصر يحتوي النص — لتجنّب مطابقات متعددة على الآباء.
    const childMatches = Array.from(node.children).some((c) => {
      const cFlat = (c.textContent || '').replace(/\s+/g, ' ').trim();
      return cFlat === expected;
    });
    return !childMatches;
  };
}

describe('FilledCell — relocation overlay across all four cell states', () => {
  // ── 1. الحالة العادية ─────────────────────────────────────────────────
  describe('normal cell', () => {
    const baseCell = {
      class_id: 'c-1',
      class_name: '1A',
      subject_id: 's-1',
      subject_name: 'رياضيات',
      is_vacant: false,
    };

    test('بدون نقل: يعرض اسم الفصل والمادة بصبغة زرقاء بلا علامة تحذير', () => {
      const { container } = render(<FilledCell cell={baseCell} />);
      expect(screen.getByText('1A')).toBeInTheDocument();
      expect(screen.getByText('رياضيات')).toBeInTheDocument();
      expect(screen.queryByText(/نُقل إلى/)).not.toBeInTheDocument();
      expect(screen.queryByTestId('cell-relocated')).not.toBeInTheDocument();
      // لا صبغة برتقالية حين لا يوجد نقل.
      expect(container.querySelector('.bg-orange-50')).toBeNull();
    });

    test('مع نقل: يلوّن بالبرتقالي ويعرض "نُقل إلى" مع علامة التحذير', () => {
      const cell = { ...baseCell, is_relocated: true, alternative_location: ALT_LOC };
      render(<FilledCell cell={cell} />);

      const relocated = screen.getByTestId('cell-relocated');
      expect(relocated).toBeInTheDocument();
      expect(relocated).toHaveClass('bg-orange-50');
      expect(relocated).toHaveClass('text-orange-700');
      // النص الكامل "نُقل إلى: المعمل" يجب أن يُكتب داخل الخلية.
      expect(screen.getByText(makeTextMatcher(`نُقل إلى: ${ALT_LOC}`))).toBeInTheDocument();
      // tooltip يجمع المادة مع تلميح النقل.
      expect(relocated).toHaveAttribute(
        'title',
        `${baseCell.subject_name} • نُقل إلى: ${ALT_LOC}`,
      );
      // علامة التحذير AlertTriangle حاضرة (svg من lucide-react).
      const svg = relocated.querySelector('svg');
      expect(svg).not.toBeNull();
      expect(svg).toHaveClass('text-orange-500');
    });

    test('علم is_relocated دون alternative_location لا يفعّل الصبغة', () => {
      const cell = { ...baseCell, is_relocated: true };  // alternative_location مفقود
      const { container } = render(<FilledCell cell={cell} />);
      expect(screen.queryByTestId('cell-relocated')).not.toBeInTheDocument();
      expect(container.querySelector('.bg-orange-50')).toBeNull();
      expect(screen.queryByText(/نُقل إلى/)).not.toBeInTheDocument();
    });
  });

  // ── 2. الحالة الشاغرة (معلمها غائب) ──────────────────────────────────
  describe('vacant cell', () => {
    const vacantCell = {
      class_id: 'c-1',
      class_name: '2B',
      is_vacant: true,
    };

    test('بدون نقل: زرّ أحمر بنص "شاغرة" وtooltip اختيار البديل', () => {
      render(<FilledCell cell={vacantCell} />);
      const btn = screen.getByRole('button', { name: /شاغرة/ });
      expect(btn).toHaveClass('bg-red-50');
      expect(btn).toHaveClass('text-red-600');
      expect(btn).toHaveAttribute('title', 'اضغط لاختيار بديل من جدول الانتظار');
      expect(screen.queryByText(/نُقل إلى/)).not.toBeInTheDocument();
    });

    test('مع نقل: يبقى اللون الأحمر ويُلحق tooltip "نُقل إلى" دون كتابته داخل الخلية', () => {
      const cell = { ...vacantCell, is_relocated: true, alternative_location: ALT_LOC };
      render(<FilledCell cell={cell} />);
      const btn = screen.getByRole('button', { name: /شاغرة/ });
      // اللون الأحمر يبقى — لا نخفي معلومة الشغور وراء البرتقالي.
      expect(btn).toHaveClass('bg-red-50');
      expect(btn).not.toHaveClass('bg-orange-50');
      // tooltip فيه التلميح، لكن نص "نُقل إلى" لا يُكتب داخل الخلية.
      expect(btn).toHaveAttribute(
        'title',
        `اضغط لاختيار بديل من جدول الانتظار • نُقل إلى: ${ALT_LOC}`,
      );
      expect(screen.queryByText(`نُقل إلى: ${ALT_LOC}`)).not.toBeInTheDocument();
    });
  });

  // ── 3. الحالة المُستبدلة (الخانة الأصلية بعد إسناد بديل) ──────────────
  describe('substituted cell', () => {
    const substitutedCell = {
      class_id: 'c-1',
      class_name: '3C',
      is_vacant: false,
      is_substituted: true,
      substitute_teacher_name: 'أ. خالد',
    };

    test('بدون نقل: صبغة خضراء وtooltip "بديل: …"', () => {
      const { container } = render(<FilledCell cell={substitutedCell} />);
      const root = container.firstChild;
      expect(root).toHaveClass('bg-emerald-50/70');
      expect(root).toHaveAttribute('title', 'البديل: أ. خالد');
      expect(screen.getByText('3C')).toBeInTheDocument();
      // النص داخل الخلية يستخدم substituteShortLabel ("بديل")، أما tooltip
      // فيستخدم substituteWithName ("البديل: …"). الفرق مقصود.
      expect(screen.getByText(makeTextMatcher('بديل: أ. خالد'))).toBeInTheDocument();
      expect(screen.queryByText(/نُقل إلى/)).not.toBeInTheDocument();
    });

    test('مع نقل: يبقى اللون الأخضر ويُلحق tooltip "نُقل إلى"', () => {
      const cell = {
        ...substitutedCell,
        is_relocated: true,
        alternative_location: ALT_LOC,
      };
      const { container } = render(<FilledCell cell={cell} />);
      const root = container.firstChild;
      expect(root).toHaveClass('bg-emerald-50/70');
      expect(root).not.toHaveClass('bg-orange-50');
      expect(root).toHaveAttribute(
        'title',
        `البديل: أ. خالد • نُقل إلى: ${ALT_LOC}`,
      );
      // نص "نُقل إلى" لا يُكتب داخل الخلية حتى لا يُخفي معلومة الاستبدال.
      expect(screen.queryByText(`نُقل إلى: ${ALT_LOC}`)).not.toBeInTheDocument();
    });
  });

  // ── 4. حالة "بديل" (الخانة المضافة لصف المعلم البديل) ─────────────────
  describe('substitute cell', () => {
    const substituteCell = {
      class_id: 'c-1',
      class_name: '4D',
      subject_name: 'علوم',
      is_vacant: false,
      is_substitute: true,
      original_teacher_name: 'أ. سعد',
    };

    test('بدون نقل: صبغة بنفسجية وtooltip "بديل عن …" مع أيقونة Repeat', () => {
      const { container } = render(<FilledCell cell={substituteCell} />);
      const root = container.firstChild;
      expect(root).toHaveClass('bg-violet-50/70');
      expect(root).toHaveAttribute('title', 'بديل عن أ. سعد');
      expect(screen.getByText('4D')).toBeInTheDocument();
      expect(screen.getByText('علوم')).toBeInTheDocument();
      // أيقونة Repeat يجب أن تكون موجودة (svg).
      expect(root.querySelector('svg')).not.toBeNull();
      expect(screen.queryByText(/نُقل إلى/)).not.toBeInTheDocument();
    });

    test('مع نقل: يبقى اللون البنفسجي ويُلحق tooltip "نُقل إلى"', () => {
      const cell = {
        ...substituteCell,
        is_relocated: true,
        alternative_location: ALT_LOC,
      };
      const { container } = render(<FilledCell cell={cell} />);
      const root = container.firstChild;
      expect(root).toHaveClass('bg-violet-50/70');
      expect(root).not.toHaveClass('bg-orange-50');
      expect(root).toHaveAttribute(
        'title',
        `بديل عن أ. سعد • نُقل إلى: ${ALT_LOC}`,
      );
      // نص "نُقل إلى" لا يُكتب داخل الخلية.
      expect(screen.queryByText(`نُقل إلى: ${ALT_LOC}`)).not.toBeInTheDocument();
    });
  });
});
