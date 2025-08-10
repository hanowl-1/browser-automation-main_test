# CLAUDE.md

이 파일은 이 저장소의 코드 작업 시 Claude Code (claude.ai/code)에 대한 안내를 제공합니다.

## 프로젝트 개요

Browser Use를 사용하는 브라우저 자동화 프로젝트입니다 - LLM 에이전트를 통해 자동화된 웹 상호작용을 가능하게 하는 AI 기반 브라우저 자동화 프레임워크입니다.

## 설정 명령어

```bash
# Python 가상 환경 생성 및 활성화 (Python 3.11+ 필요)
uv venv --python 3.11
source .venv/bin/activate  # Mac/Linux
# 또는
.venv\Scripts\activate     # Windows

# Browser Use 및 의존성 설치
uv pip install browser-use

# Playwright 브라우저 설치
uv run playwright install
```

## 환경 설정

필요한 API 키와 설정으로 `.env` 파일을 생성하세요. `dev.env` 파일을 템플릿으로 사용할 수 있습니다:

```bash
# dev.env를 .env로 복사
cp dev.env .env

# .env 파일 편집하여 실제 API 키 입력
nano .env  # 또는 선호하는 편집기 사용
```

주요 환경 변수:
- `OPENAI_API_KEY`: OpenAI API 키 (GPT-4용)
- `ANTHROPIC_API_KEY`: Anthropic API 키 (Claude용)
- `KAKAO_EMAIL`, `KAKAO_PASSWORD`: 카카오 채널 로그인 정보
- `TIKTOK_EMAIL`, `TIKTOK_PASSWORD`: TikTok Shop 로그인 정보
- `SLACK_WEBHOOK_URL`: Slack 알림용 웹훅 URL

자세한 설정은 `dev.env` 파일을 참조하세요.

## 프로젝트 구조

```
browser-automation/
├── src/
│   ├── agents/         # 에이전트 정의 및 작업
│   ├── models/         # 구조화된 출력을 위한 Pydantic 모델
│   ├── utils/          # 헬퍼 함수
│   └── config/         # 설정 파일
├── tests/              # 테스트 파일
├── logs/               # 대화 로그 및 스크린샷
├── .env               # API 키 및 환경 변수
└── requirements.txt    # Python 의존성
```

## 에이전트 설정 옵션

### 핵심 매개변수
- `task` (필수): 에이전트를 위한 주요 지침
- `llm` (필수): 채팅 모델 인스턴스
- `use_vision`: 시각적 처리 활성화/비활성화 (기본값: True)
- `vision_detail_level`: 'low', 'high', 또는 'auto' (기본값)
- `controller`: 사용자 정의 함수 레지스트리
- `save_conversation_path`: 대화 기록 저장 경로
- `extend_system_message`: 기본 프롬프트에 지침 추가
- `override_system_message`: 전체 시스템 프롬프트 교체 (권장하지 않음)

### 비전 설정
- 비전을 비활성화하면 비용 절감 (GPT-4o의 경우 이미지당 ~800-1000 토큰)
- 더 빠르고 저렴한 처리를 위해 'low' 세부 수준 사용
- 자세한 시각적 분석을 위해 'high' 사용

## 브라우저 설정

### BrowserSession 매개변수
- `headless`: UI 없이 실행 (기본값: True)
- `channel`: 브라우저 유형 ('chromium', 'chrome', 'edge')
- `executable_path`: 사용자 정의 브라우저 실행 파일
- `user_data_dir`: 브라우저 프로필 디렉토리
- `stealth`: 봇 감지 회피
- `viewport`: 창 크기 {'width': 964, 'height': 647}
- `user_agent`: 사용자 정의 브라우저 식별
- `allowed_domains`: 특정 도메인으로 탐색 제한
- `proxy`: 네트워크 프록시 설정
- `permissions`: 특정 브라우저 권한 부여
- `deterministic_rendering`: 일관되지만 느린 렌더링
- `highlight_elements`: 상호작용 요소 경계 표시
- `wait_for_network_idle_page_load_time`: 네트워크 대기 시간

### 보안 고려사항
- 에이전트는 로그인된 세션, 쿠키, 저장된 비밀번호에 접근 가능
- 다른 에이전트를 위해 격리된 브라우저 프로필 사용
- `disable_security`: ⚠️ 매우 위험 - 절대적으로 필요한 경우가 아니면 피하세요
- 접근을 제한하려면 `allowed_domains` 사용

## 출력 형식 설정

Pydantic 모델을 사용하여 구조화된 출력 정의:

```python
from pydantic import BaseModel
from typing import List

class DataItem(BaseModel):
    title: str
    url: str
    description: str

class DataCollection(BaseModel):
    items: List[DataItem]

controller = Controller(output_model=DataCollection)
```

## 시스템 프롬프트 사용자 정의

기본 프롬프트 확장 (권장):
```python
extend_system_message = """
에이전트를 위한 추가 지침...
"""
```

전체 프롬프트 재정의 (필요한 경우가 아니면 권장하지 않음):
```python
override_system_message = """
완전히 교체된 시스템 프롬프트...
"""
```

## 핵심 코드 패턴

### 기본 에이전트
```python
from browser_use.llm import ChatOpenAI
from browser_use import Agent
from dotenv import load_dotenv
import asyncio

load_dotenv()

llm = ChatOpenAI(model="gpt-4o")

async def main():
    agent = Agent(
        task="Your automation task",
        llm=llm,
    )
    result = await agent.run()
    return result

asyncio.run(main())
```

### 완전한 사용자 정의가 포함된 고급 에이전트
```python
from browser_use import Agent, Controller, BrowserSession
from browser_use.llm import ChatOpenAI
from pydantic import BaseModel
import asyncio

# 출력 구조 정의
class SearchResult(BaseModel):
    title: str
    url: str
    summary: str

class SearchResults(BaseModel):
    results: List[SearchResult]

# 브라우저 설정
browser_session = BrowserSession(
    headless=False,
    stealth=True,
    viewport={'width': 1280, 'height': 720},
    user_data_dir='~/.config/browseruse/profiles/research'
)

# 출력 모델로 컨트롤러 설정
controller = Controller(output_model=SearchResults)

# 에이전트 설정
agent = Agent(
    task="Search and extract top 5 AI news articles",
    llm=ChatOpenAI(model="gpt-4o"),
    controller=controller,
    use_vision=True,
    vision_detail_level='auto',
    save_conversation_path="logs/conversation",
    extend_system_message="Focus on recent articles from reputable sources"
)

# 브라우저 세션으로 실행
result = await agent.run(browser_session=browser_session)
```

## 모범 사례

1. **브라우저 관리**
   - 여러 브라우저를 위해 고유한 `user_data_dir` 사용
   - 디버깅을 위해 `headless=False` 설정
   - 감지를 피하기 위해 `stealth=True` 활성화
   - 브라우저 세션을 적절히 종료

2. **성능 최적화**
   - 필요하지 않을 때 비전 비활성화
   - 간단한 작업에는 'low' 비전 세부 사용
   - 적절한 오류 처리 구현
   - 데이터 추출을 위해 구조화된 출력 사용

3. **보안**
   - 절대적으로 필요한 경우가 아니면 보안을 비활성화하지 마세요
   - 격리된 브라우저 프로필 사용
   - 가능한 경우 도메인 접근 제한
   - API 키를 .env에 안전하게 저장

4. **개발**
   - 처음에는 `headless=False`로 테스트
   - 디버깅을 위해 대화 저장
   - 예측 가능한 결과를 위해 구조화된 출력 사용
   - 네트워크 실패를 위한 재시도 로직 구현

## 작업 실행

```bash
# 메인 스크립트 실행
python main.py

# 고급 에이전트 실행
python advanced_agent.py

# uv 사용
uv run python main.py
```

## 테스트

```bash
# 모든 테스트 실행
pytest tests/

# 상세 출력으로 실행
pytest -v tests/

# 특정 테스트 실행
pytest tests/test_agent.py
```

## 문제 해결

- 실행 전 모든 Chrome 인스턴스 종료
- Python 3.11+ 설치 확인
- 브라우저 실행 파일 경로 확인
- .env 파일의 API 키 확인
- 디버깅을 위해 `headless=False` 사용

## 문서 참조

- 빠른 시작: https://docs.browser-use.com/quickstart
- 에이전트 설정: https://docs.browser-use.com/customize/agent-settings
- 브라우저 설정: https://docs.browser-use.com/customize/browser-settings
- 출력 형식: https://docs.browser-use.com/customize/output-format
- 시스템 프롬프트: https://docs.browser-use.com/customize/system-prompt