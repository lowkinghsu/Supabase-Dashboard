import streamlit as st
import os
import time
import datetime
import csv
import uuid
import threading
import shutil
import tempfile
import torch
import torchaudio
import requests  # 用於 Supabase API 輕量傳輸
import io        # 用於 Supabase 資料轉為 CSV 記憶體字串

# ================= 🔐 全域安全機制 =================

# 修正：排隊鎖必須是標準的模組級全域變數，才能跨瀏覽器、跨使用者完美排隊！
CPU_LOCK = threading.Lock()

# 🎯 優先從環境變數 (Secrets) 讀取管理員密碼，若未設定則使用備用密碼
# ⚠️ 安全提醒：下方 fallback 密碼只是「本機測試沒設定環境變數時」的保險，
# 正式站部署務必在 HF Secrets 設定 ADMIN_PASSWORD，否則等於後台密碼是公開原始碼裡的這行字。
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "FallbackDefaultPwd123!").strip()
ADMIN_PASSWORD_IS_FALLBACK = "ADMIN_PASSWORD" not in os.environ or not os.environ.get("ADMIN_PASSWORD", "").strip()


# ================= 🧹 暫存檔自動清理與系統健康檢測 =================

# 🎯 本工作站所有處理模組建立暫存目錄/檔案時，一律使用下列專屬前綴，
# 讓自動清理「只清得到我們自己留下的殘留」，絕不誤刪系統或其他程式的暫存檔。
TEMP_PREFIXES = ("denoise_", "ilrdf_asr_", "ilrdf_burn_", "ilrdf_tools_")

_last_cleanup_ts = 0.0
_CLEANUP_INTERVAL_SEC = 600   # 每 10 分鐘最多真正掃描一次磁碟，避免每次網頁互動都掃描拖慢反應
_STALE_AGE_HOURS = 2          # 超過這個時數還留在磁碟上的暫存檔，視為處理失敗留下的殘留，允許清除


def _list_our_temp_entries():
    """列出系統暫存目錄中，屬於本工作站（符合 TEMP_PREFIXES）的所有殘留項目"""
    tmp_root = tempfile.gettempdir()
    entries = []
    try:
        for name in os.listdir(tmp_root):
            if name.startswith(TEMP_PREFIXES):
                entries.append(os.path.join(tmp_root, name))
    except OSError:
        pass
    return entries


def _entry_size_bytes(path):
    try:
        if os.path.isdir(path):
            return sum(
                os.path.getsize(os.path.join(dp, f))
                for dp, _, files in os.walk(path) for f in files
            )
        return os.path.getsize(path)
    except OSError:
        return 0


def cleanup_stale_temp_files(max_age_hours=_STALE_AGE_HOURS):
    """實際執行清理：刪除超過時限的本工作站殘留暫存檔/目錄，回傳 (刪除數量, 釋放MB)"""
    cutoff = time.time() - max_age_hours * 3600
    removed_count = 0
    freed_bytes = 0
    for path in _list_our_temp_entries():
        try:
            if os.path.getmtime(path) >= cutoff:
                continue
            freed_bytes += _entry_size_bytes(path)
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.remove(path)
            removed_count += 1
        except OSError:
            continue
    return removed_count, round(freed_bytes / (1024 * 1024), 2)


def maybe_run_background_cleanup():
    """輕量守門：每 10 分鐘才真正掃描一次磁碟，其餘時間直接跳過，不拖慢正常頁面互動"""
    global _last_cleanup_ts
    now = time.time()
    if now - _last_cleanup_ts < _CLEANUP_INTERVAL_SEC:
        return
    _last_cleanup_ts = now
    try:
        cleanup_stale_temp_files()
    except Exception:
        pass


def get_system_health():
    """供管理員後台「系統健康檢查」使用：回傳磁碟、暫存檔、外部服務連線狀態的即時快照"""
    health = {}

    try:
        total, _used, free = shutil.disk_usage(tempfile.gettempdir())
        health["disk_free_gb"] = round(free / (1024 ** 3), 2)
        health["disk_total_gb"] = round(total / (1024 ** 3), 2)
    except Exception:
        health["disk_free_gb"] = None
        health["disk_total_gb"] = None

    entries = _list_our_temp_entries()
    health["temp_item_count"] = len(entries)
    health["temp_usage_mb"] = round(sum(_entry_size_bytes(p) for p in entries) / (1024 * 1024), 2)

    health["ffmpeg_ok"] = shutil.which("ffmpeg") is not None

    # 外部關鍵服務連線檢測（辨識 ASR / 翻譯 MT），皆設短逾時避免拖住健康檢查本身
    services = {
        "ASR辨識服務 (sapolita.ithuan.tw)": "https://sapolita.ithuan.tw/",
        "MT翻譯服務 (ai-labs.ilrdf.org.tw)": "https://ai-labs.ilrdf.org.tw/kari-seejiq-tnpusu-ai-hmjil/",
    }
    service_status = {}
    for label, url in services.items():
        start = time.time()
        try:
            res = requests.get(url, timeout=6)
            service_status[label] = {
                "ok": res.status_code < 500,
                "status_code": res.status_code,
                "latency_ms": round((time.time() - start) * 1000),
            }
        except Exception as e:
            service_status[label] = {
                "ok": False,
                "status_code": None,
                "latency_ms": None,
                "error": str(e)[:120],
            }
    health["services"] = service_status
    return health

# ================= 📊 系統初始化與視覺 =================

def init_session_state():
    """初始化所有跨分頁需要用到的全域狀態變數"""
    if "session_id" not in st.session_state:
        st.session_state.session_id = uuid.uuid4().hex[:4].upper()
    if "current_user" not in st.session_state:
        st.session_state.current_user = f"訪客_{st.session_state.session_id}"
    if "processed_file_path" not in st.session_state:
        st.session_state.processed_file_path = None
    if "processed_file_name" not in st.session_state:
        st.session_state.processed_file_name = None
    if "is_processing" not in st.session_state:
        st.session_state.is_processing = False
    if "error_message" not in st.session_state:
        st.session_state.error_message = None
    if "process_target" not in st.session_state:
        st.session_state.process_target = None

def inject_css():
    """注入客製化 CSS 進行視覺強化與全域版面防震 (瞞天過海拉伸版 5.1)"""
    st.markdown("""
    <style>
        /* 🎯 【全域版面抗震線路 5.0 - 寬版視覺/置中底層 欺騙線路】 */
        html, body {
            overflow-x: hidden !important; /* 徹底封鎖微幅橫向溢出 */
            overflow-y: auto !important;
        }
        
        /* 💡 核心魔法：強制將置中框架橫向拉伸到 97% 寬度，完美達成寬版效果卻完全不抖動！ */
        section[data-testid="stMainBlockContainer"] {
            max-width: 1300px !important;
            width: 99% !important;
            margin: 0 auto !important;
            padding-top: 2rem !important;
            padding-bottom: 8rem !important; /* 底部安全緩衝墊 */
        }
        
        /* 🎯 關鍵修正：釋放 Streamlit 頂層外殼，確保側邊欄選單按鈕（☰）完美現身 */
        footer { display: none !important; }
        div[data-testid="stHeaderDecoration"] { display: none !important; } /* 只隱藏彩色裝飾線 */
        header[data-testid="stHeader"] { background: transparent !important; } /* 讓背景透明維持美觀 */

        /* 以下維持您原本的精美視覺設定，完全不動 */
        html, body, [class*="css"] {
            font-size: 1.1rem;
        }
        
        /* 1️⃣ 修正：大標題防護區（徹底防止單字掉到第二行） */
        h1 {
            font-size: 2.0rem !important; 
            font-weight: 800 !important;
            color: #1E3A8A;
            margin-bottom: 0.5rem !important;
            text-align: center;            
            white-space: nowrap !important; /* 強制大標題一行到底，絕不折行 */
        }
        
        [data-testid="stSidebar"] h1 {
            font-size: 1.6rem !important;
            white-space: nowrap;
        }
        h2 {
            font-size: 2rem !important;
            font-weight: 700 !important;
            color: #2563EB;
        }
        h3 {
            font-size: 1.5rem !important;
            font-weight: 600 !important;
        }
        [data-testid="stWidgetLabel"] p {
            font-size: 20pt !important;
            font-weight: 700 !important;
            color: #1E3A8A !important;
        }
        [data-testid="stFileUploadDropzone"] div[data-testid="stMarkdownContainer"] p {
            visibility: hidden;
            position: relative;
        }
        [data-testid="stFileUploadDropzone"] div[data-testid="stMarkdownContainer"] p::after {
            content: "請將檔案拖曳至此處";
            visibility: visible;
            position: absolute;
            top: 0; left: 0; width: 100%;
            text-align: center;
            font-size: 1.3rem !important;
            font-weight: 600 !important;
            color: #4B5563 !important;
            display: block;
        }
        [data-testid="stFileUploader"] button {
            color: transparent !important;
            position: relative;
        }
        [data-testid="stFileUploader"] button::after {
            content: "瀏覽檔案";
            visibility: visible;
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            color: #1F2937 !important;
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            white-space: nowrap;
        }
        
        /* 2️⃣ 修正：紅色大按鈕防護區（強迫按鈕文字舒展成單行，且外框容器絕對置中） */
        div.stButton {
            display: flex !important;
            justify-content: center !important; 
            width: 100% !important;
        }
        
        .stButton > button {
            font-size: 1.15rem !important;
            font-weight: 600 !important;
            border-radius: 8px !important;
            padding: 0.6rem 2.0rem !important; 
            transition: all 0.3s ease;
            border: 1px solid #D1D5DB;
            white-space: nowrap !important;   
            width: max-content !important;    
        }
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            border-color: #3B82F6;
        }
        /* 確保 Streamlit 按鈕內部的文字段落標籤也同步受到鐵腕保護 */
        .stButton > button p {
            white-space: nowrap !important;
        }

        /* 3️⃣ 🎯 穩定版：用「隱形標記錨點」抓取 AI 直接翻譯按鈕。
           ⚠️ 舊版用「第幾個元件」硬編位置(nth-child)，只要頁面上其他地方增減一個元件，
           位置就會全部偏移，導致跑版或誤套到別的按鈕——這是這次抓到的真實 bug，已改用不受頁面異動影響的標記寫法。
           標記本身由 modules/asr_mt.py 在按鈕正上方插入 .ilrdf-gemini-btn-marker */
        div[data-testid="element-container"]:has(.ilrdf-gemini-btn-marker) + div[data-testid="element-container"] .stButton button {
            background-color: #FFF5F5 !important; /* 溫柔、具提醒感的消光淡紅色 */
            color: #C53030 !important;            /* 顯眼的深紅色文字 */
            border: 2px solid #FEB2B2 !important; /* 淺紅細邊框襯托 */
            width: 100% !important;               /* 完美滿格 */
        }

        /* 滑鼠懸停時的紅潤微光動態效果 */
        div[data-testid="element-container"]:has(.ilrdf-gemini-btn-marker) + div[data-testid="element-container"] .stButton button:hover {
            background-color: #FED7D7 !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 4px 12px rgba(229, 62, 62, 0.3) !important; /* 紅色高階防護微光 */
        }
    </style>
    """, unsafe_allow_html=True)

# ================= 📊 系統日誌與統計 =================

LOG_FILE = "denoise_usage_log.csv"

def log_usage(user_name, original_name, file_size_mb, action_type, duration_sec, status, error_info):
    """將使用紀錄完整寫入本地 CSV 檔案與 Supabase 雲端永久資料庫"""
    tz_taipei = datetime.timezone(datetime.timedelta(hours=8))
    timestamp = datetime.datetime.now(tz_taipei).strftime("%Y-%m-%d %H:%M:%S")
    
    ext = os.path.splitext(original_name)[1].lower()
    if ext in [".wav", ".mp3", ".m4a", ".aac", ".flac"]:
        file_type = "音檔"
    elif ext in [".mp4", ".mov", ".avi", ".mkv"]:
        file_type = "影片"
    else:
        file_type = "文本"
        
    sub_url = os.environ.get("SUPABASE_URL", "").strip()
    sub_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    if sub_url and sub_key:
        try:
            headers = {
                "apikey": sub_key,
                "Authorization": f"Bearer {sub_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            payload = {
                "timestamp": timestamp, "user_name": user_name, "original_name": original_name,
                "file_type": file_type, "file_size_mb": float(file_size_mb), "action_type": action_type,
                "duration_sec": float(duration_sec), "status": status, "error_info": error_info
            }
            res = requests.post(f"{sub_url}/rest/v1/denoise_usage_log", headers=headers, json=payload, timeout=4)
            if res.status_code not in [200, 201]:
                st.error(f"💥 Supabase 紀錄失敗: {res.status_code}")
        except Exception:
            pass

    try:
        file_exists = os.path.isfile(LOG_FILE)
        with open(LOG_FILE, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["處理時間", "使用者姓名", "原始檔名", "檔案類型", "檔案大小(MB)", "執行動作/參數", "處理耗時(秒)", "處理狀態", "錯誤詳細資訊"])
            writer.writerow([timestamp, user_name, original_name, file_type, file_size_mb, action_type, duration_sec, status, error_info])
    except Exception:
        pass


def get_usage_data():
    """讀取總處理資料，供管理員下載 (優先從 Supabase 撈取全量數據，斷線時降級讀取本地暫存)"""
    sub_url = os.environ.get("SUPABASE_URL", "").strip()
    sub_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    
    if sub_url and sub_key:
        try:
            headers = {"apikey": sub_key, "Authorization": f"Bearer {sub_key}"}
            res = requests.get(f"{sub_url}/rest/v1/denoise_usage_log?order=id.asc", headers=headers, timeout=5)
            if res.status_code == 200:
                rows = res.json()
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["處理時間", "使用者姓名", "原始檔名", "檔案類型", "檔案大小(MB)", "執行動作/參數", "處理耗時(秒)", "處理狀態", "錯誤詳細資訊"])
                for r in rows:
                    writer.writerow([r['timestamp'], r['user_name'], r['original_name'], r['file_type'], r['file_size_mb'], r['action_type'], r['duration_sec'], r['status'], r['error_info']])
                output.seek(0)
                return output.readlines()
        except Exception:
            pass

    try:
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8-sig") as f:
                return f.readlines()
        return []
    except Exception:
        return []


# ================= 🔥 問題回報雲端對接模組 (除錯改造版) =================

def submit_bug_report(user_name, page_name, issue_type, description):
    """將使用者填寫的問題與意見即時推送至 Supabase 雲端資料庫 (加裝錯誤解剖器)"""
    tz_taipei = datetime.timezone(datetime.timedelta(hours=8))
    timestamp = datetime.datetime.now(tz_taipei).strftime("%Y-%m-%d %H:%M:%S")
    
    sub_url = os.environ.get("SUPABASE_URL", "").strip()
    sub_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    
    if not user_name.strip():
        user_name = "匿名使用者"
        
    if sub_url and sub_key:
        try:
            headers = {
                "apikey": sub_key,
                "Authorization": f"Bearer {sub_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            payload = {
                "timestamp": timestamp,
                "user_name": user_name,
                "page_name": page_name,
                "issue_type": issue_type,
                "description": description
            }
            res = requests.post(f"{sub_url}/rest/v1/system_bug_reports", headers=headers, json=payload, timeout=5)
            
            # 【關鍵除錯改造】如果失敗，立刻在畫面上大聲講出原因！
            if res.status_code not in [200, 201]:
                st.error(f"💥 Supabase 拒絕接收問題回報！代碼: {res.status_code} | 原因: {res.text}")
                return False
            return True
        except Exception as e:
            st.error(f"📡 連線至回報資料庫發生異常: {str(e)}")
            return False
    return False


def get_bug_reports_data():
    """供管理員一鍵撈取並打包成標準 CSV 格式的問題回報清單"""
    sub_url = os.environ.get("SUPABASE_URL", "").strip()
    sub_key = os.environ.get("SUPABASE_ANON_KEY", "").strip()
    
    if sub_url and sub_key:
        try:
            headers = {"apikey": sub_key, "Authorization": f"Bearer {sub_key}"}
            res = requests.get(f"{sub_url}/rest/v1/system_bug_reports?order=id.asc", headers=headers, timeout=5)
            if res.status_code == 200:
                rows = res.json()
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(["回報時間", "通報人姓名/單位", "發生功能頁面", "問題分類", "詳細狀況描述"])
                for r in rows:
                    writer.writerow([r['timestamp'], r['user_name'], r['page_name'], r['issue_type'], r['description']])
                output.seek(0)
                return output.readlines()
        except Exception:
            pass
    return []


# ================= 🧠 AI 模型快取與補丁 =================

def apply_patches():
    """修正 DeepFilterNet 內部尋找 Git 的 bug"""
    try:
        import df.utils
        df.utils.get_git_root = lambda: "."
        df.utils.get_commit_hash = lambda: "web_v1"
        df.utils.get_branch_name = lambda: "master"
    except ImportError:
        pass


# 💡 修正後：把這個開機魔王裝飾器註解掉，不讓它在開機時強制霸佔 CPU！
# @st.cache_resource(show_spinner="正在將 AI 降噪模型載入伺服器記憶體 (僅需一次)...")
def load_ai_model():
    """全域緩存 AI 模型，改用延遲加載模式，完美避開開機卡死"""
    # 💡 檢查 session_state 裡面有沒有現成的模型，有就直接拿，達成完美快取！
    if "cached_model" in st.session_state and "cached_df_state" in st.session_state:
        return st.session_state.cached_model, st.session_state.cached_df_state
        
    try:
        apply_patches()
        try:
            torchaudio.set_audio_backend("soundfile")
        except Exception:
            pass
            
        from df.enhance import init_df
        # 只有在真正需要時，才在大眾看不到的後台靜靜載入大模型
        with st.spinner("⏳ 正在啟動後台 AI 降噪核心，首次載入需時 1-2 分鐘，請稍候..."):
            model, df_state, _ = init_df(model_base_dir=None)
            
        # 塞進全域快取快遞箱中
        st.session_state.cached_model = model
        st.session_state.cached_df_state = df_state
        return model, df_state
    except ImportError as e:
        raise RuntimeError(f"套件載入失敗！錯誤訊息: {str(e)}")
    except Exception as e:
        raise RuntimeError(f"模型初始化發生錯誤: {str(e)}")