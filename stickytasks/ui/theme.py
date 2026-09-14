"""Colours and stylesheet for the panel chrome.

The task cards are coloured by due date, so the surrounding chrome is kept
deliberately neutral and dark: it has to stay out of the way of a column of
saturated reds, ambers and greens.
"""

from __future__ import annotations

BG = "#1c1f26"
BG_HEADER = "#151820"
BG_INPUT = "#262a33"
BG_HOVER = "#30353f"
FG = "#e6e9ef"
FG_DIM = "#9aa3b2"
BORDER = "#333844"
ACCENT = "#4c8dff"


def panel_stylesheet(font_size: int = 10) -> str:
    return f"""
    QWidget#StickyPanel {{
        background: {BG};
    }}
    QWidget#PanelHeader {{
        background: {BG_HEADER};
        border-bottom: 1px solid {BORDER};
    }}
    QWidget#PanelFooter {{
        background: {BG_HEADER};
        border-top: 1px solid {BORDER};
    }}
    QLabel {{
        color: {FG};
        font-size: {font_size}pt;
    }}
    QLabel#PanelTitle {{
        color: {FG};
        font-size: {font_size + 1}pt;
        font-weight: 600;
    }}
    QLabel#FooterLabel {{
        color: {FG_DIM};
        font-size: {font_size - 1}pt;
    }}
    QLineEdit, QComboBox, QDateEdit, QSpinBox, QPlainTextEdit, QTextEdit {{
        background: {BG_INPUT};
        color: {FG};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 3px 6px;
        font-size: {font_size}pt;
        selection-background-color: {ACCENT};
    }}
    QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus,
    QPlainTextEdit:focus, QTextEdit:focus {{
        border: 1px solid {ACCENT};
    }}
    QComboBox::drop-down {{ border: none; width: 16px; }}
    QComboBox QAbstractItemView {{
        background: {BG_INPUT};
        color: {FG};
        selection-background-color: {ACCENT};
        border: 1px solid {BORDER};
    }}
    QToolButton {{
        background: transparent;
        color: {FG};
        border: none;
        border-radius: 4px;
        padding: 2px;
        font-size: {font_size}pt;
    }}
    QToolButton:hover {{ background: {BG_HOVER}; }}
    QToolButton:checked {{ background: {ACCENT}; color: #ffffff; }}
    QPushButton {{
        background: {BG_INPUT};
        color: {FG};
        border: 1px solid {BORDER};
        border-radius: 4px;
        padding: 5px 12px;
        font-size: {font_size}pt;
    }}
    QPushButton:hover {{ background: {BG_HOVER}; }}
    QPushButton:default {{ background: {ACCENT}; border-color: {ACCENT}; color: #ffffff; }}
    QScrollArea {{ background: {BG}; border: none; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 0;
    }}
    QScrollBar::handle:vertical {{
        background: {BORDER}; border-radius: 5px; min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {FG_DIM}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
    QMenu {{
        background: {BG_INPUT}; color: {FG}; border: 1px solid {BORDER};
    }}
    QMenu::item:selected {{ background: {ACCENT}; }}
    QCheckBox, QRadioButton, QGroupBox {{ color: {FG}; font-size: {font_size}pt; }}
    QGroupBox {{
        border: 1px solid {BORDER}; border-radius: 4px;
        margin-top: 10px; padding-top: 8px;
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 8px; padding: 0 4px; }}
    QTableWidget {{
        background: {BG_INPUT}; color: {FG};
        gridline-color: {BORDER}; border: 1px solid {BORDER};
        font-size: {font_size}pt;
    }}
    QHeaderView::section {{
        background: {BG_HEADER}; color: {FG_DIM};
        border: none; border-bottom: 1px solid {BORDER}; padding: 4px;
    }}
    QDialog {{ background: {BG}; }}
    QTabWidget::pane {{
        background: {BG};
        border: 1px solid {BORDER};
        border-radius: 4px;
        top: -1px;
    }}
    QTabWidget > QWidget {{ background: {BG}; }}
    QTabBar::tab {{
        background: {BG_HEADER};
        color: {FG_DIM};
        border: 1px solid {BORDER};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        padding: 6px 14px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{ background: {BG}; color: {FG}; }}
    QTabBar::tab:hover {{ color: {FG}; }}
    QCheckBox:disabled, QRadioButton:disabled, QLabel:disabled {{ color: #6b7280; }}
    QSpinBox:disabled, QDateEdit:disabled, QComboBox:disabled, QLineEdit:disabled {{
        color: #5b6472; background: #20242c;
    }}
    QSlider::groove:horizontal {{
        background: {BG_INPUT}; height: 4px; border-radius: 2px;
    }}
    QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
    QSlider::handle:horizontal {{
        background: {FG}; width: 12px; height: 12px;
        margin: -5px 0; border-radius: 6px;
    }}
    QToolTip {{
        background: {BG_INPUT}; color: {FG};
        border: 1px solid {BORDER}; padding: 3px;
    }}
    """
