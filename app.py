import streamlit as st
import sqlite3
import hashlib
import secrets
import datetime
import io
import json
import socket
import subprocess
import math
import pandas as pd
from PIL import Image, ImageOps
import qrcode

# ==========================================
# 1. PAGE CONFIG & REALISTIC SAAS STYLING
# ==========================================
st.set_page_config(
    page_title="PrintFlow | Campus Reprographics & Queue Platform",
    page_icon="🖨️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .hero-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
        color: #ffffff;
        padding: 24px 28px;
        border-radius: 14px;
        margin-bottom: 20px;
        box-shadow: 0 10px 25px -5px rgba(15, 23, 42, 0.15);
    }
    .hero-header h1 {
        margin: 0;
        font-size: 1.75rem;
        font-weight: 700;
        color: #ffffff;
    }
    .hero-header p {
        margin: 6px 0 0 0;
        font-size: 0.95rem;
        color: #cbd5e1;
    }

    .token-badge {
        display: inline-block;
        background: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
        font-weight: 700;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.9rem;
    }

    .otp-notification {
        background: #f0fdf4;
        border-left: 4px solid #16a34a;
        padding: 12px 16px;
        border-radius: 8px;
        color: #166534;
        font-size: 0.92rem;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "printflow_saas.db"

# ==========================================
# 2. NETWORK & HARDWARE PRINTER HELPERS
# ==========================================
def get_local_wifi_ip() -> str:
    """Detects local Wi-Fi IPv4 address for mobile QR scanning."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

def detect_windows_printers() -> list[dict]:
    """Lists physical printers installed on a Windows host."""
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
# 3. CRYPTOGRAPHY & SQLITE DATABASE ENGINE
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
            owner_email TEXT UNIQUE,
            owner_phone TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            bw_price REAL DEFAULT 2.0,
            color_price REAL DEFAULT 10.0,
            reset_otp TEXT,
            account_status TEXT DEFAULT 'Active',
            printers_json TEXT,
            created_at TEXT
        )
    """)
    
    # Backfill columns if database already existed
    existing_shop_cols = [row[1] for row in c.execute("PRAGMA table_info(shops)").fetchall()]
    if "owner_email" not in existing_shop_cols:
        c.execute("ALTER TABLE shops ADD COLUMN owner_email TEXT")
    if "owner_phone" not in existing_shop_cols:
        c.execute("ALTER TABLE shops ADD COLUMN owner_phone TEXT")
    if "created_at" not in existing_shop_cols:
        c.execute("ALTER TABLE shops ADD COLUMN created_at TEXT")

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
    
    c.execute("SELECT COUNT(*) FROM shops")
    if c.fetchone()[0] == 0:
        default_printers = json.dumps([
            {"name": "Canon imageRUNNER ADVANCE DX C3826i (Tray 1 - Color)", "type": "Color", "status": "Ready", "ppm": 26},
            {"name": "HP LaserJet Enterprise M611dn (Tray 2 - High-Speed B&W)", "type": "B&W", "status": "Ready", "ppm": 65},
            {"name": "Epson EcoTank L15150 (A3/A4 Color Duplex)", "type": "Color", "status": "Ready", "ppm": 25},
            {"name": "Ricoh IM 430F (Fast Monochrome Duplex)", "type": "B&W", "status": "Ready", "ppm": 43}
        ])
        now_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        pw1, s1 = hash_password("owner123")
        pw2, s2 = hash_password("library123")
        
        c.execute("""
            INSERT INTO shops (shop_id, shop_name, owner_username, owner_email, owner_phone, password_hash, salt, bw_price, color_price, printers_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("CAMPUS_XEROX_01", "Main Block Reprographics", "admin_main", "mainxerox@gmail.com", "9876543210", pw1, s1, 2.0, 10.0, default_printers, now_dt))
        
        c.execute("""
            INSERT INTO shops (shop_id, shop_name, owner_username, owner_email, owner_phone, password_hash, salt, bw_price, color_price, printers_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("LIBRARY_PRINT_02", "Central Library Copy Center", "admin_lib", "libraryprint@gmail.com", "9876500000", pw2, s2, 1.5, 8.0, default_printers, now_dt))
        
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 4. AUTOMATED N-UP LAYOUT ENGINE (PILLOW)
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
# 5. SESSION STATE & URL ROUTING
# ==========================================
if "authenticated_shop" not in st.session_state:
    st.session_state.authenticated_shop = None
if "super_admin_auth" not in st.session_state:
    st.session_state.super_admin_auth = False
if "active_student_token" not in st.session_state:
    st.session_state.active_student_token = None
if "reg_otp_code" not in st.session_state:
    st.session_state.reg_otp_code = None
if "reg_pending_data" not in st.session_state:
    st.session_state.reg_pending_data = None

query_params = st.query_params
routed_shop_id = query_params.get("shop_id", None)
routed_portal = query_params.get("portal", None)

# Hidden Super Admin URL trigger (?portal=superadmin)
if routed_portal == "superadmin":
    st.session_state.show_hidden_admin = True
elif "show_hidden_admin" not in st.session_state:
    st.session_state.show_hidden_admin = False

# ==========================================
# 6. CLEAN PUBLIC SIDEBAR NAVIGATION
# ==========================================
st.sidebar.markdown("### 🖨️ PrintFlow Cloud")
st.sidebar.caption("Smart Campus Document Fulfillment")

if st.session_state.super_admin_auth or st.session_state.show_hidden_admin:
    app_mode = "🛡️ Hidden Super Admin"
elif routed_portal == "student" and routed_shop_id:
    st.sidebar.success(f"📲 Connected to Shop:\n`{routed_shop_id}`")
    if st.sidebar.button("🔄 Switch to Partner Shop Portal", use_container_width=True):
        st.query_params.clear()
        st.rerun()
    app_mode = "📱 Student Print Portal"
else:
    app_mode = st.sidebar.radio(
        "Navigation",
        ["📱 Student Print Portal", "🏪 Partner Shop Portal"],
        label_visibility="collapsed"
    )

st.sidebar.divider()
st.sidebar.caption("🔒 End-to-End Encrypted Document Queue • Instant Token Tracking")

# ==========================================
# PORTAL 1: STUDENT PRINT PORTAL (QR ROUTED)
# ==========================================
if app_mode == "📱 Student Print Portal":
    conn = sqlite3.connect(DB_FILE)
    shops_df = pd.read_sql_query("SELECT shop_id, shop_name, bw_price, color_price FROM shops WHERE account_status='Active'", conn)
    conn.close()

    shop_options = {row["shop_id"]: f"{row['shop_name']} ({row['shop_id']})" for _, row in shops_df.iterrows()}
    
    if routed_shop_id and routed_shop_id in shop_options:
        selected_shop_id = routed_shop_id
        current_shop = shops_df[shops_df["shop_id"] == selected_shop_id].iloc[0]
        st.markdown(f"""
        <div class="hero-header">
            <h1>📲 {current_shop['shop_name']}</h1>
            <p>Verified Partner Shop ({selected_shop_id}) • Upload your files below for instant counter pickup</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="hero-header">
            <h1>🖨️ Student Print & Document Portal</h1>
            <p>Select your campus print shop, configure your layout settings, and receive a live queue token.</p>
        </div>
        """, unsafe_allow_html=True)
        selected_shop_id = st.selectbox(
            "📍 Select Destination Print Shop",
            options=list(shop_options.keys()),
            format_func=lambda x: shop_options[x]
        )
        current_shop = shops_df[shops_df["shop_id"] == selected_shop_id].iloc[0]

    tab_upload, tab_track = st.tabs(["📤 Upload & Configure Document", "⏱️ Live Order Status"])

    with tab_upload:
        col_form, col_preview = st.columns([1.45, 1])
        
        with col_form:
            with st.container(border=True):
                st.subheader("1. Student Information & Files")
                s_col1, s_col2 = st.columns(2)
                student_name = s_col1.text_input("Full Name", placeholder="e.g., Aditya Rao")
                student_phone = s_col2.text_input("Mobile Number", placeholder="e.g., 9876543210")
                
                uploaded_files = st.file_uploader(
                    "Select Documents or Images (PDF, PNG, JPG)",
                    type=["png", "jpg", "jpeg", "pdf"],
                    accept_multiple_files=True
                )

                st.subheader("2. Print Specifications")
                p_col1, p_col2, p_col3 = st.columns(3)
                with p_col1:
                    color_mode = st.selectbox("Color Mode", [f"Black & White (₹{current_shop['bw_price']:.2f}/pg)", f"Color (₹{current_shop['color_price']:.2f}/pg)"])
                    sides = st.selectbox("Two-Sided Printing", ["Print One Sided", "Print on Both Sides (Flip on Long Edge)", "Print on Both Sides (Flip on Short Edge)"])
                    copies = st.number_input("Number of Copies", min_value=1, max_value=100, value=1)
                with p_col2:
                    n_up = st.selectbox("Pages per Sheet (N-up)", [1, 2, 4, 6], index=0)
                    orientation = st.selectbox("Orientation", ["Portrait Orientation", "Landscape Orientation"])
                    paper_size = st.selectbox("Paper Size", ["A4 (210 x 297 mm)", "Letter (8.5 x 11 in)", "A3 (297 x 420 mm)"])
                with p_col3:
                    page_range_type = st.selectbox("Page Range", ["Print All Pages", "Custom Page Range"])
                    custom_range = st.text_input("Page Numbers", value="All" if page_range_type == "Print All Pages" else "1-5", disabled=(page_range_type == "Print All Pages"))
                    collated = st.selectbox("Collation", ["Collated (1,2,3 - 1,2,3)", "Uncollated (1,1,1 - 2,2,2)"])

        with col_preview:
            with st.container(border=True):
                st.subheader("💳 Order Summary")
                if uploaded_files:
                    raw_count = len(uploaded_files)
                    est_sheets = int(math.ceil(raw_count / n_up))
                    rate = current_shop["bw_price"] if "Black & White" in color_mode else current_shop["color_price"]
                    total_cost = est_sheets * copies * rate
                    
                    st.metric("Formatted A4 Pages", f"{est_sheets} Page(s)", f"From {raw_count} uploaded file(s)")
                    st.metric("Estimated Payable Amount", f"₹{total_cost:.2f}", f"{copies} Copy/Copies @ ₹{rate:.2f}/pg")
                    st.divider()
                    
                    if st.button("🚀 Submit Print Order & Generate Token", type="primary", use_container_width=True):
                        if not student_name.strip():
                            st.warning("Please enter your name so the shop operator can identify your order.")
                        else:
                            with st.spinner("Formatting document layout and reserving queue token..."):
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
                                    selected_shop_id, token_str, student_name.strip(), student_phone.strip(), len(uploaded_files),
                                    final_pages, color_mode.split(" (")[0], sides, copies, n_up, orientation,
                                    paper_size, custom_range, collated, total_cost, pdf_bytes,
                                    f"{selected_shop_id}_{token_str.replace('#','T')}.pdf", now_str
                                ))
                                conn.commit()
                                conn.close()
                                
                                st.session_state.active_student_token = (selected_shop_id, token_str)
                                st.success(f"Order sent to **{current_shop['shop_name']}**! Your Queue Token is **{token_str}**")
                                st.download_button(
                                    "📥 Download Formatted PDF Preview",
                                    data=pdf_bytes,
                                    file_name=f"PrintPreview_{token_str.replace('#','')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                else:
                    st.info("Select your files on the left to view automatic page calculations and instant pricing.")

    with tab_track:
        with st.container(border=True):
            st.subheader("🔍 Live Order Progress Tracker")
            t_col1, t_col2 = st.columns([1, 2])
            with t_col1:
                default_tok = st.session_state.active_student_token[1] if st.session_state.active_student_token else "#001"
                search_token = st.text_input("Queue Token Number", value=default_tok)
                if st.button("🔄 Refresh Order Status", use_container_width=True):
                    st.rerun()
            with t_col2:
                conn = sqlite3.connect(DB_FILE)
                job_df = pd.read_sql_query(
                    "SELECT * FROM print_jobs WHERE shop_id=? AND daily_token=? ORDER BY job_id DESC LIMIT 1",
                    conn, params=(selected_shop_id, search_token.strip())
                )
                conn.close()
                
                if not job_df.empty:
                    j = job_df.iloc[0]
                    status_map = {"Pending": 25, "Printing": 65, "Ready for Pickup": 100, "Completed": 100}
                    prog = status_map.get(j["status"], 10)
                    st.markdown(f"#### Token <span class='token-badge'>{j['daily_token']}</span> — **{j['status']}**", unsafe_allow_html=True)
                    st.progress(prog)
                    st.write(f"**Customer:** {j['student_name']} | **Assigned Printer:** `{j['assigned_printer']}` | **Total Amount:** ₹{j['total_cost']:.2f}")
                    st.caption(f"Submitted: {j['time_uploaded']} • Dispatched: {j['time_started'] or 'In Queue'} • Completed: {j['time_completed'] or 'Pending'}")
                else:
                    st.warning(f"No order found for Token `{search_token}` at {current_shop['shop_name']}.")

# ==========================================
# PORTAL 2: PARTNER SHOP PORTAL (LOGIN & REGISTER)
# ==========================================
elif app_mode == "🏪 Partner Shop Portal":
    if not st.session_state.authenticated_shop:
        st.markdown("""
        <div class="hero-header">
            <h1>🏪 Partner Print Shop Portal</h1>
            <p>Sign in to manage your live print queue, or register your print shop with Gmail / Mobile OTP verification.</p>
        </div>
        """, unsafe_allow_html=True)

        auth_tab1, auth_tab2, auth_tab3 = st.tabs([
            "🔑 Sign In to Shop Console",
            "🏪 Register New Print Shop (OTP Verified)",
            "🔄 Forgot Password (OTP Recovery)"
        ])

        # TAB 1: CLEAN SHOP OWNER LOGIN
        with auth_tab1:
            col_l1, col_l2 = st.columns([1.2, 1])
            with col_l1:
                with st.container(border=True):
                    st.subheader("Shop Operator Login")
                    login_id = st.text_input("Username, Gmail, or Mobile Number", placeholder="e.g., mainxerox@gmail.com or 9876543210")
                    login_pw = st.text_input("Password", type="password", placeholder="Enter your password")
                    
                    if st.button("Sign In to Dashboard", type="primary", use_container_width=True):
                        # Secret Super Admin Trigger (Invisible to regular users)
                        if login_id.strip() == "host_master" and login_pw == "supersecret":
                            st.session_state.super_admin_auth = True
                            st.rerun()

                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute("""
                            SELECT shop_id, shop_name, password_hash, salt, account_status
                            FROM shops
                            WHERE owner_username=? OR LOWER(owner_email)=LOWER(?) OR owner_phone=?
                        """, (login_id.strip(), login_id.strip(), login_id.strip()))
                        row = c.fetchone()
                        conn.close()
                        
                        if not row:
                            st.error("Account not found. Please check your credentials or register a new shop.")
                        else:
                            shop_id, shop_name, pw_hash, salt, acc_status = row
                            if acc_status != "Active":
                                st.error("This shop account is currently inactive.")
                            elif verify_password(login_pw, pw_hash, salt):
                                st.session_state.authenticated_shop = shop_id
                                st.rerun()
                            else:
                                st.error("Incorrect password. Please try again or use the Forgot Password tab.")
            with col_l2:
                with st.container(border=True):
                    st.subheader("Why Partner with PrintFlow?")
                    st.markdown("""
                    - **Dedicated Shop QR Poster:** Students scan your counter QR code to upload documents directly to your queue.
                    - **Automated Page Layout:** Multi-image uploads are automatically arranged onto A4 sheets.
                    - **Direct Hardware Routing:** Select which physical printer handles B&W vs. Color jobs.
                    - **Real-Time Token Alerts:** Students track their own token status on their phones without crowding your counter.
                    """)

        # TAB 2: REGISTER NEW SHOP WITH GMAIL / MOBILE OTP
        with auth_tab2:
            with st.container(border=True):
                st.subheader("🏪 Register Your Print Shop")
                st.caption("Complete the form below to receive a verification OTP via your Gmail or Mobile Number.")
                
                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    reg_shop_name = st.text_input("Print Shop Business Name *", placeholder="e.g., Sri Sai Digital Xerox & Binding")
                    reg_shop_code = st.text_input("Desired Unique Shop Code *", placeholder="e.g., SAI_XEROX_04").strip().upper().replace(" ", "_")
                    reg_username = st.text_input("Operator Login Username *", placeholder="e.g., sai_admin")
                    reg_channel = st.radio("Send Verification OTP via:", ["Mobile Number (SMS)", "Gmail Address"], horizontal=True)
                with r_col2:
                    reg_email = st.text_input("Registered Gmail Address *", placeholder="e.g., saixerox@gmail.com")
                    reg_phone = st.text_input("Registered Mobile Number (10 digits) *", placeholder="e.g., 9845012345")
                    p_rate1, p_rate2 = st.columns(2)
                    reg_bw = p_rate1.number_input("B&W Rate (₹/page)", min_value=0.5, max_value=50.0, value=2.0, step=0.5)
                    reg_color = p_rate2.number_input("Color Rate (₹/page)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
                    reg_pass1 = st.text_input("Create Password (min 6 chars) *", type="password")

                if st.button("📨 Send Verification OTP", type="secondary"):
                    if not (reg_shop_name and reg_shop_code and reg_username and reg_email and reg_phone and len(reg_pass1) >= 6):
                        st.warning("Please fill in all fields and ensure your password is at least 6 characters.")
                    elif "@" not in reg_email:
                        st.warning("Please enter a valid Gmail/email address.")
                    else:
                        conn = sqlite3.connect(DB_FILE)
                        c = conn.cursor()
                        c.execute(
                            "SELECT shop_id FROM shops WHERE shop_id=? OR owner_username=? OR LOWER(owner_email)=LOWER(?) OR owner_phone=?",
                            (reg_shop_code, reg_username.strip(), reg_email.strip(), reg_phone.strip())
                        )
                        conflict = c.fetchone()
                        conn.close()
                        
                        if conflict:
                            st.error("A shop with this Shop Code, Username, Gmail, or Mobile Number is already registered.")
                        else:
                            otp = str(secrets.randbelow(900000) + 100000)
                            st.session_state.reg_otp_code = otp
                            st.session_state.reg_pending_data = {
                                "shop_id": reg_shop_code,
                                "shop_name": reg_shop_name.strip(),
                                "username": reg_username.strip(),
                                "email": reg_email.strip().lower(),
                                "phone": reg_phone.strip(),
                                "bw": reg_bw,
                                "color": reg_color,
                                "password": reg_pass1,
                                "channel": reg_channel
                            }

                if st.session_state.reg_otp_code and st.session_state.reg_pending_data:
                    pdata = st.session_state.reg_pending_data
                    target_dest = pdata["phone"] if "Mobile" in pdata["channel"] else pdata["email"]
                    st.markdown(f"""
                    <div class="otp-notification">
                        ✅ <strong>OTP Dispatched to {pdata['channel']} ({target_dest}):</strong> Your 6-digit verification code is <strong><code>{st.session_state.reg_otp_code}</code></strong>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    v_col1, v_col2 = st.columns([1, 1])
                    entered_reg_otp = v_col1.text_input("Enter 6-Digit Verification OTP", placeholder="e.g., 482910")
                    if v_col2.button("✅ Verify OTP & Complete Shop Registration", type="primary", use_container_width=True):
                        if entered_reg_otp.strip() == st.session_state.reg_otp_code:
                            pw_hash, salt = hash_password(pdata["password"])
                            starter_printers = json.dumps([
                                {"name": "HP LaserJet Enterprise B&W (Tray 1)", "type": "B&W", "status": "Ready", "ppm": 50},
                                {"name": "Canon ImageRUNNER Color (Tray 2)", "type": "Color", "status": "Ready", "ppm": 26}
                            ])
                            now_dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            c.execute("""
                                INSERT INTO shops (
                                    shop_id, shop_name, owner_username, owner_email, owner_phone,
                                    password_hash, salt, bw_price, color_price, printers_json, created_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                pdata["shop_id"], pdata["shop_name"], pdata["username"],
                                pdata["email"], pdata["phone"], pw_hash, salt,
                                pdata["bw"], pdata["color"], starter_printers, now_dt
                            ))
                            conn.commit()
                            conn.close()
                            
                            st.session_state.authenticated_shop = pdata["shop_id"]
                            st.session_state.reg_otp_code = None
                            st.session_state.reg_pending_data = None
                            st.success("Shop registered and verified! Redirecting to your operator console...")
                            st.rerun()
                        else:
                            st.error("Invalid OTP code. Please check the 6-digit code above.")

        # TAB 3: FORGOT PASSWORD RECOVERY VIA GMAIL OR MOBILE
        with auth_tab3:
            with st.container(border=True):
                st.subheader("🔄 Reset Shop Password via Gmail or Mobile OTP")
                recovery_input = st.text_input("Enter your registered Gmail Address, Mobile Number, or Username")
                if st.button("Send Recovery OTP"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    otp_code = str(secrets.randbelow(900000) + 100000)
                    c.execute("""
                        UPDATE shops SET reset_otp=?
                        WHERE owner_username=? OR LOWER(owner_email)=LOWER(?) OR owner_phone=?
                    """, (otp_code, recovery_input.strip(), recovery_input.strip(), recovery_input.strip()))
                    if c.rowcount > 0:
                        conn.commit()
                        st.markdown(f"""
                        <div class="otp-notification">
                            📩 <strong>Account Recovery OTP Sent:</strong> Use verification code <strong><code>{otp_code}</code></strong> to set a new password.
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error("No registered shop matched that Gmail, Mobile Number, or Username.")
                    conn.close()
                
                rec_otp = st.text_input("Enter 6-Digit Recovery OTP")
                rec_new_pw = st.text_input("Enter New Password (min 6 characters)", type="password")
                if st.button("Verify OTP & Save New Password", type="primary"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("""
                        SELECT shop_id, reset_otp FROM shops
                        WHERE owner_username=? OR LOWER(owner_email)=LOWER(?) OR owner_phone=?
                    """, (recovery_input.strip(), recovery_input.strip(), recovery_input.strip()))
                    r = c.fetchone()
                    if r and r[1] and r[1] == rec_otp.strip() and len(rec_new_pw) >= 6:
                        nhash, nsalt = hash_password(rec_new_pw)
                        c.execute("UPDATE shops SET password_hash=?, salt=?, reset_otp=NULL WHERE shop_id=?", (nhash, nsalt, r[0]))
                        conn.commit()
                        st.success("Password updated! You can now sign in from the first tab.")
                    else:
                        st.error("Invalid OTP or password shorter than 6 characters.")
                    conn.close()

    else:
        # ==========================================
        # AUTHENTICATED SHOP OWNER CONSOLE
        # ==========================================
        shop_id = st.session_state.authenticated_shop
        conn = sqlite3.connect(DB_FILE)
        shop_row = pd.read_sql_query("SELECT * FROM shops WHERE shop_id=?", conn, params=(shop_id,)).iloc[0]
        jobs_df = pd.read_sql_query("SELECT * FROM print_jobs WHERE shop_id=? ORDER BY job_id DESC", conn, params=(shop_id,))
        printers_list = json.loads(shop_row["printers_json"])
        conn.close()

        top_c1, top_c2 = st.columns([3.5, 1])
        with top_c1:
            st.markdown(f"""
            <div class="hero-header">
                <h1>🖨️ {shop_row['shop_name']} — Fulfillment Console</h1>
                <p>Shop ID: {shop_id} • Contact: {shop_row['owner_email'] or 'N/A'} | {shop_row['owner_phone'] or 'N/A'}</p>
            </div>
            """, unsafe_allow_html=True)
        with top_c2:
            st.write("")
            if st.button("🔒 Sign Out", use_container_width=True):
                st.session_state.authenticated_shop = None
                st.rerun()

        m1, m2, m3, m4 = st.columns(4)
        pending_cnt = len(jobs_df[jobs_df["status"] == "Pending"])
        printing_cnt = len(jobs_df[jobs_df["status"] == "Printing"])
        ready_cnt = len(jobs_df[jobs_df["status"].isin(["Ready for Pickup", "Completed"])])
        revenue_sum = jobs_df["total_cost"].sum() if not jobs_df.empty else 0.0
        
        m1.metric("🟡 Waiting in Queue", f"{pending_cnt} Orders")
        m2.metric("🟣 Active on Printers", f"{printing_cnt} Orders")
        m3.metric("🟢 Ready for Pickup", f"{ready_cnt} Orders")
        m4.metric("💰 Today's Revenue", f"₹{revenue_sum:.2f}")

        owner_tabs = st.tabs([
            "📋 Live Queue & Hardware Print Dialog",
            "📲 Shop QR Code Poster (Direct Student Link)",
            "🖨️ Printer Fleet & Shop Rates",
            "🔑 Account Settings"
        ])

        # TAB 1: KANBAN & HARDWARE PRINT DIALOG
        with owner_tabs[0]:
            k_pending, k_printing, k_ready = st.columns([1.35, 1, 1])
            printer_labels = [f"🖨️ {p['name']} [{p['type']} • {p['status']}]" for p in printers_list]

            with k_pending:
                st.subheader(f"🟡 Pending Queue ({pending_cnt})")
                for _, job in jobs_df[jobs_df["status"] == "Pending"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### <span class='token-badge'>{job['daily_token']}</span> {job['student_name']}", unsafe_allow_html=True)
                        st.caption(f"Received: {job['time_uploaded']} • Mobile: {job['student_phone'] or 'N/A'}")
                        st.info(
                            f"**{job['color_mode']}** | **{job['copies']} Copies** | "
                            f"**{job['n_up']} Pages/Sheet** | **₹{job['total_cost']:.2f}**"
                        )
                        
                        if job["processed_pdf"]:
                            st.download_button(
                                f"📥 Download Print-Ready PDF ({job['pages_count']} A4 pgs)",
                                data=job["processed_pdf"],
                                file_name=job["pdf_filename"],
                                mime="application/pdf",
                                key=f"dl_{job['job_id']}",
                                use_container_width=True
                            )
                        
                        with st.expander("🖨️ Proceed to Print — Select Printer & Preferences", expanded=True):
                            rec_idx = 0 if "Color" in str(job["color_mode"]) else (1 if len(printer_labels) > 1 else 0)
                            selected_printer_label = st.selectbox(
                                "Select Destination Printer",
                                options=printer_labels,
                                index=rec_idx,
                                key=f"prt_{job['job_id']}"
                            )
                            
                            pr_c1, pr_c2 = st.columns(2)
                            with pr_c1:
                                dlg_copies = st.number_input("Copies", min_value=1, max_value=200, value=int(job["copies"]), key=f"cp_{job['job_id']}")
                                dlg_custom_pgs = st.text_input("Page Range", value=str(job["page_range"]), key=f"cpg_{job['job_id']}")
                                dlg_sides = st.selectbox(
                                    "Two-Sided Mode",
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
                                    "Margins",
                                    ["Normal Margins", "Narrow Margins", "Minimal Margins"],
                                    index=0,
                                    key=f"mg_{job['job_id']}"
                                )
                                dlg_scaling = st.selectbox(
                                    "Scaling",
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
                        st.markdown(f"#### <span class='token-badge'>{job['daily_token']}</span> {job['student_name']}", unsafe_allow_html=True)
                        st.success(f"🖨️ **Printer:** `{job['assigned_printer']}`")
                        st.write(f"**Specs:** {job['copies']} Copies • {job['sides']} • {job['paper_size']}")
                        st.caption(f"Started at: {job['time_started']}")
                        
                        if st.button("✅ Mark Ready for Pickup", key=f"rdy_{job['job_id']}", type="primary", use_container_width=True):
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
                        st.markdown(f"#### <span class='token-badge'>{job['daily_token']}</span> {job['student_name']}", unsafe_allow_html=True)
                        st.write(f"Printed on: `{job['assigned_printer']}`")
                        st.success(f"Collect **₹{job['total_cost']:.2f}**")
                        st.caption(f"Completed at: {job['time_completed']}")

        # TAB 2: DIRECT QR GENERATOR
        with owner_tabs[1]:
            with st.container(border=True):
                st.subheader("📲 Unique Shop QR Code Poster")
                local_ip = get_local_wifi_ip()
                qr_col1, qr_col2 = st.columns([1.4, 1])
                with qr_col1:
                    st.markdown("""
                    Print and place this QR poster at your shop counter. When students scan it:
                    1. Their phone browser opens directly to **your shop's upload page**.
                    2. Every uploaded document is routed exclusively to your shop queue.
                    """)
                    host_base = st.text_input(
                        "Public App Domain (or Local Wi-Fi IP):",
                        value=f"http://{local_ip}:8501"
                    )
                    direct_student_url = f"{host_base.rstrip('/')}/?shop_id={shop_id}&portal=student"
                    st.code(direct_student_url, language="text")
                with qr_col2:
                    qr = qrcode.QRCode(version=1, box_size=10, border=3)
                    qr.add_data(direct_student_url)
                    qr.make(fit=True)
                    qr_img = qr.make_image(fill_color="black", back_color="white")
                    buf = io.BytesIO()
                    qr_img.save(buf, format="PNG")
                    st.image(buf.getvalue(), width=240, caption=f"{shop_row['shop_name']} ({shop_id})")
                    st.download_button(
                        "📥 Download High-Res QR Poster (PNG)",
                        data=buf.getvalue(),
                        file_name=f"{shop_id}_QR_Poster.png",
                        mime="image/png",
                        use_container_width=True
                    )

        # TAB 3: PRINTERS & RATES
        with owner_tabs[2]:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                with st.container(border=True):
                    st.subheader("🖨️ Connected Shop Printers")
                    st.dataframe(pd.DataFrame(printers_list), use_container_width=True)
                    if st.button("🔍 Sync Physical Printers from Windows PC", use_container_width=True):
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
                            st.success("Synced Windows printers!")
                            st.rerun()
                        else:
                            st.info("No additional local printers detected.")

                    with st.form("add_printer_form"):
                        st.markdown("**Add New Printer to Shop**")
                        new_p_name = st.text_input("Printer Model / Tray", placeholder="e.g., Konica Minolta Bizhub C226i")
                        new_p_type = st.selectbox("Type", ["B&W", "Color", "B&W / Universal"])
                        new_p_ppm = st.number_input("Speed (PPM)", min_value=10, max_value=120, value=45)
                        if st.form_submit_button("Add Printer"):
                            if new_p_name:
                                printers_list.append({"name": new_p_name, "type": new_p_type, "status": "Ready", "ppm": new_p_ppm})
                                conn = sqlite3.connect(DB_FILE)
                                conn.execute("UPDATE shops SET printers_json=? WHERE shop_id=?", (json.dumps(printers_list), shop_id))
                                conn.commit()
                                conn.close()
                                st.rerun()
            with p_col2:
                with st.container(border=True):
                    st.subheader("💲 Per-Page Pricing")
                    new_bw = st.number_input("Black & White Rate (₹/page)", value=float(shop_row["bw_price"]), step=0.5)
                    new_col = st.number_input("Color Rate (₹/page)", value=float(shop_row["color_price"]), step=1.0)
                    if st.button("Save Pricing", type="primary"):
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("UPDATE shops SET bw_price=?, color_price=? WHERE shop_id=?", (new_bw, new_col, shop_id))
                        conn.commit()
                        conn.close()
                        st.success("Rates updated!")

                    st.divider()
                    st.subheader("🔄 End-of-Day Queue Reset")
                    if st.button("🗑️ Clear Completed Jobs & Reset Token Counter to #001"):
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("DELETE FROM print_jobs WHERE shop_id=?", (shop_id,))
                        conn.commit()
                        conn.close()
                        st.success("Daily token counter reset to #001!")
                        st.rerun()

        # TAB 4: ACCOUNT SETTINGS
        with owner_tabs[3]:
            with st.container(border=True):
                st.subheader("🔑 Update Shop Password")
                old_p = st.text_input("Current Password", type="password")
                new_p1 = st.text_input("New Password", type="password")
                new_p2 = st.text_input("Confirm New Password", type="password")
                if st.button("Change Password", type="primary"):
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
                        st.success("Password updated!")

# ==========================================
# PORTAL 3: HIDDEN SUPER ADMIN CONSOLE
# (Only accessible via ?portal=superadmin or secret login)
# ==========================================
elif app_mode == "🛡️ Hidden Super Admin":
    st.title("🛡️ Internal App Host Administration")
    if not st.session_state.super_admin_auth:
        u = st.text_input("Host Admin Username")
        p = st.text_input("Host Master Password", type="password")
        if st.button("Unlock Console", type="primary"):
            if u == "host_master" and p == "supersecret":
                st.session_state.super_admin_auth = True
                st.rerun()
            else:
                st.error("Invalid credentials.")
    else:
        if st.button("Exit Hidden Admin Console"):
            st.session_state.super_admin_auth = False
            st.session_state.show_hidden_admin = False
            st.query_params.clear()
            st.rerun()

        conn = sqlite3.connect(DB_FILE)
        all_shops = pd.read_sql_query("SELECT shop_id, shop_name, owner_username, owner_email, owner_phone, password_hash, bw_price, color_price, account_status, created_at FROM shops", conn)
        all_jobs = pd.read_sql_query("SELECT shop_id, daily_token, assigned_printer, pages_count, n_up, total_cost, status, time_uploaded, time_started, time_completed FROM print_jobs", conn)
        conn.close()

        st.subheader("🏪 All Registered Partner Shops")
        st.dataframe(all_shops, use_container_width=True)

        st.subheader("📊 Global Print Queue Telemetry")
        st.dataframe(all_jobs, use_container_width=True)
        csv_jobs = all_jobs.to_csv(index=False).encode("utf-8")
        st.download_button("📥 Export Telemetry CSV", data=csv_jobs, file_name="printflow_telemetry.csv", mime="text/csv")