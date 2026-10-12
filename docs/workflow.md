# 전체 워크플로

이 흐름은 스크립트가 문서 작성이나 모델 호출을 자동으로 대신하는 구조가 아닙니다. **메인 에이전트가 단계 순서대로 작업**하고, 실행 보조기가 상태·증거·의존성을 검사합니다.

---

## 단계와 게이트

| 단계 | 담당 | 작업 | 게이트 |
|---|---|---|---|
| `preflight` | 메인 에이전트 | 프로젝트·대상 스킬·원문·허용 쓰기 경로·호스트를 고정 | 실제 경로와 초기 해시 기록 |
| `inventory` | 메인 에이전트 | 원문 구조와 스킬·문서·기존 기록을 목록화 | 모든 원문 단위에 대응 후보 또는 누락 사유 |
| `source-audit` | `source-reviewer` | 원문 주장·표·그림 표본과 지식 자료 대조 | 귀속·누락·모호성과 근거 위치 기록 |
| `skill-refinement` | 메인 에이전트 | 확인된 결함만 스킬·레퍼런스에 반영 | 직접 원칙·적용 지침·새 제안 구분 |
| `documentation` | 메인 에이전트 | README·상세 가이드·예시 보완 | 기본 사용과 고급 활용 경로 제공 |
| `static-checks` | 메인 에이전트 | 파일·해시·경로·링크·앵커·호스트 배치 검사 | 필수 구조 통과와 제외 범위 명시 |
| `behavior-tests` | `forward-tester` | 최소 자료만 받은 새 컨텍스트의 대표·회귀 시험 | 사전 기준을 만족하는 판정과 증거 |
| `improvement` | 메인 에이전트 | 실패 근거에 맞춘 최소 수정과 재검사 | 보완 횟수·영향 범위 기록 |
| `freeze` | `release-reviewer` | 최종 스킬·문서·시험 기준 해시 고정 | 검토할 버전이 하나로 고정 |
| `host-smoke` | 메인 에이전트 | 고정본을 사용 중인 호스트에서 1회 실행 | 로드·수행·종료·해시 일치 증거 |
| `final-review` | `release-reviewer` | 전체 증거와 한계 판정 | 완료 또는 차단 이유 명시 |

> [!IMPORTANT]
> `host-smoke`는 `freeze` 뒤에만 실행합니다. 호스트 호출 뒤 내용 결함이 발견되면 그 실행을 완료 근거로 사용하지 않고, 다음 실행에서 보완합니다.

`source-audit`의 `pass`는 모든 인벤토리 단위를 감사하고 발견 사항을 정확히 기록했다는 뜻입니다. 초기 스킬의 정확성 통과를 뜻하지는 않습니다. `mismatch`·`needs-refinement`은 3단계 보완으로 진행하며, 원문 접근 불가나 미검수 단위만 `blocked`입니다. 최종 `freeze`에서는 중요한 미해결 사항이 있으면 통과할 수 없습니다.

---

## 원문 대조 기준

원문을 읽을 때는 다음 네 층을 구분합니다.

| 구분 | 기록 방법 |
|---|---|
| 원문의 직접 설명 | 원문 위치와 해당 스킬 자료 위치를 함께 기록 |
| 스킬의 재구성 | 여러 직접 설명을 어떻게 묶었는지 설명 |
| 검증 기반 적용 지침 | 책의 직접 문장으로 인용하지 않고 일반적 검증 지침으로 표시 |
| 새 프로젝트 제안 | 원문 밖의 선택지·가정·결정 질문으로 분리 |

사례의 수치·정책을 대상 프로젝트의 기본값으로 바꾸지 않습니다. 원문이 모호하면 위치, 영향, 미정 결정을 적고 단일 답을 만들어내지 않습니다. PDF 쪽수와 인쇄 쪽수의 대응도 원문별로 확인합니다.

표·그림은 스킬이 직접 근거로 드는 항목과 추출 누락·모순이 의심되는 항목을 우선 표본 검사합니다. 후보 목록과 실제 검사 목록을 모두 남기며, 전수 재현이나 전수 시각 검사를 주장하지 않습니다.

---

## 문서 보완 기준

대상 스킬의 루트 README와 `docs/`만 다룹니다. 프로젝트에 여러 스킬이 있으면 기존 루트 README는 보존하고, 해당 스킬의 상세 가이드를 `docs/` 아래 별도 영역으로 둡니다.

| 문서 요소 | 최소 내용 |
|---|---|
| README 상단 | 설치와 시작하기, 실제 스킬 이름과 프로젝트 이름의 구분 |
| 구조 안내 | 모든 장·주제의 자료 위치와 활용 목적 |
| 고급 가이드 | 장별 전략, 서로 다른 예시 2개, 후속 요청 1개 |
| 공통 활용 | 공통 고급 프롬프트 4개와 다장 연계 시나리오 3개 |
| 각 예시 | 필요한 입력, 기대 결과, 미정 사항, 검토 기준 |

Markdown의 표·구분선·강조·알림 블록은 정보의 역할에 맞춰 사용합니다. 장식만을 위해 경고를 늘리지 않습니다.

---

## 재개와 무효화

`run_state.py`는 실행 상태와 단계 증거를 관리합니다. 대표 명령은 다음과 같습니다.

```bash
python3 -B "$FOLLOWUP_SKILL_DIR/scripts/run_state.py" start --run-dir "$FOLLOWUP_RUN_DIR" --stage source-audit
python3 -B "$FOLLOWUP_SKILL_DIR/scripts/run_state.py" finish --run-dir "$FOLLOWUP_RUN_DIR" --stage source-audit --evidence source-reviewer/source-audit.json
python3 -B "$FOLLOWUP_SKILL_DIR/scripts/run_state.py" verify --run-dir "$FOLLOWUP_RUN_DIR"
python3 -B "$FOLLOWUP_SKILL_DIR/scripts/run_state.py" resume --run-dir "$FOLLOWUP_RUN_DIR"
```

스킬·문서·프롬프트·시험 기준·검사기·호스트 설정이 바뀌면 관련 하위 단계와 최종 판정은 무효입니다. 다음 명령으로 보완이 시작되는 지점을 명시합니다.

```bash
python3 -B "$FOLLOWUP_SKILL_DIR/scripts/run_state.py" revise \
  --run-dir "$FOLLOWUP_RUN_DIR" \
  --from-stage documentation \
  --reason '문서 예시의 출처 구분을 보완함'
```

동일한 일반 도구 실패는 한 번만 재시도합니다. 내용 보완은 최대 두 번으로 제한합니다. 원문 접근, 독립 평가, 사용 호스트의 실제 호출 중 필수 조건이 없으면 완료가 아니라 `blocked`로 끝냅니다.

---

## 단계 산출물 확인

필수 산출물은 `references/harness-spec.json`이 정본이며, 증거 필드의 자세한 의미는 `references/evidence-contract.md`에 있습니다. 검사기는 다음과 같이 호출합니다.

```bash
python3 -B "$FOLLOWUP_SKILL_DIR/scripts/check_package.py" \
  --project /absolute/path/to/project \
  --skill .agents/skills/my-book-skill \
  --documents README.md \
  --documents docs \
  --run-dir /absolute/path/to/run \
  --output /absolute/path/to/run/coordinator/static-checks.json
```

필수 Python 모듈이 없으면 자동 설치하지 않습니다. [문제 해결](troubleshooting.md)에서 차단 기록과 복구 방식을 확인하세요.

