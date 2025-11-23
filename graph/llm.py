import requests
import json


class CLOVAStudioLLM:
    def __init__(self, completion_executor):
        self.completion_executor = completion_executor

    def invoke(self, prompt: str, system_message: str = "당신은 금융 데이터 분석을 도와주는 전문 AI입니다. 사용자의 요청을 정확하게 분석하고 구조화하여 답변하세요.") -> str:
        """CLOVA Studio API를 사용하여 LLM 응답 생성"""
        request_data = {
            'messages': [
                # 인자로 받은 system_message를 사용(Task 5에는 각자 다른 system_message 사용)
                # 별도로 지정하지 않으면 위에 설정된 기본값
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            # 'topP': 1.0,
            # 'topK': 0,
            # 'maxTokens': 1000,
            # 'temperature': 0.0,
            # 'repeatPenalty': 1.2,
            # 'stopBefore': [],
            # 'includeAiFilters': True,
            # 'seed': 0
            
            #Task 5용 Generation params 설정(Test용)
            # 'topP': 0.8,
            # 'topK': 0,
            # 'maxTokens': 2000,
            # 'temperature': 0.3,
            # 'repeatPenalty': 1.2,
            # 'stopBefore': [],
            # 'includeAiFilters': True,
            # 'seed': 0
        }

        try:
            response = self.completion_executor.execute(request_data)
            return response.strip() if response else "응답을 받을 수 없습니다."
        except Exception as e:
            return "API 호출 중 오류가 발생했습니다."


# # -*- coding: utf-8 -*-
# class CompletionExecutor:
#     def __init__(self, host, api_key, request_id):
#         self._host = host
#         self._api_key = api_key
#         self._request_id = request_id
    
#     def execute(self, completion_request):
#         headers = {
#             'Authorization': self._api_key,
#             'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
#             'Content-Type': 'application/json; charset=utf-8',
#             'Accept': 'application/json'
#         }

#         try:
#             # with 문 대신 직접 변수에 할당하고, 타임아웃을 추가합니다.
#             r = requests.post(self._host + '/testapp/v1/chat-completions/HCX-003',
#                                   headers=headers, json=completion_request)
            
#             # 요청 실패 시, 서버가 반환한 상세 오류를 출력하도록 수정
#             r.raise_for_status()
            
#             response_json = r.json()
#             return response_json.get('result', {}).get('message', {}).get('content', '')

#         except requests.exceptions.RequestException as e:
#             # 오류 발생 시 더 상세한 정보를 출력
#             print(f"--- 🚨 CLOVA Studio API 요청 오류 발생 ---")
#             print(f"오류 메시지: {e}")
#             # 서버로부터 응답이 있는 경우, 상태 코드와 내용을 출력
#             if e.response is not None:
#                 print(f"상태 코드: {e.response.status_code}")
#                 print(f"서버 응답 내용: {e.response.text}")
#             print("-----------------------------------------")
#             return "" # 기존과 같이 빈 문자열 반환
#         except json.JSONDecodeError as e:
#             print(f"응답을 JSON으로 파싱하는 데 실패했습니다: {e}")
#             # 파싱에 실패한 원본 텍스트를 확인하기 위해 출력
#             if 'r' in locals() and r.text:
#                 print(f"원본 응답 텍스트: {r.text}")
#             return ""

# -*- coding: utf-8 -*-
class CompletionExecutor:
    def __init__(self, host, api_key, request_id):
        self._host = host
        self._api_key = api_key
        self._request_id = request_id
    
    def execute(self, completion_request):
        headers = {
            'Authorization': self._api_key, # Authorization X-NCP-CLOVASTUDIO-API-KEY
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
            'Content-Type': 'application/json; charset=utf-8',
            'Accept': 'application/json' # event/stream -> 'application/json'으로 응답 타입을 지정합니다.
            
        }

        try:
            # stream=False가 기본값이므로 stream 인자를 제거하거나 명시적으로 False로 설정합니다.
            with requests.post(self._host + '/testapp/v1/chat-completions/HCX-003', # HCX-003
                               headers=headers, json=completion_request) as r:
                
                # 요청 실패 시 예외를 발생시킵니다.
                r.raise_for_status()
                
                # 응답 전체를 JSON으로 파싱합니다.
                response_json = r.json()
                
                # JSON 구조에 따라 실제 메시지 내용을 추출합니다.
                # CLOVA Studio Chat Completion의 일반적인 응답 구조입니다.
                return response_json.get('result', {}).get('message', {}).get('content', '')

        except requests.exceptions.RequestException as e:
            print(f"API 요청 중 오류 발생: {e}")
            return ""
        except json.JSONDecodeError:
            print("응답을 JSON으로 파싱하는 데 실패했습니다.")
            return ""