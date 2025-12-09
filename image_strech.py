import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QScrollArea, QSpinBox)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QPoint, QEvent

class ImageCanvas(QWidget):
    def __init__(self):
        super().__init__()
        self.image = None  # QImage
        self.cv_image = None # numpy array (RGB)
        self.points = []
        self.selecting_mode = False
        self.scale_factor = 1.0
        self.scroll_area = None
        self.target_width = 300
        self.target_height = 300
        self.setMinimumSize(400, 400)

    def set_target_resolution(self, width, height):
        self.target_width = width
        self.target_height = height

    def set_scroll_area(self, scroll_area):
        self.scroll_area = scroll_area

    def load_image(self, file_path):
        # Load image using OpenCV
        img = cv2.imread(file_path)
        if img is not None:
            # Convert BGR to RGB
            self.cv_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            self.scale_factor = 1.0
            self.update_image_from_cv()
            self.points = []
            self.selecting_mode = False
            self.update()
        else:
            QMessageBox.critical(self, "Error", "Failed to load image.")

    def update_image_from_cv(self):
        if self.cv_image is None:
            return
        height, width, channel = self.cv_image.shape
        bytes_per_line = 3 * width
        # Create QImage from numpy array
        self.image = QImage(self.cv_image.data, width, height, bytes_per_line, QImage.Format_RGB888)
        # Resize widget to match image size with scale
        self.setFixedSize(int(width * self.scale_factor), int(height * self.scale_factor))
        self.update()

    def start_stretch_selection(self):
        if self.image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return
        self.selecting_mode = True
        self.points = []
        self.update()

    def mousePressEvent(self, event):
        if self.selecting_mode and self.image:
            pos = event.pos()
            # Convert to image coordinates
            img_x = pos.x() / self.scale_factor
            img_y = pos.y() / self.scale_factor
            
            # Ensure point is within image bounds
            if 0 <= img_x < self.image.width() and 0 <= img_y < self.image.height():
                self.points.append((img_x, img_y))
                self.update()
                
                if len(self.points) == 4:
                    self.perform_stretch()
                    self.selecting_mode = False

    def perform_stretch(self):
        if len(self.points) != 4:
            return

        pts = np.array(self.points, dtype="float32")
        
        # Sort points to order: top-left, top-right, bottom-right, bottom-left
        rect = np.zeros((4, 2), dtype="float32")
        
        # Top-left will have the smallest sum, bottom-right will have the largest sum
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        
        # Top-right will have the smallest difference, bottom-left will have the largest difference
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]
        
        # Destination points for target resolution
        w = self.target_width
        h = self.target_height
        dst = np.array([
            [0, 0],
            [w, 0],
            [w, h],
            [0, h]], dtype="float32")
            
        # Compute the perspective transform matrix and apply it
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(self.cv_image, M, (w, h))
        
        self.cv_image = warped
        self.scale_factor = 1.0 # Reset zoom after stretch
        self.update_image_from_cv()
        self.points = []
        QMessageBox.information(self, "Success", f"Image stretched to {w}x{h} pixels.")

    def handle_zoom(self, event, viewport_pos):
        if self.image:
            old_scale = self.scale_factor
            
            # Get current scrollbar values
            old_scroll_x = self.scroll_area.horizontalScrollBar().value()
            old_scroll_y = self.scroll_area.verticalScrollBar().value()

            delta = event.angleDelta().y()
            if delta > 0:
                new_scale = old_scale * 1.1
            else:
                new_scale = old_scale * 0.9
            
            # Limit zoom
            new_scale = max(0.1, min(new_scale, 10.0))
            
            self.scale_factor = new_scale
            self.update_image_from_cv()

            # Adjust scrollbars to zoom towards cursor
            if self.scroll_area:
                # viewport_pos is relative to the viewport
                # We need the position relative to the content (canvas) BEFORE the zoom
                # But since we just resized, the canvas coordinates have changed.
                
                # Let's use the viewport position directly.
                # The point under the cursor in the viewport should remain under the cursor.
                # Viewport X = (Content X - Scroll X)
                # Content X = Viewport X + Scroll X
                
                # We want: (New Content X - New Scroll X) = Viewport X
                # New Scroll X = New Content X - Viewport X
                
                # New Content X = Old Content X * (new_scale / old_scale)
                # Old Content X = Viewport X + Old Scroll X
                
                scale_ratio = new_scale / old_scale
                
                mouse_x_viewport = viewport_pos.x()
                mouse_y_viewport = viewport_pos.y()
                
                old_content_x = mouse_x_viewport + old_scroll_x
                old_content_y = mouse_y_viewport + old_scroll_y
                
                new_content_x = old_content_x * scale_ratio
                new_content_y = old_content_y * scale_ratio
                
                new_scroll_x = new_content_x - mouse_x_viewport
                new_scroll_y = new_content_y - mouse_y_viewport
                
                self.scroll_area.horizontalScrollBar().setValue(int(new_scroll_x))
                self.scroll_area.verticalScrollBar().setValue(int(new_scroll_y))

    def wheelEvent(self, event):
        # This might not be called if ScrollArea intercepts it, 
        # but we keep it for cases where it is called.
        # We'll use the event filter in MainWindow to ensure it works.
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.image:
            # Draw image scaled
            target_rect = self.rect()
            painter.drawImage(target_rect, self.image)
        
        # Draw selection points and lines
        if self.selecting_mode and self.points:
            painter.scale(self.scale_factor, self.scale_factor)
            painter.setPen(QPen(Qt.red, 8))
            for pt in self.points:
                painter.drawPoint(int(pt[0]), int(pt[1]))
            
            if len(self.points) > 1:
                painter.setPen(QPen(Qt.yellow, 2))
                for i in range(len(self.points) - 1):
                    painter.drawLine(int(self.points[i][0]), int(self.points[i][1]), 
                                     int(self.points[i+1][0]), int(self.points[i+1][1]))
                # Close the loop if 4 points (though it processes immediately)
                if len(self.points) == 4:
                     painter.drawLine(int(self.points[3][0]), int(self.points[3][1]), 
                                     int(self.points[0][0]), int(self.points[0][1]))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Stretch Editor")
        self.resize(800, 600)
        
        self.canvas = ImageCanvas()
        
        # Scroll area for the canvas
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.canvas)
        self.scroll_area.setWidgetResizable(False) # Honor the widget's size (important for scrolling large images)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        
        # Pass scroll area to canvas for zoom handling
        self.canvas.set_scroll_area(self.scroll_area)
        
        # Install event filter to capture wheel events for zooming
        self.scroll_area.viewport().installEventFilter(self)

        # Layouts
        main_layout = QHBoxLayout()
        sidebar_layout = QVBoxLayout()
        
        # Buttons
        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self.load_image)
        
        stretch_btn = QPushButton("Stretch")
        stretch_btn.clicked.connect(self.canvas.start_stretch_selection)
        stretch_btn.setToolTip("Click 4 points on the image to define corners")
        
        save_btn = QPushButton("Save Image")
        save_btn.clicked.connect(self.save_image)
        
        # Resolution inputs
        self.width_spin = QSpinBox()
        self.width_spin.setRange(1, 10000)
        self.width_spin.setValue(300)
        self.width_spin.setSuffix(" px")
        self.width_spin.setToolTip("Target Width")
        self.width_spin.valueChanged.connect(self.update_resolution)
        
        self.height_spin = QSpinBox()
        self.height_spin.setRange(1, 10000)
        self.height_spin.setValue(300)
        self.height_spin.setSuffix(" px")
        self.height_spin.setToolTip("Target Height")
        self.height_spin.valueChanged.connect(self.update_resolution)

        # Add widgets to sidebar
        sidebar_layout.addWidget(load_btn)
        sidebar_layout.addWidget(stretch_btn)
        sidebar_layout.addWidget(save_btn)
        
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(QLabel("Target Size:"))
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("x"))
        size_layout.addWidget(self.height_spin)
        sidebar_layout.addLayout(size_layout)
        
        sidebar_layout.addStretch() # Push items to top

        # Add sidebar and scroll area to main layout
        main_layout.addLayout(sidebar_layout)
        main_layout.addWidget(self.scroll_area)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def update_resolution(self):
        self.canvas.set_target_resolution(self.width_spin.value(), self.height_spin.value())

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.canvas.load_image(path)

    def save_image(self):
        if self.canvas.image is None:
            QMessageBox.warning(self, "Warning", "No image to save.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Save Image", "stretched.png", "Images (*.png *.jpg *.jpeg *.bmp)")
        if path:
            self.canvas.image.save(path)

    def eventFilter(self, source, event):
        if source == self.scroll_area.viewport() and event.type() == QEvent.Wheel:
            self.canvas.handle_zoom(event, event.pos())
            return True
        return super().eventFilter(source, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
