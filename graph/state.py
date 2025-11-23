from typing import TypedDict, Literal, Dict, Any, Optional, List


class AgentState(TypedDict):
    """
    Agent의 상태를 정의하는 TypedDict입니다.
    그래프의 노드 간에 데이터가 이 구조를 통해 전달됩니다.

    Attributes:
        query (str): 사용자의 원본 입력 쿼리
        task_number (int): Task Router에 의해 분류된 작업 번호
        result (str): Task Executor에 의해 생성된 최종 또는 중간 결과
    """
    query: str
    task_number: int
    result: str
    task_route: str
    
    # State에 LLM Instance 정의
    llm: Any

    # Task1-3 하위 그래프 내 라우팅을 위한 상태 추가
    llm_plan: Optional[Dict[str, Any]]
    generated_answer: Optional[str]
    connection: Any
    description: Optional[str]

    # Task4 하위 그래프 내 라우팅을 위한 상태 추가
    sub_route: Literal["", "Rewriting", "Clarify"]
    turn_count: int  # <--- 이 줄을 추가하세요.
    
    # Task5 하위 그래프 내 라우팅을 위한 상태 추가
    error: Optional[str]
    transaction_records: List[Dict[str, Any]]
    my_data: Optional[Dict[str, Any]]
    preprocessed_data: Optional[Dict[str, Any]]
    identified_risk_pattern: Optional[Dict[str, Any]]
    triggering_trade_info: Optional[Dict[str, Any]]
    is_verified: bool
    search_queries: List[str] # 복수형으로 변경
    search_results_korean: Optional[List[Dict[str, Any]]]
    selected_document_url: Optional[str]
    news_analysis_result: Optional[Dict[str, Any]]
    extracted_important_sentence: Optional[str]
    screenshot_image_base64: Optional[str]
    screenshot_image_path: Optional[str]
    final_alert_message: str
    run_id: Optional[str]