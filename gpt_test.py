
import requests
import json

# Ollama API 엔드포인트 및 모델 이름 설정
API_URL = "http://localhost:11434/v1/chat/completions"
MODEL_NAME = "gpt-oss"

def test_ollama_api():
    """
    Ollama gpt-oss 모델 API를 테스트하는 함수
    """
    headers = {
        "Content-Type": "application/json"
    }

    # 모델에게 보낼 간단한 테스트 프롬프트
    prompt = "안녕하세요! 간단한 자기소개 부탁해요."

    # OpenAI 호환 API 형식에 맞는 데이터 구성
    data = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7, # 약간의 창의성을 부여
        "stream": False # 스트리밍 방식 비활성화
    }

    print(f"'{MODEL_NAME}' 모델에 요청을 보냅니다...")
    print(f"프롬프트: {prompt}")

    try:
        # API에 POST 요청 보내기
        response = requests.post(API_URL, headers=headers, data=json.dumps(data), timeout=60)
        
        # HTTP 오류가 발생하면 예외를 발생시킴
        response.raise_for_status()
        
        # 응답 받은 JSON 데이터 파싱
        response_json = response.json()
        
        # 모델의 답변 내용 추출
        content = response_json['choices'][0]['message']['content']
        
        print("\n--- 모델 응답 ---")
        print(content)
        print("------------------")

    except requests.exceptions.RequestException as e:
        print(f"\n[오류] API 호출에 실패했습니다: {e}")
        print("Ollama 서버가 'ollama serve' 명령어로 실행 중인지 확인해주세요.")
    except (json.JSONDecodeError, KeyError) as e:
        print(f"\n[오류] API 응답을 파싱하는 데 실패했습니다: {e}")
        print("모델의 응답 형식이 예상과 다릅니다.")
    except Exception as e:
        print(f"\n[오류] 알 수 없는 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    test_ollama_api()
