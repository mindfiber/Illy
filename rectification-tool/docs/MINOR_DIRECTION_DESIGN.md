# Minor Direction Matching — 설계 문서

## 배경

현재 엔진은 메이저 디렉션 4종(planet-angle, angle-planet, planet-LoF, LoF-planet)만 매칭에 사용한다. 그러나 임상적으로 **메이저가 없어도 같은 사건 시기에 사건을 상징하는 마이너 디렉션이 군집·단독으로 나타나면 메이저와 비슷한 효과**를 내는 케이스가 많다.

특히:
- 연애 이벤트(Venus): 길성→흉성 1개만 있어도 메이저와 동일하게 인정 가능.
- 이동/이사 이벤트: 달/수성 → 행성 1개도 메이저와 동일.
- 일리 차트(03:45)의 G01(2000-03 대학입학): 메이저 길성 PD 0개, 그러나 길성→길성 마이너 군집 3개.

## 1. PD 분류 (Direction Classification)

각 PD는 다음 셋 중 하나로 분류된다.

### A. Major
다음 4 종류 중 하나.
- `planet-angle` (e.g., Sun → ASC)
- `angle-planet` (e.g., ASC → Sun)
- `planet-LoF` (e.g., Jupiter → LoF)
- `LoF-planet` (e.g., LoF → Jupiter)

(현재 `pa_ap()` 함수가 이걸 판정한다.)

### B. Minor
- Z mode `planet-planet` (Antiscion / Contraantiscion 포함, 양쪽 모두 행성류)
- M mode (mundane) PD
- Major이지만 이벤트 룰의 allowed planet set에서 빠진 행성을 포함하는 PD

### C. Lunar Single-Axis (달 단독 지표)
- `Moon → angle` 또는 `angle → Moon` (planet-angle major이지만 달이라는 점)
- **일반 이벤트에서는 사용 안 함**.
- **이동/이사 이벤트에서만 메이저로 인정**.

## 2. Aspect Quality (관계 품질)

PD에 등장하는 두 점의 길흉성 조합을 분류:

- `benefic_benefic` — 양쪽 모두 Sun/Jupiter/Venus 또는 angle/LoF (angle은 중성으로 취급).
  - 단, 메이저는 angle 한쪽이 자동으로 angle. 마이너에선 양쪽 행성으로 길성성 검사.
- `benefic_malefic` — 한쪽은 길성, 한쪽은 Mars/Saturn.
- `malefic_malefic` — 양쪽 모두 Mars/Saturn.
- `mixed` — Moon, Mercury, LoF 등이 포함된 경우.

## 3. 이벤트 카테고리 & 매칭 룰

### G_GENERAL (G그룹 일반 길성)
**해당 이벤트 타입:** `university_admission`, `graduate_school_admission`, `employment_start`, `first_employment`, `promotion_award`, `career_honor_event`, `graduation`

**매칭 우선순위:**
1. **Major Match** — Major + Sun/Jupiter/Venus 1개 이상
2. **Minor Single** — Minor PD 중 `benefic_benefic` 1개 이상 (e.g., 길성→길성)
3. **Minor Cluster** — Minor PD 중 임의 길성 관련 PD 3개 이상
4. **(매칭 없음)**

**가중치:**
- Major Match: `1.0 × base_weight`
- Minor Single: `0.7 × base_weight`
- Minor Cluster: `0.7 × base_weight`

### H_RELATIONSHIP (연애/결혼)
**해당 이벤트 타입:** `relationship`, `marriage`

**매칭 우선순위:**
1. **Major Match** — **Venus만** 메이저 (Venus → angle/LoF, angle/LoF → Venus)
2. **Minor Equal** — `benefic_benefic` 또는 `benefic_malefic` 마이너 1개 이상 (메이저와 동일 가중치)
   - Jupiter 메이저(Venus 외 길성)도 여기 포함. 가끔 시기 약간 어긋날 때 발생.
3. **Minor Cluster** — 마이너 3개 이상

**가중치:**
- Major Match: `1.0 × base_weight`
- Minor Equal: `1.0 × base_weight` (메이저와 동일)
- Minor Cluster: `0.7 × base_weight`

**비고**: Venus 외 길성 메이저(예: Jupiter → ASC)는 임상상 가끔 등장하지만 시기 어긋남이 흔하다.
이 경우 라벨은 `Minor·Equal`로 표시한다 (사용자 룰).

### T_TRANSITION (이동/이사)
**해당 이벤트 타입:** `relocation`, `move_house` (현재 케이스에 없음. 향후 추가 시 적용)

**매칭 우선순위:**
1. **Major/Equal** — Moon 또는 Mercury가 한쪽이고 다른 쪽이 임의 점인 PD 1개 이상 (메이저든 마이너든 동일 가중치)

**가중치:** `1.0 × base_weight`

### K_HARSH (흉성 이벤트)
**해당 이벤트 타입:** `surgery_medical_major`, `mental_health_crisis`, `family_death`, `loss_general`, `employment_end`, `dropout`

**매칭 우선순위 (연애와 동일 구조):**
1. **Major Match** — Mars/Saturn 메이저 (Mars/Saturn → angle/LoF, angle/LoF → Mars/Saturn)
2. **Minor Equal** — `malefic_malefic` 또는 `benefic_malefic` 마이너 1개 (메이저와 동일 가중치)
3. **Minor Cluster** — 마이너 3개 이상

**가중치:**
- Major Match: `1.0 × base_weight`
- Minor Equal: `1.0 × base_weight`
- Minor Cluster: `0.7 × base_weight`

**중요 흉성 강제 메이저 룰:**
중요도 높은 흉성 이벤트(`family_death` 등 크리티컬 이벤트)는 반드시 Major Match만 인정.
Minor만 매칭되면 mandatory_ok=False로 처리.

`CRITICAL_HARSH_TYPES = {"family_death"}`  
(향후 사용자 지정으로 확장 가능)

## 4. Mandatory 판정

- 필수 이벤트(`marriage`, `childbirth`, `first_employment`, `university_admission`, `graduate_school_admission`)에 **Major Match / Minor Equal / Minor Single / Minor Cluster** 중 어느 것이라도 매칭되면 `mandatory_ok = True`.
- 모두 없으면 `mandatory_ok = False`.

이 변경으로 일리 03:45의 G01/G02가 Minor Single로 인정되어 본순위 진입 가능해진다.

## 5. 점수 시스템 통합

```
score = sum_over_matched_events(
    base_weight(event)
    × match_quality_factor   # 1.0 (Major/Equal) or 0.7 (Single/Cluster)
    × career_weight(event)   # 기존 룰 유지
)
+ sum_over_matched_events(0.25 × pd_count_for_event)
- 0.5 × max(uni_tiers)   # 기존 admission month tier 룰
```

## 6. 출력 포맷

각 매칭 PD 라인에 매치 종류 표시:

```
- G01:university_admission [Major] Sun Conjunctio LoF D | 1999-02-04
- G01:university_admission [Minor·Single] Antiscion Moon Quadrat Venus D | 2000-02-28
- H_REL:relationship [Minor·Equal] Venus Sextil Saturn C | 2008-12-10
- G02:university_admission [Minor·Cluster] M Mars Trigon Venus D | 1999-12-29
```

미싱 이벤트도 함께 표시:
```
미싱 이벤트:
- G05:employment_start (2015-05) — 매칭 PD 없음
필수 미싱: 없음
```

## 7. 구현 Phase

1. **Phase 1: G그룹 일반 — Minor Single & Cluster**
   - PD 분류 함수 추가 (`classify_pd`)
   - Aspect quality 함수 (`aspect_quality`)
   - G그룹 룰 확장
   - 효과 검증: 일리 03:45 G01/G02 매칭 여부 확인

2. **Phase 2: H_RELATIONSHIP — Minor Equal**
   - 연애 이벤트 길성→흉성 1개 인정
   - 효과 검증: yoo, sunny relationship 매칭 비교

3. **Phase 3: 출력 포맷**
   - 매치 종류 라벨링
   - 미싱 이벤트 상세 출력 (IMMUTABLE_RULES #4 준수)

4. **Phase 4: T_TRANSITION**
   - 새 이벤트 카테고리 추가 + 룰

5. **Phase 5: K_HARSH 마이너 군집** (미정)

6. **Phase 6: 달 단독 지표 처리 (이동 한정)**

## 8. 룰 충돌 / 오버라이드 룰

- 달이 promissor/significator로 등장하는 메이저 PD(`Moon → ASC` 등)는 일반 이벤트에서는 거부, 이동 이벤트에서만 인정.
- 마이너에서 한쪽이 달인 planet-Moon / Moon-planet 조합은 일반 이벤트에서도 사용 가능.
- antiscion/contraantiscion 자체는 마이너에 한해 양쪽 행성으로 취급.

## 9. 회귀 영향 예측

- **일리 03:45**: G01/G02 → Minor Single 매칭 → mandatory_ok=True → 본순위 진입 가능.
- **sunny 05:48**: 큰 변화 없음 (메이저 매칭이 충분함).
- **yoo 15:48**: relationship 마이너 매칭이 추가될 수 있음.
- **kim 20:48**: G01 마이너 매칭으로 mandatory miss 회복 가능성.

각 phase 후 회귀 결과 비교 필수.
