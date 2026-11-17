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
import smtplib
from email.message import EmailMessage
import requests
import pandas as pd
import fitz  # PyMuPDF
from PIL import Image, ImageOps
import qrcode

# ==========================================
# 1. PAGE CONFIG & ENTERPRISE SAAS CSS THEME
# ==========================================
st.set_page_config(
    page_title="PrintFlow Cloud | Smart Reprographics SaaS",
    page_icon="🖨️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

    /* Global Typography & Background */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #0f172a;
    }
    .stApp {
        background: radial-gradient(circle at top right, #eef2ff 0%, #f8fafc 45%, #f1f5f9 100%);
    }

    /* Hide Default Streamlit Chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {background: transparent !important;}

    /* Sleek Sidebar Styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #090d16 0%, #0f172a 100%) !important;
        border-right: 1px solid #1e293b;
    }
    section[data-testid="stSidebar"] * {
        color: #f8fafc !important;
    }
    section[data-testid="stSidebar"] .stCaption {
        color: #94a3b8 !important;
    }
    section[data-testid="stSidebar"] input {
        background-color: #1e293b !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
    }

    /* Container Card Elevation */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 16px !important;
        padding: 20px !important;
        box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05) !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }

    /* Primary & Secondary Buttons */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.65rem 1.2rem !important;
        font-weight: 700 !important;
        letter-spacing: 0.2px !important;
        box-shadow: 0 6px 16px -3px rgba(37, 99, 235, 0.35) !important;
        transition: all 0.2s ease !important;
    }
    div.stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 10px 22px -3px rgba(37, 99, 235, 0.5) !important;
    }
    div.stButton > button[kind="secondary"] {
        background-color: #f8fafc !important;
        color: #1e293b !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
    }

    /* Modern Pill Tabs */
    button[data-baseweb="tab"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 10px 20px !important;
    }

    /* Top Hero Glass Banner */
    .saas-hero {
        background: linear-gradient(125deg, #090d16 0%, #1e1b4b 55%, #1d4ed8 100%);
        border-radius: 20px;
        padding: 28px 34px;
        color: white;
        margin-bottom: 24px;
        box-shadow: 0 18px 35px -10px rgba(15, 23, 42, 0.25);
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(255, 255, 255, 0.12);
    }
    .saas-hero-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(8px);
        color: #93c5fd;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 5px 12px;
        border-radius: 999px;
        margin-bottom: 10px;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    .saas-hero h1 {
        font-size: 1.95rem;
        font-weight: 800;
        margin: 0;
        color: #ffffff;
        letter-spacing: -0.5px;
    }
    .saas-hero p {
        font-size: 0.96rem;
        color: #cbd5e1;
        margin: 6px 0 0 0;
    }

    /* Executive KPI Stat Cards */
    .kpi-card {
        background: #ffffff;
        border-radius: 16px;
        padding: 20px 22px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .kpi-title {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.6px;
        color: #64748b;
    }
    .kpi-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #0f172a;
        margin-top: 6px;
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    .kpi-sub {
        font-size: 0.78rem;
        font-weight: 600;
        margin-top: 4px;
    }

    /* Digital Invoice / Receipt Box */
    .receipt-box {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
        border-radius: 16px;
        padding: 22px;
        border: 1px solid #334155;
        box-shadow: 0 12px 28px -6px rgba(15, 23, 42, 0.25);
    }
    .receipt-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px dashed #475569;
        padding-bottom: 12px;
        margin-bottom: 14px;
    }
    .receipt-row {
        display: flex;
        justify-content: space-between;
        font-size: 0.9rem;
        color: #cbd5e1;
        margin: 8px 0;
    }
    .receipt-total {
        border-top: 1px dashed #475569;
        margin-top: 14px;
        padding-top: 14px;
        display: flex;
        justify-content: space-between;
        align-items: baseline;
    }
    .receipt-price {
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.85rem;
        font-weight: 800;
        color: #38bdf8;
    }

    /* Monospace Token Pill */
    .token-pill {
        font-family: 'JetBrains Mono', monospace;
        background: #eef2ff;
        color: #3730a3;
        border: 1px solid #c7d2fe;
        padding: 4px 12px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 0.92rem;
    }

    /* Kanban Column Headers */
    .kanban-col-header {
        padding: 12px 16px;
        border-radius: 12px;
        font-weight: 700;
        font-size: 0.95rem;
        margin-bottom: 14px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .kh-pending { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
    .kh-printing { background: #f5f3ff; color: #6d28d9; border: 1px solid #ddd6fe; }
    .kh-ready { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }

    /* OTP Alert Banner */
    .otp-banner {
        background: linear-gradient(90deg, #ecfdf5 0%, #f0fdf4 100%);
        border: 1px solid #86efac;
        border-left: 5px solid #16a34a;
        padding: 16px 20px;
        border-radius: 12px;
        color: #14532d;
        margin: 14px 0;
    }

    /* Visual Stepper for Student Order Tracking */
    .stepper-wrap {
        display: flex;
        justify-content: space-between;
        margin: 22px 0;
        gap: 10px;
    }
    .step-item {
        flex: 1;
        text-align: center;
        padding: 14px 10px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        background: #f8fafc;
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748b;
    }
    .step-active {
        background: #eff6ff;
        border: 2px solid #2563eb;
        color: #1d4ed8;
        font-weight: 700;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.12);
    }
    .step-done {
        background: #ecfdf5;
        border: 1px solid #34d399;
        color: #047857;
    }
</style>
""", unsafe_allow_html=True)

DB_FILE = "printflow_saas.db"

# ==========================================
# 2. REAL SMS & GMAIL OTP DISPATCH ENGINE
# ==========================================
def dispatch_real_otp(destination: str, otp_code: str, channel: str, smtp_user: str = "", smtp_pass: str = "", fast2sms_key: str = "") -> tuple[bool, str]:
    clean_dest = destination.strip()

    if "Gmail" in channel or "@" in clean_dest:
        if smtp_user and smtp_pass:
            try:
                msg = EmailMessage()
                msg["Subject"] = f"PrintFlow Verification Code: {otp_code}"
                msg["From"] = smtp_user
                msg["To"] = clean_dest
                msg.set_content(
                    f"Hello,\n\nYour 6-digit PrintFlow verification OTP is: {otp_code}\n\n"
                    f"Use this code to complete your print shop verification.\n\n- PrintFlow Cloud"
                )
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
                    server.login(smtp_user, smtp_pass)
                    server.send_message(msg)
                return True, f"Live email delivered to **{clean_dest}** via Gmail SMTP."
            except Exception as e:
                return False, f"SMTP Notice ({e}). Instant verification code displayed below."
        return False, "Instant Sandbox OTP generated below (Add Gmail App Password in sidebar for live email delivery)."

    else:
        phone_digits = "".join(filter(str.isdigit, clean_dest))[-10:]
        if fast2sms_key and len(phone_digits) == 10:
            try:
                url = "https://www.fast2sms.com/dev/bulkV2"
                payload = {"variables_values": otp_code, "route": "otp", "numbers": phone_digits}
                headers = {
                    "authorization": fast2sms_key,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Cache-Control": "no-cache"
                }
                resp = requests.post(url, data=payload, headers=headers, timeout=10)
                data = resp.json()
                if data.get("return") is True:
                    return True, f"Live SMS delivered to **+91-{phone_digits}**!"
                else:
                    return False, f"Gateway Notice: {data.get('message', 'Check API Key')}. Code displayed below."
            except Exception as e:
                return False, f"SMS Notice ({e}). Code displayed below."
        return False, "Instant Sandbox OTP generated below (Add Fast2SMS key in sidebar for cellular SMS)."

# ==========================================
# 3. EXACT PDF & IMAGE PAGE COUNTER + N-UP ENGINE
# ==========================================
def parse_custom_page_range(range_str: str, max_pages: int) -> list[int]:
    if not range_str or range_str.strip().lower() == "all":
        return list(range(max_pages))
    selected = set()
    parts = range_str.replace(" ", "").split(",")
    for part in parts:
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start_p = max(1, int(start_s))
                end_p = min(max_pages, int(end_s))
                if start_p <= end_p:
                    for p in range(start_p - 1, end_p):
                        selected.add(p)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= max_pages:
                    selected.add(p - 1)
            except ValueError:
                continue
    return sorted(selected) if selected else list(range(max_pages))

def inspect_uploaded_files(uploaded_files) -> tuple[int, list[dict]]:
    total_raw_pages = 0
    breakdown = []
    for f in uploaded_files:
        f.seek(0)
        fname = f.name
        if fname.lower().endswith(".pdf"):
            try:
                pdf_bytes = f.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                pg_cnt = max(1, len(doc))
                doc.close()
            except Exception:
                pg_cnt = 1
            breakdown.append({"Document": fname, "Format": "PDF", "Pages": pg_cnt})
            total_raw_pages += pg_cnt
        else:
            breakdown.append({"Document": fname, "Format": "Image", "Pages": 1})
            total_raw_pages += 1
        f.seek(0)
    return total_raw_pages, breakdown

def build_nup_pdf(uploaded_files, n_up: int, color_mode: str, orientation: str, page_range_str: str = "All") -> tuple[bytes, int]:
    a4_w, a4_h = (1240, 1754) if "Portrait" in orientation else (1754, 1240)
    margin = 40
    is_bw = "Black & White" in color_mode

    all_page_images = []
    for f in uploaded_files:
        f.seek(0)
        fname = f.name.lower()
        if fname.endswith(".pdf"):
            try:
                pdf_bytes = f.read()
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                for page in doc:
                    pix = page.get_pixmap(dpi=150)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    if is_bw:
                        img = ImageOps.grayscale(img).convert("RGB")
                    all_page_images.append(img)
                doc.close()
            except Exception:
                pass
        elif fname.endswith((".png", ".jpg", ".jpeg")):
            img = Image.open(f).convert("RGB")
            if is_bw:
                img = ImageOps.grayscale(img).convert("RGB")
            all_page_images.append(img)
        f.seek(0)

    if not all_page_images:
        return b"", 1

    selected_indices = parse_custom_page_range(page_range_str, len(all_page_images))
    filtered_images = [all_page_images[i] for i in selected_indices]

    grid_map = {
        1: (1, 1),
        2: (1, 2) if "Portrait" in orientation else (2, 1),
        4: (2, 2),
        6: (2, 3) if "Portrait" in orientation else (3, 2)
    }
    cols, rows = grid_map.get(n_up, (1, 1))
    cell_w = (a4_w - margin * (cols + 1)) // cols
    cell_h = (a4_h - margin * (rows + 1)) // rows

    output_pages = []
    for i in range(0, len(filtered_images), n_up):
        canvas = Image.new("RGB", (a4_w, a4_h), "white")
        batch = filtered_images[i:i + n_up]
        for idx, img in enumerate(batch):
            r = idx // cols
            c = idx % cols
            img_copy = img.copy()
            img_copy.thumbnail((cell_w, cell_h), Image.Resampling.LANCZOS)

            x = margin + c * (cell_w + margin) + (cell_w - img_copy.width) // 2
            y = margin + r * (cell_h + margin) + (cell_h - img_copy.height) // 2
            canvas.paste(img_copy, (x, y))
        output_pages.append(canvas)

    pdf_buffer = io.BytesIO()
    output_pages[0].save(pdf_buffer, format="PDF", save_all=True, append_images=output_pages[1:])
    return pdf_buffer.getvalue(), len(output_pages)

# ==========================================
# 4. NETWORK & HARDWARE PRINTER HELPERS
# ==========================================
def get_local_wifi_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"

def detect_windows_printers() -> list[dict]:
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
# 5. CRYPTOGRAPHY & SQLITE DATABASE ENGINE
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
# 6. SESSION STATE & URL ROUTING
# ==========================================
for k, v in {
    "authenticated_shop": None,
    "super_admin_auth": False,
    "active_student_token": None,
    "reg_otp_code": None,
    "reg_pending_data": None,
    "reg_dispatch_msg": "",
    "rec_otp_code": None,
    "rec_target_user": None,
    "smtp_email": "",
    "smtp_app_password": "",
    "fast2sms_api_key": ""
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

query_params = st.query_params
routed_shop_id = query_params.get("shop_id", None)
routed_portal = query_params.get("portal", None)

if routed_portal == "superadmin":
    st.session_state.show_hidden_admin = True
elif "show_hidden_admin" not in st.session_state:
    st.session_state.show_hidden_admin = False

# ==========================================
# 7. SIDEBAR BRANDING & NAVIGATION
# ==========================================
st.sidebar.markdown("""
<div style="padding: 10px 4px 18px 4px; border-bottom: 1px solid #1e293b; margin-bottom: 18px;">
    <div style="font-size: 1.35rem; font-weight: 800; letter-spacing: -0.5px; color: #ffffff;">
        🖨️ PrintFlow <span style="color: #38bdf8; font-weight: 700;">Cloud</span>
    </div>
    <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 4px;">
        Autonomous Document Queue & Dispatch
    </div>
</div>
""", unsafe_allow_html=True)

if st.session_state.super_admin_auth or st.session_state.show_hidden_admin:
    app_mode = "🛡️ Hidden Super Admin"
elif routed_portal == "student" and routed_shop_id:
    st.sidebar.success(f"📲 QR Session Active\nShop ID: `{routed_shop_id}`")
    if st.sidebar.button("🔄 Switch to Partner Portal", use_container_width=True):
        st.query_params.clear()
        st.rerun()
    app_mode = "📱 Student Print Portal"
else:
    st.sidebar.caption("SELECT WORKSPACE")
    app_mode = st.sidebar.radio(
        "Workspace",
        ["📱 Student Print Portal", "🏪 Partner Shop Portal"],
        label_visibility="collapsed"
    )

st.sidebar.divider()
with st.sidebar.expander("⚙️ Live SMS / Gmail OTP Gateway"):
    st.caption("Optional: Add keys for cellular SMS or Gmail SMTP delivery. Otherwise, OTPs appear instantly on screen.")
    st.session_state.fast2sms_api_key = st.text_input("Fast2SMS API Key", value=st.session_state.fast2sms_api_key, type="password")
    st.session_state.smtp_email = st.text_input("Sender Gmail", value=st.session_state.smtp_email, placeholder="yourapp@gmail.com")
    st.session_state.smtp_app_password = st.text_input("Gmail App Password", value=st.session_state.smtp_app_password, type="password")

st.sidebar.markdown("""
<div style="margin-top: 28px; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 10px; border: 1px solid rgba(255,255,255,0.08); font-size: 0.76rem; color: #94a3b8;">
    🟢 <strong>System Status:</strong> All Print Nodes Online<br>
    🔒 <strong>Security:</strong> PBKDF2-SHA256 Encrypted
</div>
""", unsafe_allow_html=True)

# ==========================================
# PORTAL 1: STUDENT PRINT PORTAL
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
        <div class="saas-hero">
            <div class="saas-hero-badge">📲 QR Express Terminal • Verified Partner</div>
            <h1>{current_shop['shop_name']}</h1>
            <p>Upload your PDFs or images below. Your files are automatically formatted and routed to counter <strong>{selected_shop_id}</strong>.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="saas-hero">
            <div class="saas-hero-badge">⚡ Zero-Queue Campus Printing</div>
            <h1>Student Document & Layout Portal</h1>
            <p>Select your campus reprographics center, customize N-up page layouts, and receive an instant digital queue token.</p>
        </div>
        """, unsafe_allow_html=True)

        bar_c1, bar_c2 = st.columns([2.2, 1])
        with bar_c1:
            selected_shop_id = st.selectbox(
                "📍 Choose Active Campus Print Center",
                options=list(shop_options.keys()),
                format_func=lambda x: shop_options[x]
            )
        current_shop = shops_df[shops_df["shop_id"] == selected_shop_id].iloc[0]
        with bar_c2:
            st.markdown(f"""
            <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:12px; padding:10px 16px; margin-top:4px; display:flex; justify-content:space-around;">
                <div><span style="font-size:0.75rem; color:#64748b; font-weight:600;">B&W TARIFF</span><br><strong style="font-size:1.1rem; color:#0f172a;">₹{current_shop['bw_price']:.2f}/pg</strong></div>
                <div style="border-left:1px solid #e2e8f0; padding-left:16px;"><span style="font-size:0.75rem; color:#64748b; font-weight:600;">COLOR TARIFF</span><br><strong style="font-size:1.1rem; color:#2563eb;">₹{current_shop['color_price']:.2f}/pg</strong></div>
            </div>
            """, unsafe_allow_html=True)

    tab_upload, tab_track = st.tabs(["📤 1. Upload & Configure Print Job", "⏱️ 2. Live Token Status Tracker"])

    with tab_upload:
        col_form, col_preview = st.columns([1.45, 1])

        with col_form:
            with st.container(border=True):
                st.markdown("#### 👤 Student Details & File Upload")
                s_col1, s_col2 = st.columns(2)
                student_name = s_col1.text_input("Full Name *", placeholder="e.g., Aditya Rao")
                student_phone = s_col2.text_input("WhatsApp / Mobile Number", placeholder="e.g., 9876543210")

                uploaded_files = st.file_uploader(
                    "Drop PDF documents or images (PNG, JPG) here",
                    type=["png", "jpg", "jpeg", "pdf"],
                    accept_multiple_files=True
                )

            with st.container(border=True):
                st.markdown("#### ⚙️ Print & Layout Preferences")
                p_col1, p_col2, p_col3 = st.columns(3)
                with p_col1:
                    color_mode = st.selectbox("Color Output", [f"Black & White (₹{current_shop['bw_price']:.2f}/pg)", f"Color (₹{current_shop['color_price']:.2f}/pg)"])
                    sides = st.selectbox("Duplex Mode", ["Print One Sided", "Print on Both Sides (Flip on Long Edge)", "Print on Both Sides (Flip on Short Edge)"])
                    copies = st.number_input("Copies", min_value=1, max_value=100, value=1)
                with p_col2:
                    n_up = st.selectbox("Pages per Sheet (N-up)", [1, 2, 4, 6], index=0)
                    orientation = st.selectbox("Orientation", ["Portrait Orientation", "Landscape Orientation"])
                    paper_size = st.selectbox("Paper Stock", ["A4 (210 x 297 mm)", "Letter (8.5 x 11 in)", "A3 (297 x 420 mm)"])
                with p_col3:
                    page_range_type = st.selectbox("Page Selection", ["Print All Pages", "Custom Page Range"])
                    custom_range = st.text_input(
                        "Page Numbers (e.g. 1-5, 8)",
                        value="All" if page_range_type == "Print All Pages" else "1-5",
                        disabled=(page_range_type == "Print All Pages")
                    )
                    collated = st.selectbox("Collation", ["Collated (1,2,3 - 1,2,3)", "Uncollated (1,1,1 - 2,2,2)"])

        with col_preview:
            with st.container(border=True):
                st.markdown("#### 🧾 Instant Digital Estimate")
                if uploaded_files:
                    total_raw_pages, file_breakdown = inspect_uploaded_files(uploaded_files)
                    active_page_indices = parse_custom_page_range(custom_range, total_raw_pages)
                    selected_raw_pages = len(active_page_indices)
                    billable_pages_per_copy = int(math.ceil(selected_raw_pages / n_up))

                    if "Both Sides" in sides:
                        physical_sheets_per_copy = int(math.ceil(billable_pages_per_copy / 2))
                    else:
                        physical_sheets_per_copy = billable_pages_per_copy

                    rate_per_page = float(current_shop["bw_price"]) if "Black & White" in color_mode else float(current_shop["color_price"])
                    total_billable_pages = billable_pages_per_copy * int(copies)
                    total_cost = total_billable_pages * rate_per_page

                    st.dataframe(pd.DataFrame(file_breakdown), use_container_width=True, hide_index=True)

                    st.markdown(f"""
                    <div class="receipt-box">
                        <div class="receipt-header">
                            <span style="font-weight:700; color:#ffffff; font-size:0.95rem;">{current_shop['shop_name']}</span>
                            <span style="background:#1e3a8a; color:#93c5fd; padding:3px 10px; border-radius:99px; font-size:0.75rem; font-weight:700;">LIVE QUOTE</span>
                        </div>
                        <div class="receipt-row">
                            <span>Detected Source Pages</span>
                            <strong>{selected_raw_pages} of {total_raw_pages} pg(s)</strong>
                        </div>
                        <div class="receipt-row">
                            <span>N-Up Layout ({n_up} per page)</span>
                            <strong>{billable_pages_per_copy} A4 page(s)/copy</strong>
                        </div>
                        <div class="receipt-row">
                            <span>Physical Paper Sheets</span>
                            <strong>{physical_sheets_per_copy} sheet(s)/copy</strong>
                        </div>
                        <div class="receipt-row">
                            <span>Copies × Tariff Rate</span>
                            <strong>{copies} × ₹{rate_per_page:.2f}</strong>
                        </div>
                        <div class="receipt-total">
                            <div>
                                <div style="font-size:0.75rem; color:#94a3b8; text-transform:uppercase; font-weight:700;">Estimated Total</div>
                                <div style="font-size:0.8rem; color:#cbd5e1;">Pay at shop counter upon pickup</div>
                            </div>
                            <div class="receipt-price">₹{total_cost:.2f}</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.write("")
                    if st.button("🚀 Confirm Print Order & Generate Token", type="primary", use_container_width=True):
                        if not student_name.strip():
                            st.warning("Please enter your Full Name before submitting.")
                        else:
                            with st.spinner("Running N-up PDF Layout Engine & assigning queue token..."):
                                pdf_bytes, final_pages = build_nup_pdf(
                                    uploaded_files, n_up, color_mode, orientation, custom_range
                                )
                                final_total_cost = final_pages * int(copies) * rate_per_page

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
                                    paper_size, custom_range, collated, final_total_cost, pdf_bytes,
                                    f"{selected_shop_id}_{token_str.replace('#','T')}.pdf", now_str
                                ))
                                conn.commit()
                                conn.close()

                                st.session_state.active_student_token = (selected_shop_id, token_str)
                                st.success(f"🎉 Order Confirmed! Your Queue Token is **{token_str}** (Payable: ₹{final_total_cost:.2f})")
                                st.download_button(
                                    "📥 Download Formatted A4 PDF Preview",
                                    data=pdf_bytes,
                                    file_name=f"PrintPreview_{token_str.replace('#','')}.pdf",
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                else:
                    st.markdown("""
                    <div style="text-align:center; padding: 38px 18px; background:#f8fafc; border: 2px dashed #cbd5e1; border-radius: 14px; color:#64748b;">
                        <div style="font-size:2.2rem; margin-bottom:8px;">📄</div>
                        <div style="font-weight:700; color:#1e293b; font-size:1rem;">No Documents Selected Yet</div>
                        <div style="font-size:0.86rem; margin-top:4px;">Upload any PDF or image batch on the left to inspect exact page counts and live pricing.</div>
                    </div>
                    """, unsafe_allow_html=True)

    with tab_track:
        with st.container(border=True):
            st.markdown("#### 🛰️ Real-Time Queue Token Tracker")
            t_col1, t_col2 = st.columns([1, 2.2])
            with t_col1:
                default_tok = st.session_state.active_student_token[1] if st.session_state.active_student_token else "#001"
                search_token = st.text_input("Enter Queue Token Number", value=default_tok)
                if st.button("🔄 Refresh Live Status", type="primary", use_container_width=True):
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
                    st_val = j["status"]
                    s1_cls = "step-done" if st_val in ["Printing", "Ready for Pickup", "Completed"] else "step-active"
                    s2_cls = "step-active" if st_val == "Printing" else ("step-done" if st_val in ["Ready for Pickup", "Completed"] else "")
                    s3_cls = "step-active" if st_val in ["Ready for Pickup", "Completed"] else ""

                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span class="token-pill">{j['daily_token']}</span>
                            <span style="font-size:1.15rem; font-weight:800; margin-left:10px;">{j['student_name']}</span>
                        </div>
                        <div style="font-family:'JetBrains Mono',monospace; font-size:1.25rem; font-weight:800; color:#2563eb;">
                            ₹{j['total_cost']:.2f}
                        </div>
                    </div>
                    <div class="stepper-wrap">
                        <div class="step-item {s1_cls}">1. Queued at Shop</div>
                        <div class="step-item {s2_cls}">2. Printing on Hardware</div>
                        <div class="step-item {s3_cls}">3. Ready for Counter Pickup</div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.write(f"**Assigned Hardware Printer:** `{j['assigned_printer']}` | **Specs:** {j['pages_count']} A4 pgs × {j['copies']} copies ({j['color_mode']})")
                    st.caption(f"Uploaded: {j['time_uploaded']} • Dispatched: {j['time_started'] or 'Waiting'} • Completed: {j['time_completed'] or 'In Progress'}")
                else:
                    st.info(f"No order found for Token `{search_token}` at {current_shop['shop_name']}.")

# ==========================================
# PORTAL 2: PARTNER SHOP PORTAL
# ==========================================
elif app_mode == "🏪 Partner Shop Portal":
    if not st.session_state.authenticated_shop:
        st.markdown("""
        <div class="saas-hero">
            <div class="saas-hero-badge">🏪 Partner Enterprise Console</div>
            <h1>PrintFlow Partner Portal</h1>
            <p>Sign in to manage your live print queue and hardware printers, or onboard your shop with instant OTP verification.</p>
        </div>
        """, unsafe_allow_html=True)

        auth_tab1, auth_tab2, auth_tab3 = st.tabs([
            "🔑 Operator Sign In",
            "🏪 Register New Print Shop (OTP Verified)",
            "🔄 Password Recovery"
        ])

        with auth_tab1:
            col_l1, col_l2 = st.columns([1.15, 1])
            with col_l1:
                with st.container(border=True):
                    st.markdown("#### 🔐 Sign In to Operator Terminal")
                    login_id = st.text_input("Username, Gmail, or Mobile Number", placeholder="e.g., mainxerox@gmail.com or 9876543210")
                    login_pw = st.text_input("Operator Password", type="password", placeholder="••••••••")

                    if st.button("Access Shop Terminal →", type="primary", use_container_width=True):
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
                            st.error("Account not found. Check your login ID or register a new shop.")
                        else:
                            shop_id, shop_name, pw_hash, salt, acc_status = row
                            if acc_status != "Active":
                                st.error("This shop account is currently inactive.")
                            elif verify_password(login_pw, pw_hash, salt):
                                st.session_state.authenticated_shop = shop_id
                                st.rerun()
                            else:
                                st.error("Incorrect password. Please try again.")
            with col_l2:
                with st.container(border=True):
                    st.markdown("#### 🚀 Built for High-Volume Reprographics")
                    st.markdown("""
                    * **📲 Counter QR Routing:** Students scan your shop QR poster and land directly on your branded upload portal.
                    * **📐 Automated N-Up & PDF Engine:** Multi-page PDFs and image batches are counted, priced, and formatted automatically.
                    * **🖨️ Hardware Print Dispatcher:** Route B&W jobs to high-speed laser trays and color jobs to ink/toner units in one click.
                    """)

        with auth_tab2:
            with st.container(border=True):
                st.markdown("#### 🏪 Onboard Your Print Shop")
                st.caption("Register your shop credentials and verify via Mobile SMS or Gmail OTP.")

                r_col1, r_col2 = st.columns(2)
                with r_col1:
                    reg_shop_name = st.text_input("Print Shop Business Name *", placeholder="e.g., Sri Sai Digital Reprographics")
                    reg_shop_code = st.text_input("Unique Shop ID Code *", placeholder="e.g., SAI_XEROX_04").strip().upper().replace(" ", "_")
                    reg_username = st.text_input("Operator Login Username *", placeholder="e.g., sai_admin")
                    reg_channel = st.radio("Send Verification OTP via:", ["Mobile Number (SMS)", "Gmail Address"], horizontal=True)
                with r_col2:
                    reg_email = st.text_input("Official Gmail Address *", placeholder="e.g., saixerox@gmail.com")
                    reg_phone = st.text_input("Mobile Number (10 digits) *", placeholder="e.g., 9845012345")
                    p_rate1, p_rate2 = st.columns(2)
                    reg_bw = p_rate1.number_input("B&W Tariff (₹/page)", min_value=0.5, max_value=50.0, value=2.0, step=0.5)
                    reg_color = p_rate2.number_input("Color Tariff (₹/page)", min_value=1.0, max_value=100.0, value=10.0, step=1.0)
                    reg_pass1 = st.text_input("Create Operator Password (min 6 chars) *", type="password")

                if st.button("📨 Generate & Send Verification OTP", type="secondary", use_container_width=True):
                    if not (reg_shop_name and reg_shop_code and reg_username and reg_email and reg_phone and len(reg_pass1) >= 6):
                        st.warning("Please complete all fields and ensure your password is at least 6 characters.")
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
                            st.error("A shop with this Shop Code, Username, Gmail, or Mobile Number already exists.")
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
                            target_dest = reg_phone.strip() if "Mobile" in reg_channel else reg_email.strip()
                            _, status_msg = dispatch_real_otp(
                                target_dest, otp, reg_channel,
                                st.session_state.smtp_email,
                                st.session_state.smtp_app_password,
                                st.session_state.fast2sms_api_key
                            )
                            st.session_state.reg_dispatch_msg = status_msg
                            st.toast(f"📱 Verification OTP: {otp}", icon="💬")

                if st.session_state.reg_otp_code and st.session_state.reg_pending_data:
                    pdata = st.session_state.reg_pending_data
                    target_dest = pdata["phone"] if "Mobile" in pdata["channel"] else pdata["email"]
                    st.markdown(f"""
                    <div class="otp-banner">
                        📲 <strong>OTP Dispatch ({target_dest}):</strong> {st.session_state.reg_dispatch_msg}<br>
                        🔑 <strong>Verification OTP Code: <span style="font-family:'JetBrains Mono',monospace; font-size:1.15rem;">{st.session_state.reg_otp_code}</span></strong>
                    </div>
                    """, unsafe_allow_html=True)

                    v_col1, v_col2 = st.columns([1, 1])
                    entered_reg_otp = v_col1.text_input("Enter 6-Digit Verification OTP", value=st.session_state.reg_otp_code)
                    if v_col2.button("✅ Verify OTP & Launch Shop Portal", type="primary", use_container_width=True):
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
                            st.rerun()
                        else:
                            st.error("Invalid OTP code.")

        with auth_tab3:
            with st.container(border=True):
                st.markdown("#### 🔄 Reset Operator Password")
                recovery_input = st.text_input("Enter Registered Gmail, Mobile Number, or Username")
                if st.button("Send Recovery OTP", type="secondary"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    otp_code = str(secrets.randbelow(900000) + 100000)
                    c.execute("""
                        UPDATE shops SET reset_otp=?
                        WHERE owner_username=? OR LOWER(owner_email)=LOWER(?) OR owner_phone=?
                    """, (otp_code, recovery_input.strip(), recovery_input.strip(), recovery_input.strip()))
                    if c.rowcount > 0:
                        conn.commit()
                        st.session_state.rec_otp_code = otp_code
                        st.session_state.rec_target_user = recovery_input.strip()
                        ch = "Gmail Address" if "@" in recovery_input else "Mobile Number (SMS)"
                        _, msg = dispatch_real_otp(
                            recovery_input.strip(), otp_code, ch,
                            st.session_state.smtp_email,
                            st.session_state.smtp_app_password,
                            st.session_state.fast2sms_api_key
                        )
                        st.session_state.rec_msg = msg
                        st.toast(f"🔑 Recovery OTP: {otp_code}", icon="📩")
                    else:
                        st.error("No registered shop matched that Gmail, Mobile Number, or Username.")
                    conn.close()

                if st.session_state.rec_otp_code:
                    st.markdown(f"""
                    <div class="otp-banner">
                        📩 <strong>Recovery Status:</strong> {st.session_state.get('rec_msg', '')}<br>
                        🔑 <strong>Recovery OTP Code: <code>{st.session_state.rec_otp_code}</code></strong>
                    </div>
                    """, unsafe_allow_html=True)

                rec_otp = st.text_input("Enter 6-Digit Recovery OTP", value=st.session_state.rec_otp_code or "")
                rec_new_pw = st.text_input("Enter New Password (min 6 characters)", type="password")
                if st.button("Verify OTP & Update Password", type="primary"):
                    target_u = st.session_state.rec_target_user or recovery_input.strip()
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("""
                        SELECT shop_id, reset_otp FROM shops
                        WHERE owner_username=? OR LOWER(owner_email)=LOWER(?) OR owner_phone=?
                    """, (target_u, target_u, target_u))
                    r = c.fetchone()
                    if r and r[1] and r[1] == rec_otp.strip() and len(rec_new_pw) >= 6:
                        nhash, nsalt = hash_password(rec_new_pw)
                        c.execute("UPDATE shops SET password_hash=?, salt=?, reset_otp=NULL WHERE shop_id=?", (nhash, nsalt, r[0]))
                        conn.commit()
                        st.session_state.rec_otp_code = None
                        st.success("Password updated! Sign in using the first tab.")
                    else:
                        st.error("Invalid OTP or password shorter than 6 characters.")
                    conn.close()

    else:
        # ==========================================
        # AUTHENTICATED SHOP OWNER WORKSTATION
        # ==========================================
        shop_id = st.session_state.authenticated_shop
        conn = sqlite3.connect(DB_FILE)
        shop_row = pd.read_sql_query("SELECT * FROM shops WHERE shop_id=?", conn, params=(shop_id,)).iloc[0]
        jobs_df = pd.read_sql_query("SELECT * FROM print_jobs WHERE shop_id=? ORDER BY job_id DESC", conn, params=(shop_id,))
        printers_list = json.loads(shop_row["printers_json"])
        conn.close()

        top_c1, top_c2 = st.columns([3.8, 1])
        with top_c1:
            st.markdown(f"""
            <div class="saas-hero" style="margin-bottom:18px; padding:22px 28px;">
                <div class="saas-hero-badge">🟢 LIVE FULFILLMENT WORKSTATION • {shop_id}</div>
                <h1>{shop_row['shop_name']}</h1>
                <p>Operator: <strong>{shop_row['owner_username']}</strong> • Email: {shop_row['owner_email'] or 'N/A'} • Mobile: {shop_row['owner_phone'] or 'N/A'}</p>
            </div>
            """, unsafe_allow_html=True)
        with top_c2:
            st.write("")
            st.write("")
            if st.button("🔒 Sign Out of Workstation", use_container_width=True):
                st.session_state.authenticated_shop = None
                st.rerun()

        pending_cnt = len(jobs_df[jobs_df["status"] == "Pending"])
        printing_cnt = len(jobs_df[jobs_df["status"] == "Printing"])
        ready_cnt = len(jobs_df[jobs_df["status"].isin(["Ready for Pickup", "Completed"])])
        revenue_sum = jobs_df["total_cost"].sum() if not jobs_df.empty else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.markdown(f"""<div class="kpi-card"><div class="kpi-title">🟡 Awaiting Print</div><div class="kpi-value">{pending_cnt}</div><div class="kpi-sub" style="color:#d97706;">In incoming queue</div></div>""", unsafe_allow_html=True)
        k2.markdown(f"""<div class="kpi-card"><div class="kpi-title">🟣 Active on Hardware</div><div class="kpi-value">{printing_cnt}</div><div class="kpi-sub" style="color:#7c3aed;">Dispatched to trays</div></div>""", unsafe_allow_html=True)
        k3.markdown(f"""<div class="kpi-card"><div class="kpi-title">🟢 Ready for Pickup</div><div class="kpi-value">{ready_cnt}</div><div class="kpi-sub" style="color:#059669;">Awaiting collection</div></div>""", unsafe_allow_html=True)
        k4.markdown(f"""<div class="kpi-card"><div class="kpi-title">💰 Session Revenue</div><div class="kpi-value">₹{revenue_sum:.2f}</div><div class="kpi-sub" style="color:#2563eb;">B&W ₹{shop_row['bw_price']:.1f} • Col ₹{shop_row['color_price']:.1f}</div></div>""", unsafe_allow_html=True)

        st.write("")
        owner_tabs = st.tabs([
            "📋 Live Queue & Hardware Print Dialog",
            "📲 Counter QR Code Poster",
            "🖨️ Printer Fleet & Tariffs",
            "🔑 Security Settings"
        ])

        with owner_tabs[0]:
            k_pending, k_printing, k_ready = st.columns([1.4, 1, 1])
            printer_labels = [f"🖨️ {p['name']} [{p['type']} • {p['status']}]" for p in printers_list]

            with k_pending:
                st.markdown(f"""<div class="kanban-col-header kh-pending"><span>🟡 Incoming Print Queue</span><span>{pending_cnt} Jobs</span></div>""", unsafe_allow_html=True)
                for _, job in jobs_df[jobs_df["status"] == "Pending"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"""
                        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                            <div><span class="token-pill">{job['daily_token']}</span> <strong style="font-size:1.05rem; margin-left:6px;">{job['student_name']}</strong></div>
                            <span style="font-family:'JetBrains Mono',monospace; font-weight:800; font-size:1.1rem; color:#0f172a;">₹{job['total_cost']:.2f}</span>
                        </div>
                        <div style="font-size:0.8rem; color:#64748b; margin-bottom:10px;">
                            🕒 {job['time_uploaded']} • 📞 {job['student_phone'] or 'N/A'}
                        </div>
                        <div style="background:#f8fafc; border:1px solid #e2e8f0; padding:8px 12px; border-radius:8px; font-size:0.84rem; margin-bottom:10px;">
                            <strong>{job['color_mode']}</strong> • <strong>{job['pages_count']} A4 pgs/copy</strong> × <strong>{job['copies']} Copies</strong> • {job['n_up']}-up
                        </div>
                        """, unsafe_allow_html=True)

                        if job["processed_pdf"]:
                            st.download_button(
                                f"📥 Download Formatted PDF ({job['pages_count']} pgs)",
                                data=job["processed_pdf"],
                                file_name=job["pdf_filename"],
                                mime="application/pdf",
                                key=f"dl_{job['job_id']}",
                                use_container_width=True
                            )

                        with st.expander("🖨️ Open Hardware Print Dialog", expanded=True):
                            rec_idx = 0 if "Color" in str(job["color_mode"]) else (1 if len(printer_labels) > 1 else 0)
                            selected_printer_label = st.selectbox(
                                "Destination Hardware Printer",
                                options=printer_labels,
                                index=rec_idx,
                                key=f"prt_{job['job_id']}"
                            )

                            pr_c1, pr_c2 = st.columns(2)
                            with pr_c1:
                                dlg_copies = st.number_input("Copies", min_value=1, max_value=200, value=int(job["copies"]), key=f"cp_{job['job_id']}")
                                dlg_custom_pgs = st.text_input("Page Range", value=str(job["page_range"]), key=f"cpg_{job['job_id']}")
                                dlg_sides = st.selectbox(
                                    "Duplex Mode",
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

                            unit_rate = float(shop_row["bw_price"]) if "Black" in str(job["color_mode"]) else float(shop_row["color_price"])
                            updated_cost = int(job["pages_count"]) * int(dlg_copies) * unit_rate
                            st.caption(f"**Calculated Total:** {job['pages_count']} pgs × {dlg_copies} copies × ₹{unit_rate:.2f} = **₹{updated_cost:.2f}**")

                            if st.button("🖨️ Dispatch to Printer Now", key=f"start_{job['job_id']}", type="primary", use_container_width=True):
                                clean_printer = selected_printer_label.replace("🖨️ ", "").split(" [")[0]
                                conn = sqlite3.connect(DB_FILE)
                                c = conn.cursor()
                                now_s = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                c.execute("""
                                    UPDATE print_jobs
                                    SET status='Printing', assigned_printer=?, copies=?, sides=?, orientation=?,
                                        paper_size=?, page_range=?, collated=?, margins=?, scaling=?, total_cost=?, time_started=?
                                    WHERE job_id=?
                                """, (
                                    clean_printer, dlg_copies, dlg_sides, dlg_orient, dlg_size,
                                    dlg_custom_pgs, dlg_collated, dlg_margins, dlg_scaling, updated_cost, now_s, job["job_id"]
                                ))
                                conn.commit()
                                conn.close()
                                st.rerun()

            with k_printing:
                st.markdown(f"""<div class="kanban-col-header kh-printing"><span>🟣 Active on Printers</span><span>{printing_cnt} Jobs</span></div>""", unsafe_allow_html=True)
                for _, job in jobs_df[jobs_df["status"] == "Printing"].iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### <span class='token-pill'>{job['daily_token']}</span> {job['student_name']}", unsafe_allow_html=True)
                        st.success(f"🖨️ **Active Tray:** `{job['assigned_printer']}`")
                        st.write(f"**Job:** {job['pages_count']} pgs × {job['copies']} Copies • {job['sides']} • **₹{job['total_cost']:.2f}**")
                        st.caption(f"Dispatched at: {job['time_started']}")

                        if st.button("✅ Mark Ready for Pickup", key=f"rdy_{job['job_id']}", type="primary", use_container_width=True):
                            conn = sqlite3.connect(DB_FILE)
                            c = conn.cursor()
                            now_c = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            c.execute("UPDATE print_jobs SET status='Ready for Pickup', time_completed=? WHERE job_id=?", (now_c, job["job_id"]))
                            conn.commit()
                            conn.close()
                            st.rerun()

            with k_ready:
                st.markdown(f"""<div class="kanban-col-header kh-ready"><span>🟢 Ready for Pickup</span><span>{ready_cnt} Jobs</span></div>""", unsafe_allow_html=True)
                for _, job in jobs_df[jobs_df["status"].isin(["Ready for Pickup", "Completed"])].iterrows():
                    with st.container(border=True):
                        st.markdown(f"#### <span class='token-pill'>{job['daily_token']}</span> {job['student_name']}", unsafe_allow_html=True)
                        st.write(f"Printed on: `{job['assigned_printer']}` ({job['pages_count']} pgs × {job['copies']} copies)")
                        st.success(f"Collect **₹{job['total_cost']:.2f}** at Counter")
                        st.caption(f"Completed at: {job['time_completed']}")

        with owner_tabs[1]:
            with st.container(border=True):
                st.markdown("#### 📲 Official Shop Counter QR Code Poster")
                local_ip = get_local_wifi_ip()
                qr_col1, qr_col2 = st.columns([1.4, 1])
                with qr_col1:
                    st.markdown("""
                    Display this QR code at your counter. When students scan it:
                    1. Their phone browser opens directly to **your shop's express upload portal**.
                    2. All uploaded PDFs and images route straight to your workstation queue.
                    """)
                    host_base = st.text_input(
                        "Public Cloud URL (or Local Wi-Fi IP):",
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
                        "📥 Download Printable QR Poster (PNG)",
                        data=buf.getvalue(),
                        file_name=f"{shop_id}_QR_Poster.png",
                        mime="image/png",
                        use_container_width=True
                    )

        with owner_tabs[2]:
            p_col1, p_col2 = st.columns(2)
            with p_col1:
                with st.container(border=True):
                    st.markdown("#### 🖨️ Connected Hardware Printers")
                    st.dataframe(pd.DataFrame(printers_list), use_container_width=True, hide_index=True)
                    if st.button("🔍 Auto-Detect Windows System Printers", use_container_width=True):
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
                            st.info("No new local printers detected.")

                    with st.form("add_printer_form"):
                        st.markdown("**Add Hardware Printer to Workstation**")
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
                    st.markdown("#### 💲 Shop Tariff Configuration")
                    new_bw = st.number_input("Black & White Rate (₹/page)", value=float(shop_row["bw_price"]), step=0.5)
                    new_col = st.number_input("Color Rate (₹/page)", value=float(shop_row["color_price"]), step=1.0)
                    if st.button("Update Shop Tariffs", type="primary", use_container_width=True):
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("UPDATE shops SET bw_price=?, color_price=? WHERE shop_id=?", (new_bw, new_col, shop_id))
                        conn.commit()
                        conn.close()
                        st.success("Tariffs updated!")

                    st.divider()
                    st.markdown("#### 🔄 End-of-Day Queue Reset")
                    if st.button("🗑️ Archive Queue & Reset Token Counter to #001", use_container_width=True):
                        conn = sqlite3.connect(DB_FILE)
                        conn.execute("DELETE FROM print_jobs WHERE shop_id=?", (shop_id,))
                        conn.commit()
                        conn.close()
                        st.success("Daily token counter reset to #001!")
                        st.rerun()

        with owner_tabs[3]:
            with st.container(border=True):
                st.markdown("#### 🔑 Update Operator Password")
                old_p = st.text_input("Current Password", type="password")
                new_p1 = st.text_input("New Password", type="password")
                new_p2 = st.text_input("Confirm New Password", type="password")
                if st.button("Save New Password", type="primary"):
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
# ==========================================
elif app_mode == "🛡️ Hidden Super Admin":
    st.markdown("""
    <div class="saas-hero">
        <div class="saas-hero-badge">🛡️ INTERNAL HOST ADMINISTRATION</div>
        <h1>PrintFlow Network Master Control</h1>
        <p>Multi-tenant registry, cryptographic credential audit, and global queue telemetry.</p>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.super_admin_auth:
        u = st.text_input("Host Admin Username")
        p = st.text_input("Host Master Password", type="password")
        if st.button("Unlock Master Console", type="primary"):
            if u == "host_master" and p == "supersecret":
                st.session_state.super_admin_auth = True
                st.rerun()
            else:
                st.error("Invalid credentials.")
    else:
        if st.button("Exit Master Console"):
            st.session_state.super_admin_auth = False
            st.session_state.show_hidden_admin = False
            st.query_params.clear()
            st.rerun()

        conn = sqlite3.connect(DB_FILE)
        all_shops = pd.read_sql_query("SELECT shop_id, shop_name, owner_username, owner_email, owner_phone, password_hash, bw_price, color_price, account_status, created_at FROM shops", conn)
        all_jobs = pd.read_sql_query("SELECT shop_id, daily_token, assigned_printer, pages_count, copies, n_up, total_cost, status, time_uploaded, time_started, time_completed FROM print_jobs", conn)
        conn.close()

        with st.container(border=True):
            st.subheader("🏪 Registered Partner Print Shops")
            st.dataframe(all_shops, use_container_width=True, hide_index=True)

        with st.container(border=True):
            st.subheader("📊 Global Print Queue Telemetry")
            st.dataframe(all_jobs, use_container_width=True, hide_index=True)
            csv_jobs = all_jobs.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Export Global Telemetry CSV", data=csv_jobs, file_name="printflow_telemetry.csv", mime="text/csv")
