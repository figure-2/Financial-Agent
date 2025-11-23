from langgraph.graph import StateGraph, END
from .state import AgentState
from .router import task_router, force_end_node

# 하위 그래프 임포트
from .task1_subgraph import task1_graph
from .task2_subgraph import task2_graph
from .task3_subgraph import task3_graph
from .task4_subgraph import task4_graph 
from .task5_subgraph import task5_graph


def should_continue_after_123(state: AgentState) -> str:
    """
    Task 1, 2, 3 실행 후 다음 경로를 결정하는 조건부 엣지입니다.
    """
    print("\n---CONDITIONAL EDGE: After Executor (1, 2, 3)---")
    if state['generated_answer'] == "SQL 조회 실패":
        # 결과가 '데이터 없음' 이면 Task 4로 이동
        print(f"{state['description']} -> Task 4로 이동")
        return "route_to_task_4"
    else:
        # 정상 처리 시 워크플로우 종료
        print("분기 조건: 정상 처리 -> 종료")
        return END
    

def route_after_clarification(state: AgentState) -> str:
    """하위 그래프 실행 후 다음 경로를 결정합니다."""
    print("\n---CONDITIONAL EDGE: After Clarification Sub-graph---")

    # turn_count는 subgraph_clarification의 rewrite_node에서 1씩 증가합니다.
    turn_count = state.get('turn_count', 0) 

    if state['result'] == "__REWRITE_SUCCESS__":
        if turn_count < 2:
            print(f"분기 조건: 질문 재작성 성공 (현재 {turn_count}회) -> 메인 라우터로 복귀 (Loop)")
            return "resubmit_to_router"
        else:
            print(f"분기 조건: 최대 반복 횟수({turn_count}회) 도달 -> 강제 종료")
            return "force_end" # 강제 종료를 위한 새로운 경로
    else:
        # 역질문이 생성되었거나, 실패한 경우 워크플로우 종료
        print("분기 조건: 역질문 생성 또는 실패 -> 종료")
        return END


def build_graph():
    """
    LangGraph의 StateGraph를 사용하여 Agent 워크플로우를 구축하고 컴파일합니다.
    """

    # 하위 그래프 빌드
    task1_chain = task1_graph()
    task2_chain = task2_graph()
    task3_chain = task3_graph()
    task4_chain = task4_graph()
    task5_chain = task5_graph()

    # Agent 상태 정의
    workflow = StateGraph(AgentState)

    # 1. 노드 추가
    workflow.add_conditional_edges(
        "task_router",
        # state에서 'task_route' 값을 읽어와 라우팅 경로로 사용
        lambda state: state["task_route"],
        {
            "route_to_task_1": "task_executor_1",
            "route_to_task_2": "task_executor_2",
            "route_to_task_3": "task_executor_3",
            "route_to_task_5": "task_executor_5",
        }
    )

    # 하위 그래프 자체를 하나의 노드로 추가
    workflow.add_node("task_router", task_router)
    workflow.add_node("task_executor_1", task1_chain)
    workflow.add_node("task_executor_2", task2_chain)
    workflow.add_node("task_executor_3", task3_chain)
    workflow.add_node("task_executor_4", task4_chain)
    workflow.add_node("task_executor_5", task5_chain)
    workflow.add_node("force_end_node", force_end_node) # 강제 종료 노드 추가

    # 2. 엣지 설정
    # 워크플로우 시작점 설정
    workflow.set_entry_point("task_router")
    
    # 조건부 엣지: Executor(1,2,3)의 결과에 따라 분기
    workflow.add_conditional_edges(
        "task_executor_1",
        should_continue_after_123,
        {
            "route_to_task_4": "task_executor_4",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "task_executor_2",
        should_continue_after_123,
        {
            "route_to_task_4": "task_executor_4",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "task_executor_3",
        should_continue_after_123,
        {
            "route_to_task_4": "task_executor_4",
            END: END
        }
    )

    workflow.add_conditional_edges(
        "task_executor_4", 
        route_after_clarification, 
        {
            "resubmit_to_router": "task_router", # 재작성 성공 시 다시 라우터로
            "force_end": "force_end_node", 
            END: END
        }
    )

    # 일반 엣지: Task 4와 5 실행 후에는 항상 종료
    #workflow.add_edge("task_executor_4", END)
    workflow.add_edge("force_end_node", END) # 강제 종료 노드는 항상 END로 연결
    workflow.add_edge("task_executor_5", END)

    # 3. 그래프 컴파일
    app = workflow.compile()
    
    # 생성된 그래프의 다이어그램을 이미지 파일로 저장 (디버깅에 유용)
    # app.get_graph().draw_mermaid_png(output_file_path="graph_diagram.png")
    
    return app