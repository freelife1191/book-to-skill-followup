# 전체 워크플로

[← 프로젝트 소개](../README.md) · [가이드 홈](index.md) · [릴리스 노트](../release/README.md)

<details open>
<summary><strong>이 문서의 목차</strong></summary>

- [단계와 게이트](#doc-section-1)
- [원문 대조 기준](#doc-section-2)
- [문서 보완 기준](#doc-section-3)
- [제작 도구와 배포물 분리](#doc-section-4)
- [재개와 무효화](#doc-section-5)
- [단계 산출물 확인](#doc-section-6)

</details>

이 흐름은 스크립트가 문서 작성이나 모델 호출을 자동으로 대신하는 구조가 아닙니다. **메인 에이전트가 단계 순서대로 작업**하고, 실행 보조기가 상태·증거·의존성을 검사합니다.

---

<a id="doc-section-1"></a>

## 단계와 게이트

| 단계 | 담당 | 작업 | 게이트 |
|---|---|---|---|
| `preflight` | 메인 에이전트 | 프로젝트·대상 스킬·원문·허용 쓰기 경로·호스트를 고정 | 실제 경로와 초기 해시 기록 |
| `inventory` | 메인 에이전트 | 원문 구조와 스킬·문서·기존 기록을 목록화 | 모든 원문 단위에 대응 후보 또는 누락 사유 |
| `source-audit` | `source-reviewer` | 원문 주장·표·그림 표본과 지식 자료 대조 | 귀속·누락·모호성과 근거 위치 기록 |
| `skill-refinement` | 메인 에이전트 | 확인된 결함만 스킬·레퍼런스에 반영 | 직접 원칙·적용 지침·새 제안 구분 |
| `documentation` | 메인 에이전트 | README·상세 가이드·예시 보완 | 기본 사용과 고급 활용 경로 제공 |
| `static-checks` | 메인 에이전트 | 파일·해시·경로·링크·앵커·호스트 배치 검사 | 필수 구조 통과와 제외 범위 명시 |
| `behavior-tests` | `forward-tester` | 최소 자료만 받은 새 컨텍스트의 대표·회귀 시험, 일부는 사용 호스트 CLI 새 세션으로 실행 | 사전 기준을 만족하는 판정과 증거, 원래 로그의 로드·접근·읽기 범위 점검 |
| `improvement` | 메인 에이전트 | 실패 근거에 맞춘 최소 수정과 재검사 | 보완 횟수·영향 범위 기록 |
| `language-review` | `release-reviewer` | `humanizer → grammar-checker → style-guide`로 한국어 문장·문법·용어를 독립 검수 | 현재 Markdown·JSON·YAML 전체, 출처 해시, 의미 보존 6개 항목 |
| `freeze` | `release-reviewer` | 최종 스킬·문서·시험 기준 해시 고정 | 검토할 버전이 하나로 고정 |
| `host-smoke` | 메인 에이전트 | 고정본을 사용 중인 호스트에서 1회 실행 | 로드·수행·종료·해시 일치 증거 |
| `final-review` | `release-reviewer` | 전체 증거와 한계 판정 | 완료 또는 차단 이유 명시 |

> [!IMPORTANT]
> `host-smoke`는 `freeze` 뒤에만 실행합니다. 호스트 호출 뒤 내용 결함이 발견되면 그 실행을 완료 근거로 사용하지 않고, 다음 실행에서 보완합니다.

`language-review`에서 표현 보정이 필요하면 `freeze` 전에 `revise --from-stage documentation`을 기록하고 정적 검사·독립 시험을 포함한 뒤 단계를 새 subject로 다시 수행합니다. `freeze` 뒤 교정은 허용하지 않습니다. 자동 정규식만으로 어색한 문장 검수 통과를 주장하지 않으며, 영어 원문·원문 제목·코드·해당 분야의 전문 용어는 문맥에 맞게 보존합니다.

`source-audit`의 `pass`는 모든 인벤토리 단위를 감사하고 발견 사항을 정확히 기록했다는 뜻입니다. 초기 스킬의 정확성 통과를 뜻하지는 않습니다. `mismatch`·`needs-refinement`은 3단계 보완으로 진행하며, 원문 접근 불가나 미검수 단위만 `blocked`입니다. 최종 `freeze`에서는 중요한 미해결 사항이 있으면 통과할 수 없습니다.

---

<a id="doc-section-2"></a>

## 원문 대조 기준

원문을 읽을 때는 다음 네 층을 구분합니다.

| 구분 | 기록 방법 |
|---|---|
| 원문의 직접 설명 | 원문 위치와 해당 스킬 자료 위치를 함께 기록 |
| 스킬의 재구성 | 여러 직접 설명을 어떻게 묶었는지 설명 |
| 검증 기반 적용 지침 | 책의 직접 문장으로 인용하지 않고 일반적 검증 지침으로 표시 |
| 새 프로젝트 제안 | 원문 밖의 선택지·가정·결정 질문으로 분리 |

사례의 수치·정책을 대상 프로젝트의 기본값으로 바꾸지 않습니다. 원문이 모호하면 위치, 영향, 미정 결정을 적고 단일 답을 만들어내지 않습니다. PDF 쪽수와 인쇄 쪽수의 대응도 원문별로 확인합니다.

장·절 제목의 대응만으로 내용 충실도를 통과시키지 않습니다. 세부 기법·성립 조건·예외·대조 사례를 실제 반영 문장까지 비교하고, 수치의 초기값·주기·단위와 용어의 원문 용법을 확인합니다. 원문에서 확인한 수치 방법은 구체적이라는 이유로 제거하지 않습니다. [세부 검수 기준](../.agents/skills/book-to-skill-followup/references/source-audit.md#세부-내용의-충실도)을 따릅니다.

표·그림은 스킬이 직접 근거로 드는 항목과 추출 누락·모순이 의심되는 항목을 우선 표본 검사합니다. 후보 목록과 실제 검사 목록을 모두 남기며, 전수 재현이나 전수 시각 검사를 주장하지 않습니다.

---

<a id="doc-section-3"></a>

## 문서 보완 기준

대상 스킬의 루트 README와 `docs/`만 다룹니다. 프로젝트에 여러 스킬이 있으면 기존 루트 README는 보존하고, 해당 스킬의 상세 가이드를 `docs/` 아래 별도 영역으로 둡니다.

| 문서 요소 | 최소 내용 |
|---|---|
| README 상단 | 설치와 시작하기, 실제 스킬 이름과 프로젝트 이름의 구분 |
| 구조 안내 | 모든 장·주제의 자료 위치와 활용 목적 |
| 고급 가이드 | 장별 전략, 목적이 드러나는 제목을 붙인 서로 다른 예시 2개·후속 요청 1개, 실제 제목이 표시된 바로가기 |
| 공통 활용 | 공통 고급 프롬프트 4개와 다장 연계 시나리오 3개 |
| 각 예시 | 필요한 입력, 기대 결과, 미정 사항, 검토 기준 |

Markdown의 표·구분선·강조·알림 블록은 정보의 역할에 맞춰 사용합니다. 장식만을 위해 경고를 늘리지 않습니다.

목차·장별 바로가기는 예시 번호만 나열하지 않고 대상 절의 실제 제목을 표시합니다. 긴 제목은 목록이나 표로 배치합니다. 작성·검토 기준은 [프롬프트 제목과 바로가기](../.agents/skills/book-to-skill-followup/references/documentation.md#프롬프트-제목과-바로가기)에 있습니다.

보강한 조건은 README의 문제별 안내, 예시의 산출물·확인 기준, 후속 입력과 결과에 연결합니다. 기존 ID·앵커·가상 입력·정책·숫자는 유지하며, 기존 맥락에 맞지 않으면 별도 예시로 보완합니다. 새 대화의 후속에는 실제 선택안과 조건 판정·근거·미확인 사항을 넘기고 유지/변경 이유를 받습니다. [인계 기준](../.agents/skills/book-to-skill-followup/references/documentation.md#보강한-조건을-예시와-후속으로-연결)과 [대표 연계 시험](../.agents/skills/book-to-skill-followup/references/evaluation.md#예시와-후속의-연계-시험)을 따릅니다.

<a id="doc-section-4"></a>

## 제작 도구와 배포물 분리

이 후속 스킬은 책 결과물 밖의 제작 작업 공간에서 실행합니다. 책 저장소에 해당 스킬·그 별칭·제작용 프로필을 기본 복사하지 않습니다. 정적 검사는 중첩된 제작 스킬과 프로젝트 설치의 실제 추적·제외 상태를 확인합니다. 이미 추적된 파일은 제외 패턴만 추가해도 배포에서 사라지지 않으므로 승인된 작업 범위에서 정리합니다. 실제 폴더 복사·아카이브에는 별도의 파일 목록 확인이 필요합니다. [배포 분리 계약](../.agents/skills/book-to-skill-followup/references/packaging.md)을 참고하세요.

---

<a id="doc-section-5"></a>

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

동일한 일반 도구 실패는 한 번만 재시도합니다. 내용 보완은 최대 두 번으로 제한합니다. 원문 접근, 독립 평가, 한국어 마지막 검수, 사용 호스트의 실제 호출 중 필수 조건이 없으면 완료가 아니라 `blocked`로 끝냅니다.

---

<a id="doc-section-6"></a>

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

---

[↑ 문서 처음](#전체-워크플로) · [가이드 홈](index.md) · [다음 릴리스 노트 작성](../release/_template.md)
