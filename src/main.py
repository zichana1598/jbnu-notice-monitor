from collectors.http_collector import fetch
from parsers.csai_parser import parse

url = "https://csai.jbnu.ac.kr/csai/29107/subview.do"

html = fetch(url)
notices = parse(html)
