# Rectification Tool Handoff

## Project Purpose

이 프로젝트의 목적은 헬레니스틱/전통 점성학 기반의 생시보정 도구를 만드는 것이다.
핵심은 Morinus의 Primary Directions 계산 결과와 최대한 일치하는 자체 PD 엔진을 만들고, 고객이 자연어로 입력한 인생 사건 목록과 PD hit를 대조해 유효 생시 후보를 산출하는 것이다.

최종 목표는 사용자가 Morinus에서 PD 리스트를 직접 뽑아 주지 않아도, 이 엔진만으로 Morinus와 같은 방식의 PD 계산과 생시보정 후보 산출을 수행하는 것이다.

## Absolute Rules

1. 이 프로젝트에서 만들어야 하는 것은 생시보정 PD 엔진이다.
2. Morinus PD 리스트는 최종 결과 산출용이 아니라 엔진 오류 검증과 고도화를 위한 기준 데이터다.
3. 최종 생시 후보는 반드시 자체 엔진 계산값으로 산출해야 한다.
4. 사용자가 “결과를 가져오라”고 하면 출력 형식은 반드시 다음을 포함한다.
   - 최종 생시 후보 1순위
   - 최종 생시 후보 2순위
   - 최종 생시 후보 3순위
   - 각 후보의 순위 도출 근거
   - 매칭 개수
   - 어떤 사건 종류가 매칭됐는지
   - 해당 후보의 매칭 PD 리스트
   - 미싱 이벤트/PD 리스트
   - 필수 이벤트 미싱 여부
5. 결혼, 출생, 첫 취업, 대학입학, 대학원진학은 필수급 이벤트다.
6. 필수 이벤트가 미싱되면 본순위 후보로 두지 말고 번외/수기검증 대상으로 분리한다.
7. 1사건=1PD로 강제하지 않는다. 한 사건에 복수 PD hit가 있을 수 있으며, 같은 윈도우 안의 유효 hit가 많을수록 가점될 수 있다.
8. 유효 PD의 기본 우선순위는 행성-앵글 / 앵글-행성 / 행성-LoF / LoF-행성이다.
9. ASC, MC, LoF가 핵심 앵글이다. 단, Morinus 출력에서 `Dsc/Desc/DSC`로 표시되는 일부 항목은 실제 작업상 LoF로 읽어야 하는 경우가 있었다.
10. 앵글-앵글 디렉션은 근거 PD로 쓰지 않는다.
11. G그룹 길성 이벤트는 Sun/Jupiter/Venus 중심이다. Saturn/Mars가 G그룹 근거로 나오면 의심해야 한다.
12. K/L 흉성 이벤트는 Mars/Saturn 중심이다.
13. 여성 결혼 이벤트는 Jupiter/Sun/Venus 중심으로 봐야 한다. Moon antiscion 같은 항목을 결혼 핵심 근거로 삼으면 안 된다.
14. 출산 이벤트는 아들은 Jupiter/Sun(+Venus), 딸은 Venus/Jupiter 중심으로 본다. Mercury는 5하우스 로드 등 특수 상황에서만 후순위 참고로 둔다.
15. 대학입학은 11월-3월 hit가 1순위, 4월 hit가 2순위, 5월 hit가 3순위다. 최종 1순위 후보가 대학입학을 5월 hit로만 맞추면 매우 약하다.
16. 취업/커리어 이벤트는 기간이 중요하다. 1년 이상 지속된 일은 메이저 지표로 보기 쉽고, 몇 개월짜리 일은 약하게 보거나 미싱되어도 감안한다.
17. 창업처럼 장기간 이어지는 커리어 사건은 일반 단기 취업보다 우선한다.
18. 고객이 “전후”라고 생시를 적으면 전체 탐색은 보통 전후 30분으로 잡되, 1순위 범위는 전후 15분이다. 2순위 범위는 그 바깥의 유효범위다.
19. 범위가 2시간 이상이면 먼저 Jupiter ingress로 ASC sign 후보를 좁히는 보조 절차를 쓴다.
20. 출력 포맷과 엔진 규칙은 임의로 바꾸지 않는다. 규칙 변경은 사용자 지시가 있을 때만 한다.

## Current Engine State

최근 커밋:

`8d096e4 Replace empirical arc-date offset with Morinus convDate formula`

핵심 반영 사항:

- MorinusWinEng2.7의 `morinus.exe`는 Python 2.5 / PyInstaller 2.0 번들로 확인됐다.
- 디컴파일된 핵심 파일은 `MorinusWinEng2.7/morinus.exe_extracted/out1_manual_extracted/` 아래에 있다.
- 현재 사용 설정은 Placidian semiarc이므로 `placidiansapd_decompiled.py`가 핵심 참조 파일이다.
- `primdirs_decompiled.py`에서 `create()`, `calcTime()`, `getDiff()` 로직을 확인했다.
- **arc→date 변환 공식 확정**: `primdirs_decompiled.py`에서 Morinus Naibod COEFF = 1.01456164 = 365.2422/360 확인.
  - `ti_years = arc * (365.2422/360)`
  - `birth_dec = year + (doy-1) / 365.2422`
  - `event_dec = birth_dec + ti_years`
  - `d_idx = int(frac * 365.0)` (revConvDate는 365.0 사용)
  - 경험적 -2.15 offset 제거. ±1d 정확도 83.6% → 100% (7만 row 기준).
- `Res/placedb.dat` 파서를 추가했다.
- `.hor` 파일 파서를 추가해 Morinus에 실제 저장된 birth data와 좌표를 읽을 수 있게 했다.
- `YongIn`, `Mine`, `ICN`, `Taegu`, `#Seoul` 같은 Morinus 저장 좌표를 회귀 기준에 반영했다.
- ASC/MC를 significator로 받을 때 Morinus는 일반 planet/LoF significator와 다른 별도 공식을 쓴다는 점을 확인했고, `zodiacal_promissor_aspect_to_angle()`에 반영했다.
- **PD 커버리지**: Z-mode core rows 98% 매칭. 나머지 2%는 angle-angle 방향(규칙 10으로 의도적 제외).

## Important Files

- `src/rectification_engine/pd_morinus.py`
  - Morinus식 PD arc 계산 핵심.
  - `zodiacal_promissor_aspect_to_angle()`이 ASC/MC significator용 공식이다.
  - `morinus_create_arc()`는 Morinus `create()`의 arc 정규화 방식을 따른다.

- `src/rectification_engine/places.py`
  - Morinus `Res/placedb.dat` 파서.
  - 사용자가 Morinus에 입력해둔 도시 좌표가 있으면 그 값을 우선 사용한다.

- `src/rectification_engine/morinus_hor.py`
  - Morinus `.hor` 파일 파서.
  - 실제 저장된 생년월일, 시간, 장소명, 위경도를 확인하는 데 쓴다.

- `tools/compare_engine_core_pd.py`
  - Morinus fixture와 엔진 core PD arc를 대조한다.

- `tools/run_regression_suite.py`
  - 여러 케이스에 대해 최종 후보 랭킹, 이벤트-PD 매칭, Morinus audit을 생성한다.

- `input/regression_cases.json`
  - 현재 회귀 검증 케이스.
  - sunny_411_custom, yoo_408, kim_409, illy_personal이 들어 있다.

- `IMMUTABLE_RULES.md`
  - 사용자가 고정한 프로젝트 절대 규칙.

## Morinus Source Findings

중요한 Morinus 디컴파일 참조:

- `placidiansapd_decompiled.py`
  - Placidus semiarc PD 본체.
  - `calcZodPromAspsInterPlanetary`
  - `calcZodAscMC2Planets`
  - `calcZodAscMC2LoF`
  - `calcZodLoF2Planets`
  - `calcZodPlanets2LoF`
  - `toPlanets`
  - `toPlanet`
  - `toLoF`
  - `getZodMDSA`

- `primdirs_decompiled.py`
  - `create`
  - `calcTime`
  - `getDiff`
  - `toZodAscMC`
  - ASC/MC/IC/DESC 관련 별도 arc 공식

현재 core arc 검증 결과:

- Morinus fixture core rows: 23049 (compare_engine_core_pd.py 기준)
- direction match ratio: 1.0 (100%)
- arc diff p50: 약 0.000018도
- arc diff p95: 약 0.000267도
- arc diff max: 약 0.000514도
- **arc→date ±1d 정확도**: 100% (7만 row 검증, 구공식은 83.6%)
- **PD 커버리지**: Z-mode core 98% (나머지 2% = angle-angle, 규칙 제외)

따라서 **엔진 핵심 계산(arc + date 변환 + PD 커버리지)은 완료 상태**다.

## Remaining Work

1. ~~Date conversion~~ **완료** (8d096e4)
   - Morinus calcTime() 원본 공식으로 대체. 경험적 offset 제거.

2. ~~Full PD generation coverage~~ **완료** (진단 결과: 2% gap = angle-angle = 의도적 제외)

3. Ranking logic
   - PD arc/date는 정확해졌지만 랭킹이 아직 수동 판단과 다르다.
   - 필수 이벤트 우선순위, 창업/장기 커리어 가중치, 대학입학 month tier, 미싱 처리 규칙을 더 정교화해야 한다.
   - 현재 expected rank: sunny=05:45 (정답 05:48 없음), yoo=15:48이 3위, kim=번외, illy=03:45가 1순위권 밖

4. Output format
   - “미싱/필수미싱 상세는 후보별 이벤트 매칭 산출 단계에서 보강 필요” 문구 제거
   - 실제 미싱 이벤트/PD 목록을 각 후보마다 출력하게 보강 필요.

2. Full PD generation coverage
   - core fixture matched rows는 좋지만 unmatched rows가 있다.
   - 어떤 유형이 빠지는지 분류해야 한다.
   - 특히 mundane, antiscia, LoF, angle-related branches가 모두 Morinus 설정과 동일한지 계속 확인해야 한다.

3. Ranking logic
   - 현재 expected rank:
     - sunny_411_custom expected 05:48 -> rank 4
     - yoo_408 expected 15:48 -> rank 3
     - kim_409 expected 20:49 -> rank 13 / 본순위 없음
     - illy_personal expected 03:45 -> rank 16
   - PD arc는 좋아졌지만 랭킹이 아직 사용자 수동 판단과 다르다.
   - 필수 이벤트 우선순위, 창업/장기 커리어 가중치, 대학입학 month tier, 미싱 처리 규칙을 더 정교화해야 한다.

4. Output format
   - 결과 출력은 반드시 1/2/3순위와 근거 PD 리스트, 미싱 리스트를 함께 제공해야 한다.
   - `regression_rank_report.txt`에는 아직 “미싱/필수미싱 상세는 후보별 이벤트 매칭 산출 단계에서 보강 필요” 문구가 남아 있다.
   - 이 문구가 나오지 않도록 실제 미싱 상세를 산출하게 고쳐야 한다.

5. Morinus local files
   - `MorinusWinEng2.7/`은 로컬 참조 폴더이며 gitignore 처리되어 있다.
   - 이 폴더는 커밋하지 않는다.
   - 필요하면 로컬에서만 디컴파일 결과를 참조한다.

## Known Regression Truths

사용자가 수동으로 픽스한 정답 후보:

- `illy_personal`: 03:45, birth second 53, place `Mine` / 126E40, 37N26
- `yoo_408`: 15:48, place `YongIn` / 127E15, 37N10
- `kim_409`: 20:49, place `#Seoul` / 126E58, 37N33
- `sunny_411_custom`: 사용자가 최근 05:48 Morinus 파일을 제공했고, 검증 기준으로 포함됨

## Useful Commands

PowerShell에서 Python 3.11을 명시해야 한다. 기본 `python`은 Python 3.14이고 `swisseph`가 없다.

```powershell
$env:PYTHONPATH='src'; py -3.11 tools\compare_engine_core_pd.py
```

```powershell
$env:PYTHONPATH='src'; py -3.11 tools\run_regression_suite.py
```

```powershell
$env:PYTHONPATH='src'; py -3.11 -m compileall -q src tools\compare_engine_core_pd.py tools\run_regression_suite.py
```

## Git State

Recent committed baseline:

```text
ea764a1 Align rectification engine with Morinus fixtures
```

Do not commit:

- `MorinusWinEng2.7/`
- `rectification-tool/output/`
- `rectification-tool/tools/tmp_*.py`
- `rectification-tool/input/tmp_*.json`
- `rectification-tool/tools/pyinstxtractor*.py`

These are ignored in `.gitignore`.

## Next Recommended Step

다음 채팅에서 이어갈 때는 다음 순서가 좋다.

1. Morinus `util.convDate()` 소스 추출/디컴파일.
2. `run_regression_suite.py`의 `arc_date()`를 Morinus 날짜 변환과 맞추기.
3. Morinus fixture 전체에 대해 date exact / ±1 day / ±2 day 비율 재측정.
4. `regression_rank_report.txt`의 미싱 상세 출력 보강.
5. 랭킹 규칙 보정.

