# 실행·증거 계약

보조기는 구조와 해시를 확인한다. JSON만 채웠다고 실제 작업을 수행한 것이 아니다. 실행 전에 하위 명령 --help를 확인한다. init은 프로젝트·상대 스킬·원문 절대 경로(반복 가능)·상대 문서 경로(반복 가능)·호스트를 받으며 _workspace/harness/book-to-skill-followup/<run-id>/에 기록한다.

원문 source, 설치된 후속 스킬 toolchain, 대상 지식·문서·관련 프로필 subject의 fingerprint를 분리한다. run과 캐시는 subject에서 제외한다. artifact는 run 상대 실제 regular file이며 symlink/루트 탈출을 허용하지 않는다. source 외부 입력은 명시적 읽기 전용이다.

## 단계별 구조

공통 verdict는 pass/fail/blocked다. 검사 단계는 snapshot의 현재 digest를 subject_digest로 기록한다. 제작자 producer_id는 run 상태에 있고 독립 reviewer/evaluator는 다른 실제 세션 ID를 쓴다.

| 단계 | 내용 |
|---|---|
| preflight | project/skill_rel/source_hashes/write_paths를 init 상태와 결속, scope_confirmed: true |
| inventory | expected_unit_ids, units: id/source_path/source_locator/skill_files/status/reason |
| source-audit | 전체 units, claims: id/unit_id/origin/source_locator/verdict, reviewer_id, visual_candidates/visual_checks |
| skill-refinement | changes: 상대 path/이유, units_covered, resolutions |
| documentation | units_covered, reviewed_prompt_ids, 전체 전략·장별2예시/후속1·공통4/연계3 의미 검토 |
| static-checks | 검사기의 errors/scanned_files/files_digest/subject_digest/project/skill과 현재 스냅샷 일치 |
| behavior-tests | subject_digest, cases: retrieval/application/critique 각 1개 이상과 발견 오류 regression |
| improvement | changes, units_covered, revisions(상태의 현재 값), 보완·재검사 범위 |
| freeze | subject_digest, 독립 reviewer_id, blockers 빈 배열, addressed_findings, independent_review_evidence와 직접 내용 검토 |
| host-smoke | host/returncode/loaded/turn_completed/subject_digest/trace_file/trace_sha256/proof_files와 한계 |
| final-review | subject_digest, 독립 reviewer_id, blockers, post_host: true |

changes는 허용된 프로젝트 상대 path만 쓴다. 변화가 없으면 빈 배열이다. inventory status는 mapped/missing/excluded이며 누락/제외는 reason을 쓴다. 주장 origin은 author/synthesis/validation-guidance/proposal이다.

source-audit의 pass는 전체 감사를 수행해 발견 사항을 정확히 기록했다는 뜻이다. 초기 스킬에서 mismatch/needs-refinement를 발견하면 finding으로 보존하고 다음 보완 단계로 진행한다. 원문에 접근하지 못했거나 단위를 실제 검토하지 못한 경우는 blocked다. 최종 freeze에서는 중요한 미해결 오류·누락을 차단한다. 원문 자체의 불확실성을 정확히 표시하는 것은 결함과 구분한다.

source-audit units는 id와 verdict(pass 또는 needs-refinement)를 갖는 객체다. claims는 각 단위의 id/unit_id/origin/source_locator/verdict(pass/mismatch/uncertain) 객체이며 전체 단위에 최소 하나씩 있어야 한다. source_path는 선언된 원문, skill_files는 대상 스킬 아래 프로젝트 상대 파일이다.

보완할 claim(mismatch)은 claim:<id>, unit(needs-refinement)은 unit:<id>로 식별한다. skill-refinement의 resolutions는 이 ID 전체를 정확히 포함하는 id/kind/reason/paths 객체 목록이다. kind는 fixed/documented/false-positive이며 실제 파일 위치와 처리 이유를 적는다. findings가 없으면 빈 배열이다. freeze의 addressed_findings는 같은 전체 ID 목록이고 독립 검토자는 실제 파일에서 처리가 적절한지 확인한다. ID를 채우는 것만으로 의미상 해결된 것은 아니다.

behavior case는 id/kind/fresh/evaluator_id/verdict/input_file/answer_file/rubric_file/assertions/read_files를 가진다. 기본 kind는 retrieval/application/critique, 추가 오류 사례는 regression이다. input/answer/rubric은 run 상대 파일이다. rubric은 결과를 보기 전에 고정하고 수행자에게 예상 답안을 누설하지 않는다. assertions는 id/passed/reason 객체이며 실제 의미를 검토한다.

read_files는 path/sha256/scope를 기록한다. scope=project는 프로젝트 상대 경로, run은 run 상대 경로, source는 선언된 원문의 절대 경로다. 목록이 없으면 빈 배열이며 증거 종류를 별도로 표시한다. 실존·해시 확인은 실제 과거 tooltrace를 대체하지 않는다. 추가 rubric·원래 trace 등 참조 자료는 evidence_artifacts의 path/sha256/scope로 결속한다.

host proof_files는 run 상대 path/sha256 객체 목록이다. trace_file의 JSON에는 실제 호스트 로그에서 추출한 성공 read 이벤트와 turn.completed가 있어야 하고, 격리 복사한 SKILL.md가 읽힌 증거를 포함해야 한다. 정상 종료와 loaded 자기 주장만으로는 부족하다.

## 무효화와 완료

증거·case 입력/답변/rubric/trace의 해시를 결속한다. 최초 실패를 보존하고 정정·재생성·새 독립 평가를 분리한다. 생산 단계는 내용을 바꿀 수 있지만 검사 이후의 변경은 관련 검증을 stale로 만든다. source/spec/toolchain 변경은 이전 완료 근거를 무효화한다. 보완 뒤 필요한 단계를 재실행한다.

제작자 ID를 지정하지 않으면 run별 coordinator ID를 발급한다. 실제 수행·검토 세션 ID를 기록하고 보완 후 최종 평가자는 이전 통과 평가자를 재사용하지 않는다. 보조기의 ID/메타데이터 검사는 실제 프로세스 격리를 자동 증명하지 않으므로 네이티브 호출의 fresh 설정과 가능한 도구 trace를 함께 검토한다.

verify는 실제 파일/해시/단계 의존성을 확인한다. finalize는 모든 필수 성공과 유효한 1회 host 증거를 요구한다. frozen subject가 바뀌거나 호스트 후 수정이 필요하면 새 run을 만든다. host/최종 결과를 스킬 source.json에 덧붙여 검증 버전을 바꾸지 않고 기록에만 저장한다. GUI와 다른 호스트의 미검증은 별도 한계다.
