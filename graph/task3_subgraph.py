import json
import os
import re
import warnings
from typing import Any, Dict, Tuple

from langgraph.graph import END, StateGraph
from sqlalchemy import text, Connection
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .state import AgentState
from .utils import setup_database_engine

warnings.filterwarnings("ignore")

# --- 상수 정의 (Constants) ---
RESULT_LIMIT = 20
MAX_SEARCH_DAYS = 30

# 프롬프트 상수
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
RESOURCES_DIR = os.path.join(CURRENT_DIR, '..', 'resources', 'prompts')
PROMPT_FILE = "task3_prompt.txt"

# 작업 유형 (Task Types)
TASK_DETECT_SIGNAL = "DETECT_SIGNAL"
TASK_FIND_SIGNAL_PERIOD = "FIND_SIGNAL_PERIOD"
TASK_COUNT_SIGNAL_PERIOD = "COUNT_SIGNAL_PERIOD"

# 신호 유형 (Signal Types)
SIGNAL_RSI_OVERBOUGHT = "RSI_OVERBOUGHT"
SIGNAL_RSI_OVERSOLD = "RSI_OVERSOLD"
SIGNAL_VOLUME_SURGE = "VOLUME_SURGE"
SIGNAL_MA_BREAKOUT = "MA_BREAKOUT"
SIGNAL_BBAND_UPPER_TOUCH = "BBAND_UPPER_TOUCH"
SIGNAL_BBAND_LOWER_TOUCH = "BBAND_LOWER_TOUCH"
SIGNAL_GOLDEN_CROSS = "GOLDEN_CROSS"
SIGNAL_DEAD_CROSS = "DEAD_CROSS"
SIGNAL_CROSS_INTEGRATED = "CROSS_INTEGRATED"


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
    TASK3_PROMPT = load_prompt(PROMPT_FILE)
except FileNotFoundError as e:
    print(e)
    # 프롬프트 로딩 실패 시, 프로그램이 비정상적으로 동작하는 것을 막기 위해
    # 빈 문자열로 초기화하거나 혹은 다른 예외 처리를 할 수 있습니다.
    TASK3_PROMPT = ""


def parse_question_with_llm(state: AgentState) -> Dict[str, Any]:
    """
    LLM을 사용하여 기술적 분석 질문을 구조화된 JSON 계획으로 변환합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'llm_plan' 키에 파싱된 계획을 담은 딕셔너리.
    """
    print("---\nTask 3: Parsing")
    query = state["query"]
    llm = state["llm"]

    # 모듈 레벨에서 로드된 프롬프트 템플릿을 사용합니다.
    if not TASK3_PROMPT:
        # 프롬프트 로딩에 실패한 경우 에러 처리
        print("Error: Task 1 프롬프트가 로드되지 않았습니다.")
        return {"llm_plan": None}
        
    prompt = TASK3_PROMPT.format(query=query)

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


# --- `execute_plan`을 위한 헬퍼 함수들 ---

def _handle_detect_signal(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """DETECT_SIGNAL 작업 처리"""
    try:
        date = params['date']
        signal = params.get('signal_type')
        th = params.get('thresholds', {})
        query_text, query_params = "", {}

        if signal == SIGNAL_RSI_OVERBOUGHT:
            rsi_val = th.get('rsi', 70)
            query_text = (
                'SELECT company, rsi FROM technical_signals '
                'WHERE date = :date AND rsi >= :rsi_val '
                'ORDER BY rsi DESC LIMIT :limit'
            )
            query_params = {"date": date, "rsi_val": rsi_val, "limit": RESULT_LIMIT + 1}
        # ... 다른 signal 유형에 대한 쿼리 생성 로직 추가 ...
        else:
            return "SQL 조회 실패", "알 수 없는 신호 유형입니다."

        results = conn.execute(text(query_text), query_params).fetchall()
        if not results:
            return "조건에 맞는 종목 없음", ""

        answer_list = [f"{r.company}(RSI:{r.rsi:.1f})" for r in results[:RESULT_LIMIT]]
        answer = ", ".join(answer_list)
        if len(results) > RESULT_LIMIT:
            answer += " 등이 있습니다."
        return answer, ""

    except (KeyError, SQLAlchemyError) as e:
        print(f"Signal detection error: {e}")
        return "SQL 조회 실패", "신호 탐색 중 오류가 발생했습니다."


def _handle_count_signal_period(
    conn: Connection, params: Dict[str, Any]
) -> Tuple[str, str]:
    """COUNT_SIGNAL_PERIOD 작업 처리"""
    try:
        stock_name = params["stock_name"]
        start_date = params["start_date"]
        end_date = params["end_date"]
        signal_type = params.get('signal_type')
        q_params = {"stock": stock_name, "start": start_date, "end": end_date}

        if signal_type == SIGNAL_CROSS_INTEGRATED:
            gc_q = text(
                "SELECT COUNT(*) FROM technical_signals WHERE company = :stock "
                "AND date BETWEEN :start AND :end AND golden_cross = TRUE"
            )
            dc_q = text(
                "SELECT COUNT(*) FROM technical_signals WHERE company = :stock "
                "AND date BETWEEN :start AND :end AND dead_cross = TRUE"
            )
            gc_count = conn.execute(gc_q, q_params).scalar() or 0
            dc_count = conn.execute(dc_q, q_params).scalar() or 0
            if gc_count == 0 and dc_count == 0:
                return "없음", ""
            return f"데드크로스 {dc_count}번, 골든크로스 {gc_count}번", ""
        else:
            signal_col = 'golden_cross' if signal_type == SIGNAL_GOLDEN_CROSS else 'dead_cross'
            query = text(
                f'SELECT COUNT(*) FROM technical_signals WHERE company = :stock '
                f'AND date BETWEEN :start AND :end AND {signal_col} = TRUE'
            )
            count = conn.execute(query, q_params).scalar() or 0
            return f"{count}번" if count > 0 else "없음", ""

    except (KeyError, SQLAlchemyError) as e:
        print(f"Signal count error: {e}")
        return "SQL 조회 실패", "신호 횟수 계산 중 오류가 발생했습니다."


def execute_plan(state: AgentState) -> Dict[str, Any]:
    """
    분석된 계획에 따라 DB를 조회하고, 결과를 생성합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태.

    Returns:
        Dict[str, Any]: 'generated_answer'와 'description'(선택)을 포함한 결과.
    """
    print("---\nTask 3: Execute plan")
    plan = state.get("llm_plan")
    engine = setup_database_engine()

    if not isinstance(plan, dict) or not plan.get('parameters'):
        return {
            "generated_answer": "SQL 조회 실패",
            "description": "질문의 의도를 파악할 수 없습니다."
        }

    task = plan.get('task_type')
    params = plan.get('parameters', {})
    generated_answer = "알 수 없는 작업 유형입니다."
    description = ""

    try:
        with engine.connect() as connection:
            if task == TASK_DETECT_SIGNAL:
                generated_answer, description = _handle_detect_signal(connection, params)
            elif task == TASK_COUNT_SIGNAL_PERIOD:
                generated_answer, description = _handle_count_signal_period(connection, params)
            # 다른 task 유형에 대한 핸들러 호출
            else:
                description = f"'{task}' 유형의 작업은 아직 지원되지 않습니다."
                generated_answer = "SQL 조회 실패"

    except OperationalError:
        description = "데이터베이스 조회 시간이 초과되었습니다."
        generated_answer = "SQL 조회 실패"
    except Exception as e:
        print(f"예상치 못한 오류 발생: {e}")
        description = "알 수 없는 오류가 발생했습니다."
        generated_answer = "SQL 조회 실패"

    if description:
        return {"generated_answer": generated_answer, "description": description}
    return {"generated_answer": generated_answer}


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


def task3_graph() -> StateGraph:
    """
    기술적 분석 질의응답을 위한 에이전트 그래프를 빌드하고 컴파일합니다.

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
