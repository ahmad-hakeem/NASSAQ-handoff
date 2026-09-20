# Optional Teacher Qualifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let school principals create and edit teachers with degree, experience, and rank omitted while validating any supplied values and storing absence as `NULL`.

**Architecture:** Normalize and validate qualification input at the two backend write boundaries (wizard create and principal professional edit), preserving the distinction between omitted update fields and explicit clears. Update the React wizard and editor so blank experience remains blank, optional labels have no asterisks, and review surfaces show `غير مضاف`.

**Tech Stack:** React 18, Jest/Testing Library, FastAPI, Pydantic v2, SQLAlchemy/PostgreSQL, pytest.

---

## File Map

- Modify `frontend/src/features/teachers/components/wizards/AddTeacherWizard.jsx`: optional wizard state, validation, labels, payload, and review placeholders.
- Modify `frontend/src/features/teachers/components/wizards/__tests__/AddTeacherWizard.test.js`: empty/partial/zero/invalid qualification behavior and payload assertions.
- Modify `backend/src/modules/academics/controllers/academics_teacher_routes.py`: create-request normalization, supported-option validation, and nullable persistence.
- Modify `backend/tests/test_teacher_professional_profile_full.py`: create permutations and edit/clear persistence coverage.
- Modify `backend/src/modules/teacher_management/controllers/principal_management_routes.py`: update-request field-presence handling, clearing, and validation.
- Modify `frontend/src/features/platform/components/management/TeacherProfileDialog.jsx`: preserve blank experience and submit explicit clears.
- Modify `frontend/src/features/platform/components/management/__tests__/TeacherProfileDialog.professionalData.test.jsx`: editor clear and explicit-zero payload coverage.

No migration is planned because the persisted `qualification`, `rank`, and
`years_of_experience` columns are already nullable.

### Task 1: Backend create contract

**Files:**
- Modify: `backend/src/modules/academics/controllers/academics_teacher_routes.py:460-487, 782-946`
- Test: `backend/tests/test_teacher_professional_profile_full.py`

- [ ] **Step 1: Write failing create-contract tests**

Add parametrized API tests that create unique teachers with qualifications set
to `{}`, explicit `null` values, blank strings, each single valid field, all
valid fields, and explicit experience `0`. Fetch each full profile and assert:

```python
assert professional["academic_degree"] is expected_degree
assert professional["teacher_rank"] is expected_rank
assert professional["years_of_experience"] == expected_experience
```

Add invalid cases and assert `422` with qualification-specific details:

```python
@pytest.mark.parametrize("qualifications", [
    {"years_of_experience": -1},
    {"years_of_experience": "not-a-number"},
    {"academic_degree": "unsupported-degree"},
    {"teacher_rank": "unsupported-rank"},
])
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```bash
cd backend && ENVIRONMENT=development uv run pytest \
  tests/test_teacher_professional_profile_full.py -q
```

Expected: new tests fail because missing experience persists as `0`, blank
strings are not consistently normalized, and option membership is not checked.

- [ ] **Step 3: Implement create normalization and validation**

Change `TeacherWizardCreate.years_of_experience` to default to `None`. Add a
Pydantic validation helper or typed nested model that implements:

```python
def optional_text(value):
    if value is None:
        return None
    value = value.strip()
    return value or None

def optional_non_negative_int(value):
    if value is None or value == "":
        return None
    parsed = int(value)
    if parsed < 0:
        raise ValueError("سنوات الخبرة يجب أن تكون صفراً أو أكثر")
    return parsed
```

Use key-presence-aware extraction instead of `or`:

```python
qualifications = data.qualifications or {}
academic_degree = optional_text(
    qualifications["academic_degree"]
    if "academic_degree" in qualifications
    else data.academic_degree
)
years_of_experience = optional_non_negative_int(
    qualifications["years_of_experience"]
    if "years_of_experience" in qualifications
    else data.years_of_experience
)
```

Load the active values from the existing academic-degree and teacher-rank option
sources used by the option endpoints. Reject a non-null value not in the active
set. Keep identity validation and locking unchanged. Persist `None` directly in
both canonical and legacy alias columns.

- [ ] **Step 4: Run focused backend tests**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit the backend create contract**

```bash
git add backend/src/modules/academics/controllers/academics_teacher_routes.py \
  backend/tests/test_teacher_professional_profile_full.py
git commit -m "fix: make teacher qualifications optional"
```

### Task 2: Wizard UI and review contract

**Files:**
- Modify: `frontend/src/features/teachers/components/wizards/AddTeacherWizard.jsx:143-145, 188-223, 435-466, 588-615`
- Test: `frontend/src/features/teachers/components/wizards/__tests__/AddTeacherWizard.test.js`

- [ ] **Step 1: Write failing wizard tests**

Change the test helper so step 2 can be left untouched. Add tests asserting:

```javascript
expect(screen.getByText('next')).not.toBeDisabled();
fireEvent.click(screen.getByText('next'));
expect(screen.getAllByText('غير مضاف')).toHaveLength(3);
```

Submit the empty case and assert:

```javascript
expect(mockApi.post).toHaveBeenCalledWith('/teachers/create', expect.objectContaining({
  qualifications: expect.objectContaining({
    academic_degree: null,
    teacher_rank: null,
    years_of_experience: null,
  }),
}));
```

Add cases for degree only, rank only, experience only, all values, explicit `0`,
and negative experience. Assert the negative case stays on step 2 and shows a
field error.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
cd frontend && CI=true npx craco test --watchAll=false \
  --runTestsByPath src/features/teachers/components/wizards/__tests__/AddTeacherWizard.test.js
```

Expected: empty degree/rank block navigation, empty experience becomes `0`, and
review values are blank rather than `غير مضاف`.

- [ ] **Step 3: Implement minimal wizard changes**

Initialize:

```javascript
const [qualData, setQualData] = useState({
  academic_degree: null,
  teacher_rank: null,
  years_of_experience: null,
});
```

Remove `required` from the three `FormField` calls and remove degree/rank
required checks. Preserve experience input with:

```javascript
const raw = e.target.value;
setQualData(p => ({
  ...p,
  years_of_experience: raw === '' ? null : Number(raw),
}));
```

Validate only when experience is non-null and reject non-integer or negative
values. Normalize the submitted qualifications object to nullable values. Render
`غير مضاف` for null/blank degree, rank, and experience; append the years suffix
only when experience is present.

- [ ] **Step 4: Run the focused frontend test**

Run the command from Step 2. Expected: all tests pass.

- [ ] **Step 5: Commit the wizard UI**

```bash
git add frontend/src/features/teachers/components/wizards/AddTeacherWizard.jsx \
  frontend/src/features/teachers/components/wizards/__tests__/AddTeacherWizard.test.js
git commit -m "fix: allow blank teacher qualifications in wizard"
```

### Task 3: Professional edit and clear contract

**Files:**
- Modify: `backend/src/modules/teacher_management/controllers/principal_management_routes.py:320-362`
- Modify: `frontend/src/features/platform/components/management/TeacherProfileDialog.jsx:65-95, 170-185, 350-425`
- Test: `backend/tests/test_teacher_professional_profile_full.py`
- Test: `frontend/src/features/platform/components/management/__tests__/TeacherProfileDialog.professionalData.test.jsx`

- [ ] **Step 1: Write failing backend edit tests**

Create a teacher with all three values, then send:

```python
payload = {
    "academic_degree": None,
    "teacher_rank": "",
    "years_of_experience": None,
}
```

Assert the full profile returns all three as `None`, including legacy
`qualification` and `rank` aliases when read directly. Add invalid supplied
degree/rank/experience cases and assert `422`. Add an omitted-field case proving
unmentioned values remain unchanged.

- [ ] **Step 2: Write failing frontend editor tests**

Open professional edit, clear degree/rank/experience, save, and assert:

```javascript
expect(mockApi.put).toHaveBeenCalledWith(
  '/principal/teacher/t-ahmed-123/professional-info',
  expect.objectContaining({
    academic_degree: null,
    teacher_rank: null,
    years_of_experience: null,
  })
);
```

Add explicit experience `0` and assert the payload preserves `0`.

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```bash
cd backend && ENVIRONMENT=development uv run pytest \
  tests/test_teacher_professional_profile_full.py -q
cd ../frontend && CI=true npx craco test --watchAll=false \
  --runTestsByPath src/features/platform/components/management/__tests__/TeacherProfileDialog.professionalData.test.jsx
```

Expected: backend ignores explicit nulls; frontend coerces blank experience to
zero and does not normalize clears.

- [ ] **Step 4: Implement update presence semantics**

Use Pydantic's `data.model_fields_set` to distinguish omission from explicit
clear:

```python
provided = data.model_fields_set
for field in optional_qualification_fields:
    if field not in provided:
        continue
    value = normalize_optional_value(getattr(data, field))
    updates[field] = value
```

Mirror `academic_degree` to `qualification` and `teacher_rank` to `rank`, even
when clearing to `None`. Reuse the same supported-option and non-negative integer
rules as create. Keep tenant scoping and audit writing unchanged.

In the editor, preserve blank experience as `null`, provide clearable select
controls using the component's supported empty/reset pattern, and normalize the
three optional values before `api.put`.

- [ ] **Step 5: Run focused edit tests**

Run both commands from Step 3. Expected: all tests pass.

- [ ] **Step 6: Commit edit support**

```bash
git add backend/src/modules/teacher_management/controllers/principal_management_routes.py \
  backend/tests/test_teacher_professional_profile_full.py \
  frontend/src/features/platform/components/management/TeacherProfileDialog.jsx \
  frontend/src/features/platform/components/management/__tests__/TeacherProfileDialog.professionalData.test.jsx
git commit -m "fix: support clearing teacher qualifications"
```

### Task 4: Regression and runtime verification

**Files:**
- Verify only; modify prior files only if a failing assertion identifies a defect in this feature.

- [ ] **Step 1: Run focused suites together**

```bash
cd backend && ENVIRONMENT=development uv run pytest \
  tests/test_teacher_professional_profile_full.py \
  tests/test_teacher_restore_create_contract.py -q
cd ../frontend && CI=true npx craco test --watchAll=false \
  --runTestsByPath \
  src/features/teachers/components/wizards/__tests__/AddTeacherWizard.test.js \
  src/features/platform/components/management/__tests__/TeacherProfileDialog.professionalData.test.jsx
```

Expected: all tests pass, including duplicate identity and restore protections.

- [ ] **Step 2: Run project gates**

```bash
bash scripts/ci/run_gate_local.sh backend
bash scripts/ci/run_gate_local.sh frontend
```

Expected: both gates exit `0`. If unrelated pre-existing failures occur, capture
their exact output and still verify every touched focused suite passes.

- [ ] **Step 3: Restart and inspect the application**

Restart `Backend API` and `Frontend Dev` once. Verify the principal teacher
wizard at `/principal/users-classes`:

- qualification labels have no asterisks;
- Next works with all three blank;
- review displays `غير مضاف`;
- empty, partial, complete, and explicit-zero submissions succeed;
- malformed supplied values are blocked;
- editing can add and clear values.

- [ ] **Step 4: Check logs and final diff**

Confirm no new backend exceptions or browser console errors. Run:

```bash
git diff --check
git status --short
```

Expected: clean diff checks and only intentional files present.