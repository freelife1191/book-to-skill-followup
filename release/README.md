# 릴리스 노트 가이드

[← 프로젝트 소개](../README.md) · [문서 지도](../docs/index.md) · [GitHub Releases](https://github.com/freelife1191/book-to-skill-followup/releases)

변경 내역을 날짜별 Markdown 파일로 남기고, 배포할 때 해당 파일을 GitHub Release 본문으로 사용합니다.

## 파일 구조

```text
release/
├── README.md                                    # 작성 규칙·배포 안내·노트 목록
├── _template.md                                 # 새 노트의 원본
└── 2026-10-15-documentation-and-release-guide.md  # 날짜별 변경 내역
```

## 이름 규칙

**`yyyy-mm-dd-title.md`**를 사용합니다. 날짜는 한국 시간(Asia/Seoul)의 작성일, `title`은 변경 주제를 나타내는 영어 소문자와 숫자·하이픈 조합입니다.

| 항목 | 규칙 | 예시 |
|---|---|---|
| 날짜 | 실제 달력 날짜, 연도 4자리·월/일 2자리 | `2026-10-15` |
| 제목 | 소문자 kebab-case, 단어 사이 하이픈 | `documentation-and-release-guide` |
| 확장자 | Markdown | `.md` |
| 같은 날 여러 노트 | 제목을 다르게 작성 | `2026-10-15-source-citation-fix.md` |
| 버전·태그 | 프로젝트의 실제 버전을 별도로 지정 | 날짜 파일명을 버전으로 자동 간주하지 않음 |

`README.md`와 `_template.md`는 관리 문서이므로 날짜별 노트 규칙의 예외입니다. 노트 목록에 새 항목을 추가하고 README나 관련 가이드에서도 연결합니다.

## 노트 목록

| 작성일 | 변경 내용 |
|---|---|
| 2026-10-15 | [문서 구성과 릴리스 노트 가이드](2026-10-15-documentation-and-release-guide.md) |

## 작성 순서

1. [_template.md](_template.md)를 새 날짜·제목 파일로 복사합니다.
2. 사용자에게 달라진 점, 대상과 필요한 조치, 호환성·제약을 적습니다.
3. 실제 실행한 검사와 미검증 범위를 구분하고 관련 문서 링크를 붙입니다.
4. 노트·목록·관련 문서를 함께 커밋하고 푸시합니다. 태그와 공개 릴리스는 별도 단계입니다.

> [!TIP]
> GitHub Release 본문은 파일 내용을 그대로 사용합니다. 노트 안의 문서 링크는 저장소의 전체 GitHub URL로 적어 공개 화면에서도 이동할 수 있게 합니다. 특정 배포본에 고정할 링크는 해당 태그나 커밋 URL을 사용하세요.

## GitHub Release에 사용하기

아래 명령은 **향후 배포용 예시**입니다. `gh` 인증과 대상 커밋의 원격 반영을 먼저 확인하고, 기존 버전 정책에 맞는 새 태그를 선택합니다. 인증 값은 환경변수로만 전달하며 파일·명령 인자·원격 URL에 적지 않습니다.

### 새 태그로 초안 생성

저장소 루트에서 실제 값으로 변수들을 바꾼 뒤 실행합니다. `--target`은 태그가 아직 없을 때 태그를 만들 기준입니다.

```bash
RELEASE_TAG='실제-새-태그'
RELEASE_COMMIT='원격에-푸시한-전체-커밋-SHA'
RELEASE_TITLE='실제 릴리스 제목'
RELEASE_NOTE='release/2026-10-15-documentation-and-release-guide.md'

gh release create "$RELEASE_TAG"   --repo freelife1191/book-to-skill-followup   --target "$RELEASE_COMMIT"   --draft   --title "$RELEASE_TITLE"   --notes-file "$RELEASE_NOTE"
```

### 이미 원격에 있는 태그 사용

대상 태그와 커밋을 확인한 후 `--verify-tag`를 사용합니다. 태그가 없으면 중단하고 자동 생성하지 않습니다.

```bash
gh release create "$RELEASE_TAG"   --repo freelife1191/book-to-skill-followup   --verify-tag   --draft   --title "$RELEASE_TITLE"   --notes-file "$RELEASE_NOTE"
```

### 기존 릴리스에 노트 적용

대상 릴리스의 태그·커밋·공개 상태를 먼저 확인합니다. 다음 명령은 본문을 파일 전체로 교체하므로 기존 내용을 보존할지 검토한 뒤 사용합니다.

```bash
gh release edit "$RELEASE_TAG"   --repo freelife1191/book-to-skill-followup   --notes-file "$RELEASE_NOTE"
```

### 초안 검토와 공개

초안 화면에서 태그와 변경 내용을 확인합니다. 공개하기로 정한 **초안**에 아래 명령을 실행하면 GitHub Release가 공개됩니다.

```bash
gh release edit "$RELEASE_TAG"   --repo freelife1191/book-to-skill-followup   --draft=false
```

노트 파일 저장·커밋·푸시는 공개 릴리스 생성이나 태그 푸시를 자동으로 실행하지 않습니다. 이 구조에는 자동 배포 워크플로가 없습니다.

## 배포 전 확인

- [ ] 노트 이름과 작성일이 규칙에 맞는다.
- [ ] 노트가 실제 변경 내용·검증 범위와 일치한다.
- [ ] 책 원문·PDF·인증 파일·실행 로그·작업 복사본이 포함되지 않았다.
- [ ] 대상 커밋이 원격에 있고 태그가 그 커밋을 가리킨다.
- [ ] 노트의 링크가 공개 저장소의 문서로 이동한다.
- [ ] 초안의 본문과 호환성·미검증 범위를 확인했다.

공식 옵션 설명: [gh release create](https://cli.github.com/manual/gh_release_create) · [gh release edit](https://cli.github.com/manual/gh_release_edit).
