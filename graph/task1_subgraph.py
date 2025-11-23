import json
import os
import re
import warnings
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

import yfinance as yf
from langgraph.graph import StateGraph, END
from sqlalchemy import text, Connection
from sqlalchemy.exc import SQLAlchemyError

from .state import AgentState
from .utils import setup_database_engine

warnings.filterwarnings("ignore")

# --- 상수 정의 (Constants) ---
# 프롬프트 상수
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(CURRENT_DIR, '..', 'resources', 'prompts')
PROMPT_FILE = "task1_prompt.txt"

# 작업 유형 (Task Types)
TASK_PRICE_INQUIRY = "PRICE_INQUIRY"
TASK_MARKET_STATISTICS = "MARKET_STATISTICS"
TASK_RANKING = "RANKING"
TASK_COMPARISON = "COMPARISON"
TASK_SPECIFIC_RANKING = "SPECIFIC_RANKING"
TASK_COMPARE_TO_AVERAGE = "COMPARE_TO_AVERAGE"
TASK_MARKET_PROPORTION = "MARKET_PROPORTION"

# 메트릭 (Metrics)
METRIC_OPEN = "open"
METRIC_HIGH = "high"
METRIC_LOW = "low"
METRIC_CLOSE = "close"
METRIC_VOLUME = "volume"
METRIC_CHANGE_RATE = "change_rate"
METRIC_MARKET_CAP = "market_cap"
METRIC_TRADING_VALUE = "trading_value"

# 통계 (Statistics)
STAT_RISING_STOCKS = "rising_stocks"
STAT_FALLING_STOCKS = "falling_stocks"
STAT_INDEX_PRICE = "index_price"
STAT_TOTAL_TRADED_STOCKS = "total_traded_stocks"

# 순위 기준 (Rank By)
RANK_BY_PRICE_INCREASE = "price_increase"
RANK_BY_PRICE_DECREASE = "price_decrease"
RANK_BY_VOLUME = "volume"
RANK_BY_PRICE_HIGH = "price_high"

# 시장 (Markets)
MARKET_KOSPI = "KOSPI"
MARKET_KOSDAQ = "KOSDAQ"

# CTE(Common Table Expression) 정의
# 전일 대비 데이터를 계산하기 위한 SQL 구문을 상수로 정의하여 중복을 제거합니다.
DAILY_DATA_CTE = """
WITH daily_data AS (
    SELECT
        "date", "company", "market", "adj_close", "volume", "open",
        LAG("adj_close", 1, "open") OVER (PARTITION BY "company" ORDER BY "date")
            AS "prev_adj_close"
    FROM stocks_kospi_kosdaq
)
"""


def format_value(value: Any, metric: str) -> Optional[str]:
    """
    데이터베이스 결과를 사람이 읽기 좋은 문자열 형태로 포맷합니다.

    Args:
        value (Any): 포맷할 값.
        metric (str): 값의 종류 (예: 'open', 'volume').

    Returns:
        Optional[str]: 포맷된 문자열. 값이 None이면 None을 반환합니다.
    """
    if value is None:
        return None
    if metric in [
        METRIC_OPEN, METRIC_HIGH, METRIC_LOW, METRIC_CLOSE,
        METRIC_TRADING_VALUE
    ]:
        return f"{int(value):,}원"
    if metric == METRIC_VOLUME:
        return f"{int(value):,}주"
    if metric == METRIC_CHANGE_RATE:
        return f"{value:+.2f}%"
    if metric in [
        STAT_RISING_STOCKS, STAT_FALLING_STOCKS, STAT_TOTAL_TRADED_STOCKS
    ]:
        return f"{int(value):,}개"
    if metric == STAT_INDEX_PRICE:
        return f"{value:.2f}"
    return str(value)


def is_trading_day(date_str: str, conn: Connection) -> Tuple[bool, str]:
    """
    주어진 날짜가 거래일인지 데이터베이스에 질의하여 확인합니다.

    Args:
        date_str (str): 확인할 날짜 ("YYYY-MM-DD").
        conn (Connection): 데이터베이스 연결 객체.

    Returns:
        Tuple[bool, str]: 거래일 여부와 메시지를 담은 튜플.
    """
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        return False, "잘못된 날짜 형식입니다. 'YYYY-MM-DD' 형식으로 입력해주세요."

    if dt.weekday() >= 5:
        return False, f"{dt.strftime('%A')} (데이터 없음)"

    query = text(
        'SELECT EXISTS (SELECT 1 FROM index_kospi_kosdaq '
        'WHERE "date" = :check_date LIMIT 1);'
    )
    try:
        result = conn.execute(query, {"check_date": date_str}).scalar()
        if not result:
            return False, "해당 날짜는 거래일이 아닙니다 (데이터 없음)."
    except SQLAlchemyError as e:
        print(f"DB 조회 오류: {e}")
        return False, "데이터베이스 조회 중 오류가 발생했습니다."

    return True, ""


def load_prompt(file_name: str) -> str:
    """
    지정된 파일명으로 resources 폴더에서 프롬프트 내용을 읽어옵니다.

    Args:
        file_name (str): 읽어올 프롬프트 파일의 이름.

    Returns:
        str: 파일에서 읽어온 프롬프트 내용.

    Raises:
        FileNotFoundError: 지정된 파일을 찾을 수 없을 때 발생합니다.
    """
    file_path = os.path.join(RESOURCES_DIR, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 파일이 없을 경우, 명확한 오류 메시지와 함께 예외를 다시 발생시킴
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

# --- Prompts ---
# 모듈 로드 시점에 프롬프트를 불러옵니다.
try:
    TASK1_PROMPT = load_prompt(PROMPT_FILE)
except FileNotFoundError as e:
    print(e)
    # 프롬프트 로딩 실패 시, 프로그램이 비정상적으로 동작하는 것을 막기 위해
    # 빈 문자열로 초기화하거나 혹은 다른 예외 처리를 할 수 있습니다.
    TASK1_PROMPT = ""


def parse_question_with_llm(state: AgentState) -> Dict[str, Any]:
    """
    LLM을 사용하여 자연어 질문을 구조화된 JSON 계획으로 변환합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'llm_plan' 키에 파싱된 계획을 담은 딕셔너리.
    """
    print("---\nTask 1: Parsing")
    query = state["query"]
    llm = state["llm"]
    
    # 모듈 레벨에서 로드된 프롬프트 템플릿을 사용합니다.
    if not TASK1_PROMPT:
        # 프롬프트 로딩에 실패한 경우 에러 처리
        print("Error: Task 1 프롬프트가 로드되지 않았습니다.")
        return {"llm_plan": None}
        
    prompt = TASK1_PROMPT.format(query=query)

    llm_plan = None
    try:
        response_str = llm.invoke(prompt)
        match = re.search(r'\{.*\}', response_str, re.DOTALL)
        if match:
            clean_json_str = match.group(0)
            llm_plan = json.loads(clean_json_str)
        else:
            raise json.JSONDecodeError("JSON 객체를 찾을 수 없습니다.", response_str, 0)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"LLM 파싱 실패: {e}")
        return {"llm_plan": None}

    return {"llm_plan": llm_plan}


# --- `execute_plan`을 위한 헬퍼 함수들 ---

def _handle_price_inquiry(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """PRICE_INQUIRY 작업 처리"""
    try:
        metric, stock_name, date = params["metric"], params["stock_name"], params["date"]
        if metric == METRIC_CHANGE_RATE:
            query = text(
                DAILY_DATA_CTE + 'SELECT (("adj_close" - "prev_adj_close") / '
                '"prev_adj_close") * 100 FROM daily_data '
                'WHERE "date" = :d AND "company" = :s AND "prev_adj_close" > 0'
            )
            result = conn.execute(query, {"d": date, "s": stock_name}).scalar()
        else:
            db_column = "adj_close" if metric == METRIC_CLOSE else metric
            query = text(
                f'SELECT "{db_column}" FROM stocks_kospi_kosdaq '
                'WHERE "company" = :s AND "date" = :d'
            )
            result = conn.execute(query, {"s": stock_name, "d": date}).scalar()

        formatted_value = format_value(result, metric)
        return (formatted_value, "") if formatted_value else \
               ("SQL 조회 실패", "해당 종목/날짜의 데이터가 없습니다.")
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "필수 파라미터가 누락되었거나 DB 오류가 발생했습니다."


def _handle_market_statistics(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """MARKET_STATISTICS 작업 처리"""
    try:
        stat, date = params['statistic'], params['date']
        market = params.get('market')
        query_params = {"d": date, "m": market}

        if stat == STAT_INDEX_PRICE:
            if not market:
                return "SQL 조회 실패", "지수 조회를 위한 시장 정보가 없습니다."
            markets = (market,) if isinstance(market, str) else tuple(market)
            query = text(
                'SELECT "close" FROM index_kospi_kosdaq '
                'WHERE "market" IN :m AND "date" = :d'
            )
            results = conn.execute(query, {"m": markets, "d": date}).fetchall()
            if results:
                formatted = ", ".join([format_value(r[0], stat) for r in results])
                return formatted, ""
            return "SQL 조회 실패", "해당 날짜의 지수 데이터가 없습니다."
        else:
            base_query = DAILY_DATA_CTE + 'SELECT COUNT(*) FROM daily_data WHERE "date" = :d'
            market_filter = ' AND "market" = :m' if market else ''
            condition = ""
            if stat == STAT_RISING_STOCKS:
                condition = ' AND "adj_close" > "prev_adj_close"'
            elif stat == STAT_FALLING_STOCKS:
                condition = ' AND "adj_close" < "prev_adj_close"'
            else:
                return "SQL 조회 실패", "알 수 없는 통계 유형입니다."

            query_str = f'{base_query}{market_filter}{condition}'
            result = conn.execute(text(query_str), query_params).scalar()
            return format_value(result, stat), ""
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "시장 통계 조회 중 오류가 발생했습니다."


def _handle_ranking(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """RANKING 작업 처리"""
    try:
        rank_by, date = params['rank_by'], params['date']
        market = params.get('market')
        top_n = params.get('top_n', 5)
        market_filter = ' AND "market" = :m' if market else ''
        query_params = {"d": date, "m": market, "top_n": top_n}
        query_str = ""

        if rank_by in [RANK_BY_PRICE_INCREASE, RANK_BY_PRICE_DECREASE]:
            order = 'DESC' if rank_by == RANK_BY_PRICE_INCREASE else 'ASC'
            query_str = (
                DAILY_DATA_CTE + 'SELECT "company" FROM daily_data '
                'WHERE "date" = :d AND "prev_adj_close" > 0 '
                f'{market_filter} ORDER BY (("adj_close" - "prev_adj_close") '
                ' / "prev_adj_close") '
                f'{order} LIMIT :top_n'
            )
        elif rank_by == RANK_BY_VOLUME:
            query_str = (
                'SELECT "company" FROM stocks_kospi_kosdaq '
                f'WHERE "date" = :d {market_filter} '
                'ORDER BY "volume" DESC LIMIT :top_n'
            )
        else:
            return "SQL 조회 실패", "알 수 없는 순위 기준입니다."

        results = conn.execute(text(query_str), query_params).fetchall()
        return (", ".join([row[0] for row in results]), "") if results else \
               ("SQL 조회 실패", "해당 조건의 종목이 없습니다.")
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "랭킹 조회 중 오류가 발생했습니다."


def _handle_comparison(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """COMPARISON 작업 처리"""
    try:
        stock_names, metric, date = params['stock_names'], params['metric'], params['date']

        if all(s in [MARKET_KOSPI, MARKET_KOSDAQ] for s in stock_names):
            query = text(
                'SELECT "market" FROM index_kospi_kosdaq WHERE "date" = :d '
                'AND "market" IN :s ORDER BY "close" DESC LIMIT 1'
            )
            result = conn.execute(query, {"d": date, "s": tuple(stock_names)}).scalar()
            return (result, "") if result else ("SQL 조회 실패", "지수 데이터가 없습니다.")

        if metric == METRIC_MARKET_CAP:
            market_caps = []
            for s_name in stock_names:
                info_q = text(
                    'SELECT "ticker", "adj_close" FROM stocks_kospi_kosdaq '
                    'WHERE "company" = :s AND "date" = :d'
                )
                stock_info = conn.execute(info_q, {"s": s_name, "d": date}).fetchone()
                if stock_info:
                    ticker, adj_close = stock_info
                    try:
                        shares = yf.Ticker(ticker).info.get('sharesOutstanding')
                        if shares and adj_close:
                            market_caps.append({'company': s_name, 'market_cap': shares * adj_close})
                    except Exception as e:
                        print(f"yfinance API 호출 실패: {ticker}, {e}")
            if not market_caps:
                return "SQL 조회 실패", "시가총액을 계산할 수 없습니다."
            winner = max(market_caps, key=lambda x: x['market_cap'])
            return f"{winner['company']} ({winner['market_cap']:,}원)", ""

        order_by_col = ""
        if metric == METRIC_CHANGE_RATE:
            order_by_col = '(("adj_close" - "prev_adj_close") / "prev_adj_close")'
            query_str = (
                DAILY_DATA_CTE + f'SELECT "company", {order_by_col} as val '
                'FROM daily_data WHERE "date" = :d AND "company" IN :s '
                'AND "prev_adj_close" > 0 ORDER BY val DESC LIMIT 1'
            )
        else:
            order_by_col = f'"{metric}"'
            query_str = (
                f'SELECT "company", {order_by_col} as val FROM stocks_kospi_kosdaq '
                'WHERE "date" = :d AND "company" IN :s '
                'ORDER BY val DESC LIMIT 1'
            )
        result = conn.execute(text(query_str), {"d": date, "s": tuple(stock_names)}).fetchone()
        if not result:
            return "SQL 조회 실패", "비교할 종목의 데이터가 없습니다."
        return f"{result[0]} ({format_value(result[1], metric)})", ""
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "비교 조회 중 오류가 발생했습니다."


def _handle_specific_ranking(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """SPECIFIC_RANKING 작업 처리"""
    try:
        stock_name, rank_by, date = params['stock_name'], params['rank_by'], params['date']
        order_by_clause = ""
        if rank_by == RANK_BY_PRICE_INCREASE:
            order_by_clause = 'ORDER BY (("adj_close" - "prev_adj_close") / "prev_adj_close") DESC'
        elif rank_by == RANK_BY_PRICE_DECREASE:
            order_by_clause = 'ORDER BY (("adj_close" - "prev_adj_close") / "prev_adj_close") ASC'
        elif rank_by == RANK_BY_VOLUME:
            order_by_clause = 'ORDER BY "volume" DESC'
        else:
            return "SQL 조회 실패", "알 수 없는 순위 기준입니다."

        query_str = (
            DAILY_DATA_CTE + f'SELECT "rank" FROM (SELECT "company", RANK() OVER ({order_by_clause}) '
            'as "rank" FROM daily_data WHERE "date" = :d AND "prev_adj_close" > 0) '
            'as ranked_data WHERE "company" = :s'
        )
        result = conn.execute(text(query_str), {"d": date, "s": stock_name}).scalar()
        return (f"{result}위", "") if result else ("SQL 조회 실패", "순위 데이터가 없습니다.")
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "특정 종목 순위 조회 중 오류가 발생했습니다."


def _handle_compare_to_average(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """COMPARE_TO_AVERAGE 작업 처리"""
    try:
        stock_name, metric, date = params['stock_name'], params['metric'], params['date']
        if metric != METRIC_CHANGE_RATE:
            return "SQL 조회 실패", "현재 등락률만 시장 평균과 비교할 수 있습니다."

        stock_q = text(
            DAILY_DATA_CTE + 'SELECT (("adj_close" - "prev_adj_close") / "prev_adj_close") '
            'FROM daily_data WHERE "date" = :d AND "company" = :s AND "prev_adj_close" > 0'
        )
        stock_rate = conn.execute(stock_q, {"d": date, "s": stock_name}).scalar()

        market_filter = ' AND "market" = :m' if params.get('market') else ''
        avg_q = text(
            DAILY_DATA_CTE + f'SELECT AVG(("adj_close" - "prev_adj_close") / "prev_adj_close") '
            f'FROM daily_data WHERE "date" = :d AND "prev_adj_close" > 0 {market_filter}'
        )
        avg_rate = conn.execute(avg_q, {"d": date, "m": params.get('market')}).scalar()

        if stock_rate is None or avg_rate is None:
            return "SQL 조회 실패", "비교 데이터가 부족합니다."

        result_text = "예" if stock_rate > avg_rate else "아니오"
        symbol = ">" if stock_rate > avg_rate else "<"
        return f"{result_text} ({stock_rate:+.2%} {symbol} 시장평균 {avg_rate:+.2%})", ""
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "시장 평균 비교 중 오류가 발생했습니다."


def _handle_market_proportion(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """MARKET_PROPORTION 작업 처리"""
    try:
        stock_name, metric, date = params['stock_name'], params['metric'], params['date']
        if metric != METRIC_VOLUME:
            return "SQL 조회 실패", "현재 거래량만 시장 내 비중을 계산할 수 있습니다."

        stock_q = text('SELECT "volume" FROM stocks_kospi_kosdaq WHERE "date" = :d AND "company" = :s')
        stock_volume = conn.execute(stock_q, {"d": date, "s": stock_name}).scalar()

        total_q = text('SELECT SUM("volume") FROM stocks_kospi_kosdaq WHERE "date" = :d')
        total_volume = conn.execute(total_q, {"d": date}).scalar()

        if stock_volume is None or total_volume is None or total_volume == 0:
            return "SQL 조회 실패", "비중 계산이 불가합니다."

        proportion = (stock_volume / total_volume) * 100
        return f"{proportion:.2f}% ({stock_volume:,}주 / {total_volume:,}주)", ""
    except (KeyError, SQLAlchemyError):
        return "SQL 조회 실패", "시장 비중 계산 중 오류가 발생했습니다."


def execute_plan(state: AgentState) -> Dict[str, Any]:
    """
    분석된 계획을 데이터베이스에 실행하여 답변을 생성합니다.
    각 작업 유형을 별도의 헬퍼 함수로 라우팅합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'generated_answer'와 'description'(선택)을 포함한 결과.
    """
    print("---\nTask 1: Execute plan")
    plan = state.get("llm_plan")
    if not plan or "task_type" not in plan or "parameters" not in plan:
        return {"generated_answer": "LLM 분석에 실패하였습니다."}

    engine = setup_database_engine()
    task = plan['task_type']
    params = plan['parameters']
    date = params.get('date')

    # 핸들러 함수 매핑
    handler_map = {
        TASK_PRICE_INQUIRY: _handle_price_inquiry,
        TASK_MARKET_STATISTICS: _handle_market_statistics,
        TASK_RANKING: _handle_ranking,
        TASK_COMPARISON: _handle_comparison,
        TASK_SPECIFIC_RANKING: _handle_specific_ranking,
        TASK_COMPARE_TO_AVERAGE: _handle_compare_to_average,
        TASK_MARKET_PROPORTION: _handle_market_proportion,
    }

    try:
        with engine.connect() as connection:
            if not date:
                return {"generated_answer": "SQL 조회 실패", "description": "날짜 정보가 없습니다."}

            is_trade_day, message = is_trading_day(date, connection)
            if not is_trade_day:
                return {"generated_answer": "SQL 조회 실패", "description": message}

            handler = handler_map.get(task)
            if handler:
                generated_answer, description = handler(connection, params)
            else:
                generated_answer = "SQL 조회 실패"
                description = f"'{task}' 유형의 작업은 아직 지원되지 않습니다."

    except SQLAlchemyError as e:
        print(f"데이터베이스 연결 또는 실행 오류: {e}")
        description = "데이터베이스 처리 중 오류가 발생했습니다."
        generated_answer = "SQL 조회 실패"
    except Exception as e:
        print(f"예상치 못한 오류 발생: {e}")
        description = "알 수 없는 오류가 발생했습니다."
        generated_answer = "SQL 조회 실패"

    return {"generated_answer": generated_answer, "description": description} if description else {"generated_answer": generated_answer}


def evaluate_and_log(state: AgentState) -> Dict[str, Any]:
    """
    처리된 질문의 결과를 기록하고 최종 `result`를 생성합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'result' 키에 최종 답변을 담은 딕셔너리.
    """
    print('\nState:', state)
    generated_answer = state.get("generated_answer", "")
    description = state.get("description", "")

    final_answer = description if generated_answer == 'SQL 조회 실패' else generated_answer

    result_details = {
        "query": state.get("query"),
        "llm_plan": state.get("llm_plan"),
        "final_answer": final_answer
    }

    print("\n--- 개별 질문 처리 로그 ---")
    print(f"질문: {result_details['query']}")
    print(f"최종 답변: {final_answer}")

    return {"result": final_answer}


def task1_graph() -> StateGraph:
    """
    금융 질의응답 작업을 위한 에이전트 그래프를 빌드하고 컴파일합니다.

    Returns:
        StateGraph: 컴파일된 LangGraph 워크플로우.
    """
    workflow = StateGraph(AgentState)

    workflow.add_node("parse_question", parse_question_with_llm)
    workflow.add_node("execute_plan", execute_plan)
    workflow.add_node("evaluate_and_log", evaluate_and_log)

    workflow.set_entry_point("parse_question")
    workflow.add_edge("parse_question", "execute_plan")
    workflow.add_edge("execute_plan", "evaluate_and_log")
    workflow.add_edge("evaluate_and_log", END)

    return workflow.compile()
