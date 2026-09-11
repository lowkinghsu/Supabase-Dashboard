#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
healthcheck.py — ILRDF 智慧族語影音智能化處理工作站 自動健康檢測腳本

用途：
  1. 本機手動執行：`python healthcheck.py`，快速掌握目前系統狀態，不用逐個功能點來點去試。
  2. CI / 排程自動執行：`python healthcheck.py --network-only`，只檢查對外部服務的連線
     （辨識/翻譯/Supabase），適合放進 GitHub Actions 定期排程，第一時間發現外部依賴掛掉。

設計原則：完全不依賴 streamlit / torch / gradio_client 等專案重量級套件，
只用 Python 標準函式庫，確保這支健康檢測腳本本身「不會因為專案主程式壞掉而一起壞掉」。
"""

import ast
import os
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request

# 🎯 修正：Windows 主控台預設編碼（cp950/cp936）印不出 emoji，會讓這支檢測腳本自己先當機。
# 強制輸出用 UTF-8，印不出的字元用替代符號頂著，絕不讓「檢測工具本身」變成新的 bug 來源。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 必須跟 utils.py 裡的 TEMP_PREFIXES 保持一致，才能正確統計本工作站留下的暫存檔殘留量
TEMP_PREFIXES = ("denoise_", "ilrdf_asr_", "ilrdf_burn_", "ilrdf_tools_")

EXTERNAL_SERVICES = {
    "ASR辨識服務 (sapolita.ithuan.tw)": "https://sapolita.ithuan.tw/",
    "MT翻譯服務 (ai-labs.ilrdf.org.tw)": "https://ai-labs.ilrdf.org.tw/kari-seejiq-tnpusu-ai-hmjil/",
}

ENV_VARS_TO_CHECK = ["ADMIN_PASSWORD", "GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY"]


class Result:
    def __init__(self):
        self.lines = []
        self.has_fail = False

    def ok(self, msg):
        self.lines.append(f"✅ {msg}")

    def warn(self, msg):
        self.lines.append(f"⚠️  {msg}")

    def fail(self, msg):
        self.lines.append(f"❌ {msg}")
        self.has_fail = True

    def section(self, title):
        self.lines.append(f"\n== {title} ==")


def check_python_syntax(result):
    """遍歷專案內所有 .py 檔案，確認語法完整可解析——避免壞掉的程式碼被推上正式站才發現"""
    result.section("原始碼語法檢查")
    py_files = []
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".cache", "__pycache__")]
        for fn in filenames:
            if fn.endswith(".py"):
                py_files.append(os.path.join(dirpath, fn))

    bad_files = []
    for path in py_files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                source = f.read()
            ast.parse(source, filename=path)
        except SyntaxError as e:
            bad_files.append((path, str(e)))

    if bad_files:
        for path, err in bad_files:
            rel = os.path.relpath(path, PROJECT_ROOT)
            result.fail(f"{rel} 語法錯誤：{err}")
    else:
        result.ok(f"共檢查 {len(py_files)} 個 .py 檔案，語法全部正常")


def check_ffmpeg(result, required=True):
    result.section("FFmpeg 檢測")
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        result.ok(f"ffmpeg / ffprobe 皆存在（{ffmpeg_path}）")
    else:
        missing = []
        if not ffmpeg_path:
            missing.append("ffmpeg")
        if not ffprobe_path:
            missing.append("ffprobe")
        msg = f"找不到：{', '.join(missing)}——降噪、辨識、剪輯轉檔全部都會失敗"
        if required:
            result.fail(msg)
        else:
            result.warn(msg + "（此環境非部署環境，可忽略）")


def check_env_vars(result):
    result.section("環境變數檢查（僅檢查是否存在，不會顯示內容）")
    for name in ENV_VARS_TO_CHECK:
        val = os.environ.get(name, "").strip()
        if val:
            result.ok(f"{name} 已設定")
        else:
            if name == "ADMIN_PASSWORD":
                result.warn(f"{name} 未設定 → 目前會使用原始碼內建的備用密碼，等於後台密碼公開，正式站務必設定")
            else:
                result.warn(f"{name} 未設定")


def check_disk_and_temp(result):
    result.section("磁碟空間與暫存檔殘留量")
    tmp_root = tempfile.gettempdir()
    try:
        total, used, free = shutil.disk_usage(tmp_root)
        free_gb = free / (1024 ** 3)
        if free_gb < 1:
            result.fail(f"磁碟剩餘空間僅 {free_gb:.2f} GB，隨時可能導致上傳/處理失敗")
        elif free_gb < 5:
            result.warn(f"磁碟剩餘空間 {free_gb:.2f} GB，建議留意")
        else:
            result.ok(f"磁碟剩餘空間 {free_gb:.2f} GB")
    except OSError as e:
        result.warn(f"無法讀取磁碟空間：{e}")

    total_size = 0
    total_count = 0
    try:
        for name in os.listdir(tmp_root):
            if name.startswith(TEMP_PREFIXES):
                total_count += 1
                full_path = os.path.join(tmp_root, name)
                try:
                    if os.path.isdir(full_path):
                        total_size += sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, _, files in os.walk(full_path) for f in files
                        )
                    else:
                        total_size += os.path.getsize(full_path)
                except OSError:
                    continue
    except OSError:
        pass

    size_mb = total_size / (1024 * 1024)
    if total_count == 0:
        result.ok("本工作站暫存目錄乾淨，沒有殘留檔案")
    elif size_mb < 200:
        result.warn(f"目前有 {total_count} 個本站殘留暫存項目，共 {size_mb:.1f} MB（正常範圍，可自動清理）")
    else:
        result.warn(f"目前有 {total_count} 個本站殘留暫存項目，共 {size_mb:.1f} MB——數字偏高，代表近期有不少處理失敗的殘留，建議進後台手動清理一次")


def check_external_services(result):
    result.section("外部關鍵服務連線檢測")
    for label, url in EXTERNAL_SERVICES.items():
        start = time.time()
        try:
            req = urllib.request.Request(url, method="GET", headers={"User-Agent": "ILRDF-HealthCheck/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                latency_ms = round((time.time() - start) * 1000)
                status = resp.status
                if status < 500:
                    result.ok(f"{label}：正常（{latency_ms} ms，狀態碼 {status}）")
                else:
                    result.fail(f"{label}：伺服器錯誤（狀態碼 {status}）")
        except urllib.error.HTTPError as e:
            # 4xx 通常代表服務本身活著、只是這個路徑要求別的方法/參數，不算連線異常
            if e.code < 500:
                result.ok(f"{label}：服務有回應（狀態碼 {e.code}）")
            else:
                result.fail(f"{label}：伺服器錯誤（狀態碼 {e.code}）")
        except Exception as e:
            result.fail(f"{label}：連線失敗（{e}）——辨識/翻譯功能目前很可能無法使用")


def main():
    network_only = "--network-only" in sys.argv
    syntax_only = "--syntax-only" in sys.argv

    result = Result()
    print("🩺 ILRDF 智慧族語影音智能化處理工作站 — 系統健康檢測")
    if syntax_only:
        mode_desc = "僅檢查原始碼語法（CI 用，不需要 ffmpeg/網路）"
    elif network_only:
        mode_desc = "僅檢查外部服務連線（CI/排程用）"
    else:
        mode_desc = "完整檢測（本機手動用）"
    print(f"   模式：{mode_desc}")

    if syntax_only:
        check_python_syntax(result)
    elif network_only:
        check_external_services(result)
    else:
        check_python_syntax(result)
        check_ffmpeg(result, required=True)
        check_env_vars(result)
        check_disk_and_temp(result)
        check_external_services(result)

    print("\n".join(result.lines))
    print("\n" + "=" * 60)
    if result.has_fail:
        print("❌ 檢測結果：發現需要處理的異常，請往上查看標示 ❌ 的項目。")
        sys.exit(1)
    else:
        print("✅ 檢測結果：一切正常。")
        sys.exit(0)


if __name__ == "__main__":
    main()
