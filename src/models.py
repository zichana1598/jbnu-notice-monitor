from dataclasses import dataclass

@dataclass
class Notice:
    id: str
    source: str
    title: str
    url: str
    published_at: str
