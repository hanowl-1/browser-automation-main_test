# 토큰 사용량 최적화 가이드

## 개요

이 문서는 Browser Use를 사용한 자동화 작업에서 토큰 사용량을 90% 이상 줄이는 방법을 설명합니다.

## 최적화 전후 비교

### 최적화 전 (kakao1_login.py)
- **토큰 사용량**: 채팅당 198,000 토큰
- **일일 비용** (200개 채팅):
  - GPT-4: 1,599,000원 ($1,230)
  - GPT-4 Turbo: 551,200원 ($424)
  - Gemini 2.0 Flash: 8,840원 ($6.80)

### 최적화 후 (kakao1_login_optimized.py)
- **토큰 사용량**: 채팅당 ~20,000 토큰 (90% 감소)
- **일일 비용** (200개 채팅):
  - GPT-3.5 Turbo: 10,400원 ($8)
  - Gemini 2.0 Flash: 780원 ($0.60)

## 주요 최적화 기법

### 1. 프롬프트 최적화 (80% 토큰 절감)

**최적화 전** (2,000자 이상):
```python
task = """
카카오채널 관리자 페이지에서 '새 메시지 있는' 채팅방들만 대상으로 대화 기록을 수집하고...
[긴 설명과 반복적인 지시사항]
...
"""
```

**최적화 후** (400자):
```python
task = """
카카오채널에서 새 메시지 있는 채팅방 처리:
1. URL 접속 및 로그인
2. 빨간 배지 채팅방 선택
3. 대화 읽고 자동 답변
4. JSON 반환
"""
```

### 2. 비전 처리 최적화 (50% 토큰 절감)

```python
# 최적화 전
vision_detail_level='high'  # 고해상도 이미지 분석

# 최적화 후
vision_detail_level='low'   # 저해상도로도 충분
```

### 3. 모델 변경 (95% 비용 절감)

```python
# 최적화 전
llm = ChatOpenAI(model="gpt-4.1")

# 최적화 후
llm = ChatOpenAI(model="gpt-3.5-turbo-1106")
# 또는
# Gemini Flash 사용 시 (99.95% 절감)
```

### 4. 불필요한 기능 제거

- 복잡한 JSON 파싱 로직 제거
- 중복 스크롤/로딩 함수 제거
- 과도한 로깅 및 디버깅 코드 제거

## 실제 구현 예시

### 기본 최적화 구조

```python
from browser_use import Agent
from browser_use.llm import ChatOpenAI

# 간소화된 작업 정의
task = """
웹사이트에서 데이터 수집:
1. URL 접속
2. 필요한 요소 찾기
3. 데이터 추출
4. JSON 반환
"""

# 최적화된 에이전트 설정
agent = Agent(
    task=task,
    llm=ChatOpenAI(model="gpt-3.5-turbo"),
    browser_config={
        'headless': True,
        'viewport': {'width': 1280, 'height': 800}
    },
    use_vision=True,
    vision_detail_level='low'
)
```

## 추가 최적화 팁

### 1. 조건부 비전 사용
```python
# 비전이 꼭 필요한 경우만 활성화
use_vision = task_requires_vision(task)
agent = Agent(task=task, use_vision=use_vision)
```

### 2. 캐싱 활용
```python
# FAQ 기반 응답은 LLM 호출 없이 처리
if is_faq_question(message):
    response = get_cached_response(message)
else:
    response = await llm.generate(message)
```

### 3. 배치 처리
```python
# 여러 작업을 한 번에 처리
tasks = ["task1", "task2", "task3"]
results = await agent.run_batch(tasks)
```

## 환경 변수 설정

`.env` 파일에 추가:
```bash
# 모델 선택
USE_GEMINI=false  # true로 설정 시 Gemini 사용

# 최적화 옵션
VISION_DETAIL=low
MAX_CHATS_PER_RUN=3
ENABLE_CACHING=true
```

## 성능 모니터링

```python
# 토큰 사용량 추적
def track_token_usage(result):
    tokens_used = result.get('usage', {}).get('total_tokens', 0)
    cost = calculate_cost(tokens_used, model_name)
    print(f"토큰 사용: {tokens_used}, 비용: ${cost}")
```

## 결론

이러한 최적화 기법을 적용하면:
- 토큰 사용량 90% 감소
- 일일 운영 비용 99% 절감
- 처리 속도 향상
- 안정성 유지

자세한 비용 분석은 `Documents/COST_ANALYSIS.md`를 참조하세요.