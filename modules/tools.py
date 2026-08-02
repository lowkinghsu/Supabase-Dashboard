import streamlit as st
import os
import subprocess
import tempfile
import shutil
import time
from utils import log_usage

def render_tools_page():
    """渲染影音剪輯與轉檔小工具頁面"""
    st.title("✂️ 影音剪輯與轉檔小工具")
    st.info("💡 **工作站輔助工具**：這裡提供輕量化的本地端處理工具，幫助您在進行 AI 降噪或辨識前，先解決檔案過大或過長的問題！")

    tab1, tab2, tab3, tab4 = st.tabs(["🎵 抽取音訊", "✂️ 片段剪輯", "🗜️ 格式轉換", "🔗 影音合併"])

    # ----------------- 子工具 1：抽取音訊 -----------------
    with tab1:
        st.subheader("🎵 影片轉純音檔 (大幅縮小體積)")
        ext_file = st.file_uploader("請上傳影片檔", type=["mp4", "mov", "avi", "mkv"], key="ext_uploader")
        if ext_file:
            if st.button("🚀 一鍵抽取音訊", use_container_width=True):
                with st.status("處理中...", expanded=True) as status:
                    start_time = time.time()
                    try:
                        work_dir = tempfile.mkdtemp()
                        input_path = os.path.join(work_dir, ext_file.name)
                        output_name = os.path.splitext(ext_file.name)[0] + "_audio.mp3"
                        output_path = os.path.join(work_dir, output_name)
                        
                        with open(input_path, "wb") as f:
                            ext_file.seek(0)
                            while True:
                                chunk = ext_file.read(4 * 1024 * 1024)
                                if not chunk: break
                                f.write(chunk)
                            
                        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-vn", "-c:a", "libmp3lame", "-q:a", "2", output_path, "-loglevel", "error"], check=True)
                        with open(output_path, "rb") as f:
                            out_bytes = f.read()
                            
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, ext_file.name, round(ext_file.size/(1024*1024),2), "抽取音訊", duration, "成功", "無")
                        status.update(label="✅ 抽取成功！", state="complete")
                        st.download_button("⬇️ 下載純音檔 (MP3)", data=out_bytes, file_name=output_name, mime="audio/mpeg", use_container_width=True)
                        shutil.rmtree(work_dir, ignore_errors=True)
                    except Exception as e:
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, ext_file.name, round(ext_file.size/(1024*1024),2), "抽取音訊", duration, "失敗", str(e))
                        status.update(label="❌ 處理失敗", state="error")
                        st.error(f"發生錯誤：{str(e)}")

    # ----------------- 子工具 2：片段剪輯 -----------------
    with tab2:
        st.subheader("✂️ 片段剪輯 (無損裁切)")
        trim_file = st.file_uploader("請上傳影音檔", type=["mp4", "mov", "avi", "wav", "mp3", "m4a"], key="trim_uploader")
        if trim_file:
            col_t1, col_t2 = st.columns(2)
            with col_t1: start_time_str = st.text_input("開始時間 (格式 HH:MM:SS)", value="00:00:00")
            with col_t2: end_time_str = st.text_input("結束時間 (格式 HH:MM:SS)", value="00:01:00")
                
            if st.button("✂️ 開始剪輯", use_container_width=True):
                with st.status("處理中...", expanded=True) as status:
                    start_time = time.time()
                    try:
                        work_dir = tempfile.mkdtemp()
                        input_path = os.path.join(work_dir, trim_file.name)
                        ext = os.path.splitext(trim_file.name)[1]
                        output_name = os.path.splitext(trim_file.name)[0] + "_cut" + ext
                        output_path = os.path.join(work_dir, output_name)
                        
                        with open(input_path, "wb") as f:
                            trim_file.seek(0)
                            while True:
                                chunk = trim_file.read(4 * 1024 * 1024)
                                if not chunk: break
                                f.write(chunk)
                            
                        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-ss", start_time_str, "-to", end_time_str, "-c", "copy", output_path, "-loglevel", "error"], check=True)
                        with open(output_path, "rb") as f:
                            out_bytes = f.read()
                            
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, trim_file.name, round(trim_file.size/(1024*1024),2), f"片段剪輯 ({start_time_str}-{end_time_str})", duration, "成功", "無")
                        status.update(label="✅ 剪輯成功！", state="complete")
                        st.download_button(f"⬇️ 下載剪輯後檔案", data=out_bytes, file_name=output_name, use_container_width=True)
                        shutil.rmtree(work_dir, ignore_errors=True)
                    except Exception as e:
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, trim_file.name, round(trim_file.size/(1024*1024),2), "片段剪輯", duration, "失敗", str(e))
                        status.update(label="❌ 處理失敗", state="error")
                        st.error(f"發生錯誤：{str(e)}")

    # ----------------- 子工具 3：格式轉換 -----------------
    with tab3:
        st.subheader("🗜️ 格式轉換與壓縮")
        conv_file = st.file_uploader("請上傳要轉換的檔案", type=["wav", "mp3", "m4a", "flac", "mp4", "mov"], key="conv_uploader")
        if conv_file:
            target_format = st.selectbox("請選擇目標格式：", [".mp3 (推薦)", ".m4a (音質佳)", ".wav (無損)"])
            target_ext = target_format.split(" ")[0]
            if st.button("🗜️ 開始轉換", use_container_width=True):
                with st.status("處理中...", expanded=True) as status:
                    start_time = time.time()
                    try:
                        work_dir = tempfile.mkdtemp()
                        input_path = os.path.join(work_dir, conv_file.name)
                        output_name = os.path.splitext(conv_file.name)[0] + "_converted" + target_ext
                        output_path = os.path.join(work_dir, output_name)
                        
                        with open(input_path, "wb") as f:
                            conv_file.seek(0)
                            while True:
                                chunk = conv_file.read(4 * 1024 * 1024)
                                if not chunk: break
                                f.write(chunk)
                            
                        if target_ext == ".mp3":
                            cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-c:a", "libmp3lame", "-q:a", "2", output_path, "-loglevel", "error"]
                        elif target_ext == ".m4a":
                            cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-c:a", "aac", "-b:a", "192k", output_path, "-loglevel", "error"]
                        else:
                            cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-c:a", "pcm_s16le", "-ar", "48000", output_path, "-loglevel", "error"]
                            
                        subprocess.run(cmd, check=True)
                        with open(output_path, "rb") as f:
                            out_bytes = f.read()
                            
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, conv_file.name, round(conv_file.size/(1024*1024),2), f"格式轉換 ({target_ext})", duration, "成功", "無")
                        status.update(label="✅ 轉換成功！", state="complete")
                        st.download_button(f"⬇️ 下載轉換後檔案", data=out_bytes, file_name=output_name, use_container_width=True)
                        shutil.rmtree(work_dir, ignore_errors=True)
                    except Exception as e:
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, conv_file.name, round(conv_file.size/(1024*1024),2), "格式轉換", duration, "失敗", str(e))
                        status.update(label="❌ 處理失敗", state="error")
                        st.error(f"發生錯誤：{str(e)}")

    # ----------------- 子工具 4：影音合併 -----------------
    with tab4:
        st.subheader("🔗 影音合併 (無損拼接)")
        merge_files = st.file_uploader("請依序上傳要合併的檔案 (可多選)", type=["mp4", "mov", "wav", "mp3", "m4a"], accept_multiple_files=True, key="merge_uploader")
        if merge_files and len(merge_files) > 1:
            if st.button("🔗 開始合併", use_container_width=True):
                with st.status("處理中...", expanded=True) as status:
                    start_time = time.time()
                    try:
                        work_dir = tempfile.mkdtemp()
                        list_file_path = os.path.join(work_dir, "files.txt")
                        ext = os.path.splitext(merge_files[0].name)[1]
                        output_name = "Merged_Output" + ext
                        output_path = os.path.join(work_dir, output_name)
                        
                        total_size = 0
                        with open(list_file_path, "w", encoding="utf-8") as list_file:
                            for i, f_obj in enumerate(merge_files):
                                total_size += f_obj.size
                                temp_name = f"temp_{i}{ext}"
                                temp_path = os.path.join(work_dir, temp_name)
                                
                                with open(temp_path, "wb") as f:
                                    f_obj.seek(0)
                                    while True:
                                        chunk = f_obj.read(4 * 1024 * 1024)
                                        if not chunk: break
                                        f.write(chunk)
                                list_file.write(f"file '{temp_name}'\n")
                                
                        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_path, "-loglevel", "error"], check=True)
                        with open(output_path, "rb") as f:
                            out_bytes = f.read()
                            
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, "多檔合併", round(total_size/(1024*1024),2), "影音合併", duration, "成功", "無")
                        status.update(label="✅ 合併成功！", state="complete")
                        st.download_button(f"⬇️ 下載合併後檔案", data=out_bytes, file_name=output_name, use_container_width=True)
                        shutil.rmtree(work_dir, ignore_errors=True)
                    except Exception as e:
                        duration = round(time.time() - start_time, 1)
                        log_usage(st.session_state.current_user, "多檔合併", 0, "影音合併", duration, "失敗", str(e))
                        status.update(label="❌ 處理失敗", state="error")
                        st.error(f"發生錯誤：{str(e)}")