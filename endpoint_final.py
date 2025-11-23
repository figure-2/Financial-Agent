import uvicorn
from fastapi import FastAPI, Header, HTTPException, Body
from pydantic import BaseModel
from typing import Optional
# from graph.utils import load_config, ImageServer, create_shareable_url

# 기존 프로젝트의 함수 및 클래스를 임포트합니다.
# 실제 프로젝트 구조에 맞게 경로를 수정해야 할 수 있습니다.
try:
    from graph.builder import build_graph
    # llm_instance 생성을 위한 클래스를 임포트합니다.
    # 아래 경로는 예시이며, 실제 프로젝트 구조에 맞게 수정해주세요.
    from graph.llm import CompletionExecutor, CLOVAStudioLLM
    
except ImportError as e:
    print(f"오류: 필요한 모듈을 찾을 수 없습니다. ({e})")
    print("프로젝트 구조를 확인하세요. (예: clova_studio, graph 폴더가 올바른 위치에 있는지)")
    exit()

# FastAPI 애플리케이션 인스턴스 생성
app = FastAPI(
    title="Financial Agent API",
    description="LangGraph 기반 금융 정보 제공 Agent를 위한 FastAPI 엔드포인트입니다."
)


# 요청 본문(body) 모델이었던 AgentRequest 클래스는 더 이상 필요 없으므로 삭제하거나 주석 처리합니다.
# class AgentRequest(BaseModel):
#     question: str

#-- API 엔드포인트 정의 --
# 1. @app.post를 @app.get으로 변경
@app.get("/agent", summary="금융 Agent 실행", response_description="Agent의 최종 답변")
async def run_agent(
    # 2. request_body 대신 'question' 쿼리 파라미터를 직접 받도록 수정
    question: str, 
    authorization: Optional[str] = Header(None, alias="Authorization", description="Bearer {API_KEY}"),
    request_id: Optional[str] = Header(None, alias="X-NCP-CLOVASTUDIO-REQUEST-ID", description="Clova Studio Request ID")
):
    """
    ... (docstring 생략) ...
    """

    #api_key = authorization.split("Bearer ")[1]
    api_key = authorization
    print("api_key:", api_key)
    
    # 1. 헤더 유효성 검사 (기존과 동일)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="'Authorization' 헤더가 없거나 'Bearer' 타입이 아닙니다.")
    # if not request_id:
    #     raise HTTPException(status_code=400, detail="'X-NCP-CLOVASTUDIO-REQUEST-ID' 헤더가 없습니다.")



    # config = load_config()

    # # Task 5를 위한 이미지 서버 생성
    # image_server = ImageServer(host_ip=config['host_ip'], 
    #                            port=config['port'],
    #                            image_directory='./results/task5')
    # image_server.start()

    try:
        # 2. API 요청마다 동적으로 LLM 인스턴스 생성 (기존과 동일)
        completion_executor = CompletionExecutor(
            host='https://clovastudio.stream.ntruss.com', # https://clovastudio.apigw.ntruss.com
            api_key=api_key,
            request_id=request_id
        )
        llm_instance = CLOVAStudioLLM(completion_executor)

        # 3. Agent 그래프 빌드 (기존과 동일)
        agent_app = build_graph()

        # 4. Agent 실행을 위한 입력값 구성
        inputs = {
            "llm": llm_instance,
            # 3. request_body.question 대신 함수 인자로 받은 question을 바로 사용
            "query": question, 
            "sub_route": "",
            "turn_count": 0
        }

        # 5. Agent 실행 및 결과 반환 (기존과 동일)
        final_state = agent_app.invoke(inputs)
        result = final_state.get('result', '오류: 최종 결과를 찾을 수 없습니다.')

        return {"answer": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 실행 중 오류 발생: {e}")


@app.get("/", summary="API 상태 확인")
def read_root():
    return {"status": "Financial Agent API is running"}


# -- Uvicorn 서버 실행 --

if __name__ == "__main__":
    # Uvicorn 서버가 0.0.0.0:8000 에서 실행됩니다.
    print("금융 Agent API 서버를 시작합니다. 서버를 중지하려면 Ctrl+C를 누르세요.")
    uvicorn.run(app, host="0.0.0.0", port=8000)