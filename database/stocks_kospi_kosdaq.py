import os
from datetime import datetime
from typing import List

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

# --- 상수 정의 (Constants) ---
CSV_PATH: str = "../data/korean_stocks_kospi_kosdaq.csv"
START_DATE: str = "2024-01-01"
END_DATE: str = datetime.now().strftime("%Y-%m-%d")
TABLE_NAME: str = "stocks_kospi_kosdaq"


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


def load_company_info(file_path: str) -> pd.DataFrame | None:
    """
    CSV 파일에서 기업 정보를 로드합니다.

    Args:
        file_path (str): 기업 정보가 담긴 CSV 파일 경로.

    Returns:
        pd.DataFrame | None: 로드된 기업 정보 데이터프레임, 파일이 없으면 None.
    """
    try:
        company_info = pd.read_csv(file_path, dtype={"Ticker": str})
        print(f"'{file_path}'에서 {len(company_info)}개 종목 정보를 로드했습니다.")
        return company_info
    except FileNotFoundError:
        print(f"오류: '{file_path}' 파일을 찾을 수 없습니다.")
        return None


def generate_yf_tickers(company_df: pd.DataFrame) -> pd.DataFrame:
    """
    기업 정보 데이터프레임에 Yahoo Finance 티커 컬럼('yf_ticker')을 추가합니다.
    KOSPI는 '.KS', KOSDAQ은 '.KQ' 접미사를 사용합니다.

    Args:
        company_df (pd.DataFrame): 'Ticker'와 'Market' 컬럼이 있는 데이터프레임.

    Returns:
        pd.DataFrame: 'yf_ticker' 컬럼이 추가된 데이터프레임.
    """
    company_df["yf_ticker"] = company_df.apply(
        lambda row: f"{row['Ticker']}.KS"
        if row["Market"] == "KOSPI"
        else f"{row['Ticker']}.KQ",
        axis=1,
    )
    return company_df


def fetch_stock_data(
    tickers: List[str], start: str, end: str
) -> pd.DataFrame:
    """
    Yahoo Finance로부터 지정된 기간의 개별 종목 데이터를 다운로드합니다.

    Args:
        tickers (List[str]): 다운로드할 종목 티커 리스트.
        start (str): 데이터 조회 시작일 (YYYY-MM-DD).
        end (str): 데이터 조회 종료일 (YYYY-MM-DD).

    Returns:
        pd.DataFrame: 다운로드된 종목 데이터. 데이터가 없으면 빈 DataFrame을 반환합니다.
    """
    print(f"{len(tickers)}개 종목의 데이터 다운로드를 시작합니다.")
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


def transform_stock_data(
    raw_data: pd.DataFrame, company_info: pd.DataFrame
) -> pd.DataFrame:
    """
    다운로드한 주식 데이터를 기업 정보와 병합하고 최종 형태로 변환합니다.

    Args:
        raw_data (pd.DataFrame): yfinance로부터 받은 원본 데이터.
        company_info (pd.DataFrame): 'yf_ticker'가 포함된 기업 정보.

    Returns:
        pd.DataFrame: 변환 및 병합이 완료된 최종 데이터프레임.
    """
    # Wide format에서 Long format으로 데이터를 변환합니다.
    data_long = raw_data.stack(level=1, future_stack=True).reset_index()
    data_long.rename(columns={"Ticker": "yf_ticker"}, inplace=True)
    print("데이터를 Long Format으로 변환했습니다.")

    # 기업 정보와 주가 데이터를 병합합니다.
    final_df = pd.merge(data_long, company_info, on="yf_ticker", how="left")
    
    # 컬럼명을 소문자로 변경하고 순서를 정리합니다.
    final_df.rename(
        columns={
            "Date": "date", "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
            "Company": "company", "yf_ticker": "ticker", "Market": "market",
        },
        inplace=True,
    )
    
    ordered_columns = [
        "date", "company", "ticker", "market", "open", "high", "low",
        "close", "adj_close", "volume"
    ]
    final_df = final_df[ordered_columns]
    print("기업 정보 병합 및 최종 데이터 정리를 완료했습니다.")
    return final_df


def load_data_to_db(
    df: pd.DataFrame, table_name: str, engine: Engine
) -> None:
    """
    데이터프레임을 데이터베이스의 지정된 테이블에 저장합니다.

    Args:
        df (pd.DataFrame): 저장할 데이터프레임.
        table_name (str): 데이터를 저장할 테이블의 이름.
        engine (Engine): SQLAlchemy 엔진 객체.
    """
    try:
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        print(
            f"'{table_name}' 테이블에 {len(df)}개 레코드를 성공적으로 저장했습니다."
        )
    except SQLAlchemyError as e:
        print(f"DB 저장 중 오류 발생: {e}")


def main():
    """스크립트의 메인 실행 함수"""
    engine = get_db_engine()
    if not engine:
        return

    company_info = load_company_info(CSV_PATH)
    if company_info is None:
        return

    company_info_with_tickers = generate_yf_tickers(company_info)
    yf_tickers = company_info_with_tickers["yf_ticker"].tolist()

    raw_data = fetch_stock_data(yf_tickers, START_DATE, END_DATE)

    if not raw_data.empty:
        final_df = transform_stock_data(raw_data, company_info_with_tickers)
        load_data_to_db(final_df, TABLE_NAME, engine)


if __name__ == "__main__":
    main()