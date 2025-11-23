import requests
import json

import pandas as pd
import re
import os
from pathlib import Path
import yaml
from dotenv import load_dotenv
from sqlalchemy import create_engine

import threading
from flask import Flask, send_from_directory
    

# 종목 데이터 로드
def load_stock_data(data_path):
    """CSV 파일에서 종목 데이터 로드"""
    try:
        # CSV 파일 경로 (실제 파일 경로로 변경 필요)
        csv_path = data_path

        # CSV 파일 로드
        stock_df = pd.read_csv(csv_path, encoding='utf-8-sig')

        # 티커 형식 통일 (6자리 숫자 + .KS/.KQ)
        def format_ticker(ticker, market):
            # 숫자만 추출
            ticker_num = re.sub(r'[^0-9]', '', str(ticker))
            # 6자리로 패딩
            ticker_padded = ticker_num.zfill(6)
            # 시장에 따라 접미사 추가
            if market == 'KOSPI':
                return f"{ticker_padded}.KS"
            elif market in ['KOSDAQ', 'KONEX']:
                return f"{ticker_padded}.KQ"
            else:
                return f"{ticker_padded}.KS"  # 기본값

        stock_df['formatted_ticker'] = stock_df.apply(
            lambda row: format_ticker(row['ticker'], row['market']), axis=1
        )

        return stock_df

    except FileNotFoundError:
        # 기본 종목 데이터 (예시)
        default_stocks = [
            {"company_name": "삼성전자", "ticker": "005930", "market": "KOSPI", "formatted_ticker": "005930.KS"},
            {"company_name": "SK하이닉스", "ticker": "000660", "market": "KOSPI", "formatted_ticker": "000660.KS"},
            {"company_name": "LG에너지솔루션", "ticker": "373220", "market": "KOSPI", "formatted_ticker": "373220.KS"},
            {"company_name": "현대차", "ticker": "005380", "market": "KOSPI", "formatted_ticker": "005380.KS"},
            {"company_name": "기아", "ticker": "000270", "market": "KOSPI", "formatted_ticker": "000270.KS"},
            {"company_name": "NAVER", "ticker": "035420", "market": "KOSPI", "formatted_ticker": "035420.KS"},
            {"company_name": "카카오", "ticker": "035720", "market": "KOSPI", "formatted_ticker": "035720.KS"},
            {"company_name": "셀트리온", "ticker": "068270", "market": "KOSPI", "formatted_ticker": "068270.KS"},
            {"company_name": "삼성바이오로직스", "ticker": "207940", "market": "KOSPI", "formatted_ticker": "207940.KS"},
            {"company_name": "에코프로비엠", "ticker": "247540", "market": "KOSPI", "formatted_ticker": "247540.KS"},
        ]
        return pd.DataFrame(default_stocks)
    except Exception as e:
        return pd.DataFrame()
    

def find_stock_ticker(company_name, STOCK_DF, STOCK_ABBREVIATIONS):
    """회사명으로 티커 찾기"""
    if STOCK_DF.empty:
        return None

    # 정확한 매치 찾기
    exact_match = STOCK_DF[STOCK_DF['company_name'] == company_name]
    if not exact_match.empty:
        return exact_match.iloc[0]['formatted_ticker']

    # 부분 매치 찾기 (포함 관계)
    partial_match = STOCK_DF[STOCK_DF['company_name'].str.contains(company_name, na=False)]
    if not partial_match.empty:
        return partial_match.iloc[0]['formatted_ticker']

    # 약어 매치 찾기
    if company_name in STOCK_ABBREVIATIONS:
        full_name = STOCK_ABBREVIATIONS[company_name]
        return find_stock_ticker(full_name)

    return None


def get_stock_info(company_name, STOCK_DF, STOCK_ABBREVIATIONS):
    """회사명으로 종목 정보 가져오기"""
    if STOCK_DF.empty:
        return None

    # 정확한 매치 찾기
    exact_match = STOCK_DF[STOCK_DF['company_name'] == company_name]
    if not exact_match.empty:
        return exact_match.iloc[0].to_dict()

    # 부분 매치 찾기
    partial_match = STOCK_DF[STOCK_DF['company_name'].str.contains(company_name, na=False)]
    if not partial_match.empty:
        return partial_match.iloc[0].to_dict()

    # 약어 매치 찾기
    if company_name in STOCK_ABBREVIATIONS:
        full_name = STOCK_ABBREVIATIONS[company_name]
        return get_stock_info(full_name)

    return None


def remove_exact_duplicate(text: str) -> str:
    """
    문자열이 'A+A' 형태로 완벽히 중복된 경우, 'A'만 반환합니다.
    그렇지 않은 경우 원본 문자열을 그대로 반환합니다.
    """
    # 1. 문자열의 길이가 짝수인지, 그리고 비어있지 않은지 확인합니다.
    if not text or len(text) % 2 != 0:
        return text

    # 2. 문자열의 중간 지점을 계산합니다.
    midpoint = len(text) // 2

    # 3. 문자열을 정확히 반으로 나눕니다.
    first_half = text[:midpoint]
    second_half = text[midpoint:]

    # 4. 두 부분이 정확히 동일한지 확인합니다.
    if first_half == second_half:
        # 동일하다면, 앞부분(중복 제거된 부분)만 반환합니다.
        return first_half
    else:
        # 동일하지 않다면, 안전하게 원본 문자열을 반환합니다.
        return text
    

def load_config():
    """
    프로젝트 루트를 기준으로 config.yaml 파일을 불러옵니다.
    환경변수가 있으면 우선 사용하고, 없으면 config.yaml의 값을 사용합니다.
    
    Returns:
        dict: config.yaml 파일의 내용을 담은 딕셔너리 (환경변수로 오버라이드됨)
    """
    # .env 파일 로드
    load_dotenv()
    
    # 1. 현재 파일(builder.py)의 절대 경로를 가져옵니다.
    current_file_path = Path(__file__)
    
    # 2. 현재 파일이 속한 디렉토리(graph/)의 부모 디렉토리(miraeasset_festa/)를 찾습니다.
    # 이것이 프로젝트의 루트(root) 경로가 됩니다.
    project_root = current_file_path.parent.parent
    
    # 3. 프로젝트 루트 경로를 기준으로 config.yaml 파일의 경로를 조합합니다.
    config_path = project_root / "configs" / "config.yaml"
    
    # 4. 파일을 열고 yaml 형식으로 파싱합니다.
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 5. 환경변수가 있으면 우선 사용 (보안을 위해)
    if os.getenv("CLOVA_API_KEY"):
        config['api_key'] = os.getenv("CLOVA_API_KEY")
    if os.getenv("CLOVA_REQUEST_ID"):
        config['request_id'] = os.getenv("CLOVA_REQUEST_ID")
    if os.getenv("NAVER_CLIENT_ID"):
        config['naver_client_id'] = os.getenv("NAVER_CLIENT_ID")
    if os.getenv("NAVER_CLIENT_SECRET"):
        config['naver_client_secret'] = os.getenv("NAVER_CLIENT_SECRET")
    if os.getenv("HOST_IP"):
        config['host_ip'] = os.getenv("HOST_IP")
    if os.getenv("PORT"):
        config['port'] = int(os.getenv("PORT"))
        
    return config


def setup_database_engine():
    """
    YAML 설정 파일과 환경 변수에서 데이터베이스 설정을 불러와 SQLAlchemy 엔진을 생성하고 반환
    """
    try:
        load_dotenv()

        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST")
        db_port = os.getenv("DB_PORT")
        db_name = os.getenv("DB_NAME")

        database_url = (f"postgresql://{db_user}:{db_password}@"
                        f"{db_host}:{db_port}/{db_name}")
        engine = create_engine(database_url,client_encoding="utf8")
        print("Supabase 데이터베이스에 성공적으로 연결되었습니다!")
        return engine
    except Exception as e:
        print(f"데이터베이스 또는 설정 파일 오류: {e}")
        return None


class ImageServer:
    def __init__(self, host_ip: str, port: int, image_directory: str):
        """
        ImageServer 인스턴스를 초기화합니다.
        
        :param host: 외부 접속용 호스트 주소 (예: '147.47.39.102')
        :param port: 서버 포트 번호
        :param image_directory: 이미지가 실제로 저장된 폴더의 경로 (예: './results/task5')
        """
        self.host_ip = host_ip
        self.port = port
        self.image_dir = os.path.abspath(image_directory)  #  지정된 경로를 절대 경로로 변환
        self.url_prefix = 'images'  # URL에 사용할 경로 이름 (고정)
        
        self.app = Flask(__name__)
        self._setup()

    def _setup(self):
        os.makedirs(self.image_dir, exist_ok=True)
        self._register_routes()

    def _register_routes(self):
        def serve_image_route(filename):
            return send_from_directory(self.image_dir, filename)
        
        rule = f'/{self.url_prefix}/<path:filename>'
        self.app.add_url_rule(rule, endpoint="serve_image", view_func=serve_image_route)

    def _run_in_background(self):
        self.app.run(host='0.0.0.0', port=self.port)

    def start(self):
        server_thread = threading.Thread(target=self._run_in_background)
        server_thread.daemon = True
        server_thread.start()
        print(f" * 이미지 공유 서버가 '{self.image_dir}' 폴더를 대상으로 실행 중입니다.")
        print(f" * URL: http://{self.host_ip}:{self.port}/{self.url_prefix}/<filename>")

def create_shareable_url(local_image_path: str, host_ip: str, port: int):
    if not local_image_path or not os.path.exists(local_image_path):
        return None
    
    filename = os.path.basename(local_image_path)
    return f"http://{host_ip}:{port}/images/{filename}"