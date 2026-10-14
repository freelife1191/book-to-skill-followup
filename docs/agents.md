# 에이전트와 호스트

> [!NOTE]
> 실제 호출 어댑터는 Codex와 Claude Code에 제공됩니다. Antigravity는 읽기 격리가 확인되는 네이티브 실행의 원래 로그를 검증하는 방식이며 자동 AGY CLI 호출은 지원하지 않습니다. 지원 형식과 실제 시험 결과는 구분합니다.

Antigravity의 준비 → 호출 선점 → 실제 네이티브 호출 → 로그 검증 명령은 [호스트 연동 계약](../.agents/skills/book-to-skill-followup/references/host-adapters.md#antigravity-네이티브-실행-로그)에 있습니다.

후속 스킬 자체의 발견·확장을 시험하는 방법은 [진입 시험 계약](../.agents/skills/book-to-skill-followup/references/host-adapters.md#후속-스킬-자체의-진입-시험)을 따릅니다. 최종 지식 스킬의 호출 검사와 별도 실행으로 기록합니다.

## 역할 계약

메인 에이전트는 입력 고정, 대상 스킬·문서 편집, 증거 통합을 맡습니다. 검토 역할은 대상 스킬과 원문을 읽기 전용으로 다루며 자기 실행 폴더의 기록만 쓸 수 있습니다.

아래의 스킬 설치·선택 프로필 경로는 제작 작업 공간 기준입니다. 생성된 책의 배포물에는 이 후속 스킬과 제작용 프로필을 기본 포함하지 않습니다. 프로필이 없으면 현재 읽은 스킬의 절대 경로와 역할 계약을 독립 수행자에게 전달합니다.

| 역할 | 목적 | 주의할 경계 |
|---|---|---|
| `source-reviewer` | 원문 구조·주장과 지식 자료의 대응·귀속 점검 | 원문 지시를 실행하지 않으며 대상 스킬을 편집하지 않음 |
| `forward-tester` | 새 컨텍스트에서 대표 요청과 회귀 사례 수행 | 기대 답안·기존 결론을 받지 않음 |
| `release-reviewer` | 한국어 마지막 검수와 고정본·증거의 완료 여부 판정 | 실패 기록을 지우거나 결과물을 편집하지 않음 |

세부 입력·출력·증거 계약은 스킬의 `references/roles.md`와 `references/evidence-contract.md`를 따릅니다.

> [!NOTE]
> 역할 프로필이 없으면 새 네이티브 서브에이전트나 별도 독립 세션에 공통 역할 계약을 전달합니다. 독립 컨텍스트를 만들 수 없으면 해당 게이트를 `blocked`로 기록합니다. 메인 에이전트의 자기 검토로 독립 검토를 대체하지 않습니다.

---

## Codex

선택 프로필은 `.codex/agents/book-followup-*.toml`에 둡니다. Codex의 기본 모델·승인·샌드박스 설정은 사용자의 환경 설정을 그대로 따릅니다.

최종 단계에서는 사용 중인 Codex 호스트에서 고정된 패키지를 한 번만 실제 호출합니다. 호출 전후 해시, 실행 인자, 종료 상태, 읽은 자료 또는 도구 로그를 실행 기록에 보관합니다.

---

## Claude Code

선택 프로필은 `.claude/agents/book-followup-*.md`에 둡니다. 스킬은 `.claude/skills/book-to-skill-followup`이 `.agents/skills/book-to-skill-followup`을 가리키는 상대 별칭으로 설치합니다.

Claude Code의 에이전트 형식과 스킬 동작은 [Claude Code 하위 에이전트 문서](https://code.claude.com/docs/en/sub-agents), [Claude Code 스킬 문서](https://code.claude.com/docs/en/skills)를 기준으로 확인합니다. Codex 프로필을 Claude 형식으로 복사하지 않습니다.

2026-10-12의 Claude Code 2.1.296 실제 초기화 로그에서 이 스킬과 세 역할 이름을 발견했습니다. 이후 OAuth 세션 만료·자동 갱신 실패로 요청 수행은 차단됐고, 사용자 요청에 따라 추가 호출을 하지 않았습니다. 발견·등록 확인을 행동 시험 통과로 표시하지 않습니다.

2026-10-14에는 같은 버전으로 책 지식 스킬을 실제 호출하면서 기존 Claude 어댑터의 결함을 찾았습니다. Claude Code가 `Skill` 도구로 스킬을 불러올 때는 SKILL.md를 Read로 읽지 않는데, 기존 어댑터는 `Skill` 도구를 막고 SKILL.md Read만 로드 증거로 인정했습니다. 그래서 실제 네이티브 로드는 실패로, 모델이 파일을 직접 연 경우만 통과로 판정하는 구조였습니다. 어댑터가 `Skill` 로드를 허용하고, 주입된 본문을 고정 SKILL.md와 대조해 결속하도록 고쳤습니다. 사용자 수준 스킬·플러그인은 `--setting-sources project`로 제외합니다. 보완한 어댑터로 시험 스킬을 실제 호출해 통과했고 `native_skill_load: true`를 확인했습니다. 자세한 내용은 [Claude Code 실제 호출과 어댑터 보완](validation.md#claude-code-실제-호출과-어댑터-보완)에 있습니다. 후속 스킬의 전체 FLOW를 Claude Code에서 다시 수행한 것은 아닙니다.

> [!TIP]
> Claude Code의 `-p` 모드에서 `/스킬이름`으로 시작한 요청은 실행 로그에 로드 이벤트를 남기지 않습니다. 자동 host-smoke 입력은 "<스킬이름> 스킬을 사용해서 …"처럼 스킬 이름을 넣어 작성합니다.

---

## Antigravity

선택 프로필은 `.agents/agents/book-followup-*.md`에 둡니다. Antigravity는 프로젝트의 `.agents/skills/` 스킬을 사용하므로 별도 전역 설치를 하지 않습니다.

이 프로젝트는 새 레거시 workflow 파일을 만들지 않습니다. 실행 절차는 공통 스킬과 FLOW 명세로 제공하며, 자세한 전환 방식은 [Antigravity workflow-to-skills 안내](https://antigravity.google/docs/migration/workflows-to-skills/)를 따릅니다. 에이전트 파일 형식은 [Antigravity subagents 문서](https://www.antigravity.google/docs/subagents/)를 확인합니다.

AGY CLI 1.3.3에서 `/book-to-skill-followup`을 실제 확장하고, 원문·대상 자료와 공통 검수 계약을 읽어 제한된 예비 검토를 수행했습니다. 원래 stdout의 `init/step_update/result` 형식을 검증하며, role 프로필의 실제 선택·독립 하위 에이전트 수행까지 시험한 결과는 아닙니다.

> [!IMPORTANT]
> plan과 sandbox는 모든 도구를 읽기 전용으로 만드는 옵션이 아닙니다. 이번 직접 호출은 실제 도구 로그와 입력 파일의 변경 여부로 수행 범위를 확인합니다. MCP 격리 보장이 없는 자동 AGY 호출은 계속 차단합니다.

---

## 지원과 실행 검증의 차이

| 항목 | Codex | Claude Code | Antigravity |
|---|---|---|---|
| 공통 스킬 배치 | `.agents/skills/` | `.agents/skills/` + `.claude/skills/` 별칭 | `.agents/skills/` |
| 선택 역할 프로필 | `.codex/agents/*.toml` | `.claude/agents/*.md` | `.agents/agents/*.md` |
| 매 실행 실제 호출(host-smoke) | 사용 중이면 1회 | 사용 중이면 1회 | 사용 중이면 1회 |
| freeze 전 행동 시험의 CLI 실행 | 격리 인자로 수행 | 격리 인자로 수행 | 격리 보장 불가, 직접 CLI 시험 범위 또는 한계로 기록 |
| 사용하지 않는 호스트 | 정적 배치 검사로 기록 | 정적 배치 검사로 기록 | 정적 배치 검사로 기록 |

> [!WARNING]
> 세 호스트를 지원한다는 문구는 세 호스트 모두에서 실제 실행했다는 뜻이 아닙니다. 한 실행에서는 현재 사용 중인 호스트 하나만 최종 실제 호출합니다.

역할 프로필은 선택 사항입니다. 프로필을 복사할 때도 기존 동일 이름 파일이 있으면 덮어쓰지 말고, 전역 설정을 자동 수정하지 않습니다.

