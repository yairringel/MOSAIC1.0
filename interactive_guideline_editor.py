"""
Interactive Mosaic Guideline Editor - PyQt Version
Handles Step C: Interactive Guideline Drawing & Edge Erasing
"""

import sys
import numpy as np
import json
import os
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import cv2

class InteractiveMosaicEditor(QMainWindow):
    def __init__(self, img0, img_edges):
        super().__init__()
        self.img0 = img0
        self.img_edges = img_edges.copy()
        self.original_edges = img_edges.copy()
        
        # Initialize drawing data
        self.drawn_lines = []
        self.splines = []  # List of splines, each spline is a list of control points
        self.current_spline = None
        self.selected_control_point = None  # (spline_index, point_index)
        self.current_line = None
        self.is_drawing = False
        self.is_dragging_control_point = False
        
        # Current mode
        self.current_mode = "draw"  # "draw", "erase", "delete", "spline"
        
        # Drawing settings
        self.line_width = 3
        self.erase_radius = 10
        
        # Zoom and pan
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.last_pan_point = None
        
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("Interactive Mosaic Guideline Editor")
        self.setGeometry(100, 100, 1400, 800)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QHBoxLayout(central_widget)
        
        # Create canvas first
        self.canvas = MosaicCanvas(self)
        
        # Left panel for controls (created after canvas)
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)
        
        # Canvas for drawing
        main_layout.addWidget(self.canvas)
        
        # Set layout proportions
        main_layout.setStretchFactor(control_panel, 0)
        main_layout.setStretchFactor(self.canvas, 1)
        
        # Status bar
        self.statusBar().showMessage("Ready - Use drawing tools to add guidelines")
        
        # Keyboard shortcuts
        self.setFocusPolicy(Qt.StrongFocus)
        
    def create_control_panel(self):
        panel = QWidget()
        panel.setFixedWidth(300)
        layout = QVBoxLayout(panel)
        
        # Title
        title = QLabel("Interactive Guideline Editor")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Mode selection
        mode_group = QGroupBox("Drawing Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.mode_draw = QRadioButton("Draw Guidelines")
        self.mode_draw.setChecked(True)
        self.mode_draw.toggled.connect(lambda: self.set_mode("draw"))
        mode_layout.addWidget(self.mode_draw)
        
        self.mode_erase = QRadioButton("Erase Edges")
        self.mode_erase.toggled.connect(lambda: self.set_mode("erase"))
        mode_layout.addWidget(self.mode_erase)
        
        self.mode_delete = QRadioButton("Delete Lines")
        self.mode_delete.toggled.connect(lambda: self.set_mode("delete"))
        mode_layout.addWidget(self.mode_delete)
        
        self.mode_spline = QRadioButton("Spline Mode")
        self.mode_spline.toggled.connect(lambda: self.set_mode("spline"))
        mode_layout.addWidget(self.mode_spline)
        
        layout.addWidget(mode_group)
        
        # Drawing settings
        settings_group = QGroupBox("Settings")
        settings_layout = QFormLayout(settings_group)
        
        # Line width
        self.line_width_spin = QSpinBox()
        self.line_width_spin.setRange(1, 20)
        self.line_width_spin.setValue(self.line_width)
        self.line_width_spin.valueChanged.connect(self.update_line_width)
        settings_layout.addRow("Line Width:", self.line_width_spin)
        
        # Erase radius
        self.erase_radius_spin = QSpinBox()
        self.erase_radius_spin.setRange(5, 50)
        self.erase_radius_spin.setValue(self.erase_radius)
        self.erase_radius_spin.valueChanged.connect(self.update_erase_radius)
        settings_layout.addRow("Erase Radius:", self.erase_radius_spin)
        
        layout.addWidget(settings_group)
        
        # Actions
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout(actions_group)
        
        # Clear all lines
        self.clear_btn = QPushButton("Clear All Lines")
        self.clear_btn.clicked.connect(self.clear_all_lines)
        actions_layout.addWidget(self.clear_btn)
        
        # Reset edges
        self.reset_btn = QPushButton("Reset Edges")
        self.reset_btn.clicked.connect(self.reset_edges)
        actions_layout.addWidget(self.reset_btn)
        
        # Clear all detected edges
        self.clear_edges_btn = QPushButton("Clear All Detected Edges")
        self.clear_edges_btn.clicked.connect(self.clear_all_detected_edges)
        actions_layout.addWidget(self.clear_edges_btn)
        
        # Convert lines to splines
        self.convert_to_splines_btn = QPushButton("Convert Lines to Splines")
        self.convert_to_splines_btn.clicked.connect(self.convert_lines_to_splines)
        actions_layout.addWidget(self.convert_to_splines_btn)
        
        # Save and load buttons
        self.save_lines_btn = QPushButton("Save Lines/Splines")
        self.save_lines_btn.clicked.connect(self.save_lines)
        actions_layout.addWidget(self.save_lines_btn)
        
        self.load_lines_btn = QPushButton("Load Lines/Splines")
        self.load_lines_btn.clicked.connect(self.load_lines)
        actions_layout.addWidget(self.load_lines_btn)
        
        # Undo last action
        self.undo_btn = QPushButton("Undo Last")
        self.undo_btn.clicked.connect(self.undo_last)
        actions_layout.addWidget(self.undo_btn)
        
        layout.addWidget(actions_group)
        
        # View controls
        view_group = QGroupBox("View")
        view_layout = QVBoxLayout(view_group)
        
        # Zoom controls
        zoom_layout = QHBoxLayout()
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(self.zoom_out_btn)
        view_layout.addLayout(zoom_layout)
        
        # Reset view
        self.reset_view_btn = QPushButton("Reset View")
        self.reset_view_btn.clicked.connect(self.reset_view)
        view_layout.addWidget(self.reset_view_btn)
        
        layout.addWidget(view_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.lines_label = QLabel("Lines drawn: 0")
        stats_layout.addWidget(self.lines_label)
        
        self.edges_label = QLabel("Edge pixels: 0")
        stats_layout.addWidget(self.edges_label)
        
        layout.addWidget(stats_group)
        
        # Done button
        layout.addStretch()
        self.done_btn = QPushButton("Finish Editing")
        self.done_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 15px;
                font-size: 14px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.done_btn.clicked.connect(self.finish_editing)
        layout.addWidget(self.done_btn)
        
        return panel
    
    def set_mode(self, mode):
        self.current_mode = mode
        self.canvas.setCursor(self.get_cursor_for_mode())
        
        # Update status
        status_messages = {
            "draw": "Drawing mode - Click and drag to draw guidelines",
            "erase": "Erase mode - Click to erase detected edges",
            "delete": "Delete mode - Click on lines to delete them",
            "spline": "Spline mode - Click to place control points, drag to move them"
        }
        self.statusBar().showMessage(status_messages[mode])
    
    def get_cursor_for_mode(self):
        if self.current_mode == "draw":
            return Qt.CrossCursor
        elif self.current_mode == "erase":
            return Qt.PointingHandCursor
        elif self.current_mode == "delete":
            return Qt.ForbiddenCursor
        elif self.current_mode == "spline":
            return Qt.CrossCursor
        return Qt.ArrowCursor
    
    def update_line_width(self, value):
        self.line_width = value
    
    def update_erase_radius(self, value):
        self.erase_radius = value
    
    def clear_all_lines(self):
        self.drawn_lines = []
        self.splines = []
        self.current_spline = None
        self.selected_control_point = None
        self.update_statistics()
        self.canvas.update()
    
    def reset_edges(self):
        self.img_edges = self.original_edges.copy()
        self.update_statistics()
        self.canvas.update()
    
    def clear_all_detected_edges(self):
        self.img_edges = np.zeros_like(self.img_edges)
        self.update_statistics()
        self.canvas.update()
    
    def convert_lines_to_splines(self):
        """Convert all drawn lines to splines with evenly distributed control points"""
        for line in self.drawn_lines:
            if len(line) >= 2:
                # Sample control points from the line (every nth point)
                step = max(1, len(line) // 6)  # Create ~6 control points maximum
                control_points = [line[i] for i in range(0, len(line), step)]
                if control_points[-1] != line[-1]:  # Make sure end point is included
                    control_points.append(line[-1])
                self.splines.append(control_points)
        
        # Clear the original lines
        self.drawn_lines = []
        self.update_statistics()
        self.canvas.update()
    
    def save_lines(self):
        """Save drawn lines and splines to a JSON file"""
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Lines and Splines", 
            "mosaic_lines.json", 
            "JSON files (*.json);;All files (*.*)"
        )
        
        if filename:
            try:
                # Prepare data for saving
                save_data = {
                    "drawn_lines": self.drawn_lines,
                    "splines": self.splines,
                    "line_width": self.line_width,
                    "erase_radius": self.erase_radius,
                    "image_dimensions": [self.canvas.image_width, self.canvas.image_height],
                    "version": "1.0"
                }
                
                # Save to JSON file
                with open(filename, 'w') as f:
                    json.dump(save_data, f, indent=2)
                
                self.statusBar().showMessage(f"Lines saved to {os.path.basename(filename)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save lines:\n{str(e)}")
    
    def load_lines(self):
        """Load drawn lines and splines from a JSON file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Lines and Splines", 
            "", 
            "JSON files (*.json);;All files (*.*)"
        )
        
        if filename:
            try:
                # Load from JSON file
                with open(filename, 'r') as f:
                    load_data = json.load(f)
                
                # Restore data
                self.drawn_lines = load_data.get("drawn_lines", [])
                self.splines = load_data.get("splines", [])
                
                # Restore settings if available
                if "line_width" in load_data:
                    self.line_width = load_data["line_width"]
                    self.line_width_spin.setValue(self.line_width)
                
                if "erase_radius" in load_data:
                    self.erase_radius = load_data["erase_radius"]
                    self.erase_radius_spin.setValue(self.erase_radius)
                
                # Check image dimensions compatibility
                if "image_dimensions" in load_data:
                    saved_dims = load_data["image_dimensions"]
                    current_dims = [self.canvas.image_width, self.canvas.image_height]
                    
                    if saved_dims != current_dims:
                        reply = QMessageBox.question(
                            self, 
                            "Dimension Mismatch",
                            f"Saved lines were created for image size {saved_dims[0]}x{saved_dims[1]}\n"
                            f"Current image size is {current_dims[0]}x{current_dims[1]}\n\n"
                            f"Do you want to scale the lines to fit the current image?",
                            QMessageBox.Yes | QMessageBox.No
                        )
                        
                        if reply == QMessageBox.Yes:
                            self.scale_lines_to_current_image(saved_dims, current_dims)
                
                # Clear current editing state
                self.current_line = None
                self.current_spline = None
                self.selected_control_point = None
                self.is_drawing = False
                self.is_dragging_control_point = False
                
                # Update display
                self.update_statistics()
                self.canvas.update()
                self.statusBar().showMessage(f"Lines loaded from {os.path.basename(filename)}")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load lines:\n{str(e)}")
    
    def scale_lines_to_current_image(self, old_dims, new_dims):
        """Scale loaded lines to fit the current image dimensions"""
        scale_x = new_dims[0] / old_dims[0]
        scale_y = new_dims[1] / old_dims[1]
        
        # Scale drawn lines
        for line in self.drawn_lines:
            for i in range(len(line)):
                x, y = line[i]
                line[i] = (x * scale_x, y * scale_y)
        
        # Scale splines
        for spline in self.splines:
            for i in range(len(spline)):
                x, y = spline[i]
                spline[i] = (x * scale_x, y * scale_y)
    
    def undo_last(self):
        if self.drawn_lines:
            self.drawn_lines.pop()
            self.update_statistics()
            self.canvas.update()
    
    def zoom_in(self):
        self.zoom_factor *= 1.2
        self.canvas.update()
    
    def zoom_out(self):
        self.zoom_factor /= 1.2
        self.canvas.update()
    
    def reset_view(self):
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.canvas.update()
    
    def update_statistics(self):
        total_curves = len(self.drawn_lines) + len(self.splines)
        self.lines_label.setText(f"Lines/Splines drawn: {total_curves}")
        edge_count = np.sum(self.img_edges)
        self.edges_label.setText(f"Edge pixels: {edge_count}")
    
    def finish_editing(self):
        self.close()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_D:
            self.mode_draw.setChecked(True)
        elif event.key() == Qt.Key_E:
            self.mode_erase.setChecked(True)
        elif event.key() == Qt.Key_X:
            self.mode_delete.setChecked(True)
        elif event.key() == Qt.Key_S:
            self.mode_spline.setChecked(True)
        elif event.key() == Qt.Key_C:
            self.clear_all_lines()
        elif event.key() == Qt.Key_R:
            self.reset_edges()
        elif event.key() == Qt.Key_Q:
            self.clear_all_detected_edges()
        elif event.key() == Qt.Key_Z and event.modifiers() == Qt.ControlModifier:
            self.undo_last()
        elif event.key() == Qt.Key_S and event.modifiers() == Qt.ControlModifier:
            self.save_lines()
        elif event.key() == Qt.Key_O and event.modifiers() == Qt.ControlModifier:
            self.load_lines()
        elif event.key() == Qt.Key_Plus or event.key() == Qt.Key_Equal:
            self.zoom_in()
        elif event.key() == Qt.Key_Minus:
            self.zoom_out()
        elif event.key() == Qt.Key_0:
            self.reset_view()
        
        super().keyPressEvent(event)

class MosaicCanvas(QWidget):
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        
        # Convert numpy array to QImage for display
        self.update_display_image()
        
    def generate_spline_points(self, control_points, num_points=100):
        """Generate smooth spline curve from control points using Catmull-Rom splines"""
        if len(control_points) < 2:
            return control_points
        
        if len(control_points) == 2:
            # Linear interpolation for 2 points
            p1, p2 = control_points
            points = []
            for t in np.linspace(0, 1, num_points):
                x = p1[0] * (1 - t) + p2[0] * t
                y = p1[1] * (1 - t) + p2[1] * t
                points.append((x, y))
            return points
        
        # Catmull-Rom spline for 3+ points
        points = []
        control_points = np.array(control_points)
        
        # Add duplicate points at the ends for better curve behavior
        extended_points = np.vstack([
            control_points[0],
            control_points,
            control_points[-1]
        ])
        
        for i in range(len(control_points) - 1):
            p0 = extended_points[i]
            p1 = extended_points[i + 1]
            p2 = extended_points[i + 2]
            p3 = extended_points[i + 3]
            
            segment_points = int(num_points / (len(control_points) - 1))
            for j in range(segment_points):
                t = j / segment_points
                
                # Catmull-Rom formula
                x = 0.5 * (
                    2 * p1[0] +
                    (-p0[0] + p2[0]) * t +
                    (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t * t +
                    (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t * t * t
                )
                
                y = 0.5 * (
                    2 * p1[1] +
                    (-p0[1] + p2[1]) * t +
                    (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t * t +
                    (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t * t * t
                )
                
                points.append((x, y))
        
        return points
        
    def update_display_image(self):
        # Create RGB display image
        img = self.editor.img0.copy()
        
        # Convert to uint8 if needed
        if img.dtype != np.uint8:
            if img.max() <= 1.0:  # Assume normalized float
                img = (img * 255).astype(np.uint8)
            else:  # Scale to 0-255 range
                img = ((img - img.min()) / (img.max() - img.min()) * 255).astype(np.uint8)
        
        if len(img.shape) == 3:
            h, w, c = img.shape
            if c == 3:  # Already RGB or BGR
                rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            else:  # RGBA or other
                rgb_image = img[:, :, :3]  # Take first 3 channels
        else:
            h, w = img.shape
            rgb_image = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        
        self.display_image = rgb_image
        self.image_height, self.image_width = h, w
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Clear background
        painter.fillRect(self.rect(), QColor(64, 64, 64))
        
        # Calculate image position and size with zoom and pan
        widget_width = self.width()
        widget_height = self.height()
        
        # Calculate scaled image dimensions
        scale_x = widget_width / self.image_width
        scale_y = widget_height / self.image_height
        scale = min(scale_x, scale_y) * self.editor.zoom_factor
        
        scaled_width = int(self.image_width * scale)
        scaled_height = int(self.image_height * scale)
        
        # Center the image with pan offset
        x = (widget_width - scaled_width) // 2 + self.editor.pan_x
        y = (widget_height - scaled_height) // 2 + self.editor.pan_y
        
        # Draw base image
        qimg = QImage(self.display_image.data, self.image_width, self.image_height, 
                     self.image_width * 3, QImage.Format_RGB888)
        painter.drawImage(QRect(x, y, scaled_width, scaled_height), qimg)
        
        # Always show detected edges as green lines
        if np.any(self.editor.img_edges > 0):
            # Draw detected edges as thin green lines
            painter.setPen(QPen(QColor(0, 255, 0), 1))  # Green thin lines for edges
            
            # Find edge pixels and draw them
            edge_points = np.where(self.editor.img_edges > 0)
            for i in range(len(edge_points[0])):
                edge_y = edge_points[0][i]
                edge_x = edge_points[1][i]
                screen_x = x + edge_x * scale
                screen_y = y + edge_y * scale
                painter.drawPoint(int(screen_x), int(screen_y))
        
        # Draw manually drawn lines
        painter.setPen(QPen(QColor(255, 0, 0), 2))  # Red lines
        for line in self.editor.drawn_lines:
            if len(line) > 1:
                qpoints = []
                for px, py in line:
                    screen_x = x + px * scale
                    screen_y = y + py * scale
                    qpoints.append(QPointF(screen_x, screen_y))
                
                for i in range(len(qpoints) - 1):
                    painter.drawLine(qpoints[i], qpoints[i + 1])
        
        # Draw splines
        painter.setPen(QPen(QColor(0, 0, 255), 2))  # Blue splines
        for spline in self.editor.splines:
            if len(spline) >= 2:
                spline_points = self.generate_spline_points(spline)
                qpoints = []
                for px, py in spline_points:
                    screen_x = x + px * scale
                    screen_y = y + py * scale
                    qpoints.append(QPointF(screen_x, screen_y))
                
                for i in range(len(qpoints) - 1):
                    painter.drawLine(qpoints[i], qpoints[i + 1])
        
        # Draw current spline being created
        if self.editor.current_spline and len(self.editor.current_spline) >= 1:
            painter.setPen(QPen(QColor(0, 255, 255), 2))  # Cyan for current spline
            
            # Draw control points as small circles
            painter.setBrush(QBrush(QColor(0, 255, 255)))
            for px, py in self.editor.current_spline:
                screen_x = x + px * scale
                screen_y = y + py * scale
                painter.drawEllipse(QPointF(screen_x, screen_y), 3, 3)
            
            # If we have enough points, draw the spline curve
            if len(self.editor.current_spline) >= 2:
                spline_points = self.generate_spline_points(self.editor.current_spline)
                qpoints = []
                for px, py in spline_points:
                    screen_x = x + px * scale
                    screen_y = y + py * scale
                    qpoints.append(QPointF(screen_x, screen_y))
                
                painter.setPen(QPen(QColor(0, 255, 255), 1))  # Thin cyan line
                for i in range(len(qpoints) - 1):
                    painter.drawLine(qpoints[i], qpoints[i + 1])
        
        # Draw control points for splines
        painter.setPen(QPen(QColor(0, 0, 255), 2))
        painter.setBrush(QBrush(QColor(255, 255, 0)))  # Yellow control points
        for spline_idx, spline in enumerate(self.editor.splines):
            for point_idx, (px, py) in enumerate(spline):
                screen_x = x + px * scale
                screen_y = y + py * scale
                
                # Highlight selected control point
                if (self.editor.selected_control_point and 
                    self.editor.selected_control_point[0] == spline_idx and 
                    self.editor.selected_control_point[1] == point_idx):
                    painter.setBrush(QBrush(QColor(255, 0, 255)))  # Magenta for selected
                else:
                    painter.setBrush(QBrush(QColor(255, 255, 0)))  # Yellow for normal
                
                painter.drawEllipse(QPointF(screen_x, screen_y), 4, 4)
        
        # Draw current line being drawn
        if self.editor.current_line and len(self.editor.current_line) > 1:
            painter.setPen(QPen(QColor(255, 255, 0), 2))  # Yellow for current line
            qpoints = []
            for px, py in self.editor.current_line:
                screen_x = x + px * scale
                screen_y = y + py * scale
                qpoints.append(QPointF(screen_x, screen_y))
            
            for i in range(len(qpoints) - 1):
                painter.drawLine(qpoints[i], qpoints[i + 1])
        
        # Store transform parameters for mouse handling
        self.image_x = x
        self.image_y = y
        self.image_scale = scale
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Convert screen coordinates to image coordinates
            image_x, image_y = self.screen_to_image(event.x(), event.y())
            
            if 0 <= image_x < self.image_width and 0 <= image_y < self.image_height:
                if self.editor.current_mode == "draw":
                    self.editor.is_drawing = True
                    self.editor.current_line = [(image_x, image_y)]
                    
                elif self.editor.current_mode == "erase":
                    self.erase_edges(image_x, image_y)
                    
                elif self.editor.current_mode == "delete":
                    self.delete_line_at_point(image_x, image_y)
                    
                elif self.editor.current_mode == "spline":
                    # Check if clicking on existing control point
                    clicked_control_point = self.find_control_point_at(image_x, image_y)
                    if clicked_control_point:
                        self.editor.selected_control_point = clicked_control_point
                        self.editor.is_dragging_control_point = True
                    else:
                        # Add new control point to current spline or start new spline
                        if self.editor.current_spline is None:
                            self.editor.current_spline = [(image_x, image_y)]
                        else:
                            self.editor.current_spline.append((image_x, image_y))
                        self.update()
        
        elif event.button() == Qt.RightButton:
            if self.editor.current_mode == "spline" and self.editor.current_spline:
                # Finish current spline
                if len(self.editor.current_spline) >= 2:
                    self.editor.splines.append(self.editor.current_spline)
                    self.editor.update_statistics()
                self.editor.current_spline = None
                self.update()
            else:
                # Start panning
                self.editor.last_pan_point = event.pos()
    
    def mouseMoveEvent(self, event):
        if self.editor.is_drawing and self.editor.current_line:
            image_x, image_y = self.screen_to_image(event.x(), event.y())
            
            if 0 <= image_x < self.image_width and 0 <= image_y < self.image_height:
                self.editor.current_line.append((image_x, image_y))
                self.update()
        
        elif self.editor.is_dragging_control_point and self.editor.selected_control_point:
            # Move selected control point
            image_x, image_y = self.screen_to_image(event.x(), event.y())
            if 0 <= image_x < self.image_width and 0 <= image_y < self.image_height:
                spline_idx, point_idx = self.editor.selected_control_point
                self.editor.splines[spline_idx][point_idx] = (image_x, image_y)
                self.update()
        
        elif self.editor.last_pan_point and event.buttons() & Qt.RightButton:
            # Handle panning
            delta = event.pos() - self.editor.last_pan_point
            self.editor.pan_x += delta.x()
            self.editor.pan_y += delta.y()
            self.editor.last_pan_point = event.pos()
            self.update()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.editor.is_drawing:
            # Finish drawing line
            if self.editor.current_line and len(self.editor.current_line) > 1:
                self.editor.drawn_lines.append(self.editor.current_line)
                self.editor.update_statistics()
            
            self.editor.current_line = None
            self.editor.is_drawing = False
            self.update()
            
        elif event.button() == Qt.LeftButton and self.editor.is_dragging_control_point:
            # Stop dragging control point
            self.editor.is_dragging_control_point = False
            self.editor.selected_control_point = None
            
        elif event.button() == Qt.RightButton:
            # Stop panning
            self.editor.last_pan_point = None
    
    def wheelEvent(self, event):
        # Zoom with mouse wheel
        delta = event.angleDelta().y()
        if delta > 0:
            self.editor.zoom_factor *= 1.1
        else:
            self.editor.zoom_factor /= 1.1
        
        self.update()
    
    def screen_to_image(self, screen_x, screen_y):
        """Convert screen coordinates to image coordinates"""
        if hasattr(self, 'image_x') and hasattr(self, 'image_y') and hasattr(self, 'image_scale'):
            image_x = (screen_x - self.image_x) / self.image_scale
            image_y = (screen_y - self.image_y) / self.image_scale
            return int(image_x), int(image_y)
        return 0, 0
    
    def erase_edges(self, center_x, center_y):
        """Erase detected edges in a circular area"""
        radius = self.editor.erase_radius
        y_indices, x_indices = np.ogrid[:self.image_height, :self.image_width]
        
        # Create circular mask
        mask = ((x_indices - center_x) ** 2 + (y_indices - center_y) ** 2) <= radius ** 2
        
        # Erase edges in the circular area
        self.editor.img_edges[mask] = 0
        self.editor.update_statistics()
        self.update()
    
    def find_control_point_at(self, x, y, tolerance=10):
        """Find control point near the given coordinates"""
        for spline_idx, spline in enumerate(self.editor.splines):
            for point_idx, (px, py) in enumerate(spline):
                if abs(px - x) <= tolerance and abs(py - y) <= tolerance:
                    return (spline_idx, point_idx)
        return None
    
    def delete_line_at_point(self, point_x, point_y):
        """Delete a drawn line or spline near the clicked point"""
        tolerance = 10  # Distance tolerance for line selection
        
        # Check regular lines first
        for i, line in enumerate(self.editor.drawn_lines):
            for lx, ly in line:
                if abs(lx - point_x) <= tolerance and abs(ly - point_y) <= tolerance:
                    del self.editor.drawn_lines[i]
                    self.editor.update_statistics()
                    self.update()
                    return
        
        # Check splines
        for i, spline in enumerate(self.editor.splines):
            for lx, ly in spline:
                if abs(lx - point_x) <= tolerance and abs(ly - point_y) <= tolerance:
                    del self.editor.splines[i]
                    self.editor.update_statistics()
                    self.update()
                    return

def run_interactive_editor(img0, img_edges):
    """
    Run the interactive mosaic guideline editor
    
    Parameters:
    - img0: Original image (numpy array)
    - img_edges: Detected edge image (numpy array)
    
    Returns:
    - manual_edges: Binary image of manually drawn guidelines
    - modified_edges: Modified edge detection result
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    editor = InteractiveMosaicEditor(img0, img_edges)
    editor.show()
    
    # Run the editor and wait for completion
    app.exec_()
    
    # Convert drawn lines to binary edge image
    manual_edges = np.zeros_like(img_edges, dtype=np.uint8)
    
    # Draw regular lines
    for line in editor.drawn_lines:
        if len(line) > 1:
            for i in range(len(line) - 1):
                x1, y1 = line[i]
                x2, y2 = line[i + 1]
                
                # Draw line using OpenCV
                cv2.line(manual_edges, (int(x1), int(y1)), (int(x2), int(y2)), 
                        1, editor.line_width)
    
    # Draw splines
    canvas = editor.canvas
    for spline in editor.splines:
        if len(spline) >= 2:
            spline_points = canvas.generate_spline_points(spline, num_points=200)
            for i in range(len(spline_points) - 1):
                x1, y1 = spline_points[i]
                x2, y2 = spline_points[i + 1]
                
                # Draw spline segment using OpenCV
                cv2.line(manual_edges, (int(x1), int(y1)), (int(x2), int(y2)), 
                        1, editor.line_width)
    
    return manual_edges, editor.img_edges

# Test the editor if run directly
if __name__ == "__main__":
    # Create test data
    test_img = np.random.randint(0, 255, (400, 600, 3), dtype=np.uint8)
    test_edges = np.random.randint(0, 2, (400, 600), dtype=np.uint8)
    
    # Run interactive editor
    additional_edges, modified_edges = run_interactive_editor(test_img, test_edges)
    
    print(f"Manual edges shape: {additional_edges.shape}")
    print(f"Modified edges shape: {modified_edges.shape}")
    print(f"Manual edge pixels: {np.sum(additional_edges)}")
    print(f"Modified edge pixels: {np.sum(modified_edges)}")
