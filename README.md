#  Financial-agent

---

##  목차

1. [Agent 구조도](#agent-structure)
2. [Agent 평가 방법](#agent-usage)
3. [주요 기능 및 API 호출 예시](#main-features)
    - [Task 1: 단순 조회](#task1)
    - [Task 2: 조건 검색](#task2)
    - [Task 3: 시그널 감지](#task3)
    - [Task 4: 모호한 의미 해석](#task4)
    - [Task 5: 집중 투자 위험 알림](#task5)
4. [Local 환경 실행 가이드](#local-setup)

---


<a id="agent-usage"></a>
##  Agent 평가 방법

배포된 API 엔드포인트를 통해 Agent의 기능을 테스트하고 성능을 평가할 수 있습니다.

### API Endpoint
```
http://211.188.58.134:8000/agent
```

### API 호출 예시
참고 파일 : `eval.py`

```python
import requests

# API 설정
URL = 'http://211.188.58.134:8000/agent'
API_KEY = 'nv-89f...'  # 실제 평가시 미래에셋증권 평가용 API KEY 사용
REQUEST_ID = '23ef...'  # 요청별 고유 ID

# 헤더 설정
headers = {
    'Authorization': f'Bearer {API_KEY}',
    'X-NCP-CLOVASTUDIO-REQUEST-ID': f'{REQUEST_ID}'
}

# 요청 파라미터
params = {
    'question': '거래량이 전날 대비 15% 이상 오른 종목을 모두 보여줘'
}

# API 호출
response = requests.get(URL, headers=headers, params=params)
print(response.json())  # {'answer': '애드바이오텍, 아난티, 엠에프엠코리아 입니다.'}
```

---

<a id="main-features"></a>
##  주요 기능 및 API 호출 예시

Agent가 수행할 수 있는 5가지 핵심 기능과 실제 API 호출 예시입니다.

<a id="task1"></a>
###  Task 1: 단순 조회
주식 시장의 다양한 금융 정보를 자연어 질문으로 조회할 수 있는 기능입니다.  
복잡한 SQL 쿼리를 작성할 필요 없이 일상적인 언어로 데이터베이스의 정보에 접근할 수 있습니다.

#### 1. 자연어 파싱 프로세스

```python
def parse_question_with_llm(state: AgentState) -> Dict[str, Any]:
    # LLM을 통해 자연어를 구조화된 JSON으로 변환
    # 지원 task_type: PRICE_INQUIRY, MARKET_STATISTICS, RANKING, 
    #               COMPARISON, SPECIFIC_RANKING, COMPARE_TO_AVERAGE, 
    #               MARKET_PROPORTION
```

#### 2. 실행 계획 처리

```python
def execute_plan(state: AgentState) -> Dict[str, Any]:
    # 분석된 JSON 계획을 SQL 쿼리로 변환하여 데이터베이스 조회 실행
    # 거래일 검증, CTE를 활용한 등락률 계산, 결과 포맷팅 수행
    # 각 task_type별 쿼리 생성 및 실행 로직 처리
```

#### 3. 지원되는 작업 유형 및 사용 예제

| Task Type | 설명 | 사용 사례 |
|-----------|------|----------|
| `PRICE_INQUIRY` | 특정 종목의 가격 정보 조회 | 시가, 고가, 저가, 종가, 등락률 |
| `MARKET_STATISTICS` | 시장 전체 통계 정보 | 상승/하락 종목 수, 지수 가격 |
| `RANKING` | 조건별 종목 순위 | 상승률/하락률/거래량 상위 종목 |
| `COMPARISON` | 복수 종목 간 비교 | 가격, 시가총액 비교 |
| `SPECIFIC_RANKING` | 특정 종목의 순위 확인 | 전체 시장 내 순위 |
| `COMPARE_TO_AVERAGE` | 시장 평균 대비 비교 | 개별 종목 vs 시장 평균 |
| `MARKET_PROPORTION` | 시장 내 비중 계산 | 전체 시장 대비 비율 |

- 가격 조회 (`PRICE_INQUIRY`)
```python
질문: "동부건설우의 2024-11-06 시가는?"
JSON 변환: {
    "task_type": "PRICE_INQUIRY",
    "parameters": {
        "date": "2024-11-06",
        "stock_name": "동부건설우",
        "metric": "open"
    }
}
답변: "15,400원"
```

- 시장 통계 (`MARKET_STATISTICS`)

```python
질문: "2025-03-15에 KOSDAQ에서 상승한 종목은 몇 개?"
JSON 변환: {
    "task_type": "MARKET_STATISTICS",
    "parameters": {
        "date": "2025-03-15",
        "market": "KOSDAQ",
        "statistic": "rising_stocks"
    }
}
답변: "487개"
```

- 순위 조회 (`RANKING`)
```python
질문: "2025-01-20에서 KOSPI에서 상승률 높은 종목 5개는?"
JSON 변환: {
    "task_type": "RANKING",
    "parameters": {
        "date": "2025-01-20",
        "market": "KOSPI",
        "rank_by": "price_increase",
        "top_n": 5
    }
}
답변: "삼성전자, SK하이닉스, 현대차, POSCO홀딩스, LG화학"
```

- 시가총액 비교 (`COMPARISON`)
```python
질문: "2025-04-07에 카카오와 현대차 중 시가총액이 더 큰 종목은?"
JSON 변환: {
    "task_type": "COMPARISON",
    "parameters": {
        "date": "2025-04-07",
        "stock_names": ["카카오", "현대차"],
        "metric": "market_cap"
    }
}
답변: "현대차 (45,234,567,890,123원)"
```

- 특정 종목 순위 (`SPECIFIC_RANKING`)
```python 
질문: "2025-02-03에 셀트리온의 거래량 순위는?"
JSON 변환: {
    "task_type": "SPECIFIC_RANKING",
    "parameters": {
        "date": "2025-02-03",
        "stock_name": "셀트리온",
        "rank_by": "volume"
    }
}
답변: "12위"
```

- 시장 평균 대비 비교 (`COMPARE_TO_AVERAGE`)
```python
질문: "2024-11-18에 카카오의 등락률이 시장 평균보다 높은가?"
JSON 변환: {
    "task_type": "COMPARE_TO_AVERAGE",
    "parameters": {
        "date": "2024-11-18",
        "stock_name": "카카오",
        "metric": "change_rate"
    }
}
답변: "예 (+3.45% > 시장평균 +1.23%)"
```

- 시장 비중 (`MARKET_PROPORTION`)
```python
질문: "2024-07-22에 NAVER의 거래량이 전체 시장 거래량의 몇 %인가?"
JSON 변환: {
    "task_type": "MARKET_PROPORTION",
    "parameters": {
        "date": "2024-07-22",
        "stock_name": "NAVER",
        "metric": "volume"
    }
}
답변: "2.34% (1,234,567주 / 52,768,900주)"
```

#### 4. 에러 처리

| 에러 상황 | 검증 방법 | 반환 메시지 |
|-----------|------|----------|
| `주말/공휴일` | `dt.weekday() >= 5` | "토요일 (데이터 없음)" |
| `데이터 없음` | DB 조회 결과 NULL | "해당 날짜 데이터 없음" |
| `LLM 파싱 실패` | JSON 디코딩 예외 | "LLM 분석에 실패하였습니다" |
| `종목 미존재` | DB 조회 결과 없음 | "해당 종목 데이터가 없습니다" |
| `알 수 없는 작업` | task_type 불일치 | "알 수 없는 작업 유형입니다" |

#### 5. 데이터 포맷팅

```python
def format_value(value: Any, metric: str) -> Optional[str]:
    # 가격: "15,400원"
    # 거래량: "1,234,567주"
    # 등락률: "+3.45%"
    # 지수: "2,456.78"
```
  
---

<a id="task2"></a>
###  Task 2: 조건 검색
복잡한 조건을 만족하는 종목들을 필터링하여 검색하는 고급 기능입니다.  
여러 조건을 AND 연산으로 결합하여 정교한 검색이 가능하며, 등락률과 거래량 변동률 같은 동적 지표도 지원합니다.

#### 1. 자연어 파싱 프로세스

```python
def parse_question_with_llm(state: AgentState) -> Dict[str, Any]:
    # LLM을 사용하여 자연어 질문을 구조화된 JSON 객체로 변환
    # 날짜, 시장, 조건을 추출하여 JSON 형식으로 구조화
    # 수치는 단위를 제거하고 숫자만 추출 (300% → 300, 10만원 → 100000)
```

#### 2. 실행 계획 처리

```python
def execute_plan(state: AgentState) -> Dict[str, Any]:
    # LLM이 생성한 구조화된 계획에 따라 SQL 쿼리를 생성하고 실행
    # CTE를 활용한 전일 대비 계산, 동적 WHERE 절 생성
    # 결과가 20개를 초과할 경우 "등이 있습니다" 추가
```

#### 3. 지원되는 작업 유형 및 사용 예제

| Task Type | 설명 | 사용 사례 |
|-----------|------|----------|
| `price_change` | 전일 대비 등락률 (%) | (현재가 - 전일가) / 전일가 × 100 |
| `volume_change` | 전일 대비 거래량 변동률 (%) | (현재거래량 - 전일거래량) / 전일거래량 × 100 |
| `close_price` | 종가 (원) | 수정종가 직접 비교 |
| `volume` | 거래량 (주) | 거래량 직접 비교 |

- 상승/하락 종목 검색 (`price_change`)

```python
질문: "2025-07-21에 등락률이 -5% 이하인 KOSDAQ 종목들을 찾아줘"
JSON 변환: {
    "date": "2025-07-21",
    "market": "KOSDAQ", 
    "conditions": [{
        "type": "price_change",
        "op": "<=",
        "value": -5
    }]
}
답변: "에코프로비엠, 펄어비스, 카카오게임즈, 알테오젠, 씨젠"
```

- 거래량 급증 검색 (`volume_change`)

```python
질문: "2025-05-14에 거래량이 전날대비 300% 이상 증가한 종목을 모두 보여줘"
JSON 변환: {
    "date": "2025-05-14",
    "market": "all",
    "conditions": [{
        "type": "volume_change",
        "op": ">=",
        "value": 300
    }]
}
답변: "삼성바이오로직스, 셀트리온, 에코프로비엠, 펄어비스, 카카오게임즈 등이 있습니다."
```

- 종가 검색 (`close_price`)

```python
질문: "2025-06-10에 KOSPI에서 종가가 5만원 이하인 종목은?"
JSON 변환: {
    "date": "2025-06-10", 
    "market": "KOSPI",
    "conditions": [{
        "type": "close_price",
        "op": "<=",
        "value": 50000
    }]
}
# SQL: WHERE "adj_close" <= 50000 AND "market" = 'KOSPI'
답변: "한화솔루션, 현대건설, 두산에너빌리티, SK이노베이션, 대한항공"
```

- 복합 조건 검색 (`close_price`, `volume`)

```python
질문: "2025-09-05에 KOSPI에서 종가가 10만원 이상이고 거래량이 50만주 이상인 종목 알려줘"
JSON 변환: {
    "date": "2025-09-05",
    "market": "KOSPI",
    "conditions": [
        {"type": "close_price", "op": ">=", "value": 100000},
        {"type": "volume", "op": ">=", "value": 500000}
    ]
}
답변: "삼성전자, SK하이닉스, LG에너지솔루션, 삼성바이오로직스"
```

#### 4. 에러 처리

| 에러 상황 | 검증 방법 | 반환 메시지 |
|-----------|------|----------|
| `날짜 누락` | `plan.get('date') is None` | "필수 정보(날짜)가 누락되었습니다" |
| `날짜 형식 오류` | `datetime.strptime()`예외 | "날짜 형식이 올바르지 않습니다: 'YYYY-MM-DD' 형식 필요" |
| `조건 누락` | `plan.get('conditions') is None` | "유효한 실행 계획이 없습니다" |
| `DB 연결 실패` | `engine is None` | "데이터베이스에 연결할 수 없습니다" |
| `쿼리 실행 오류` | `Exception`발생 | "데이터베이스 쿼리 실행 중 오류가 발생했습니다" |
| `결과 없음` | `results == []` | "조건에 맞는 종목 없음" |
  
---

<a id="task3"></a>
###  Task 3: 시그널 감지
기술적 분석 지표를 활용하여 매매 시점을 포착하는 고급 분석 기능입니다.   
RSI, 이동평균선, 볼린저 밴드, 골든크로스/데드크로스 등 다양한 기술적 지표를 종합적으로 활용하여 투자 시그널을 감지합니다.

#### 1. 자연어 파싱 프로세스

```python
def parse_question_with_llm(state: AgentState) -> Dict[str, Any]:
    # LLM을 사용하여 기술적 분석 질문을 구조화된 JSON 계획으로 변환
    # 작업 유형, 날짜/기간, 시그널 종류, 임계값을 추출
    # 기본값과 다른 기준을 사용할 경우 thresholds 파라미터로 지정
```

#### 2. 실행 계획 처리

```python
def execute_plan(state: AgentState) -> Dict[str, Any]:
    # 분석된 계획에 따라 DB를 조회하고 결과를 생성
    # 각 시그널 유형별 SQL 쿼리 생성 및 실행
    # 답변이 20개를 초과할 경우 LIMIT 적용 및 "등이 있습니다" 추가
```

#### 3. 지원되는 작업 유형 및 사용 예제

| Task Type | 설명 | 사용 사례 |
|-----------|------|----------|
| `DETECT_SIGNAL` | 특정일의 시그널 감지 | RSI 과매수/과매도, 거래량 급증 등 |
| `FIND_SIGNAL_PERIOD` | 기간 내 시그널 발생 종목 검색 | 골든크로스/데드크로스 발생 종목 |
| `COUNT_SIGNAL_PERIOD` | 특정 종목의 기간 내 시그널 횟수 | 개별 종목의 시그널 발생 빈도 |

| Signal Type | 설명 | 기본 임계값 |
|-----------|------|----------|
| `RSI_OVERBOUGHT` | RSI 과매수 | 70 이상 |
| `RSI_OVERSOLD` | RSI 과매도 | 30 이하 |
| `VOLUME_SURGE` | 거래량 급증 | 20일 평균 대비 200% |
| `MA_BREAKOUT` | 이동평균선 돌파 | MA20 기준 |
| `BBAND_UPPER_TOUCH` | 볼린저 밴드 상단 접촉 | - |
| `BBAND_LOWER_TOUCH` | 볼린저 밴드 하단 접촉 | - |
| `GOLDEN_CROSS` | 골든크로스 (5일선 > 20일선) | - |
| `DEAD_CROSS` | 데드크로스 (5일선 < 20일선) | - |

- RSI 과매수 종목 검색 (`DETECT_SIGNAL: RSI_OVERBOUGHT`)

```python
질문: "2025-01-20에 RSI 과매수 종목을 알려줘"
JSON 변환: {
    "task_type": "DETECT_SIGNAL",
    "parameters": {
        "date": "2025-01-20",
        "signal_type": "RSI_OVERBOUGHT",
        "thresholds": {"rsi": 70}
    }
}
# SQL: SELECT company, rsi WHERE date = :date AND rsi >= 70
답변: "에코프로(RSI:85.3), 펄어비스(RSI:82.1), 카카오게임즈(RSI:78.5)"
```

- RSI 과매도 종목 검색 (`DETECT_SIGNAL: RSI_OVERSOLD`)


```python
질문: "2025-03-06에 RSI가 20 이하인 과매도 종목을 알려줘"
JSON 변환: {
    "task_type": "DETECT_SIGNAL",
    "parameters": {
        "date": "2025-03-06",
        "signal_type": "RSI_OVERSOLD",
        "thresholds": {"rsi": 20}
    }
}
답변: "한화솔루션(RSI:15.3), 두산에너빌리티(RSI:18.7), 현대건설(RSI:19.5)"
```

- 거래량 급증 종목 검색 (`DETECT_SIGNAL: VOLUME_SURGE`)

```python
질문: "2025-02-17에 거래량이 20일 평균 대비 300% 이상 급증한 종목을 알려줘"
JSON 변환: {
    "task_type": "DETECT_SIGNAL",
    "parameters": {
        "date": "2025-02-17",
        "signal_type": "VOLUME_SURGE",
        "thresholds": {"volume_surge_percent": 300}
    }
}
답변: "에코프로비엠(450%), 펄어비스(380%), 카카오게임즈(325%)"
```

- 이동평균선 돌파 종목 검색 (`DETECT_SIGNAL: MA_BREAKOUT`)

```python
질문: "2024-07-05에 종가가 60일 이동평균보다 3% 이상 높은 종목을 알려줘"
JSON 변환: {
    "task_type": "DETECT_SIGNAL",
    "parameters": {
        "date": "2024-07-05",
        "signal_type": "MA_BREAKOUT",
        "thresholds": {"ma_period": 60, "ma_breakout_percent": 3}
    }
}
답변: "삼성전자(5.23%), SK하이닉스(4.87%), 현대차(3.65%)"
```

- 기간 내 데드크로스 발생 종목 검색 (`FIND_SIGNAL_PERIOD: DEAD_CROSS`)

```python
질문: "2024-09-11부터 2024-10-11까지 데드크로스가 발생한 종목을 알려줘"
JSON 변환: {
    "task_type": "FIND_SIGNAL_PERIOD",
    "parameters": {
        "start_date": "2024-09-11",
        "end_date": "2024-10-11",
        "signal_type": "DEAD_CROSS"
    }
}
답변: "2024-10-08 기준: 카카오, 네이버, 셀트리온, 현대차, SK하이닉스"
```

- 특정 종목의 시그널 발생 횟수 계산 (`COUNT_SIGNAL_PERIOD: GOLDEN_CROSS`)

```python
질문: "현대백화점에서 2024-06-01부터 2025-06-30까지 골든크로스가 몇번 발생했어?"
JSON 변환: {
    "task_type": "COUNT_SIGNAL_PERIOD",
    "parameters": {
        "stock_name": "현대백화점",
        "start_date": "2024-06-01",
        "end_date": "2025-06-30",
        "signal_type": "GOLDEN_CROSS"
    }
}
답변: "3번"
```

- 통합 크로스 검색 (`COUNT_SIGNAL_PERIOD: CROSS_INTEGRATED`)

```python
질문: "패션플랫폼이 2024-06-01부터 2025-06-30까지 데드크로스 또는 골든크로스가 몇번 발생했어?"
JSON 변환: {
    "task_type": "COUNT_SIGNAL_PERIOD",
    "parameters": {
        "stock_name": "패션플랫폼",
        "start_date": "2024-06-01",
        "end_date": "2025-06-30",
        "signal_type": "CROSS_INTEGRATED"
    }
}
답변: "데드크로스 2번, 골든크로스 3번"
```

#### 4. 에러 처리

| 에러 상황 | 검증 방법 | 반환 메시지 |
|-----------|------|----------|
| `날짜 누락` | `params.get('date') is None` | "날짜 정보가 없습니다" |
| `날짜 형식 오류` | `datetime.strptime()`예외 | "날짜 형식이 올바르지 않습니다: 'YYYY-MM-DD' 형식 필요" |
| `기간 정보 누락` | `start_date or end_date is None` | "기간 정보가 없습니다" |
| `조회 기간 초과` | `(end_date - start_date).days > 30` | "조회 기간이 30일을 초과하여 너무 깁니다" |
| `종목/기간 누락` | `not all([stock_name, dates])` | "종목 또는 기간 정보가 부족합니다" |
| `DB 타임아웃` | `OperationalError` | "데이터베이스 조회 시간이 초과되었습니다" |
| `알 수 없는 시그널` | `signal not in valid_signals` | "알 수 없는 신호 유형입니다" |
| `결과 없음` | `results == []` | "조건에 맞는 종목 없음" 또는 "해당 기간에 조건에 맞는 종목 없음" |

---

<a id="task4"></a>
###  Task 4: 모호한 의미 해석
불완전하거나 모호한 주식 관련 질문을 자동으로 해석하고 명확하게 변환하는 AI 에이전트입니다.  
축약어, 은어, 불명확한 표현을 인식하여 적절히 변환하거나 사용자에게 추가 정보를 요청합니다.

- 핵심 설계 철학
  - LLM이 모호성을 판단하는 명확한 기준을 적용하기 위해 **모호성을 유형화**하고, **Checklist처럼 Yes/No로 처리**하도록 설계
 
- 금융 도메인에서의 모호성 유형화
  - 증권 현업 전문가 자문을 통해 금융 도메인의 모호성을 4가지로 유형화
    - **유형1) 축약어**: "삼전" → "삼성전자"
    - **유형2) 전문용어**: "떡상", "눌림목"
    - **유형3) 중의적 표현**: 여러 의미로 해석 가능한 표현(예. 최근, 과거 등)
    - **유형4) 조건 누락**: 날짜, 종목명 등 필수 정보 누락
    - 참고 논문: [FinDER](https://arxiv.org/abs/2504.15800), [PACIFIC](https://aclanthology.org/2022.emnlp-main.469/)

- 모호성 정량화 방법론
  - 기존 연구의 한계점
    - 전문가 직접 Annotation → 높은 비용
    - LLM 다중 답변 후 다양도 측정 → 비효율적

- 해결책: CheckEval 방식 적용
  - **Checklist 형태의 Yes/No 조건문**으로 모호성 판단
  - 사람의 일관성 문제 해결
  - 명확한 점수 기준 제공
  - 참고 논문: [CheckEval](https://arxiv.org/abs/2403.18771)

- 모호성 판단 후 처리 방안
  - **Query Rewriting**: DB/지식그래프 활용 가능하도록 질문 재작성
  - **Clarification**: 누락된 정보에 대해 사용자에게 역질문
  - 참고 논문: [APA](https://arxiv.org/abs/2404.11972), [Query Clarification](https://arxiv.org/abs/2310.09716)

#### 1. 모호성 감지 프로세스

```python
def task4_router_node(state: AgentState) -> dict:
    # 사용자 질문의 모호성 유형을 판단하여 처리 경로 결정
    # 4가지 조건을 체크하여 Rewriting 또는 Clarify 경로 선택
    # 조건 1,2는 Rewriting, 조건 3,4는 Clarify로 라우팅
```

#### 2. 질문 재작성 및 명확화

```python
def rewrite_query_node(state: AgentState) -> dict:
    # 종목 축약어와 주식 은어를 정식 용어로 자동 변환
    # 변환된 질문을 반환하여 메인 그래프가 재처리
    # turn_count를 통해 무한 루프 방지
```

```python
def clarify_question_node(state: AgentState) -> dict:
    # 모호한 기간이나 누락된 정보에 대한 역질문 생성
    # 사용자 친화적이고 선택지를 제공하는 형태의 질문
    # 간단하고 명료한 한 문장 형태로 생성
```

#### 3. 모호성 유형 및 처리 예제

| Task Type | 모호성 유형 | 처리 방식 | 예시 |
|-----------|----------|---------|-----|
| `유형1` | 종목 축약어 포함 | Rewriting | 삼전 → 삼성전자 |
| `유형2` | 주식 은어 포함 | Rewriting | 떡상 → 큰 폭 상승 |
| `유형3` | 모호한 기간 포함 | Clarifying | 최근 → 며칠 기준? |
| `유형4` | 정보 누락 | Clarifying | 종목명/날짜 요청 |

- 종목 축약어 변환 (`유형1`)

```python
# 주요 축약어 변환 예시
삼전 → 삼성전자
하닉 → SK하이닉스
카뱅 → 카카오뱅크
현차/현기차 → 현대차
나평정 → NICE평가정보
엔솔 → LG에너지솔루션
SKT → SK텔레콤
한전 → 한국전력

질문: "삼전 주가 알려줘"
변환: "삼성전자 주가 알려줘"
결과: "__REWRITE_SUCCESS__" 반환 → 메인 그래프 재실행
```

- 주식 은어 변환 (`유형2`)

```python
# 주요 은어 변환 사전
떡상 → 전일 대비 큰 폭으로 상승한
따상 → 공모가의 2배로 시초가 형성 후 상한가 도달한
평단 → 평균 매수 단가
물타기 → 추가 매수로 평균 단가를 낮춘
눌림목 → 일정 기간 하락 조정이 있었던
단타족 → 단기 매매 투자자

질문: "오늘 떡상한 종목 보여줘"
변환: "오늘 전일 대비 큰 폭으로 상승한 종목 보여줘"
```

- 모호한 기간 역질문 (`유형3`)

```python
질문: "삼성전자의 최근 종가는?"
역질문: "삼성전자의 최근 며칠의 종가를 알려드릴까요? 예 - 1일, 3일, 5일"

질문: "요즘 상승한 종목들 알려줘"
역질문: "최근 며칠 동안의 상승 종목을 확인하고 싶으신가요?"
```

- 누락 정보 역질문 (`유형4`)

```python
질문: "2025-07-24의 종가를 알려줘"
역질문: "어떤 종목의 2025-07-24 종가를 확인하고 싶으신가요?"

질문: "상승률 1위 종목은?"
역질문: "어느 날짜의 상승률 1위 종목을 확인하고 싶으신가요?"

질문: "거래량 많은 종목 5개"
역질문: "어느 날짜의 거래량 상위 5개 종목을 알려드릴까요?"
```

#### 4. 처리 플로우

```python
사용자 입력 → 모호성 분석 → 경로 결정
              ├─ 조건 1,2 → Rewriting → 변환된 질문 → 재처리
              └─ 조건 3,4 → Clarifying → 역질문 생성
```

---

<a id="task5"></a>
###  Task 5: 집중 투자 위험 알림

개인 투자자의 매매 패턴을 분석하여 과도한 집중 투자 위험을 감지하고, 뉴스 분석을 통해 매매 동기를 파악하여 맞춤형 경고를 제공하는 리스크 관리 기능입니다. <br>
투자자의 나이, 투자성향, 자산규모를 고려한 개인화된 집중 투자 위험 분석(PTPRA: Personalized Trading Pattern Risk Alert)을 수행합니다. <br>
최종적으로 위험 분석을 통해, 적합한 뉴스를 하이라이팅하여 보여줍니다. <br>
LLM의 생성문 끝 부분에서 '하이라이팅한 뉴스 기사 이미지: http://~~~' 부분에 -> image 링크를 클릭하면 image가 url 형태로 띄워집니다.



#### 1. 데이터 추출 프로세스
```python
def extract_transactions(state: AgentState) -> Dict[str, Any]:
    # 사용자 입력에서 JSON 형태의 매매 기록 추출
    # 날짜, 거래유형, 종목, 가격, 수량 정보를 파싱
    # 시간순으로 정렬하여 포트폴리오 변화 추적

def extract_mydata(state: AgentState) -> Dict[str, Any]:
    # LLM을 활용하여 마이데이터 정보 추출
    # 투자성향을 5가지 카테고리로 분류
    # 나이와 총 금융자산 정보 구조화
```

#### 2. 위험 분석 및 검증
```python
def analyze_risk_patterns(state: AgentState) -> Dict[str, Any]:
    # 매매 기록으로부터 현재 포트폴리오 계산
    # 개인화된 위험 임계치 = 투자성향 한도 × 생애주기 계수
    # 단일 종목 집중도가 임계치를 초과하는지 검사

def verify_analysis_results(state: AgentState) -> Dict[str, Any]:
    # 계산된 위험 패턴의 정확성 검증
    # 보고된 비중과 실제 계산 비중의 일치 여부 확인
    # 오류 발생 시 에러 처리 노드로 라우팅
```

#### 3. 지원되는 입력 형식 및 사용 예제

- 입력되는 데이터 구조

| 데이터 유형 | 필수 항목 | 형식 |
|----------|---------|-----|
| `텍스트 Input` | "제 매매 패턴을 분석해 주세요." | 텍스트 |
| `매매 기록` | 날짜, 거래유형, 종목, 가격, 수량 | JSON 배열 |
| `마이데이터` | 투자성향, 나이, 총 금융자산 | JSON 객체 |

- 투자성향 분류

| 투자성향 | 주식 비중 한도 | 위험 수준 |
|--------|------------|---------|
| `안정형` | 20% | 매우 낮음 |
| `안정추구형` | 40% | 낮음 |
| `위험중립형` | 60% | 보통 |
| `적극투자형` | 80% | 높음 |
| `공격투자형` | 90% | 매우 높음 |

- 생애주기 계수

| 연령대 | 계수 | 설명 |
|------|-----|-----|
| `20-39세` | 0.30 | 젊은 층, 위험 감수 가능 |
| `40-59세` | 0.20 | 중년층, 안정성 추구 |
| `60세 이상` | 0.10 | 노년층, 보수적 운용 |


- 최종 위험 기준 = (투자 성향별 주식 투자 한도) × (생애주기별 자산 집중도 한도)

| 생애주기 / 집중도 한도 | 안정형(20%) | 안정추구형(40%) | 위험중립형(60%) | 적극투자형(80%) | 공격투자형(90%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `초기 (30%)` | <small>6.00%</small> | <small>12.00%</small> | <small>18.00%</small> | <small>24.00%</small> | <small>27.00%</small> |
| `중기 (20%)` | <small>4.00%</small> | <small>8.00%</small> | <small>12.00%</small> | <small>16.00%</small> | <small>18.00%</small> |
| `후기 (10%)` | <small>2.00%</small> | <small>4.00%</small> | <small>6.00%</small> | <small>8.00%</small> | <small>9.00%</small> |

- 기본 입력 예제


```python
{
  "매매기록": [
    {
      "날짜": "2025-05-26",
      "거래유형": "매수",
      "종목": "LG화학",
      "가격": 412000,
      "수량": 80
    },
    {
      "날짜": "2025-05-27",
      "거래유형": "매수",
      "종목": "카카오뱅크",
      "가격": 23500,
      "수량": 150
    }
  ],
  "마이데이터": {
    "투자성향(profile)": "위험중립형",
    "나이(age)": 25,
    "총금융자산(total_financial_assets)": 90000000
  }
}
```

- 위험 분석 결과

```python
# 개인화 임계치 계산
투자성향 한도: 60% (위험중립형)
생애주기 계수: 0.30 (25세)
최종 임계치: 0.60 × 0.30 = 18%

# 포트폴리오 분석
LG화학 비중(personalized_threshold): 90% (32,960,000원 / 36,485,000원)
임계치(concentration) 초과: 90% > 18% ✓

# 위험 패턴 감지
{
  "risk_category": "집중 투자 위험",
  "stock_name": "LG화학",
  "concentration": 0.18,
  "description": f"'{riskiest_stock}' 종목의 비중이 {max_concentration:.2%}로, 고객님의 프로필(나이: {age}세, 성향: {profile})에 따른 권장 한도 {personalized_threshold:.2%}를 초과한 상황입니다.",
  "recommendation": "특정 종목에 대한 과도한 투자는 해당 종목의 가격 변동에 포트폴리오 전체가 크게 흔들릴 수 있습니다. 분산 투자를 통해 안정성을 높이는 것을 고려해보세요."
}
```

#### 4. 뉴스 분석 프로세스

```python
def search_korean_documents(state: AgentState) -> Dict[str, Any]:
    # 네이버 뉴스 API를 통한 관련 뉴스 검색
    # 매수일 기준 -7일 ~ 당일 뉴스 우선 필터링
    # 중복 제거 및 시점 기반 정렬

def analyze_and_extract_from_news(state: AgentState) -> Dict[str, Any]:
    # 3단계 뉴스 분석 프로세스
    # 1. 가장 관련성 높은 뉴스 URL 선정
    # 2. Selenium으로 원문 전체 스크래핑
    # 3. 핵심 문단 추출 (LLM 활용)

def capture_highlighted_image(state: AgentState) -> Dict[str, Any]:
    # BeautifulSoup으로 HTML 분석 및 <mark> 태그 삽입
    # Selenium으로 수정된 HTML 렌더링
    # 하이라이트 영역 중심으로 스크린샷 캡처
```

#### 5. 최종 리포트 구성

1. 매매 인식: 거래 내역 확인
2. 원인 추정: 뉴스 기반 매매 동기 분석
3. 위험 경고: 개인화된 위험 수준 알림
4. 권고 사항: 분산 투자 제안
5. 시각적 근거: 하이라이팅된 뉴스 이미지

```python
최근 **2025년 05월 26일**에 진행하신 **'LG화학' 매수** 기록을 확인했습니다.

고객님의 이러한 결정은 아마도 **'LG화학이 일본 노리타케와 전력 반도체용 실버 페이스트 공동 개발에 성공함으로써, 전기차 시장에서의 경쟁력 강화 및 실적 개선 기대감 상승'** 관련 소식 때문이었을 것으로 생각됩니다. 당시 뉴스에서는 'LG화학이 일본 정밀세라믹 전문기업 노리타케와 손잡고 전기차 전력 반도체에 사용되는 고성능 접착제 시장 공략에 나선다. 양사는 16일 차세대 차량용 전력 반도체용 ‘실버 페이스트(Silver Paste)’를 공동 개발했다고 밝혔다.'라며 긍정적인 전망을 내놓았죠.

하지만 고객님의 프로필(나이: 35세, 성향: 위험중립형)을 기준으로 분석한 결과, 현재 **'집중 투자 위험'** 상태에 해당합니다. 'LG화학' 종목의 비중이 90.34%로, 고객님의 프로필(나이: 35세, 성향: 위험중립형)에 따른 권장 한도 18.00%를 초과한 상황입니다.

이러한 집중 투자 패턴이 지속될 경우, 해당 종목의 작은 변동성에도 전체 자산이 크게 영향을 받을 수 있으며, 예상치 못한 하락 시 큰 손실로 이어질 위험이 있습니다. 특정 종목에 대한 과도한 투자는 해당 종목의 가격 변동에 포트폴리오 전체가 크게 흔들릴 수 있습니다. 분산 투자를 통해 안정성을 높이는 것을 고려해보세요.

[하이라이팅된 뉴스 이미지]
하이라이팅한 뉴스 기사 이미지: http://147.47.39.102:8000/images/20250728_190233_183488.png
원본 자료: https://n.news.naver.com/...
```

#### 6. 에러 처리

| 에러 상황 | 검증 방법 | 반환 메시지 |
|--------|------------|---------|
| `매매기록 파싱 실패` | JSON 디코딩 예외 | "매매 기록 JSON 파싱 중 오류 발생" |
| `마이데이터 누락` | 필수 필드 null | "마이데이터(투자성향, 나이, 총금융자산) 정보가 부족합니다" |
| `포트폴리오 없음` | 총 가치 = 0 | "모든 종목이 매도되어 분석할 현재 보유 포트폴리오가 없습니다" |
| `뉴스 검색 실패` | API 응답 없음 | "관련 뉴스를 찾을 수 없습니다" |
| `스크래핑 실패` | Selenium 타임아웃 | "뉴스 원문을 가져오는 데 실패했습니다" |
| `검증 실패` | 비중 불일치 | "보고된 비중과 실제 계산된 비중이 다릅니다" |

---

<a id="local-setup"></a>
## 🚀 Local 환경에서 Agent 실행하기

### 01. Docker Image 생성

프로젝트 Root Directory에서 아래 명령어를 실행하여 Agent 실행에 필요한 모든 환경이 포함된 Docker Image를 Build합니다.

```bash
# Docker 디렉토리로 이동
cd docker/

# Docker 이미지 빌드
docker build -t financial-agent .
```

### 02. Docker 컨테이너 생성 및 실행

빌드된 이미지를 컨테이너로 실행합니다.

> 💡 **Note**: `make_container.sh` 내부에는 docker run 명령어가 포함되어 있으며, Agent 서버가 외부 요청을 받을 수 있도록 특정 포트(예: 8000번)를 지정하여 호스트와 연결하도록 구성되어 있습니다.

```bash
# 컨테이너 생성 및 실행
bash make_container.sh
```

### 03. Chrome Driver 설치

Task 5를 위한 Chrome Driver를 설치합니다.

> 💡 **Note**: `make_container.sh`를 실행하였던 /docker 위치에서 아래 명령어를 통해 Chrome Driver를 설치합니다.

```bash
# 컨테이너 생성 및 실행
bash chrome_driver.sh
```

### 04. 데이터베이스 구축

Agent가 사용하는 금융 데이터(예: 날짜별 종가, 시가 등)를 yfinance로 구축합니다.  
`index_kospi_kosdaq`, `stocks_kospi_kosdaq`, `technical_signals` 총 3가지 테이블을 구축합니다.

<p align="center">
  <img src="https://github.com/user-attachments/assets/af85aa90-1c41-4090-9216-d01315026613" alt="Workflow Diagram" width="600"/>
</p>

- `index_kospi_kosdaq`: KOSPI/KOSDAQ 지수 데이터 수집
- `stocks_kospi_kosdaq`: KOSPI/KOSDAQ 전 종목의 개별 주가 데이터 수집
- `technical_signals`: 주가 데이터 기반 기술적 지표 계산
  - RSI, 이동평균선(5~240일), 볼린저밴드, 골든/데드크로스 등


```bash
# 데이터베이스 초기화 및 데이터 로드
bash make_db.sh
```

### 05. Agent 실행

모든 설정이 완료되면 다음 명령어로 Agent를 실행합니다.

```bash
# 실행
python endpoint_final.py
```

---


