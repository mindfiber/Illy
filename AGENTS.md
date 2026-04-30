# AGENTS.md

# Astrology Project — Root Instructions

이 프로젝트는 크게 네 영역으로 분리한다.

1. `rectification-tool/`
   - 생시보정 계산/검증/이벤트 처리
   - PD 엔진, Morinus 일치화, 후보군 산출
   - 이 폴더 안에서는 `rectification-tool/AGENTS.md`를 최우선 적용한다.

2. `hellenistic-notes/`
   - 헬레니스틱 점성학 이론 정리
   - 강의 교안 초안
   - 연구 노트
   - 이 폴더 안에서는 `hellenistic-notes/INSTRUCTIONS.md`를 적용한다.

3. `chart-readings/`
   - 실제 차트 해석 기록
   - 호러리/네이탈/이벤트 분석
   - 이 폴더 안에서는 `chart-readings/INSTRUCTIONS.md`를 적용한다.

4. `references/`
   - 원전, 번역, 규칙표, 용어집
   - 출처 기반 자료 정리

5. `prompts/`
   - 해석용 프롬프트
   - 리서치용 프롬프트
   - Codex/ChatGPT 작업 지침

## Root Rule

루트 AGENTS.md는 전체 프로젝트 구조 안내용이다.
각 하위 폴더의 세부 작업 규칙은 해당 폴더의 지침 파일을 우선한다.

## Conflict Resolution

- 생시보정 계산/엔진 관련 작업 → `rectification-tool/AGENTS.md`
- 헬레니스틱 이론/교안/강의안 → `hellenistic-notes/INSTRUCTIONS.md`
- 실제 차트 해석 → `chart-readings/INSTRUCTIONS.md`
- 프롬프트 작성/정리 → `prompts/`
- 원전/출처/용어 정리 → `references/`

서로 다른 폴더의 규칙을 섞지 않는다.
