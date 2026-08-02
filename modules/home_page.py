# modules/home_page.py
import streamlit as st
import os

def render_home_page():
    """渲染大氣的官方工作站入口網 (精簡公務版：完全移除數據方塊，修復根目錄音樂播放)"""
    
    # 1. 隱藏側邊欄，並【強制鎖定 2026 全域防震軌道】防止大圖引發寬度計算的無窮震盪抖動迴圈
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        /* 🎯 治本神方：強制鎖定全域捲軸與底層容器，安定寬度計算，網頁絕不再抖動 */
        html, body, [data-testid="stAppViewContainer"] {
            overflow-y: scroll !important;
        }
        /* 給予底部充足的緩衝空間，避免滾動條邊界跳動 */
        [data-testid="stMainBlockContainer"] {
            padding-bottom: 6rem !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # 2. 頂部官方導覽列 (已徹底拔除「內部管理網關」標籤，回歸官方純淨感)
    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center; padding:14px 24px; background:white; border-bottom:1px solid #e2e8f0; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.05); font-family:system-ui, -apple-system, sans-serif;">
        <div style="display:flex; align-items:center; gap:12px;">
            <div style="background:linear-gradient(135deg, #b91c1c, #047857); color:white; padding:8px 14px; border-radius:6px; font-weight:bold; font-size:0.95rem; letter-spacing:1px; box-shadow:0 2px 4px rgba(0,0,0,0.1);">ILRDF</div>
            <div style="font-size:1.35rem; font-weight:800; color:#0c4a6e; letter-spacing:0.5px;">智慧族語影音智能化處理工作站</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 3. 主視覺官方看板 (Hero Section)
    st.markdown("""
    <div style="text-align:center; padding: 4rem 1rem 2.5rem 1rem; background: radial-gradient(circle at top right, rgba(12, 165, 233, 0.05), transparent); border-bottom: 1px solid #e2e8f0; font-family: system-ui, sans-serif;">
        <h1 style="font-size: 2.6rem; color: #0c4a6e; margin-bottom: 1.2rem; font-weight: 800; letter-spacing: -0.5px;">財團法人原住民族語言研究發展基金會</h1>
        <p style="font-size: 1.2rem; color: #475569; max-width: 800px; margin: 0 auto; line-height: 1.6;">
            智慧族語影音智能化處理工作站專門提供田野調查、語料採集之影音或音訊自動化精細降噪、高精度語音辨識（ASR）與機器翻譯（MT）核心調校。
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 4. 🎵 串接全新的「原生安全音樂播放線路」
    audio_path = "bgm.mp3"
    if os.path.exists(audio_path):
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        
        # 建立置中、精美的音軌控制盤
        _, music_container, _ = st.columns([1, 2, 1])
        with music_container:
            st.write("")
            st.caption("🎵 **工作站環境背景音樂**（支援循環播放，使用者可自主調配音量與開關）：")
            st.audio(audio_bytes, format="audio/mp3", loop=True)
    else:
        st.error("⚠️ 系統在根目錄找不到 bgm.mp3 文件，請確認檔案是否確實上傳到最外層目錄中。")

    # 5. 進入智能化處理主控台按鈕
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        if st.button("🔓 點擊驗證並進入族語AI智能化處理工作站", use_container_width=True, type="primary"):
            st.session_state.entered = True  
            st.rerun()

    # ==================== 🛠️ 6. 核心處理模組介紹區 (完全體一致性優化版) ====================
    st.markdown("<br><h3 style='color:#0c4a6e; font-weight:800; font-family:system-ui; margin-bottom:1.2rem; text-align:center;'>工作站核心處理模組</h3>", unsafe_allow_html=True)
    mc1, mc2, mc3 = st.columns(3)
    
    with mc1:
        st.markdown("""
        <div style="background: linear-gradient(145deg, #ffffff, #f0f9ff); border: 1px solid #bae6fd; border-radius: 12px; padding: 2rem; min-height: 240px; height: auto; box-sizing: border-box; box-shadow: 0 4px 12px rgba(12, 165, 233, 0.06); font-family: system-ui, sans-serif; display: flex; flex-direction: column;">
            <h4 style="font-size: 1.25rem; color: #0c4a6e; margin-bottom: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 6px; min-height: 2.2rem;">🎙️ 影音降噪工具</h4>
            <p style="font-size: 0.95rem; color: #334155; line-height: 1.6; margin: 0;">內建 DeepFilterNet 深度學習降噪神經網路，全自動過濾田野調查中斑駁的環境背景雜訊，精準還原清晰語音。</p>
        </div>
        """, unsafe_allow_html=True)
        
    with mc2:
        st.markdown("""
        <div style="background: linear-gradient(145deg, #ffffff, #f0f9ff); border: 1px solid #bae6fd; border-radius: 12px; padding: 2rem; min-height: 240px; height: auto; box-sizing: border-box; box-shadow: 0 4px 12px rgba(12, 165, 233, 0.06); font-family: system-ui, sans-serif; display: flex; flex-direction: column;">
            <h4 style="font-size: 1.25rem; color: #0c4a6e; margin-bottom: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 6px; min-height: 2.2rem;">📝 自動化雙語辨識</h4>
            <p style="font-size: 0.95rem; color: #334155; line-height: 1.6; margin: 0;">對接原語會專屬語音辨識（ASR）與 NLLB 翻譯模型（MT），支援 16 原住民族語與繁體華語的雙向翻譯字幕。</p>
        </div>
        """, unsafe_allow_html=True)
        
    with mc3:
        st.markdown("""
        <div style="background: linear-gradient(145deg, #ffffff, #f0f9ff); border: 1px solid #bae6fd; border-radius: 12px; padding: 2rem; min-height: 240px; height: auto; box-sizing: border-box; box-shadow: 0 4px 12px rgba(12, 165, 233, 0.06); font-family: system-ui, sans-serif; display: flex; flex-direction: column;">
            <h4 style="font-size: 1.25rem; color: #0c4a6e; margin-bottom: 0.85rem; font-weight: 700; display: flex; align-items: center; gap: 6px; min-height: 2.2rem;">✂️ 影音剪輯與轉檔</h4>
            <p style="font-size: 0.95rem; color: #334155; line-height: 1.6; margin: 0;">提供輕量化多媒體前處理工具箱，協助同仁快速進行影音格式轉換、採集段落切割及純音訊抽取優化。</p>
        </div>
        """, unsafe_allow_html=True)

    # ==================== 📸 7. 操作指引多格漫畫圖卡區塊 ====================
    st.markdown("<br><br><h3 style='color:#0c4a6e; font-weight:800; font-family:system-ui; margin-bottom:1rem; text-align:center;'>📱 工作站系統操作圖文指引</h3>", unsafe_allow_html=True)
    
    _, img_container, _ = st.columns([0.02, 0.96, 0.02])
    with img_container:
        img_filename = "home.jpg"
        if os.path.exists(img_filename):
            st.image(
                img_filename, 
                caption="智慧族語影音智能化處理工作站 - 系統實戰操作步驟指引", 
                use_column_width=True
            )
        else:
            st.warning(f"📡 系統暫時偵測不到指引圖檔：{img_filename}，請確認是否上傳到專案的最外層根目錄。")

    # 8. 官方頁腳
    st.markdown("""
    <br><br>
    <div style="text-align: center; color: #64748b; font-size: 0.875rem; padding: 2rem 0; border-top: 1px solid #e2e8f0; font-family: system-ui;">
        © 2026 財團法人原住民族語言研究發展基金會 (ILRDF). All Rights Reserved. 智慧族語影音智能化處理工作站安全部署測試版
    </div>
    """, unsafe_allow_html=True)