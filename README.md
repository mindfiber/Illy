# Astrology

헬레니스틱 점성학 연구, 교안 작성, 실제 차트 해석, 생시보정 툴 개발을 함께 관리하는 프로젝트.

## Folder Structure

```text
Astrology/
  rectification-tool/      # 생시보정 계산/검증/이벤트 처리
  hellenistic-notes/       # 헬레니스틱 이론 정리, 교안 초안
  chart-readings/          # 실제 차트 해석 기록
  references/              # 원전, 번역, 규칙표, 용어집
  prompts/                 # 해석용 프롬프트/작업 지침
  AGENTS.md                # 전체 작업 규칙
```

## Design Principle

생시보정 툴은 계산/검증 중심으로 엄격하게 분리한다.
헬레니스틱 해석, 교안, 연구 노트는 별도 지침을 적용하여 자유롭게 해석과 문서화를 수행한다.
