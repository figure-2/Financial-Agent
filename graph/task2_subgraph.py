import json
import os
import re
import warnings
from datetime import datetime
from typing import Any, Dict

from langgraph.graph import END, StateGraph
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .state import AgentState
from .utils import setup_database_engine

warnings.filterwarnings("ignore")

# --- 상수 정의 (Constants) ---
RESULT_LIMIT = 20  # 한 번에 반환할 최대 결과 수
DEFAULT_MARKET = "all"

# 프롬프트 상수
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(CURRENT_DIR, '..', 'resources', 'prompts')
PROMPT_FILE = "task2_prompt.txt"

# 조건 유형 (Condition Types)
COND_PRICE_CHANGE = "price_change"
COND_VOLUME_CHANGE = "volume_change"
COND_CLOSE_PRICE = "close_price"
COND_VOLUME = "volume"


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
    TASK2_PROMPT = load_prompt(PROMPT_FILE)
except FileNotFoundError as e:
    print(e)
    # 프롬프트 로딩 실패 시, 프로그램이 비정상적으로 동작하는 것을 막기 위해
    # 빈 문자열로 초기화하거나 혹은 다른 예외 처리를 할 수 있습니다.
    TASK2_PROMPT = ""
    

def parse_question_with_llm(state: AgentState) -> Dict[str, Any]:
    """
    LLM을 사용하여 자연어 질문을 구조화된 JSON 객체로 변환합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'llm_plan' 키에 파싱된 계획을 담은 딕셔너리.
    """
    print("---\nTask 2: Parsing")
    query = state["query"]
    llm = state["llm"]

    # 모듈 레벨에서 로드된 프롬프트 템플릿을 사용합니다.
    if not TASK2_PROMPT:
        # 프롬프트 로딩에 실패한 경우 에러 처리
        print("Error: Task 1 프롬프트가 로드되지 않았습니다.")
        return {"llm_plan": None}
        
    prompt = TASK2_PROMPT.format(query=query)

    llm_plan = None
    try:
        response_str = llm.invoke(prompt)
        # LLM 응답에서 JSON 객체만 정확히 추출합니다.
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


def _build_sql_query_and_params(plan: Dict[str, Any]) -> (str, Dict[str, Any]):
    """
    LLM 계획을 기반으로 SQL 쿼리와 파라미터를 생성합니다.

    Args:
        plan (Dict[str, Any]): LLM이 생성한 실행 계획.

    Returns:
        Tuple[str, Dict[str, Any]]: 생성된 SQL 쿼리 문자열과 파라미터 딕셔너리.
    """
    # CTE(Common Table Expression)를 사용하여 전일 데이터와 비교를 용이하게 합니다.
    cte = """
    WITH daily_data AS (
        SELECT "date", "company", "market", "close", "volume", "adj_close",
               LAG("adj_close", 1) OVER w AS prev_adj_close,
               LAG("volume", 1) OVER w AS prev_volume
        FROM stocks_kospi_kosdaq
        WINDOW w AS (PARTITION BY "company" ORDER BY "date")
    )
    """
    # 20개를 초과하는지 확인하기 위해 21개를 요청합니다.
    params = {'target_date': plan['date'], 'limit': RESULT_LIMIT + 1}
    where_clauses = ["CAST(\"date\" AS DATE) = :target_date"]

    if plan.get('market', DEFAULT_MARKET) != DEFAULT_MARKET:
        params['market'] = plan['market'].upper()
        where_clauses.append("\"market\" = :market")

    for i, cond in enumerate(plan['conditions']):
        col, op, val = cond['type'], cond['op'], cond['value']
        param_name = f"val_{i}"

        if col in [COND_PRICE_CHANGE, COND_VOLUME_CHANGE]:
            multiplier = 1.0 + (val / 100.0)
            params[param_name] = multiplier
            field, prev_field = ("adj_close", "prev_adj_close") \
                if col == COND_PRICE_CHANGE else ("volume", "prev_volume")
            where_clauses.append(
                f"\"{field}\" {op} ({prev_field} * :{param_name}) AND "
                f"{prev_field} IS NOT NULL AND {prev_field} > 0"
            )
        elif col in [COND_CLOSE_PRICE, COND_VOLUME]:
            params[param_name] = val
            field = "adj_close" if col == COND_CLOSE_PRICE else "volume"
            where_clauses.append(f"\"{field}\" {op} :{param_name}")

    query_string = (
        f"{cte} SELECT \"company\" FROM daily_data "
        f"WHERE {' AND '.join(where_clauses)} LIMIT :limit;"
    )
    return query_string, params


def execute_plan(state: AgentState) -> Dict[str, Any]:
    """
    LLM이 생성한 구조화된 계획에 따라 SQL 쿼리를 생성하고 실행합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'generated_answer'와 'description'(선택)을 포함한 결과.
    """
    print("---\nTask 2: Execute plan")
    plan = state.get("llm_plan")
    engine = setup_database_engine()

    if not plan or not plan.get("conditions") or not engine:
        return {
            "generated_answer": "SQL 조회 실패",
            "description": "유효한 실행 계획이 없거나 DB에 연결할 수 없습니다."
        }

    date = plan.get('date')
    if not date:
        return {
            "generated_answer": "SQL 조회 실패",
            "description": "필수 정보(날짜)가 누락되었습니다."
        }
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return {
            "generated_answer": "SQL 조회 실패",
            "description": f"날짜 형식이 올바르지 않습니다: '{date}'."
        }

    try:
        query_string, params = _build_sql_query_and_params(plan)
        query = text(query_string)

        with engine.connect() as connection:
            result_proxy = connection.execute(query, params)
            results = [row[0] for row in result_proxy]

            if not results:
                return {"generated_answer": "조건에 맞는 종목 없음"}

            answer_str = ", ".join(results[:RESULT_LIMIT])
            if len(results) > RESULT_LIMIT:
                answer_str += " 등이 있습니다."

            return {"generated_answer": answer_str}
    except (SQLAlchemyError, KeyError) as e:
        print(f"쿼리 실행 실패: {e}")
        return {
            "generated_answer": "SQL 조회 실패",
            "description": "데이터베이스 쿼리 실행 중 오류가 발생했습니다."
        }


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

    if generated_answer == "SQL 조회 실패":
        final_answer = description
    else:
        final_answer = generated_answer

    result_details = {
        "query": state.get("query"),
        "llm_plan": state.get("llm_plan"),
        "final_answer": final_answer
    }

    print("\n--- 개별 질문 처리 로그 ---")
    print(f"질문: {result_details['query']}")
    print(f"최종 답변: {final_answer}")

    return {"result": final_answer}


def task2_graph() -> StateGraph:
    """
    조건부 주식 조회를 위한 에이전트 그래프를 빌드하고 컴파일합니다.

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
