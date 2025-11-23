import os
import warnings
from typing import List

import pandas as pd
import pandas_ta as ta
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

warnings.filterwarnings("ignore", category=FutureWarning)

# --- 상수 정의 (Constants) ---
SOURCE_TABLE: str = "stocks_kospi_kosdaq"
TARGET_TABLE: str = "technical_signals"
RSI_LENGTH: int = 14
BBANDS_LENGTH: int = 20
AVG_VOLUME_WINDOW: int = 20
MA_LENGTHS: List[int] = [5, 10, 15, 20, 40, 50, 60, 80, 100, 120, 200, 240]
SHORT_TERM_MA: int = 5  # 골든/데드 크로스 계산용 단기 이평선
LONG_TERM_MA: int = 20  # 골든/데드 크로스 계산용 장기 이평선


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


def fetch_stock_prices(table_name: str, engine: Engine) -> pd.DataFrame | None:
    """
    데이터베이스에서 주가 데이터를 로드합니다.

    Args:
        table_name (str): 주가 데이터가 저장된 테이블 이름.
        engine (Engine): SQLAlchemy 엔진 객체.

    Returns:
        pd.DataFrame | None: 로드된 주가 데이터프레임, 실패 시 None.
    """
    print("주가 데이터 로드를 시작합니다.")
    query = (
        f'SELECT date, company, "close", volume '
        f"FROM {table_name} "
        "ORDER BY company, date"
    )
    try:
        df = pd.read_sql(query, engine, parse_dates=["date"])
        print(f"총 {len(df)}개의 레코드를 성공적으로 로드했습니다.")
        return df
    except SQLAlchemyError as e:
        print(f"데이터 로드 중 DB 오류 발생: {e}")
        return None


def calculate_signals_for_group(group: pd.DataFrame) -> pd.DataFrame:
    """
    단일 종목 그룹에 대한 모든 기술적 지표를 계산합니다.

    Args:
        group (pd.DataFrame): 날짜순으로 정렬된 단일 종목의 데이터.

    Returns:
        pd.DataFrame: 기술적 지표가 추가된 데이터프레임.
    """
    # RSI 계산
    group.ta.rsi(length=RSI_LENGTH, append=True, col_names=("rsi",))

    # 이동 평균선(MA) 계산
    for length in MA_LENGTHS:
        group.ta.sma(length=length, append=True, col_names=(f"ma{length}",))

    # 볼린저 밴드(Bollinger Bands) 계산
    bbands = group.ta.bbands(length=BBANDS_LENGTH, append=True)
    if bbands is not None and not bbands.empty:
        group["bollinger_upper"] = bbands[f"BBU_{BBANDS_LENGTH}_2.0"]
        group["bollinger_lower"] = bbands[f"BBL_{BBANDS_LENGTH}_2.0"]

    # 거래량 이동 평균 계산
    group[f"avg_volume_{AVG_VOLUME_WINDOW}d"] = (
        group["volume"].rolling(window=AVG_VOLUME_WINDOW).mean()
    )

    # 골든 크로스 / 데드 크로스 계산
    ma_short = f"ma{SHORT_TERM_MA}"
    ma_long = f"ma{LONG_TERM_MA}"
    group["golden_cross"] = (
        (group[ma_short].shift(1) < group[ma_long].shift(1))
        & (group[ma_short] > group[ma_long])
    )
    group["dead_cross"] = (
        (group[ma_short].shift(1) > group[ma_long].shift(1))
        & (group[ma_short] < group[ma_long])
    )
    return group


def clean_final_dataframe(signals_df: pd.DataFrame) -> pd.DataFrame:
    """
    계산된 지표 데이터프레임을 최종 형태로 정제합니다.
    (컬럼 선택, 결측치 처리, 데이터 타입 변환)

    Args:
        signals_df (pd.DataFrame): 기술적 지표가 포함된 데이터프레임.

    Returns:
        pd.DataFrame: 정제된 최종 데이터프레임.
    """
    final_columns = [
        "date", "company", "rsi", "bollinger_upper", "bollinger_lower",
        f"avg_volume_{AVG_VOLUME_WINDOW}d", "golden_cross", "dead_cross"
    ] + [f"ma{length}" for length in MA_LENGTHS]
    
    # 존재하지 않는 컬럼은 제외하고 선택
    existing_columns = [col for col in final_columns if col in signals_df.columns]
    final_df = signals_df[existing_columns].copy()

    # MA60이 계산되려면 최소 60일의 데이터가 필요하므로, 이 값 없는 데이터는 불완전하다고 판단하여 제거합니다.
    final_df.dropna(subset=['ma60'], inplace=True)
    
    final_df["golden_cross"] = final_df["golden_cross"].astype(bool)
    final_df["dead_cross"] = final_df["dead_cross"].astype(bool)
    
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
        print("계산된 기술적 지표를 데이터베이스에 저장합니다.")
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        print(
            f"'{table_name}' 테이블에 {len(df)}개의 레코드를 성공적으로 저장했습니다."
        )
    except SQLAlchemyError as e:
        print(f"DB 저장 중 오류 발생: {e}")


def main():
    """스크립트의 메인 실행 함수"""
    engine = get_db_engine()
    if not engine:
        return

    stock_prices_df = fetch_stock_prices(SOURCE_TABLE, engine)
    if stock_prices_df is None or stock_prices_df.empty:
        print("주가 데이터가 없어 기술적 지표를 계산할 수 없습니다.")
        return

    print("종목별 기술적 지표 계산을 시작합니다.")
    # 각 종목별로 지표 계산 함수를 적용합니다.
    signals_df = stock_prices_df.groupby("company").apply(
        calculate_signals_for_group
    )
    signals_df.reset_index(drop=True, inplace=True)
    print("모든 종목의 기술적 지표 계산을 완료했습니다.")

    final_df = clean_final_dataframe(signals_df)
    load_data_to_db(final_df, TARGET_TABLE, engine)


if __name__ == "__main__":
    main()