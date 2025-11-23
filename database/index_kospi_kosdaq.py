import os
from datetime import datetime
from typing import Dict, List

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# --- 상수 정의 (Constants) ---
INDEX_TICKERS: Dict[str, str] = {
    "^KS11": "KOSPI",
    "^KQ11": "KOSDAQ",
}
START_DATE: str = "2020-01-01"
END_DATE: str = datetime.now().strftime("%Y-%m-%d")
TABLE_NAME: str = "index_kospi_kosdaq"


def get_db_engine() -> Engine | None:
    """
    환경 변수에서 데이터베이스 연결 정보를 로드하여 SQLAlchemy 엔진을 생성합니다.

    Returns:
        Engine | None: 성공 시 SQLAlchemy Engine 객체, 실패 시 None.
    """
    load_dotenv()
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")

    if not all([db_user, db_password, db_host, db_port, db_name]):
        print("오류: 데이터베이스 연결 정보가 환경변수에 올바르게 설정되지 않았습니다.")
        return None

    try:
        db_url = (
            f"postgresql://{db_user}:{db_password}@{db_host}:"
            f"{db_port}/{db_name}"
        )
        engine = create_engine(db_url)
        print(f"데이터베이스 '{db_name}'에 성공적으로 연결되었습니다.")
        return engine
    except Exception as e:
        print(f"데이터베이스 연결 중 오류 발생: {e}")
        return None


def fetch_index_data(
    tickers: List[str], start: str, end: str
) -> pd.DataFrame:
    """
    Yahoo Finance로부터 지정된 기간의 지수 데이터를 다운로드합니다.

    Args:
        tickers (List[str]): 다운로드할 지수 티커 리스트.
        start (str): 데이터 조회 시작일 (YYYY-MM-DD).
        end (str): 데이터 조회 종료일 (YYYY-MM-DD).

    Returns:
        pd.DataFrame: 다운로드된 지수 데이터. 데이터가 없으면 빈 DataFrame을 반환합니다.
    """
    print("KOSPI, KOSDAQ 지수 데이터 다운로드를 시작합니다.")
    print(f"기간: {start} ~ {end}")
    data = yf.download(
        tickers,
        start=start,
        end=end,
        progress=True,
        auto_adjust=False,
    )
    if data.empty:
        print("데이터 다운로드에 실패했거나 해당 기간에 데이터가 없습니다.")
    else:
        print("데이터 다운로드를 완료했습니다.")
    return data


def transform_data(
    raw_data: pd.DataFrame, ticker_mapping: Dict[str, str]
) -> pd.DataFrame:
    """
    다운로드한 원본 데이터를 분석하기 좋은 형태로 변환합니다.
    (Wide format -> Long format, 컬럼명 변경, 'market' 컬럼 추가 등)

    Args:
        raw_data (pd.DataFrame): yfinance로부터 받은 원본 데이터.
        ticker_mapping (Dict[str, str]): 티커와 시장 이름을 매핑한 딕셔너리.

    Returns:
        pd.DataFrame: 변환된 데이터프레임.
    """
    # Wide format에서 Long format으로 데이터를 변환합니다.
    data_long = raw_data.stack(level=1, future_stack=True).reset_index()
    data_long.rename(
        columns={"Date": "date", "Ticker": "ticker"}, inplace=True
    )
    print("데이터를 Long Format으로 변환했습니다.")

    # 시장(market) 정보를 추가합니다.
    data_long["market"] = data_long["ticker"].map(ticker_mapping)

    # 컬럼명을 소문자로 변경하고 순서를 정리합니다.
    final_df = data_long.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
        }
    )
    
    # 최종 컬럼 순서 지정
    ordered_columns = [
        "date", "ticker", "market", "open", "high", "low", 
        "close", "adj_close", "volume"
    ]
    final_df = final_df[ordered_columns]
    print("최종 데이터 프레임 정리를 완료했습니다.")
    return final_df


def load_data_to_db(
    df: pd.DataFrame, table_name: str, engine: Engine
) -> None:
    """
    변환된 데이터프레임을 데이터베이스의 지정된 테이블에 저장합니다.

    Args:
        df (pd.DataFrame): 저장할 데이터프레임.
        table_name (str): 데이터를 저장할 테이블의 이름.
        engine (Engine): SQLAlchemy 엔진 객체.
    """
    try:
        df.to_sql(
            table_name,
            engine,
            if_exists="replace",
            index=False,
        )
        print(
            f"'{table_name}' 테이블에 {len(df)}개의 레코드를 성공적으로 저장했습니다."
        )
    except SQLAlchemyError as e:
        print(f"DB 저장 중 오류 발생: {e}")
    except Exception as e:
        print(f"예상치 못한 오류가 발생했습니다: {e}")


def main():
    """스크립트의 메인 실행 함수"""
    engine = get_db_engine()
    if not engine:
        return

    yf_tickers = list(INDEX_TICKERS.keys())
    raw_data = fetch_index_data(yf_tickers, START_DATE, END_DATE)

    if not raw_data.empty:
        final_df = transform_data(raw_data, INDEX_TICKERS)
        load_data_to_db(final_df, TABLE_NAME, engine)


if __name__ == "__main__":
    main()
