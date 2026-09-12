FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    fonts-noto-cjk \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

COPY --chown=user . $HOME/app

EXPOSE 7860

# 🎯 修正：Hugging Face Spaces 是把整個 App 嵌在 huggingface.co 網域下的 iframe 裡執行，
# 瀏覽器會擋掉跨網域 iframe 的 XSRF cookie，導致 Streamlit 內建的 file_uploader 上傳一律失敗
# （前端噴出 AxiosError 403）。這是 Streamlit 官方與社群都證實的已知問題，正式修法就是關閉 XSRF 保護。
# 🎯 追加修正：另有使用者回報 "AxiosError: Network Error"（無狀態碼，代表連線根本沒收到回應），
# 這是另一個有記錄在案的 Streamlit 部署問題 (streamlit/streamlit#9719)，社群做法是連同
# CORS 保護一起關閉（單獨關 XSRF 不一定夠）。這裡一併加上，但不保證 100% 解決——
# 若還是偶發，很可能混雜了行動網路本身不穩定的因素，需要再觀察。
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.maxUploadSize=500", "--server.enableXsrfProtection=false", "--server.enableCORS=false"]