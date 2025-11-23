from .state import AgentState
import re


# 데이터베이스(DB) 연결을 시뮬레이션하기 위한 스켈레톤 코드
# 실제 구현 시에는 이곳에 DB 조회 로직 넣기
db = {
    "삼성전자": {"종가": "85,000", "등락률": "+1.2%", "RSI": "65.0"},
    "카카오": {"종가": "45,000", "등락률": "-0.5%", "RSI": "48.5"},
}


def task_router(state: AgentState) -> dict:
    """
    [Step 1: Task Router]
    사용자의 쿼리를 기반으로 Task 번호를 결정합니다.
    """
    query = state['query']
    task_number = 0

    # 1차 필터: Task5 (매매 패턴 분석) - 최우선으로 추가
    if '매매 패턴을 분석' in query:
        task_number = 5

    # 2차 필터: Task3 (기술적 분석)
    task3_keywords = [
        'RSI', '이동평균', '볼린저', '골든크로스', '데드크로스', 
        '과매수', '과매도', '평균 대비'
    ]
    if any(keyword in query for keyword in task3_keywords):
        task_number = 3

    # 3차 필터: Task2 (조건 검색)
    task2_keywords = ['종목을 모두 보여줘', '이면서', '이고 ']
    if any(keyword in query for keyword in task2_keywords):
        task_number = 2
    if re.search(r'(\d+[%원]\s*(이상|이하)인\s+종목|거래량이\s+전날대비)', query):
        task_number = 2

    # 4차 필터: Task1 (정보/순위 조회)
    task1_patterns = [
        r'의\s+20\d{2}-\d{2}-\d{2}\s+(종가|시가|고가|저가|등락률)',
        r'(KOSPI|KOSDAQ)에서\s+[\w\s]+\s*의\s+20\d{2}-\d{2}-\d{2}',
        r'에서\s+(KOSPI|KOSDAQ)에서\s+(거래량|상승률|하락률|가격)',
        r'시장에서\s+가장\s+(비싼|거래량이 많은)\s+종목은\?',
        r'거래량\s+기준\s+상위',
        r'KOSPI\s+지수는\?',
        r'전체\s+시장\s+거래대금은\?',
        r'에\s+(상승|하락)한\s+종목은\s+몇\s+개인가\?',
        r'KOSPI\s+시장에\s+거래된\s+종목\s+수는\?'
    ]
    if any(re.search(pattern, query) for pattern in task1_patterns):
        task_number = 1
    
    # 위 경우에 해당하지 않으면 SQL 조회를 위해 간단한 Rule로 Task 임시 배정
    if task_number == 0:
        if '종가' in query:
            task_number = 1
        elif '등락률' in query:
            task_number = 2
        elif 'RSI' in query:
            task_number = 3
        else:
            # 위에도 해당하지 않으면 일단, task 1번 할당
            task_number = 1
    
    # 경로를 결정하는 문자열 생성
    route = f"route_to_task_{task_number}"
    print(f"쿼리 분석 결과: Task {task_number}\n")
    
    return {"task_route": route}


def force_end_node(state: AgentState) -> dict:
    """최대 반복 횟수 초과 시 호출되는 노드."""
    return {"result": "질문을 명확히 하는 데 실패했습니다. (최대 반복 횟수 초과)"}