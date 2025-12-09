import sys
import cv2
import numpy as np
import copy
import pickle
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, QMessageBox, QScrollArea, QSpinBox,
                             QSlider, QGroupBox, QFormLayout, QColorDialog)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, pyqtSignal

class ImageCanvas(QWidget):
    selection_changed = pyqtSignal(int) # Emits index of selected polygon, or -1

    def __init__(self):
        super().__init__()
        self.image = None  # QImage
        self.cv_image = None # numpy array (RGB)
        self.display_image = None # numpy array (RGB) with effects applied
        self.points = []
        self.selecting_mode = False
        self.scale_factor = 1.0
        self.scroll_area = None
        self.target_width = 300
        self.target_height = 300
        self.polygons = []
        self.polygon_effects = [] # List of dicts for effects
        self.current_polygon = []
        self.drawing_polygon = False
        self.selected_polygon_index = None
        self.dragging_point_index = None
        self.setFocusPolicy(Qt.StrongFocus)
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
            self.display_image = self.cv_image.copy()
            self.scale_factor = 1.0
            self.update_image_from_cv()
            self.points = []
            self.polygons = []
            self.polygon_effects = []
            self.current_polygon = []
            self.selecting_mode = False
            self.drawing_polygon = False
            self.update()
        else:
            QMessageBox.critical(self, "Error", "Failed to load image.")

    def update_image_from_cv(self):
        if self.display_image is None:
            return
        height, width, channel = self.display_image.shape
        bytes_per_line = 3 * width;
        # Create QImage from numpy array
        self.image = QImage(self.display_image.data, width, height, bytes_per_line, QImage.Format_RGB888)
        # Resize widget to match image size with scale
        self.setFixedSize(int(width * self.scale_factor), int(height * self.scale_factor))
        self.update()

    def apply_effects(self):
        if self.cv_image is None:
            return

        self.display_image = self.cv_image.copy()
        
        for i, poly in enumerate(self.polygons):
            if i >= len(self.polygon_effects):
                continue
                
            effects = self.polygon_effects[i]
            
            # Create mask for polygon
            mask = np.zeros(self.cv_image.shape[:2], dtype=np.uint8)
            pts = np.array(poly, dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
            
            # Extract ROI
            # We can optimize by bounding rect, but for now full image masking is easier to implement
            
            # 1. Brightness and Contrast
            # alpha = contrast (1.0 is original), beta = brightness (0 is original)
            alpha = effects.get('contrast', 1.0)
            beta = effects.get('brightness', 0)
            
            # 2. Saturation
            sat_scale = effects.get('saturation', 1.0)
            
            # 3. Warmth (Temperature)
            warmth = effects.get('warmth', 0)

            # 4. Tint
            tint_color = effects.get('tint_color', (255, 255, 255)) # RGB
            tint_strength = effects.get('tint_strength', 0) / 100.0 # 0.0 to 1.0
            
            # Apply to the whole image (or ROI) then mask copy back
            # To avoid processing full image, let's crop to bounding rect
            x, y, w, h = cv2.boundingRect(pts)
            roi = self.display_image[y:y+h, x:x+w].astype(np.float32)
            roi_mask = mask[y:y+h, x:x+w]
            
            # Only process if mask is not empty
            if np.sum(roi_mask) > 0:
                # Brightness/Contrast
                roi = roi * alpha + beta
                roi = np.clip(roi, 0, 255)
                
                # Saturation
                if sat_scale != 1.0:
                    roi_hsv = cv2.cvtColor(roi.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
                    roi_hsv[:, :, 1] *= sat_scale
                    roi_hsv[:, :, 1] = np.clip(roi_hsv[:, :, 1], 0, 255)
                    roi = cv2.cvtColor(roi_hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)

                # Warmth (R increases, B decreases)
                if warmth != 0:
                    # R channel is 0, B is 2 in RGB
                    r = roi[:, :, 0]
                    b = roi[:, :, 2]
                    
                    r += warmth
                    b -= warmth
                    
                    roi[:, :, 0] = np.clip(r, 0, 255)
                    roi[:, :, 2] = np.clip(b, 0, 255)

                # Tint
                if tint_strength > 0:
                    # Create a solid color layer
                    tint_layer = np.full_like(roi, tint_color, dtype=np.float32)
                    # Blend
                    roi = cv2.addWeighted(roi, 1.0 - tint_strength, tint_layer, tint_strength, 0)

                # Blend back
                roi = roi.astype(np.uint8)
                
                # Use mask to copy only polygon area
                # We need 3-channel mask
                roi_mask_3 = cv2.merge([roi_mask, roi_mask, roi_mask])
                
                # Where mask is set, use processed ROI, else use original (which is already in display_image)
                # Actually we are modifying display_image in place
                current_roi = self.display_image[y:y+h, x:x+w]
                np.copyto(current_roi, roi, where=roi_mask_3.astype(bool))

        self.update_image_from_cv()

    def start_stretch_selection(self):
        if self.image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return
        self.selecting_mode = True
        self.drawing_polygon = False
        self.points = []
        self.update()

    def start_polygon_drawing(self):
        if self.image is None:
            QMessageBox.warning(self, "Warning", "Please load an image first.")
            return False
        self.drawing_polygon = True
        self.selecting_mode = False
        self.current_polygon = []
        self.update()
        return True

    def stop_polygon_drawing(self):
        self.drawing_polygon = False
        self.current_polygon = []
        self.update()

    def mousePressEvent(self, event):
        if self.image:
            pos = event.pos()
            # Convert to image coordinates
            img_x = pos.x() / self.scale_factor
            img_y = pos.y() / self.scale_factor
            
            # Ensure point is within image bounds (allow slightly outside for editing handles)
            if 0 <= img_x < self.image.width() and 0 <= img_y < self.image.height() or (not self.selecting_mode and not self.drawing_polygon):
                
                if self.selecting_mode:
                    self.points.append((img_x, img_y))
                    self.update()
                    
                    if len(self.points) == 4:
                        self.perform_stretch()
                        self.selecting_mode = False
                
                elif self.drawing_polygon:
                    if event.button() == Qt.LeftButton:
                        self.current_polygon.append((img_x, img_y))
                        self.update()
                    elif event.button() == Qt.RightButton:
                        if len(self.current_polygon) > 2:
                            self.polygons.append(self.current_polygon)
                            # Add default effects for new polygon
                            self.polygon_effects.append({
                                'brightness': 0,
                                'contrast': 1.0,
                                'saturation': 1.0,
                                'warmth': 0,
                                'tint_color': (255, 255, 255),
                                'tint_strength': 0
                            })
                            self.current_polygon = []
                            # self.drawing_polygon = False # Keep drawing mode active
                            self.update()
                        else:
                            # Maybe cancel if not enough points? Or just ignore
                            pass
                else:
                    # Edit mode
                    self.handle_edit_click(img_x, img_y)

    def handle_edit_click(self, img_x, img_y):
        hit_radius = 10 / self.scale_factor
        found_hit = False
        old_selection = self.selected_polygon_index
        
        # 1. Check vertices of currently selected polygon
        if self.selected_polygon_index is not None:
            poly = self.polygons[self.selected_polygon_index]
            for i, pt in enumerate(poly):
                if (pt[0] - img_x)**2 + (pt[1] - img_y)**2 < hit_radius**2:
                    self.dragging_point_index = i
                    found_hit = True
                    break
        
        # 2. Check vertices of all polygons (switch selection)
        if not found_hit:
            for p_idx, poly in enumerate(self.polygons):
                for i, pt in enumerate(poly):
                    if (pt[0] - img_x)**2 + (pt[1] - img_y)**2 < hit_radius**2:
                        self.selected_polygon_index = p_idx
                        self.dragging_point_index = i
                        found_hit = True
                        break
                if found_hit: break
        
        # 3. Check inside polygons
        if not found_hit:
            for p_idx, poly in enumerate(self.polygons):
                pts_np = np.array(poly, dtype=np.int32)
                dist = cv2.pointPolygonTest(pts_np, (img_x, img_y), False)
                if dist >= 0:
                    self.selected_polygon_index = p_idx
                    self.dragging_point_index = None
                    found_hit = True
                    break
        
        # 4. Deselect if clicked empty space
        if not found_hit:
            self.selected_polygon_index = None
            self.dragging_point_index = None
        
        if self.selected_polygon_index != old_selection:
            self.selection_changed.emit(self.selected_polygon_index if self.selected_polygon_index is not None else -1)

        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging_point_index is not None and self.selected_polygon_index is not None:
             pos = event.pos()
             img_x = pos.x() / self.scale_factor
             img_y = pos.y() / self.scale_factor
             
             # Update point
             self.polygons[self.selected_polygon_index][self.dragging_point_index] = (img_x, img_y)
             # Re-apply effects because polygon shape changed
             self.apply_effects()
             self.update()

    def mouseReleaseEvent(self, event):
        self.dragging_point_index = None

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.selected_polygon_index = None
            self.dragging_point_index = None
            self.selection_changed.emit(-1)
            self.update()

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
        self.display_image = self.cv_image.copy() # Update display image
        self.polygons = [] # Clear polygons as they don't match the new image
        self.polygon_effects = [] # Clear effects
        self.selected_polygon_index = None
        self.dragging_point_index = None
        self.selection_changed.emit(-1)
        
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
        painter.setRenderHint(QPainter.Antialiasing)
        if self.image:
            # Draw image scaled
            target_rect = self.rect()
            painter.drawImage(target_rect, self.image)
        
        painter.scale(self.scale_factor, self.scale_factor)

        # Draw completed polygons
        if self.polygons:
            for idx, poly in enumerate(self.polygons):
                # Highlight selected polygon
                if idx == self.selected_polygon_index:
                    painter.setPen(QPen(Qt.magenta, 1))
                else:
                    painter.setPen(QPen(Qt.green, 1))
                
                if len(poly) > 1:
                    for i in range(len(poly) - 1):
                        painter.drawLine(QPointF(poly[i][0], poly[i][1]), 
                                         QPointF(poly[i+1][0], poly[i+1][1]))
                    # Close loop
                    painter.drawLine(QPointF(poly[-1][0], poly[-1][1]), 
                                     QPointF(poly[0][0], poly[0][1]))
                
                # Draw control points for selected polygon
                if idx == self.selected_polygon_index:
                    painter.setPen(QPen(Qt.magenta, 8))
                    for pt in poly:
                        painter.drawPoint(QPointF(pt[0], pt[1]))

        # Draw current polygon being drawn
        if self.drawing_polygon and self.current_polygon:
            painter.setPen(QPen(Qt.blue, 1))
            for i in range(len(self.current_polygon) - 1):
                painter.drawLine(QPointF(self.current_polygon[i][0], self.current_polygon[i][1]), 
                                 QPointF(self.current_polygon[i+1][0], self.current_polygon[i+1][1]))
            
            # Draw points
            painter.setPen(QPen(Qt.yellow, 5))
            for pt in self.current_polygon:
                painter.drawPoint(QPointF(pt[0], pt[1]))

        # Draw selection points and lines (Stretch mode)
        if self.selecting_mode and self.points:
            painter.setPen(QPen(Qt.red, 8))
            for pt in self.points:
                painter.drawPoint(QPointF(pt[0], pt[1]))
            
            if len(self.points) > 1:
                painter.setPen(QPen(Qt.yellow, 2))
                for i in range(len(self.points) - 1):
                    painter.drawLine(QPointF(self.points[i][0], self.points[i][1]), 
                                     QPointF(self.points[i+1][0], self.points[i+1][1]))
                # Close the loop if 4 points (though it processes immediately)
                if len(self.points) == 4:
                     painter.drawLine(QPointF(self.points[3][0], self.points[3][1]), 
                                     QPointF(self.points[0][0], self.points[0][1]))

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

        self.copied_effects = None

        # Layouts
        main_layout = QHBoxLayout()
        
        # Sidebar container
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(300)
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_layout.setContentsMargins(0, 0, 0, 0) # Remove extra margins
        
        # Buttons
        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self.load_image)
        
        self.stretch_btn = QPushButton("Stretch")
        self.stretch_btn.clicked.connect(self.start_stretch_mode)
        self.stretch_btn.setToolTip("Click 4 points on the image to define corners")
        
        self.polygon_btn = QPushButton("Polygon")
        self.polygon_btn.setCheckable(True)
        self.polygon_btn.clicked.connect(self.toggle_polygon_mode)
        self.polygon_btn.setToolTip("Left click to add points, Right click to finish polygon")

        save_btn = QPushButton("Save Image")
        save_btn.clicked.connect(self.save_image)
        
        save_project_btn = QPushButton("Save Project")
        save_project_btn.clicked.connect(self.save_project)
        
        load_project_btn = QPushButton("Load Project")
        load_project_btn.clicked.connect(self.load_project)
        
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
        sidebar_layout.addWidget(self.stretch_btn)
        sidebar_layout.addWidget(self.polygon_btn)
        sidebar_layout.addWidget(save_btn)
        sidebar_layout.addWidget(save_project_btn)
        sidebar_layout.addWidget(load_project_btn)
        
        sidebar_layout.addSpacing(20)
        sidebar_layout.addWidget(QLabel("Target Size:"))
        
        size_layout = QHBoxLayout()
        size_layout.addWidget(self.width_spin)
        size_layout.addWidget(QLabel("x"))
        size_layout.addWidget(self.height_spin)
        sidebar_layout.addLayout(size_layout)
        
        sidebar_layout.addSpacing(20)
        
        # Polygon Effects Group
        self.effects_group = QGroupBox("Polygon Effects")
        self.effects_group.setEnabled(False)
        effects_layout = QFormLayout()
        
        self.brightness_slider = QSlider(Qt.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.update_effects)
        
        self.contrast_slider = QSlider(Qt.Horizontal)
        self.contrast_slider.setRange(0, 200) # 0.0 to 2.0 (div by 100)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.update_effects)
        
        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setRange(0, 200) # 0.0 to 2.0 (div by 100)
        self.saturation_slider.setValue(100)
        self.saturation_slider.valueChanged.connect(self.update_effects)
        
        self.warmth_slider = QSlider(Qt.Horizontal)
        self.warmth_slider.setRange(-100, 100)
        self.warmth_slider.setValue(0)
        self.warmth_slider.valueChanged.connect(self.update_effects)
        
        self.tint_btn = QPushButton("Select Tint Color")
        self.tint_btn.clicked.connect(self.select_tint_color)
        self.tint_btn.setStyleSheet("background-color: white; color: black;")
        
        self.tint_strength_slider = QSlider(Qt.Horizontal)
        self.tint_strength_slider.setRange(0, 100)
        self.tint_strength_slider.setValue(0)
        self.tint_strength_slider.valueChanged.connect(self.update_effects)

        # Copy/Paste Buttons
        copy_paste_layout = QHBoxLayout()
        self.copy_btn = QPushButton("Copy Colors")
        self.copy_btn.clicked.connect(self.copy_colors)
        self.paste_btn = QPushButton("Paste Colors")
        self.paste_btn.clicked.connect(self.paste_colors)
        self.paste_btn.setEnabled(False)
        
        copy_paste_layout.addWidget(self.copy_btn)
        copy_paste_layout.addWidget(self.paste_btn)

        effects_layout.addRow(copy_paste_layout)
        effects_layout.addRow("Brightness", self.brightness_slider)
        effects_layout.addRow("Contrast", self.contrast_slider)
        effects_layout.addRow("Saturation", self.saturation_slider)
        effects_layout.addRow("Warmth", self.warmth_slider)
        effects_layout.addRow("Tint Color", self.tint_btn)
        effects_layout.addRow("Tint Strength", self.tint_strength_slider)
        
        self.effects_group.setLayout(effects_layout)
        sidebar_layout.addWidget(self.effects_group)
        
        sidebar_layout.addStretch() # Push items to top

        # Add sidebar and scroll area to main layout
        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(self.scroll_area)
        
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)
        
        # Connect signals
        self.canvas.selection_changed.connect(self.on_selection_changed)

    def on_selection_changed(self, index):
        if index == -1:
            self.effects_group.setEnabled(False)
        else:
            self.effects_group.setEnabled(True)
            # Load effects for this polygon
            effects = self.canvas.polygon_effects[index]
            
            # Block signals to prevent triggering update_effects loop
            self.brightness_slider.blockSignals(True)
            self.contrast_slider.blockSignals(True)
            self.saturation_slider.blockSignals(True)
            self.warmth_slider.blockSignals(True)
            self.tint_strength_slider.blockSignals(True)
            
            self.brightness_slider.setValue(int(effects.get('brightness', 0)))
            self.contrast_slider.setValue(int(effects.get('contrast', 1.0) * 100))
            self.saturation_slider.setValue(int(effects.get('saturation', 1.0) * 100))
            self.warmth_slider.setValue(int(effects.get('warmth', 0)))
            self.tint_strength_slider.setValue(int(effects.get('tint_strength', 0)))
            
            # Update tint button color
            color = effects.get('tint_color', (255, 255, 255))
            self.tint_btn.setStyleSheet(f"background-color: rgb({color[0]}, {color[1]}, {color[2]}); color: black;")

            self.brightness_slider.blockSignals(False)
            self.contrast_slider.blockSignals(False)
            self.saturation_slider.blockSignals(False)
            self.warmth_slider.blockSignals(False)
            self.tint_strength_slider.blockSignals(False)

    def select_tint_color(self):
        if self.canvas.selected_polygon_index is not None:
            idx = self.canvas.selected_polygon_index
            effects = self.canvas.polygon_effects[idx]
            current_color = effects.get('tint_color', (255, 255, 255))
            
            color = QColorDialog.getColor(QColor(current_color[0], current_color[1], current_color[2]), self, "Select Tint Color")
            
            if color.isValid():
                rgb = (color.red(), color.green(), color.blue())
                effects['tint_color'] = rgb
                self.tint_btn.setStyleSheet(f"background-color: rgb({rgb[0]}, {rgb[1]}, {rgb[2]}); color: black;")
                self.canvas.apply_effects()

    def copy_colors(self):
        if self.canvas.selected_polygon_index is not None:
            idx = self.canvas.selected_polygon_index
            self.copied_effects = copy.deepcopy(self.canvas.polygon_effects[idx])
            self.paste_btn.setEnabled(True)
            QMessageBox.information(self, "Info", "Colors copied.")

    def paste_colors(self):
        if self.canvas.selected_polygon_index is not None and self.copied_effects:
            idx = self.canvas.selected_polygon_index
            self.canvas.polygon_effects[idx] = copy.deepcopy(self.copied_effects)
            
            # Update UI
            self.on_selection_changed(idx)
            
            # Apply effects
            self.canvas.apply_effects()
            QMessageBox.information(self, "Info", "Colors pasted.")

    def update_effects(self):
        if self.canvas.selected_polygon_index is not None:
            idx = self.canvas.selected_polygon_index
            effects = self.canvas.polygon_effects[idx]
            
            effects['brightness'] = self.brightness_slider.value()
            effects['contrast'] = self.contrast_slider.value() / 100.0
            effects['saturation'] = self.saturation_slider.value() / 100.0
            effects['warmth'] = self.warmth_slider.value()
            effects['tint_strength'] = self.tint_strength_slider.value()
            
            self.canvas.apply_effects()

    def start_stretch_mode(self):
        # Uncheck polygon button if checked
        if self.polygon_btn.isChecked():
            self.polygon_btn.setChecked(False)
            self.canvas.stop_polygon_drawing()
        
        self.canvas.start_stretch_selection()

    def toggle_polygon_mode(self):
        if self.polygon_btn.isChecked():
            success = self.canvas.start_polygon_drawing()
            if not success:
                self.polygon_btn.setChecked(False)
        else:
            self.canvas.stop_polygon_drawing()

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

    def save_project(self):
        if self.canvas.cv_image is None:
            QMessageBox.warning(self, "Warning", "No project to save.")
            return
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", "project.msp", "Mosaic Stretch Project (*.msp)")
        if path:
            data = {
                'image': self.canvas.cv_image,
                'polygons': self.canvas.polygons,
                'effects': self.canvas.polygon_effects,
                'width': self.canvas.target_width,
                'height': self.canvas.target_height
            }
            try:
                with open(path, 'wb') as f:
                    pickle.dump(data, f)
                QMessageBox.information(self, "Success", "Project saved successfully.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save project: {str(e)}")

    def load_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Mosaic Stretch Project (*.msp)")
        if path:
            try:
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                
                self.canvas.cv_image = data['image']
                self.canvas.polygons = data['polygons']
                self.canvas.polygon_effects = data['effects']
                self.canvas.target_width = data.get('width', 300)
                self.canvas.target_height = data.get('height', 300)
                
                # Update UI controls
                self.width_spin.setValue(self.canvas.target_width)
                self.height_spin.setValue(self.canvas.target_height)
                
                # Reset state
                self.canvas.display_image = self.canvas.cv_image.copy()
                self.canvas.scale_factor = 1.0
                self.canvas.points = []
                self.canvas.current_polygon = []
                self.canvas.selecting_mode = False
                self.canvas.drawing_polygon = False
                self.canvas.selected_polygon_index = None
                self.canvas.dragging_point_index = None
                
                # Refresh
                self.canvas.apply_effects() # This calls update_image_from_cv
                self.canvas.update()
                
                # Update effects panel state
                self.on_selection_changed(-1)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project: {str(e)}")


    def eventFilter(self, source, event):
        if source == self.scroll_area.viewport() and event.type() == QEvent.Wheel:
            self.canvas.handle_zoom(event, event.pos())
            return True
        return super().eventFilter(source, event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec_())
