# Empyrion Scenario Editor
# Copyright (C) 2026  Daflo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Apercu INTEGRE des fichiers non editables (OPEN-009, v1.6.1) : images (png,
jpg, jpeg, bmp, gif, webp, tif, tiff, ico) et PDF (si le module optionnel
PyQt6-QtPdf est installe). Lecture seule, aucun risque d'ecriture. Les
formats sans parseur ni visionneuse (binaires du jeu, .dds textures, modeles
3D...) restent refuses avec le message existant -- comportement voulu.
"""
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QSizePolicy,
)

from core.i18n import t

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp',
                    '.tif', '.tiff', '.ico'}


def can_preview(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTENSIONS:
        return True
    if ext == '.pdf':
        try:
            from PyQt6.QtPdf import QPdfDocument  # noqa: F401
            return True
        except ImportError:
            return False
    return False


class ImagePreviewWidget(QWidget):
    """Apercu d'image a l'echelle 1:1 avec barres de defilement (les icones
    de blocs font souvent 64-128 px, les textures peuvent etre enormes)."""

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.label.setText(t("preview.image_error", name=path.name))
        else:
            self.label.setPixmap(pixmap)
            self.label.setMinimumSize(1, 1)
        scroll = QScrollArea()
        scroll.setWidget(self.label)
        scroll.setWidgetResizable(False)
        scroll.setBackgroundRole(QColor("#2b2b2b"))
        layout.addWidget(scroll)
        size_text = (f"{pixmap.width()} x {pixmap.height()}" if not pixmap.isNull() else "?")
        info = QLabel(t("preview.image_info", name=path.name, size=size_text))
        info.setObjectName("mutedLabel")
        layout.addWidget(info)


class PdfPreviewWidget(QWidget):
    """Apercu PDF page a page (module optionnel PyQt6-QtPdf). Navigation par
    boutons, rendu dans un QLabel pixmap."""

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        from PyQt6.QtPdf import QPdfDocument
        from PyQt6.QtPdfWidgets import QPdfView
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._doc = QPdfDocument(self)
        self._error = self._doc.load(str(path))
        view = QPdfView(self)
        view.setDocument(self._doc)
        view.setPageMode(QPdfView.PageMode.MultiPage)
        view.setZoomMode(QPdfView.ZoomMode.FitToWidth)
        layout.addWidget(view)


class UnsupportedPreviewWidget(QWidget):
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel(t("preview.unsupported", name=path.name))
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
