# app.py
import streamlit as st
import datetime
import os  # 引入作業系統模組來讀取 Docker 環境變數
import time # 確保全域時間元件正常運作

# 👑 關鍵防震配置：改回 centered 封印魔王迴圈，配合 utils.py 5.0 達成完美寬版無視覺抖動
st.set_page_config(
    page_title="原語會智慧族語影音智能化處理工作站",
    page_icon="🎙️",
    layout="centered"  
)

import streamlit.components.v1 as components
# Google Analytics 4 全站流量追蹤 (G-4M6KQ8KSY5)
components.html("""
<script async src="https://www.googletagmanager.com/gtag/js?id=G-4M6KQ8KSY5"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-4M6KQ8KSY5');
</script>
""", height=0, width=0)

# 從 utils 完美導入問題回報與數據對接功能
from utils import init_session_state, inject_css, get_usage_data, ADMIN_PASSWORD, submit_bug_report, get_bug_reports_data

# 💡 從功能模組資料夾中流暢導入包括全新網頁大廳在內的所有分頁
from modules.home_page import render_home_page
from modules.denoise import render_denoise_page
from modules.asr_mt import render_asr_mt_page
from modules.tools import render_tools_page

# 1. 執行全域初始化與客製化視覺注入
init_session_state()
inject_css()

def main():
    # 💡 智能化首頁入口狀態控管
    if "entered" not in st.session_state:
        st.session_state.entered = False

    # ==================== 🏛️ 模組 A：大氣專業官方首頁入口網 (未點擊進入前) ====================
    if not st.session_state.entered:
        render_home_page()
        st.stop() # 💡 核心安全防線：未點擊驗證前，全面阻斷下方後台側邊欄與功能業務的渲染

    # ==================== ⚙️ 模組 B：原有功能工作站邏輯 (點擊進入後流暢接軌) ====================
    # 2. 建構全域側邊欄
    with st.sidebar:
        st.title("🧭 工作站導覽")
        
        st.header("👤 使用者身分")
        user_name_input = st.text_input("您的姓名 / 單位 (必填)", help="本工作站為內部工具，請務必填寫真實姓名或單位以供數據統計喔！")
        
        if user_name_input.strip():
            st.session_state.current_user = user_name_input.strip()
            st.success(f"Embiyax su hug? 歡迎您，{st.session_state.current_user}！")
        else:
            st.session_state.current_user = ""  # 未填寫時保持清空
            
        st.markdown("---")
        
        # 主要功能分頁切換
        page_selection = st.radio(
            "請選擇功能：",
            ["🎙️ 影音降噪", "📝 辨識與翻譯", "✂️ 影音剪輯與轉檔"]
        )
        
        st.markdown("---")
        
        # ==================== 🚨 全域問題回報與建議表單 ====================
        with st.expander("🚨 系統問題與建議回報"):
            st.caption("使用過程中遇到任何錯誤或不順暢？請直接填寫下方表單，我們會即時於後台收到您的回報！")
            
            report_page = st.selectbox(
                "1. 發生問題的功能區：",
                ["🎙️ 影音降噪", "📝 辨識與翻譯", "✂️ 影音剪輯與轉檔", "🧭 整體介面/其他"]
            )
            report_type = st.selectbox(
                "2. 問題分類：",
                ["❌ 系統跑出紅字錯誤", "⏳ 轉圈圈卡死沒反應", "🤔 辨識與翻譯不準確", "💡 我有優化建議"]
            )
            report_desc = st.text_area(
                "3. 詳細狀況描述：",
                placeholder="請簡單描述您做了什麼動作、或是複製貼上紅字的錯誤訊息..."
            )
            
            if st.button("📤 提交錯誤回報", use_container_width=True):
                if not report_desc.strip():
                    st.error("請填寫第 3 項的狀況描述再送出喔！")
                else:
                    # 調用雲端對接模組
                    current_reporter = st.session_state.current_user if st.session_state.current_user else "未登入使用者"
                    with st.spinner("正在將您的問題推送至管理員後台..."):
                        success = submit_bug_report(current_reporter, report_page, report_type, report_desc.strip())
                        if success:
                            st.success("🎉 回報成功！我們已收到您的反饋，會盡快排查，感謝您的協助！")
                            # 清空輸入框
                            time_placeholder = st.empty()
                        else:
                            st.error("📡 雲端通訊失敗，請檢查網路，或截圖傳給維運窗口。")
                            
        st.markdown("---")
        
        # ==================== 🔑 進階功能設定 (實體部署環境變數版) ====================
        st.header("🔑 進階功能設定")
        
        env_gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_gemini_key != "":
            st.session_state.gemini_key = env_gemini_key
            st.success("🤖 單位專屬 AI 已全面啟用")
            
            try:
                import google.generativeai as genai
                genai.configure(api_key=st.session_state.gemini_key)
                list(genai.list_models()) 
                st.caption("✅ 字幕潤飾與雙語翻譯連線正常")
            except Exception:
                st.error("❌ 後台 Gemini 金鑰驗證失敗，請檢查 HF Secrets 設定。")
        else:
            st.warning("⚠️ 未偵測到全局金鑰，請至 HF Settings 設定 GEMINI_API_KEY。")
            
        st.markdown("---")
        
# ==================== 📊 管理員模式 (加裝問題回報下載鈕) ====================
        st.subheader("📊 管理員模式")
        admin_pwd = st.text_input("輸入管理密碼", type="password")
        
        # 💡 只有當輸入的管理密碼完全正確時，才允許執行後續的資料庫讀取
        if admin_pwd == ADMIN_PASSWORD:
            st.success("管理權限已解鎖")
            
            # 移到裡面的關鍵三行（前面要補空格對齊喔！）
            usage_data = get_usage_data()
            total_count = len(usage_data) - 1 if len(usage_data) > 0 else 0
            st.caption(f"累計處理人次: **{total_count}** 次")
            
            # 按鈕 A：下載使用數據
            if usage_data:
                st.download_button(
                    label="⬇️ 下載統計數據 (CSV)",
                    data="".join(usage_data).encode("utf-8-sig"),
                    file_name=f"system_log_{datetime.date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
                
            # 按鈕 B：一鍵打包下載所有 Bug 與同仁意見
            bug_reports = get_bug_reports_data()
            bug_count = len(bug_reports) - 1 if len(bug_reports) > 0 else 0
            st.markdown(f"待處理使用者回報：**{bug_count}** 筆")
            
            if bug_count > 0:
                st.download_button(
                    label="🚨 下載 Bug 與意見清單 (CSV)",
                    data="".join(bug_reports).encode("utf-8-sig"),
                    file_name=f"bug_reports_{datetime.date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            # 💡 密碼沒輸入或不正確時，只顯示這行提示，完全不碰資料庫！
            st.caption("🔒 輸入正確的管理密碼後，即可解鎖累積人次與數據下載功能。")

    # 【核心安全攔截】如果使用者沒有輸入姓名，直接阻斷右側畫面渲染，強迫填寫
    if not st.session_state.current_user:
        st.info("## **👋 歡迎使用 ILRDF 原語會 - 智慧族語影音智能化處理工作站！**")
        st.warning("⚠️ **請先在左側邊欄填寫「您的姓名 / 單位」**，填寫完畢後系統會自動解鎖降噪、辨識與剪輯功能。")
        st.stop() # 阻斷後續畫面

    # 3. 核心分頁路由 (只有輸入姓名後，才能走到這一階段)
    if page_selection == "🎙️ 影音降噪":
        render_denoise_page()
    elif page_selection == "📝 辨識與翻譯":
        render_asr_mt_page()
    elif page_selection == "✂️ 影音剪輯與轉檔":
        render_tools_page()

if __name__ == "__main__":
    main()