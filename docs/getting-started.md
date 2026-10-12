# 시작하기

## 1. 설치 확인

프로젝트에 다음 구조가 있어야 합니다.

```text
.agents/skills/book-to-skill-followup/
├── SKILL.md
├── references/
└── scripts/
```

Claude Code에서 스킬 이름으로 호출하려면 `.claude/skills/book-to-skill-followup`이 위 폴더를 가리키는 상대 심볼릭 링크인지 확인합니다. 설치 명령은 [루트 README](../README.md#installation)에 있습니다.

> [!IMPORTANT]
> 스킬 폴더에는 공통 역할 계약·검증 기준·실행 보조기가 함께 포함됩니다. `SKILL.md`만 복사하면 후속 검증에 필요한 자료가 빠집니다.

---

## 2. 한 번 호출하기

```text
$book-to-skill-followup
프로젝트 루트: /absolute/path/to/project
대상 스킬: /absolute/path/to/project/.agents/skills/my-book-skill
원문: /absolute/path/to/source.pdf

원문 대조부터 레퍼런스, 문서, 독립 행동 시험, 최종 호스트 검사까지 마무리해줘.
```

`프로젝트 루트`와 `대상 스킬`의 관계가 맞는지 먼저 확인합니다. 원문 경로는 기존 메타데이터에서 명확히 식별할 수 있을 때만 재사용합니다.

> [!TIP]
> 기존 검증 기록이 있으면 경로를 덧붙이세요. 이전 기록은 단서로 사용하되, 그대로 최종 통과 근거로 재활용하지 않습니다.

---

## 3. 실행 상태 시작하기

메인 에이전트가 상태 파일을 시작할 때 사용하는 명령 형식입니다. `--skill`은 프로젝트 루트에 대한 상대 경로이며, 다른 경로는 절대 경로입니다.

```bash
python3 -B /absolute/path/to/project/.agents/skills/book-to-skill-followup/scripts/run_state.py \
  init \
  --project /absolute/path/to/project \
  --skill .agents/skills/my-book-skill \
  --source /absolute/path/to/source.pdf \
  --documents README.md \
  --documents docs \
  --host codex
```

명령은 다음 위치에 새 실행 상태를 만듭니다.

```text
/absolute/path/to/project/_workspace/harness/book-to-skill-followup/<UTC_UUID>/run.json
```

`<UTC_UUID>` 실행 폴더는 이후 모든 증거의 기준점입니다. 기존 실행 폴더를 덮어쓰지 않습니다.

---

## 4. 완료 후 읽을 파일

다른 가이드의 명령 예시에서 쓰는 변수는 실제 설치 경로와 init이 반환한 실행 경로로 설정합니다.

```bash
FOLLOWUP_SKILL_DIR='/absolute/path/to/project/.agents/skills/book-to-skill-followup'
FOLLOWUP_RUN_DIR='/absolute/path/to/project/_workspace/harness/book-to-skill-followup/실행-ID'
```

| 먼저 볼 파일 | 확인할 내용 |
|---|---|
| `run.json` | 단계 상태, 입력 해시, 차단·무효화 여부 |
| `coordinator/static-checks.json` | 구조·링크·패키지 검사 결과 |
| `forward-tester/behavior-tests.json` | 독립 행동 시험의 입력·판정·제한 |
| `release-reviewer/final-review.json` | 최종 완료 또는 차단 판정 |
| `coordinator/host-smoke.json` | 고정 후 실행한 호스트 1회의 결과 |

다음으로 [워크플로](workflow.md)에서 단계별 의미와 재개 조건을 확인하세요.

