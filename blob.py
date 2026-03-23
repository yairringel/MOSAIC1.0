"""
blob.py — Mosaic Blob Detector
Workflow: Load image → Preprocess → Edge/Threshold → Morphology → Find Contours
          → Approximate Polygons → Filter → Sample Color → Export CSV
"""
import sys
import csv
import numpy as np
import cv2
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QScrollArea, QSpinBox, QDoubleSpinBox, QGroupBox,
    QFormLayout, QCheckBox, QComboBox, QSplitter
)
from PyQt5.QtGui import (
    QImage, QPainter, QPen, QColor, QBrush, QPolygonF
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QEvent, pyqtSignal


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

class BlobCanvas(QWidget):
    """Displays the image with detected contour overlays. Click to select/delete."""

    contour_selected = pyqtSignal(int)   # -1 = deselected

    def __init__(self):
        super().__init__()
        self.cv_image = None          # Original RGB image (numpy)
        self.processed_image = None   # Binary/edge image shown in 'processed' view
        self.approx_contours = []     # List of approxPolyDP results
        self.raw_contours = []        # Corresponding raw contours (for area/color)
        self.contour_colors = []      # (r, g, b) mean color per contour
        self.contour_centroids = []   # (cx, cy) per contour
        self.deleted_indices = set()
        self.selected_index = None
        self.scale_factor = 1.0
        self.scroll_area = None
        self.view_mode = 'overlay'    # 'overlay' | 'original' | 'processed'

        self.setMinimumSize(400, 400)
        self.setFocusPolicy(Qt.StrongFocus)

    def set_scroll_area(self, sa):
        self.scroll_area = sa

    # ------------------------------------------------------------------
    # Data setters
    # ------------------------------------------------------------------

    def load_image(self, path):
        img = cv2.imread(path)
        if img is None:
            return False
        self.cv_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        self.processed_image = None
        self._reset_contours()
        self.scale_factor = 1.0
        self._update_size()
        self.update()
        return True

    def _reset_contours(self):
        self.approx_contours = []
        self.raw_contours = []
        self.contour_colors = []
        self.contour_centroids = []
        self.deleted_indices = set()
        self.selected_index = None

    def set_processed(self, processed):
        self.processed_image = processed
        self.update()

    def set_contours(self, raw, approx, colors, centroids):
        self.raw_contours = raw
        self.approx_contours = approx
        self.contour_colors = colors
        self.contour_centroids = centroids
        self.deleted_indices = set()
        self.selected_index = None
        self.update()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def visible_count(self):
        return sum(1 for i in range(len(self.approx_contours))
                   if i not in self.deleted_indices)

    def get_visible_entries(self):
        """Return list of (approx_contour, color, centroid) for non-deleted entries."""
        return [
            (self.approx_contours[i], self.contour_colors[i], self.contour_centroids[i])
            for i in range(len(self.approx_contours))
            if i not in self.deleted_indices
        ]

    def _update_size(self):
        if self.cv_image is None:
            return
        h, w = self.cv_image.shape[:2]
        self.setFixedSize(int(w * self.scale_factor), int(h * self.scale_factor))

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if self.cv_image is None or not self.approx_contours:
            return
        img_x = event.x() / self.scale_factor
        img_y = event.y() / self.scale_factor

        hit = -1
        # Iterate in reverse so topmost-drawn contour wins
        for i in range(len(self.approx_contours) - 1, -1, -1):
            if i in self.deleted_indices:
                continue
            pts = self.approx_contours[i].reshape(-1, 2).astype(np.float32)
            if cv2.pointPolygonTest(pts, (img_x, img_y), False) >= 0:
                hit = i
                break

        self.selected_index = hit if hit >= 0 else None
        self.contour_selected.emit(hit)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and self.selected_index is not None:
            self.deleted_indices.add(self.selected_index)
            self.selected_index = None
            self.contour_selected.emit(-1)
            self.update()
        elif event.key() == Qt.Key_Escape:
            self.selected_index = None
            self.contour_selected.emit(-1)
            self.update()

    def handle_zoom(self, event, viewport_pos):
        if self.cv_image is None:
            return
        old_scale = self.scale_factor
        delta = event.angleDelta().y()
        new_scale = max(0.05, min(old_scale * (1.1 if delta > 0 else 0.9), 15.0))
        self.scale_factor = new_scale
        self._update_size()
        if self.scroll_area:
            ratio = new_scale / old_scale
            ox, oy = viewport_pos.x(), viewport_pos.y()
            sb_h = self.scroll_area.horizontalScrollBar()
            sb_v = self.scroll_area.verticalScrollBar()
            sb_h.setValue(int((ox + sb_h.value()) * ratio - ox))
            sb_v.setValue(int((oy + sb_v.value()) * ratio - oy))

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.cv_image is None:
            painter.fillRect(self.rect(), QColor(40, 40, 40))
            painter.setPen(Qt.white)
            painter.drawText(self.rect(), Qt.AlignCenter, "Load an image to begin")
            return

        h, w = self.cv_image.shape[:2]
        target = QRectF(0, 0, w * self.scale_factor, h * self.scale_factor)

        # Base image
        if self.view_mode == 'processed' and self.processed_image is not None:
            proc = self.processed_image
            if proc.ndim == 2:
                proc = cv2.cvtColor(proc, cv2.COLOR_GRAY2RGB)
            qi = QImage(proc.data, w, h, 3 * w, QImage.Format_RGB888)
        else:
            qi = QImage(self.cv_image.data, w, h, 3 * w, QImage.Format_RGB888)
        painter.drawImage(target, qi)

        # Contour overlays (shown in overlay and original modes)
        if self.approx_contours and self.view_mode in ('overlay', 'original'):
            painter.save()
            painter.scale(self.scale_factor, self.scale_factor)
            for idx, approx in enumerate(self.approx_contours):
                if idx in self.deleted_indices:
                    continue
                pts = approx.reshape(-1, 2)
                selected = (idx == self.selected_index)
                pen_w = (2.5 if selected else 1.2) / self.scale_factor

                if selected:
                    pen_color = QColor(255, 60, 60)
                    fill_color = QColor(255, 60, 60, 45)
                else:
                    pen_color = QColor(0, 220, 120)
                    fill_color = QColor(0, 220, 120, 25)

                painter.setPen(QPen(pen_color, pen_w))
                painter.setBrush(QBrush(fill_color))

                poly = QPolygonF([QPointF(float(p[0]), float(p[1])) for p in pts])
                painter.drawPolygon(poly)

                # Centroid dot
                if idx < len(self.contour_centroids):
                    cx, cy = self.contour_centroids[idx]
                    dot = 4.0 / self.scale_factor
                    painter.setPen(QPen(QColor(255, 230, 0), 1.0 / self.scale_factor))
                    painter.setBrush(QBrush(QColor(255, 230, 0)))
                    painter.drawEllipse(QPointF(cx, cy), dot, dot)

            painter.restore()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mosaic Blob Detector")
        self.resize(1300, 850)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)

        # ---- Canvas side ----
        canvas_container = QWidget()
        canvas_vbox = QVBoxLayout(canvas_container)
        canvas_vbox.setContentsMargins(0, 0, 0, 0)

        view_row = QHBoxLayout()
        view_row.addWidget(QLabel("View:"))
        self.view_combo = QComboBox()
        self.view_combo.addItems(["Overlay", "Original", "Processed"])
        self.view_combo.currentIndexChanged.connect(self._change_view)
        view_row.addWidget(self.view_combo)
        view_row.addStretch()
        canvas_vbox.addLayout(view_row)

        self.canvas = BlobCanvas()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.canvas.set_scroll_area(self.scroll_area)
        self.scroll_area.viewport().installEventFilter(self)
        canvas_vbox.addWidget(self.scroll_area)
        self.canvas.contour_selected.connect(self._on_contour_selected)

        splitter.addWidget(canvas_container)

        # ---- Right panel ----
        right = QWidget()
        right.setFixedWidth(330)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 6, 6, 6)

        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self.load_image)
        rl.addWidget(load_btn)

        self.detect_btn = QPushButton("Detect Blobs")
        self.detect_btn.setStyleSheet("font-weight:bold; background:#1e6fc7; color:white;")
        self.detect_btn.clicked.connect(self.run_detection)
        rl.addWidget(self.detect_btn)

        self.live_check = QCheckBox("Live Update")
        rl.addWidget(self.live_check)
        rl.addSpacing(6)

        # 1. Preprocessing
        pre = QGroupBox("1. Preprocessing")
        pfl = QFormLayout()

        self.blur_spin = QSpinBox()
        self.blur_spin.setRange(0, 51)
        self.blur_spin.setSingleStep(2)
        self.blur_spin.setValue(3)
        self.blur_spin.setToolTip("Gaussian blur kernel (0 = off). Must be odd — auto-corrected.")
        pfl.addRow("Gaussian Blur:", self.blur_spin)

        self.thresh_combo = QComboBox()
        self.thresh_combo.addItems(["Otsu", "Binary", "Adaptive Mean", "Adaptive Gaussian"])
        pfl.addRow("Threshold:", self.thresh_combo)

        self.thresh_val = QSpinBox()
        self.thresh_val.setRange(0, 255)
        self.thresh_val.setValue(127)
        self.thresh_val.setToolTip("Manual threshold value (Binary mode only)")
        pfl.addRow("Thresh Value:", self.thresh_val)

        self.invert_check = QCheckBox("Invert  (white stones, dark grout)")
        self.invert_check.setChecked(True)
        pfl.addRow("", self.invert_check)

        pre.setLayout(pfl)
        rl.addWidget(pre)

        # 2. Edge Detection
        edge = QGroupBox("2. Edge Detection (Canny)")
        efl = QFormLayout()

        self.canny_check = QCheckBox("Use Canny instead of threshold")
        efl.addRow("", self.canny_check)

        self.canny_low = QSpinBox()
        self.canny_low.setRange(0, 500)
        self.canny_low.setValue(50)
        efl.addRow("Low Threshold:", self.canny_low)

        self.canny_high = QSpinBox()
        self.canny_high.setRange(0, 500)
        self.canny_high.setValue(150)
        efl.addRow("High Threshold:", self.canny_high)

        edge.setLayout(efl)
        rl.addWidget(edge)

        # 3. Morphology
        morph = QGroupBox("3. Morphology")
        mfl = QFormLayout()

        self.morph_combo = QComboBox()
        self.morph_combo.addItems(["None", "Close", "Open", "Dilate", "Erode"])
        mfl.addRow("Operation:", self.morph_combo)

        self.morph_size = QSpinBox()
        self.morph_size.setRange(1, 51)
        self.morph_size.setSingleStep(2)
        self.morph_size.setValue(3)
        mfl.addRow("Kernel Size:", self.morph_size)

        self.morph_iters = QSpinBox()
        self.morph_iters.setRange(1, 20)
        self.morph_iters.setValue(1)
        mfl.addRow("Iterations:", self.morph_iters)

        morph.setLayout(mfl)
        rl.addWidget(morph)

        # 4. Contour Filters
        filt = QGroupBox("4. Contour Filters")
        ffl = QFormLayout()

        self.min_area = QSpinBox()
        self.min_area.setRange(0, 10_000_000)
        self.min_area.setValue(300)
        self.min_area.setSingleStep(100)
        ffl.addRow("Min Area (px²):", self.min_area)

        self.max_area = QSpinBox()
        self.max_area.setRange(0, 100_000_000)
        self.max_area.setValue(1_000_000)
        self.max_area.setSingleStep(1000)
        ffl.addRow("Max Area (px²):", self.max_area)

        self.min_circ = QDoubleSpinBox()
        self.min_circ.setRange(0.0, 1.0)
        self.min_circ.setSingleStep(0.05)
        self.min_circ.setDecimals(2)
        self.min_circ.setValue(0.0)
        self.min_circ.setToolTip("Circularity = 4π·area / perimeter².  1.0 = perfect circle.")
        ffl.addRow("Min Circularity:", self.min_circ)

        filt.setLayout(ffl)
        rl.addWidget(filt)

        # 5. Polygon Approximation
        apx = QGroupBox("5. Polygon Approximation")
        afl = QFormLayout()

        self.epsilon_spin = QDoubleSpinBox()
        self.epsilon_spin.setRange(0.001, 0.5)
        self.epsilon_spin.setSingleStep(0.005)
        self.epsilon_spin.setDecimals(3)
        self.epsilon_spin.setValue(0.02)
        self.epsilon_spin.setToolTip(
            "Douglas-Peucker epsilon as fraction of perimeter.\n"
            "Higher = fewer vertices, coarser shape."
        )
        afl.addRow("DP Epsilon:", self.epsilon_spin)

        self.max_pts = QSpinBox()
        self.max_pts.setRange(3, 500)
        self.max_pts.setValue(40)
        self.max_pts.setToolTip("Contours with more vertices than this are discarded.")
        afl.addRow("Max Vertices:", self.max_pts)

        self.convex_check = QCheckBox("Force Convex Hull")
        afl.addRow("", self.convex_check)

        apx.setLayout(afl)
        rl.addWidget(apx)

        # Status
        rl.addSpacing(8)
        self.status_lbl = QLabel("No image loaded.")
        self.status_lbl.setWordWrap(True)
        rl.addWidget(self.status_lbl)

        rl.addSpacing(8)
        self.export_btn = QPushButton("Export Polygons to CSV")
        self.export_btn.setStyleSheet("font-weight:bold;")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self.export_csv)
        rl.addWidget(self.export_btn)

        rl.addStretch()
        splitter.addWidget(right)

        self.setCentralWidget(splitter)

        # Connect live-update signals
        live_widgets = [
            self.blur_spin, self.thresh_combo, self.thresh_val,
            self.invert_check, self.canny_check, self.canny_low, self.canny_high,
            self.morph_combo, self.morph_size, self.morph_iters,
            self.min_area, self.max_area, self.min_circ,
            self.epsilon_spin, self.max_pts, self.convex_check,
        ]
        for w in live_widgets:
            if hasattr(w, 'valueChanged'):
                w.valueChanged.connect(self._maybe_live)
            elif hasattr(w, 'currentIndexChanged'):
                w.currentIndexChanged.connect(self._maybe_live)
            elif hasattr(w, 'stateChanged'):
                w.stateChanged.connect(self._maybe_live)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _maybe_live(self, *_):
        if self.live_check.isChecked() and self.canvas.cv_image is not None:
            self.run_detection()

    def _change_view(self, idx):
        self.canvas.view_mode = ['overlay', 'original', 'processed'][idx]
        self.canvas.update()

    def _on_contour_selected(self, idx):
        if idx >= 0 and idx < len(self.canvas.approx_contours):
            area = cv2.contourArea(self.canvas.approx_contours[idx])
            cx, cy = self.canvas.contour_centroids[idx]
            r, g, b = self.canvas.contour_colors[idx]
            verts = len(self.canvas.approx_contours[idx])
            self.status_lbl.setText(
                f"Selected contour #{idx}\n"
                f"Area: {area:.0f} px²\n"
                f"Centroid: ({cx:.0f}, {cy:.0f})\n"
                f"Avg color: rgb({r}, {g}, {b})\n"
                f"Vertices: {verts}\n"
                "[Delete] to remove"
            )
        else:
            count = self.canvas.visible_count()
            self.status_lbl.setText(f"{count} blobs visible.\nClick a blob to inspect.")

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        if path:
            if self.canvas.load_image(path):
                self.status_lbl.setText("Image loaded. Click 'Detect Blobs'.")
                self.export_btn.setEnabled(False)
            else:
                QMessageBox.critical(self, "Error", "Failed to load image.")

    # ------------------------------------------------------------------
    # Detection pipeline
    # ------------------------------------------------------------------

    def run_detection(self):
        if self.canvas.cv_image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return

        self.detect_btn.setEnabled(False)
        self.detect_btn.setText("Detecting…")
        QApplication.processEvents()

        img = self.canvas.cv_image  # RGB numpy array
        h, w = img.shape[:2]

        # ---- Step 1: Grayscale + Blur ----
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

        blur_k = self.blur_spin.value()
        if blur_k > 0:
            if blur_k % 2 == 0:
                blur_k += 1
            gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0)

        # ---- Step 2: Threshold / Canny ----
        if self.canny_check.isChecked():
            binary = cv2.Canny(gray, self.canny_low.value(), self.canny_high.value())
        else:
            mode = self.thresh_combo.currentText()
            if mode == "Otsu":
                _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            elif mode == "Binary":
                _, binary = cv2.threshold(gray, self.thresh_val.value(), 255, cv2.THRESH_BINARY)
            elif mode == "Adaptive Mean":
                binary = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
            else:  # Adaptive Gaussian
                binary = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        if self.invert_check.isChecked():
            binary = cv2.bitwise_not(binary)

        # ---- Step 3: Morphology ----
        morph_op = self.morph_combo.currentText()
        if morph_op != "None":
            k = self.morph_size.value()
            if k % 2 == 0:
                k += 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
            op_map = {
                "Close": cv2.MORPH_CLOSE,
                "Open":  cv2.MORPH_OPEN,
                "Dilate": cv2.MORPH_DILATE,
                "Erode":  cv2.MORPH_ERODE,
            }
            binary = cv2.morphologyEx(
                binary, op_map[morph_op], kernel,
                iterations=self.morph_iters.value()
            )

        self.canvas.set_processed(binary)

        # ---- Step 4: Find contours ----
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        min_area   = self.min_area.value()
        max_area   = self.max_area.value()
        min_circ   = self.min_circ.value()
        eps_frac   = self.epsilon_spin.value()
        max_pts    = self.max_pts.value()
        use_convex = self.convex_check.isChecked()

        raw_valid, approx_valid, colors, centroids = [], [], [], []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area or area > max_area:
                continue

            perimeter = cv2.arcLength(cnt, True)
            if perimeter <= 0:
                continue

            # Circularity filter  (4π·A / P²)
            circularity = (4.0 * np.pi * area) / (perimeter ** 2)
            if circularity < min_circ:
                continue

            # Douglas-Peucker approximation
            approx = cv2.approxPolyDP(cnt, eps_frac * perimeter, True)
            if use_convex:
                approx = cv2.convexHull(approx)
            if len(approx) < 3 or len(approx) > max_pts:
                continue

            # Centroid via image moments
            M = cv2.moments(cnt)
            if M['m00'] == 0:
                continue
            cx = M['m10'] / M['m00']
            cy = M['m01'] / M['m00']

            # Average color inside the contour mask
            mask = np.zeros((h, w), dtype=np.uint8)
            cv2.drawContours(mask, [cnt], -1, 255, -1)
            mean_c = cv2.mean(img, mask=mask)
            r, g, b = int(mean_c[0]), int(mean_c[1]), int(mean_c[2])

            raw_valid.append(cnt)
            approx_valid.append(approx)
            colors.append((r, g, b))
            centroids.append((cx, cy))

        self.canvas.set_contours(raw_valid, approx_valid, colors, centroids)

        count = len(approx_valid)
        self.status_lbl.setText(
            f"{count} blobs detected.\n"
            "Click a blob to inspect.\n"
            "[Delete] to remove selected."
        )
        self.export_btn.setEnabled(count > 0)
        self.detect_btn.setEnabled(True)
        self.detect_btn.setText("Detect Blobs")

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self):
        entries = self.canvas.get_visible_entries()
        if not entries:
            QMessageBox.warning(self, "Warning", "No blobs to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "blobs.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Same column layout as image_strech.py, plus centroid/area columns
                writer.writerow([
                    'polygon_id', 'coordinates',
                    'color_r', 'color_g', 'color_b', 'color_a',
                    'frame_r', 'frame_g', 'frame_b', 'frame_a',
                    'group_id', 'centroid_x', 'centroid_y', 'area'
                ])
                for poly_id, (approx, color, centroid) in enumerate(entries):
                    pts = approx.reshape(-1, 2)
                    coords_str = ';'.join(f"{int(p[0])},{int(p[1])}" for p in pts)
                    r, g, b = color
                    cx, cy = centroid
                    area = cv2.contourArea(approx)
                    writer.writerow([
                        poly_id, coords_str,
                        r, g, b, 255,
                        0, 0, 0, 255,
                        0,
                        f"{cx:.1f}", f"{cy:.1f}", f"{area:.1f}"
                    ])
            QMessageBox.information(
                self, "Success",
                f"Exported {len(entries)} polygons to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")

    # ------------------------------------------------------------------
    # Event filter (scroll-to-zoom)
    # ------------------------------------------------------------------

    def eventFilter(self, source, event):
        if source == self.scroll_area.viewport() and event.type() == QEvent.Wheel:
            self.canvas.handle_zoom(event, event.pos())
            return True
        return super().eventFilter(source, event)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())
