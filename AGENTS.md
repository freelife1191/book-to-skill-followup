# 프로젝트 작업 지침

답변과 문서는 한국어로 작성합니다.

## GitHub 인증·커밋·푸시

- 이 프로젝트의 GitHub 계정은 **`freelife1191`**이며 원격 저장소는 `https://github.com/freelife1191/book-to-skill-followup`입니다.
- 인증은 사용자 `~/.zshrc`의 `GITHUB_TOKEN`을 사용합니다. 부모 디렉터리의 `.envrc` 또는 상속된 `GH_TOKEN`이 다른 계정이라면 사용하지 않습니다.
- 필요한 변수만 읽고 명령의 환경에서 `GH_TOKEN`과 `GITHUB_TOKEN`을 해당 토큰으로 지정합니다. `.zshrc` 전체를 실행하거나 토큰을 출력·복사·문서화하지 않습니다.
- 변경 전에 `gh api user`로 토큰의 실제 계정이 `freelife1191`인지 확인합니다. 다르면 커밋·푸시를 중단합니다.
- 작성자와 커미터는 같은 `.zshrc`의 `GITHUB_USERNAME`·`GITHUB_USEREMAIL`을 사용합니다. 각 Git 명령에 `GIT_AUTHOR_NAME`·`GIT_AUTHOR_EMAIL`·`GIT_COMMITTER_NAME`·`GIT_COMMITTER_EMAIL`을 지정하고 전역 Git 설정은 변경하지 않습니다.
- HTTPS 푸시는 명령 한 번에 한정된 `gh auth git-credential` credential helper로 인증합니다. 토큰을 remote URL이나 Git 설정에 저장하지 않습니다.
- 커밋 전에 스테이징 목록과 비밀정보 포함 여부를 확인합니다. 원문 책/PDF, 실제 작업 복사본, 인증 파일, 실행 로그와 `output/`·`_workspace/`·`.omx/`는 배포하지 않습니다. 자체 제작한 `fixtures/` 시험 자료는 포함합니다.
- 최초 공개 생성·커밋·푸시는 사용자가 승인했습니다. 이후 작업에서 추가 푸시나 배포는 해당 요청의 범위에 따릅니다. 강제 푸시와 이력 재작성은 하지 않습니다.

## 검증

변경 범위에 맞는 단위 시험과 패키지 정적 검사를 실행합니다. 초기 Codex 전체 FLOW와 최신본의 단위·정적 검증, Antigravity 제한 호출 검증을 구분하며 최신본의 전체 FLOW 재검증을 주장하지 않습니다.
