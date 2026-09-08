> **This file is the original requirement specification** — the brief the system
> was built against, kept unedited so the finished work can be checked against
> what was actually asked for. It is not documentation of the system as built.
>
> For that, read the [README](README.md) or the reference set in
> [`docs/`](docs/README.md).
>
> Implementation by Sai Kushal ([@Saikushal185](https://github.com/Saikushal185)).

---

Build a complete production-quality full-stack application for an
“Automated Interview Scheduling and Evaluation Management System”.

The main purpose of the system is to automatically schedule interviews
using faculty availability, free time slots, panel groups, and flexible
scheduling constraints. The system must also support interview evaluation
using 7 predefined evaluation metrics provided through Excel input files.

====================================================
1. PROJECT GOAL
====================================================

The application should solve two connected problems:

A. AUTOMATED INTERVIEW SCHEDULING
Automatically generate an optimized and conflict-free interview schedule
for candidates based on:

- Candidate availability
- Faculty availability
- Faculty free slots
- Interview duration
- Panel groups
- Required number of faculty members per panel
- Faculty conflicts
- Candidate conflicts
- Break periods
- Time constraints
- Flexible scheduling preferences
- Existing bookings
- Manual constraints

B. INTERVIEW EVALUATION MANAGEMENT

After interviews, store and analyze evaluation data based on 7 evaluation
metrics.

The 7 evaluation metrics must be configurable and must not be hardcoded
deeply into the application.

====================================================
2. USER INTERFACE
====================================================

Build a professional modern web dashboard.

Main pages:

1. Dashboard
2. Data / Excel Upload
3. Candidates
4. Faculty
5. Faculty Availability
6. Free Slots
7. Panel Groups
8. Automated Scheduler
9. Interview Schedule
10. Evaluation Management
11. Analytics and Reports
12. Settings

====================================================
3. EXCEL INPUT
====================================================

Excel files will be the primary input source.

Support .xlsx and .csv files.

The application should support multiple Excel sheets or structured files.

Possible input entities include:

CANDIDATES:
- candidate_id
- candidate_name
- email
- preferred_date
- preferred_time
- availability
- additional constraints

FACULTY:
- faculty_id
- faculty_name
- department
- email

FACULTY AVAILABILITY:
- faculty_id
- date
- start_time
- end_time
- availability_status

PANEL GROUPS:
- panel_id
- panel_name
- faculty_members
- minimum_panel_size
- maximum_panel_size

INTERVIEW SETTINGS:
- interview_duration
- break_duration
- start_time
- end_time
- scheduling_date_range

EVALUATION:
The evaluation Excel sheet contains 7 metric columns.

Example:

candidate_id
metric_1
metric_2
metric_3
metric_4
metric_5
metric_6
metric_7

The application should validate all uploaded Excel files and show clear
errors when required columns are missing or data formats are invalid.

Do not hardcode the 7 metric names. Read them from configuration or
column mappings.

====================================================
4. FACULTY FREE SLOT MANAGEMENT
====================================================

The system must calculate faculty free slots automatically.

Example:

Faculty A:
Busy: 10:00–11:00
Busy: 13:00–14:00

Available window:
09:00–17:00

Calculated free slots:
09:00–10:00
11:00–13:00
14:00–17:00

Free slots must be automatically recalculated whenever:

- Faculty availability changes
- An interview is scheduled
- An interview is rescheduled
- An interview is cancelled

====================================================
5. PANEL GROUP MANAGEMENT
====================================================

Allow administrators to create interview panels.

Example:

Panel A:
- Faculty 1
- Faculty 2
- Faculty 3

Panel B:
- Faculty 4
- Faculty 5
- Faculty 6

The system should:

- Store panel groups
- Allow faculty to belong to panels
- Detect faculty conflicts
- Identify whether the complete panel is available
- Find alternative panel groups when the preferred panel is unavailable
- Allow automatic or manual panel assignment

====================================================
6. AUTOMATED SCHEDULING ENGINE
====================================================

Build a scheduling engine that automatically assigns:

Candidate
    +
Available time slot
    +
Available faculty/panel
    =
Conflict-free interview schedule

The scheduler must ensure:

1. A candidate cannot have overlapping interviews.
2. A faculty member cannot have overlapping interviews.
3. A panel cannot be double-booked.
4. Interviews are scheduled only in valid faculty free slots.
5. Interview duration is respected.
6. Break times are respected.
7. Existing bookings are respected.
8. Candidate and faculty availability is respected.
9. Scheduling conflicts are minimized.
10. The generated schedule should be optimized.

====================================================
7. FLEXIBLE SCHEDULING
====================================================

Implement flexible scheduling rules.

Each scheduling requirement should support priorities such as:

- HARD CONSTRAINT
- HIGH PRIORITY
- MEDIUM PRIORITY
- LOW PRIORITY
- FLEXIBLE

Examples:

Hard constraint:
Faculty member is unavailable.

High priority:
Candidate preferred date.

Medium priority:
Candidate preferred time.

Low priority:
Preferred panel.

Flexible:
System may choose another suitable slot or panel.

The scheduling engine should satisfy hard constraints first and optimize
soft constraints using a scoring system.

====================================================
8. SCHEDULING ALGORITHM
====================================================

Use a constraint-based scheduling approach.

Represent the problem as a constraint satisfaction / optimization problem.

Suggested process:

1. Load candidates.
2. Load faculty availability.
3. Calculate faculty free slots.
4. Load panel groups.
5. Generate valid candidate × panel × time-slot combinations.
6. Remove combinations violating hard constraints.
7. Score remaining combinations.
8. Assign the best possible slot.
9. Detect conflicts.
10. Try alternative slots/panels when conflicts occur.
11. Return scheduled and unscheduled candidates.
12. Provide a reason for every unscheduled candidate.

Implement the scheduling engine using a modular architecture so the
algorithm can later be replaced with:

- Greedy scheduling
- Backtracking
- Constraint programming
- Integer optimization

The system should be scalable.

====================================================
9. SCHEDULING RESULT
====================================================

Each generated interview schedule should contain:

- schedule_id
- candidate
- date
- start_time
- end_time
- assigned_panel
- faculty members
- status
- scheduling_score
- priority information

Possible status:

- Scheduled
- Pending
- Conflict
- Unscheduled
- Rescheduled
- Cancelled
- Completed

====================================================
10. MANUAL OVERRIDE
====================================================

Automation must not remove administrator control.

Allow the administrator to:

- Manually change a candidate's time
- Change the panel
- Change faculty members
- Lock a schedule
- Reschedule an interview
- Cancel an interview
- Mark a faculty member unavailable

After every manual change:

- Recalculate conflicts
- Recalculate affected faculty free slots
- Show warnings
- Preserve schedule history

====================================================
11. DASHBOARD
====================================================

Create a dashboard with summary cards such as:

- Total Candidates
- Scheduled Candidates
- Unscheduled Candidates
- Total Faculty
- Available Faculty
- Total Panel Groups
- Available Free Slots
- Scheduling Success Rate
- Conflicts Detected

Include:

- Upcoming interviews
- Recent scheduling activity
- Unscheduled candidates
- Conflict alerts
- Faculty availability overview

====================================================
12. SCHEDULE VIEW
====================================================

Create a visual schedule/calendar.

Support:

- Day view
- Week view
- Table view

Allow filtering by:

- Candidate
- Faculty
- Panel
- Date
- Department
- Schedule status

Clearly show conflicts and unavailable periods.

====================================================
13. EVALUATION MODULE
====================================================

The system must support 7 configurable evaluation metrics.

For each candidate:

- Store scores for all 7 metrics
- Calculate overall score
- Support configurable metric weights
- Calculate normalized scores where required
- Generate rankings
- Identify strongest and weakest metrics

Use configurable formulas.

Example:

overall_score =
(metric_1 × weight_1) +
(metric_2 × weight_2) +
...
(metric_7 × weight_7)

Do not hardcode metric names or weights.

====================================================
14. ANALYTICS
====================================================

Create analytics for:

- Performance across 7 metrics
- Average score per metric
- Candidate ranking
- Score distribution
- Panel/faculty evaluation statistics
- Scheduled vs unscheduled candidates
- Faculty workload
- Panel workload
- Slot utilization
- Scheduling efficiency

Include:

- Bar charts
- Radar charts for candidate metric profiles
- Line charts when time-series data exists
- Tables

====================================================
15. TECHNOLOGY STACK
====================================================

Use:

FRONTEND:
- Next.js
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Query / TanStack Query

BACKEND:
- Python
- FastAPI
- Pydantic

DATABASE:
- PostgreSQL

ORM:
- SQLAlchemy

DATA PROCESSING:
- Pandas
- OpenPyXL

AUTHENTICATION:
- JWT or secure session-based authentication

CHARTS:
- Recharts

CALENDAR:
- FullCalendar or an equivalent production-quality calendar library

CONTAINERIZATION:
- Docker
- Docker Compose

====================================================
16. DATABASE DESIGN
====================================================

Create tables for:

- users
- candidates
- faculty
- faculty_availability
- faculty_busy_slots
- faculty_free_slots
- panel_groups
- panel_members
- interviews
- interview_schedule_history
- evaluation_metrics
- evaluations
- evaluation_scores
- uploaded_files
- scheduling_constraints

Design proper foreign keys, indexes and timestamps.

====================================================
17. API DESIGN
====================================================

Create REST APIs for:

- Excel upload
- Data validation
- Candidate CRUD
- Faculty CRUD
- Faculty availability CRUD
- Free slot calculation
- Panel CRUD
- Automated schedule generation
- Schedule preview
- Schedule confirmation
- Manual rescheduling
- Conflict detection
- Evaluation management
- Dashboard analytics
- Report generation

====================================================
18. AUTOMATION WORKFLOW
====================================================

The primary workflow should be:

Excel Upload
    ↓
Validate Input
    ↓
Store Candidates
    ↓
Store Faculty
    ↓
Read Faculty Availability
    ↓
Calculate Faculty Free Slots
    ↓
Load Panel Groups
    ↓
Generate Scheduling Constraints
    ↓
Automated Scheduling Engine
    ↓
Conflict Detection
    ↓
Flexible Optimization
    ↓
Generate Final Schedule
    ↓
Dashboard / Calendar
    ↓
Manual Override if Required
    ↓
Interview Completion
    ↓
Enter/Upload 7-Metric Evaluation
    ↓
Calculate Results
    ↓
Analytics and Reports

====================================================
19. CODE QUALITY
====================================================

The application must:

- Use clean architecture
- Separate frontend and backend
- Use service layers
- Use repository patterns where appropriate
- Have modular scheduling logic
- Have centralized configuration
- Include input validation
- Include proper error handling
- Include logging
- Include API documentation
- Include unit tests for the scheduling algorithm
- Include sample Excel files
- Include sample seed data
- Include a comprehensive README
- Include Docker setup instructions

====================================================
20. IMPORTANT IMPLEMENTATION REQUIREMENT
====================================================

Do not build a mock dashboard with fake static data.

Implement the actual complete workflow:

Excel → Validation → Database → Availability →
Free Slot Calculation → Panel Assignment →
Automated Scheduling → Conflict Detection →
Schedule Dashboard → Evaluation → Analytics.

The automated scheduler must contain real scheduling logic and must not
randomly assign candidates to time slots.

Generate the complete project incrementally and provide a runnable,
production-quality codebase.