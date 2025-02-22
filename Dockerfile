FROM python:3.11-slim

# 设置时区为中国时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装ping工具
RUN apt-get update && apt-get install -y iputils-ping && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制项目文件
COPY requirements.txt .
COPY config.py .
COPY main.py .

# 安装依赖
RUN pip install -r requirements.txt

# 创建配置文件和日志目录
RUN mkdir -p logs && touch config.yaml

# 运行程序
CMD ["python", "main.py"]