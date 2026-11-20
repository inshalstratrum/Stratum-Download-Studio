"""Shared, native PyQt6 visual language for I-DS.

Keeps existing download/convert logic untouched. All icons are local vector paths,
rendered with QtSvg; no network, font packages or secondary UI frameworks.
"""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, Qt, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QSizePolicy,
)

COLORS = {
    "navy": "#112742",
    "deep": "#0d1f37",
    "teal": "#087e86",
    "light_teal": "#d8f4ee",
    "text": "#16314b",
    "muted": "#526a80",
    "page": "#eef4fa",
    "white": "#ffffff",
}

# Compact 24x24 stroke paths. Shared consistently between toolbar and content.
PATHS = {
    "video": '<rect x="3" y="5" width="18" height="14" rx="3"/><path d="m10 9 6 3-6 3z"/>',
    "file": '<path d="M7 3h7l5 5v13H5V5a2 2 0 0 1 2-2z"/><path d="M14 3v6h5"/><path d="M8 15h8M8 18h5"/>',
    "audio": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "archive": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M11 3v13M10 7h2M10 11h2M10 15h2"/>',
    "document": '<path d="M7 3h7l5 5v13H5V5a2 2 0 0 1 2-2z"/><path d="M14 3v6h5M8 13h8M8 17h6"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l4 2"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "convert": '<path d="m17 3 4 4-4 4M21 7H8a4 4 0 0 0-4 4"/><path d="m7 21-4-4 4-4M3 17h13a4 4 0 0 0 4-4"/>',
    "play": '<path d="m8 5 12 7-12 7z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "cancel": '<rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "pause-all": '<rect x="3.5" y="4" width="17" height="16" rx="3"/><path d="M10 8v8M14 8v8"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6"/>',
    "clear": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/><path d="M10 12l4 4M14 12l-4 4"/>',
    "settings": '<path d="M4 6h16M4 12h16M4 18h16"/><circle cx="9" cy="6" r="2" fill="white"/><circle cx="15" cy="12" r="2" fill="white"/><circle cx="8" cy="18" r="2" fill="white"/>',
    "share": '<path d="M8 12h9m-4-4 4 4-4 4"/><path d="M6 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-2"/>',
    "sidebar": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16M13 9h5M13 13h5"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a3 3 0 1 1 4.8 2.5L12 13v2"/><circle cx="12" cy="18" r=".7" fill="currentColor" stroke="none"/>',
    "narrow": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16"/>',
    "wide": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M13 4v16"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9H3z"/>',
}

BRAND_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
<defs>
 <linearGradient id="body" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#0f294c"/><stop offset="1" stop-color="#105978"/></linearGradient>
 <linearGradient id="letter" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#33decc"/><stop offset="1" stop-color="#26a9e6"/></linearGradient>
</defs>
<rect width="256" height="256" rx="56" fill="url(#body)"/>
<path d="M45 53v150" fill="none" stroke="white" stroke-linecap="round" stroke-width="27"/>
<path d="M103 56h41c55 0 90 27 90 72s-35 72-90 72h-41z" fill="none" stroke="url(#letter)" stroke-linejoin="round" stroke-width="26"/>
<path d="M164 96v53m-18-18 18 18 18-18" fill="none" stroke="white" stroke-width="12" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M144 163v8c0 5 4 8 9 8h22c5 0 9-3 9-8v-8" fill="none" stroke="#5df2d6" stroke-width="10" stroke-linecap="round"/>
</svg>"""


def _render_svg(svg: str, size: int = 72) -> QPixmap:
    image = QPixmap(size, size)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return image


def icon(name: str, color: str = COLORS["text"], size: int = 24) -> QIcon:
    path = PATHS.get(name)
    if not path:
        raise ValueError(f"Unknown I-DS icon: {name}")
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"><g fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{path}</g></svg>'
    return QIcon(_render_svg(svg, size))


def brand_icon(size: int = 72) -> QPixmap:
    return _render_svg(BRAND_SVG, size)


def elevate(widget: QWidget, *, blur: int = 22, y: int = 5, alpha: int = 30) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y)
    shadow.setColor(QColor(15, 43, 77, alpha))
    widget.setGraphicsEffect(shadow)


def make_banner(parent=None):
    banner = QFrame(parent)
    banner.setObjectName("idsBanner")
    banner.setMinimumHeight(91)
    layout = QHBoxLayout(banner)
    layout.setContentsMargins(22, 12, 20, 12)
    layout.setSpacing(14)

    emblem = QLabel()
    emblem.setPixmap(brand_icon(59))
    emblem.setAccessibleName("I-DS download logo")
    layout.addWidget(emblem)

    title_stack = QVBoxLayout()
    title_stack.setSpacing(1)
    title = QLabel("I-DS")
    title.setObjectName("idsTitle")
    title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
    subtitle = QLabel("Download Support")
    subtitle.setObjectName("idsSubtitle")
    title_stack.addWidget(title)
    title_stack.addWidget(subtitle)
    layout.addLayout(title_stack)
    layout.addStretch(1)

    metrics = QHBoxLayout()
    metrics.setSpacing(9)
    labels = {}
    for key, name in (("active", "Active"), ("waiting", "Waiting"), ("done", "Finished")):
        element = QLabel(f"{name}  0")
        element.setObjectName("idsMetric")
        element.setAlignment(Qt.AlignmentFlag.AlignCenter)
        element.setMinimumWidth(97)
        element.setAccessibleName(f"{name}: zero downloads")
        metrics.addWidget(element)
        labels[key] = element
    layout.addLayout(metrics)
    return banner, labels, subtitle


def make_empty_state(on_media, on_file, on_convert, parent=None):
    page = QWidget(parent)
    page.setObjectName("idsEmptyPage")
    outer = QVBoxLayout(page)
    outer.setContentsMargins(18, 16, 18, 16)
    outer.addStretch(2)
    card = QFrame()
    card.setObjectName("idsEmptyCard")
    card.setMinimumWidth(420)
    card.setMaximumWidth(660)
    content = QVBoxLayout(card)
    content.setContentsMargins(23, 18, 23, 19)
    content.setSpacing(7)

    heading = QLabel("What would you like to download?")
    heading.setObjectName("idsEmptyHeading")
    heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
    hint = QLabel("Choose a file or media link to begin.")
    hint.setObjectName("idsEmptyHint")
    hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

    content.addWidget(heading)
    content.addWidget(hint)
    content.addSpacing(9)
    actions = QHBoxLayout()
    actions.setSpacing(12)
    for name, glyph, callback, main in (
        ("Media", "video", on_media, False),
        ("Files", "file", on_file, True),
        ("Convert", "convert", on_convert, False),
    ):
        button = QPushButton(name)
        button.setIcon(icon(glyph, "#ffffff" if main else COLORS["teal"], 25))
        button.setIconSize(QSize(23, 23))
        button.setObjectName("idsPrimaryAction" if main else "idsSecondaryAction")
        button.setMinimumHeight(51)
        button.setAccessibleName(name)
        button.clicked.connect(callback)
        actions.addWidget(button)
    content.addLayout(actions)
    elevate(card, blur=24, y=7, alpha=33)
    center = QHBoxLayout()
    center.addStretch()
    center.addWidget(card)
    center.addStretch()
    outer.addLayout(center)
    outer.addStretch(3)
    return page


UI_POLISH_QSS = """
QMainWindow { background: #eef4fa; }
QFrame#idsBanner {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #122b49, stop:.55 #16496a, stop:1 #0c687b);
    border-radius: 14px;
}
QLabel#idsTitle { color: #ffffff; }
QLabel#idsSubtitle { color: #d4edf5; font-size: 13px; }
QToolButton#idsBannerToggle { background: rgba(255,255,255,0.15); color: white;
    border: 1px solid rgba(255,255,255,0.30); border-radius: 8px;
    min-height: 32px; min-width: 34px; }
QToolButton#idsBannerToggle:hover { background: rgba(255,255,255,0.26); }
QToolButton#idsBannerToggle:focus { border: 2px solid #5ff1d1; }
QLabel#idsMetric {
    border: 1px solid rgba(255,255,255,0.25);
    background: rgba(255,255,255,0.12);
    border-radius: 9px;
    color: #ffffff; padding: 9px 10px;
    font-weight: 650;
}
QFrame#idsEmptyCard { background: #ffffff; border-radius: 16px; }
QWidget#idsEmptyPage { background: #eef4fa; }
QLabel#idsEmptyHeading { color: #19364f; font-size: 20px; font-weight: 700; }
QLabel#idsEmptyHint { color: #51677d; font-size: 14px; }
QPushButton#idsPrimaryAction {
    color: white; background: #087e86; border-radius: 10px;
    border: 1px solid #087e86; font-weight: 700; padding: 11px 13px;
}
QPushButton#idsPrimaryAction:hover { background: #06656d; }
QPushButton#idsPrimaryAction:pressed { background: #064f59; }
QPushButton#idsSecondaryAction { border-radius: 10px; background: #edf7fa;
    color: #185174; border: 1px solid #c8e1ea; font-weight: 650; padding: 11px 12px; }
QPushButton#idsSecondaryAction:hover { background: #d9f0f3; }
QPushButton#idsSecondaryAction:pressed { background: #c9e5e8; }
QPushButton#idsPrimaryAction:focus, QPushButton#idsSecondaryAction:focus {
    border: 2px solid #249ae6;
}
QFrame#idsSidebarPanel { background: #ffffff; border-radius: 11px; }
QLabel#idsSidebarTitle { color: #19364f; font-size: 14px; font-weight: 700; }
QWidget#idsWorkspace { background: #eef4fa; }
QFrame#idsFooter { background: #ffffff; border-radius: 8px; }
QLabel#idsFooterText { color: #51677d; padding: 2px 6px; }
QTreeWidget, QTableWidget { border: 0px; border-radius: 8px; }
QToolBar { background: #f8fbfe; spacing: 3px; padding: 5px 10px; }
QToolButton { min-width: 49px; padding: 6px 8px; border-radius: 9px; }
QToolButton:hover { background: #dceff4; border-color: #a6cdd9; }
QHeaderView::section { background: #e8f0f8; padding: 10px 8px; }
QSplitter::handle { background: #d0e2ec; }
QSplitter::handle:hover { background: #5ab7bc; }
QTableWidget::item:selected, QTreeWidget::item:selected { background: #cdeee9; color: #143f4f; }
QStatusBar { background: #f7fbfe; color: #456174; }
"""
