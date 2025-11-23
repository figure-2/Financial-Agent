from graph.builder import build_graph
from graph.llm import CLOVAStudioLLM, CompletionExecutor
from graph.utils import load_config
import json

if __name__ == "__main__":
    config = load_config()

    completion_executor = CompletionExecutor(
        host='https://clovastudio.apigw.ntruss.com',
        api_key=config['api_key'],
        request_id=config['request_id']
    )

    # LLM 인스턴스 생성
    llm_instance = CLOVAStudioLLM(completion_executor)

    # 그래프(Agent) 빌드
    app = build_graph()

    # Test할 Task가 담긴 json을 입력
    with open('./data/task5.json', 'r', encoding='utf-8') as f:
        queries = json.load(f)

    print("===== 금융 Agent 실행 =====")
    for i, instance in enumerate(queries):
        print(f"\n[Test Case {i+1}]")
        print(f"입력 쿼리: '{instance['query']}'")
        
        # Agent 실행을 위한 입력값 설정
        inputs = {"query": instance['query'],
                  "llm": llm_instance,
                  "sub_route": "",
                  "turn_count": 0}
        
        # app.invoke()를 사용하여 Agent 실행 및 최종 결과 확인
        final_state = app.invoke(inputs)
        
        print(f"최종 결과: {final_state['result']}")
        print("---------------------------------")