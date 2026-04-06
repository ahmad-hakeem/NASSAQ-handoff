"""
Export Engine — محرك التصدير
نَسَّق | NASSAQ

Generates PDF, CSV, and Excel files from ReportingEngine data.
Supports Arabic RTL text in PDF and Excel outputs.

Also preserves legacy export helpers (export_students, export_attendance, etc.)
"""

import csv
import io
import json
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

import pandas as pd
import arabic_reshaper
from bidi.algorithm import get_display

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


def _reshape_ar(text: str) -> str:
    if not text:
        return text
    try:
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)
    except Exception as e:
        logging.getLogger("nassaq.export").debug("Arabic reshape failed: %s", e)
        return str(text)

FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def _register_arabic_fonts():
    regular = os.path.join(FONTS_DIR, "Amiri-Regular.ttf")
    bold = os.path.join(FONTS_DIR, "Amiri-Bold.ttf")
    if os.path.exists(regular) and "Amiri" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Amiri", regular))
    if os.path.exists(bold) and "Amiri-Bold" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Amiri-Bold", bold))


_register_arabic_fonts()

FONT_NAME = "Amiri" if "Amiri" in pdfmetrics.getRegisteredFontNames() else "Helvetica"
FONT_BOLD = "Amiri-Bold" if "Amiri-Bold" in pdfmetrics.getRegisteredFontNames() else "Helvetica-Bold"

NASSAQ_NAVY = colors.HexColor("#1E3A5F")
NASSAQ_TURQUOISE = colors.HexColor("#2DD4BF")
HEADER_BG = NASSAQ_NAVY
HEADER_FG = colors.white
ALT_ROW = colors.HexColor("#F0F9FF")

REPORT_TITLES = {
    "school_attendance": ("تقرير الحضور المدرسي", "School Attendance Report"),
    "school_participation": ("تقرير المشاركة المدرسية", "School Participation Report"),
    "school_behaviour": ("تقرير السلوك المدرسي", "School Behaviour Report"),
    "school_academic": ("تقرير الأداء الأكاديمي", "School Academic Performance Report"),
    "teacher_activity": ("تقرير نشاط المعلم", "Teacher Activity Report"),
    "teacher_session": ("تقرير حصص المعلم", "Teacher Session Report"),
    "student_progress": ("تقرير تقدم الطالب", "Student Progress Report"),
    "student_attendance": ("تقرير حضور الطالب", "Student Attendance Report"),
    "student_performance": ("تقرير أداء الطالب", "Student Performance Report"),
    "class_report": ("تقرير الفصل", "Class Report"),
    "timetable": ("الجدول الدراسي", "Timetable Report"),
}


def _ar_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ArabicTitle", fontName=FONT_BOLD, fontSize=18,
        alignment=TA_RIGHT, spaceAfter=6, textColor=NASSAQ_NAVY,
    ))
    styles.add(ParagraphStyle(
        "ArabicSubtitle", fontName=FONT_NAME, fontSize=12,
        alignment=TA_RIGHT, spaceAfter=12, textColor=colors.gray,
    ))
    styles.add(ParagraphStyle(
        "ArabicSection", fontName=FONT_BOLD, fontSize=14,
        alignment=TA_RIGHT, spaceAfter=8, spaceBefore=14, textColor=NASSAQ_NAVY,
    ))
    styles.add(ParagraphStyle(
        "ArabicBody", fontName=FONT_NAME, fontSize=10,
        alignment=TA_RIGHT, leading=14,
    ))
    styles.add(ParagraphStyle(
        "ArabicCell", fontName=FONT_NAME, fontSize=9,
        alignment=TA_CENTER, leading=12,
    ))
    return styles


def _xml_escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _make_cell_para(text, is_header=False):
    safe_text = _xml_escape(text)
    reshaped = _reshape_ar(safe_text) if isinstance(text, str) else safe_text
    style = ParagraphStyle(
        "cell",
        fontName=FONT_BOLD if is_header else FONT_NAME,
        fontSize=10 if is_header else 9,
        alignment=TA_CENTER,
        leading=14 if is_header else 12,
        textColor=colors.white if is_header else colors.black,
    )
    return Paragraph(reshaped, style)


def _build_table(headers, rows, col_widths=None):
    header_cells = [_make_cell_para(h, is_header=True) for h in headers]
    row_cells = [[_make_cell_para(c) for c in row] for row in rows]
    data = [header_cells] + row_cells
    cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            cmds.append(("BACKGROUND", (0, i), (-1, i), ALT_ROW))
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


def _safe(v, default="—"):
    if v is None:
        return default
    return str(v)


def _ar_para(text, style):
    return Paragraph(_reshape_ar(str(text)), style)


class ExportEngine:
    def __init__(self, db, reporting_engine=None):
        self.db = db
        self.reporting_engine = reporting_engine

    async def export(
        self,
        report_type: str,
        fmt: str,
        school_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        class_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> tuple:
        if not self.reporting_engine:
            raise ValueError("ReportingEngine not configured")

        report = await self.reporting_engine.generate(
            report_type=report_type,
            school_id=school_id,
            start_date=start_date,
            end_date=end_date,
            class_id=class_id,
            teacher_id=teacher_id,
            student_id=student_id,
        )
        if report.get("error"):
            raise ValueError(report["error"])

        data = report.get("data", {})
        period = report.get("period", {})
        generated = report.get("generated_at", datetime.now(timezone.utc).isoformat())

        if fmt == "pdf":
            buf = self._to_pdf(report_type, data, period, generated, school_id)
            media = "application/pdf"
            ext = "pdf"
        elif fmt == "csv":
            buf = self._to_csv(report_type, data)
            media = "text/csv; charset=utf-8"
            ext = "csv"
        elif fmt == "xlsx":
            buf = self._to_xlsx(report_type, data, period, generated)
            media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ext = "xlsx"
        else:
            raise ValueError(f"صيغة غير مدعومة: {fmt}")

        filename = f"{report_type}_{period.get('start_date', 'report')}.{ext}"
        return buf, media, filename

    def _to_pdf(self, report_type, data, period, generated, school_id):
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=20 * mm, leftMargin=20 * mm,
            topMargin=25 * mm, bottomMargin=20 * mm,
        )
        styles = _ar_styles()
        story = []

        logo_placeholder = Table(
            [[Paragraph("🏫", ParagraphStyle("logo", fontSize=28, alignment=1)),
              _ar_para("نَسَّق  NASSAQ", ParagraphStyle("brand", fontName=FONT_NAME,
                         fontSize=14, textColor=NASSAQ_NAVY, alignment=1))]],
            colWidths=[20 * mm, 140 * mm],
        )
        logo_placeholder.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(logo_placeholder)
        story.append(Spacer(1, 4 * mm))

        titles = REPORT_TITLES.get(report_type, ("تقرير", "Report"))
        story.append(_ar_para(titles[0], styles["ArabicTitle"]))
        story.append(Paragraph(titles[1], styles["ArabicSubtitle"]))

        period_text = f"{period.get('start_date', '')}  —  {period.get('end_date', '')}"
        story.append(Paragraph(period_text, styles["ArabicSubtitle"]))
        story.append(HRFlowable(width="100%", thickness=1, color=NASSAQ_TURQUOISE))
        story.append(Spacer(1, 8 * mm))

        renderer = {
            "school_attendance": self._pdf_school_attendance,
            "school_participation": self._pdf_school_participation,
            "school_behaviour": self._pdf_school_behaviour,
            "school_academic": self._pdf_school_academic,
            "teacher_activity": self._pdf_teacher_activity,
            "teacher_session": self._pdf_teacher_session,
            "student_progress": self._pdf_student_progress,
            "student_attendance": self._pdf_student_attendance,
            "student_performance": self._pdf_student_performance,
            "class_report": self._pdf_class_report,
            "timetable": self._pdf_timetable,
        }.get(report_type, self._pdf_generic)

        renderer(story, data, styles)

        story.append(Spacer(1, 10 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.gray))
        footer = f"نَسَّق NASSAQ  |  {generated[:19]}  |  {school_id}"
        story.append(Paragraph(footer, styles["ArabicBody"]))

        doc.build(story)
        buf.seek(0)
        return buf

    def _pdf_kv_table(self, story, items, styles):
        rows = [[str(v), str(k)] for k, v in items]
        t = _build_table(["القيمة", "البيان"], rows, col_widths=[60 * mm, 100 * mm])
        story.append(t)
        story.append(Spacer(1, 6 * mm))

    def _pdf_school_attendance(self, story, data, styles):
        s = data.get("summary", {})
        story.append(_ar_para("ملخص الحضور", styles["ArabicSection"]))
        kv = [
            ("إجمالي السجلات", s.get("total_records", 0)),
            ("نسبة الحضور", f"{s.get('overall_rate', 0)}%"),
        ]
        if "present" in s:
            kv.append(("حاضر", s["present"]))
        if "absent" in s:
            kv.append(("غائب", s["absent"]))
        if "late" in s:
            kv.append(("متأخر", s["late"]))
        self._pdf_kv_table(story, kv, styles)

        by_class = data.get("by_class", [])
        if by_class:
            story.append(_ar_para("الحضور حسب الفصل", styles["ArabicSection"]))
            headers = ["النسبة", "متأخر", "غائب", "حاضر", "الفصل"]
            rows = []
            for c in by_class:
                tot = c.get("present", 0) + c.get("absent", 0) + c.get("late", 0)
                rate = round(c.get("present", 0) / tot * 100, 1) if tot else 0
                rows.append([f"{rate}%", str(c.get("late", 0)), str(c.get("absent", 0)),
                             str(c.get("present", 0)), c.get("class_name", c.get("class_id", ""))])
            story.append(_build_table(headers, rows))

    def _pdf_school_participation(self, story, data, styles):
        s = data.get("summary", {})
        story.append(_ar_para("ملخص المشاركة", styles["ArabicSection"]))
        self._pdf_kv_table(story, [
            ("إجمالي الحصص", s.get("total_sessions", 0)),
            ("إجمالي التفاعلات", s.get("total_interactions", 0)),
        ], styles)

        by_class = data.get("by_class", [])
        if by_class:
            story.append(_ar_para("المشاركة حسب الفصل", styles["ArabicSection"]))
            headers = ["التفاعلات", "الفصل"]
            rows = [[str(c.get("interactions", 0)),
                      c.get("class_name", c.get("class_id", ""))]
                     for c in by_class]
            story.append(_build_table(headers, rows))

    def _pdf_school_behaviour(self, story, data, styles):
        s = data.get("summary", {})
        story.append(_ar_para("ملخص السلوك", styles["ArabicSection"]))
        self._pdf_kv_table(story, [
            ("إجمالي الحوادث", s.get("total_incidents", 0)),
        ], styles)

        by_type = data.get("by_type", [])
        if by_type:
            story.append(_ar_para("حسب النوع", styles["ArabicSection"]))
            headers = ["العدد", "النوع"]
            rows = [[str(t.get("count", 0)), _safe(t.get("type"))] for t in by_type]
            story.append(_build_table(headers, rows))

    def _pdf_school_academic(self, story, data, styles):
        s = data.get("summary", {})
        story.append(_ar_para("ملخص الأداء الأكاديمي", styles["ArabicSection"]))
        self._pdf_kv_table(story, [
            ("المتوسط العام", s.get("overall_average", 0)),
            ("إجمالي السجلات", s.get("total_records", 0)),
        ], styles)

        cp = data.get("class_performance", [])
        if cp:
            story.append(_ar_para("أداء الفصول", styles["ArabicSection"]))
            headers = ["أدنى", "أعلى", "المتوسط", "السجلات", "الفصل"]
            rows = [[str(c.get("min_score", 0)), str(c.get("max_score", 0)),
                      str(c.get("avg_score", 0)), str(c.get("records", 0)),
                      c.get("class_name", c.get("class_id", ""))] for c in cp]
            story.append(_build_table(headers, rows))

        sp = data.get("subject_performance", [])
        if sp:
            story.append(_ar_para("أداء المواد", styles["ArabicSection"]))
            headers = ["التفاعلات", "الفصول", "الحصص", "المادة"]
            rows = [[str(x.get("total_interactions", 0)), str(x.get("classes_count", 0)),
                      str(x.get("sessions", 0)), x.get("subject_name", x.get("subject_id", ""))]
                     for x in sp]
            story.append(_build_table(headers, rows))

        dist = data.get("grade_distribution", [])
        if dist:
            story.append(_ar_para("توزيع الدرجات", styles["ArabicSection"]))
            headers = ["العدد", "النطاق"]
            rows = [[str(d.get("count", 0)), d.get("range", "")] for d in dist]
            story.append(_build_table(headers, rows))

        top = data.get("top_performers", [])
        if top:
            story.append(_ar_para("المتفوقون", styles["ArabicSection"]))
            headers = ["المتوسط", "الاسم"]
            rows = [[str(x.get("avg_score", 0)), x.get("student_name", x.get("student_id", ""))]
                     for x in top[:10]]
            story.append(_build_table(headers, rows))

    def _pdf_teacher_activity(self, story, data, styles):
        s = data.get("summary", {})
        story.append(_ar_para("نشاط المعلم", styles["ArabicSection"]))
        self._pdf_kv_table(story, [
            ("إجمالي الحصص", s.get("total_sessions", 0)),
            ("إجمالي التفاعلات", s.get("total_interactions", 0)),
            ("المتوسط/حصة", s.get("avg_interactions_per_session", 0)),
        ], styles)

        by_class = data.get("class_breakdown", [])
        if by_class:
            story.append(_ar_para("حسب الفصل", styles["ArabicSection"]))
            headers = ["الحصص", "الفصل"]
            rows = [[str(c.get("sessions", 0)), c.get("class_name", c.get("class_id", ""))]
                     for c in by_class]
            story.append(_build_table(headers, rows))

    def _pdf_teacher_session(self, story, data, styles):
        sessions = data.get("sessions", [])
        if sessions:
            story.append(_ar_para("تفاصيل الحصص", styles["ArabicSection"]))
            headers = ["الدقة", "التفاعلات", "المشاركون", "الفصل", "التاريخ"]
            rows = [[f"{x.get('accuracy_rate', 0)}%", str(x.get("interactions", 0)),
                      str(x.get("unique_participants", 0)), _safe(x.get("class_id")),
                      _safe(x.get("date"))] for x in sessions[:50]]
            story.append(_build_table(headers, rows))

        engagement = data.get("class_engagement", [])
        if engagement:
            story.append(_ar_para("مستوى تفاعل الفصول", styles["ArabicSection"]))
            headers = ["المتوسط/حصة", "التفاعلات", "الحصص", "الفصل"]
            rows = [[str(e.get("avg_interactions_per_session", 0)), str(e.get("total_interactions", 0)),
                      str(e.get("sessions", 0)), e.get("class_name", e.get("class_id", ""))]
                     for e in engagement]
            story.append(_build_table(headers, rows))

    def _pdf_student_progress(self, story, data, styles):
        student = data.get("student", {})
        if student:
            story.append(_ar_para("بيانات الطالب", styles["ArabicSection"]))
            self._pdf_kv_table(story, [
                ("الاسم", student.get("name_ar", student.get("full_name", ""))),
                ("الفصل", student.get("class_id", "")),
            ], styles)

        att = data.get("attendance_trend", [])
        if att:
            story.append(_ar_para("اتجاه الحضور", styles["ArabicSection"]))
            headers = ["النسبة", "الإجمالي", "الأسبوع"]
            rows = [[f"{a.get('rate', 0)}%", str(a.get("total", 0)), a.get("week", "")]
                     for a in att]
            story.append(_build_table(headers, rows))

        grade = data.get("grade_trend", [])
        if grade:
            story.append(_ar_para("اتجاه الدرجات", styles["ArabicSection"]))
            headers = ["الدرجة", "التاريخ"]
            rows = [[str(g.get("score", 0)), g.get("date", "")] for g in grade[-20:]]
            story.append(_build_table(headers, rows))

    def _pdf_student_attendance(self, story, data, styles):
        s = data.get("summary", {})
        story.append(_ar_para("ملخص حضور الطالب", styles["ArabicSection"]))
        self._pdf_kv_table(story, [
            ("إجمالي الأيام", s.get("total_days", 0)),
            ("حاضر", s.get("present", 0)),
            ("غائب", s.get("absent", 0)),
            ("متأخر", s.get("late", 0)),
            ("النسبة", f"{s.get('attendance_rate', s.get('rate', 0))}%"),
        ], styles)

        monthly = data.get("monthly", [])
        if monthly:
            story.append(_ar_para("الحضور الشهري", styles["ArabicSection"]))
            headers = ["النسبة", "متأخر", "غائب", "حاضر", "الشهر"]
            rows = [[f"{m.get('rate', 0)}%", str(m.get("late", 0)), str(m.get("absent", 0)),
                      str(m.get("present", 0)), m.get("month", "")] for m in monthly]
            story.append(_build_table(headers, rows))

    def _pdf_student_performance(self, story, data, styles):
        student = data.get("student", {})
        if student:
            story.append(_ar_para("بيانات الطالب", styles["ArabicSection"]))
            self._pdf_kv_table(story, [
                ("الاسم", student.get("name_ar", student.get("full_name", ""))),
                ("الفصل", student.get("class_id", "")),
            ], styles)

        academic = data.get("academic", {})
        if academic:
            story.append(_ar_para("الدرجات", styles["ArabicSection"]))
            self._pdf_kv_table(story, [
                ("المتوسط", academic.get("avg_score", 0)),
                ("الأعلى", academic.get("max_score", 0)),
                ("الأدنى", academic.get("min_score", 0)),
                ("السجلات", academic.get("records", 0)),
            ], styles)

        att = data.get("attendance", {})
        if att:
            story.append(_ar_para("الحضور", styles["ArabicSection"]))
            self._pdf_kv_table(story, [
                ("الإجمالي", att.get("total_days", att.get("total", 0))),
                ("حاضر", att.get("present", 0)),
                ("النسبة", f"{att.get('rate', 0)}%"),
            ], styles)

        strengths = data.get("strengths", [])
        if strengths:
            story.append(_ar_para("نقاط القوة", styles["ArabicSection"]))
            for item in strengths:
                story.append(_ar_para(f"✓  {item}", styles["ArabicBody"]))
            story.append(Spacer(1, 4 * mm))

        improvements = data.get("areas_for_improvement", [])
        if improvements:
            story.append(_ar_para("مجالات التحسين", styles["ArabicSection"]))
            for item in improvements:
                story.append(_ar_para(f"▸  {item}", styles["ArabicBody"]))

    def _pdf_class_report(self, story, data, styles):
        s = data.get("summary", {})
        if s:
            story.append(_ar_para("ملخص الفصول", styles["ArabicSection"]))
            self._pdf_kv_table(story, [
                ("عدد الفصول", s.get("total_classes", 0)),
            ], styles)

        classes = data.get("classes", [])
        if classes:
            story.append(_ar_para("تفاصيل الفصول", styles["ArabicSection"]))
            headers = ["نسبة الحضور", "الطلاب", "الفصل"]
            rows = [[f"{c.get('attendance_rate', 0)}%", str(c.get("students", 0)),
                      c.get("class_name", c.get("class_id", ""))] for c in classes]
            story.append(_build_table(headers, rows))

        student_summaries = data.get("student_summaries", [])
        if student_summaries:
            story.append(_ar_para("ملخص الطلاب", styles["ArabicSection"]))
            headers = ["التفاعلات", "نسبة الحضور", "الاسم"]
            rows = [[str(s.get("interactions", 0)), f"{s.get('attendance_rate', 0)}%",
                      s.get("full_name", s.get("student_id", ""))] for s in student_summaries[:30]]
            story.append(_build_table(headers, rows))

    def _pdf_timetable(self, story, data, styles):
        tt = data.get("timetable", {})
        if tt:
            story.append(_ar_para("معلومات الجدول", styles["ArabicSection"]))
            self._pdf_kv_table(story, [
                ("اسم الجدول", tt.get("name", "")),
                ("الحالة", tt.get("status", "")),
                ("عدد الحصص", tt.get("total_sessions", 0)),
            ], styles)

        sessions = data.get("sessions", [])
        if sessions:
            story.append(_ar_para("الحصص الدراسية", styles["ArabicSection"]))
            headers = ["القاعة", "المادة", "المعلم", "الفصل", "الحصة", "اليوم"]
            rows = [[_safe(s.get("room")), _safe(s.get("subject_name")),
                      _safe(s.get("teacher_name")), _safe(s.get("class_name")),
                      str(s.get("period", "")), _safe(s.get("day"))]
                     for s in sessions[:100]]
            story.append(_build_table(headers, rows))

    def _pdf_generic(self, story, data, styles):
        story.append(_ar_para("بيانات التقرير", styles["ArabicSection"]))
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, (list, dict)):
                    continue
                story.append(_ar_para(f"{key}: {val}", styles["ArabicBody"]))

    def _to_csv(self, report_type, data):
        frames = self._flatten_to_frames(report_type, data)
        buf = io.BytesIO()
        buf.write(b'\xef\xbb\xbf')
        first = True
        for name, df in frames:
            if not first:
                buf.write(b"\n")
            buf.write(f"# {name}\n".encode("utf-8"))
            csv_str = df.to_csv(index=False)
            buf.write(csv_str.encode("utf-8"))
            first = False
        if not frames:
            buf.write("No data\n".encode("utf-8"))
        buf.seek(0)
        return buf

    def _to_xlsx(self, report_type, data, period, generated):
        buf = io.BytesIO()
        frames = self._flatten_to_frames(report_type, data)
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            workbook = writer.book
            header_fmt = workbook.add_format({
                "bold": True,
                "bg_color": "#1E3A5F",
                "font_color": "white",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_size": 11,
            })

            for name, df in frames:
                safe_name = name[:31]
                df = df.fillna("")
                df.to_excel(writer, index=False, sheet_name=safe_name)
                ws = writer.sheets[safe_name]
                for col_num, col_name in enumerate(df.columns):
                    ws.write(0, col_num, col_name, header_fmt)
                    max_len = max(
                        len(str(col_name)),
                        int(df[col_name].astype(str).str.len().max()) if len(df) else 0,
                    )
                    ws.set_column(col_num, col_num, min(max_len + 4, 40))

            if not frames:
                pd.DataFrame({"info": ["لا توجد بيانات"]}).to_excel(
                    writer, index=False, sheet_name="تقرير"
                )

        buf.seek(0)
        return buf

    def _flatten_to_frames(self, report_type, data):
        frames = []

        summary = data.get("summary")
        if isinstance(summary, dict):
            frames.append(("ملخص", pd.DataFrame([summary])))

        list_keys = {
            "by_class": "حسب الفصل",
            "class_breakdown": "تفصيل الفصول",
            "by_date": "حسب التاريخ",
            "by_type": "حسب النوع",
            "class_performance": "أداء الفصول",
            "subject_performance": "أداء المواد",
            "grade_distribution": "توزيع الدرجات",
            "top_performers": "المتفوقون",
            "bottom_performers": "الأضعف أداءً",
            "by_student": "حسب الطالب",
            "top_students": "أفضل الطلاب",
            "trend": "الاتجاه",
            "daily": "يومي",
            "weekly": "أسبوعي",
            "daily_trend": "الاتجاه اليومي",
            "recent": "الأحدث",
            "sessions": "الحصص",
            "class_engagement": "تفاعل الفصول",
            "attendance_trend": "اتجاه الحضور",
            "grade_trend": "اتجاه الدرجات",
            "participation_trend": "اتجاه المشاركة",
            "monthly": "شهري",
            "classes": "الفصول",
            "student_summaries": "ملخص الطلاب",
        }
        for key, label in list_keys.items():
            items = data.get(key)
            if isinstance(items, list) and items:
                frames.append((label, pd.json_normalize(items)))

        for key in ("academic", "scores", "attendance", "participation", "risk", "timetable"):
            val = data.get(key)
            if isinstance(val, dict):
                frames.append((key, pd.DataFrame([val])))

        if isinstance(data.get("student"), dict):
            frames.append(("الطالب", pd.DataFrame([data["student"]])))

        for key in ("strengths", "areas_for_improvement"):
            items = data.get(key)
            if isinstance(items, list) and items:
                frames.append((key, pd.DataFrame({key: items})))

        if isinstance(data.get("calendar"), dict) and data["calendar"]:
            cal_rows = [{"date": d, "status": s} for d, s in data["calendar"].items()]
            frames.append(("التقويم", pd.DataFrame(cal_rows)))

        return frames

    def export_to_csv(self, data: List[Dict[str, Any]], filename_prefix: str = "export") -> Dict[str, Any]:
        if not data:
            return {"content": b"", "filename": f"{filename_prefix}.csv", "content_type": "text/csv; charset=utf-8-sig"}

        output = io.StringIO()
        output.write('\ufeff')

        headers = list(data[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        for row in data:
            flat_row = {}
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    flat_row[k] = json.dumps(v, ensure_ascii=False)
                else:
                    flat_row[k] = v
            writer.writerow(flat_row)

        content = output.getvalue().encode("utf-8-sig")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return {
            "content": content,
            "filename": f"{filename_prefix}_{timestamp}.csv",
            "content_type": "text/csv; charset=utf-8-sig",
        }

    def export_to_json(self, data: Any, filename_prefix: str = "export") -> Dict[str, Any]:
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        return {
            "content": content,
            "filename": f"{filename_prefix}_{timestamp}.json",
            "content_type": "application/json; charset=utf-8",
        }

    async def export_students(self, school_id: str, class_id: Optional[str] = None, fmt: str = "csv") -> Dict[str, Any]:
        query = {"school_id": school_id, "is_active": True}
        if class_id:
            query["class_id"] = class_id

        students = await self.db.students.find(query, {
            "_id": 0, "id": 1, "full_name": 1, "student_number": 1,
            "class_id": 1, "class_name": 1, "grade_level": 1,
            "date_of_birth": 1, "national_id": 1, "gender": 1,
            "parent_name": 1, "parent_phone": 1, "enrollment_date": 1,
        }).to_list(10000)

        if fmt == "json":
            return self.export_to_json(students, "students")
        return self.export_to_csv(students, "students")

    async def export_attendance(
        self, school_id: str, start_date: str, end_date: str,
        class_id: Optional[str] = None, fmt: str = "csv"
    ) -> Dict[str, Any]:
        query = {
            "school_id": school_id,
            "date": {"$gte": start_date, "$lte": end_date},
        }
        if class_id:
            query["class_id"] = class_id

        records = await self.db.attendance.find(query, {
            "_id": 0, "student_id": 1, "class_id": 1, "date": 1,
            "status": 1, "teacher_id": 1,
        }).to_list(100000)

        student_ids = list(set(r.get("student_id") for r in records))
        students = await self.db.students.find(
            {"id": {"$in": student_ids}, "school_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "student_number": 1}
        ).to_list(10000)
        name_map = {s["id"]: s.get("full_name", "") for s in students}
        number_map = {s["id"]: s.get("student_number", "") for s in students}

        for r in records:
            r["student_name"] = name_map.get(r.get("student_id"), "")
            r["student_number"] = number_map.get(r.get("student_id"), "")

        if fmt == "json":
            return self.export_to_json(records, "attendance")
        return self.export_to_csv(records, "attendance")

    async def export_grades(
        self, school_id: str, class_id: Optional[str] = None, fmt: str = "csv"
    ) -> Dict[str, Any]:
        query = {"tenant_id": school_id}
        grades = await self.db.student_grades.find(query, {
            "_id": 0, "student_id": 1, "assessment_id": 1, "subject_id": 1,
            "score": 1, "max_score": 1, "percentage": 1, "is_passing": 1,
            "graded_at": 1,
        }).to_list(50000)

        student_ids = list(set(g.get("student_id") for g in grades))
        students = await self.db.students.find(
            {"id": {"$in": student_ids}, "school_id": school_id},
            {"_id": 0, "id": 1, "full_name": 1, "class_id": 1}
        ).to_list(10000)
        name_map = {s["id"]: s.get("full_name", "") for s in students}
        class_map = {s["id"]: s.get("class_id", "") for s in students}

        for g in grades:
            g["student_name"] = name_map.get(g.get("student_id"), "")
            g["class_id"] = class_map.get(g.get("student_id"), "")

        if class_id:
            grades = [g for g in grades if g.get("class_id") == class_id]

        if fmt == "json":
            return self.export_to_json(grades, "grades")
        return self.export_to_csv(grades, "grades")

    async def export_report(self, report_data: Dict[str, Any], fmt: str = "csv") -> Dict[str, Any]:
        report_type = report_data.get("report_type", "report")

        if fmt == "json":
            return self.export_to_json(report_data, report_type)

        flat_rows = self._flatten_report(report_data)
        return self.export_to_csv(flat_rows, report_type)

    def _flatten_report(self, report_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        report_type = report_data.get("report_type", "")

        if report_type == "student_report":
            student = report_data.get("student", {})
            att = report_data.get("attendance", {})
            part = report_data.get("participation", {})
            return [{
                "الاسم": student.get("full_name", ""),
                "الفصل": student.get("class_name", student.get("class_id", "")),
                "رقم الطالب": student.get("student_number", ""),
                "أيام الحضور": att.get("present_days", 0),
                "أيام الغياب": att.get("absent_days", 0),
                "نسبة الحضور": att.get("attendance_rate", 0),
                "إجمالي التفاعلات": part.get("total_interactions", 0),
                "الإجابات الصحيحة": part.get("correct_answers", 0),
                "نسبة الدقة": part.get("accuracy_rate", 0),
            }]

        if report_type == "class_report":
            rows = []
            for s in report_data.get("student_summaries", []):
                rows.append({
                    "الفصل": report_data.get("class_name", ""),
                    "اسم الطالب": s.get("full_name", ""),
                    "نسبة الحضور": s.get("attendance_rate", 0),
                    "التفاعلات": s.get("interactions", 0),
                })
            return rows if rows else [report_data]

        if report_type == "attendance_report":
            rows = []
            for d in report_data.get("daily_breakdown", []):
                rows.append({
                    "التاريخ": d.get("date", ""),
                    "الإجمالي": d.get("total", 0),
                    "حاضر": d.get("present", 0),
                    "غائب": d.get("absent", 0),
                    "متأخر": d.get("late", 0),
                })
            return rows if rows else [report_data]

        return [report_data]
