from bs4 import BeautifulSoup, Tag
from urllib.parse import urljoin

from models import Notice

base_url = "https://csai.jbnu.ac.kr"

def find_required(parent: Tag, name: str, class_: str | None = None) -> Tag:
    if class_ is not None:
        tag = parent.find(name, class_ = class_)
    else:
        tag = parent.find(name)

    assert isinstance(tag, Tag)
    return tag

def parse(html: str) -> list[Notice]:
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.select("tbody tr") 
    notices: list[Notice] = []

    for row in rows:
        title = find_required(row, "strong").get_text(strip = True)

        href = find_required(row, "a").get("href")
        assert isinstance(href, str)

        url = urljoin(base_url, href)
        
        notice_id = url.split("/")[-2]
        
        published_at = find_required(row, "td", "_artclTdRdate").get_text(strip = True)

        source = "csai"

        notices.append(Notice(
            id = notice_id,
            source = source,
            title = title,
            url = url,
            published_at = published_at,
            ))

    return notices
