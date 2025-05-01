FROM python:3.10-slim

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用程序代码
COPY . .

# 创建数据目录
RUN mkdir -p uploads

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PORT=12000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 12000

# 启动应用 - 针对小内存环境优化
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers=1 \
    --threads=2 \
    --worker-class=gthread \
    --worker-tmp-dir=/dev/shm \
    --timeout=120 \
    --max-requests=1000 \
    --max-requests-jitter=50 \
    app:app