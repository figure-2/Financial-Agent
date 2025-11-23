# 1. 베이스 이미지 설정
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-devel

# 2. 시스템 환경 변수 설정
ENV DEBIAN_FRONTEND=noninteractive

# 3. 시스템 패키지 설치 (사용자 요청 기반)
# apt-get update, chromium-chromedriver 설치를 반영합니다.
# 원활한 실행을 위해 python3-pip와 chromium-browser는 함께 설치합니다.
RUN apt-get update && apt-get install -y \
    python3-pip \
    chromium-browser \
    chromium-chromedriver \
    fonts-nanum* \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# 4. 파이썬 패키지 설치
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 소스 코드 복사
COPY . .

# 6. 서버 실행
CMD ["uvicorn", "financial_agent.api_server:app", "--host", "0.0.0.0", "--port", "8000"]