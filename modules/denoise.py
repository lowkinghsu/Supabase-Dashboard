import streamlit as st
import os
import subprocess
import tempfile
import shutil
import time
import torch
# 關鍵這一行：務必確保有從 utils 完美導入 CPU_LOCK！
from utils import load_ai_model, log_usage, CPU_LOCK

def process_media(source, atten_lim_db, user_name):
    """處理影音檔案的核心函式，內建智能音量優化與全域排隊鎖"""
    global_start_time = time.time()
    original_name = source.name
    file_size_mb = round(source.size / (1024 * 1024), 2)
        
    name, ext = os.path.splitext(original_name)
    audio_extensions = (".wav", ".mp3", ".m4a", ".aac", ".flac")
    is_audio_only = ext.lower() in audio_extensions
    output_ext = ext if is_audio_only else ".mp4"
    final_output_name = f"{name}_{atten_lim_db}db{output_ext}"

    work_dir = tempfile.mkdtemp(prefix="denoise_")
    input_path = os.path.join(work_dir, original_name)
    output_path = os.path.join(work_dir, final_output_name)
    temp_noisy = os.path.join(work_dir, "temp_noisy.wav")
    temp_clean = os.path.join(work_dir, "temp_clean.wav")

    # 進入全域排隊鎖，確保同時只有一個人在進行高能耗運算
    with CPU_LOCK:
        try:
            with open(input_path, "wb") as f:
                source.seek(0)
                while True:
                    chunk = source.read(4 * 1024 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)

            cmd_extract = [
                "ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "pcm_s16le",
                "-ar", "48000", "-ac", "1", temp_noisy, "-hide_banner", "-loglevel", "error"
            ]
            # 🎯 修正：加上逾時保護，避免損毀檔案讓 ffmpeg 卡死不回應，佔用全域 CPU_LOCK 導致其他人全部卡住
            subprocess.run(cmd_extract, check=True, capture_output=True, timeout=600)

            model, df_state = load_ai_model()
            from df.enhance import load_audio, save_audio, enhance
            
            audio, _ = load_audio(temp_noisy, sr=df_state.sr())
            total_samples = audio.shape[-1]
            chunk_size = df_state.sr() * 10 
            num_chunks = (total_samples + chunk_size - 1) // chunk_size
            
            progress_bar = st.progress(0)
            time_text = st.empty()
            enhanced_chunks = []
            start_time = time.time()

            for i in range(num_chunks):
                start_idx = i * chunk_size
                end_idx = min(start_idx + chunk_size, total_samples)
                
                audio_chunk = audio[:, start_idx:end_idx]
                clean_chunk = enhance(model, df_state, audio_chunk, atten_lim_db=atten_lim_db)
                enhanced_chunks.append(clean_chunk)
                
                current_progress = (i + 1) / num_chunks
                progress_bar.progress(current_progress)
                
                elapsed = time.time() - start_time
                avg_time = elapsed / (i + 1)
                remaining_time = int(avg_time * (num_chunks - (i + 1)))
                time_text.markdown(f"**🤖 AI 運算中:** `已完成 {int(current_progress*100)}%` | `剩餘約 {remaining_time} 秒`")

            enhanced_audio = torch.cat(enhanced_chunks, dim=-1)
            target_db = -1.0
            target_amplitude = 10 ** (target_db / 20)
            max_amplitude = torch.max(torch.abs(enhanced_audio))
            
            if max_amplitude > 0:
                enhanced_audio = enhanced_audio * (target_amplitude / max_amplitude)

            save_audio(temp_clean, enhanced_audio, df_state.sr())

            if is_audio_only:
                # 🎯 修正：原本不管輸出副檔名是什麼，永遠用 libmp3lame(MP3)編碼，
                # 但輸出檔名卻沿用原始副檔名 -> .aac/.flac 檔案會被塞進不接受 MP3 的容器格式，
                # ffmpeg 因此報錯「adts muxer supports only codec aac」。改成依副檔名選對應編碼器。
                audio_codec_args = {
                    ".mp3": ["-c:a", "libmp3lame", "-q:a", "2"],
                    ".aac": ["-c:a", "aac", "-b:a", "192k"],
                    ".m4a": ["-c:a", "aac", "-b:a", "192k"],
                    ".wav": ["-c:a", "pcm_s16le"],
                    ".flac": ["-c:a", "flac"],
                }.get(output_ext.lower(), ["-c:a", "libmp3lame", "-q:a", "2"])
                cmd_merge = [
                    "ffmpeg", "-y", "-i", temp_clean, *audio_codec_args,
                    output_path, "-hide_banner", "-loglevel", "error"
                ]
            else:
                cmd_merge = [
                    "ffmpeg", "-y", "-i", input_path, "-i", temp_clean, "-c:v", "copy", 
                    "-c:a", "aac", "-map", "0:v:0", "-map", "1:a:0", "-shortest", 
                    output_path, "-hide_banner", "-loglevel", "error"
                ]
                
            subprocess.run(cmd_merge, check=True, capture_output=True, timeout=1800)

            st.session_state.processed_file_path = output_path
            st.session_state.processed_file_name = final_output_name
            
            duration_sec = round(time.time() - global_start_time, 1)
            log_usage(user_name, original_name, file_size_mb, f"降噪 ({atten_lim_db}dB)", duration_sec, "成功", "無")
            return True, "處理成功！"

        except subprocess.CalledProcessError as e:
            duration_sec = round(time.time() - global_start_time, 1)
            err_msg = e.stderr.decode("utf-8", errors="ignore") if e.stderr else "無詳細錯誤"
            full_err = f"FFmpeg 錯誤: {err_msg}"
            log_usage(user_name, original_name, file_size_mb, f"降噪 ({atten_lim_db}dB)", duration_sec, "失敗", full_err)
            # 🎯 修正：失敗時原本不會清 work_dir，殘留的上傳檔/中間檔會一直佔用伺服器磁碟，
            # 累積久了會導致其他人上傳/下載也跟著失敗或變慢
            shutil.rmtree(work_dir, ignore_errors=True)
            return False, full_err
        except subprocess.TimeoutExpired:
            duration_sec = round(time.time() - global_start_time, 1)
            full_err = "FFmpeg 處理逾時（檔案可能損毀或過長），已自動中止"
            log_usage(user_name, original_name, file_size_mb, f"降噪 ({atten_lim_db}dB)", duration_sec, "失敗", full_err)
            shutil.rmtree(work_dir, ignore_errors=True)
            return False, full_err
        except Exception as e:
            duration_sec = round(time.time() - global_start_time, 1)
            full_err = f"發生錯誤: {str(e)}"
            log_usage(user_name, original_name, file_size_mb, f"降噪 ({atten_lim_db}dB)", duration_sec, "失敗", full_err)
            shutil.rmtree(work_dir, ignore_errors=True)
            return False, full_err

def render_denoise_page():
    """渲染純影音降噪頁面"""
    st.title("🎙️ ILRDF原語會-族語影音降噪工具")
    st.info("💡 **快速使用**： 1️⃣ 左方上傳檔案 :red[**➔**] 2️⃣ 點擊開始降噪 :red[**➔**] 3️⃣ 右方試聽與下載")
    
    with st.expander("📖 查看詳細操作說明", expanded=False):
        st.markdown("""
        #### 🛠️ 使用步驟
        1. **📥 上傳檔案**：將需要處理的影音檔案拖曳或點選上傳至左下方的「檔案上傳」區塊。
        2. **🎛️ 調整強度 (可選)**：展開最左側的隱藏邊欄，您可以調整「降噪強度」。
           - **最佳建議 30-50dB**：最佳平衡點！能有效去除多數背景雜音。
        3. **🚀 執行降噪**：按下「開始降噪處理」按鈕，系統會顯示目前進度與預估時間。
        4. **💾 預覽與下載**：處理完畢後，右側畫面會出現播放器。
        """)

    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ 降噪參數設定")
        atten_lim = st.slider("降噪強度 (dB)", min_value=20, max_value=100, value=40, step=5)
        st.info("💡 **建議：最佳音質區間為 30-50dB**")
        st.markdown("---")
        
        if st.button("🗑️ 清除所有暫存紀錄", use_container_width=True):
            if st.session_state.processed_file_path:
                try: 
                    shutil.rmtree(os.path.dirname(st.session_state.processed_file_path))
                except Exception: 
                    pass
            st.session_state.processed_file_path = None
            st.session_state.processed_file_name = None
            st.session_state.is_processing = False
            st.session_state.process_target = None
            st.session_state.error_message = None
            if "last_uploaded_file_key" in st.session_state:
                del st.session_state.last_uploaded_file_key
            st.rerun()

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📥 檔案上傳")
        supported = ("mp4", "mov", "avi", "mkv", "wav", "mp3", "m4a", "aac", "flac")
        uploaded_file = st.file_uploader("請選擇要降噪的檔案", type=supported)
        
        # 【修正新增：智慧重設線路】如果使用者拖入新檔案，自動清空舊成果，防止介面卡死空白
        if uploaded_file:
            current_file_key = f"{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.get("last_uploaded_file_key") != current_file_key:
                st.session_state.processed_file_path = None
                st.session_state.processed_file_name = None
                st.session_state.error_message = None
                st.session_state.last_uploaded_file_key = current_file_key
        
        if uploaded_file and not st.session_state.processed_file_path:
            # 【大檔案影片智慧攔截安全線路】
            file_ext = os.path.splitext(uploaded_file.name)[1].lower()
            file_size_mb = round(uploaded_file.size / (1024 * 1024), 2)
            is_video = file_ext in (".mp4", ".mov", ".avi", ".mkv")
            
            # 【調整為 300MB 防爆盾】
            if is_video and uploaded_file.size > 300 * 1024 * 1024:
                st.error(f"⚠️ **影片體積過大 ({file_size_mb} MB)**")
                st.warning("為了保護伺服器不因記憶體溢位（OOM）而死機，本系統限制「超過 300MB 的影片」直接進行 AI 降噪。\n\n💡 **最有效率的解法**：請先切換至左側導覽的 **「✂️ 影音剪輯與轉檔」** 功能，利用 **「🎵 抽取音訊」** 將這部影片的純音檔（MP3）提取出來（通常小於 30MB），再拿純音檔回來這裡降噪。處理完後拿去辨識，速度會快上 5 倍且絕對安全！")
            else:
                if st.button("🚀 開始降噪處理", use_container_width=True):
                    st.session_state.process_target = uploaded_file
                    st.session_state.is_processing = True
                    st.rerun()

        if st.session_state.is_processing:
            with st.status("AI 降噪處理中...", expanded=True) as status:
                st.write("⏳ 正在提取並轉換音訊格式...")
                success, msg = process_media(st.session_state.process_target, atten_lim, st.session_state.current_user)
                st.session_state.is_processing = False
                
                if success: 
                    status.update(label="✅ 處理完成！", state="complete")
                    st.rerun()
                else: 
                    status.update(label="❌ 處理失敗", state="error")
                    st.session_state.error_message = msg
                    st.rerun()

        if st.session_state.error_message:
            st.error(st.session_state.error_message)
            if st.button("🔄 重試"): 
                st.session_state.error_message = None
                st.rerun()

    with col2:
        st.subheader("🎬 成果預覽與下載")
        if st.session_state.processed_file_path and os.path.exists(st.session_state.processed_file_path):
            file_ext = os.path.splitext(st.session_state.processed_file_name)[1].lower()
            with open(st.session_state.processed_file_path, "rb") as f:
                bytes_data = f.read()
                
            if file_ext in (".mp4", ".mov", ".avi", ".mkv"): 
                st.video(bytes_data)
            else: 
                st.audio(bytes_data)
                
            st.download_button(
                label=f"⬇️ 下載降噪後檔案 ({st.session_state.processed_file_name})", 
                data=bytes_data, 
                file_name=st.session_state.processed_file_name, 
                use_container_width=True
            )
            
            if st.button("🔄 繼續處理下一個檔案", use_container_width=True):
                try: 
                    shutil.rmtree(os.path.dirname(st.session_state.processed_file_path))
                except Exception: 
                    pass
                st.session_state.processed_file_path = None
                st.session_state.processed_file_name = None
                st.session_state.error_message = None
                st.session_state.process_target = None
                st.rerun()
        else: 
            st.write("目前尚無處理好的檔案。")