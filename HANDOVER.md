# 📋 原語會智慧族語影音工作站 交接手冊 (HANDOVER.md)

> **專案狀態**：🟢 `PRODUCTION_READY`（正式生產就緒）  
> **最後更新日期**：2026-08-19  
> **維護單位**：財團法人原住民族語言研究發展基金會 (ILRDF)

---

## 一、 系統架構與關鍵技術指標

| 項目 | 技術 / 服務 | 說明 |
| :--- | :--- | :--- |
| **前端與主框架** | Streamlit 1.38.0 | 客製化防震排版、Centered 拉伸防抖動技術 |
| **流量追蹤** | Google Analytics 4 | GA4 ID: `G-4M6KQ8KSY5` |
| **深度學習降噪** | DeepFilterNet 0.5.6 | 延遲加載架構，避免開機卡死；降噪後 -1.0dB 標準化 |
| **語音辨識 (ASR)** | Gradio Client 串接 | 原語會專屬語音轉 SRT 服務 (`sapolita.ithuan.tw`) |
| **雙語機器翻譯** | Gradio MT + Gemini 3.8 Flash | 16 族語 NLLB 雙向翻譯 + LLM 語意精修 |
| **多媒體轉碼** | FFmpeg / FFprobe | 內建中文字型 (`fonts-noto-cjk`) 支援字幕硬編碼燒錄 |
| **雲端日誌與回報** | Supabase REST API | 資料表：`denoise_usage_log`, `system_bug_reports` |
| **排程保活** | GitHub Actions | 每日定時向 Supabase 請求，防止 7 天自動休眠 |

---

## 二、 重大維運問題修復紀錄

### 1. Supabase 安全漏洞修復 (`rls_disabled_in_public`)
* **問題**：官方安全檢查報告 `denoise_usage_log` 與 `system_bug_reports` 未啟用 RLS，造成公開竄改/刪除風險。
* **修復方案**：已在 Supabase 執行 SQL 啟用 RLS，並配置匿名使用者的 `INSERT` 與 `SELECT` Policy，同時完全封鎖未授權的 `UPDATE` 與 `DELETE` 權限。
* **目前狀態**：Security Advisor 達到 **0 Errors**。

### 2. Supabase 7 天無活動自動休眠 (Auto-pause) 解決方案
* **問題**：Supabase Free Tier 專案若 7 天無活動會自動暫停，造成日誌與回報無法寫入。
* **修復方案**：已在 GitHub 建立專屬保活倉庫 `lowkinghsu/Supabase-Dashboard`，配置 `.github/workflows/supabase_keep_alive.yml`，每日 UTC 00:00 (台灣時間 08:00) 自動向 REST API 發送輕量請求。
* **驗證結果**：手動執行測試已通過（Status: Success 9s，HTTP 200）。

---

## 三、 維運常用清單與 Secrets 設定

### 1. Hugging Face Spaces / 部署環境變數
* `ADMIN_PASSWORD`：管理員後台解鎖密碼（用於下載 CSV 日誌與 Bug 回報）。
* `GEMINI_API_KEY`：Google Gemini API 金鑰。
* `SUPABASE_URL`：`https://wnyckiumewmvvvoglkyd.supabase.co`。
* `SUPABASE_ANON_KEY`：Supabase 匿名公鑰。

### 2. GitHub Actions 倉庫 Secrets
* 倉庫網址：`https://github.com/lowkinghsu/Supabase-Dashboard`
* Secret 名稱：`SUPABASE_ANON_KEY`

---

## 四、 常用維運指令

⚠️ **2026-09-11 重大修正**：origin 這個 Hugging Face Space 實際部署的分支是 `main`，**不是** `master`！
過去只推 `master` 完全不會觸發正式站重新部署（`git ls-remote` 可看到 `origin` 上 `main` 跟 `master` 是兩條分支）。
`main` 上還曾經有人直接透過 HF 網頁編輯器改過 `requirements.txt`（把 `gradio_client` 從 `==1.3.0` 改成
`>=1.5.0` 這種未鎖版本，2026-08-19，作者顯示為 `ILRDF-Lowking@users.noreply.huggingface.co`），這個改動
只存在於 `main`，從來沒進過我們本地這條 git 歷史，直到這次合併才發現、才鎖回明確版本號。
以後**務必同時推 `main` 跟 `master`**，並留意如果又在 HF 網頁上直接編輯過檔案，本地要記得先 `git fetch origin main` 再合併，別直接覆蓋。

```powershell
# 1. 本地啟動伺服器
streamlit run app.py --server.port=7860

# 2. 推送至 Hugging Face Spaces（main 才是實際部署分支！）
git push origin master:main
git push origin master:master

# 3. 推送至 GitHub 保活倉庫
git push github master:master
```
