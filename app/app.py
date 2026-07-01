import os
import sqlite3
import hashlib
import hmac
import secrets
from datetime import date, datetime
from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

DB_PATH = os.getenv("DB_PATH", "/data/training_tracker.db")
APP_VERSION = "v5"

st.set_page_config(
    page_title="Training Operations Tracker",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    :root {
        --card-bg: #ffffff;
        --soft-bg: #f6f8fb;
        --line: #e7ecf3;
        --primary: #1f4e79;
        --accent: #2f80ed;
        --success: #16865f;
        --warning: #b26a00;
        --danger: #b42318;
        --text-muted: #667085;
    }
    .main .block-container {padding-top: 1.25rem; padding-bottom: 2.5rem;}
    section[data-testid="stSidebar"] {background: linear-gradient(180deg, #102a43 0%, #163b5c 100%);}
    section[data-testid="stSidebar"] * {color: #f8fbff !important;}
    section[data-testid="stSidebar"] div[role="radiogroup"] label {border-radius: 10px; padding: .35rem .5rem;}
    .hero-card {
        background: linear-gradient(135deg, #102a43 0%, #1f4e79 55%, #2f80ed 100%);
        border-radius: 18px;
        padding: 1.4rem 1.6rem;
        color: white;
        box-shadow: 0 18px 45px rgba(16, 42, 67, .18);
        margin-bottom: 1rem;
    }
    .hero-card h1 {font-size: 2.05rem; margin: 0 0 .35rem 0; color: white;}
    .hero-card p {margin: 0; color: #eaf2ff; font-size: 1rem;}
    .section-card {
        background: var(--card-bg);
        border: 1px solid var(--line);
        border-radius: 16px;
        padding: 1.05rem 1.15rem;
        box-shadow: 0 8px 24px rgba(16, 42, 67, .06);
        margin-bottom: .75rem;
    }
    .metric-card {
        background: #ffffff;
        border: 1px solid #e7ecf3;
        border-radius: 16px;
        padding: 1rem 1.1rem;
        box-shadow: 0 8px 24px rgba(16, 42, 67, .06);
        min-height: 112px;
    }
    .metric-label {font-size: .84rem; color: #667085; margin-bottom: .2rem;}
    .metric-value {font-size: 2rem; font-weight: 800; color: #102a43; line-height: 1.05;}
    .metric-help {font-size: .78rem; color: #667085; margin-top: .35rem;}
    .status-pill {display:inline-block; padding:.22rem .55rem; border-radius:999px; font-size:.75rem; font-weight:700;}
    .public-class-card {background:#ffffff; border:1px solid #e7ecf3; border-radius:14px; padding:.72rem .82rem; margin:.25rem 0 .45rem 0; box-shadow:0 6px 16px rgba(16,42,67,.05); min-height:150px;}
    .public-class-title {font-size:.94rem; font-weight:800; color:#102a43; line-height:1.15;}
    .public-class-meta {color:#667085; font-size:.78rem; margin-top:.18rem; line-height:1.25;}
    .seat-pill {display:inline-block; padding:.16rem .45rem; border-radius:999px; font-size:.72rem; font-weight:800; margin-top:.35rem;}
    .seat-open {background:#e7f7ef; color:#087443;}
    .seat-full {background:#fdecec; color:#b42318;}
    .selected-class-box {background:linear-gradient(135deg,#f8fbff,#eef6ff); border:1px solid #cfe1f7; border-radius:16px; padding:1rem; margin:.75rem 0 1rem 0;}
    .pod-ready {background:#e7f7ef; border:2px solid #16865f; color:#087443; border-radius:16px; padding:.9rem; text-align:center; font-weight:800; box-shadow:0 0 0 4px rgba(22,134,95,.08);}
    .pod-not-ready {background:#fdecec; border:2px solid #b42318; color:#b42318; border-radius:16px; padding:.9rem; text-align:center; font-weight:800; box-shadow:0 0 0 4px rgba(180,35,24,.08);}
    .pod-partial {background:#fff3dc; border:2px solid #b26a00; color:#b26a00; border-radius:16px; padding:.9rem; text-align:center; font-weight:800; box-shadow:0 0 0 4px rgba(178,106,0,.08);}
    .pill-green {background:#e7f7ef; color:#087443;}
    .pill-blue {background:#eaf2ff; color:#175cd3;}
    .pill-orange {background:#fff3dc; color:#b26a00;}
    .pill-red {background:#fdecec; color:#b42318;}
    .muted {color:#667085;}
    div[data-testid="stExpander"] {border-radius: 14px; border: 1px solid #e7ecf3; overflow: hidden;}
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 10px;
        border: 1px solid #1f4e79;
        background: #1f4e79;
        color: white;
        font-weight: 700;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {border-color:#2f80ed; background:#2f80ed; color:white;}

    .top-link {text-align:right; margin-bottom:.5rem;}
    .public-topbar {display:flex; justify-content:space-between; align-items:center; margin-bottom:.75rem;}
    .portal-badge {background:#eaf2ff; color:#175cd3; border-radius:999px; padding:.25rem .65rem; font-weight:800; font-size:.78rem;}
    .lab-card {border:1px solid #e7ecf3; border-radius:16px; padding:1rem; background:white; box-shadow:0 8px 24px rgba(16,42,67,.06); margin-bottom:.75rem;}
    .lab-dot {font-size:1.35rem; line-height:1;}
    .tiny-label {font-size:.75rem; color:#667085; text-transform:uppercase; letter-spacing:.04em; font-weight:700;}
    .progress-shell {height:16px; border-radius:999px; background:#eef2f6; overflow:hidden; border:1px solid #e7ecf3;}
    .progress-fill {height:100%; background:linear-gradient(90deg,#1f4e79,#2f80ed); border-radius:999px;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def get_conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS instructors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            specialty TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS attendees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            organization TEXT,
            role TEXT,
            status TEXT DEFAULT 'Active',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_code TEXT,
            title TEXT NOT NULL,
            category TEXT,
            level TEXT,
            duration_hours REAL DEFAULT 0,
            description TEXT,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS class_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL,
            instructor_id INTEGER,
            session_name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            delivery_type TEXT,
            location TEXT,
            capacity INTEGER DEFAULT 20,
            status TEXT DEFAULT 'Scheduled',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(course_id) REFERENCES courses(id),
            FOREIGN KEY(instructor_id) REFERENCES instructors(id)
        );

        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            attendee_id INTEGER NOT NULL,
            enrollment_status TEXT DEFAULT 'Enrolled',
            completion_status TEXT DEFAULT 'Not Started',
            completion_date TEXT,
            score REAL,
            certificate_issued INTEGER DEFAULT 0,
            pod_setup INTEGER DEFAULT 0,
            pod_name TEXT,
            pod_setup_at TEXT,
            pod_notes TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(session_id, attendee_id),
            FOREIGN KEY(session_id) REFERENCES class_sessions(id),
            FOREIGN KEY(attendee_id) REFERENCES attendees(id)
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT,
            email TEXT,
            role TEXT DEFAULT 'Instructor',
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # Lightweight migrations for users upgrading from v2 database files.
    for coldef in [
        "pod_setup INTEGER DEFAULT 0",
        "pod_name TEXT",
        "pod_setup_at TEXT",
        "pod_notes TEXT",
        "pod_account INTEGER DEFAULT 0",
        "pod_snapshot INTEGER DEFAULT 0",
        "pod_docs INTEGER DEFAULT 0",
        "lab_build_status TEXT DEFAULT 'Not Started'",
    ]:
        try:
            cur.execute(f"ALTER TABLE enrollments ADD COLUMN {coldef}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()


def run_query(query, params=None):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params or [])
    conn.close()
    return df


def execute(query, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params or [])
    conn.commit()
    conn.close()


def execute_insert(query, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params or [])
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def execute_many(query, rows):
    conn = get_conn()
    cur = conn.cursor()
    cur.executemany(query, rows)
    conn.commit()
    conn.close()


def hash_password(password: str, salt: str | None = None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return digest.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str):
    new_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(new_hash, stored_hash)


def ensure_default_admin():
    users = run_query("SELECT id FROM users LIMIT 1")
    if users.empty:
        default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
        password_hash, salt = hash_password(default_password)
        execute(
            "INSERT INTO users (username, full_name, email, role, password_hash, salt, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
            ["admin", "Default Admin", "", "Admin", password_hash, salt],
        )


def get_upcoming_public_sessions():
    today = date.today().isoformat()
    return run_query(
        """
        SELECT s.id, s.session_name, s.start_date, s.end_date, s.delivery_type, s.location, s.capacity, s.status,
               c.title AS course_title, c.course_code, c.category, c.level, c.duration_hours, c.description,
               i.name AS instructor_name,
               COALESCE(SUM(CASE WHEN e.enrollment_status IN ('Enrolled','Pending Approval','Waitlisted') THEN 1 ELSE 0 END), 0) AS signed_up,
               COALESCE(SUM(CASE WHEN e.enrollment_status='Enrolled' THEN 1 ELSE 0 END), 0) AS approved_count,
               COALESCE(SUM(CASE WHEN e.enrollment_status='Pending Approval' THEN 1 ELSE 0 END), 0) AS pending_count
        FROM class_sessions s
        JOIN courses c ON s.course_id = c.id
        LEFT JOIN instructors i ON s.instructor_id = i.id
        LEFT JOIN enrollments e ON e.session_id = s.id
        WHERE c.active=1
          AND s.status IN ('Scheduled','In Progress')
          AND s.start_date >= ?
        GROUP BY s.id
        ORDER BY s.start_date ASC, c.title ASC
        """,
        [today],
    )


def submit_public_signup(session_id, name, email, organization, role, notes):
    email = email.strip().lower()
    existing_attendee = run_query("SELECT id FROM attendees WHERE lower(email)=? LIMIT 1", [email])
    if existing_attendee.empty:
        attendee_id = execute_insert(
            "INSERT INTO attendees (name, email, organization, role, status, notes) VALUES (?, ?, ?, ?, 'Active', ?)",
            [name.strip(), email, organization.strip(), role.strip(), f"Self-signup created {datetime.now().isoformat(timespec='seconds')}"]
        )
    else:
        attendee_id = int(existing_attendee.iloc[0]["id"])
        execute(
            "UPDATE attendees SET name=COALESCE(NULLIF(?, ''), name), organization=COALESCE(NULLIF(?, ''), organization), role=COALESCE(NULLIF(?, ''), role) WHERE id=?",
            [name.strip(), organization.strip(), role.strip(), attendee_id]
        )
    try:
        execute(
            """
            INSERT INTO enrollments (session_id, attendee_id, enrollment_status, completion_status, notes)
            VALUES (?, ?, 'Pending Approval', 'Not Started', ?)
            """,
            [session_id, attendee_id, f"Self-signup request submitted {datetime.now().isoformat(timespec='seconds')}. {notes}".strip()]
        )
        return True, "Signup submitted. An instructor/admin can approve the request from Signup Requests."
    except sqlite3.IntegrityError:
        return False, "That email is already signed up for this class. Contact the instructor/admin if the status needs to be changed."


def public_signup_page(show_login_button=True):
    hero("Upcoming Training Signup", "Browse upcoming classes, select one, then request a seat for that specific class. Instructor/admin areas require sign-in.")
    sessions = get_upcoming_public_sessions()
    if sessions.empty:
        st.info("There are no upcoming classes open for signup yet.")
    else:
        st.markdown("### Upcoming Classes")
        st.caption("Select a class tile to open the signup form for that specific session.")

        if "selected_public_session_id" not in st.session_state and not sessions.empty:
            st.session_state["selected_public_session_id"] = int(sessions.iloc[0]["id"])

        cols_per_row = 3
        rows = [sessions.iloc[i:i + cols_per_row] for i in range(0, len(sessions), cols_per_row)]
        for group in rows:
            cols = st.columns(cols_per_row)
            for idx, (_, row) in enumerate(group.iterrows()):
                with cols[idx]:
                    remaining = max(int(row["capacity"] or 0) - int(row["approved_count"] or 0), 0)
                    seat_class = "seat-open" if remaining > 0 else "seat-full"
                    seat_label = f"{remaining} seats left" if remaining > 0 else "Full / waitlist"
                    selected = int(st.session_state.get("selected_public_session_id", 0)) == int(row["id"])
                    card_border = "#2f80ed" if selected else "#e7ecf3"
                    card = f"""
                    <div class="public-class-card" style="border-color:{card_border};">
                        <div class="public-class-title">{row['course_title']}</div>
                        <div class="public-class-meta"><b>{row['session_name']}</b></div>
                        <div class="public-class-meta">{row['start_date']} → {row['end_date']}</div>
                        <div class="public-class-meta">{row['delivery_type'] or ''} · {row['location'] or 'Location TBD'}</div>
                        <div class="public-class-meta">Instructor: {row['instructor_name'] or 'TBD'}</div>
                        <div class="seat-pill {seat_class}">{seat_label}</div>
                    </div>
                    """
                    st.markdown(card, unsafe_allow_html=True)
                    button_label = "Selected" if selected else "Select Class"
                    if st.button(button_label, key=f"select_public_session_{int(row['id'])}", use_container_width=True):
                        st.session_state["selected_public_session_id"] = int(row["id"])
                        st.rerun()

        selected_id = int(st.session_state.get("selected_public_session_id", int(sessions.iloc[0]["id"])))
        selected_row = sessions[sessions["id"] == selected_id]
        if selected_row.empty:
            selected_row = sessions.iloc[[0]]
            selected_id = int(selected_row.iloc[0]["id"])
            st.session_state["selected_public_session_id"] = selected_id
        selected_row = selected_row.iloc[0]
        selected_remaining = max(int(selected_row["capacity"] or 0) - int(selected_row["approved_count"] or 0), 0)

        st.markdown("### Request a Seat")
        st.markdown(
            f"""
            <div class="selected-class-box">
                <div class="public-class-title">Signing up for: {selected_row['course_title']} · {selected_row['session_name']}</div>
                <div class="public-class-meta">{selected_row['start_date']} to {selected_row['end_date']} · {selected_row['delivery_type'] or ''} · {selected_row['location'] or 'Location TBD'}</div>
                <div class="public-class-meta">Capacity: {int(selected_row['capacity'] or 0)} · Approved: {int(selected_row['approved_count'] or 0)} · Pending: {int(selected_row['pending_count'] or 0)} · Seats remaining: {selected_remaining}</div>
                <div class="public-class-meta">{selected_row['description'] or ''}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("public_signup_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full Name *")
            email = c2.text_input("Email *")
            c3, c4 = st.columns(2)
            organization = c3.text_input("Organization")
            role = c4.text_input("Role / Job Title")
            notes = st.text_area("Notes / Questions")
            submitted = st.form_submit_button("Submit Signup Request")
            if submitted:
                if not name.strip() or not email.strip() or "@" not in email:
                    st.error("Full name and a valid email are required.")
                else:
                    ok, message = submit_public_signup(selected_id, name, email, organization, role, notes)
                    if ok:
                        st.success(message)
                    else:
                        st.warning(message)
    st.divider()
    st.markdown("### Check Registration Status")
    with st.form("public_status_check"):
        status_email = st.text_input("Email used for signup")
        check = st.form_submit_button("Check Status")
        if check:
            if not status_email.strip():
                st.warning("Enter the email address used during signup.")
            else:
                status_df = run_query("""
                    SELECT a.name, c.title AS course, s.session_name, s.start_date, e.enrollment_status, e.completion_status, e.pod_name, e.pod_setup
                    FROM enrollments e
                    JOIN attendees a ON e.attendee_id=a.id
                    JOIN class_sessions s ON e.session_id=s.id
                    JOIN courses c ON s.course_id=c.id
                    WHERE lower(a.email)=lower(?)
                    ORDER BY s.start_date DESC
                """, [status_email.strip()])
                if status_df.empty:
                    st.info("No registrations found for that email address.")
                else:
                    st.dataframe(status_df, use_container_width=True, hide_index=True)
    if show_login_button:
        st.divider()
        c1, c2 = st.columns([3,1])
        with c1:
            st.caption("Instructor and admin functions are protected. Public users can browse and register without signing in.")
        with c2:
            if st.button("Instructor/Admin Sign In"):
                st.session_state["show_login"] = True
                st.rerun()


def login_page():
    ensure_default_admin()
    hero("Instructor/Admin Sign In", "Manage instructors, attendees, courses, class rosters, lab POD readiness, signups, and completions.")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")
        if submitted:
            user = run_query("SELECT * FROM users WHERE username=? AND active=1", [username.strip()])
            if not user.empty and verify_password(password, user.iloc[0]["password_hash"], user.iloc[0]["salt"]):
                st.session_state["authenticated"] = True
                st.session_state["user"] = user.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("Invalid username or password, or the account is inactive.")
    st.info("First run default account: username `admin`, password `admin123`. Change this by creating another admin account or setting DEFAULT_ADMIN_PASSWORD before first launch.")
    if st.button("Back to Public Signup"):
        st.session_state["show_login"] = False
        st.rerun()
    st.stop()


def require_login():
    ensure_default_admin()
    if st.session_state.get("authenticated"):
        return
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
    if st.session_state.get("show_login"):
        login_page()
    else:
        public_signup_page(show_login_button=True)
        st.stop()


def options_from_df(df, label_col="name"):
    if df.empty:
        return {}
    return {f"{row[label_col]} (ID {row['id']})": int(row["id"]) for _, row in df.iterrows()}


def export_excel(sheets: dict):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, df in sheets.items():
            safe = df.copy()
            safe.to_excel(writer, sheet_name=name[:31], index=False)
            worksheet = writer.sheets[name[:31]]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
                worksheet.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 45)
    return output.getvalue()


def seed_demo_data():
    if not run_query("SELECT id FROM instructors LIMIT 1").empty:
        return False
    instructors = [
        ("Chris McNeil", "chris@example.com", "VCF / NSX / Aria", "Active", "Lead instructor"),
        ("Morgan Lee", "morgan@example.com", "vSphere / Storage", "Active", "Backup instructor"),
        ("Taylor Brooks", "taylor@example.com", "Security / Operations", "Contract", "Guest instructor"),
    ]
    attendees = [
        ("Alex Carter", "alex@example.com", "Acme Federal", "Systems Engineer", "Active", ""),
        ("Jamie Rivera", "jamie@example.com", "Acme Federal", "Cloud Admin", "Active", ""),
        ("Sam Patel", "sam@example.com", "Northwind", "Network Engineer", "Active", ""),
        ("Riley Stone", "riley@example.com", "Northwind", "Platform Engineer", "Active", ""),
        ("Jordan Kim", "jordan@example.com", "Contoso", "Infrastructure Lead", "Active", ""),
    ]
    courses = [
        ("VCF9-DEPLOY-101", "VCF 9 Deployment Lab", "VCF", "Intermediate", 8, "Hands-on VCF 9 deployment workflow", 1),
        ("VCF9-DAY2-201", "VCF 9 Day 2 Configuration", "VCF", "Intermediate", 6, "Post-deployment configuration and validation", 1),
        ("NSX-OPS-201", "NSX Operations Workshop", "NSX", "Advanced", 6, "NSX operations and troubleshooting", 1),
    ]
    execute_many("INSERT INTO instructors (name,email,specialty,status,notes) VALUES (?,?,?,?,?)", instructors)
    execute_many("INSERT INTO attendees (name,email,organization,role,status,notes) VALUES (?,?,?,?,?,?)", attendees)
    execute_many("INSERT INTO courses (course_code,title,category,level,duration_hours,description,active) VALUES (?,?,?,?,?,?,?)", courses)
    execute("""
        INSERT INTO class_sessions (course_id,instructor_id,session_name,start_date,end_date,delivery_type,location,capacity,status,notes)
        VALUES (1,1,'VCF 9 Deployment Lab - June Cohort',?,?,?,?,?,?,?)
    """, [date.today().isoformat(), date.today().isoformat(), "Virtual", "Teams / Lab Portal", 12, "Scheduled", "Demo seeded session"])
    for idx, attendee_id in enumerate([1, 2, 3], start=1):
        execute("INSERT INTO enrollments (session_id, attendee_id, enrollment_status, completion_status, score, certificate_issued, pod_setup, pod_account, pod_snapshot, pod_docs, lab_build_status, pod_name, pod_notes, notes) VALUES (1, ?, 'Enrolled', 'Not Started', 0, 0, ?, ?, ?, ?, ?, ?, '', '')", [attendee_id, 1 if idx < 3 else 0, 1 if idx < 3 else 0, 1 if idx == 1 else 0, 1 if idx == 1 else 0, 'Ready' if idx == 1 else ('Building' if idx == 2 else 'Not Started'), f"POD-{idx:02d}"])
    return True


def metric_card(label, value, help_text=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-help">{help_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(title, subtitle):
    st.markdown(f"""<div class="hero-card"><h1>{title}</h1><p>{subtitle}</p></div>""", unsafe_allow_html=True)


def status_badge(status):
    color = "pill-blue"
    if status in ["Completed", "Active", "Enrolled", "Scheduled"]:
        color = "pill-green"
    elif status in ["In Progress", "Waitlisted", "Contract"]:
        color = "pill-orange"
    elif status in ["Failed", "Canceled", "Dropped", "No Show", "Inactive", "Unavailable"]:
        color = "pill-red"
    return f'<span class="status-pill {color}">{status}</span>'


init_db()
require_login()

with st.sidebar:
    user = st.session_state.get("user", {})
    st.markdown("### 🎓 Training Ops")
    st.caption(f"Training Tracker {APP_VERSION}")
    st.caption(f"Signed in: {user.get('full_name') or user.get('username')} · {user.get('role')}")
    if st.button("Sign Out"):
        st.session_state.clear()
        st.rerun()
    menu = st.radio(
        "Navigation",
        [
            "Command Center",
            "Public Portal Preview",
            "Instructors",
            "Attendees",
            "Courses",
            "Class Sessions",
            "Enrollments & Completions",
            "Course Rosters & PODs",
            "Lab Builder Queue",
            "Signup Requests",
            "Reports & Export",
            "User Management",
            "Admin",
        ],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Built for tracking instructor-led labs, customer cohorts, course completion, certificates, and training outcomes.")

instructors_df = run_query("SELECT * FROM instructors ORDER BY name")
attendees_df = run_query("SELECT * FROM attendees ORDER BY name")
courses_df = run_query("SELECT * FROM courses ORDER BY title")
sessions_df = run_query(
    """
    SELECT s.*, c.title AS course_title, c.course_code, c.category, i.name AS instructor_name
    FROM class_sessions s
    JOIN courses c ON s.course_id = c.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    ORDER BY s.start_date DESC
    """
)
completion_df = run_query(
    """
    SELECT
        e.id,
        a.name AS attendee,
        a.email AS attendee_email,
        a.organization,
        a.role,
        c.title AS course,
        c.course_code,
        c.category,
        s.session_name,
        s.start_date,
        s.end_date,
        s.delivery_type,
        i.name AS instructor,
        e.enrollment_status,
        e.completion_status,
        e.completion_date,
        e.score,
        e.certificate_issued,
        e.pod_setup,
        e.pod_account,
        e.pod_snapshot,
        e.pod_docs,
        e.lab_build_status,
        e.pod_name,
        e.pod_setup_at,
        e.pod_notes,
        e.notes
    FROM enrollments e
    JOIN attendees a ON e.attendee_id = a.id
    JOIN class_sessions s ON e.session_id = s.id
    JOIN courses c ON s.course_id = c.id
    LEFT JOIN instructors i ON s.instructor_id = i.id
    ORDER BY s.start_date DESC, a.name
    """
)

completed_count = int((completion_df["completion_status"] == "Completed").sum()) if not completion_df.empty else 0
enrolled_count = int((completion_df["enrollment_status"] == "Enrolled").sum()) if not completion_df.empty else 0
cert_count = int((completion_df["certificate_issued"] == 1).sum()) if not completion_df.empty else 0
completion_rate = round((completed_count / enrolled_count) * 100, 1) if enrolled_count else 0

if menu == "Command Center":
    hero("Training Operations Command Center", "Track instructors, students, courses, sessions, enrollments, completions, certificates, and training delivery health.")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: metric_card("Instructors", len(instructors_df), "Active delivery resources")
    with m2: metric_card("Attendees", len(attendees_df), "People in the roster")
    with m3: metric_card("Courses", len(courses_df), "Reusable course catalog")
    with m4: metric_card("Sessions", len(sessions_df), "Scheduled or completed classes")
    with m5: metric_card("Completion Rate", f"{completion_rate}%", f"{completed_count} completions")

    st.markdown("### Delivery Snapshot")
    left, middle, right = st.columns([1.1, 1, 1])
    with left:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Completion Status")
        if completion_df.empty:
            st.info("No enrollment data yet. Add attendees, sessions, and enrollments to activate the dashboard.")
        else:
            status_counts = completion_df["completion_status"].value_counts().reset_index()
            status_counts.columns = ["Completion Status", "Count"]
            fig = px.pie(status_counts, names="Completion Status", values="Count", hole=0.45)
            fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), legend_title_text="")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with middle:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Courses by Category")
        if courses_df.empty:
            st.info("No course data yet.")
        else:
            category_counts = courses_df["category"].fillna("Uncategorized").replace("", "Uncategorized").value_counts().reset_index()
            category_counts.columns = ["Category", "Count"]
            fig = px.bar(category_counts, x="Category", y="Count", text="Count")
            fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), xaxis_title="", yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section-card">', unsafe_allow_html=True)
        st.subheader("Certificates")
        metric_card("Issued", cert_count, "Certificates marked complete")
        st.write("")
        metric_card("Enrolled", enrolled_count, "Current enrolled records")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Upcoming / Recent Sessions")
    display_sessions = sessions_df.copy()
    if not display_sessions.empty:
        display_sessions = display_sessions[["session_name", "course_title", "instructor_name", "start_date", "end_date", "delivery_type", "capacity", "status", "location"]]
    st.dataframe(display_sessions, use_container_width=True, hide_index=True)

elif menu == "Public Portal Preview":
    public_signup_page(show_login_button=False)

elif menu == "Lab Builder Queue":
    hero("Lab Builder Queue", "Track the build lifecycle for student lab PODs across upcoming classes.")
    roster = completion_df[completion_df["enrollment_status"].isin(["Enrolled", "Pending Approval", "Waitlisted"])] if not completion_df.empty else completion_df
    if roster.empty:
        st.info("No enrolled or pending students yet.")
    else:
        session_names = sorted(roster["session_name"].dropna().unique())
        selected_session = st.selectbox("Class Session", session_names)
        session_roster = roster[roster["session_name"] == selected_session].copy()
        total = len(session_roster)
        ready = int((session_roster["pod_setup"] == 1).sum()) if "pod_setup" in session_roster else 0
        pct = int((ready / total) * 100) if total else 0
        c1, c2, c3 = st.columns(3)
        with c1: metric_card("Students", total, "Roster records")
        with c2: metric_card("PODs Ready", ready, "Marked green")
        with c3: metric_card("Build Progress", f"{pct}%", "Ready / total")
        st.markdown(f'<div class="progress-shell"><div class="progress-fill" style="width:{pct}%"></div></div>', unsafe_allow_html=True)
        st.markdown("### POD Build Board")
        for _, r in session_roster.iterrows():
            pod_ready = int(r.get("pod_setup") or 0) == 1
            account = int(r.get("pod_account") or 0) == 1
            snapshot = int(r.get("pod_snapshot") or 0) == 1
            docs = int(r.get("pod_docs") or 0) == 1
            status_class = "pod-ready" if pod_ready else ("pod-partial" if account or snapshot or docs else "pod-not-ready")
            status_label = "🟢 Ready" if pod_ready else ("🟡 Building" if account or snapshot or docs else "🔴 Not Started")
            with st.container():
                st.markdown(f'<div class="lab-card"><b>{r["attendee"]}</b> · <span class="muted">{r.get("attendee_email", "")}</span><br><span class="tiny-label">{r.get("pod_name") or "No POD Assigned"}</span></div>', unsafe_allow_html=True)
                a,b,c,d,e,f = st.columns([1.2,1,1,1,1,1.3])
                with a: st.markdown(f'<div class="{status_class}">{status_label}</div>', unsafe_allow_html=True)
                with b: st.markdown(f'<div class="lab-dot">{"🟢" if account else "🔴"}</div><div class="tiny-label">Account</div>', unsafe_allow_html=True)
                with c: st.markdown(f'<div class="lab-dot">{"🟢" if snapshot else "🔴"}</div><div class="tiny-label">Snapshot</div>', unsafe_allow_html=True)
                with d: st.markdown(f'<div class="lab-dot">{"🟢" if docs else "🔴"}</div><div class="tiny-label">Docs</div>', unsafe_allow_html=True)
                with e: st.markdown(f'<div class="lab-dot">{"🟢" if pod_ready else "🔴"}</div><div class="tiny-label">Ready</div>', unsafe_allow_html=True)
                with f:
                    if st.button("Update", key=f"lab_update_{int(r['id'])}"):
                        st.session_state["lab_edit_id"] = int(r["id"])
        st.divider()
        edit_id = st.session_state.get("lab_edit_id")
        if edit_id:
            row = completion_df[completion_df["id"] == edit_id].iloc[0]
            st.markdown(f"### Update Lab Build: {row['attendee']}")
            with st.form("lab_builder_update_form"):
                c1, c2, c3, c4 = st.columns(4)
                pod_name = c1.text_input("POD Name", value=str(row.get("pod_name") or ""))
                pod_account = c2.checkbox("Account Created", value=bool(row.get("pod_account") or 0))
                pod_snapshot = c3.checkbox("Snapshot Created", value=bool(row.get("pod_snapshot") or 0))
                pod_docs = c4.checkbox("Docs/Credentials Sent", value=bool(row.get("pod_docs") or 0))
                pod_setup = st.checkbox("Overall POD Ready", value=bool(row.get("pod_setup") or 0))
                build_status = st.selectbox("Build Status", ["Not Started", "Building", "Ready", "Blocked"], index=["Not Started", "Building", "Ready", "Blocked"].index(str(row.get("lab_build_status") or "Not Started")) if str(row.get("lab_build_status") or "Not Started") in ["Not Started", "Building", "Ready", "Blocked"] else 0)
                pod_notes = st.text_area("Lab Notes", value=str(row.get("pod_notes") or ""))
                if st.form_submit_button("Save Lab Build Status"):
                    timestamp = datetime.now().isoformat(timespec="seconds") if pod_setup else row.get("pod_setup_at")
                    execute("""
                        UPDATE enrollments
                        SET pod_name=?, pod_account=?, pod_snapshot=?, pod_docs=?, pod_setup=?, pod_setup_at=?, lab_build_status=?, pod_notes=?
                        WHERE id=?
                    """, [pod_name, int(pod_account), int(pod_snapshot), int(pod_docs), int(pod_setup), timestamp, build_status, pod_notes, edit_id])
                    st.success("Lab build status updated.")
                    st.session_state.pop("lab_edit_id", None)
                    st.rerun()
        st.download_button("Download Lab Builder Queue", data=export_excel({"Lab Builder Queue": session_roster}), file_name=f"lab_builder_queue_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif menu == "Instructors":
    hero("Instructor Management", "Maintain instructor profiles, delivery focus areas, availability status, and notes.")
    with st.expander("➕ Add Instructor", expanded=True):
        with st.form("add_instructor"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name")
            email = c2.text_input("Email")
            c3, c4 = st.columns(2)
            specialty = c3.text_input("Specialty / Focus Area", placeholder="VCF, NSX, Aria, vSphere, Security")
            status = c4.selectbox("Status", ["Active", "Inactive", "Contract", "Unavailable"])
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Instructor")
            if submitted:
                if not name.strip(): st.error("Instructor name is required.")
                else:
                    execute("INSERT INTO instructors (name, email, specialty, status, notes) VALUES (?, ?, ?, ?, ?)", [name, email, specialty, status, notes])
                    st.success("Instructor added."); st.rerun()
    st.dataframe(instructors_df, use_container_width=True, hide_index=True)

elif menu == "Attendees":
    hero("Attendee Roster", "Track customer students, organizations, roles, and enrollment readiness.")
    with st.expander("➕ Add Attendee", expanded=True):
        with st.form("add_attendee"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Name")
            email = c2.text_input("Email")
            c3, c4 = st.columns(2)
            organization = c3.text_input("Organization / Customer")
            role = c4.text_input("Role")
            status = st.selectbox("Status", ["Active", "Inactive"])
            notes = st.text_area("Notes")
            submitted = st.form_submit_button("Add Attendee")
            if submitted:
                if not name.strip(): st.error("Attendee name is required.")
                else:
                    execute("INSERT INTO attendees (name, email, organization, role, status, notes) VALUES (?, ?, ?, ?, ?, ?)", [name, email, organization, role, status, notes])
                    st.success("Attendee added."); st.rerun()
    st.dataframe(attendees_df, use_container_width=True, hide_index=True)

elif menu == "Courses":
    hero("Course Catalog", "Build reusable classes, labs, workshops, and certification-aligned training paths.")
    with st.expander("➕ Add Course", expanded=True):
        with st.form("add_course"):
            c1, c2 = st.columns([1, 2])
            course_code = c1.text_input("Course Code", placeholder="VCF9-DEPLOY-101")
            title = c2.text_input("Course Title")
            c3, c4, c5 = st.columns(3)
            category = c3.text_input("Category", placeholder="VCF, NSX, Aria")
            level = c4.selectbox("Level", ["Intro", "Intermediate", "Advanced", "Expert", "Workshop"])
            duration_hours = c5.number_input("Duration Hours", min_value=0.0, value=8.0, step=0.5)
            description = st.text_area("Description")
            active = st.checkbox("Active", value=True)
            submitted = st.form_submit_button("Add Course")
            if submitted:
                if not title.strip(): st.error("Course title is required.")
                else:
                    execute("INSERT INTO courses (course_code, title, category, level, duration_hours, description, active) VALUES (?, ?, ?, ?, ?, ?, ?)", [course_code, title, category, level, duration_hours, description, int(active)])
                    st.success("Course added."); st.rerun()
    st.dataframe(courses_df, use_container_width=True, hide_index=True)

elif menu == "Class Sessions":
    hero("Class Sessions", "Schedule instructor-led cohorts, assign instructors, set capacity, and track delivery status.")
    if courses_df.empty:
        st.warning("Add at least one course before creating a class session.")
    else:
        course_options = options_from_df(courses_df, "title")
        instructor_options = {"Unassigned": None}; instructor_options.update(options_from_df(instructors_df, "name"))
        with st.expander("➕ Create Class Session", expanded=True):
            with st.form("add_session"):
                c1, c2 = st.columns(2)
                course_label = c1.selectbox("Course", list(course_options.keys()))
                instructor_label = c2.selectbox("Instructor", list(instructor_options.keys()))
                session_name = st.text_input("Session Name", placeholder="VCF 9 Deployment Lab - June Cohort")
                c3, c4, c5 = st.columns(3)
                start_date = c3.date_input("Start Date", value=date.today())
                end_date = c4.date_input("End Date", value=date.today())
                capacity = c5.number_input("Capacity", min_value=1, value=20, step=1)
                c6, c7 = st.columns(2)
                delivery_type = c6.selectbox("Delivery Type", ["In-Person", "Virtual", "Hybrid", "Self-Paced"])
                status = c7.selectbox("Status", ["Scheduled", "In Progress", "Completed", "Canceled"])
                location = st.text_input("Location / Link")
                notes = st.text_area("Notes")
                submitted = st.form_submit_button("Create Session")
                if submitted:
                    if not session_name.strip(): st.error("Session name is required.")
                    elif end_date < start_date: st.error("End date cannot be before start date.")
                    else:
                        execute("""
                            INSERT INTO class_sessions
                            (course_id, instructor_id, session_name, start_date, end_date, delivery_type, location, capacity, status, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [course_options[course_label], instructor_options[instructor_label], session_name, start_date.isoformat(), end_date.isoformat(), delivery_type, location, capacity, status, notes])
                        st.success("Class session created."); st.rerun()
        st.dataframe(sessions_df, use_container_width=True, hide_index=True)

elif menu == "Enrollments & Completions":
    hero("Enrollments & Completions", "Enroll attendees, then return at the end of class to update existing student completion records.")
    if sessions_df.empty or attendees_df.empty:
        st.warning("Create at least one class session and one attendee before enrolling attendees.")
    else:
        session_options = {f"{row['session_name']} - {row['course_title']} ({row['start_date']}) [ID {row['id']} ]": int(row["id"]) for _, row in sessions_df.iterrows()}
        attendee_options = options_from_df(attendees_df, "name")
        tab1, tab2, tab3 = st.tabs(["Enroll Attendee", "Update by Class Roster", "Update Single Enrollment"])

        with tab1:
            st.info("Use this when initially signing students up for a class. Existing enrollments can be edited in the roster tabs after the course.")
            with st.form("add_enrollment"):
                session_label = st.selectbox("Class Session", list(session_options.keys()))
                attendee_label = st.selectbox("Attendee", list(attendee_options.keys()))
                c1, c2, c3 = st.columns(3)
                enrollment_status = c1.selectbox("Enrollment Status", ["Pending Approval", "Enrolled", "Waitlisted", "Dropped", "No Show"])
                completion_status = c2.selectbox("Completion Status", ["Not Started", "In Progress", "Completed", "Failed", "Incomplete"])
                certificate_issued = c3.checkbox("Certificate Issued")
                c4, c5 = st.columns(2)
                completion_date = c4.date_input("Completion Date", value=None)
                score = c5.number_input("Score", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
                p1, p2 = st.columns([1, 2])
                pod_setup = p1.checkbox("Lab POD Set Up")
                pod_name = p2.text_input("POD Name / ID")
                pod_notes = st.text_area("POD Notes")
                notes = st.text_area("Enrollment Notes")
                submitted = st.form_submit_button("Save Enrollment")
                if submitted:
                    try:
                        execute("""
                            INSERT INTO enrollments
                            (session_id, attendee_id, enrollment_status, completion_status, completion_date, score, certificate_issued, pod_setup, pod_name, pod_setup_at, pod_notes, notes)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [session_options[session_label], attendee_options[attendee_label], enrollment_status, completion_status, completion_date.isoformat() if completion_date else None, score, int(certificate_issued), int(pod_setup), pod_name, datetime.now().isoformat(timespec="seconds") if pod_setup else None, pod_notes, notes])
                        st.success("Enrollment saved."); st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("That attendee is already enrolled in this session. Use the update tabs to edit the existing record.")

        with tab2:
            st.markdown("### End-of-Course Completion Roster")
            st.caption("Pick the class, then update each student from the roster. This is the main workflow for marking completions after training.")
            selected_session_label = st.selectbox("Select Class Session", list(session_options.keys()), key="completion_roster_session")
            selected_session_id = session_options[selected_session_label]
            roster = run_query(
                """
                SELECT e.id, a.name AS attendee, a.email, a.organization, a.role,
                       e.enrollment_status, e.completion_status, e.completion_date,
                       e.score, e.certificate_issued, e.pod_setup, e.pod_name, e.notes
                FROM enrollments e
                JOIN attendees a ON e.attendee_id = a.id
                WHERE e.session_id=?
                ORDER BY a.name
                """,
                [selected_session_id],
            )
            if roster.empty:
                st.info("No students are enrolled in this selected class yet.")
            else:
                total = len(roster)
                completed = int((roster["completion_status"] == "Completed").sum())
                certs = int((roster["certificate_issued"] == 1).sum())
                ready_pods = int((roster["pod_setup"] == 1).sum())
                m1, m2, m3, m4 = st.columns(4)
                with m1: metric_card("Students", total, "Signed up for this class")
                with m2: metric_card("Completed", completed, "Marked complete")
                with m3: metric_card("Certificates", certs, "Issued/recorded")
                with m4: metric_card("PODs Ready", ready_pods, "Lab readiness")

                with st.expander("✅ Bulk mark enrolled students complete", expanded=False):
                    st.warning("This updates every student in this selected class with Enrollment Status = Enrolled.")
                    b1, b2, b3 = st.columns(3)
                    bulk_date = b1.date_input("Bulk Completion Date", value=date.today(), key="bulk_completion_date")
                    bulk_score = b2.number_input("Bulk Score", min_value=0.0, max_value=100.0, value=100.0, step=1.0, key="bulk_score")
                    bulk_cert = b3.checkbox("Issue Certificates", value=True, key="bulk_cert")
                    bulk_notes = st.text_area("Bulk Completion Notes", value="Completed course requirements.", key="bulk_notes")
                    if st.button("Mark All Enrolled Complete", key="bulk_complete_button"):
                        execute(
                            """
                            UPDATE enrollments
                            SET completion_status='Completed', completion_date=?, score=?, certificate_issued=?, notes=?
                            WHERE session_id=? AND enrollment_status='Enrolled'
                            """,
                            [bulk_date.isoformat(), bulk_score, int(bulk_cert), bulk_notes, selected_session_id],
                        )
                        st.success("Selected class roster updated.")
                        st.rerun()

                st.markdown("### Student Completion Cards")
                for _, row in roster.iterrows():
                    complete_icon = "✅" if row["completion_status"] == "Completed" else "🟠" if row["completion_status"] == "In Progress" else "⚪"
                    cert_icon = "🎓" if row["certificate_issued"] == 1 else ""
                    pod_icon = "🟢" if row["pod_setup"] == 1 else "🔴"
                    with st.expander(f"{complete_icon} {row['attendee']} — {row['completion_status']} {cert_icon} {pod_icon}", expanded=False):
                        d1, d2, d3, d4 = st.columns(4)
                        d1.write(f"**Email:** {row['email'] or ''}")
                        d2.write(f"**Organization:** {row['organization'] or ''}")
                        d3.write(f"**Enrollment:** {row['enrollment_status']}")
                        d4.write(f"**POD:** {'Ready' if row['pod_setup'] == 1 else 'Not Ready'}")
                        with st.form(f"completion_update_{row['id']}"):
                            c1, c2, c3, c4 = st.columns(4)
                            enrollment_status_val = c1.selectbox(
                                "Enrollment Status",
                                ["Pending Approval", "Enrolled", "Waitlisted", "Dropped", "No Show"],
                                index=["Pending Approval", "Enrolled", "Waitlisted", "Dropped", "No Show"].index(row["enrollment_status"]) if row["enrollment_status"] in ["Pending Approval", "Enrolled", "Waitlisted", "Dropped", "No Show"] else 0,
                                key=f"enrollment_status_{row['id']}",
                            )
                            completion_choices = ["Not Started", "In Progress", "Completed", "Failed", "Incomplete"]
                            completion_status_val = c2.selectbox(
                                "Completion Status",
                                completion_choices,
                                index=completion_choices.index(row["completion_status"]) if row["completion_status"] in completion_choices else 0,
                                key=f"completion_status_{row['id']}",
                            )
                            existing_date = date.fromisoformat(row["completion_date"]) if row["completion_date"] else date.today()
                            completion_date_val = c3.date_input("Completion Date", value=existing_date, key=f"completion_date_{row['id']}")
                            score_val = c4.number_input("Score", min_value=0.0, max_value=100.0, value=float(row["score"] or 0.0), step=1.0, key=f"score_{row['id']}")
                            certificate_val = st.checkbox("Certificate Issued", value=bool(row["certificate_issued"]), key=f"cert_{row['id']}")
                            notes_val = st.text_area("Completion / Enrollment Notes", value=row["notes"] or "", key=f"notes_{row['id']}")
                            submitted = st.form_submit_button("Save Student Update")
                            if submitted:
                                execute(
                                    """
                                    UPDATE enrollments
                                    SET enrollment_status=?, completion_status=?, completion_date=?, score=?, certificate_issued=?, notes=?
                                    WHERE id=?
                                    """,
                                    [enrollment_status_val, completion_status_val, completion_date_val.isoformat(), score_val, int(certificate_val), notes_val, int(row["id"])],
                                )
                                st.success(f"Updated {row['attendee']}.")
                                st.rerun()
                st.download_button("Download Completion Roster", data=export_excel({"Completion Roster": roster}), file_name=f"completion_roster_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        with tab3:
            st.markdown("### Update Single Enrollment")
            if completion_df.empty:
                st.info("No enrollments yet.")
            else:
                filter_col1, filter_col2 = st.columns(2)
                course_filter = filter_col1.selectbox("Filter by Course", ["All"] + sorted(completion_df["course"].dropna().unique().tolist()))
                status_filter = filter_col2.selectbox("Filter by Completion Status", ["All"] + sorted(completion_df["completion_status"].dropna().unique().tolist()))
                single_df = completion_df.copy()
                if course_filter != "All": single_df = single_df[single_df["course"] == course_filter]
                if status_filter != "All": single_df = single_df[single_df["completion_status"] == status_filter]
                if single_df.empty:
                    st.info("No enrollment records match the selected filters.")
                else:
                    enrollment_options = {f"{row['attendee']} - {row['course']} - {row['session_name']} (ID {row['id']})": int(row["id"]) for _, row in single_df.iterrows()}
                    selected = st.selectbox("Enrollment", list(enrollment_options.keys()))
                    selected_id = enrollment_options[selected]
                    current = single_df[single_df["id"] == selected_id].iloc[0]
                    with st.form("update_single_completion"):
                        c1, c2, c3 = st.columns(3)
                        completion_choices = ["Not Started", "In Progress", "Completed", "Failed", "Incomplete"]
                        completion_status = c1.selectbox("Completion Status", completion_choices, index=completion_choices.index(current["completion_status"]) if current["completion_status"] in completion_choices else 0)
                        current_date = date.fromisoformat(current["completion_date"]) if current["completion_date"] else date.today()
                        completion_date = c2.date_input("Completion Date", value=current_date)
                        score = c3.number_input("Score", min_value=0.0, max_value=100.0, value=float(current["score"] or 0.0), step=1.0)
                        certificate_issued = st.checkbox("Certificate Issued", value=bool(current["certificate_issued"]))
                        notes = st.text_area("Completion Notes", value=current["notes"] or "")
                        submitted = st.form_submit_button("Update Completion")
                        if submitted:
                            execute(
                                """
                                UPDATE enrollments SET completion_status=?, completion_date=?, score=?, certificate_issued=?, notes=? WHERE id=?
                                """,
                                [completion_status, completion_date.isoformat(), score, int(certificate_issued), notes, selected_id],
                            )
                            st.success("Completion updated.")
                            st.rerun()
        st.markdown("### All Enrollment / Completion Records")
        st.dataframe(completion_df, use_container_width=True, hide_index=True)

elif menu == "Course Rosters & PODs":
    hero("Course Rosters & Lab POD Readiness", "Select a specific class session to view enrolled students and mark each student's lab POD as ready.")
    if completion_df.empty:
        st.info("No enrollments yet. Add class sessions and enroll attendees first.")
    else:
        session_options = {f"{row['session_name']} - {row['course_title']} ({row['start_date']})": int(row["id"]) for _, row in sessions_df.iterrows()}
        selected_label = st.selectbox("Class / Course Session", list(session_options.keys()))
        selected_session_id = session_options[selected_label]
        roster = run_query(
            """
            SELECT e.id, a.name AS attendee, a.email, a.organization, a.role,
                   e.enrollment_status, e.completion_status, e.pod_setup, e.pod_name, e.pod_setup_at, e.pod_notes, e.notes
            FROM enrollments e
            JOIN attendees a ON e.attendee_id = a.id
            WHERE e.session_id=?
            ORDER BY a.name
            """,
            [selected_session_id],
        )
        total = len(roster)
        ready = int((roster["pod_setup"] == 1).sum()) if total else 0
        pct = round((ready / total) * 100, 1) if total else 0
        c1, c2, c3 = st.columns(3)
        with c1: metric_card("Signed Up", total, "Students enrolled in this session")
        with c2: metric_card("PODs Ready", ready, "Marked as lab-ready")
        with c3: metric_card("POD Readiness", f"{pct}%", "Setup completion for this roster")

        if total == 0:
            st.warning("No students are enrolled in this session yet.")
        else:
            if ready == total:
                st.markdown('<div class="pod-ready">🟢 All student lab PODs are ready</div>', unsafe_allow_html=True)
            elif ready == 0:
                st.markdown('<div class="pod-not-ready">🔴 No student lab PODs have been marked ready</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="pod-partial">🟠 {ready} of {total} student lab PODs are ready</div>', unsafe_allow_html=True)

            st.progress(ready / total)
            st.markdown("### Student POD Board")
            for _, row in roster.iterrows():
                icon = "🟢" if row["pod_setup"] == 1 else "🔴"
                status_text = "POD READY" if row["pod_setup"] == 1 else "POD NOT READY"
                box_class = "pod-ready" if row["pod_setup"] == 1 else "pod-not-ready"
                with st.expander(f"{icon} {row['attendee']} — {status_text}", expanded=False):
                    st.markdown(f'<div class="{box_class}">{icon} {status_text}</div>', unsafe_allow_html=True)
                    a, b, c = st.columns(3)
                    a.write(f"**Email:** {row['email'] or ''}")
                    b.write(f"**Organization:** {row['organization'] or ''}")
                    c.write(f"**Role:** {row['role'] or ''}")
                    with st.form(f"pod_update_{row['id']}"):
                        f1, f2 = st.columns([1, 2])
                        pod_setup = f1.checkbox("Lab POD has been set up", value=bool(row["pod_setup"]))
                        pod_name = f2.text_input("POD Name / ID", value=row["pod_name"] or "")
                        pod_notes = st.text_area("POD Notes", value=row["pod_notes"] or "")
                        submitted = st.form_submit_button("Update POD Status")
                        if submitted:
                            setup_at = datetime.now().isoformat(timespec="seconds") if pod_setup else None
                            execute("UPDATE enrollments SET pod_setup=?, pod_name=?, pod_setup_at=?, pod_notes=? WHERE id=?", [int(pod_setup), pod_name, setup_at, pod_notes, int(row["id"])])
                            st.success("POD status updated.")
                            st.rerun()
            export_roster = roster.copy()
            export_roster["pod_ready"] = export_roster["pod_setup"].map({1: "Ready", 0: "Not Ready"})
            st.download_button("Download Selected Roster", data=export_excel({"Roster POD Readiness": export_roster}), file_name=f"pod_roster_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif menu == "User Management":
    hero("Instructor Login Accounts", "Create app accounts for instructors so the site is no longer open access.")
    current_role = st.session_state.get("user", {}).get("role")
    if current_role != "Admin":
        st.warning("Only Admin users can create or manage login accounts.")
    else:
        users_df = run_query("SELECT id, username, full_name, email, role, active, created_at FROM users ORDER BY username")
        with st.expander("➕ Create Instructor/Admin Account", expanded=True):
            with st.form("create_user"):
                c1, c2 = st.columns(2)
                username = c1.text_input("Username")
                full_name = c2.text_input("Full Name")
                c3, c4 = st.columns(2)
                email = c3.text_input("Email")
                role = c4.selectbox("Role", ["Instructor", "Admin"] )
                p1, p2 = st.columns(2)
                password = p1.text_input("Temporary Password", type="password")
                confirm_password = p2.text_input("Confirm Password", type="password")
                submitted = st.form_submit_button("Create Account")
                if submitted:
                    if not username.strip() or not password:
                        st.error("Username and password are required.")
                    elif password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        try:
                            password_hash, salt = hash_password(password)
                            execute("INSERT INTO users (username, full_name, email, role, password_hash, salt, active) VALUES (?, ?, ?, ?, ?, ?, 1)", [username.strip(), full_name, email, role, password_hash, salt])
                            st.success("Account created.")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("That username already exists.")
        st.dataframe(users_df, use_container_width=True, hide_index=True)
        st.markdown("### Activate / Deactivate Account")
        if not users_df.empty:
            user_options = {f"{r['username']} - {r['role']} (ID {r['id']})": int(r["id"]) for _, r in users_df.iterrows()}
            selected_user = st.selectbox("Account", list(user_options.keys()))
            active = st.checkbox("Active", value=True)
            if st.button("Update Account Status"):
                execute("UPDATE users SET active=? WHERE id=?", [int(active), user_options[selected_user]])
                st.success("Account status updated.")
                st.rerun()

elif menu == "Signup Requests":
    hero("Signup Requests", "Review student self-registration requests and approve, waitlist, or decline them.")
    signup_df = run_query(
        """
        SELECT e.id, a.name AS attendee, a.email, a.organization, a.role,
               c.title AS course, s.session_name, s.start_date, s.end_date, s.capacity,
               e.enrollment_status, e.created_at, e.notes,
               COALESCE((SELECT COUNT(*) FROM enrollments ee WHERE ee.session_id=s.id AND ee.enrollment_status='Enrolled'), 0) AS approved_count
        FROM enrollments e
        JOIN attendees a ON e.attendee_id=a.id
        JOIN class_sessions s ON e.session_id=s.id
        JOIN courses c ON s.course_id=c.id
        WHERE e.enrollment_status='Pending Approval'
        ORDER BY s.start_date ASC, e.created_at ASC
        """
    )
    if signup_df.empty:
        st.success("No pending signup requests right now.")
    else:
        m1, m2 = st.columns(2)
        with m1: metric_card("Pending Requests", len(signup_df), "Awaiting instructor/admin review")
        with m2: metric_card("Affected Classes", signup_df["session_name"].nunique(), "Upcoming sessions with requests")
        st.dataframe(signup_df, use_container_width=True, hide_index=True)
        st.markdown("### Review Request")
        request_options = {f"{r['attendee']} → {r['course']} / {r['session_name']} ({r['start_date']}) [ID {r['id']} ]": int(r["id"]) for _, r in signup_df.iterrows()}
        selected_request = st.selectbox("Signup Request", list(request_options.keys()))
        selected_id = request_options[selected_request]
        selected_row = signup_df[signup_df["id"] == selected_id].iloc[0]
        seats_remaining = max(int(selected_row["capacity"] or 0) - int(selected_row["approved_count"] or 0), 0)
        st.info(f"Approved seats: {int(selected_row['approved_count'] or 0)} / {int(selected_row['capacity'] or 0)} · Seats remaining: {seats_remaining}")
        with st.form("review_signup_form"):
            c1, c2 = st.columns(2)
            new_status = c1.selectbox("Decision", ["Enrolled", "Waitlisted", "Dropped"], help="Use Dropped to decline/remove the request from the active roster.")
            reviewer_notes = c2.text_input("Reviewer Notes", placeholder="Approved, waitlisted, declined, etc.")
            submitted = st.form_submit_button("Update Signup Request")
            if submitted:
                note = f"{selected_row['notes'] or ''}\nReview {datetime.now().isoformat(timespec='seconds')}: {reviewer_notes}".strip()
                execute("UPDATE enrollments SET enrollment_status=?, notes=? WHERE id=?", [new_status, note, selected_id])
                st.success("Signup request updated.")
                st.rerun()
        st.download_button("Download Pending Signup Requests", data=export_excel({"Pending Signups": signup_df}), file_name=f"pending_signups_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif menu == "Reports & Export":
    hero("Reports & Export", "Review training outcomes, delivery load, course demand, completions, and export the full dataset.")
    f1, f2, f3 = st.columns(3)
    org_filter = f1.multiselect("Organization", sorted(completion_df["organization"].dropna().unique()) if not completion_df.empty else [])
    course_filter = f2.multiselect("Course", sorted(completion_df["course"].dropna().unique()) if not completion_df.empty else [])
    status_filter = f3.multiselect("Completion Status", sorted(completion_df["completion_status"].dropna().unique()) if not completion_df.empty else [])
    filtered = completion_df.copy()
    if org_filter: filtered = filtered[filtered["organization"].isin(org_filter)]
    if course_filter: filtered = filtered[filtered["course"].isin(course_filter)]
    if status_filter: filtered = filtered[filtered["completion_status"].isin(status_filter)]

    left, right = st.columns(2)
    with left:
        st.subheader("Completions by Course")
        if not filtered.empty:
            course_report = filtered.groupby(["course", "completion_status"]).size().reset_index(name="count")
            fig = px.bar(course_report, x="course", y="count", color="completion_status", barmode="group")
            fig.update_layout(xaxis_title="", yaxis_title="Count", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("No completion data for selected filters.")
    with right:
        st.subheader("Instructor Delivery Count")
        if not sessions_df.empty:
            instructor_report = sessions_df["instructor_name"].fillna("Unassigned").value_counts().reset_index()
            instructor_report.columns = ["Instructor", "Sessions"]
            fig = px.bar(instructor_report, x="Instructor", y="Sessions", text="Sessions")
            fig.update_layout(xaxis_title="", yaxis_title="Sessions", margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
        else: st.info("No session data yet.")

    st.subheader("Completion Report")
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    sheets = {"Instructors": instructors_df, "Attendees": attendees_df, "Courses": courses_df, "Class Sessions": sessions_df, "Completions": completion_df}
    st.download_button("Download Excel Export", data=export_excel(sheets), file_name=f"training_tracker_export_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

elif menu == "Admin":
    hero("Admin", "Seed demo records, review app storage, and reset lab data when needed.")
    st.warning("Reset actions delete local SQLite data from the Docker volume/container path configured for the app.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load Demo Data"):
            if seed_demo_data(): st.success("Demo data loaded.")
            else: st.info("Demo data was not loaded because data already exists.")
            st.rerun()
    with c2:
        confirm = st.checkbox("I understand this deletes all app data")
        if st.button("Reset Database", disabled=not confirm):
            conn = get_conn(); cur = conn.cursor()
            cur.executescript("DROP TABLE IF EXISTS enrollments; DROP TABLE IF EXISTS class_sessions; DROP TABLE IF EXISTS courses; DROP TABLE IF EXISTS attendees; DROP TABLE IF EXISTS instructors; DROP TABLE IF EXISTS users;")
            conn.commit(); conn.close(); init_db(); st.success("Database reset."); st.rerun()
    st.code(f"Database path: {DB_PATH}")
