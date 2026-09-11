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
from utils import (
    init_session_state, inject_css, get_usage_data, ADMIN_PASSWORD, ADMIN_PASSWORD_IS_FALLBACK,
    submit_bug_report, get_bug_reports_data, maybe_run_background_cleanup,
    cleanup_stale_temp_files, get_system_health,
)

# 💡 從功能模組資料夾中流暢導入包括全新網頁大廳在內的所有分頁
from modules.home_page import render_home_page
from modules.denoise import render_denoise_page
from modules.asr_mt import render_asr_mt_page
from modules.tools import render_tools_page

# 1. 執行全域初始化與客製化視覺注入
init_session_state()
inject_css()

def main():
    # 🎯 修正：每次有人互動時，順手檢查一次是否需要清理過期暫存檔（內建 10 分鐘節流，
    # 不會拖慢正常操作），從根本解決失敗任務留下的殘留檔案長期塞滿伺服器磁碟的問題
    maybe_run_background_cleanup()

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

            # 🎯 修正：舊版送出成功後宣稱「清空輸入框」，但實際上只建立了一個沒用到的 st.empty()，
            # 三個欄位完全沒有被清空。改用 widget 版本號讓 key 跟著換一輪，Streamlit 才會真的把欄位重置成預設值
            if "bugreport_widget_version" not in st.session_state:
                st.session_state.bugreport_widget_version = 0
            _brv = st.session_state.bugreport_widget_version

            report_page = st.selectbox(
                "1. 發生問題的功能區：",
                ["🎙️ 影音降噪", "📝 辨識與翻譯", "✂️ 影音剪輯與轉檔", "🧭 整體介面/其他"],
                key=f"report_page_{_brv}"
            )
            report_type = st.selectbox(
                "2. 問題分類：",
                ["❌ 系統跑出紅字錯誤", "⏳ 轉圈圈卡死沒反應", "🤔 辨識與翻譯不準確", "💡 我有優化建議"],
                key=f"report_type_{_brv}"
            )
            report_desc = st.text_area(
                "3. 詳細狀況描述：",
                placeholder="請簡單描述您做了什麼動作、或是複製貼上紅字的錯誤訊息...",
                key=f"report_desc_{_brv}"
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
                            # 真正清空：換一版 key，讓三個欄位在下一次重繪時變回全新、空白的元件
                            st.session_state.bugreport_widget_version += 1
                            st.rerun()
                        else:
                            st.error("📡 雲端通訊失敗，請檢查網路，或截圖傳給維運窗口。")
                            
        st.markdown("---")
        
        # ==================== 🔑 進階功能設定 (實體部署環境變數版) ====================
        st.header("🔑 進階功能設定")
        
        env_gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if env_gemini_key != "":
            st.session_state.gemini_key = env_gemini_key
            st.success("🤖 單位專屬 AI 已全面啟用")

            # 🎯 修正：舊版每次側邊欄重繪（幾乎等於每次點擊任何東西）都會重新呼叫一次
            # genai.list_models() 驗證金鑰，等於把整站每個互動都綁上一次額外的外部 API 延遲，
            # 是「整體變卡頓」的常見成因之一。改成每個 session 只在第一次、或使用者主動要求時才驗證一次。
            if "gemini_key_validated" not in st.session_state:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=st.session_state.gemini_key)
                    list(genai.list_models())
                    st.session_state.gemini_key_validated = True
                except Exception as e:
                    st.session_state.gemini_key_validated = False
                    st.session_state.gemini_key_error = str(e)[:200]

            if st.session_state.gemini_key_validated:
                st.caption("✅ 字幕潤飾與雙語翻譯連線正常")
            else:
                st.error("❌ 後台 Gemini 金鑰驗證失敗，請檢查 HF Secrets 設定。")
                if st.session_state.get("gemini_key_error"):
                    st.caption(f"詳細訊息：{st.session_state.gemini_key_error}")

            if st.button("🔄 重新驗證金鑰", use_container_width=True):
                st.session_state.pop("gemini_key_validated", None)
                st.session_state.pop("gemini_key_error", None)
                st.rerun()
        else:
            st.warning("⚠️ 未偵測到全局金鑰，請至 HF Settings 設定 GEMINI_API_KEY。")
            
        st.markdown("---")
        
# ==================== 📊 管理員模式 (加裝問題回報下載鈕) ====================
        st.subheader("📊 管理員模式")
        admin_pwd = st.text_input("輸入管理密碼", type="password")
        
        # 💡 只有當輸入的管理密碼完全正確時，才允許執行後續的資料庫讀取
        if admin_pwd == ADMIN_PASSWORD:
            st.success("管理權限已解鎖")

            if ADMIN_PASSWORD_IS_FALLBACK:
                st.warning("⚠️ 目前使用的是原始碼內建的備用管理密碼，尚未在部署環境設定 `ADMIN_PASSWORD`！任何看過原始碼的人都能用這組密碼登入後台，請盡快到 HF Space Secrets 設定專屬密碼。")

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

            # ==================== 🩺 系統健康檢查（本次新增：完成修復後的持續檢測機制） ====================
            st.markdown("---")
            st.subheader("🩺 系統健康檢查")
            st.caption("檢測伺服器磁碟空間、暫存檔累積量、FFmpeg 與外部辨識/翻譯服務的即時連線狀況。")

            if st.button("🔍 立即執行健康檢查", use_container_width=True):
                with st.spinner("正在檢測磁碟、FFmpeg 與外部服務連線..."):
                    st.session_state.health_report = get_system_health()

            if "health_report" in st.session_state:
                health = st.session_state.health_report

                hc1, hc2, hc3 = st.columns(3)
                with hc1:
                    if health["disk_free_gb"] is not None:
                        st.metric("磁碟剩餘空間", f"{health['disk_free_gb']} GB")
                    else:
                        st.metric("磁碟剩餘空間", "無法讀取")
                with hc2:
                    st.metric("本站殘留暫存檔", f"{health['temp_usage_mb']} MB", help=f"共 {health['temp_item_count']} 個項目；正常情況下應該接近 0，數字持續變大代表有處理失敗未清乾淨的殘留檔案")
                with hc3:
                    st.metric("FFmpeg 狀態", "✅ 正常" if health["ffmpeg_ok"] else "❌ 找不到")

                st.markdown("**外部關鍵服務連線狀態：**")
                for label, info in health["services"].items():
                    if info.get("ok"):
                        st.success(f"✅ {label}：正常（{info['latency_ms']} ms，狀態碼 {info['status_code']}）")
                    else:
                        detail = info.get("error") or f"狀態碼 {info.get('status_code')}"
                        st.error(f"❌ {label}：異常（{detail}）")

                if health["temp_item_count"] > 0:
                    if st.button("🧹 立即清除過期暫存檔（超過 2 小時的殘留）", use_container_width=True):
                        removed, freed_mb = cleanup_stale_temp_files()
                        st.success(f"已清除 {removed} 個殘留項目，釋放約 {freed_mb} MB 磁碟空間。")
                        st.session_state.health_report = get_system_health()
                        st.rerun()
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