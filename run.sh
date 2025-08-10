#!/bin/bash

# 가상 환경 활성화 및 스크립트 실행
source .venv/bin/activate

# 첫 번째 인자가 있으면 해당 스크립트 실행, 없으면 1_login.py 실행
if [ "$1" ]; then
    python "$@"
else
    python kakao1_login.py
fi