# Exam Management Feature — Complete Documentation

---

## SECTION 1 — FEATURE OVERVIEW

### What It Does

The Exam Management feature is a dedicated module within the Nasaq admin dashboard that handles the complete lifecycle of school examinations. It allows school administrators to organize exam periods, schedule subjects with dates and times, assign exam halls (committees) with visual seating layouts, and generate print-ready seating cards for students.

### Who Uses It

This feature is exclusively for the **School Admin (الإدارة)**. Teachers and parents do not have access to this module. The admin accesses it from the sidebar navigation under "إدارة الاختبارات" (Exam Management).

### Why the School Needs It

Saudi schools traditionally manage exam logistics using paper-based processes — printed spreadsheets, hand-drawn seating plans, and manually written seating cards. This creates several problems:

- **Time waste:** Preparing exam layouts for multiple rooms and hundreds of students takes days.
- **Human error:** Manual seat numbering and student assignment leads to mistakes — duplicate seats, missing students, or incorrect room assignments.
- **Inflexibility:** When a room changes or a seat breaks, the entire plan has to be redone.
- **Inconsistency:** Each exam period requires repeating the same tedious process from scratch.

### What Problems It Solves

- **Organizing exam periods:** The admin defines exam periods (e.g., Period 1, Period 2) and manages all subjects within each period in one structured view.
- **Scheduling subjects:** Each subject is assigned a specific date, time slot, participating classes, and observer teachers.
- **Assigning observers:** Teachers are assigned as exam hall supervisors directly within the subject scheduling interface.
- **Managing exam committees:** Physical exam rooms are configured digitally with their exact layout (rows and columns), and students are automatically distributed into seats.
- **Generating seating layouts:** A visual grid shows every seat in a room, with the ability to cancel broken or unavailable seats. Student assignments automatically adjust around cancelled seats.
- **Creating seating cards:** Professional, print-ready cards are generated for each student with customizable fields and dimensions, ready for physical distribution on exam day.

---

## SECTION 2 — ADMIN USER JOURNEY

### Step-by-Step Flow

#### Step 1: Admin Logs into the System
- The admin opens the Nasaq app and logs in using their mobile number and role selection.
- After authentication, they are directed to the Admin Dashboard (Command Center).

#### Step 2: Admin Opens the Admin Dashboard
- The dashboard shows a summary of school operations: attendance stats, upcoming events, waiting classes, and recent notifications.
- The sidebar navigation is visible on the left side of the screen.

#### Step 3: Admin Navigates to Exam Management
- The admin clicks **"إدارة الاختبارات" (Exam Management)** in the sidebar.
- The Exam Management page loads with three tabs at the top:
  1. **جدول الاختبارات** (Exam Schedule)
  2. **اللجان** (Committees)
  3. **كروت الجلوس** (Seating Cards)
- By default, the Exam Schedule tab is active.

#### Step 4: Admin Creates a New Exam Period
- On the Exam Schedule tab, the admin sees existing periods displayed as expandable cards.
- Two default periods are pre-loaded: "الفترة الأولى" (Period 1) and "الفترة الثانية" (Period 2).
- The admin clicks **"إضافة فترة" (Add Period)** to create a new period.
- The system automatically names it (e.g., "الفترة الثالثة") and adds it as an empty card.
- Periods can be deleted using the trash icon on their header.

#### Step 5: Admin Adds Subjects and Exam Dates
- The admin clicks on a period card to expand it and see its subjects.
- Inside the expanded period, the admin clicks **"إضافة مادة" (Add Subject)**.
- A dialog opens with the following fields:
  - **Subject name** (text input, e.g., "الرياضيات")
  - **Date** (date picker)
  - **Time** (text input, e.g., "08:00 - 10:00")
- After filling in the details, the admin proceeds to assign classes and observers in the same dialog.

#### Step 6: Admin Assigns Classes and Observers
- Still in the "Add Subject" dialog:
  - **Classes section:** A grid of checkboxes showing all available classes (e.g., "الرابع - أ", "الخامس - ب"). The admin checks which classes will take this exam.
  - **Observers section:** A grid of checkboxes showing all available teachers. The admin checks which teachers will supervise this exam.
- The admin clicks **"إضافة" (Add)** to save the subject.
- The subject appears in the period's table showing: subject name, date (formatted in Arabic), time (as a badge), assigned classes (as badges), and observers (as blue badges).
- Subjects can be deleted individually using the trash icon in the table row.

#### Step 7: Admin Creates Exam Committees
- The admin switches to the **"اللجان" (Committees)** tab.
- The admin clicks **"إضافة لجنة" (Add Committee)**.
- A dialog opens with two creation modes:
  - **"لجنة واحدة" (Single Committee):** Create one committee manually with a custom name and location.
  - **"إنشاء من نمط" (Create from Template):** Create multiple committees at once — one for each selected class — with the same room layout. The system auto-names them (e.g., "لجنة 2", "لجنة 3") and auto-assigns locations (e.g., "قاعة B", "قاعة C").
- In both modes, the admin configures:
  - **Number of rows** (how many seat rows in the room)
  - **Number of columns** (how many seats per row)
  - A live capacity indicator shows the total seat count (rows × columns).
  - **Classes to assign** (checkboxes for available classes).
- The admin clicks **"إضافة" (Add)** or the template button (e.g., "إنشاء 3 لجنة") to create the committee(s).
- Students are automatically generated and alphabetically sorted into seats.

#### Step 8: Admin Configures Seating Layout
- After creating committees, the admin sees them listed on the left panel of the Committees tab.
- Each committee card shows: name, location, student count, grid dimensions (e.g., 5×6), and assigned classes.
- Clicking a committee selects it and displays its **visual seating grid** on the right panel.
- The grid shows:
  - A **"السبورة" (Whiteboard)** bar at the top to orient the room.
  - A grid of seat cells, each showing the student's name (first two words) and seat number.
  - **Empty seats** appear with dashed borders and "فارغ" (Empty) text.
  - A color legend at the bottom: white = occupied, gray dashed = empty, red = cancelled.
- **Cancelling seats:** The admin clicks any seat to toggle it as cancelled (appears red with an X icon). Clicking again restores it. When a seat is cancelled, all student assignments automatically shift to fill remaining active seats in column-first order.
- **Importing students:** The admin clicks **"استيراد" (Import)** to open a dialog with a drag-and-drop file upload area (supports Excel, PDF, and images). A quick-import button loads sample data for testing.

#### Step 9: Admin Reviews Committee Statistics
- Each committee card has a **statistics icon (📊)**. Clicking it opens a dialog showing:
  - **Total seats** (blue card)
  - **Occupied seats** (green card)
  - **Empty seats** (gray card)
  - **Cancelled seats** (red card)
  - **Occupancy percentage** (indigo highlight bar)
  - **Class distribution:** A breakdown showing how many students belong to each class.

#### Step 10: Admin Generates Seating Cards
- The admin switches to the **"كروت الجلوس" (Seating Cards)** tab.
- The page is divided into two configuration panels:
  - **Left panel — Field Selection (الخانات):**
    - Four default fields with checkboxes: Student Name, National ID, Seat Number, Grade.
    - Each field can be toggled on/off. Disabled fields will not appear on printed cards.
    - The admin can click **"إضافة خانة" (Add Field)** to create custom fields (e.g., "القسم", "الملاحظات").
    - Custom fields can be deleted; default fields cannot.
  - **Right panel — Card Dimensions (المقاسات):**
    - **Card width** (in pixels, min: 200, max: 500)
    - **Card height** (in pixels, min: 120, max: 400)
    - **Per-field width percentage** (min: 10%, max: 60%) — controls how much horizontal space each field label takes on the card.
    - An info note confirms that dimension settings apply to all cards.
- Below the configuration panels, the admin selects a committee from a dropdown.
- The system displays all seating cards for the selected committee as a grid of card previews.
- Each card shows:
  - A gradient header (indigo-to-violet) with "بطاقة جلوس اختبارات" and the committee name/location.
  - Enabled fields listed vertically with labels and values (student name, national ID, seat number, grade).

#### Step 11: Admin Prints Seating Cards or Reports
- **Seating Cards:** The admin clicks **"طباعة الكروت" (Print Cards)** at the top of the Seating Cards tab. The system triggers the browser's print dialog with CSS print styling applied.
- **Committee Report:** From the Committees tab, the admin clicks **"تقرير" (Report)** on the selected committee. A dialog shows:
  - Committee details (name, location, layout, student count, classes).
  - A full student roster table with columns: row number, name, national ID, seat number, grade.
  - A **"طباعة التقرير" (Print Report)** button that triggers print output.

#### Additional Actions
- **Copy Committee:** The admin clicks the copy icon on any committee card. A dialog asks to select new classes for the copy. The system duplicates the room layout with the selected classes and fresh student assignments.
- **Delete Period/Subject/Committee:** Each item has a trash icon for individual deletion.

---

## SECTION 3 — INTERNAL LOGIC OF THE FEATURE

### 3.1 Data Structures

The feature manages four core data types:

**Exam Period**
- Contains: unique ID, title (e.g., "الفترة الأولى"), and an array of exam subjects.
- Periods act as top-level containers that group related exams together.

**Exam Subject**
- Contains: unique ID, subject name, exam date, exam time, list of assigned classes, list of observer teachers.
- Each subject belongs to exactly one period.

**Exam Committee**
- Contains: unique ID, name, location, number of rows, number of columns, list of assigned classes, list of students, list of cancelled seat keys.
- A committee represents a physical exam room with a defined seating capacity.

**Seating Card Field**
- Contains: unique ID, display label, data key, width percentage, enabled flag.
- Fields define what information appears on each printed student card.

### 3.2 Period and Subject Management

**Adding a period:**
- The system counts existing periods and assigns an ordinal Arabic title (الأولى, الثانية, الثالثة, الرابعة, الخامسة). Beyond five, it uses the number directly.
- A new period starts with an empty subjects array.

**Adding a subject:**
- Validates that the subject name is not empty before saving.
- Appends the new subject (with its classes and observers) to the target period's subjects array.
- Resets the form fields after saving.

**Deleting:**
- Periods are removed by filtering them out of the periods array.
- Subjects are removed by filtering them out of the parent period's subjects array.

### 3.3 Committee Creation Logic

**Single mode:**
- Creates one committee with the specified name, location (optional), rows, columns, and classes.
- Total capacity = rows × columns.
- Students are generated from a sample name pool and distributed across selected classes. Each class receives approximately `ceil(capacity / number_of_classes)` students. Note: when the class count does not evenly divide the capacity, the total student count may slightly exceed the grid capacity.
- Students are sorted alphabetically (Arabic locale) and seat numbers are re-assigned sequentially starting from 1.

**Template mode:**
- Creates one committee per selected class, all with the same row/column layout.
- Each committee is auto-named ("لجنة N") and auto-located ("قاعة X" using letters A, B, C...), where N and X continue from the current committee count (e.g., if 2 committees already exist, the next starts at "لجنة 3" / "قاعة C").
- Each committee gets its own set of students from the sample pool, all assigned to that single class.
- Students within each committee are alphabetically sorted and numbered.

### 3.4 Seat Assignment Algorithm

The seating grid uses a **column-first vertical** ordering:

1. The system iterates through all grid positions: for each column (left to right), then for each row (top to bottom).
2. Any position whose key (`"row-col"`) appears in the `cancelledSeats` array is skipped.
3. The remaining positions form an ordered list of "active seats."
4. Students are assigned to active seats in order: student 0 → first active seat, student 1 → second active seat, and so on.
5. If there are more active seats than students, the remaining seats show as "empty."

**When a seat is cancelled:**
- The seat key is added to the `cancelledSeats` array.
- All student assignments shift automatically because the assignment is recalculated each render based on the active seats list.
- No manual re-numbering is needed.

**When a seat is restored:**
- The seat key is removed from the `cancelledSeats` array.
- Student assignments expand to fill the newly available position.

### 3.5 Committee Copy Logic

When copying a committee:
1. The source committee's layout (rows × columns) is preserved.
2. The admin selects new classes for the copy.
3. New students are generated from the sample pool, distributed across the selected classes.
4. The copied committee receives the name of the original plus "(نسخة)" (copy).
5. The location and layout are inherited from the source.
6. Cancelled seats are NOT copied — the new committee starts with all seats active.

### 3.6 Student Import Logic

When importing students into a committee:
1. A dialog shows a file upload area (drag-and-drop for Excel, PDF, or images).
2. In the current prototype, clicking "استيراد (بيانات تجريبية)" loads 15 sample students from the name pool.
3. Imported students are alphabetically sorted and seat-numbered sequentially.
4. The import **replaces** all existing students in the committee (does not append).

### 3.7 Statistics Calculation

The statistics dialog computes:
- **Total seats** = rows × columns
- **Cancelled seats** = length of cancelledSeats array
- **Active seats** = total seats - cancelled seats
- **Occupied seats** = min(student count, active seats)
- **Empty seats** = active seats - occupied seats
- **Occupancy percentage** = (occupied / active) × 100, rounded to nearest integer
- **Class distribution** = count of students grouped by their grade field

### 3.8 Seating Card Generation

Cards are rendered as a grid of styled card components:
- Each card has a fixed width and height set by the admin (default: 300×180 px).
- The header uses a gradient background (indigo-to-violet) showing "بطاقة جلوس اختبارات" and the committee name/location.
- The body iterates over all enabled seating fields and displays each as a label:value pair.
- Field values are mapped from the student object:
  - `name` → student name
  - `nationalId` → national ID number
  - `seatNumber` → assigned seat number
  - `grade` → class/grade
  - Any custom field → shows "—" (no data mapping for custom fields in the prototype)
- The print button triggers `window.print()`, relying on CSS `print:` utilities for physical output formatting.

### 3.9 Seating Card Field Management

- **Default fields** (Student Name, National ID, Seat Number, Grade) cannot be deleted — only toggled on/off.
- **Custom fields** can be added with any label and can be deleted.
- **Width percentage** controls the minimum width of the label column on the card (clamped between 10% and 60%).
- All field settings are shared across all cards — there is no per-committee field customization.

### 3.10 Report Generation

The committee report dialog shows:
- A summary card with committee details: name, location, layout dimensions, student count, assigned classes.
- A full HTML table listing all students with their row number, name, national ID, seat number, and grade.
- A print button that triggers browser print with the report content formatted for paper output.

---

## SECTION 4 — RECONSTRUCTED PROMPT

### Reconstructed Prompt (Estimated)

> Build an Exam Management system for the admin dashboard of the Nasaq educational platform. The page should use the existing AdminLayout wrapper and be fully in Arabic (RTL). Use shadcn/ui components (Tabs, Dialog, Card, Badge, Select, Checkbox, Button, Input, Label) and lucide-react icons. All data should be managed with React useState — no backend API calls.
>
> The page should have a title "إدارة الاختبارات" with a subtitle, and contain three tabs:
>
> **Tab 1: جدول الاختبارات (Exam Schedule)**
> - Show exam periods as expandable/collapsible cards with gradient headers. Start with two default periods: "الفترة الأولى" (with 3 pre-loaded subjects: الرياضيات, العلوم, اللغة العربية with sample dates, times, classes, and observers) and "الفترة الثانية" (empty).
> - "Add Period" button creates new periods with automatic Arabic ordinal naming (الثالثة, الرابعة, الخامسة...).
> - Each period can be deleted and has a subject count indicator.
> - Inside each expanded period: an "Add Subject" button and a table showing subjects with columns: المادة, التاريخ (formatted in Arabic with month/day/weekday), الوقت (as outline badge), الفصول (as secondary badges), الملاحظون (as blue badges), and a delete button.
> - "Add Subject" opens a dialog with: subject name input, date picker, time input, a 3-column checkbox grid for class selection (9 classes: الرابع أ/ب/ج, الخامس أ/ب/ج, السادس أ/ب/ج), and a 2-column checkbox grid for observer selection (6 teachers).
>
> **Tab 2: اللجان (Committees)**
> - Split into two columns: left panel = committee list, right panel = seating grid of selected committee.
> - Each committee card shows: name, location icon + text, student count, grid dimensions (rows×columns), and class badges. Cards are selectable with highlighted border.
> - Each committee card has action icons: copy, statistics, delete.
> - "Add Committee" button opens a dialog with a two-button mode toggle at the top:
>   - "لجنة واحدة" (Single): shows name + location inputs, rows/columns inputs, and class checkboxes.
>   - "إنشاء من نمط" (Template): hides name/location, shows an info box explaining automatic naming, rows/columns inputs, and class checkboxes. Shows "سيتم إنشاء N لجنة" confirmation and button text updates to "إنشاء N لجنة".
> - Both modes show a capacity indicator: "السعة: N مقعد · الترتيب عمودي أبجدي تلقائي".
> - The seating grid: display a "السبورة" (Whiteboard) bar at the top, then a CSS grid with columns based on the committee's column count. Each cell is clickable to toggle cancel/restore. Occupied seats show student name (first 2 words) and seat number badge. Empty seats show "فارغ" with dashed border. Cancelled seats show red XCircle icon with reduced opacity. Below the grid: instruction text and a 3-item color legend (occupied, empty, cancelled).
> - Seat assignment uses column-first vertical ordering: iterate columns left-to-right, rows top-to-bottom, skip cancelled seats, assign students to remaining active positions in order.
> - Above the grid: "Import" button (opens upload dialog with drag-drop area supporting Excel/PDF/image, plus a "sample data" quick-import button) and "Report" button (opens dialog with committee summary + full student table + print button).
> - Copy committee dialog: select new classes for the copy, preserves rows/columns layout.
> - Statistics dialog: 4-card grid (total seats blue, occupied green, empty gray, cancelled red), occupancy percentage bar (indigo), class distribution list with badges.
>
> **Tab 3: كروت الجلوس (Seating Cards)**
> - Header with "Add Field" and "Print Cards" buttons.
> - Two-column layout:
>   - Left card "الخانات": list of fields with checkbox + label. Default fields (اسم الطالب, رقم الهوية, رقم الجلوس, الصف) cannot be deleted. Custom fields have a delete button.
>   - Right card "المقاسات": card width/height inputs in px, and for each enabled field a width percentage input (clamped 10-60%). Info note: "المقاسات تنطبق على جميع كروت الطباعة".
> - Below: a committee selector dropdown. When selected, render all student cards in a flex-wrap grid.
> - Each card: fixed width/height per admin settings, gradient header (indigo→violet) with "بطاقة جلوس اختبارات" and committee name/location, body with enabled fields as label:value pairs.
> - Print button calls window.print().
> - "Add Field" dialog: single input for field label, adds to the field list with enabled=true and default width=20%.
>
> Pre-populate with sample data: 30 Arabic student names, 9 available classes, 6 available observer teachers, and one default committee ("لجنة 1" at "قاعة A", 5 rows × 6 columns, with 20 students from "الرابع - أ").
>
> Add data-testid attributes to all interactive elements following the pattern: button-*, input-*, tab-*, card-*, seat-*, field-config-*, checkbox-*, select-*, row-*.

---

## SECTION 5 — PRODUCT PURPOSE OF THE EXAM MODULE

### Why This Feature Exists

The Exam Management module exists because Saudi schools face a recurring operational burden every exam period. Preparing for exams requires administrators to:

1. Define which subjects are being tested, on which dates, and at what times.
2. Decide which classes participate in each exam.
3. Assign teacher supervisors (observers) to each exam hall.
4. Set up physical rooms with seating arrangements that accommodate the right number of students.
5. Handle unavailable seats (broken chairs, restricted positions).
6. Produce individual seating cards that tell each student exactly where to sit.
7. Print reports for the supervision committee.

Traditionally, all of this is done with spreadsheets, paper forms, and manual calculations. It takes days of work before each exam period, and any last-minute change (a room swap, a new student, a broken seat) means redoing significant portions of the plan.

### What It Achieves

- **Organizing exams:** All exam periods, subjects, dates, times, classes, and observers live in one organized interface instead of scattered files and documents.
- **Managing committees:** Each exam room is configured once with its exact physical layout. The system handles the math of capacity, seat numbering, and student distribution automatically.
- **Generating seating cards:** Instead of writing or typing hundreds of individual cards, the system generates them instantly with customizable layout. Change a setting and all cards update in real-time.
- **Simplifying school exam operations:** The entire workflow — from defining the exam schedule to printing the last seating card — happens in one place. Cancel a seat and assignments adjust. Add students and cards regenerate. Copy a room layout and create identical setups in seconds.

### The Bottom Line

This module transforms exam preparation from a multi-day administrative task into a streamlined digital workflow. Every student gets a clearly assigned seat, every room is properly configured, every teacher knows their supervision assignment, and the admin can print everything with one click — all before the first exam begins.
