#!/usr/bin/env python3
"""
최적화된 Kakao Channel 대화 수집 자동화
토큰 사용량을 최소화하여 비용을 절감한 버전
"""

from browser_use import Agent
from browser_use.llm import ChatOpenAI
from dotenv import load_dotenv
import asyncio
import os
import json
import re
import unicodedata
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from typing import Any, List, Optional
import ast
from datetime import datetime
from chatbot_handler import SuperMembersChatbot

# 환경 변수 로드
load_dotenv()

SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/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"

# 파이썬 변수로 결과 누적 저장
PY_RESULTS: List[dict] = []


def post_to_slack(webhook_url: str, text: str) -> bool:
    try:
        data_bytes = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
        req = Request(
            webhook_url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=15) as resp:
            status = resp.getcode()
            return 200 <= status < 300
    except (HTTPError, URLError) as e:
        print(f"❌ 슬랙 전송 실패: {e}")
        return False
    except Exception as e:
        print(f"❌ 슬랙 전송 중 알 수 없는 오류: {e}")
        return False


def extract_json_from_text(text: str) -> Optional[str]:
    """간소화된 JSON 추출 함수"""
    if not text:
        return None
    
    # 코드 펜스 제거
    text = re.sub(r"```json\s*([\s\S]*?)\s*```", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"```\s*([\s\S]*?)\s*```", r"\1", text)
    
    # 가장 간단한 JSON 배열 패턴 매칭
    match = re.search(r'\[[\s\S]*\]', text)
    if match:
        try:
            json.loads(match.group(0))
            return match.group(0)
        except:
            pass
    
    return None


async def on_step_end_collect(agent) -> None:
    """단순화된 결과 수집 함수"""
    try:
        # history에서 JSON 추출
        hist_text = str(getattr(getattr(agent, "state", None), "history", ""))
        json_text = extract_json_from_text(hist_text)
        if json_text:
            data = json.loads(json_text)
            if isinstance(data, list):
                PY_RESULTS.extend([x for x in data if isinstance(x, dict)])
    except Exception:
        pass


async def optimized_kakao_automation():
    """최적화된 카카오채널 자동화"""
    print("🚀 최적화된 카카오채널 자동화 시작...")
    
    # 챗봇 초기화
    chatbot = SuperMembersChatbot(faq_file_path="qna.json")
    print("🤖 챗봇 로드 완료")
    
    # LLM 설정 (GPT-3.5 또는 Gemini Flash 사용 가능)
    use_gemini = os.getenv("USE_GEMINI", "false").lower() == "true"
    
    if use_gemini:
        # Gemini 2.0 Flash 사용 (미래 구현용)
        print("💎 Gemini 2.0 Flash 사용 중...")
        # TODO: Gemini Flash 통합
        llm = ChatOpenAI(model="gpt-3.5-turbo-1106")  # 임시 폴백
    else:
        # GPT-3.5 Turbo 사용 (GPT-4 대비 95% 저렴)
        llm = ChatOpenAI(model="gpt-3.5-turbo-1106")
    
    # 극도로 간소화된 작업 정의 (토큰 90% 절감)
    task = """
카카오채널에서 새 메시지 있는 채팅방 처리:

1. https://center-pf.kakao.com/_gwELG/chats 접속
2. 로그인: vof@nate.com / phozphoz1!
3. 빨간 배지 있는 채팅방만 선택 (최대 3개)
4. 각 채팅방:
   - 클릭하여 진입
   - 대화 읽기
   - Python 실행: chatbot.generate_response(마지막_고객_메시지, room_id)
   - 응답 입력 후 전송
   - 채팅방 나가기

5. JSON 형식으로 반환:
[{
  "roomId": "ID",
  "roomName": "이름", 
  "conversations": [{"speaker": "customer/agent", "text": "메시지"}],
  "autoReply": {"sent": true, "message": "답변"}
}]

파일 작성 금지. 빈 결과는 []
"""

    try:
        # 에이전트 생성 (최적화 설정)
        agent = Agent(
            task=task,
            llm=llm,
            browser_config={
                'headless': False,
                'viewport': {'width': 1280, 'height': 800},  # 더 작은 뷰포트
            },
            use_vision=True,
            vision_detail_level='low'  # 'high' -> 'low'로 변경 (50% 토큰 절감)
        )

        print("⏳ 실행 중...")

        # 에이전트 실행
        result = await agent.run(on_step_end=on_step_end_collect)
        
        print("\n✅ 완료!")
        
        # 결과 처리
        sent_count = 0
        parsed_results = []
        
        if PY_RESULTS:
            # 중복 제거
            seen = set()
            for item in PY_RESULTS:
                if not isinstance(item, dict):
                    continue
                key = (item.get("roomId"), item.get("roomName"))
                if key in seen:
                    continue
                seen.add(key)
                parsed_results.append(item)
                
                # 슬랙 전송
                try:
                    text_payload = json.dumps(item, ensure_ascii=False, indent=2)
                    if post_to_slack(SLACK_WEBHOOK_URL, text_payload):
                        sent_count += 1
                        print(f"📤 슬랙 전송: {item.get('roomName', 'Unknown')}")
                except Exception as e:
                    print(f"⚠️ 전송 오류: {e}")
        
        # 요약 출력
        print(f"\n📊 실행 요약:")
        print(f"- 처리된 채팅방: {len(parsed_results)}개")
        print(f"- 슬랙 전송: {sent_count}건")
        
        # 로그 저장
        os.makedirs("logs", exist_ok=True)
        with open("logs/optimized_results.json", "w", encoding="utf-8") as f:
            json.dump(parsed_results, f, ensure_ascii=False, indent=2)
        
        # 브라우저 유지
        if os.getenv("NON_INTERACTIVE") != "1":
            print("\n🌐 Enter 키를 누르면 종료합니다...")
            input()
        
        return result
        
    except Exception as e:
        print(f"❌ 오류: {e}")
        return None


async def main():
    """메인 함수"""
    print("=" * 60)
    print("최적화된 Kakao Channel 자동화")
    print("=" * 60)
    
    await optimized_kakao_automation()
    
    print("\n프로그램 종료")


if __name__ == "__main__":
    asyncio.run(main())