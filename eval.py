# eval.py (수정 후)
import requests

# ❗ API End-point를 서버의 공용 IP와 포트 번호로 수정합니다.
URL = 'http://211.188.58.134:8000/agent' # http://175.45.203.235:8000/agent http://127.0.0.1:8000/agent


# 실제 평가시에는 미래에셋증권 평가용 API KEY 사용.
API_KEY = ''  
REQUEST_ID = ''  

headers = {
    'Authorization': f'Bearer {API_KEY}',
    'X-NCP-CLOVASTUDIO-REQUEST-ID': f'{REQUEST_ID}'
}

params = {
    'question': '거래량이 전날 대비 15% 이상 오른 종목을 모두 보여줘'
}

requests.get(URL, headers=headers, params=params)
print(response.text)  # {'answer': '애드바이오텍, 아난티, 엠에프엠코리아 입니다.'}