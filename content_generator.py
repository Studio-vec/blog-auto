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


def _build_prompt(topic: dict) -> str:
    place_desc = f"{topic['place']} ({topic['theme']}, {topic['season']} 추천)"
    trip_type = f"{topic['category']} 코스"
    hint_tags = " ".join(f"#{t}" for t in topic.get("tags", []))
    vibe = topic.get("vibe", "")
    photo_points = topic.get("photo_points", [])
    photo_hint = "\n".join(f"  - {p}" for p in photo_points) if photo_points else "  - 없음"

    return f"""다음 국내 여행지에 대한 블로그 여행 후기를 작성해줘.
독자: 20~40대 여성 + 커플 여행 계획 중인 남성
기준: 2023~2025년 최신 트렌드 반영

여행지: {place_desc}
여행 형태: {trip_type}
감성 키워드: {vibe}
핵심 포토존 (반드시 본문에 포함할 것):
{photo_hint}
관련 키워드: {hint_tags}

아래 형식을 정확히 따라서 작성해줘:

---
[제목]: 이모지 포함, SEO 친화적인 제목
(예: 📸 담양 당일치기 | 죽녹원 감성샷 명당부터 힙한 카페 골목까지 커플 코스 추천)

[본문]:
1. 인트로 (여행 배경과 설레는 감정 2~3문장 — 커플 또는 여성 솔로 여행자 시점)
2. [📸 사진] + 여행지 소개 (2023~2025년 현재 분위기, 왜 지금 핫한지)
3. 📸 포토존 & 감성 스팟 (최소 3곳 — 찍는 각도·시간대·구도 팁 포함, 인스타 감성 강조)
4. 🗺️ 추천 코스 (시간대별 동선, 커플 기준으로 구체적으로)
5. 🍽️ 맛집 추천 (2~3곳 — 메뉴·가격·분위기·인스타 감성 여부 포함)
6. ☕ 힙한 카페 추천 (1~2곳 — 인테리어·시그니처 메뉴·포토존 여부 포함)
7. 🏨 숙소 추천 (뷰 좋거나 감성 있는 곳 위주, 가격대 포함)
8. 💡 여행 꿀팁 (혼잡 시간대·주차·예약 필수 여부·커플 추천 포인트 등)
9. 마무리 (설레는 여운이 남는 마무리)

[해시태그]: 15개 이상 (#국내여행 #커플여행 #포토스팟 #감성여행 #여행스타그램 등 포함)
---

실제 블로그처럼 자연스럽고 생생하게 써줘."""


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
    title, body, tags = _parse_response(raw)

    return {
        "title": title,
        "body": body,
        "tags": tags,
        "topic": topic,
        "raw": raw,
    }


def _parse_response(raw: str) -> tuple[str, str, str]:
    """생성된 텍스트에서 제목·본문·태그를 분리."""
    import re
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
