# 문서 구성과 릴리스 노트 가이드

> 작성일: 2026-10-15 · 대상: 책 지식 스킬 후속 완성 사용자와 저장소 관리자

설치·작업 흐름·검증 범위와 상세 문서를 README 상단에서 찾을 수 있게 정돈했습니다. 날짜별 변경 내역을 GitHub Release 본문으로 사용할 수 있는 `release/` 구조를 추가했습니다.

## 변경 내용

- README 상단에 소개 배너, 스킬·호스트 안내 배지, 주요 문서 바로가기를 배치했습니다.
- 긴 가이드에 펼칠 수 있는 목차를 추가하고 모든 사용자 문서에 프로젝트·가이드 홈·릴리스 탐색을 연결했습니다.
- 수동 설치 명령을 접이식 영역으로 묶고 작업 단계를 Mermaid 흐름도로 표시했습니다.
- `release/yyyy-mm-dd-title.md` 이름 규칙, 작성 템플릿과 변경 내역 목록을 추가했습니다.
- 노트 파일로 GitHub Release 초안 생성·기존 본문 갱신·초안 공개를 진행하는 절차를 문서화했습니다.

## 사용자 조치와 호환성

사용자는 문서 탐색을 그대로 이용하면 됩니다. 관리자에게는 다음 변경부터 날짜와 주제를 적은 파일로 노트를 작성하는 방식이 추가됩니다. 스킬 호출 이름·설치 경로·실행 계약은 변경하지 않았습니다. 기존 사용법·링크 앵커·검증 이력과 한계를 유지합니다.

## 검증

- 패키지 정적 검사 74개 파일과 사용자 Markdown 12개 파일의 링크·앵커 검사, SVG 구조 검사, `git diff --check`가 통과했습니다.
- GitHub Markdown 렌더링 API로 README 상단의 제목·배너·탐색을 확인했습니다.
- 기존 단위 시험 90개와 하위 검사 23개가 통과했습니다. 후속 전체 FLOW나 실제 호스트 재호출을 뜻하지 않습니다.

## 한계와 미검증 범위

이번 변경은 문서와 릴리스 노트 구조에 한정됩니다. 후속 스킬의 전체 FLOW와 Codex·Claude Code·Antigravity 실제 호출을 다시 검증한 릴리스가 아닙니다. 파일의 커밋·푸시는 공개 GitHub Release의 생성이나 새 태그 배포를 뜻하지 않습니다.

## 관련 문서

- [프로젝트 소개](https://github.com/freelife1191/book-to-skill-followup/blob/main/README.md)
- [상세 가이드](https://github.com/freelife1191/book-to-skill-followup/blob/main/docs/index.md)
- [릴리스 노트 가이드](https://github.com/freelife1191/book-to-skill-followup/blob/main/release/README.md)
- [다음 노트 템플릿](https://github.com/freelife1191/book-to-skill-followup/blob/main/release/_template.md)
