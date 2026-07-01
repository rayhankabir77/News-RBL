FROM python:3.10-slim

# কাজের ডিরেক্টরি সেট করা
WORKDIR /app

# সিস্টেম ডিপেন্ডেন্সি ইনস্টল করা
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# পাইথন প্যাকেজ কপি ও ইনস্টল করা
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# বটের কোড কপি করা
COPY . .

# রান করার কমান্ড
CMD ["python", "bot.py"]
