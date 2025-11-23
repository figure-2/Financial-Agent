#!/bin/bash

# 오류 발생 시 즉시 스크립트를 중단합니다.
set -e

echo "--- 데이터베이스 구축을 시작합니다 ---"

echo "1/3: KOSPI/KOSDAQ 지수 데이터 구축 중..."
python index_kospi_kosdaq.py

echo "2/3: 개별 종목 데이터 구축 중..."
python stocks_kospi_kosdaq.py

echo "3/3: 기술적 분석 신호 생성 중..."
python technical_signals.py

echo "--- 모든 작업이 성공적으로 완료되었습니다 ---"