#!/usr/bin/env python3
"""
TikTok Shop 페이지 접속
Browser Use를 사용하여 TikTok Shop Affiliate 페이지에 접속합니다.
"""

from browser_use import Agent
from browser_use.llm import ChatOpenAI
from dotenv import load_dotenv
import asyncio
import os

# 환경 변수 로드
load_dotenv()


async def open_tiktok_shop():
    """
    TikTok Shop Affiliate 페이지를 엽니다.
    """
    print("🚀 TikTok Shop 페이지 접속 시작...")
    
    # LLM 초기화 (Browser Use의 ChatOpenAI 사용)
    llm = ChatOpenAI(model="gpt-4.1")
    
    # 에이전트 작업 정의
    task = """
    TikTok Shop Affiliate 사이트에 로그인합니다:
    
    1. https://affiliate-us.tiktok.com 으로 이동
    2. 페이지가 완전히 로드될 때까지 대기
    3. Email 탭 (Email 또는 Phone 선택 부분에서 Email 탭)을 클릭
    4. Email 입력란에 'company@cosduck.com' 입력
    5. Password 입력란에 'phozphoz1!' 입력
    6. Log in 버튼 클릭
    7. 캡챠가 뜨면 캡챠를 수행
    8. 로그인 성공 여부 확인
    """
    
    try:
        # 에이전트 생성 (Browser Use 0.5.9 버전 방식)
        agent = Agent(
            task=task,
            llm=llm,
            browser_config={
                'headless': False,  # 브라우저 창 표시
                'viewport': {'width': 1440, 'height': 900},
            }
        )
        
        print("⏳ TikTok Shop 페이지로 이동 중...")
        
        # 에이전트 실행
        result = await agent.run()
        
        print("\n✅ 페이지 접속 완료!")
        print("\n📊 페이지 상태:")
        print("-" * 50)
        print(result)
        print("-" * 50)
        
        # 브라우저 열린 상태 유지
        print("\n🌐 브라우저가 열려 있습니다.")
        print("Enter 키를 누르면 브라우저를 닫고 종료합니다...")
        input()
        
        return result
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return None


async def main():
    """메인 함수"""
    print("=" * 60)
    print("TikTok Shop Affiliate 페이지 접속")
    print("=" * 60)
    
    await open_tiktok_shop()
    
    print("\n프로그램이 종료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())