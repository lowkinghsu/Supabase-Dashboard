@echo off
echo Starting ILRDF Video Station Server...
REM 修正：這是 Streamlit 應用，必須用 "streamlit run" 啟動，
REM 直接用 "python app.py" 只會執行腳本本身、不會啟動網頁伺服器（畫面打不開）。
start http://127.0.0.1:7860
streamlit run app.py --server.port=7860
pause
