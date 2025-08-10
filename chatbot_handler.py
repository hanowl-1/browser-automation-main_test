#!/usr/bin/env python3
"""
슈퍼멤버스 FAQ 기반 챗봇 핸들러
Kakao Channel 자동 응답을 위한 지능형 챗봇 시스템
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import logging

# 로깅 설정
logger = logging.getLogger(__name__)


class SuperMembersChatbot:
    """슈퍼멤버스 FAQ 기반 챗봇"""
    
    def __init__(self, faq_file_path: str = None):
        """
        챗봇 초기화
        
        Args:
            faq_file_path: FAQ JSON 파일 경로
        """
        self.faq_data = {}
        self.conversation_history = {}
        
        # FAQ 데이터 로드
        if faq_file_path:
            self.load_faq_data(faq_file_path)
        
        # 사용자 타입 분류를 위한 키워드
        self.blogger_keywords = [
            "블로거", "등급", "리뷰", "포인트", "환급", "블로그", "랭킹",
            "심사", "화이트", "블랙", "레드", "슈퍼차트", "캠페인", "원고"
        ]
        
        self.advertiser_keywords = [
            "광고주", "사장님", "매장", "업체", "결제", "세금계산서", 
            "할부", "패키지", "광고", "체험단", "모집", "해지"
        ]
        
        # 제품/매장 구분 키워드
        self.product_keywords = ["제품", "배송", "출고", "구매", "환급금"]
        self.store_keywords = ["매장", "방문", "예약", "체험", "이용코드"]
    
    def load_faq_data(self, file_path: str):
        """FAQ 데이터 로드"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.faq_data = json.load(f)
            logger.info(f"FAQ 데이터 로드 완료: {file_path}")
        except Exception as e:
            logger.error(f"FAQ 데이터 로드 실패: {e}")
            # 기본 FAQ 데이터 사용
            self.faq_data = {"블로거": [], "광고주": []}
    
    def classify_user_type(self, message: str, conversation_id: str = None) -> str:
        """
        사용자 타입 분류 (블로거 vs 광고주)
        
        Args:
            message: 사용자 메시지
            conversation_id: 대화 ID
            
        Returns:
            "블로거" 또는 "광고주"
        """
        # 대화 기록에서 이전 분류 확인
        if conversation_id and conversation_id in self.conversation_history:
            if self.conversation_history[conversation_id].get("user_type"):
                return self.conversation_history[conversation_id]["user_type"]
        
        message_lower = message.lower()
        
        # 키워드 매칭 점수 계산
        blogger_score = sum(1 for keyword in self.blogger_keywords if keyword in message_lower)
        advertiser_score = sum(1 for keyword in self.advertiser_keywords if keyword in message_lower)
        
        # 사용자 타입 결정
        user_type = "광고주" if advertiser_score > blogger_score else "블로거"
        
        # 대화 기록에 저장
        if conversation_id:
            if conversation_id not in self.conversation_history:
                self.conversation_history[conversation_id] = {}
            self.conversation_history[conversation_id]["user_type"] = user_type
        
        return user_type
    
    def find_best_answer(self, message: str, user_type: str) -> Optional[Dict]:
        """
        메시지에 가장 적합한 FAQ 답변 찾기
        
        Args:
            message: 사용자 메시지
            user_type: 사용자 타입 ("블로거" 또는 "광고주")
            
        Returns:
            가장 적합한 FAQ 항목 또는 None
        """
        if user_type not in self.faq_data:
            return None
        
        message_lower = message.lower()
        best_match = None
        best_score = 0
        
        # FAQ 항목별로 점수 계산
        for faq_item in self.faq_data[user_type]:
            if not faq_item.get("question") or not faq_item.get("answer"):
                continue
            
            question_lower = faq_item["question"].lower()
            
            # 완전 일치
            if message_lower == question_lower:
                return faq_item
            
            # 부분 일치 점수 계산
            score = 0
            
            # 질문에 포함된 단어 비교
            message_words = set(re.findall(r'\w+', message_lower))
            question_words = set(re.findall(r'\w+', question_lower))
            
            # 공통 단어 개수
            common_words = message_words & question_words
            if common_words:
                score = len(common_words) / max(len(message_words), len(question_words))
            
            # 핵심 키워드 포함 여부 (가중치 부여)
            important_keywords = ["안되", "어떻게", "언제", "왜", "문제", "불가", "가능"]
            for keyword in important_keywords:
                if keyword in message_lower and keyword in question_lower:
                    score += 0.2
            
            # 최고 점수 업데이트
            if score > best_score and score > 0.3:  # 최소 임계값
                best_score = score
                best_match = faq_item
        
        return best_match
    
    def generate_response(self, message: str, conversation_id: str = None) -> str:
        """
        사용자 메시지에 대한 응답 생성
        
        Args:
            message: 사용자 메시지
            conversation_id: 대화 ID (대화 기록 추적용)
            
        Returns:
            챗봇 응답
        """
        # 대화 기록 초기화
        if conversation_id and conversation_id not in self.conversation_history:
            self.conversation_history[conversation_id] = {
                "messages": [],
                "user_type": None,
                "created_at": datetime.now()
            }
        
        # 메시지 기록
        if conversation_id:
            self.conversation_history[conversation_id]["messages"].append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now()
            })
        
        # 사용자 타입 분류
        user_type = self.classify_user_type(message, conversation_id)
        
        # FAQ에서 답변 찾기
        faq_match = self.find_best_answer(message, user_type)
        
        if faq_match:
            response = faq_match["answer"]
            
            # 제품/매장 타입에 따른 추가 정보
            if faq_match.get("type"):
                if "제품" in faq_match["type"] and any(kw in message for kw in self.product_keywords):
                    response += "\n\n💡 제품 관련 추가 문의사항이 있으시면 말씀해 주세요."
                elif "매장" in faq_match["type"] and any(kw in message for kw in self.store_keywords):
                    response += "\n\n📍 매장 관련 추가 문의사항이 있으시면 말씀해 주세요."
        else:
            # FAQ에 없는 경우 기본 응답
            if user_type == "블로거":
                response = self._get_default_blogger_response(message)
            else:
                response = self._get_default_advertiser_response(message)
        
        # 응답 기록
        if conversation_id:
            self.conversation_history[conversation_id]["messages"].append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.now()
            })
        
        return response
    
    def _get_default_blogger_response(self, message: str) -> str:
        """블로거용 기본 응답"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["안녕", "반가", "하이"]):
            return "안녕하세요! 슈퍼멤버스 블로거님 👋\n무엇을 도와드릴까요? 등급, 리뷰, 포인트 등 궁금하신 점을 말씀해 주세요."
        
        elif any(word in message_lower for word in ["감사", "고마"]):
            return "감사합니다! 슈퍼멤버스와 함께해 주셔서 감사해요 😊\n더 도움이 필요하시면 언제든 문의해 주세요."
        
        elif any(word in message_lower for word in ["등급", "심사"]):
            return "등급 관련 문의를 주셨네요. 구체적으로 어떤 점이 궁금하신가요?\n- 등급 심사 기간\n- 등급 재심사\n- 등급 변경 사유\n위 내용 중 궁금하신 점을 선택해 주세요."
        
        else:
            return "[null]"
    
    def _get_default_advertiser_response(self, message: str) -> str:
        """광고주용 기본 응답"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["안녕", "반가", "하이"]):
            return "안녕하세요! 슈퍼멤버스 광고주님 👋\n광고 진행, 결제, 체험단 관리 등 무엇을 도와드릴까요?"
        
        elif any(word in message_lower for word in ["감사", "고마"]):
            return "감사합니다! 슈퍼멤버스를 선택해 주셔서 감사해요 😊\n광고 효과를 극대화할 수 있도록 최선을 다하겠습니다."
        
        elif any(word in message_lower for word in ["광고", "시작", "진행"]):
            return "광고 진행을 원하시는군요! 다음 순서로 진행됩니다:\n1. 슈퍼멤버스 홈페이지 회원가입\n2. 채팅으로 상호명 전달\n3. 광고 정보 및 카드 등록\n4. 광고 검수 및 시작\n\n자세한 안내가 필요하시면 말씀해 주세요."
        
        else:
            return "[null]"
    
    def get_conversation_summary(self, conversation_id: str) -> str:
        """대화 요약 생성"""
        if conversation_id not in self.conversation_history:
            return "대화 기록이 없습니다."
        
        history = self.conversation_history[conversation_id]
        user_type = history.get("user_type", "미분류")
        message_count = len([m for m in history["messages"] if m["role"] == "user"])
        
        summary = f"사용자 타입: {user_type}\n"
        summary += f"총 문의 횟수: {message_count}회\n"
        summary += f"대화 시작: {history['created_at'].strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # 최근 3개 메시지 요약
        recent_messages = history["messages"][-6:]  # 사용자/봇 각 3개
        if recent_messages:
            summary += "\n최근 대화:\n"
            for msg in recent_messages:
                role = "고객" if msg["role"] == "user" else "챗봇"
                summary += f"- {role}: {msg['content'][:50]}...\n"
        
        return summary


# 테스트용 함수
def test_chatbot():
    """챗봇 테스트"""
    # FAQ 파일 경로
    faq_path = "qna.json"
    
    # 챗봇 초기화
    chatbot = SuperMembersChatbot(faq_path)
    
    # 테스트 메시지들
    test_messages = [
        "안녕하세요",
        "블로거 등급 재심사는 언제인가요?",
        "제품 환급은 언제 받을 수 있나요?",
        "광고 진행하고 싶어요",
        "세금계산서 발행 가능한가요?",
        "알 수 없는 질문입니다"
    ]
    
    print("=== 슈퍼멤버스 챗봇 테스트 ===\n")
    
    for msg in test_messages:
        print(f"사용자: {msg}")
        response = chatbot.generate_response(msg, "test_conversation")
        print(f"챗봇: {response}\n")
        print("-" * 50 + "\n")


if __name__ == "__main__":
    test_chatbot()