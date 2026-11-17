import streamlit as st
import sqlite3
import hashlib
import secrets
import datetime
import io
import json
import socket
import subprocess
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
from sklearn.ensemble import IsolationForest
import qrcode

# ==========================================
# 1. PAGE CONFIG & CUSTOM UI STYLING
# ==========================================
st.set_page_config(
    page_title="SmartPrint SaaS | Multi-Tenant Queue & Security",
    page_icon="🖨️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .print-dialog-box {
        background-color: #f8fafc;
        border: 2px solid #cbd5e1;
        border-radius: 10px;
        padding: 14px;
        margin-top: 8px;
    }
    .qr-banner {
        background: linear-gradient(90deg, #0f172a 0%, #1e3a8a 100%);
        color: white;
        padding: 16px 22px;
        border-radius: 12px;
        margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "xerox_saas.db"

# ==========================================
# 2. AUTO-DETECT LOCAL WI-FI IP & WINDOWS PRINTERS
# ==========================================
def get_local_wifi_ip() -> str:
    """Finds the Windows machine's local Wi-Fi IPv4 address so phones can scan the QR code."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

def detect_windows_printers() -> list[dict]:
    """Queries Windows WMIC/PowerShell to list actual physical printers installed on the PC."""
    detected = []
    try:
        cmd = ["powershell", "-Command", "Get-Printer | Select-Object -ExpandProperty Name"]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=3)
        for line in output.splitlines():
            p_name = line.strip()
            if p_name:
                p_type = "Color" if any(k in p_name.lower() for k in ["color", "ink", "c3", "ecotank", "pixma"]) else "B&W / Universal"
                detected.append({"name": f"{p_name} (System Ready)", "type": p_type, "status": "Ready", "ppm": 35})
    except Exception:
        pass
    return detected

# ==========================================
# 3. CRYPTOGRAPHY & DATABASE ENGINE (SQLite)
# ==========================================
def hash_password(password: str, salt: str = None) -> tuple[str, str]:
    if not salt:
        salt = secrets.token_hex(16)
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
    return pw_hash, salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    pw_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(pw_hash, stored_hash)

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS shops (
            shop_id TEXT PRIMARY KEY,
            shop_name TEXT NOT NULL,
            owner_username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            bw_price REAL DEFAULT 2.0,
            color_price REAL DEFAULT 10.0,
            reset_otp TEXT,
            failed_attempts INTEGER DEFAULT 0,
            account_status TEXT DEFAULT 'Active',
            printers_json TEXT
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS print_jobs (
            job_id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id TEXT NOT NULL,
            daily_token TEXT NOT NULL,
            student_name TEXT,
            student_phone TEXT,
            file_count INTEGER,
            pages_count INTEGER,
            color_mode TEXT,
            sides TEXT,
            copies INTEGER,
            n_up INTEGER,
            orientation TEXT,
            paper_size TEXT,
            page_range TEXT,
            collated TEXT,
            margins TEXT DEFAULT 'Normal Margins',
            scaling TEXT DEFAULT 'Fit to Printable Area',
            total_cost REAL,
            status TEXT DEFAULT 'Pending',
            assigned_printer TEXT DEFAULT 'Unassigned',
            processed_pdf BLOB,
            pdf_filename TEXT,
            time_uploaded TEXT,
            time_started TEXT,
            time_completed TEXT
        )
    """)
    
    # Backfill new columns safely if upgrading an existing xerox_saas.db
    existing_cols = [row[1] for row in c.execute("PRAGMA table_info(print_jobs)").fetchall()]
    if "margins" not in existing_cols:
        c.execute("ALTER TABLE print_jobs ADD COLUMN margins TEXT DEFAULT 'Normal Margins'")
    if "scaling" not in existing_cols:
        c.execute("ALTER TABLE print_jobs ADD COLUMN scaling TEXT DEFAULT 'Fit to Printable Area'")

    c.execute("""
        CREATE TABLE IF NOT EXISTS login_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_id TEXT,
            timestamp TEXT,
            hour_of_day INTEGER,
            failed_attempts INTEGER,
            ip_risk_score REAL,
            typing_speed_ms REAL,
            is_anomaly INTEGER,
            action_taken TEXT
        )
    """)
    
    c.execute("SELECT COUNT(*) FROM shops")
    if c.fetchone()[0] == 0:
        default_printers = json.dumps([
            {"name": "Canon imageRUNNER ADVANCE DX C3826i (Tray 1 - Color)", "type": "Color", "status": "Ready", "ppm": 26},
            {"name": "HP LaserJet Enterprise M611dn (Tray 2 - High-Speed B&W)", "type": "B&W", "status": "Ready", "ppm": 65},
            {"name": "Epson EcoTank L15150 (A3/A4 Color Duplex)", "type": "Color", "status": "Ready", "ppm": 25},
            {"name": "Ricoh IM 430F (Fast Monochrome Duplex)", "type": "B&W", "status": "Ready", "ppm": 43}
        ])
        pw1, s1 = hash_password("owner123")
        pw2, s2 = hash_password("library123")
        c.execute("""
            INSERT INTO shops (shop_id, shop_name, owner_username, password_hash, salt, bw_price, color_price, printers_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("CAMPUS_XEROX_01", "Main Block Xerox Center", "admin_main", pw1, s1, 2.0, 10.0, default_printers))
        
        c.execute("""
            INSERT INTO shops (shop_id, shop_name, owner_username, password_hash, salt, bw_price, color_price, printers_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, ("LIBRARY_PRINT_02", "Central Library Reprographics", "admin_lib", pw2, s2, 1.5, 8.0, default_printers))
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 4. ISOLATION FOREST ANOMALY DETECTOR
# ==========================================
@st.cache_resource
def load_anomaly_detector():
    np.random.seed(42)
    normal_data = []
    for _ in range(600):
        hour = int(np.random.normal(13, 3)) % 24
        fails = np.random.choice([0, 1], p=[0.92, 0.08])
        ip_risk = np.random.uniform(0.01, 0.22)
        typing_ms = np.random.normal(220, 25)
        normal_data.append([hour, fails, ip_risk, typing_ms])
        
    for _ in range(35):
        hour = np.random.choice([1, 2, 3, 4, 23])
        fails = np.random.randint(3, 9)
        ip_risk = np.random.uniform(0.75, 0.99)
        typing_ms = np.random.choice([np.random.uniform(30, 80), np.random.uniform(420, 600)])
        normal_data.append([hour, fails, ip_risk, typing_ms])
        
    df_train = pd.DataFrame(normal_data, columns=["hour", "fails", "ip_risk", "typing_ms"])
    model = IsolationForest(contamination=0.06, random_state=42)
    model.fit(df_train)
    return model

anomaly_model = load_anomaly_detector()

# ==========================================
# 5. AUTOMATED N-UP LAYOUT ENGINE (PILLOW)
# ==========================================
def build_nup_pdf(uploaded_files, n_up: int, color_mode: str, orientation: str) -> tuple[bytes, int]:
    """Stitches multiple uploaded images onto A4 pages automatically."""
    a4_w, a4_h = (1240, 1754) if "Portrait" in orientation else (1754, 1240)
    margin = 40
    
    images = []
    for f in uploaded_files:
        if f.name.lower().endswith((".png", ".jpg", ".jpeg")):
            img = Image.open(f).convert("RGB")
            if "Black & White" in color_mode:
                img = ImageOps.grayscale(img).convert("RGB")
            images.append(img)
            
    if not images:
        first_file = uploaded_files[0]
        first_file.seek(0)
        return first_file.read(), len(uploaded_files)

    grid_map = {
        1: (1, 1),
        2: (1, 2) if "Portrait" in orientation else (2, 1),
        4: (2, 2),
        6: (2, 3) if "Portrait" in orientation else (3, 2)
    }
    cols, rows = grid_map.get(n_up, (1, 1))
    cell_w = (a4_w - margin * (cols + 1)) // cols
    cell_h = (a4_h - margin * (rows + 1)) // rows

    pages = []
    for i in range(0, len(images), n_up):
        canvas = Image.new("RGB", (a4_w, a4_h), "white")
        batch = images[i:i + n_up]
        for idx, img in enumerate(batch):
            r = idx // cols
            c = idx % cols
            img_copy = img.copy()
            img_copy.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)
            
            x = margin + c * (cell_w + margin) + (cell_w - img_copy.width) // 2
            y = margin + r * (cell_h + margin) + (cell_h - img_copy.height) // 2
            canvas.paste(img_copy, (x, y))
        pages.append(canvas)

    pdf_buffer = io.BytesIO()
    pages[0].save(pdf_buffer, format="PDF", save_all=True, append_images=pages[1:])
    return pdf_buffer.getvalue(), len(pages)

# ==========================================
# 6. SESSION STATE & QR URL ROUTING
# ==========================================
if "authenticated_shop" not in st.session_state:
    st.session_state.authenticated_shop = None
if "super_admin_auth" not in st.session_state:
    st.session_state.super_admin_auth = False
if "active_student_token" not in st.session_state:
    st.session_state.active_student_token = None

query_params = st.query_params
routed_shop_id = query_params.get("shop_id", None)
routed_portal = query_params.get("portal", None)

# If a student scanned a Shop QR Code (?shop_id=...&portal=student), route straight to Student Portal
st.sidebar.title("🖨️ SmartPrint SaaS")
st.sidebar.caption("Multi-Tenant Queue & ML Security")

if routed_portal == "student" and routed_shop_id:
    st.sidebar.success(f"📲 QR Scan Detected!\nLocked to Shop: `{routed_shop_id}`")
    if st.sidebar.button("🔓 Switch to Staff / Admin View"):
        st.query_params.clear()
        st.rerun()
    app_mode = "📱 Student Print Portal"
else:
    app_mode = st.sidebar.radio(
        "Select Portal:",
        ["📱 Student Print Portal", "🔐 Shop Owner Dashboard", "🛡️ Super Admin (App Host)"]
    )
    st.sidebar.divider()
    st.sidebar.markdown("**Quick Demo Credentials:**")
    st.sidebar.code(
        "Shop 1 User: admin_main\nPassword: owner123\n\n"
        "Shop 2 User: admin_lib\nPassword: library123\n\n"
        "Super Admin: host_master\nPassword: supersecret",
        language="text"
    )

# ==========================================
# PORTAL 1: STUDENT PRINT PORTAL (QR ROUTED)
# ==========================================
if app_mode == "📱 Student Print Portal":
    conn = sqlite3.connect(DB_FILE)
    shops_df = pd.read_sql_query("SELECT shop_id, shop_name, bw_price, color_price FROM shops WHERE account_status='Active'", conn)
    conn.close()

    shop_options = {row["shop_id"]: f"{row['shop_name']} ({row['shop_id']})" for _, row in shops_df.iterrows()}
    
    # Automatically lock to the scanned QR code shop if present in URL
    if routed_shop_id and routed_shop_id in shop_options:
        selected_shop_id = routed_shop_id
        current_shop = shops_df[shops_df["shop_id"] == selected_shop_id].iloc[0]
        st.markdown(f"""
        <div class="qr-banner">
            <h2 style="margin:0; color:white;">📲 {current_shop['shop_name']} — Student Upload Portal</h2>
            <p style="margin:4px 0 0 0; opacity:0.9;">Connected via Unique Shop QR Code ({selected_shop_id}) • Instant Queue Token Assignment</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        col_hdr1, col_hdr2 = st.columns([2, 1])
        with col_hdr1:
            st.title("📱 Student Print & Layout Portal")
            st.markdown("Scan a shop's QR code or choose your campus shop on the right to upload documents.")
        with col_hdr2:
            selected_shop_id = st.selectbox(
                "📍 Select Campus Xerox Shop:",
                options=list(shop_options.keys()),
                format_func=lambda x: shop_options[x]
            )
        current_shop = shops_df[shops_df["shop_id"] == selected_shop_id].iloc[0]

    tab_upload, tab_track = st.tabs(["📤 Upload & Configure Print Job", "⏱️ Live Token Tracker"])

    with tab_upload:
        col_form, col_preview = st.columns([1.4, 1])
        
        with col_form:
            with st.container(border=True):
                st.subheader("1. Student & File Details")
                s_col1, s_col2 = st.columns(2)
                student_name = s_col1.text_input("Your Name", placeholder="e.g., Rahul Sharma")
                student_phone = s_col2.text_input("Phone / WhatsApp Number", placeholder="e.g., 9876543210")
                
                uploaded_files = st.file_uploader(
                    "Upload Images (JPG/PNG for N-up stitching) or PDFs",
                    type=["png", "jpg", "jpeg", "pdf"],
                    accept_multiple_files=True
                )

                st.subheader("2. Document Print Preferences")
                p_col1, p_col2, p_col3 = st.columns(3)
                with p_col1:
                    color_mode = st.selectbox("Color Mode", [f"Black & White (₹{current_shop['bw_price']}/pg)", f"Color (₹{current_shop['color_price']}/pg)"])
                    sides = st.selectbox("Print Sides", ["Print One Sided", "Print on Both Sides (Flip on Long Edge)", "Print on Both Sides (Flip on Short Edge)"])
                    copies = st.number_input("Copies", min_value=1, max_value=100, value=1)
                with p_col2:
                    n_up = st.selectbox("Pages per Sheet (N-up Layout)", [1, 2, 4, 6], index=0)
                    orientation = st.selectbox("Orientation", ["Portrait Orientation", "Landscape Orientation"])
                    paper_size = st.selectbox("Paper Size", ["A4 (210 x 297 mm)", "Letter (8.5 x 11 in)", "A3 (297 x 420 mm)"])
                with p_col3:
                    page_range_type = st.selectbox("Page Range", ["Print All Pages", "Custom Page Range"])
                    custom_range = st.text_input("Pages to Print", value="All" if page_range_type == "Print All Pages" else "1-5", disabled=(page_range_type == "Print All Pages"))
                    collated = st.selectbox("Collation", ["Collated (1,2,3 - 1,2,3)", "Uncollated (1,1,1 - 2,2,2)"])

        with col_preview:
            with st.container(border=True):
                st.subheader("⚡ Automated Layout & Cost Estimator")
                if uploaded_files:
                    raw_count = len(uploaded_files)
                    est_sheets = int(np.ceil(raw_count / n_up))
                    rate = current_shop["bw_price"] if "Black & White" in color_mode else current_shop["color_price"]
                    total_cost = est_sheets * copies * rate
                    
                    st.metric("Total Output Pages (Post N-up)", f"{est_sheets} Page(s)", f"From {raw_count} uploaded file(s)")
                    st.metric("Estimated Total Price", f"₹{total_cost:.2f}", f"{copies} Copy/Copies @ ₹{rate}/pg")
                    
                    if st.button("🚀 Generate Print-Ready PDF & Get Token", type="primary", use_container_width=True):
                        if not student_name:
                            st.warning("Please enter your name so the shop operator can call your token.")
                        else:
                            with st.spinner("Running Automated N-up Layout Engine..."):
                                pdf_bytes, final_pages = build_nup_pdf(uploaded_files, n_up, color_mode, orientation)
                                
                                conn = sqlite3.connect(DB_FILE)
                                c = conn.cursor()
                                c.execute("SELECT COUNT(*) FROM print_jobs WHERE shop_id=?", (selected_shop_id,))
                                next_num = c.fetchone()[0] + 1
                                token_str = f"#{next_num:03d}"
                                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                
                                c.execute("""
                                    INSERT INTO print_jobs (
                                        shop_id, daily_token, student_name, student_phone, file_count, pages_count,
                                        color_mode, sides, copies, n_up, orientation, paper_size, page_range, collated,
                                        margins, scaling, total_cost, status, processed_pdf, pdf_filename, time_uploaded
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Normal Margins', 'Fit to Printable Area', ?, 'Pending', ?, ?, ?)
                                """, (
                                    selected_shop_id, token_str, student_name, student_phone, len(uploaded_files),
                                    final_pages, color_mode.split(" (")[0], sides, copies, n_up, orientation,
                                    paper_size, custom_range, collated, total_cost, pdf_bytes,
                                    f"{selected_shop_id}_{token_str.replace('#','T')}.pdf", now_str
                                ))
                                conn.commit()
                                conn.close()
                                
                                st.session_state.active_student_token = (selected_shop_id, token_str)
                                st.success(f"✅ Sent to **{current_shop['shop_name']}**! Your Token Number is **{token_str}**")
                                st.download_button(
                                    "📥 Preview Stitched A4 PDF",
                                    data=pdf_bytes,
                                    file_name=f"Preview_{token_str}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                else:
                    st.info("Upload your images or PDFs on the left to preview the N-up sheet calculation and instant pricing.")

    with tab_track:
        st.subheader("🔍 Real-Time Token Status Tracker")
        t_col1, t_col2 = st.columns([1, 2])
        with t_col1:
            default_tok = st.session_state.active_student_token[1] if st.session_state.active_student_token else "#001"
            search_token = st.text_input("Enter Your Daily Token (e.g., #001)", value=default_tok)
            if st.button("🔄 Refresh Live Status"):
                st.rerun()
        with t_col2:
            conn = sqlite3.connect(DB_FILE)
            job_df = pd.read_sql_query(
                "SELECT * FROM print_jobs WHERE shop_id=? AND daily_token=? ORDER BY job_id DESC LIMIT 1",
                conn, params=(selected_shop_id, search_token)
            )
            conn.close()
            
            if not job_df.empty:
                j = job_df.iloc[0]
                status_map = {"Pending": 25, "Printing": 65, "Ready for Pickup": 100, "Completed": 100}
                prog = status_map.get(j["status"], 10)
                st.markdown(f"### Token `{j['daily_token']}` — Status: **{j['status']}**")
                st.progress(prog)
                st.write(f"**Student:** {j['student_name']} | **Assigned Hardware Printer:** `{j['assigned_printer']}` | **Total Bill:** ₹{j['total_cost']:.2f}")
                st.caption(f"Uploaded: {j['time_uploaded']} | Dispatched to Printer: {j['time_started'] or 'Waiting in Queue'} | Ready: {j['time_completed'] or 'In Progress'}")
            else:
                st.warning(f"No active job found for Token `{search_token}` at {current_shop['shop_name']}.")

# ==========================================
# PORTAL 2: SHOP OWNER DASHBOARD (PROTECTED)
# ==========================================
elif app_mode == "🔐 Shop Owner Dashboard":
    if not st.session_state.authenticated_shop:
        st.title("🔐 Shop Owner Authentication Gateway")
        st.markdown("Protected by **Zero-Knowledge PBKDF2-SHA256 Hashing** and **Isolation Forest ML Anomaly Detection**.")
        
        auth_tab1, auth_tab2 = st.tabs(["🔑 Operator Login", "🔄 Forgot / Reset Password"])
        
        with auth_tab1:
            col_login, col_ml = st.columns([1.2, 1])
            with col_ml:
                with st.container(border=True):
                    st.subheader("🛡️ ML Security Telemetry Simulator")
                    st.caption("Adjust parameters to test how the Isolation Forest blocks suspicious logins in real time.")
                    sim_hour = st.slider("Simulated Login Hour (24h)", 0, 23, datetime.datetime.now().hour)
                    sim_ip_risk = st.slider("Network IP Risk Score (0.0 = Clean, 1.0 = Tor/VPN)", 0.0, 1.0, 0.08)
                    sim_typing = st.slider("Keystroke Flight Time (ms/key)", 40, 550, 215)
            
            with col_login:
                with st.container(border=True):
                    st.subheader("Sign In to Shop Terminal")
                    username_in = st.text_input("Shop Owner Username", value="admin_main")
                    password_in = st.text_input("Password", type="password", value="owner123")
                    otp_challenge_in = st.text_input("2FA Security OTP (Only if challenged by ML)", placeholder="Leave blank unless prompted")
                    
                    if st.button("Authenticate & Open Terminal", type="primary", use_container_width=True):
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute("SELECT shop_id, shop_name, password_hash, salt, failed_attempts, account_status FROM shops WHERE owner_username=?", (username_in,))
                        row = c.fetchone()
                        
                        if not row:
                            st.error("Invalid username or password.")
                        else:
                            shop_id, shop_name, pw_hash, salt, fails, acc_status = row
                            if acc_status != "Active":
                                st.error("This shop account has been suspended by the Super Admin.")
                            else:
                                features = pd.DataFrame([[sim_hour, fails, sim_ip_risk, sim_typing]], columns=["hour", "fails", "ip_risk", "typing_ms"])
                                pred = anomaly_model.predict(features)[0]
                                is_anomaly = 1 if pred == -1 else 0
                                
                                if verify_password(password_in, pw_hash, salt):
                                    if is_anomaly == 1 and otp_challenge_in != "998877":
                                        c.execute("""
                                            INSERT INTO login_logs (shop_id, timestamp, hour_of_day, failed_attempts, ip_risk_score, typing_speed_ms, is_anomaly, action_taken)
                                            VALUES (?, ?, ?, ?, ?, ?, 1, 'Challenged - Blocked pending 2FA')
                                        """, (shop_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sim_hour, fails, sim_ip_risk, sim_typing))
                                        conn.commit()
                                        st.error("🚨 **ANOMALOUS LOGIN DETECTED BY ISOLATION FOREST!** Enter emergency 2FA code `998877` above to verify identity.")
                                    else:
                                        c.execute("UPDATE shops SET failed_attempts=0 WHERE shop_id=?", (shop_id,))
                                        c.execute("""
                                            INSERT INTO login_logs (shop_id, timestamp, hour_of_day, failed_attempts, ip_risk_score, typing_speed_ms, is_anomaly, action_taken)
                                            VALUES (?, ?, ?, ?, ?, ?, ?, 'Approved')
                                        """, (shop_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sim_hour, fails, sim_ip_risk, sim_typing, is_anomaly))
                                        conn.commit()
                                        st.session_state.authenticated_shop = shop_id
                                        st.rerun()
                                else:
                                    new_fails = fails + 1
                                    c.execute("UPDATE shops SET failed_attempts=? WHERE shop_id=?", (new_fails, shop_id))
                                    c.execute("""
                                        INSERT INTO login_logs (shop_id, timestamp, hour_of_day, failed_attempts, ip_risk_score, typing_speed_ms, is_anomaly, action_taken)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, 'Invalid Password')
                                    """, (shop_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sim_hour, new_fails, sim_ip_risk, sim_typing, is_anomaly))
                                    conn.commit()
                                    st.error(f"Incorrect password. Failed attempts recorded: {new_fails}")
                        conn.close()

        with auth_tab2:
            with st.container(border=True):
                st.subheader("Self-Service OTP Password Reset")
                reset_user = st.text_input("Enter your registered Owner Username", key="rst_u")
                if st.button("Generate Temporary Reset OTP"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    otp_code = str(secrets.randbelow(900000) + 100000)
                    c.execute("UPDATE shops SET reset_otp=? WHERE owner_username=?", (otp_code, reset_user))
                    if c.rowcount > 0:
                        conn.commit()
                        st.info(f"📱 Simulated SMS Dispatch: Your 6-digit password reset OTP is **`{otp_code}`**")
                    else:
                        st.error("Username not found.")
                    conn.close()
                
                entered_otp = st.text_input("Enter 6-Digit OTP")
                new_pass = st.text_input("New Password", type="password")
                if st.button("Verify OTP & Update Password", type="primary"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("SELECT reset_otp FROM shops WHERE owner_username=?", (reset_user,))
                    r = c.fetchone()
                    if r and r[0] and r[0] == entered_otp and len(new_pass) >= 6:
                        nhash, nsalt = hash_password(new_pass)
                        c.execute("UPDATE shops SET password_hash=?, salt=?, reset_otp=NULL, failed_attempts=0 WHERE owner_username=?", (nhash, nsalt, reset_user))
                        conn.commit()
                        st.success("Password updated! You can now log in using your new password.")
                    else:
                        st.error("Invalid OTP or password shorter than 6 characters.")
                    conn.close()

    else:
        # ==========================================
        # AUTHENTICATED OWNER WORKSPACE
        # ==========================================
        shop_id = st.session_state.authenticated_shop
        conn = sqlite3.connect(DB_FILE)
        shop_row = pd.read_sql_query("SELECT * FROM shops WHERE shop_id=?", conn, params=(shop_id,)).iloc[0]
        jobs_df = pd.read_sql_query("SELECT * FROM print_jobs WHERE shop_id=? ORDER BY job_id DESC", conn, params=(shop_id,))
        printers_list = json.loads(shop_row["printers_json"])
        conn.close()

        top_c1, top_c2 = st.columns([3, 1])
        with top_c1:
            st.title(f"🖨️ {shop_row['shop_name']} — Operator Console")
            st.caption(f"Tenant ID: `{shop_id}` | Hardware Printer Selection & Live Queue")
        with top_c2:
            if st.button("🔒 Log Out of Terminal", use_container_width=True):
                st.session_state.authenticated_shop = None
                st.rerun()

        m1, m2, m3, m4 = st.columns(4)
        pending_cnt = len(jobs_df[jobs_df["status"] == "Pending"])
        printing_cnt = len(jobs_df[jobs_df["status"] == "Printing"])
        ready_cnt = len(jobs_df[jobs_df["status"].isin(["Ready for Pickup", "Completed"])])
        revenue_sum = jobs_df["total_cost"].sum() if not jobs_df.empty else 0.0
        
        m1.metric("🟡 Pending Queue", f"{pending_cnt} Jobs")
        m2.metric("🟣 Printing Now", f"{printing_cnt} Jobs")
        m3.metric("🟢 Ready / Completed", f"{ready_cnt} Jobs")
        m4.metric("💰 Total Shop Revenue", f"₹{revenue_sum:.2f}")

        owner_tabs = st.tabs([
            "📋 Live Queue & Hardware Print Dialog",
            "📲 Shop QR Code Generator (Direct Student Link)",
            "🖨️ Manage Connected Printers & Pricing",
            "🔑 Security & Password Settings"
        ])

        # TAB 1: KANBAN & FULL WINDOWS-STYLE PRINT DIALOG
        with owner_tabs[0]:
            k_pending, k_printing, k_ready = st.columns([1.35, 1, 1])
            printer_labels = [f"🖨️ {p['name']} [{p['type']} • {p['status']}]" for p in printers_list]

            with k_pending:
                st.subheader(f"🟡 Pending Queue ({pending_cnt})")
                for _, job in jobs_df[jobs_df["status"] == "Pending"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"### Token `{job['daily_token']}` — {job['student_name']}")
                        st.caption(f"Uploaded: {job['time_uploaded']} | Phone: {job['student_phone'] or 'N/A'}")
                        st.info(
                            f"**{job['color_mode']}** | **{job['copies']} Copies** | "
                            f"**{job['n_up']} Pages/Sheet** | **Total: ₹{job['total_cost']:.2f}**"
                        )
                        
                        if job["processed_pdf"]:
                            st.download_button(
                                f"📥 Download Stitched PDF ({job['pages_count']} A4 pgs)",
                                data=job["processed_pdf"],
                                file_name=job["pdf_filename"],
                                mime="application/pdf",
                                key=f"dl_{job['job_id']}",
                                use_container_width=True
                            )
                        
                        # FULL HARDWARE PRINTER & PRINT SETTINGS DIALOG
                        with st.expander("🖨️ Proceed to Print — Select Printer & Print Settings", expanded=True):
                            st.markdown("**1. Destination Hardware Printer**")
                            rec_idx = 0 if "Color" in str(job["color_mode"]) else (1 if len(printer_labels) > 1 else 0)
                            selected_printer_label = st.selectbox(
                                "Available Printers (Ready)",
                                options=printer_labels,
                                index=rec_idx,
                                key=f"prt_{job['job_id']}",
                                help="Choose which physical printer in your shop will print this token."
                            )
                            
                            st.markdown("**2. Print Settings & Page Setup**")
                            pr_c1, pr_c2 = st.columns(2)
                            with pr_c1:
                                dlg_copies = st.number_input("Copies", min_value=1, max_value=200, value=int(job["copies"]), key=f"cp_{job['job_id']}")
                                dlg_range = st.selectbox(
                                    "Page Range",
                                    ["Print All Pages", "Custom Page Range", "Print Current Page"],
                                    index=0 if job["page_range"] == "All" else 1,
                                    key=f"rg_{job['job_id']}"
                                )
                                dlg_custom_pgs = st.text_input("Pages", value=str(job["page_range"]), key=f"cpg_{job['job_id']}")
                                dlg_sides = st.selectbox(
                                    "One-Sided / Two-Sided",
                                    ["Print One Sided", "Print on Both Sides (Flip on Long Edge)", "Print on Both Sides (Flip on Short Edge)"],
                                    index=0 if "One" in str(job["sides"]) else 1,
                                    key=f"sd_{job['job_id']}"
                                )
                                dlg_collated = st.selectbox(
                                    "Collation",
                                    ["Collated (1,2,3 - 1,2,3)", "Uncollated (1,1,1 - 2,2,2)"],
                                    index=0 if "Collated" in str(job["collated"]) else 1,
                                    key=f"col_{job['job_id']}"
                                )
                            with pr_c2:
                                dlg_orient = st.selectbox(
                                    "Orientation",
                                    ["Portrait Orientation", "Landscape Orientation"],
                                    index=0 if "Portrait" in str(job["orientation"]) else 1,
                                    key=f"or_{job['job_id']}"
                                )
                                dlg_size = st.selectbox(
                                    "Paper Size",
                                    ["A4 (210 x 297 mm)", "Letter (8.5 x 11 in)", "A3 (297 x 420 mm)", "Legal (8.5 x 14 in)"],
                                    index=0,
                                    key=f"sz_{job['job_id']}"
                                )
                                dlg_margins = st.selectbox(
                                    "Page Margins",
                                    ["Normal Margins (1\" x 1\")", "Narrow Margins (0.5\" x 0.5\")", "Minimal Margins"],
                                    index=0,
                                    key=f"mg_{job['job_id']}"
                                )
                                dlg_nup = st.selectbox(
                                    "Pages Per Sheet",
                                    ["1 Page Per Sheet", "2 Pages Per Sheet", "4 Pages Per Sheet", "6 Pages Per Sheet"],
                                    index=[1, 2, 4, 6].index(int(job["n_up"])) if int(job["n_up"]) in [1, 2, 4, 6] else 0,
                                    key=f"nup_{job['job_id']}"
                                )
                                dlg_scaling = st.selectbox(
                                    "Page Scaling",
                                    ["Fit to Printable Area", "Actual Size (100%)", "Shrink Oversized Pages"],
                                    index=0,
                                    key=f"sc_{job['job_id']}"
                                )

                            if st.button("🖨️ Send Job to Selected Printer", key=f"start_{job['job_id']}", type="primary", use_container_width=True):
                                clean_printer = selected_printer_label.replace("🖨️ ", "").split(" [")[0]
                                conn = sqlite3.connect(DB_FILE)
                                c = conn.cursor()
                                now_s = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                c.execute("""
                                    UPDATE print_jobs
                                    SET status='Printing', assigned_printer=?, copies=?, sides=?, orientation=?,
                                        paper_size=?, page_range=?, collated=?, margins=?, scaling=?, time_started=?
                                    WHERE job_id=?
                                """, (
                                    clean_printer, dlg_copies, dlg_sides, dlg_orient, dlg_size,
                                    dlg_custom_pgs, dlg_collated, dlg_margins, dlg_scaling, now_s, job["job_id"]
                                ))
                                conn.commit()
                                conn.close()
                                st.rerun()

            with k_printing:
                st.subheader(f"🟣 Printing Now ({printing_cnt})")
                for _, job in jobs_df[jobs_df["status"] == "Printing"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"### Token `{job['daily_token']}` — {job['student_name']}")
                        st.success(f"🖨️ **Printer:** `{job['assigned_printer']}`")
                        st.write(f"**Copies:** {job['copies']} | **Sides:** {job['sides']}")
                        st.write(f"**Paper:** {job['paper_size']} ({job['orientation']}) | **Scaling:** {job['scaling']}")
                        st.caption(f"Sent to printer at: {job['time_started']}")
                        
                        if st.button("✅ Mark Print Completed & Ready", key=f"rdy_{job['job_id']}", type="primary", use_container_width=True):
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            now_c = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            c.execute("UPDATE print_jobs SET status='Ready for Pickup', time_completed=? WHERE job_id=?", (now_c, job["job_id"]))
                            conn.commit()
                            conn.close()
                            st.rerun()

            with k_ready:
                st.subheader(f"🟢 Ready for Pickup ({ready_cnt})")
                for _, job in jobs_df[jobs_df["status"].isin(["Ready for Pickup", "Completed"])].iterrows():
                    with st.container(border=True):
                        st.markdown(f"### Token `{job['daily_token']}` — {job['student_name']}")
                        st.write(f"Printed on: `{job['assigned_printer']}`")
                        st.success(f"Collect **₹{job['total_cost']:.2f}** at Counter")
                        st.caption(f"Completed at: {job['time_completed']}")

        # TAB 2: DIRECT STUDENT PORTAL QR GENERATOR
        with owner_tabs[1]:
            st.subheader("📲 Shop QR Code Poster (Opens Student Upload Portal Directly)")
            local_ip = get_local_wifi_ip()
            
            qr_col1, qr_col2 = st.columns([1.3, 1])
            with qr_col1:
                st.markdown("""
                **How this QR Code works:**
                1. It automatically uses your Windows Wi-Fi IP address (`http://<your-ip>:8501`) instead of `localhost` so any phone connected to the same Wi-Fi/Hotspot can scan it.
                2. It embeds `?shop_id=...&portal=student` so scanning the code **directly opens the Student Document Upload Portal** for your shop.
                """)
                host_base = st.text_input(
                    "Base Server URL (Auto-detected Windows Wi-Fi IP — or paste your Render/Ngrok URL):",
                    value=f"http://{local_ip}:8501"
                )
                direct_student_url = f"{host_base.rstrip('/')}/?shop_id={shop_id}&portal=student"
                st.code(direct_student_url, language="text")
                st.info("💡 **Tip for phone scanning:** Make sure you started Streamlit with `streamlit run app.py --server.address 0.0.0.0` so Windows allows mobile devices on your Wi-Fi to connect.")

            with qr_col2:
                qr = qrcode.QRCode(version=1, box_size=10, border=3)
                qr.add_data(direct_student_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="black", back_color="white")
                buf = io.BytesIO()
                qr_img.save(buf, format="PNG")
                
                st.image(buf.getvalue(), width=260, caption=f"Scan to upload directly to {shop_row['shop_name']}")
                st.download_button(
                    "📥 Download Printable Shop QR Poster (PNG)",
                    data=buf.getvalue(),
                    file_name=f"{shop_id}_Student_Portal_QR.png",
                    mime="image/png",
                    use_container_width=True
                )

        # TAB 3: HARDWARE PRINTERS & PRICING
        with owner_tabs[2]:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                st.subheader("🖨️ Available Shop Printers")
                st.dataframe(pd.DataFrame(printers_list), use_container_width=True)
                
                if st.button("🔍 Auto-Detect Installed Windows Printers on This PC", use_container_width=True):
                    win_printers = detect_windows_printers()
                    if win_printers:
                        existing_names = {p["name"] for p in printers_list}
                        for wp in win_printers:
                            if wp["name"] not in existing_names:
                                printers_list.append(wp)
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("UPDATE shops SET printers_json=? WHERE shop_id=?", (json.dumps(printers_list), shop_id))
                        conn.commit()
                        conn.close()
                        st.success(f"Synced {len(win_printers)} Windows system printer(s)!")
                        st.rerun()
                    else:
                        st.warning("No additional Windows printers detected.")

                with st.form("add_printer_form"):
                    st.markdown("**Manually Add a Printer to Shop List**")
                    new_p_name = st.text_input("Printer Name / Tray", placeholder="e.g., Konica Minolta Bizhub C226i")
                    new_p_type = st.selectbox("Printer Type", ["B&W", "Color", "B&W / Universal"])
                    new_p_ppm = st.number_input("Speed (Pages Per Minute)", min_value=10, max_value=120, value=45)
                    if st.form_submit_button("Add Printer"):
                        if new_p_name:
                            printers_list.append({"name": new_p_name, "type": new_p_type, "status": "Ready", "ppm": new_p_ppm})
                            conn = sqlite3.connect(DB_FILE)
                            conn.execute("UPDATE shops SET printers_json=? WHERE shop_id=?", (json.dumps(printers_list), shop_id))
                            conn.commit()
                            conn.close()
                            st.success("Printer added to your Print Dialog!")
                            st.rerun()

            with p_col2:
                st.subheader("💲 Dynamic Shop Tariff Configuration")
                new_bw = st.number_input("Black & White Rate (₹ per page)", value=float(shop_row["bw_price"]), step=0.5)
                new_col = st.number_input("Color Rate (₹ per page)", value=float(shop_row["color_price"]), step=1.0)
                if st.button("Save Pricing Update", type="primary"):
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("UPDATE shops SET bw_price=?, color_price=? WHERE shop_id=?", (new_bw, new_col, shop_id))
                    conn.commit()
                    conn.close()
                    st.success("Shop rates updated immediately.")

                st.divider()
                st.subheader("🔄 Daily Token Counter Reset")
                if st.button("🗑️ Clear Queue & Reset Daily Token Counter to #001"):
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("DELETE FROM print_jobs WHERE shop_id=?", (shop_id,))
                    conn.commit()
                    conn.close()
                    st.success("Queue cleared and token counter reset to #001!")
                    st.rerun()

        # TAB 4: CHANGE PASSWORD
        with owner_tabs[3]:
            st.subheader("🔑 Change Operator Password")
            old_p = st.text_input("Current Password", type="password")
            new_p1 = st.text_input("New Password", type="password")
            new_p2 = st.text_input("Confirm New Password", type="password")
            if st.button("Update Password", type="primary"):
                if new_p1 != new_p2 or len(new_p1) < 6:
                    st.error("New passwords must match and be at least 6 characters.")
                elif not verify_password(old_p, shop_row["password_hash"], shop_row["salt"]):
                    st.error("Current password is incorrect.")
                else:
                    nh, ns = hash_password(new_p1)
                    conn = sqlite3.connect(DB_FILE)
                    conn.execute("UPDATE shops SET password_hash=?, salt=? WHERE shop_id=?", (nh, ns, shop_id))
                    conn.commit()
                    conn.close()
                    st.success("Password changed securely!")

# ==========================================
# PORTAL 3: SUPER ADMIN (APP HOST)
# ==========================================
elif app_mode == "🛡️ Super Admin (App Host)":
    st.title("🛡️ Super Admin Multi-Tenant Control Center")
    if not st.session_state.super_admin_auth:
        u = st.text_input("App Host Username", value="host_master")
        p = st.text_input("App Host Master Password", type="password", value="supersecret")
        if st.button("Unlock Super Admin Console", type="primary"):
            if u == "host_master" and p == "supersecret":
                st.session_state.super_admin_auth = True
                st.rerun()
            else:
                st.error("Unauthorized access.")
    else:
        if st.button("Log Out Super Admin"):
            st.session_state.super_admin_auth = False
            st.rerun()

        conn = sqlite3.connect(DB_FILE)
        all_shops = pd.read_sql_query("SELECT shop_id, shop_name, owner_username, password_hash, bw_price, color_price, failed_attempts, account_status FROM shops", conn)
        all_logs = pd.read_sql_query("SELECT * FROM login_logs ORDER BY log_id DESC LIMIT 100", conn)
        all_jobs = pd.read_sql_query("SELECT shop_id, daily_token, assigned_printer, pages_count, n_up, total_cost, status, time_uploaded, time_started, time_completed FROM print_jobs", conn)
        conn.close()

        sa_tab1, sa_tab2, sa_tab3 = st.tabs(["🏪 Registered Tenants & Zero-Knowledge Hashes", "🚨 Isolation Forest Security Logs", "📊 Scopus Research Telemetry Export"])

        with sa_tab1:
            st.subheader("Registered Xerox Shops (Multi-Tenant Registry)")
            st.dataframe(all_shops, use_container_width=True)

            with st.expander("➕ Provision New Campus Xerox Shop Tenant"):
                ns_id = st.text_input("Unique Shop ID", placeholder="e.g., HOSTEL_XEROX_03")
                ns_name = st.text_input("Shop Display Name", placeholder="e.g., Mens Hostel Block-C Print Shop")
                ns_user = st.text_input("Assigned Owner Username", placeholder="e.g., admin_hostel")
                ns_pass = st.text_input("Initial Owner Password", type="password")
                if st.button("Create New Shop Tenant", type="primary"):
                    if ns_id and ns_name and ns_user and len(ns_pass) >= 6:
                        h, s = hash_password(ns_pass)
                        default_p = json.dumps([
                            {"name": "HP LaserJet Pro M404dn (B&W)", "type": "B&W", "status": "Ready", "ppm": 40},
                            {"name": "Epson L3250 Wi-Fi Color", "type": "Color", "status": "Ready", "ppm": 15}
                        ])
                        conn = sqlite3.connect(DB_FILE)
                        try:
                            conn.execute(
                                "INSERT INTO shops (shop_id, shop_name, owner_username, password_hash, salt, printers_json) VALUES (?, ?, ?, ?, ?, ?)",
                                (ns_id.strip().upper(), ns_name, ns_user, h, s, default_p)
                            )
                            conn.commit()
                            st.success(f"Tenant `{ns_id}` created!")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("Shop ID or Username already exists.")
                        finally:
                            conn.close()

        with sa_tab2:
            st.subheader("Isolation Forest Authentication Telemetry")
            st.dataframe(all_logs, use_container_width=True)

        with sa_tab3:
            st.subheader("📊 Export Empirical Data for Scopus Paper")
            st.dataframe(all_jobs, use_container_width=True)
            csv_jobs = all_jobs.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Print Queue Telemetry (CSV)", data=csv_jobs, file_name="scopus_print_telemetry.csv", mime="text/csv")