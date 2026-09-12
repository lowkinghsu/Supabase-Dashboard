import streamlit as st
import os
import subprocess
import tempfile
import shutil
import time
import datetime
import re
import math  # 用於時間軸精確切分計算
# 引入先前修正的全域排隊鎖與日誌工具
from utils import CPU_LOCK, log_usage

def split_long_srt_blocks(srt_string, max_duration=6.0):
    """
    【防禦性智慧切片核心演算法】
    自動解析 SRT 字幕，若某段時間軸跨度超過 max_duration 秒，
    則自動將其等分切割，並按比例重新分配時間戮記與族語單字。
    """
    def srt_time_to_seconds(t_str):
        parts = t_str.strip().replace('.', ',').split(':')
        h, m = parts[0], parts[1]
        s, ms = parts[2].split(',')
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0

    def seconds_to_srt_time(secs):
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        ms = int(round((secs - math.floor(secs)) * 1000))
        if ms >= 1000:
            s += 1
            ms -= 1000
        if s >= 60:
            m += 1
            s -= 60
        if m >= 60:
            h += 1
            m -= 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    # 統一換行符號並按標準雙換行切分區塊
    srt_string = srt_string.replace('\r\n', '\n').strip()
    blocks = srt_string.split('\n\n')
    new_blocks = []
    global_idx = 1

    for block in blocks:
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        if len(lines) < 3:
            continue
        
        timecode = lines[1]
        text = " ".join(lines[2:])  # 確保族語內文拉回單行以利精準字串切分
        
        # 驗證時間軸格式
        match = re.match(r'(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)', timecode)
        if not match:
            new_blocks.append(f"{global_idx}\n{timecode}\n{text}")
            global_idx += 1
            continue
            
        start_str, end_str = match.groups()
        try:
            start_sec = srt_time_to_seconds(start_str)
            end_sec = srt_time_to_seconds(end_str)
        except Exception:
            new_blocks.append(f"{global_idx}\n{timecode}\n{text}")
            global_idx += 1
            continue
            
        duration = end_sec - start_sec
        
        # 檢查是否超過黃金秒數上限
        if duration <= max_duration:
            new_blocks.append(f"{global_idx}\n{start_str} --> {end_str}\n{text}")
            global_idx += 1
        else:
            # 啟動智慧切片手術
            n_parts = math.ceil(duration / max_duration)
            words = text.split()
            
            if len(words) == 0:
                for p in range(n_parts):
                    p_start = start_sec + (duration / n_parts) * p
                    p_end = start_sec + (duration / n_parts) * (p + 1)
                    new_blocks.append(f"{global_idx}\n{seconds_to_srt_time(p_start)} --> {seconds_to_srt_time(p_end)}\n")
                    global_idx += 1
            else:
                # 將族語單字群等分均攤至各小區間
                words_per_part = math.ceil(len(words) / n_parts)
                for p in range(n_parts):
                    p_start = start_sec + (duration / n_parts) * p
                    p_end = start_sec + (duration / n_parts) * (p + 1)
                    
                    part_words = words[p * words_per_part : (p + 1) * words_per_part]
                    if not part_words:
                        continue
                    part_text = " ".join(part_words)
                    
                    new_blocks.append(f"{global_idx}\n{seconds_to_srt_time(p_start)} --> {seconds_to_srt_time(p_end)}\n{part_text}")
                    global_idx += 1
                        
    return "\n\n".join(new_blocks)

def render_asr_mt_page():
    """渲染族語辨識與翻譯頁面"""
    st.title("📝 族語辨識與翻譯 (SRT 字幕版)")
    st.info("💡 **工作流**： 1️⃣ 上傳影音生成 SRT 字幕 :red[**➔**] 2️⃣ 一鍵生成雙語字幕檔 :red[**➔**] 3️⃣ 燒錄字幕進影片")
    
    DIALECT_MAP = {
        "阿美語 (Amis)": "formosan_ami", "泰雅語 (Atayal)": "formosan_tay", "排灣語 (Paiwan)": "formosan_pwn",
        "布農語 (Bunun)": "formosan_bnn", "卑南語 (Puyuma)": "formosan_pyu", "魯凱語 (Rukai)": "formosan_dru",
        "鄒語 (Cou)": "formosan_tsu", "賽夏語 (SaySiyat)": "formosan_sai", "達悟語 (Tao)": "formosan_tao",
        "邵語 (Thau)": "formosan_tha", "噶瑪蘭語 (kebalan)": "formosan_ckv", "太魯閣語 (Truku)": "formosan_trv",
        "撒奇萊雅語 (Sakizaya)": "formosan_szy", "賽德克語 (Seediq)": "formosan_sed", "拉阿魯哇語 (Hla'alua)": "formosan_hlv",
        "卡那卡那富語 (Kanakanavu)": "formosan_xnb"
    }

    MT_ETHNICITY_MAP = {
        "阿美語 (Amis)": "阿美", "泰雅語 (Atayal)": "泰雅", "排灣語 (Paiwan)": "排灣", "布農語 (Bunun)": "布農",
        "卑南語 (Puyuma)": "卑南", "魯凱語 (Rukai)": "魯凱", "鄒語 (Cou)": "鄒", "賽夏語 (SaySiyat)": "賽夏",
        "達悟語 (Tao)": "雅美", "邵語 (Thau)": "邵", "噶瑪蘭語 (kebalan)": "噶瑪蘭", "太魯閣語 (Truku)": "太魯閣",
        "撒奇萊雅語 (Sakizaya)": "撒奇萊雅", "賽德克語 (Seediq)": "賽德克", "拉阿魯哇語 (Hla'alua)": "拉阿魯哇",
        "卡那卡那富語 (Kanakanavu)": "卡那卡那富"
    }
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("1️⃣ 語音辨識 (生成 SRT)")
        selected_lang = st.selectbox("請選擇檔案的族語語別：", list(DIALECT_MAP.keys()))
        # 🎯 修正：原本漏了 aac（降噪頁面、log_usage 都早就把 aac 當成合法音檔），
        # 造成使用者在這裡連選都選不到 .aac 檔案
        asr_file = st.file_uploader("請上傳要辨識的影音檔", type=["wav", "mp3", "m4a", "aac", "flac", "mp4", "mov", "avi"])
        st.caption("📶 大型檔案上傳建議使用 Wi-Fi，行動網路(4G/5G)訊號不穩時容易上傳失敗中斷。")
        
        if asr_file:
            file_ext = os.path.splitext(asr_file.name)[1].lower()
            file_size_mb = round(asr_file.size / (1024 * 1024), 2)
            
            st.markdown("**👀 檔案預覽：**")
            if file_ext in [".mp4", ".mov", ".avi"]:
                st.video(asr_file)
            else:
                st.audio(asr_file)
                
            if st.button("🚀 開始生成 SRT 字幕", use_container_width=True):
                if "mt_result" in st.session_state:
                    del st.session_state.mt_result
                
                with tempfile.NamedTemporaryFile(delete=False, prefix="ilrdf_asr_", suffix=file_ext) as tmp_file:
                    asr_file.seek(0)
                    while True:
                        chunk = asr_file.read(4 * 1024 * 1024)
                        if not chunk:
                            break
                        tmp_file.write(chunk)
                    input_path = tmp_file.name

                try:
                    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", input_path]
                    probe_result = subprocess.run(probe_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                    media_duration = float(probe_result.stdout.strip())
                    est_seconds = max(5, int(media_duration * 0.3) + 5)
                    est_str = f"{est_seconds // 60} 分 {est_seconds % 60} 秒" if est_seconds > 60 else f"{est_seconds} 秒"
                    duration_display = f"{int(media_duration // 60)} 分 {int(media_duration % 60)} 秒" if media_duration > 60 else f"{int(media_duration)} 秒"
                except Exception:
                    duration_display = "未知"
                    est_str = "約 1~2 分鐘"

                st.warning(f"⏳ **系統運算中...**\n偵測到影音長度為 **{duration_display}**，預估處理時間： **{est_str}**。")
                
                with st.status("AI 語音辨識中，請耐心等候...", expanded=True) as status:
                    start_time = time.time()
                    try:
                        upload_path = input_path
                        if file_ext in [".mp4", ".mov", ".avi"]:
                            st.write("✂️ 正在抽取音訊以加速傳輸...")
                            audio_path = input_path.replace(file_ext, ".wav")
                            subprocess.run(["ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", audio_path, "-loglevel", "error"], check=True, timeout=600)
                            upload_path = audio_path

                        st.write("🔗 正在連線至 ILRDF SRT 生成模型...")
                        from gradio_client import Client, handle_file
                        # 🎯 修正：明確設定連線逾時（180 秒），避免對方服務沒回應時，
                        # 使用者的分頁無限期卡死轉圈圈（這是「辨識按鈕沒反應」的常見成因之一）
                        client = Client("https://sapolita.ithuan.tw/", httpx_kwargs={"timeout": 180})
                        raw_result = client.predict(
                            audio={"video": handle_file(upload_path)},
                            api_name="/generate_srt"
                        )
                        
                        cleaned_lines = []
                        for line in raw_result.split('\n'):
                            if not re.match(r'^\d+$', line.strip()) and not '-->' in line and line.strip() != '':
                                line = re.sub(r'^\s*族語[：:]\s*', '', line)
                                line = re.sub(r'\s*華語[：:].*$', '', line)
                            cleaned_lines.append(line)
                        
                        initial_srt_output = '\n'.join(cleaned_lines)
                        
                        # 【智慧切片線路接入點】將模型吐出的長時碼強制重編碼，分割為 6 秒內的黃金長度
                        st.session_state.asr_result = split_long_srt_blocks(initial_srt_output, max_duration=6.0)
                        
                        try:
                            os.remove(input_path)
                            if upload_path != input_path:
                                os.remove(upload_path)
                        except Exception:
                            pass
                        
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, asr_file.name, file_size_mb, f"ASR辨識 ({selected_lang})", duration, "成功", "無")
                        status.update(label="✅ SRT 字幕生成完成！", state="complete")
                    except Exception as e:
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, asr_file.name, file_size_mb, f"ASR辨識 ({selected_lang})", duration, "失敗", str(e))
                        status.update(label="❌ 辨識失敗", state="error")
                        st.error(f"API 呼叫發生錯誤：{str(e)}")
                        # 🎯 修正：失敗時原本完全沒有清暫存檔，長期會把伺服器磁碟塞滿導致上傳/下載全部變慢或失敗，
                        # 現在無論成功或失敗都確保清乾淨
                        for leftover in (input_path, upload_path):
                            try:
                                if leftover and os.path.exists(leftover):
                                    os.remove(leftover)
                            except Exception:
                                pass
    
    with col2:
        st.subheader("📝 字幕編輯與翻譯")
        if "asr_result" in st.session_state:
            # 💡 【新增：版本防禦機制】初始化輸入框版本號
            if "asr_widget_version" not in st.session_state:
                st.session_state.asr_widget_version = 0
                
            # 🎯 關鍵修正點（第 224 行）：這一行前面請精確保持「12個標準空格」！
            edited_asr_text = st.text_area(
                "✏️ 原始 SRT 字幕 (可直接修改)：", 
                value=st.session_state.asr_result, 
                height=250,
                key=f"asr_text_area_{st.session_state.asr_widget_version}"
            )
            # 💡 【智慧同步】同仁手動打完字點擊空白處，即時將內容洗回全域變數中
            st.session_state.asr_result = edited_asr_text
            
            # 🎯 【修正對齊】整套 Gemini 邏輯精確對齊 12 個空格
            st.markdown("**✨ Gemini AI 進階處理**")

            # 🎯 新增：改成「使用時才輸入」模式。系統後台若有設定好且驗證通過的金鑰會自動代入使用，
            # 但也讓每個人可以在這裡直接貼上自己的 Gemini API Key（只存在您這次瀏覽器 session 記憶體中，
            # 不會被記錄、寫入日誌或傳到後台資料庫）。這樣即使後台共用金鑰失效或額度用完，
            # 同仁仍可用自己的金鑰繼續使用這個功能，不用等後台改設定。
            manual_gemini_key = st.text_input(
                "🔑 Gemini API Key（留空則自動使用系統後台金鑰；若後台金鑰失效，請在此貼上您自己的金鑰）",
                type="password",
                key="manual_gemini_key_input",
                placeholder="AIza..."
            )
            system_key_usable = bool(st.session_state.get("gemini_key")) and st.session_state.get("gemini_key_validated")
            active_gemini_key = manual_gemini_key.strip() or (st.session_state.get("gemini_key", "") if system_key_usable else "")

            if manual_gemini_key.strip():
                st.caption("✅ 將使用您剛輸入的金鑰（僅本次瀏覽器 session 使用）")
            elif not active_gemini_key:
                st.caption("💡 系統後台未偵測到有效金鑰，請在上方輸入您自己的 Gemini API Key 才能使用此功能。")

            # 💡 【防爆機制 1】初始化安全狀態鎖與冷卻機制
            if "gemini_processing" not in st.session_state:
                st.session_state.gemini_processing = False

            # 💡 【防爆機制 2】執行期間將按鈕禁用（Disabled），防止人類肉體連擊
            # 🎯 隱形標記錨點：讓 utils.py 的 CSS 能穩定抓到「這顆」按鈕上紅色警示樣式，
            # 不再依賴會被頁面改版打亂的第幾個元件計數（對應 utils.py 的 .ilrdf-gemini-btn-marker 規則）
            st.markdown('<span class="ilrdf-gemini-btn-marker"></span>', unsafe_allow_html=True)
            if st.button(
                "🚀 AI直接翻譯雙語字幕",
                key="gemini_flash_btn",
                use_container_width=True,
                disabled=st.session_state.gemini_processing or not active_gemini_key
            ):
                st.session_state.gemini_processing = True
                st.rerun()

            # 💡 【防爆機制 3】真正的 API 執行外殼，由 Session 狀態控制
            if st.session_state.gemini_processing:
                with st.spinner("LLM AI正在深度雙語翻譯..."):
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=active_gemini_key)

                        # 🎯 2026-09 更新：改用已 GA（正式生產版）的 Gemini 3.8 Flash，較舊版 3.5 Flash 更新更穩定
                        model = genai.GenerativeModel('gemini-3.8-flash')

                        prompt = (
                            "請讀取以下的單語 SRT 字幕檔。保留原本的序號與時間軸，保留原本族語文字作為第二行，在下方加上翻譯的繁體中文，每一段字幕留一空白行。"
                            "請直接回傳純文字的完整雙語 SRT 內容，絕對不要用任何 markdown 程式碼區塊（如 ``` ）包覆。\n\n"
                            f"原始 SRT：\n{edited_asr_text}"
                        )
                        response = model.generate_content(prompt)
                        reply_text = response.text.strip()

                        if reply_text.startswith("```"):
                            # 🎯 修正：原正規表達式字元類別寫成 [a-zA-Oa-z]（誤植，大寫只到 O），
                            # 導致語言標籤含大寫 P~Z（例如 ```SRT）時剝不掉 code fence，字幕檔會多出雜訊行
                            reply_text = re.sub(r'^```[a-zA-Z]*\n', '', reply_text)
                            reply_text = re.sub(r'\n```$', '', reply_text)
                            reply_text = reply_text.strip()

                        st.session_state.mt_result = reply_text
                    except Exception as e:
                        st.error(f"API 發生錯誤（請檢查模型名稱或金鑰）：{str(e)}")
                    finally:
                        # 💡 【防爆機制 4】無論成功或失敗，最後一定要解鎖，並強制刷新頁面釋放按鈕
                        st.session_state.gemini_processing = False
                        st.rerun()

            # 🎯 【修正對齊】以下大區塊脫離 Gemini 判斷，回歸大隊伍垂直切齊（12 個空格）
            st.markdown("---")
            st.subheader("2️⃣ 機器翻譯 (生成雙語 SRT)")
            
            if st.button("🇹🇼 逐句翻譯並生成雙語字幕", use_container_width=True):
                with st.status("AI 機器翻譯中...", expanded=True) as mt_status:
                    start_time = time.time()
                    try:
                        ethnicity_name = MT_ETHNICITY_MAP[selected_lang]
                        from gradio_client import Client
                        # 🎯 修正：同樣加上逾時設定，避免翻譯服務沒回應時逐句卡死整個流程
                        mt_client = Client("https://ai-labs.ilrdf.org.tw/kari-seejiq-tnpusu-ai-hmjil/", httpx_kwargs={"timeout": 60})
                        lang_code_response = mt_client.predict(ethnicity=ethnicity_name, api_name="/lambda")
                        actual_lang_code = lang_code_response['value'] if isinstance(lang_code_response, dict) and 'value' in lang_code_response else lang_code_response
                            
                        blocks = st.session_state.asr_result.strip().split('\n\n')
                        bilingual_srt_lines = []
                        half_to_full = str.maketrans({',': '，', '.': '。', '?': '？', '!': '！', ':': '：', ';': '；', '(': '（', ')': '）'})
                        progress_bar = st.progress(0)
                        
                        for i, block in enumerate(blocks):
                            lines = block.strip().split('\n')
                            if len(lines) >= 3:
                                idx = lines[0]
                                timecode = lines[1]
                                source_text = " ".join(lines[2:])
                                
                                try:
                                    trans_result = mt_client.predict(text=source_text, src_lang=actual_lang_code, tgt_lang="zho_Hant", api_name="/translate")
                                    trans_result = trans_result.translate(half_to_full)
                                except Exception:
                                    trans_result = "[翻譯失敗]"
                                
                                bilingual_srt_lines.extend([idx, timecode, source_text, trans_result, ""])
                            progress_bar.progress((i + 1) / len(blocks))
                        
                        st.session_state.mt_result = "\n".join(bilingual_srt_lines)
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, "SRT文本", 0, f"MT翻譯 ({selected_lang})", duration, "成功", "無")
                        mt_status.update(label="✅ 雙語字幕生成完成！", state="complete")
                    except Exception as e:
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, "SRT文本", 0, f"MT翻譯 ({selected_lang})", duration, "失敗", str(e))
                        mt_status.update(label="❌ 翻譯失敗", state="error")
                        st.error(f"翻譯過程發生錯誤：{str(e)}")
            
            # === ✍️ 精確替換為以下這段（加裝 edited_mt_text 同步線路） ===
            if "mt_result" in st.session_state:
                st.success("✨ 雙語字幕生成成功！")
                
                # 🎯 修正：用變數捕捉您手動修改的成果，並即時洗回系統記憶體中
                edited_mt_text = st.text_area("🇹🇼 雙語 SRT 預覽：", value=st.session_state.mt_result, height=250)
                st.session_state.mt_result = edited_mt_text
                
                st.download_button(
                    label="📥 下載雙語字幕檔 (.srt)",
                    data=st.session_state.mt_result, # 這時候下載按鈕拿到的就是熱騰騰修改後的文字了！
                    file_name=f"族語雙語字幕_{datetime.date.today()}.srt",
                    mime="text/plain",
                    use_container_width=True
                )
                
                if asr_file:
                    current_file_ext = os.path.splitext(asr_file.name)[1].lower()
                    if current_file_ext in [".mp4", ".mov", ".avi"]:
                        st.markdown("---")
                        st.subheader("🎬 影片字幕直接嵌入影片")
                        
                        if st.button("🔥 開始燒錄字幕", use_container_width=True):
                            with st.status("正在將字幕燒錄至影片中...", expanded=True) as burn_status:
                                start_time = time.time()
                                with CPU_LOCK:
                                    work_dir = None
                                    try:
                                        work_dir = tempfile.mkdtemp(prefix="ilrdf_burn_")
                                        video_path = os.path.join(work_dir, "input_video" + current_file_ext)
                                        srt_path = os.path.join(work_dir, "subs.srt")
                                        output_path = os.path.join(work_dir, "output_hardsub.mp4")
                                        
                                        with open(video_path, "wb") as f:
                                            asr_file.seek(0)
                                            while True:
                                                chunk = asr_file.read(4 * 1024 * 1024)
                                                if not chunk: break
                                                f.write(chunk)
                                                
                                        with open(srt_path, "w", encoding="utf-8") as f:
                                            f.write(st.session_state.mt_result)
                                            
                                        srt_path_ff = srt_path.replace('\\', '/').replace(':', '\\:')
                                        st.write("⚙️ 正在進行影像重新編碼與字幕渲染 (採用 Noto Sans CJK 字型)...")
                                        
                                        cmd = [
                                            "ffmpeg", "-y", "-i", video_path,
                                            "-vf", f"subtitles='{srt_path_ff}':force_style='Fontname=Noto Sans CJK TC,FontSize=20,MarginV=15'",
                                            "-c:a", "copy", output_path, "-loglevel", "error"
                                        ]
                                        # 🎯 修正：加上逾時保護，避免損毀影片讓 ffmpeg 卡死不回應時佔用全域 CPU_LOCK 導致其他人全部卡住
                                        subprocess.run(cmd, check=True, timeout=3600)
                                        
                                        with open(output_path, "rb") as f:
                                            out_video_bytes = f.read()
                                            
                                        duration = round(time.time() - start_time, 1)
                                        log_usage(st.session_state.current_user, asr_file.name, round(asr_file.size/(1024*1024),2), "字幕燒錄", duration, "成功", "無")
                                        burn_status.update(label="✅ 字幕燒錄完成！", state="complete")
                                        st.success("🎉 影片處理完畢！")
                                        
                                        st.download_button(
                                            label="⬇️ 下載含字幕影片 (.mp4)",
                                            data=out_video_bytes,
                                            file_name=f"族語雙語影片_{datetime.date.today()}.mp4",
                                            mime="video/mp4",
                                            use_container_width=True
                                        )
                                        shutil.rmtree(work_dir, ignore_errors=True)
                                    except Exception as e:
                                        duration = round(time.time() - start_time, 1)
                                        log_usage(st.session_state.current_user, asr_file.name, round(asr_file.size/(1024*1024),2), "字幕燒錄", duration, "失敗", str(e))
                                        burn_status.update(label="❌ 燒錄失敗", state="error")
                                        st.error(f"FFmpeg 處理發生錯誤：{str(e)}")
                                        # 🎯 修正：失敗時原本不會清 work_dir，殘留的影片檔會一直佔用伺服器磁碟
                                        if work_dir:
                                            shutil.rmtree(work_dir, ignore_errors=True)
        else:
            st.info("👈 請先在左側上傳影音檔並執行「生成 SRT 字幕」。")