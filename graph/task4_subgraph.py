# workspace/graph/task4_subgraph.py
import os
from langgraph.graph import StateGraph, END
from .state import AgentState

# --- Constants ---
# 경로 관련 상수
# 이 스크립트 파일이 있는 디렉토리의 절대 경로
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# prompts 리소스 폴더 경로
PROMPTS_DIR = os.path.join(CURRENT_DIR, '..', 'resources', 'prompts', 'task4')

# 프롬프트 파일명 상수
TASK4_ROUTER_PROMPT_FILE = "task4_router_prompt.txt"
REWRITE_PROMPT_FILE = "rewrite_prompt.txt"
CLARIFY_PROMPT_FILE = "clarify_prompt.txt"

# 라우팅 경로 및 결과 플래그 상수
ROUTE_REWRITING = "Rewriting"
ROUTE_CLARIFY = "Clarify"
REWRITE_SUCCESS_FLAG = "__REWRITE_SUCCESS__"
REWRITE_FAIL_FLAG = "__REWRITE_FAIL__"

# 모호성 유형 상수
REWRITE_TYPES = {'1', '2'}  # 재작성이 필요한 모호성 유형
CLARIFY_TYPES = {'3', '4'}  # 사용자에게 되물어야 하는 모호성 유형

# --- Prompts ---

# --- Helper Functions ---
def load_prompt(file_name: str) -> str:
    """
    지정된 파일명으로 prompts 폴더에서 프롬프트 내용을 읽어옵니다.

    Args:
        file_name (str): 읽어올 프롬프트 파일의 이름.

    Returns:
        str: 파일에서 읽어온 프롬프트 내용.

    Raises:
        FileNotFoundError: 지정된 파일을 찾을 수 없을 때 발생합니다.
    """
    file_path = os.path.join(PROMPTS_DIR, file_name)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # 파일이 없을 경우, 명확한 오류 메시지와 함께 예외를 다시 발생시킴
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

# 프롬프트 로딩
TASK4_ROUTER_PROMPT = load_prompt(TASK4_ROUTER_PROMPT_FILE)
REWRITE_PROMPT = load_prompt(REWRITE_PROMPT_FILE)
CLARIFY_PROMPT = load_prompt(CLARIFY_PROMPT_FILE)


# --- Nodes ---
def task4_router_node(state: AgentState) -> dict:
    """
    쿼리의 모호성 유형을 판단하여 'Rewriting' 또는 'Clarify' 경로를 결정합니다.

    LLM을 사용하여 쿼리를 분석하고, 모호성 유형에 따라 다음 단계를 지정합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태. 'query'와 'llm'을 포함합니다.

    Returns:
        dict: 'sub_route' 키에 다음 노드의 이름을 담은 딕셔너리.
    """
    print("---\nSUB-NODE: Clarify Router---")
    llm = state['llm']
    query = state['query']

    if not llm:
        # LLM이 없는 경우, 사용자에게 되묻는 경로로 안전하게 처리
        return {"sub_route": ROUTE_CLARIFY, "result": "LLM이 없어 질문을 명확히 할 수 없습니다."}

    prompt = TASK4_ROUTER_PROMPT.format(query=query)
    print(f"task 4 query : {query}")
    response = llm.invoke(prompt).strip()
    print(f"모호성 분석 결과: {response}")

    # LLM의 응답(예: "1, 2, 4")에서 발견된 모호성 유형을 확인
    detected_types = set(response)
    if any(t in REWRITE_TYPES for t in detected_types):
        print(f"경로 결정: {ROUTE_REWRITING}")
        return {"sub_route": ROUTE_REWRITING}
    elif any(t in CLARIFY_TYPES for t in detected_types):
        print(f"경로 결정: {ROUTE_CLARIFY}")
        return {"sub_route": ROUTE_CLARIFY}
    else:
        # LLM이 명확한 유형을 찾지 못한 경우, 되묻는 것을 기본값으로 처리
        print(f"경로 결정: 유형 불명확 -> {ROUTE_CLARIFY}")
        return {"sub_route": ROUTE_CLARIFY}


def rewrite_query_node(state: AgentState) -> dict:
    """
    모호한 질문을 명확하게 재작성합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태. 'query'와 'llm'을 포함합니다.

    Returns:
        dict: 재작성된 'query', 처리 결과 'result', 증가된 'turn_count'를 담은 딕셔너리.
    """
    print("---\nSUB-NODE: Rewrite Query---")
    llm = state['llm']
    query = state['query']

    if not llm:
        return {"query": query, "result": REWRITE_FAIL_FLAG}

    prompt = REWRITE_PROMPT.format(query=query)
    rewritten_query = llm.invoke(prompt).replace("명확한 질문 :", "").strip()
    print(f"재작성된 질문: {rewritten_query}")

    current_turn = state.get('turn_count', 0)

    # 메인 그래프가 루프를 돌 수 있도록 특별한 결과 플래그와 함께 반환
    return {
        "query": rewritten_query,
        "result": REWRITE_SUCCESS_FLAG,
        "turn_count": current_turn + 1
    }


def clarify_question_node(state: AgentState) -> dict:
    """
    사용자에게 모호한 부분을 되물을 질문을 생성합니다.

    Args:
        state (AgentState): 현재 에이전트의 상태. 'query'와 'llm'을 포함합니다.

    Returns:
        dict: 생성된 역질문을 'result' 키에 담아 반환합니다.
    """
    print("---\nSUB-NODE: Clarify Question---")
    llm = state['llm']
    query = state['query']

    if not llm:
        return {"result": "질문이 모호합니다. 좀 더 구체적으로 질문해주세요."}

    prompt = CLARIFY_PROMPT.format(query=query)
    clarification_question = llm.invoke(prompt)
    print(f"생성된 역질문: {clarification_question}")

    return {"result": clarification_question}


# --- Graph Builder ---
def task4_graph():
    """
    모호성 처리를 위한 하위 그래프(subgraph)를 빌드하고 컴파일합니다.

    Returns:
        CompiledGraph: LangGraph로 컴파일된 실행 가능한 그래프 객체.
    """
    sub_workflow = StateGraph(AgentState)

    sub_workflow.add_node("task4_router", task4_router_node)
    sub_workflow.add_node("rewrite_query", rewrite_query_node)
    sub_workflow.add_node("clarify_question", clarify_question_node)

    sub_workflow.set_entry_point("task4_router")

    # task4_router 노드의 결과('sub_route')에 따라 다음 노드를 결정
    sub_workflow.add_conditional_edges(
        "task4_router",
        lambda state: state["sub_route"],
        {
            ROUTE_REWRITING: "rewrite_query",
            ROUTE_CLARIFY: "clarify_question"
        }
    )

    # Rewriting 또는 Clarify 노드를 실행한 후에는 하위 그래프를 종료
    sub_workflow.add_edge("rewrite_query", END)
    sub_workflow.add_edge("clarify_question", END)

    return sub_workflow.compile()