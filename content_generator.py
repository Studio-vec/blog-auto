import re
import anthropic
from config import ANTHROPIC_API_KEY
from topics import pick_topic

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


SYSTEM_PROMPT = """너는 트렌디하고 감성적인 20~30대 여성 국내 여행 블로거야.
주 독자층은 '여행을 좋아하는 20~40대 여성'과 '여자친구와 커플 여행을 계획 중인 남성'이야.
2023~2025년 최신 국내 여행 트렌드를 반영해서 써줘.

독자에게 어필해야 할 핵심 포인트:
- 인스타그램·릴스에 올리기 좋은 포토존, 감성샷 스팟 강조
- 힙하고 분위기 있는 카페·레스토랑 (인테리어·메뉴·가격 구체적으로)
- 자연경관이더라도 "여기서 찍으면 예쁜 각도·시간대·구도" 팁 포함
- 커플이 함께 즐길 수 있는 액티비티, 야경 스팟, 로맨틱한 포인트 명시
- 여성이 '이 글 보고 바로 가보고 싶다' 느끼게 만드는 감성 문체
- 남성이 '여자친구를 여기 데려가면 완벽하겠다' 확신 들게 만드는 실용 정보

글쓰기 규칙:
- 친근하고 생동감 있는 해요체 (너무 딱딱하지 않게)
- 이모지 적절히 사용 (과하지 않게)
- 사진 자리에는 [📸 사진] 으로 표시
- 각 섹션은 이모지 소제목으로 구분
- 2023~2025년 기준 실제 운영 중인 맛집·카페·숙소 정보
- 가격·운영시간·예약 방법·주차 정보 등 실용 정보 포함
- 혼잡도·베스트 방문 시간 같은 현실적인 팁 포함"""

FACT_CHECK_SYSTEM = """너는 국내 여행 정보 팩트체커야.
블로그 글에 포함된 사실 정보를 2023~2025년 기준으로 검토하고, 오류를 수정하거나 불확실한 정보에 주의 표시를 달아줘.

검토 기준:
- 맛집·카페·숙소 이름이 실제 존재하는 곳인지 (불확실하면 삭제하고 대체)
- 가격이 실제와 크게 다르면 수정 (확인 불가면 "약 X원대" 형식 유지)
- 운영시간·예약방법·주차 정보가 틀렸으면 수정, 불확실하면 뒤에 "(방문 전 확인 필수)" 추가
- 체험 프로그램이 실제 운영 중인지, 가격·소요시간이 합리적인지
- 포토존·스팟 설명이 실제와 맞는지
- 존재하지 않거나 폐업이 확실한 곳은 삭제하고 비슷한 실제 장소로 교체

수정 원칙:
- 감성적인 문체와 구조는 그대로 유지
- 사실 오류만 최소한으로 수정
- 확인할 수 없는 세부 정보(정확한 가격, 정확한 운영시간)는 삭제하지 말고 불확실성 표시만 추가
- 전체 분량이 크게 줄어들면 안 됨"""


def _build_prompt(topic: dict) -> str:
    place_desc = f"{topic['place']} ({topic['theme']}, {topic['season']} 추천)"
    trip_type = f"{topic['category']} 코스"
    hint_tags = " ".join(f"#{t}" for t in topic.get("tags", []))
    vibe = topic.get("vibe", "")
    photo_points = topic.get("photo_points", [])
    photo_hint = "\n".join(f"  - {p}" for p in photo_points) if photo_points else "  - 없음"
    best_time = topic.get("best_time", "")
    experience = topic.get("experience", "")

    best_time_line = f"방문 최적 시기: {best_time}\n" if best_time else ""
    experience_line = f"커플 체험 활동 (반드시 본문에 포함할 것):\n  - {experience}\n" if experience else ""

    return f"""다음 국내 여행지에 대한 블로그 여행 후기를 작성해줘.
독자: 20~40대 여성 + 커플 여행 계획 중인 남성
기준: 2023~2025년 최신 트렌드 반영

여행지: {place_desc}
여행 형태: {trip_type}
감성 키워드: {vibe}
{best_time_line}핵심 포토존 (반드시 본문에 포함할 것):
{photo_hint}
{experience_line}관련 키워드: {hint_tags}

아래 형식을 정확히 따라서 작성해줘:

---
[제목]: 이모지 포함, SEO 친화적인 제목
(예: 📸 담양 당일치기 | 죽녹원 감성샷 명당부터 힙한 카페 골목까지 커플 코스 추천)

[본문]:
1. 인트로 (여행 배경과 설레는 감정 2~3문장 — 커플 또는 여성 솔로 여행자 시점)
2. [📸 사진] + 여행지 소개 (2023~2025년 현재 분위기, 왜 지금 핫한지)
3. 📅 언제 가면 가장 예쁠까? (방문 최적 시기·계절별 차이, 비수기 꿀팁 포함)
4. 📸 포토존 & 감성 스팟 (최소 3곳 — 찍는 각도·시간대·구도 팁 포함, 인스타 감성 강조)
5. 🎯 커플 체험 (1~2시간 이상 함께 즐기는 체험 활동 — 예약 방법·가격·소요시간·후기 포인트 포함)
6. 🗺️ 추천 코스 (시간대별 동선, 커플 기준으로 구체적으로)
7. 🍽️ 맛집 추천 (2~3곳 — 메뉴·가격·분위기·인스타 감성 여부 포함)
8. ☕ 힙한 카페 추천 (1~2곳 — 인테리어·시그니처 메뉴·포토존 여부 포함)
9. 🏨 숙소 추천 (뷰 좋거나 감성 있는 곳 위주, 가격대 포함)
10. 💡 여행 꿀팁 (혼잡 시간대·주차·예약 필수 여부·커플 추천 포인트 등)
11. 마무리 (설레는 여운이 남는 마무리)

[해시태그]: 15개 이상 (#국내여행 #커플여행 #포토스팟 #감성여행 #여행스타그램 등 포함)
---

실제 블로그처럼 자연스럽고 생생하게 써줘."""


_CTA_HTML = """
<div style="margin: 40px 0; padding: 24px 28px; background: linear-gradient(135deg, #f0f7ff 0%, #e8f4fd 100%); border-left: 4px solid #4a9eff; border-radius: 12px;">
  <p style="margin: 0 0 8px 0; font-size: 15px; font-weight: 700; color: #1a6fc4;">📍 코스 짜기 귀찮을 때, 그냥 따라오세요!</p>
  <p style="margin: 0 0 12px 0; font-size: 14px; color: #444; line-height: 1.6;">제가 직접 다녀온 국내 여행 코스만 모아둔 곳이에요. 동선·맛집·포토존까지 그대로 따라가면 되는 코스를 정리해뒀으니, 여행 계획 세우기 복잡하다면 한번 들러보세요 🗺️</p>
  <a href="https://huihui-travel.vercel.app/" target="_blank" rel="noopener noreferrer"
     style="display: inline-block; padding: 10px 20px; background: #4a9eff; color: #fff; font-size: 14px; font-weight: 600; border-radius: 8px; text-decoration: none;">
    👉 내가 직접 짠 여행 코스 보러 가기
  </a>
</div>
"""


def _fact_check_raw(raw: str, topic: dict) -> str:
    """생성된 원문을 팩트체크하고 수정된 원문 반환."""
    place = topic.get("place", "")
    print(f"[팩트체크] {place} 글 사실 확인 중...")

    fact_prompt = f"""다음은 '{place}' 국내 여행 블로그 포스트야. 아래 항목을 꼼꼼히 사실 확인하고 수정해줘.

확인 항목:
1. 맛집·카페·숙소 이름 — 실제 존재 여부, 폐업 여부
2. 가격 정보 — 실제 가격대와 크게 다르면 수정
3. 운영시간·예약방법 — 불확실하면 "(방문 전 확인 필수)" 추가
4. 체험 프로그램 — 실제 운영 여부, 가격·소요시간 합리성
5. 포토존·스팟 — 실제 접근 가능한 곳인지
6. 교통·주차 정보 — 사실과 다른 내용 수정

[원본 포스트]
{raw}

위 원본을 그대로 출력하되, 사실 오류만 수정해서 완성된 포스트 전체를 출력해줘.
형식(제목/본문/해시태그 구조)은 반드시 원본과 동일하게 유지해줘."""

    checked = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=FACT_CHECK_SYSTEM,
        messages=[{"role": "user", "content": fact_prompt}],
    )

    result = checked.content[0].text
    print(f"[팩트체크] 완료 ✅")
    return result


def generate_post(topic: dict | None = None) -> dict:
    """Claude API로 블로그 포스트 생성. 반환: {title, body, tags, topic}"""
    if topic is None:
        topic = pick_topic()

    prompt = _build_prompt(topic)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text
    raw = _fact_check_raw(raw, topic)
    title, body, tags = _parse_response(raw)
    body = body + _CTA_HTML

    return {
        "title": title,
        "body": body,
        "tags": tags,
        "topic": topic,
        "raw": raw,
    }


def _parse_response(raw: str) -> tuple[str, str, str]:
    """생성된 텍스트에서 제목·본문·태그를 분리."""
    lines = raw.strip().splitlines()

    title = ""
    body_lines = []
    tags_lines = []

    mode = "scan"
    for line in lines:
        stripped = line.strip()

        # 제목 감지 (다양한 포맷 대응)
        if re.match(r"\[제목\]\s*:", stripped) or re.match(r"#+\s*.+", stripped) and not title:
            title = re.sub(r"^\[제목\]\s*:\s*", "", stripped)
            title = re.sub(r"^#+\s*", "", title).strip()
            mode = "body"
            continue

        # 본문 시작
        if re.match(r"\[본문\]\s*:", stripped):
            mode = "body"
            continue

        # 해시태그 섹션 시작
        if re.match(r"\[해시태그\]\s*:", stripped):
            rest = re.sub(r"^\[해시태그\]\s*:\s*", "", stripped)
            tags_lines.append(rest)
            mode = "tags"
            continue

        if mode == "body":
            body_lines.append(line)
        elif mode == "tags":
            tags_lines.append(stripped)
    # 제목이 파싱 안 됐으면 첫 줄에서 추출 시도
    if not title:
        for line in lines:
            s = line.strip()
            if s and not s.startswith("["):
                title = re.sub(r"^#+\s*", "", s).strip()
                break

    body = "\n".join(body_lines).strip()
    tags = " ".join(t for t in tags_lines if t).strip()

    # 해시태그가 파싱 안 됐으면 raw에서 # 태그 추출
    if not tags:
        tags = " ".join(re.findall(r"#[가-힣A-Za-z0-9]+", raw))

    html_body = _to_html(body)
    return title, html_body, tags


def _to_html(text: str) -> str:
    """마크다운 스타일 텍스트를 기본 HTML로 변환."""
    html_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            html_lines.append("<br>")
            continue
        if s.startswith("## "):
            html_lines.append(f"<h3>{s[3:]}</h3>")
        elif s.startswith("# "):
            html_lines.append(f"<h2>{s[2:]}</h2>")
        elif s.startswith("[📸 사진]"):
            html_lines.append(
                '<div style="background:#f5f5f5;padding:60px;text-align:center;'
                'margin:16px 0;border-radius:8px;color:#888;">📸 사진을 여기에 추가하세요</div>'
            )
        elif s.startswith("- ") or s.startswith("• "):
            html_lines.append(f"<li>{s[2:]}</li>")
        else:
            html_lines.append(f"<p>{s}</p>")

    return "\n".join(html_lines)
