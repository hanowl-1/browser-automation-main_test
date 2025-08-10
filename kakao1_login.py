#!/usr/bin/env python3
"""
Kakao Channel 대화 수집 자동화
Browser Use를 사용하여 카카오 채널 관리자 페이지에서
새 메시지가 없는 채팅방만 열어 대화를 문답(JSON 배열)으로 수집하고
수집 결과를 슬랙 웹훅으로 전송합니다.
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


def _strip_code_fences(s: str) -> str:
    # ```json ... ``` 또는 ``` ... ``` 제거
    s = re.sub(r"```json\s*([\s\S]*?)\s*```", r"\1", s, flags=re.IGNORECASE)
    s = re.sub(r"```\s*([\s\S]*?)\s*```", r"\1", s)
    return s


def _strip_invisible(s: str) -> str:
    # BOM, 제로폭 공백 등 포맷 문자 제거
    return "".join(ch for ch in s if unicodedata.category(ch) != "Cf")


def _extract_bracket_block(s: str) -> str:
    # 가장 바깥 대괄호 배열 또는 객체를 찾아 반환 (휴리스틱)
    first = s.find("[")
    last = s.rfind("]")
    if first != -1 and last != -1 and last > first:
        return s[first:last + 1].strip()
    first = s.find("{")
    last = s.rfind("}")
    if first != -1 and last != -1 and last > first:
        return s[first:last + 1].strip()
    return s.strip()


def _safe_json_candidate(text: str) -> Optional[str]:
    """텍스트가 JSON 배열/객체처럼 보이면 원문 반환, 아니면 None."""
    t = (text or "").strip()
    if t.startswith("[") or t.startswith("{"):
        # 주석 라인 제거 시도
        t = re.sub(r"^\s*//.*$", "", t, flags=re.MULTILINE)
        return t
    return None


def _find_last_parseable_json_block(text: str) -> Optional[str]:
    """문자열에서 실제 json.loads가 성공하는 마지막 JSON 배열/객체 블록을 반환."""
    if not text:
        return None
    s = _strip_code_fences(_strip_invisible(text))

    # 1) 'Result:' 이후 꼬리에서 먼저 탐색 (우선순위 높음)
    tail = None
    m_tail = re.search(r"Result:\s*([\s\S]+)$", s)
    if m_tail:
        tail = m_tail.group(1)
    search_spaces = [t for t in [tail, s] if t]

    for space in search_spaces:
        candidates: list[str] = []
        # 배열 → 객체 순으로 수집하되, 마지막 성공 후보를 선택
        for pattern in (r"\[[\s\S]*?\]", r"\{[\s\S]*?\}"):
            try:
                for m in re.finditer(pattern, space):
                    block = m.group(0)
                    try:
                        json.loads(block)
                        candidates.append(block)
                    except Exception:
                        continue
            except Exception:
                continue
        # 배열을 우선 반환, 없으면 마지막 객체 반환
        arrays = [c for c in candidates if c.strip().startswith("[")]
        if arrays:
            return arrays[-1]
        if candidates:
            return candidates[-1]

    return None


def _find_json_array_stack(text: str) -> Optional[str]:
    """문자열을 한 글자씩 순회하며 따옴표/이스케이프/배열 괄호 균형을 추적해 완전한 첫 JSON 배열 서브스트링을 찾는다."""
    if not text:
        return None
    s = _strip_code_fences(_strip_invisible(text))
    in_string = False
    string_quote = ''
    escape = False
    level = 0
    start_idx = -1
    for i, ch in enumerate(s):
        if in_string:
            if escape:
                escape = False
                continue
            if ch == '\\':
                escape = True
                continue
            if ch == string_quote:
                in_string = False
            continue
        # not in string
        if ch in ('"', "'"):
            in_string = True
            string_quote = ch
            continue
        if ch == '[':
            if level == 0:
                start_idx = i
            level += 1
            continue
        if ch == ']':
            if level > 0:
                level -= 1
                if level == 0 and start_idx != -1:
                    block = s[start_idx:i+1]
                    try:
                        json.loads(block)
                        return block
                    except Exception:
                        # 계속 탐색
                        start_idx = -1
                        continue
    return None


def _find_best_json_array(text: str) -> Optional[str]:
    """문자열에서 파싱 가능한 모든 JSON 배열 후보 중 도메인 스키마에 가장 잘 맞는 배열을 선택."""
    if not text:
        return None
    s = _strip_code_fences(_strip_invisible(text))

    def _score_array_block(block: str) -> tuple[int, Optional[str]]:
        try:
            data = json.loads(block)
        except Exception:
            return (-9999, None)
        if not isinstance(data, list):
            return (-9999, None)
        score = 0
        # 1) 첫 원소가 dict인지 (필수)
        if len(data) > 0 and isinstance(data[0], dict):
            score += 3
        else:
            # 첫 원소가 dict가 아니면 강한 패널티
            return (-9999, None)
        # 2) 키 일치도
        if len(data) > 0 and isinstance(data[0], dict):
            first = data[0]
            for k in ("roomId", "roomName", "conversations", "messages", "userHint"):
                if k in first:
                    score += 2
            # conversations/messages 내부 구조 가점
            conv = first.get("conversations") or first.get("messages")
            if isinstance(conv, list) and len(conv) > 0 and isinstance(conv[0], dict):
                for k in ("speaker", "text", "timestamp"):
                    if k in conv[0]:
                        score += 1
        return (score, block)

    best_block: Optional[str] = None
    best_score = -9999

    # 0) 'Result:' 꼬리 우선 스캔
    tail = None
    m_tail = re.search(r"Result:\s*([\s\S]+)$", s)
    if m_tail:
        tail = m_tail.group(1)
    search_spaces = [t for t in [tail, s] if t]

    for space in search_spaces:
        for m in re.finditer(r"\[[\s\S]*?\]", space):
            block = m.group(0)
            sc, chosen = _score_array_block(block)
            if chosen is not None and sc > best_score:
                best_score = sc
                best_block = chosen
        if best_block is not None:
            break  # 꼬리에서 찾았으면 그걸 우선 사용

    # 최소 점수 기준 미달 시 None
    if best_score < 5:
        return None
    return best_block


# 직전 함수들(_find_last_parseable_json_block, _find_json_array_stack, _find_best_json_array) 위/아래 컨텍스트 유지


def _iter_json_arrays_stack(text: str):
    """텍스트에서 문자열 리터럴과 이스케이프를 인지하며 대괄호 균형 기반으로
    모든 JSON 배열 서브스트링을 순서대로 산출한다."""
    if not text:
        return
    s = _strip_code_fences(_strip_invisible(text))
    idx = 0
    n = len(s)
    while idx < n:
        in_string = False
        string_quote = ''
        escape = False
        level = 0
        start_idx = -1
        i = idx
        found_any = False
        while i < n:
            ch = s[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == '\\':
                    escape = True
                elif ch == string_quote:
                    in_string = False
                i += 1
                continue
            # not in string
            if ch in ('"', "'"):
                in_string = True
                string_quote = ch
                i += 1
                continue
            if ch == '[':
                if level == 0:
                    start_idx = i
                level += 1
                i += 1
                continue
            if ch == ']':
                if level > 0:
                    level -= 1
                    if level == 0 and start_idx != -1:
                        block = s[start_idx:i+1]
                        try:
                            json.loads(block)
                            yield block
                            found_any = True
                            idx = i + 1
                            break
                        except Exception:
                            start_idx = -1
                i += 1
                continue
            i += 1
        if not found_any:
            break


def _iter_json_arrays_lenient(text: str):
    """따옴표 구간을 고려하지 않고, 대괄호 균형만으로 전체 텍스트에서 JSON 배열 서브스트링을 모두 찾는다.
    repr 문자열처럼 따옴표 내부에 배열이 들어있는 경우를 포착하기 위한 최후의 수단."""
    if not text:
        return
    s = _strip_code_fences(_strip_invisible(text))
    level = 0
    start_idx = -1
    for i, ch in enumerate(s):
        if ch == '[':
            if level == 0:
                start_idx = i
            level += 1
        elif ch == ']':
            if level > 0:
                level -= 1
                if level == 0 and start_idx != -1:
                    block = s[start_idx:i+1]
                    try:
                        json.loads(block)
                        yield block
                    except Exception:
                        pass
    return


def _score_array_block_for_domain(block: str) -> int:
    try:
        data = json.loads(block)
    except Exception:
        return -9999
    if not isinstance(data, list):
        return -9999
    score = 0
    # 첫 원소가 dict인지 (필수)
    if len(data) > 0 and isinstance(data[0], dict):
        score += 3
    else:
        return -9999
    # 키 일치도 가점
    first = data[0]
    for k in ("roomId", "roomName", "conversations", "messages", "userHint"):
        if k in first:
            score += 2
    conv = first.get("conversations") or first.get("messages") if isinstance(first, dict) else None
    if isinstance(conv, list) and len(conv) > 0 and isinstance(conv[0], dict):
        for k in ("speaker", "text", "timestamp"):
            if k in conv[0]:
                score += 1
    return score


def _pick_best_array_from_text(text: str) -> Optional[str]:
    """텍스트에서 발견 가능한 모든 배열 후보를 수집해 스키마 점수로 최적 후보를 선택."""
    if not text:
        return None
    best_block = None
    best_score = -9999
    # 1) 스택 기반 배열 전수 스캔 (따옴표 인지)
    for block in _iter_json_arrays_stack(text):
        sc = _score_array_block_for_domain(block)
        if sc > best_score:
            best_score = sc
            best_block = block
            # 빠른 종료 기준 (충분 가점일 때)
            if best_score >= 7:
                break
    # 2) 여전히 부족하면 lenient 스캐너로 재시도(따옴표 무시)
    if best_score < 5:
        for block in _iter_json_arrays_lenient(text):
            sc = _score_array_block_for_domain(block)
            if sc > best_score:
                best_score = sc
                best_block = block
                if best_score >= 7:
                    break
    # 2) 점수 미달 시 None
    if best_score < 5:
        return None
    return best_block


def _find_array_after_last_result(text: str) -> Optional[str]:
    """문자열에서 마지막 'Result:' 이후 꼬리 영역만 대상으로 최적 JSON 배열을 선택."""
    if not text:
        return None
    s = _strip_code_fences(_strip_invisible(text))
    last = None
    for m in re.finditer(r"Result:\s*", s):
        last = m
    if not last:
        return None
    tail = s[last.end():]
    # 꼬리에서 최적 후보 선택 (스택 기반 전수 + lenient + 스키마 점수)
    picked = _pick_best_array_from_text(tail)
    if picked:
        return picked
    # 보조: 스키마 점수 기반 전체 탐색
    arr = _find_best_json_array(tail)
    if arr:
        return arr
    # 마지막 파싱 가능한 블록 보조
    arr = _find_last_parseable_json_block(tail)
    return arr


def _find_any_json_array(text: str) -> Optional[str]:
    """스키마 점수 기반으로 최적 배열을 선택하되, 필요한 경우에만 일반 폴백으로 내려간다."""
    if not text:
        return None
    # 0) 마지막 Result: 꼬리 우선
    tail_arr = _find_array_after_last_result(text)
    if tail_arr:
        try:
            json.loads(tail_arr)
            return tail_arr
        except Exception:
            pass
    # 1) 전체 문자열에서 최적 후보 선택 (stack+lenient)
    picked = _pick_best_array_from_text(text)
    if picked:
        return picked
    # 2) 마지막 파싱 가능한 블록
    block = _find_last_parseable_json_block(text)
    if block:
        try:
            # 가능한 경우 객체가 아닌 배열일 때만 허용
            data = json.loads(block)
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return block
        except Exception:
            return None
    return None


def _extract_quoted_strings(text: str, pattern: str) -> List[str]:
    """pattern의 첫 번째 캡처 그룹이 따옴표로 둘러싸인 문자열 전체가 되도록 하고,
    이를 ast.literal_eval로 안전하게 디코드해 실제 문자열 리스트를 반환한다."""
    results: List[str] = []
    try:
        for m in re.finditer(pattern, text, flags=re.DOTALL):
            quoted = m.group(1)
            try:
                decoded = ast.literal_eval(quoted)
                if isinstance(decoded, str):
                    results.append(decoded)
            except Exception:
                # 디코딩 실패 시 원문을 보관
                results.append(quoted.strip("'\""))
    except Exception:
        pass
    return results

def _extract_json_from_agent_repr(text: str) -> Optional[str]:
    """AgentHistoryList 같은 Python repr 문자열에서 'done.text'나 'extracted_content' 내부의
    JSON 배열을 찾아 최적 후보 1개를 반환한다."""
    if not text:
        return None
    s = _strip_code_fences(_strip_invisible(text))
    candidates: List[str] = []

    # 1) done.text 안쪽 문자열 추출 (단일/삼중 따옴표 모두)
    pat_done = r"['\"]done['\"]\s*[:=]\s*\{[\s\S]*?['\"]text['\"]\s*[:=]\s*('''[\s\S]*?'''|'[\s\S]*?'|\"\"\"[\s\S]*?\"\"\"|\"[\s\S]*?\")[\s\S]*?\}"
    for inner in _extract_quoted_strings(s, pat_done):
        # 안쪽 문자열에서 실제 JSON 배열을 찾는다 (stack+lenient)
        arr = _find_any_json_array(inner)
        if arr:
            candidates.append(arr)

    # 2) extracted_content 안쪽 문자열도 검사 (최신 항목이 뒤에 올 확률 높음)
    pat_ec = r"extracted_content\s*[=:]\s*('''[\s\S]*?'''|'[\s\S]*?'|\"\"\"[\s\S]*?\"\"\"|\"[\s\S]*?\")"
    for inner in _extract_quoted_strings(s, pat_ec):
        arr = _find_any_json_array(inner)
        if arr:
            candidates.append(arr)

    # 3) 마지막 수단: repr 전체에서 lenient로 직접 배열 찾기
    if not candidates:
        for block in _iter_json_arrays_lenient(s):
            try:
                data = json.loads(block)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    candidates.append(block)
            except Exception:
                continue

    if not candidates:
        return None
    return candidates[-1]


def extract_json_text(result_obj: Any) -> str:
    """에이전트 반환(result_obj)에서 최종 JSON 텍스트를 우선순위로 추출한다."""
    # 0) 구조화된 속성(result/final_result/output 등) 우선 확인
    try:
        for attr in ("result", "final_result", "output", "content", "text"):
            if hasattr(result_obj, attr):
                val = getattr(result_obj, attr)
                if isinstance(val, (list, dict)):
                    return json.dumps(val, ensure_ascii=False)
                if isinstance(val, str):
                    cand = _find_any_json_array(val)
                    if cand:
                        return cand
    except Exception:
        pass

    # 1) 마지막 단계에서 '[]' 리터럴이 보이면 최우선 채택
    try:
        all_results = getattr(result_obj, "all_results", None)
        if all_results:
            last = all_results[-1]
            last_ec = getattr(last, "extracted_content", None) or ""
            if re.fullmatch(r"\s*\[\s*\]\s*", last_ec or ""):
                return "[]"
            last_ltm = getattr(last, "long_term_memory", "") or ""
            if "[]" in last_ltm:
                return "[]"
    except Exception:
        pass

    # 2) all_results의 마지막(extracted_content)와 memory에서 도메인 스키마에 맞는 배열을 찾음
    try:
        all_results = getattr(result_obj, "all_results", None)
        if all_results:
            for ar in reversed(all_results):
                ec = getattr(ar, "extracted_content", None) or ""
                if re.fullmatch(r"\s*\[\s*\]\s*", ec):
                    return "[]"
                cand = _find_any_json_array(ec)
                if cand:
                    return cand
            for ar in reversed(all_results):
                ltm = getattr(ar, "long_term_memory", "") or ""
                if "[]" in ltm:
                    return "[]"
                cand = _find_any_json_array(ltm)
                if cand:
                    return cand
    except Exception:
        pass

    # 2.5) all_model_outputs에서 done.text 탐색
    try:
        mos = getattr(result_obj, "all_model_outputs", None)
        if mos and isinstance(mos, list):
            for mo in reversed(mos):
                try:
                    if isinstance(mo, dict):
                        dv = mo.get("done")
                        # done이 dict인 경우 text 필드 우선
                        if isinstance(dv, dict):
                            dt = dv.get("text") or ""
                            cand = _find_any_json_array(dt)
                            if cand:
                                return cand
                        # done이 문자열인 경우 직접 파싱
                        elif isinstance(dv, str):
                            cand = _find_any_json_array(dv)
                            if cand:
                                return cand
                except Exception:
                    continue
    except Exception:
        pass

    # 3) 문자열 전체에서 최적 배열 찾기 (최후 수단)
    try:
        s = str(result_obj)
        cand = _find_any_json_array(s)
        if cand:
            return cand
    except Exception:
        pass

    return ""


def print_pretty_summary(agent_result: Any, parsed_json: Optional[List[dict]], sent_count: int) -> None:
    print("\n🧾 실행 요약")
    print("-" * 50)
    try:
        steps = getattr(agent_result, "all_results", []) or []
        steps_count = len(steps)
        if steps_count == 0:
            # 문자열 기반 폴백 카운트 (ActionResult 등장 회수)
            try:
                txt = str(agent_result) if agent_result is not None else ""
                m = re.findall(r"ActionResult\(", txt)
                if m:
                    steps_count = len(m)
            except Exception:
                pass
        print(f"총 단계 수: {steps_count}")
        max_show = 8
        for idx, ar in enumerate(steps[-max_show:]):
            et = getattr(ar, "extracted_content", None)
            et_preview = (et or "").strip().replace("\n", " ")
            if len(et_preview) > 160:
                et_preview = et_preview[:160] + "..."
            ltm = getattr(ar, "long_term_memory", "") or ""
            ltm_preview = ltm.strip().replace("\n", " ")
            if len(ltm_preview) > 160:
                ltm_preview = ltm_preview[:160] + "..."
            print(f"[{idx+1}] extracted: {et_preview}")
            if ltm_preview:
                print(f"    memory: {ltm_preview}")
    except Exception:
        print("단계 요약 생성 중 오류가 발생했지만, 실행은 계속됩니다.")
    print(f"슬랙 전송 건수: {sent_count}")
    print("-" * 50)

    # 파일 저장
    try:
        os.makedirs("logs", exist_ok=True)
        # 요약 텍스트
        with open(os.path.join("logs", "run.txt"), "w", encoding="utf-8") as f:
            # 파일 기록도 문자열 폴백 카운트 적용
            steps = getattr(agent_result, "all_results", []) or []
            steps_count = len(steps)
            if steps_count == 0:
                try:
                    txt = str(agent_result) if agent_result is not None else ""
                    m = re.findall(r"ActionResult\(", txt)
                    if m:
                        steps_count = len(m)
                except Exception:
                    pass
            f.write("총 단계 수: " + str(steps_count) + "\n")
            for ar in getattr(agent_result, "all_results", []) or []:
                et = (getattr(ar, "extracted_content", "") or "").strip()
                ltm = (getattr(ar, "long_term_memory", "") or "").strip()
                f.write(f"- extracted: {et}\n")
                if ltm:
                    f.write(f"  memory: {ltm}\n")
            f.write(f"슬랙 전송 건수: {sent_count}\n")
        # JSON 저장
        if parsed_json is not None:
            with open(os.path.join("logs", "summary.json"), "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, ensure_ascii=False, indent=2)
    except Exception:
        print("로그 파일 저장 중 오류가 발생했습니다.")


def _collect_numeric_ids_from_obj(obj: Any) -> List[str]:
    """중첩 객체에서 숫자 ID 후보(13~19자리)를 모두 수집."""
    found: set[str] = set()
    def _walk(x: Any):
        try:
            if isinstance(x, dict):
                for k, v in x.items():
                    _walk(k)
                    _walk(v)
            elif isinstance(x, list):
                for v in x:
                    _walk(v)
            elif isinstance(x, (str, bytes)):
                s = x if isinstance(x, str) else x.decode("utf-8", errors="ignore")
                for m in re.finditer(r"\b\d{13,19}\b", s):
                    found.add(m.group(0))
            elif isinstance(x, (int,)):
                s = str(x)
                if 13 <= len(s) <= 19:
                    found.add(s)
        except Exception:
            pass
    _walk(obj)
    return sorted(found)


async def on_step_start_extract_spa_ids(agent) -> None:
    """채팅 목록 페이지에서 SPA 내부 상태를 읽어 채팅방 ID 후보를 추출해 로그에 기록."""
    try:
        page = await agent.browser_session.get_current_page()
        # 페이지가 닫혔거나 컨텍스트가 없는 경우 안전 종료
        try:
            _ = page.url
        except Exception:
            return
        url = page.url
        # 로그인/계정 도메인일 경우 훅 작동 금지
        if "accounts.kakao.com" in url:
            return
        # 목록 페이지이되 상세가 아닌 경우에만 시도
        if "/_gwELG/chats" in url and "/chats/" not in url:
            # 로드 상태 안정화 대기 (최대 5초)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
            except Exception:
                pass
            # evaluate 재시도(최대 3회, 0.3s 증가 대기)
            nd = None
            ap = None
            last_error = None
            for i in range(3):
                try:
                    state = await page.evaluate("() => ({ nd: (window.__NEXT_DATA__ ?? null), apollo: (window.__APOLLO_STATE__ ?? null) })")
                    nd = state.get("nd") if isinstance(state, dict) else None
                    ap = state.get("apollo") if isinstance(state, dict) else None
                    break
                except Exception as e:
                    last_error = e
                    await asyncio.sleep(0.3 * (i + 1))
            # 스크립트 태그 시도
            if not nd:
                try:
                    nd_text = await page.evaluate("() => (document.querySelector('script#__NEXT_DATA__')?.textContent) || null")
                    if nd_text:
                        try:
                            nd = json.loads(nd_text)
                        except Exception:
                            nd = None
                except Exception:
                    pass
            # DOM에서 /chats/<숫자> 패턴 수집
            href_ids: List[str] = []
            try:
                hrefs = await page.evaluate("() => Array.from(document.querySelectorAll('a[href*=\"/chats/\"]')).map(a => a.getAttribute('href'))")
                if isinstance(hrefs, list):
                    for h in hrefs:
                        if isinstance(h, str):
                            m = re.search(r"/chats/(\d+)", h)
                            if m:
                                href_ids.append(m.group(1))
            except Exception:
                pass
            # 내부 상태에서 숫자 ID 수집
            candidates: List[str] = []
            for obj in [nd, ap]:
                if obj:
                    candidates.extend(_collect_numeric_ids_from_obj(obj))
            # 13~19자리 숫자 중 중복 제거
            unique_ids = sorted(set(href_ids + candidates))
            # 저장 및 요약 출력
            os.makedirs("logs", exist_ok=True)
            out = {"url": url, "nextData_found": bool(nd), "apollo_found": bool(ap), "href_ids": href_ids, "numeric_ids": unique_ids}
            with open(os.path.join("logs", "chat_ids.json"), "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"🔎 SPA 상태 추출: nextData={bool(nd)}, apollo={bool(ap)}, href_ids={len(href_ids)}, numeric_ids={len(unique_ids)}")
    except Exception as e:
        print(f"SPA 상태 추출 훅 오류: {e}")


async def on_step_start_load_full_history(agent) -> None:
    """채팅 상세 페이지에서 스크롤/더보기 클릭을 반복해 과거 메시지를 끝까지 로드한다."""
    try:
        page = await agent.browser_session.get_current_page()
        try:
            current_url = page.url
        except Exception:
            return
        # 상세 채팅 URL에서만 동작
        if not re.search(r"/_gwELG/chats/\d+", current_url):
            return

        async def eval_scroll_once() -> dict:
            return await page.evaluate(
                """
                () => {
                  // 스크롤 가능한 컨테이너 후보 찾기
                  const all = Array.from(document.querySelectorAll('*'));
                  const candidates = all.filter(el => {
                    const s = getComputedStyle(el);
                    const over = s.overflowY;
                    const scrollable = (over === 'auto' || over === 'scroll');
                    return scrollable && el.clientHeight > 150 && el.scrollHeight > el.clientHeight + 20 && typeof el.scrollTop === 'number';
                  });
                  // 가장 큰 scrollHeight를 가진 컨테이너 선택, 없으면 문서 루트
                  const pick = (candidates.sort((a,b) => (b.scrollHeight - a.scrollHeight))[0]) || document.scrollingElement || document.body;
                  const msgSelector = 'li, [role="listitem"], .message, .msg, .bubble';
                  const countBefore = pick.querySelectorAll(msgSelector).length;
                  const prevTop = pick.scrollTop;

                  // 최상단으로 스크롤
                  pick.scrollTop = 0;

                  // 상단에 더보기/이전 버튼이 있으면 클릭
                  const labels = ['이전', '더보기', '이전 대화', 'more', 'previous', 'load'];
                  const buttons = Array.from(pick.querySelectorAll('button, a'))
                    .filter(b => {
                      const t = (b.textContent || '').toLowerCase();
                      return labels.some(x => t.includes(x));
                    })
                    .slice(0, 3);
                  buttons.forEach(b => b.click());

                  return { countBefore, prevTop };
                }
                """
            )

        async def eval_state() -> dict:
            return await page.evaluate(
                """
                () => {
                  const all = Array.from(document.querySelectorAll('*'));
                  const candidates = all.filter(el => {
                    const s = getComputedStyle(el);
                    const over = s.overflowY;
                    const scrollable = (over === 'auto' || over === 'scroll');
                    return scrollable && el.clientHeight > 150 && el.scrollHeight > el.clientHeight + 20 && typeof el.scrollTop === 'number';
                  });
                  const pick = (candidates.sort((a,b) => (b.scrollHeight - a.scrollHeight))[0]) || document.scrollingElement || document.body;
                  const msgSelector = 'li, [role="listitem"], .message, .msg, .bubble';
                  const count = pick.querySelectorAll(msgSelector).length;
                  const atTop = Math.abs(pick.scrollTop) <= 2;
                  return { count, atTop, scrollTop: pick.scrollTop, scrollHeight: pick.scrollHeight, clientHeight: pick.clientHeight };
                }
                """
            )

        noIncreaseStreak = 0
        lastCount = -1
        for i in range(40):  # 최대 40회 시도
            try:
                before = await eval_scroll_once()
            except Exception:
                break
            await asyncio.sleep(0.8)
            try:
                after = await eval_state()
            except Exception:
                break

            count = int(after.get('count', 0))
            at_top = bool(after.get('atTop', False))

            if count > lastCount:
                lastCount = count
                noIncreaseStreak = 0
            else:
                noIncreaseStreak += 1

            # 두 번 연속 증가 없음 & 이미 최상단이면 종료
            if noIncreaseStreak >= 2 and at_top:
                print(f"🔼 과거 메시지 로딩 완료 추정: 총 메시지 {count}개, 반복 {i+1}회")
                break
        else:
            print(f"ℹ️ 과거 메시지 로딩 최대 시도 도달(40회). 현재 메시지 수: {lastCount}")
    except Exception as e:
        print(f"히스토리 로딩 훅 오류: {e}")


async def on_step_start_combined(agent) -> None:
    # 목록 페이지에서는 SPA 상태에서 chatId 힌트 추출, 상세 페이지에서는 과거 대화 끝까지 로드
    await on_step_start_extract_spa_ids(agent)
    await on_step_start_load_full_history(agent)


async def on_step_end_collect(agent) -> None:
    """에이전트 각 단계 종료 시 모델 출력/추출물에서 결과 JSON을 찾아 파이썬 변수(PY_RESULTS)에 누적 저장."""
    try:
        # 1) history 전체 문자열에서 우선 탐색 (마지막 Result: 꼬리 최우선)
        try:
            hist_text = str(getattr(getattr(agent, "state", None), "history", ""))
            arr = _find_array_after_last_result(hist_text) or _find_any_json_array(hist_text)
            if arr:
                data = json.loads(arr)
                if isinstance(data, list) and data and isinstance(data[0], dict):
                    PY_RESULTS.extend([x for x in data if isinstance(x, dict)])
        except Exception:
            pass

        # 2) all_results의 마지막 extracted_content에서 보조 탐색
        try:
            hist = getattr(getattr(agent, "state", None), "history", None)
            all_results = getattr(hist, "all_results", None)
            if all_results:
                for ar in reversed(all_results):
                    ec = getattr(ar, "extracted_content", None) or ""
                    arr = _find_array_after_last_result(ec) or _find_any_json_array(ec)
                    if arr:
                        data = json.loads(arr)
                        if isinstance(data, list) and data and isinstance(data[0], dict):
                            PY_RESULTS.extend([x for x in data if isinstance(x, dict)])
                            break
        except Exception:
            pass

        # 3) all_model_outputs의 done.text에서 추가 보조 탐색
        try:
            hist = getattr(getattr(agent, "state", None), "history", None)
            mos = getattr(hist, "all_model_outputs", None)
            if mos and isinstance(mos, list):
                for mo in reversed(mos):
                    try:
                        if isinstance(mo, dict):
                            dv = mo.get("done")
                            dt = None
                            if isinstance(dv, dict):
                                dt = dv.get("text") or ""
                            elif isinstance(dv, str):
                                dt = dv
                            if dt:
                                arr = _find_array_after_last_result(dt) or _find_any_json_array(dt)
                                if arr:
                                    data = json.loads(arr)
                                    if isinstance(data, list) and data and isinstance(data[0], dict):
                                        PY_RESULTS.extend([x for x in data if isinstance(x, dict)])
                                        break
                    except Exception:
                        continue
        except Exception:
            pass
    except Exception:
        pass


async def open_tiktok_shop():
    """
    카카오채널 관리자 페이지를 엽니다.
    """
    print("🚀 카카오채널 관리자 페이지 접속 및 대화 수집 시작...")
    
    # 챗봇 초기화
    chatbot = SuperMembersChatbot(faq_file_path="qna.json")
    print("🤖 슈퍼멤버스 FAQ 챗봇 로드 완료")
    
    # LLM 초기화 (Browser Use의 ChatOpenAI 사용)
    llm = ChatOpenAI(model="gpt-4.1")

    # 에이전트 작업 정의
    task = """
카카오채널 관리자 페이지에서 '새 메시지 있는' 채팅방들만 대상으로 대화 기록을 수집하고, 자동 답변을 전송한 후 결과를 엄격한 JSON으로 반환하라. JSON 외 텍스트/코드펜스/설명 금지.

0) 금지 사항
- write_file 등 파일 생성/수정 액션 금지. todo.md 같은 파일 작성 금지.
- 로그인/대기 구간에서는 done 호출 금지. 결과(JSON)를 반환할 때만 done을 호출한다.

1) 접속/로그인/대기(수동 인증 지원)
- https://center-pf.kakao.com/_gwELG/chats 로 이동해 완전 로드 대기.
- 로그인 필요 시 ID 'vof@nate.com' / PW 'phozphoz1!' 입력.
- reCAPTCHA 등 추가 인증이 나타나면 사용자가 수동으로 인증을 완료할 때까지 기다린다.
- 현재 URL이 https://center-pf.kakao.com/_gwELG/chats (목록)로 바뀔 때까지 3초 간격으로 최대 300회(약 15분) 확인한다.
- 이 단계에서 어떤 경우에도 done을 호출하지 말고, 대기/재시도를 수행한다.

2) '새 메시지 있는' 채팅방 선별 (비전+DOM)
- 각 row의 유저명 오른쪽 '빨간 배경 + 숫자' 배지를 비전으로 판별. 배지가 있으면 '읽지 않음'으로 간주하고 선택.
- 배지 후보: 붉은(#c00~#f44 계열) 배경 사각/원 + 대비되는 숫자 텍스트. class(badge|count|unread), aria/data-*도 보조 단서로 사용.
- 배지가 있는 row만 대상으로 진행. 너무 많으면 상위 3개만 처리(성능 최적화).

3) 채팅방 진입 (팝업 회피 및 탭 전환)
- 우선 DOM에서 row의 outerHTML/속성/인접 스크립트에서 '/chats/<숫자>' 패턴을 탐색해 chatId를 찾을 것.
- 찾으면 go_to_url('https://center-pf.kakao.com/_gwELG/chats/<chatId>').
- 못 찾으면 row를 클릭하되, 클릭 직후 반드시 모든 열린 탭/창의 URL을 조사해 '/chats/\\d+'에 매칭되는 탭으로 즉시 전환. 팝업으로 열렸다면 해당 팝업 탭으로 포커스 이동.
- 전환 후 현재 탭 URL에서 chatId를 추출. 처리 완료 후 상세 탭은 닫고 목록 탭으로 복귀.

4) 대화 전체 로딩
- 상세 뷰에서 대화 스크롤 영역을 최상단까지 반복 스크롤. 더 이상 로드되지 않을 때까지 수행(스크롤 위치/로딩 인디케이터/메시지 카운트 변화로 판단). 스크롤 시도 횟수 상한 30회, '증가 없음' 2회 연속이면 종료.

5) 발화 시퀀스(JSON)
- Q/A 페어링을 하지 말고, 시간순(오름차순)으로 화자와 발화 텍스트를 그대로 나열한다.
- 화자는 말풍선 정렬/닉네임/role label로 판별하여 'customer' 또는 'agent'로 기록하되, 불명확하면 화면 표시명을 그대로 사용.
- 각 발화에 가능한 경우 timestamp를 포함. 사이트 표기(예: 오후03:47)는 ISO8601(예: 2025-07-24T15:47:00)로 정규화 시도하되, 불가하면 원문 그대로 둔다.

6) 자동 답변 전송
- 마지막 고객 메시지를 추출하여 파이썬 코드로 슈퍼멤버스 챗봇을 호출한다.
- 챗봇 응답 생성 과정:
  a) 대화에서 마지막 customer 메시지를 찾는다
  b) 파이썬 코드 실행: 
     from chatbot_handler import SuperMembersChatbot
     chatbot = SuperMembersChatbot('qna.json')
     response = chatbot.generate_response(last_customer_message, room_id)
  c) 생성된 응답을 메시지 입력창에 입력
  d) [null] 응답인 경우 기본 템플릿 사용:
     - 문의/질문 키워드 포함: "안녕하세요! 문의 주신 내용 확인했습니다. 잠시만 기다려 주시면 자세히 안내해 드리겠습니다."
     - 불만/문제 키워드 포함: "불편을 드려 죄송합니다. 빠르게 확인하여 도움드리겠습니다."
     - 기타: "안녕하세요! 무엇을 도와드릴까요?"
- 메시지 입력창에 답변을 입력하고 전송 버튼을 클릭한다.
- 전송 완료 후 해당 채팅방을 나가고 다음 채팅방으로 이동한다.

7) 출력 스키마:
[
  {
    "roomId": "<숫자>",
    "roomName": "방 이름",
    "userHint": "고객 식별 보조(선택)",
    "conversations": [
      {"speaker": "customer", "text": "첫 발화", "timestamp": "2025-07-24T15:47:00"},
      {"speaker": "agent",    "text": "답변",   "timestamp": "2025-07-24T15:49:00"}
    ],
    "autoReply": {
      "sent": true,
      "message": "전송한 자동 답변 내용",
      "timestamp": "2025-07-24T15:50:00"
    }
  }
]

8) 제약
- 반드시 '배지 있는' 채팅방만 포함.
- 최종 결과는 JSON 배열만 반환. 그 외 텍스트/로그/설명/코드펜스 금지.
- 빈 경우 [].

9) 최적화/안정화
- 새 탭/팝업이 뜨면 즉시 '/chats/\\d+' URL 탭으로 전환 후 작업. 작업 후 닫고 목록으로 복귀.
- 시야(비전) 수준은 높게 유지하고, 불확실하면 확대 스냅샷으로 배지 유무 재확인.
    """

    try:
        # 에이전트 생성
        agent = Agent(
            task=task,
            llm=llm,
            browser_config={
                'headless': False,  # 브라우저 창 표시
                'viewport': {'width': 1440, 'height': 900},
            },
            use_vision=True,
            vision_detail_level='high'
        )

        print("⏳ 카카오 채팅방 수집 진행 중...")

        # 에이전트 실행 (SPA 내부 상태 추출 훅 연결)
        result = await agent.run(on_step_start=on_step_start_combined, on_step_end=on_step_end_collect)
 
        print("\n✅ 수집 작업 완료! 요약과 결과를 정리합니다.")
 
        # 실행 직후: 전체 result 문자열 및 done 텍스트를 먼저 기록 (이후 폴백 파싱에서 활용)
        try:
            os.makedirs("logs", exist_ok=True)
            with open(os.path.join("logs", "agent_result.txt"), "w", encoding="utf-8") as f:
                f.write(str(result))
            try:
                done_texts: list[str] = []
                mos = getattr(result, "all_model_outputs", None)
                if mos and isinstance(mos, list):
                    for mo in mos:
                        if isinstance(mo, dict):
                            dv = mo.get("done")
                            if isinstance(dv, dict) and isinstance(dv.get("text"), str):
                                done_texts.append(dv.get("text"))
                            elif isinstance(dv, str):
                                done_texts.append(dv)
                with open(os.path.join("logs", "done_texts.txt"), "w", encoding="utf-8") as f:
                    for i, t in enumerate(done_texts):
                        f.write(f"=== done[{i}] ===\n")
                        f.write((t or "").strip() + "\n\n")
            except Exception:
                pass
        except Exception:
            pass

        # 결과 파싱 및 슬랙 전송 (파이썬 변수 우선)
        sent_count = 0
        parsed: Optional[List[dict]] = None
        if PY_RESULTS:
            parsed = []
            # 중복 제거(간단히 roomId+roomName 기준)
            seen = set()
            for item in PY_RESULTS:
                if not isinstance(item, dict):
                    continue
                key = (item.get("roomId"), item.get("roomName"))
                if key in seen:
                    continue
                seen.add(key)
                parsed.append(item)
                try:
                    text_payload = json.dumps(item, ensure_ascii=False, indent=2)
                    ok = post_to_slack(SLACK_WEBHOOK_URL, text_payload)
                    if ok:
                        sent_count += 1
                        room = item.get("roomName") or item.get("room_id") or "(roomName 없음)"
                        print(f"📤 슬랙 전송 완료: {room}")
                    else:
                        print("⚠️ 슬랙 전송 실패 (상세는 위 오류 참조)")
                except Exception as e:
                    print(f"⚠️ 항목 전송 중 오류: {e}")
        else:
            # 폴백: 기존 파서 사용
            raw_json = extract_json_text(result)
            if not raw_json:
                # 추가 폴백: 에이전트 히스토리 문자열에서 직접 추출
                try:
                    hist_text = str(getattr(getattr(agent, "state", None), "history", ""))
                    cand = _find_any_json_array(hist_text)
                    if cand:
                        raw_json = cand
                except Exception:
                    pass
            if not raw_json:
                # all_model_outputs의 done.text에서 폴백 추출
                try:
                    mos = getattr(result, "all_model_outputs", None)
                    if mos and isinstance(mos, list):
                        for mo in reversed(mos):
                            if isinstance(mo, dict):
                                dv = mo.get("done")
                                if isinstance(dv, dict):
                                    dt = dv.get("text") or ""
                                    cand = _find_any_json_array(dt)
                                    if cand:
                                        raw_json = cand
                                        break
                                elif isinstance(dv, str):
                                    cand = _find_any_json_array(dv)
                                    if cand:
                                        raw_json = cand
                                        break
                except Exception:
                    pass
            if not raw_json:
                # 최후 폴백: result의 문자열 표현에서 추출 (스택 기반 포함)
                try:
                    cand = _find_any_json_array(str(result))
                    if cand:
                        raw_json = cand
                except Exception:
                    pass
            if not raw_json:
                # 파일 폴백: 실행 시 저장된 logs/agent_result.txt 전체에서 추출
                try:
                    if os.path.exists(os.path.join("logs", "agent_result.txt")):
                        with open(os.path.join("logs", "agent_result.txt"), "r", encoding="utf-8") as f:
                            ar_text = f.read()
                        # 1) repr 내부의 done.text / extracted_content 문자열에서 직접 추출
                        cand = _extract_json_from_agent_repr(ar_text)
                        if not cand:
                            # 2) 기존 전체 텍스트 스캔 폴백
                            cand = _find_any_json_array(ar_text)
                        if cand:
                            raw_json = cand
                except Exception:
                    pass
 
            if not raw_json:
                print("❗ 유효한 JSON 텍스트를 추출하지 못했습니다. 원본 요약만 출력합니다.")
            else:
                try:
                    parsed_generic = json.loads(raw_json)
                    # 성공 시 마지막 후보를 agent_last.txt에 기록
                    try:
                        os.makedirs("logs", exist_ok=True)
                        with open(os.path.join("logs", "agent_last.txt"), "w", encoding="utf-8") as f:
                            f.write(raw_json)
                    except Exception:
                        pass
                    if isinstance(parsed_generic, list):
                        parsed_list: List[dict] = []
                        for idx, item in enumerate(parsed_generic):
                            if not isinstance(item, dict):
                                print(f"⚠️ 리스트 {idx}번 항목이 객체가 아님: {type(item).__name__}. 건너뜀")
                                continue
                            parsed_list.append(item)
                            try:
                                text_payload = json.dumps(item, ensure_ascii=False, indent=2)
                                ok = post_to_slack(SLACK_WEBHOOK_URL, text_payload)
                                if ok:
                                    sent_count += 1
                                    room = item.get("roomName") or item.get("room_id") or "(roomName 없음)"
                                    print(f"📤 슬랙 전송 완료: {room}")
                                else:
                                    print("⚠️ 슬랙 전송 실패 (상세는 위 오류 참조)")
                            except Exception as e:
                                print(f"⚠️ 항목 전송 중 오류: {e}")
                        parsed = parsed_list
                    else:
                        print("⚠️ 예상과 다른 형식의 결과입니다. 리스트(JSON 배열)가 아닙니다.")
                except Exception as e:
                    print("❗ JSON 파싱 실패. 원본 일부 미리보기:")
                    preview = raw_json[:400].replace("\n", " ")
                    print(preview)
                    print(f"에러: {e}")
                    try:
                        os.makedirs("logs", exist_ok=True)
                        with open(os.path.join("logs", "agent_last.txt"), "w", encoding="utf-8") as f:
                            f.write(raw_json)
                    except Exception:
                        pass
 
        # 사람이 읽기 쉬운 요약 출력 및 파일 저장
        print_pretty_summary(result, parsed, sent_count)
        # 파이썬 변수 결과 저장(디버깅용)
        try:
            os.makedirs("logs", exist_ok=True)
            to_save = parsed if parsed is not None else (PY_RESULTS if PY_RESULTS else [])
            with open(os.path.join("logs", "py_results.json"), "w", encoding="utf-8") as f:
                json.dump(to_save, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        
        # 브라우저 열린 상태 유지
        if os.getenv("NON_INTERACTIVE") == "1":
            pass
        else:
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
    print("Kakao Channel 대화 수집 및 슬랙 전송")
    print("=" * 60)
    
    await open_tiktok_shop()
    
    print("\n프로그램이 종료되었습니다.")


if __name__ == "__main__":
    asyncio.run(main())