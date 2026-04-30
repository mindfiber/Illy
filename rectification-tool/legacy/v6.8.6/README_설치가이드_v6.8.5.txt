EXE PD 패킷 생성기 v6.8.5 (placeDB 에러 수정)
=============================================

핵심 수정
- EXE 실행 폴더 옆의 assets/placeDB.csv 를 우선 사용(교체 반영됨)
- 입력 행에서 도시 칼럼 위치를 고정 가정하지 않고, 전체 셀을 스캔하여 도시를 찾음
- A열 숨김 등으로 생기는 '선행 빈 탭' 자동 제거

폴더 구조
---------
EXE_PD_engine_v6.8.5.py
requirements_EXE_PD_engine_v6.8.5.txt
build_windows_EXE_PD_engine_v6.8.5.bat
assets/
  placeDB.csv
  ephe/ (Swiss Ephemeris 파일들)

빌드(처음 1번)
--------------
build_windows_EXE_PD_engine_v6.8.5.bat 더블클릭
dist\EXE_PD_engine_v6.8.5.exe 생성

사용(매번)
----------
EXE 실행 → 고객 1행 전체 복붙 → PD ZIP 생성
출력: YYMMDD_고객명_PD.zip

주의
----
- PD 계산 코어는 별도 구현 필요(현재 pd_hits.parquet는 빈 테이블)
