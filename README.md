# 책 지식 스킬 후속 완성 <a id="document-top"></a>

`book-to-skill`로 변환한 지식 스킬을 **원문 대조부터 레퍼런스·문서·독립 시험·최종 호스트 검사까지** 마무리하는 후속 작업 스킬입니다. 변환기를 다시 만들지 않으며, 이미 생성된 스킬을 더 정확하고 사용하기 쉬운 결과물로 완성합니다.

> [!IMPORTANT]
> 스킬의 후속 작업 FLOW는 대상 프로젝트의 Git 저장소를 초기화하거나 전역 설정을 바꾸지 않습니다. 원문과 대상 프로젝트의 쓰기 범위는 실행 시작 시 명시적으로 고정합니다.

---

## 설치 <a id="installation"></a>

먼저 저장소를 복제합니다.

```bash
git clone https://github.com/freelife1191/book-to-skill-followup.git
cd book-to-skill-followup
```

> [!NOTE]
> 실행 보조기는 **Python 3.11 이상**, 정적 검사기는 **PyYAML·markdown-it-py**가 필요합니다. 필요한 도구가 없으면 자동 설치하지 않고 차단 사유를 알려줍니다. [환경 확인과 문제 해결](docs/troubleshooting.md#도구검사기가-실행되지-않음)을 참고하세요.

### 프롬프트로 설치

Codex에 아래처럼 요청합니다.

```text
/Users/freelife/ai/book-to-skill-followup/.agents/skills/book-to-skill-followup 을
현재 프로젝트의 .agents/skills/에 설치하고 Claude 별칭도 연결해줘.
기존 대상이 있으면 덮어쓰지 말고 중단해줘.
```

### CLI로 수동 설치

다음 명령은 이 프로젝트의 스킬 폴더 전체를 현재 프로젝트로 복사하고 Claude Code용 별칭을 만듭니다. 대상 스킬이나 별칭이 이미 있으면 **복사 전에 중단**합니다.

```bash
SKILL_SOURCE='/absolute/path/to/book-to-skill-followup/.agents/skills/book-to-skill-followup'
SKILL_TARGET="$PWD/.agents/skills/book-to-skill-followup"
CLAUDE_TARGET="$PWD/.claude/skills/book-to-skill-followup"

test -d "$SKILL_SOURCE" || { printf '%s\n' "스킬 원본을 찾을 수 없습니다: $SKILL_SOURCE" >&2; exit 1; }
if [ -e "$SKILL_TARGET" ] || [ -L "$SKILL_TARGET" ] || [ -e "$CLAUDE_TARGET" ] || [ -L "$CLAUDE_TARGET" ]; then
  printf '%s\n' '대상 스킬 또는 Claude 별칭이 이미 있습니다. 기존 항목을 보존합니다.' >&2
  exit 1
fi

mkdir -p "$(dirname "$SKILL_TARGET")" "$(dirname "$CLAUDE_TARGET")"
cp -R "$SKILL_SOURCE" "$SKILL_TARGET"
ln -s '../../.agents/skills/book-to-skill-followup' "$CLAUDE_TARGET"
```

Antigravity는 프로젝트의 `.agents/skills/`를 그대로 사용합니다. 선택 역할 프로필을 함께 쓰려면 [에이전트와 호스트](docs/agents.md)를 따릅니다.

> [!NOTE]
> 다른 프로젝트에 설치하려면 해당 프로젝트로 이동한 뒤 명령을 실행하세요. `SKILL_SOURCE`는 복제한 저장소 안의 실제 스킬 절대 경로로 바꿉니다. 이 저장소의 커밋·푸시 인증 규칙은 [프로젝트 지침](AGENTS.md#github-인증커밋푸시)을 따릅니다.

---

## TOC <a id="toc"></a>

- [설치](#installation)
- [한 번에 사용하기](#quick-start)
- [결과물](#outputs)
- [FLOW](#flow)
- [역할](#roles)
- [검증 범위와 한계](#verification-limits)
- [상세 가이드](#guides)

### 상세 가이드

- [시작하기](docs/getting-started.md)
- [전체 워크플로](docs/workflow.md)
- [에이전트와 호스트](docs/agents.md)
- [고급 활용](docs/advanced-usage.md)
- [검수와 시험](docs/validation.md)
- [문제 해결](docs/troubleshooting.md)
- [이력과 설계 근거](docs/history.md)

---

## 한 번에 사용하기 <a id="quick-start"></a>

아래 세 항목을 실제 절대 경로로 제공하면 됩니다.

```text
$book-to-skill-followup
프로젝트 루트: /path/to/project
대상 스킬: /path/to/project/.agents/skills/my-book-skill
원문: /path/to/book.pdf

변환 이후 원문 검수, 레퍼런스 보강, README와 가이드,
장별 고급 프롬프트, 독립 시험, 보완과 최종 호스트 검사까지 마무리해줘.
```

| 입력 | 필요한 이유 |
|---|---|
| 프로젝트 루트 | 허용된 문서·스킬 편집 경계와 실행 기록 위치를 정합니다. |
| 대상 스킬 | 검수·보완·시험할 스킬을 하나로 고정합니다. |
| 원문 | 장·주제 대응, 출처 주장, 표·그림 표본을 대조합니다. |

> [!TIP]
> 대상 스킬이 여러 개이거나 원문이 모호하면 하나를 임의로 고르지 않습니다. 이번 실행의 대상과 원문을 먼저 확정한 뒤 다시 호출하세요.

---

## 결과물 <a id="outputs"></a>

실행은 대상 프로젝트의 `_workspace/harness/book-to-skill-followup/<실행 ID>/`에 증거와 판정을 남깁니다. 대상 스킬에는 원문 대조로 확인된 보완만 반영하며, 루트 README와 `docs/`에는 설치·빠른 사용·상세 가이드를 정리합니다.

주요 산출물은 다음과 같습니다.

- 원문 단위별 반영 위치·누락·모호성·귀속 검수 기록
- 보완된 스킬·레퍼런스·README·상세 가이드
- 정적 검사와 독립 사용 시험의 입력·답변·판정
- 최종 고정 해시와 사용 중인 호스트의 실제 호출 기록

실행 상태와 산출물 계약은 [워크플로](docs/workflow.md), 증거의 의미는 [검수와 시험](docs/validation.md)에서 확인할 수 있습니다.

---

## FLOW <a id="flow"></a>

| 단계 | 핵심 작업 | 완료 기준 |
|---|---|---|
| 0–2 | 입력 고정, 원문 구조·내용 대조 | 모든 원문 단위의 반영 위치 또는 누락 사유 기록 |
| 3–4 | 스킬·레퍼런스와 README·가이드 보완 | 출처와 적용 지침을 구분하고 사용 경로를 제공 |
| 5–7 | 정적 검사, 독립 시험, 최소 보완 | 실패 근거에 맞춘 수정과 영향 범위 재검사 |
| 8–9 | 최종 고정, 실제 호스트 호출 | 고정 해시와 실행 증거가 일치 |

전체 단계와 재개·무효화 규칙은 [전체 워크플로](docs/workflow.md)에 있습니다.

---

## 역할 <a id="roles"></a>

| 역할 | 책임 | 파일 편집 범위 |
|---|---|---|
| 메인 에이전트 | 입력 확정, 대상 스킬·문서 보완, 단계 통합 | 승인된 대상 스킬·README·`docs/` |
| `source-reviewer` | 원문과 지식의 대응·귀속 검수 | 자신의 검수 기록만 |
| `forward-tester` | 새 컨텍스트에서 현실적인 요청 수행 | 격리된 시험 기록만 |
| `release-reviewer` | 고정된 결과물과 증거의 최종 판정 | 자신의 판정 기록만 |

선택 역할 프로필은 편의를 위한 것입니다. 프로필이 없으면 메인 에이전트는 **새 네이티브 서브에이전트 또는 독립 세션**에 같은 역할 계약을 전달할 수 있습니다. 이를 만들 수 없으면 독립 검토 게이트는 `blocked`로 기록하며, 같은 메인 컨텍스트의 자기 검토로 대체하지 않습니다. 자세한 설치·형식은 [에이전트와 호스트](docs/agents.md)를 참조하세요.

---

## 검증 범위와 한계 <a id="verification-limits"></a>

- **모든 장·주제**의 반영 여부와 스킬의 출처 주장을 확인합니다. 이는 원문의 모든 문장·표·그림을 재현하거나 전수 시각 검사를 보장한다는 뜻이 아닙니다.
- 표·그림은 스킬이 직접 주장에 사용하는 자료와 추출 누락·모순이 의심되는 자료를 우선 표본 검사합니다.
- 지원 대상은 Codex·Claude Code·Antigravity입니다. 세 호스트의 정적 배치를 제공한다는 뜻이며, 매 실행에서 실제 호출하는 호스트는 **사용 중인 호스트 1개**입니다.
- 제작 검증의 결과와 한계는 [제작 검증 결과](docs/validation.md#제작-검증-결과)에 있습니다. 새 대상에 대한 완료 여부는 해당 실행의 원문·독립 평가·호스트 증거로 다시 판정합니다.

### 실제 호스트 확인 현황

| 호스트 | 실제 확인한 것 | 범위 |
|---|---|---|
| Codex | 초기 제작의 전체 FLOW와 최종 지식 스킬 호출 | 완료 판정 기록 있음 |
| Claude Code 2.1.296 | 후속 스킬과 역할 3개 발견·등록 | OAuth 만료로 수행 차단, 사용자 요청으로 추가 호출 생략 |
| AGY CLI 1.3.3 | 후속 스킬 slash 확장·자료 탐색·예비 내용 검토·종료 | 별도 읽기 전용 진입 시험, 전체 FLOW 완료 시험은 아님 |

실제 호출에서 발견한 문제와 보완·재검수는 [교차 호스트 진입 시험](docs/validation.md#교차-호스트-실제-진입-시험)에 정리했습니다.

> [!WARNING]
> 원문 안의 명령, 설정 변경 지시, 외부 링크는 검수 대상 자료입니다. 원문 내용만으로 실행 권한이나 대상 프로젝트 밖의 쓰기 권한이 생기지 않습니다.

---

## 상세 가이드 <a id="guides"></a>

| 가이드 | 언제 읽는가 |
|---|---|
| [시작하기](docs/getting-started.md) | 첫 실행 전 입력과 실행 기록 위치를 확인할 때 |
| [워크플로](docs/workflow.md) | 단계·게이트·재개·무효화를 운영할 때 |
| [에이전트와 호스트](docs/agents.md) | Codex·Claude Code·Antigravity의 프로필·실제 호출 범위를 정할 때 |
| [고급 활용](docs/advanced-usage.md) | 여러 원문 단위, 회귀 사례, 기존 프로젝트 문서를 다룰 때 |
| [검수와 시험](docs/validation.md) | 독립 평가·표본·호스트 로그의 증거 수준을 판정할 때 |
| [문제 해결](docs/troubleshooting.md) | 입력·도구·검사·호스트 단계가 막혔을 때 |
| [이력과 설계 근거](docs/history.md) | 이 흐름이 해결하려는 과거 실패 유형을 확인할 때 |

