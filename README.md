---
title: Ilrdf-video-station
emoji: 🎙️
colorFrom: indigo
colorTo: red
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# 🎙️ 原語會智慧族語影音智能化處理工作站 (ILRDF Video Station)

> **財團法人原住民族語言研究發展基金會 (ILRDF)** 專屬之族語語料採集、田野調查影音前處理與智慧化辨識/翻譯工作站。

---

## 🌟 專案核心特色與功能模組

### 1. 🎙️ 影音降噪工具 (`modules/denoise.py`)
- **DeepFilterNet 深度學習降噪**：全自動去除田野調查中的風聲、環境音、底噪與雜訊，精準還原人聲音質。
- **音量智能標準化**：降噪後自動進行 -1.0 dB 音量增益補償，避免聲音衰減。
- **伺服器防爆盾**：限制 300MB 以上超大影片直衝降噪，引導先抽取純音檔以提升 5 倍速度並防止 OOM。

### 2. 📝 族語辨識與翻譯 (`modules/asr_mt.py`)
- **16 族語語音辨識 (ASR)**：串接原語會專屬服務 (`sapolita.ithuan.tw`) 一鍵生成標準帶時間軸的 SRT 字幕。
- **智慧切片演算法 (`split_long_srt_blocks`)**：自動將超過 6 秒的長字幕依字數比例等分切片為黃金長度。
- **雙向機器翻譯 (MT)**：支援原語會 16 族語 NLLB 翻譯模型，並整合 Google Gemini 3.8 Flash 進行雙語語意潤飾。
- **雙語字幕燒錄 (Hardsub)**：利用 FFmpeg 將雙語字幕直接燒錄進影片（支援 Noto Sans CJK 字型）。

### 3. ✂️ 影音剪輯與轉檔小工具 (`modules/tools.py`)
- **🎵 音訊抽取**：一鍵將各類影片格式轉換抽取為輕量 MP3。
- **✂️ 片段剪輯**：依時間戳記（HH:MM:SS）進行快速無損音訊/影片裁切。
- **🗜️ 格式轉換**：支援 MP3、M4A、WAV 等格式相互轉換與位元率優化。
- **🔗 影音合併**：支援多個影音檔案透過 FFmpeg `concat` 進行無損拼接。

---

## 🛡️ 系統架構與安全機制

- **全域排隊鎖 (`CPU_LOCK`)**：採用 `threading.Lock()` 確保同一時間伺服器僅執行一項高能耗運算，防止多使用者併發造成伺服器崩潰。
- **延遲加載模型 (Lazy Load)**：避開伺服器開機時的高負載，改於使用者首次執行降噪時才動態載入。
- **RLS 資料列層級安全防護**：Supabase 資料庫全面啟用 RLS，禁止外部未授權篡改與刪除。
- **GitHub Actions 自動保活機制**：每日排程向 Supabase 發送輕量請求，防止免費版專案因 7 天無活動而被自動暫停休眠。
- **暫存檔自動清理 (`utils.cleanup_stale_temp_files`)**：所有處理模組失敗時的殘留暫存檔，每 10 分鐘自動掃描並清除超過 2 小時的項目，避免長期累積塞滿伺服器磁碟導致上傳/下載變慢或失敗。
- **系統健康檢查（後台 + 獨立腳本雙軌）**：管理員後台新增「🩺 系統健康檢查」面板，即時顯示磁碟空間、暫存檔累積量、FFmpeg 與 ASR/MT 外部服務連線狀況；另提供可獨立執行、零額外套件依賴的 [`healthcheck.py`](healthcheck.py)，並透過 `.github/workflows/health_check.yml` 每 3 小時自動巡檢一次外部服務。

---

## 📂 專案檔案結構

```text
05_Portal_ILRDF_Video_Station/
├── .github/
│   └── workflows/
│       ├── supabase_keep_alive.yml # 🤖 Supabase 每日自動保活排程工作流
│       └── health_check.yml        # 🩺 每 3 小時自動巡檢 ASR/MT 外部服務 + 原始碼語法
├── modules/
│   ├── home_page.py                # 🏛️ 官方首頁大廳 (Hero Section、音樂播放、指引圖卡)
│   ├── denoise.py                  # 🎙️ 深度學習影音降噪模組
│   ├── asr_mt.py                   # 📝 族語辨識、長字幕切片、翻譯與字幕燒錄
│   └── tools.py                    # ✂️ 影音抽取、裁切、轉檔、合併工具箱
├── app.py                          # 🚀 Streamlit 系統主入口與身分驗證路由
├── utils.py                        # 🛠️ 公用函式庫 (CPU鎖、模型延遲加載、Supabase日誌、CSS防震、暫存清理、健康檢查)
├── healthcheck.py                  # 🩺 獨立健康檢測腳本 (可本機手動跑，也可 CI 排程跑)
├── Dockerfile                      # 🐳 容器化部署定義檔 (安裝 FFmpeg 與中文字型)
├── requirements.txt                # 📦 Python 套件依賴清單
├── start_server.bat                # 💻 本地端快速啟動腳本
├── bgm.mp3                         # 🎵 首頁背景音樂
└── home.jpg                        # 📸 系統實戰操作圖文指引
```

---

## 🚀 部署與環境變數設定

### 必需環境變數 (Secrets)
| 變數名稱 | 說明 | 範例 / 用途 |
| :--- | :--- | :--- |
| `ADMIN_PASSWORD` | 管理員後台登入密碼 | 用於解鎖下載統計報表與 Bug 清單 |
| `GEMINI_API_KEY` | Google Gemini API 金鑰 | 用於 LLM 雙語字幕深度翻譯與潤飾 |
| `SUPABASE_URL` | Supabase 專案網址 | `https://xxxx.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase 匿名公鑰 | 用於日誌寫入與 GitHub Actions 保活 |

---

## 📜 授權條款
MIT License © 2026 財團法人原住民族語言研究發展基金會 (ILRDF)
