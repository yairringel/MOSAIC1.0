#!/usr/bin/env python3
"""
Mandala Mosaic Application
A simple PyQt5 application with a central canvas and side panels.
"""

import sys
import csv
import json
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QFrame, QLabel, QPushButton, QFileDialog, QCheckBox, QSpinBox, QLineEdit, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QPoint, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QPixmap, QBrush, QFont, QPolygon, QCursor


class Canvas(QWidget):
    """Central canvas widget for drawing/displaying content"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 600)
        self.setStyleSheet("background-color: white; border: 1px solid black;")
        self.background_image = None
        
        # Polygon drawing mode variables
        self.polygon_mode = False
        self.polygon_points = []  # Points for the current polygon being drawn
        self.polygon_cursor_size = 10  # Size of the square cursor in pixels
        self.polygons = []  # List of completed polygons
        
        # Zoom and pan variables
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.is_panning = False
        self.last_pan_point = None
        
        # Image offset variables (separate from zoom/pan)
        self.image_offset_x = 0
        self.image_offset_y = 0
        
        # Radial copies setting
        self.num_copies = 6  # Default number of radial copies
        self.mandala_mode = True  # Whether to create radial copies (mandala mode)
        
        # Eraser mode
        self.eraser_mode = False
        self.is_erasing = False  # Track if currently dragging to erase
        
        # Fixed mandala center in world coordinates (will be set after widget is shown)
        self.mandala_center_world_x = None
        self.mandala_center_world_y = None
        
        # Center point offset
        self.center_offset_x = 0
        self.center_offset_y = 0
        
        # Parent shape tracking for polygon groups
        self.polygon_groups = []  # List of polygon groups, each group shares the same parent
        self.current_group_id = 0  # Counter for unique group IDs
        
        # Selection tracking
        self.selected_polygon_index = -1  # Index of currently selected polygon (-1 means none)
        self.selected_polygon_indices = []  # List of all selected polygon indices (for group selection)
        
        # Control point editing
        self.selected_control_point = -1  # Index of selected control point (-1 means none)
        self.is_dragging_control_point = False
        self.control_point_size = 8  # Size of control point circles in pixels
        
        # Debug visualization
        self.debug_circle_dots = []  # List of (x, y) positions for debugging circular positions
        
        # Circle drawing
        self.show_circle = False
        self.circle_diameter = 1000  # Default diameter
        
        # Circle drag handle
        self.is_dragging_center = False
        self.drag_handle_size = 12  # Size of the drag handle circle
        
        # Image drag handle
        self.is_dragging_image = False
        self.image_drag_start_offset_x = 0
        self.image_drag_start_offset_y = 0
        
        # Image visibility
        self.show_image = True  # Default to showing image
        
        # Enable mouse tracking for cursor display
        self.setMouseTracking(True)
        
        # Enable keyboard focus for key events
        self.setFocusPolicy(Qt.StrongFocus)
        
        # Timer for cursor updates in polygon mode
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.update_cursor)
        # Don't start timer by default - only when entering polygon mode
    
    def update_cursor(self):
        """Update cursor display in polygon mode"""
        if self.polygon_mode:
            self.update()  # Refresh display to show cursor
    
    def screen_to_world(self, screen_x, screen_y):
        """Convert screen coordinates to world coordinates"""
        world_x = (screen_x - self.pan_offset_x) / self.zoom_factor
        world_y = (screen_y - self.pan_offset_y) / self.zoom_factor
        return world_x, world_y
    
    def world_to_screen(self, world_x, world_y):
        """Convert world coordinates to screen coordinates"""
        screen_x = world_x * self.zoom_factor + self.pan_offset_x
        screen_y = world_y * self.zoom_factor + self.pan_offset_y
        return screen_x, screen_y
    
    def set_num_copies(self, num_copies):
        """Set the number of radial copies to create"""
        self.num_copies = max(1, num_copies)  # Ensure at least 1 copy
    
    def set_mandala_mode(self, enabled):
        """Set whether to create radial copies (mandala mode)"""
        self.mandala_mode = enabled
    
    def set_eraser_mode(self, enabled):
        """Set whether eraser mode is enabled"""
        self.eraser_mode = enabled
        if enabled:
            # Exit polygon mode if active
            if self.polygon_mode:
                self.polygon_mode = False
                self.polygon_points = []  # Clear any in-progress polygon
                self.cursor_timer.stop()
                
                # Update polygon checkbox to reflect the change
                parent = self.parent()
                while parent:
                    for child in parent.findChildren(QCheckBox):
                        if child.text() == "Polygon" and hasattr(child, 'setChecked'):
                            child.blockSignals(True)
                            child.setChecked(False)
                            child.blockSignals(False)
                            break
                    parent = parent.parent()
            
            # Set cursor to indicate eraser mode
            self.setCursor(Qt.PointingHandCursor)
        else:
            # Reset cursor
            self.setCursor(Qt.ArrowCursor if not self.polygon_mode else Qt.BlankCursor)
        self.update()  # Refresh display
    
    def set_circle_visible(self, visible):
        """Set whether to show the circle"""
        self.show_circle = visible
        self.update()  # Refresh display
    
    def set_circle_diameter(self, diameter):
        """Set the circle diameter"""
        self.circle_diameter = max(1, diameter)  # Ensure positive value
        if self.show_circle:
            self.update()  # Refresh display if circle is visible
    
    def set_image_visible(self, visible):
        """Set whether to show the background image"""
        self.show_image = visible
        self.update()  # Refresh display
    
    def get_circle_drag_handle_position(self):
        """Get the screen position of the circle drag handle (top-left of circle)"""
        if (not self.show_circle or 
            self.mandala_center_world_x is None or 
            self.mandala_center_world_y is None):
            return None, None
        
        # Get circle center in screen coordinates
        screen_center_x, screen_center_y = self.world_to_screen(
            self.mandala_center_world_x, 
            self.mandala_center_world_y
        )
        
        # Calculate circle radius in screen coordinates
        user_circle_radius_world = self.circle_diameter / 2.0
        circle_screen_radius = abs(user_circle_radius_world * self.zoom_factor)
        
        # Position handle at top-left of circle (45 degrees from center)
        import math
        angle = math.radians(225)  # 225 degrees = top-left
        handle_x = screen_center_x + circle_screen_radius * math.cos(angle)
        handle_y = screen_center_y + circle_screen_radius * math.sin(angle)
        
        return handle_x, handle_y
    
    def is_point_in_drag_handle(self, screen_x, screen_y):
        """Check if a screen point is inside the drag handle"""
        handle_x, handle_y = self.get_circle_drag_handle_position()
        if handle_x is None or handle_y is None:
            return False
        
        # Check if point is within handle circle
        distance = math.sqrt((screen_x - handle_x)**2 + (screen_y - handle_y)**2)
        return distance <= self.drag_handle_size / 2
    
    def get_image_drag_handle_position(self):
        """Get the screen position of the image drag handle (bottom-left of image)"""
        if (not self.show_image or 
            not self.background_image or 
            self.background_image.isNull()):
            return None, None
        
        # Get image position in world coordinates
        image_world_x = self.image_offset_x
        image_world_y = self.image_offset_y
        
        # Get image dimensions in world coordinates
        image_world_width = self.background_image.width()
        image_world_height = self.background_image.height()
        
        # Bottom-left corner of image in world coordinates
        bottom_left_world_x = image_world_x
        bottom_left_world_y = image_world_y + image_world_height
        
        # Convert to screen coordinates
        handle_x, handle_y = self.world_to_screen(bottom_left_world_x, bottom_left_world_y)
        
        return handle_x, handle_y
    
    def is_point_in_image_drag_handle(self, screen_x, screen_y):
        """Check if a screen point is inside the image drag handle"""
        handle_x, handle_y = self.get_image_drag_handle_position()
        if handle_x is None or handle_y is None:
            return False
        
        # Check if point is within handle circle
        distance = math.sqrt((screen_x - handle_x)**2 + (screen_y - handle_y)**2)
        return distance <= self.drag_handle_size / 2
    
    def set_background_image(self, image_path, desired_size=None):
        """Set background image for the canvas, optionally resizing it"""
        try:
            # Load the original image
            original_pixmap = QPixmap(image_path)
            
            if desired_size is not None:
                # Get original dimensions
                original_width = original_pixmap.width()
                original_height = original_pixmap.height()
                
                # Determine which side is longer
                longer_side = max(original_width, original_height)
                
                # Calculate scale factor
                scale_factor = desired_size / longer_side
                
                # Calculate new dimensions maintaining aspect ratio
                new_width = int(original_width * scale_factor)
                new_height = int(original_height * scale_factor)
                
                # Resize the image
                self.background_image = original_pixmap.scaled(
                    new_width, new_height, 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
            else:
                # Use original size
                self.background_image = original_pixmap
            
            self.update()  # Trigger repaint
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def toggle_polygon_mode(self):
        """Toggle polygon drawing mode on/off"""
        self.polygon_mode = not self.polygon_mode
        
        if self.polygon_mode:
            # Entering polygon mode - exit eraser mode if active
            if self.eraser_mode:
                self.eraser_mode = False
                
                # Update eraser checkbox to reflect the change
                parent = self.parent()
                while parent:
                    for child in parent.findChildren(QCheckBox):
                        if child.text() == "Eraser Mode" and hasattr(child, 'setChecked'):
                            child.blockSignals(True)
                            child.setChecked(False)
                            child.blockSignals(False)
                            break
                    parent = parent.parent()
            
            self.polygon_points = []  # Reset points
            self.setCursor(Qt.BlankCursor)  # Hide cursor, we'll draw our own
            self.cursor_timer.start(50)  # Start cursor updates
        else:
            # Exiting polygon mode
            self.setCursor(Qt.ArrowCursor)  # Restore normal cursor
            self.polygon_points = []  # Clear any points
            self.cursor_timer.stop()  # Stop cursor updates
        
        self.update()  # Refresh display
    
    def add_polygon_point(self, screen_x, screen_y):
        """Add a point to the current polygon being drawn"""
        if not self.polygon_mode:
            return
        
        # Convert screen coordinates to world coordinates for storage
        world_x, world_y = self.screen_to_world(screen_x, screen_y)
        self.polygon_points.append((world_x, world_y))
        self.update()  # Refresh to show new point
    
    def finish_polygon(self):
        """Finish the current polygon if we have enough points"""
        if len(self.polygon_points) >= 3:
            if self.mandala_mode:
                # Create the original polygon plus radial copies
                self.create_radial_polygons()
            else:
                # Create only a single polygon (no copies)
                self.create_single_polygon()
        elif len(self.polygon_points) > 0:
            # Have some points but not enough
            # Keep the points, don't clear them - user might want to add more
            pass
        # If no points, do nothing silently
    
    def create_radial_polygons(self):
        """Create polygons arranged in a circle around center"""
        if len(self.polygon_points) < 3:
            return
        
        # Get mandala center in world coordinates (use fixed center)
        self.initialize_mandala_center()  # Ensure center is initialized
        center_world_x = self.mandala_center_world_x
        center_world_y = self.mandala_center_world_y
        
        # Calculate angle between each copy
        angle_step = 360.0 / self.num_copies if self.num_copies > 0 else 60.0
        
        # Create a new group for this set of polygons
        group_id = self.current_group_id
        self.current_group_id += 1
        
        # Store the original parent shape (first polygon in the group)
        parent_shape = {
            'points': list(self.polygon_points),  # Copy the original points
            'center': (center_world_x, center_world_y),
            'angle_step': angle_step,
            'num_copies': self.num_copies,
            'group_id': group_id,
            'creation_order': len(self.polygon_groups)
        }
        
        # Create group data structure
        group_polygons = []
        
        # Get color from original polygon points (for all copies to share)
        if self.background_image and not self.background_image.isNull():
            # Get average color from background image using original points
            shared_color = self.get_average_color_from_background(self.polygon_points)
        else:
            # No background image - use transparent polygons
            shared_color = QColor(0, 0, 0, 0)  # Fully transparent
        
        # Create specified number of polygons with calculated rotation
        for i in range(self.num_copies):
            angle_degrees = i * angle_step
            angle_radians = math.radians(angle_degrees)
            
            # Rotate each point around the center
            rotated_points = []
            for world_x, world_y in self.polygon_points:
                # Translate to origin (relative to center)
                rel_x = world_x - center_world_x
                rel_y = world_y - center_world_y
                
                # Apply rotation
                rotated_x = rel_x * math.cos(angle_radians) - rel_y * math.sin(angle_radians)
                rotated_y = rel_x * math.sin(angle_radians) + rel_y * math.cos(angle_radians)
                
                # Translate back
                final_x = rotated_x + center_world_x
                final_y = rotated_y + center_world_y
                
                rotated_points.append((final_x, final_y))
            
            # Create polygon data using the shared color from original points
            polygon_data = {
                'points': rotated_points,
                'color': shared_color,  # All copies use the same color
                'group_id': group_id,
                'copy_index': i,  # Index within the group (0 = original, 1+ = copies)
                'rotation_angle': angle_degrees,
                'parent_shape': parent_shape  # Reference to the parent shape data
            }
            
            self.polygons.append(polygon_data)
            group_polygons.append(polygon_data)
        
        # Store the group information
        group_info = {
            'group_id': group_id,
            'parent_shape': parent_shape,
            'polygons': group_polygons,
            'creation_time': len(self.polygon_groups)  # Simple timestamp
        }
        self.polygon_groups.append(group_info)
        
        # Clear current points after creating all polygons
        self.polygon_points = []
        self.update()  # Refresh display
    
    def create_single_polygon(self):
        """Create a single polygon without radial copies"""
        if len(self.polygon_points) < 3:
            return
        
        # Use same filling logic as mandala mode
        if self.background_image and not self.background_image.isNull():
            # Get average color from background image for this polygon
            color = self.get_average_color_from_background(self.polygon_points)
        else:
            # No background image - use transparent polygons
            color = QColor(0, 0, 0, 0)  # Fully transparent
        
        # Create polygon data structure (similar to radial polygons but simpler)
        polygon_data = {
            'points': list(self.polygon_points),  # Copy the points
            'color': color,
            'is_single': True  # Mark as single polygon (not part of mandala group)
        }
        
        # Add to polygons list
        self.polygons.append(polygon_data)
        
        # Clear current points
        self.polygon_points = []
        self.update()  # Refresh display
    
    def get_polygon_group_by_id(self, group_id):
        """Get polygon group information by group ID"""
        for group in self.polygon_groups:
            if group['group_id'] == group_id:
                return group
        return None
    
    def get_parent_shape(self, polygon_data):
        """Get the parent shape for a given polygon"""
        if 'parent_shape' in polygon_data:
            return polygon_data['parent_shape']
        return None
    
    def get_siblings(self, polygon_data):
        """Get all sibling polygons (same parent) for a given polygon"""
        if 'group_id' not in polygon_data:
            return []
        
        group_info = self.get_polygon_group_by_id(polygon_data['group_id'])
        if group_info:
            return group_info['polygons']
        return []
    
    def regenerate_group(self, group_id, new_parent_points=None):
        """Regenerate all polygons in a group with optionally modified parent shape"""
        group_info = self.get_polygon_group_by_id(group_id)
        if not group_info:
            return False
        
        # Remove old polygons from the main list
        old_polygons = group_info['polygons']
        for old_poly in old_polygons:
            if old_poly in self.polygons:
                self.polygons.remove(old_poly)
        
        # Use new parent points if provided, otherwise use original
        if new_parent_points is None:
            new_parent_points = group_info['parent_shape']['points']
        else:
            # Update the parent shape with the new points
            group_info['parent_shape']['points'] = new_parent_points[:]
        
        # Temporarily set polygon_points to regenerate
        old_points = self.polygon_points
        old_num_copies = self.num_copies
        
        self.polygon_points = new_parent_points
        self.num_copies = group_info['parent_shape']['num_copies']
        
        # Create new polygons
        self.create_radial_polygons()
        
        # Restore original settings
        self.polygon_points = old_points
        self.num_copies = old_num_copies
        
        return True
    
    def get_average_color_from_background(self, world_points):
        """Get average color from background image at polygon area"""
        if not self.background_image or self.background_image.isNull():
            return QColor(128, 128, 128, 255)  # Default gray, fully opaque if no image
        
        try:
            # Convert QPixmap to QImage for pixel access
            background_image = self.background_image.toImage()
            
            # Convert world coordinates to image coordinates
            image_points = []
            for world_x, world_y in world_points:
                # Account for image offset
                image_x = world_x - self.image_offset_x
                image_y = world_y - self.image_offset_y
                image_points.append((int(image_x), int(image_y)))
            
            # Find bounding box of the polygon
            if not image_points:
                return QColor(128, 128, 128, 100)
            
            min_x = max(0, min(x for x, y in image_points))
            max_x = min(background_image.width() - 1, max(x for x, y in image_points))
            min_y = max(0, min(y for x, y in image_points))
            max_y = min(background_image.height() - 1, max(y for x, y in image_points))
            
            # Sample pixels within the polygon bounding box
            red_sum = green_sum = blue_sum = pixel_count = 0
            
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    # Simple point-in-polygon test using the bounding box
                    if self.point_in_polygon(x, y, image_points):
                        pixel = background_image.pixel(x, y)
                        red_sum += (pixel >> 16) & 0xFF
                        green_sum += (pixel >> 8) & 0xFF
                        blue_sum += pixel & 0xFF
                        pixel_count += 1
            
            if pixel_count > 0:
                # Calculate average color
                avg_red = red_sum // pixel_count
                avg_green = green_sum // pixel_count
                avg_blue = blue_sum // pixel_count
                return QColor(avg_red, avg_green, avg_blue, 255)  # Fully opaque
            else:
                return QColor(128, 128, 128, 255)  # Default gray, fully opaque
                
        except Exception as e:
            print(f"Error sampling background color: {e}")
            return QColor(128, 128, 128, 255)  # Default gray, fully opaque on error
    
    def point_in_polygon(self, x, y, polygon_points):
        """Simple point-in-polygon test using ray casting algorithm"""
        if len(polygon_points) < 3:
            return False
        
        inside = False
        j = len(polygon_points) - 1
        
        for i in range(len(polygon_points)):
            xi, yi = polygon_points[i]
            xj, yj = polygon_points[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def mousePressEvent(self, event):
        """Handle mouse press events"""
        # Ensure canvas has focus for keyboard events
        self.setFocus()
        
        if event.button() == Qt.LeftButton and self.polygon_mode:
            # In polygon mode, left click adds point to polygon
            self.add_polygon_point(event.x(), event.y())
        elif event.button() == Qt.RightButton and self.polygon_mode:
            # Right click finishes the polygon
            self.finish_polygon()
        elif event.button() == Qt.LeftButton and not self.polygon_mode:
            # Check for eraser mode first
            if self.eraser_mode:
                world_x, world_y = self.screen_to_world(event.x(), event.y())
                self.erase_polygon_at_point(world_x, world_y)
                self.is_erasing = True  # Start erasing mode for drag
                return
            
            # Check for drag handle click
            if self.is_point_in_drag_handle(event.x(), event.y()):
                # Start dragging center point
                self.is_dragging_center = True
                self.setCursor(Qt.ClosedHandCursor)
                return
            elif self.is_point_in_image_drag_handle(event.x(), event.y()):
                # Start dragging image
                self.is_dragging_image = True
                self.image_drag_start_offset_x = self.image_offset_x
                self.image_drag_start_offset_y = self.image_offset_y
                self.last_pan_point = event.pos()
                self.setCursor(Qt.ClosedHandCursor)
                return
            
            # In selection mode, check for control point clicks
            control_point_index = self.find_control_point_at_screen_pos(event.x(), event.y())
            
            if control_point_index >= 0:
                # Start dragging control point
                self.selected_control_point = control_point_index
                self.is_dragging_control_point = True
                self.setCursor(Qt.ClosedHandCursor)
                self.update()
            else:
                # Check for polygon selection
                world_x, world_y = self.screen_to_world(event.x(), event.y())
                self.select_polygon_at_point(world_x, world_y)
        elif event.button() == Qt.MiddleButton:
            # Start panning
            self.is_panning = True
            self.last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events"""
        if self.is_erasing:
            # Continue erasing while dragging
            world_x, world_y = self.screen_to_world(event.x(), event.y())
            self.erase_polygon_at_point(world_x, world_y)
        elif self.is_dragging_center:
            # Drag center point by converting screen movement to world offset
            world_x, world_y = self.screen_to_world(event.x(), event.y())
            
            # Calculate base center position (canvas center without offset)
            canvas_center_screen_x = self.width() / 2
            canvas_center_screen_y = self.height() / 2
            base_center_x, base_center_y = self.screen_to_world(canvas_center_screen_x, canvas_center_screen_y)
            
            # Calculate new offset from dragged position
            new_offset_x = world_x - base_center_x
            new_offset_y = world_y - base_center_y
            
            # Update center offset and mandala center
            self.center_offset_x = new_offset_x
            self.center_offset_y = new_offset_y
            self.update_mandala_center()
            self.update()
            
        elif self.is_dragging_image:
            # Drag image by converting screen movement to world offset
            if self.last_pan_point:
                delta = event.pos() - self.last_pan_point
                # Convert screen delta to world delta (accounting for zoom)
                world_delta_x = delta.x() / self.zoom_factor
                world_delta_y = delta.y() / self.zoom_factor
                
                # Update image offset
                self.image_offset_x += world_delta_x
                self.image_offset_y += world_delta_y
                self.last_pan_point = event.pos()
                self.update()
            
        elif self.is_dragging_control_point and self.selected_control_point >= 0:
            # Drag control point to reshape polygon
            world_x, world_y = self.screen_to_world(event.x(), event.y())
            
            # Update only the control point position of the primary selected polygon
            if (self.selected_polygon_index >= 0 and 
                self.selected_polygon_index < len(self.polygons)):
                
                polygon_data = self.polygons[self.selected_polygon_index]
                points = polygon_data['points']
                
                if self.selected_control_point < len(points):
                    # Update only the selected control point in the primary polygon
                    points[self.selected_control_point] = (world_x, world_y)
                    self.update()
                    
        elif self.is_panning and self.last_pan_point:
            # Update pan offset
            delta = event.pos() - self.last_pan_point
            self.pan_offset_x += delta.x()
            self.pan_offset_y += delta.y()
            self.last_pan_point = event.pos()
            self.update()
        elif self.polygon_mode:
            # Update cursor position for polygon mode
            self.update()
        else:
            # Check if hovering over drag handles and update cursor
            if (not self.is_dragging_control_point and 
                not self.is_panning):
                
                if self.is_point_in_drag_handle(event.x(), event.y()):
                    self.setCursor(Qt.OpenHandCursor)
                elif (self.background_image and 
                      self.is_point_in_image_drag_handle(event.x(), event.y())):
                    self.setCursor(Qt.OpenHandCursor)
                elif not self.polygon_mode and not self.eraser_mode:
                    self.setCursor(Qt.ArrowCursor)
                elif self.eraser_mode and not self.polygon_mode:
                    self.setCursor(Qt.PointingHandCursor)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events"""
        if self.is_erasing:
            # Stop erasing
            self.is_erasing = False
        elif self.is_dragging_center:
            # Stop dragging center
            self.is_dragging_center = False
            self.setCursor(Qt.ArrowCursor if not self.polygon_mode else Qt.BlankCursor)
        elif self.is_dragging_control_point:
            # When control point dragging is complete, update copies in mandala mode
            if (self.mandala_mode and len(self.selected_polygon_indices) > 1 and 
                self.selected_polygon_index >= 0 and self.selected_control_point >= 0):
                
                # Get the final position of the dragged control point
                polygon_data = self.polygons[self.selected_polygon_index]
                points = polygon_data['points']
                
                if self.selected_control_point < len(points):
                    final_x, final_y = points[self.selected_control_point]
                    self.update_corresponding_points_in_copies(final_x, final_y)
                    self.update()  # Force a redraw
            
            # Stop dragging control point
            self.is_dragging_control_point = False
            self.selected_control_point = -1
            self.setCursor(Qt.ArrowCursor)
        elif self.is_dragging_image:
            self.is_dragging_image = False
            self.last_pan_point = None
            self.setCursor(Qt.ArrowCursor)
        elif self.is_panning:
            self.is_panning = False
            self.last_pan_point = None
            self.setCursor(Qt.ArrowCursor if not self.polygon_mode else Qt.BlankCursor)
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming"""
        # Get mouse position before zoom
        mouse_pos = event.pos()
        old_world_x, old_world_y = self.screen_to_world(mouse_pos.x(), mouse_pos.y())
        
        # Update zoom factor
        zoom_in = event.angleDelta().y() > 0
        zoom_factor = 1.25 if zoom_in else 0.8
        
        # Limit zoom range
        new_zoom = self.zoom_factor * zoom_factor
        if 0.1 <= new_zoom <= 10.0:
            self.zoom_factor = new_zoom
            
            # Adjust pan offset to keep mouse position fixed
            new_screen_x, new_screen_y = self.world_to_screen(old_world_x, old_world_y)
            self.pan_offset_x += mouse_pos.x() - new_screen_x
            self.pan_offset_y += mouse_pos.y() - new_screen_y
            
            self.update()
    
    def keyPressEvent(self, event):
        """Handle key press events"""
        if event.key() == Qt.Key_Escape:
            # Escape key releases polygon mode
            if self.polygon_mode:
                self.polygon_mode = False
                self.polygon_points = []  # Clear any in-progress polygon
                self.setCursor(Qt.ArrowCursor)
                self.cursor_timer.stop()
                self.update()
                
                # Find and update the checkbox - look for it in the widget hierarchy
                parent = self.parent()
                while parent:
                    # Look for SidePanel widgets in the parent's children
                    for child in parent.findChildren(QCheckBox):
                        if child.text() == "Polygon" and hasattr(child, 'setChecked'):
                            # Block signals to prevent triggering toggle_polygon_mode again
                            child.blockSignals(True)
                            child.setChecked(False)
                            child.blockSignals(False)
                            break
                    parent = parent.parent()
                    
        elif event.key() == Qt.Key_P:
            # P key toggles polygon mode
            self.toggle_polygon_mode()
            
            # Find and update the checkbox - look for it in the widget hierarchy
            parent = self.parent()
            while parent:
                # Look for SidePanel widgets in the parent's children
                for child in parent.findChildren(QCheckBox):
                    if child.text() == "Polygon" and hasattr(child, 'setChecked'):
                        # Block signals to prevent triggering toggle_polygon_mode again
                        child.blockSignals(True)
                        child.setChecked(self.polygon_mode)
                        child.blockSignals(False)
                        break
                parent = parent.parent()
                
        elif event.key() == Qt.Key_E:
            # E key toggles eraser mode
            self.set_eraser_mode(not self.eraser_mode)
            
            # Find and update the checkbox - look for it in the widget hierarchy
            parent = self.parent()
            while parent:
                # Look for SidePanel widgets in the parent's children
                for child in parent.findChildren(QCheckBox):
                    if child.text() == "Eraser Mode" and hasattr(child, 'setChecked'):
                        # Block signals to prevent triggering toggle_polygon_mode again
                        child.blockSignals(True)
                        child.setChecked(self.eraser_mode)
                        child.blockSignals(False)
                        break
                parent = parent.parent()
                    
        elif event.key() == Qt.Key_Delete:
            # Delete key removes selected polygon(s)
            if self.selected_polygon_indices:
                self.delete_selected_polygon()
        else:
            super().keyPressEvent(event)
    
    def delete_selected_polygon(self):
        """Delete the currently selected polygon(s) and update groups"""
        if not self.selected_polygon_indices:
            return
        
        # Sort indices in descending order to avoid index shifting issues when deleting
        indices_to_delete = sorted(self.selected_polygon_indices, reverse=True)
        
        # Delete polygons and track affected groups
        affected_groups = set()
        
        for index in indices_to_delete:
            if 0 <= index < len(self.polygons):
                polygon_to_delete = self.polygons[index]
                
                # Track which groups are affected
                if 'group_id' in polygon_to_delete:
                    affected_groups.add(polygon_to_delete['group_id'])
                
                # Remove from polygons list
                self.polygons.pop(index)
        
        # Update polygon groups for affected groups
        for group_id in affected_groups:
            for group in self.polygon_groups[:]:  # Use slice copy to avoid modification during iteration
                if group['group_id'] == group_id:
                    # Rebuild the group's polygon list
                    group['polygons'] = [p for p in group['polygons'] if p in self.polygons]
                    # If group is now empty, remove it
                    if not group['polygons']:
                        self.polygon_groups.remove(group)
        
        # Clear selection
        self.selected_polygon_index = -1
        self.selected_polygon_indices = []
        self.update()
    
    def erase_polygon_at_point(self, world_x, world_y):
        """Erase the specific polygon at the given point (not its copies)"""
        # Find polygon at point
        for i, polygon_data in enumerate(self.polygons):
            points = polygon_data['points']
            if self.point_in_polygon(world_x, world_y, points):
                # Remove this specific polygon
                affected_group_id = polygon_data.get('group_id')
                self.polygons.pop(i)
                
                # Update polygon groups
                if affected_group_id is not None:
                    for group in self.polygon_groups[:]:
                        if group['group_id'] == affected_group_id:
                            # Rebuild the group's polygon list
                            group['polygons'] = [p for p in group['polygons'] if p in self.polygons]
                            # If group is now empty, remove it
                            if not group['polygons']:
                                self.polygon_groups.remove(group)
                
                self.update()
                return True  # Successfully erased one polygon
        return False  # No polygon found at point
    
    def select_polygon_at_point(self, world_x, world_y):
        """Select a polygon at the given world coordinates"""
        self.selected_polygon_index = -1
        self.selected_polygon_indices = []
        
        # Check polygons in reverse order (last drawn first)
        for i in range(len(self.polygons) - 1, -1, -1):
            polygon_data = self.polygons[i]
            points = polygon_data['points']
            
            if self.point_in_polygon(world_x, world_y, points):
                self.selected_polygon_index = i
                
                # Check if this polygon is part of a mandala group
                if self.mandala_mode and 'group_id' in polygon_data:
                    # Select entire group in mandala mode
                    group_id = polygon_data['group_id']
                    self.select_polygon_group(group_id)
                else:
                    # Select only this polygon (single mode or standalone polygon)
                    self.selected_polygon_indices = [i]
                
                break
        
        self.update()
    
    def select_polygon_group(self, group_id):
        """Select all polygons in a group"""
        self.selected_polygon_indices = []
        for i, polygon_data in enumerate(self.polygons):
            if 'group_id' in polygon_data and polygon_data['group_id'] == group_id:
                self.selected_polygon_indices.append(i)
    
    def point_in_polygon(self, x, y, polygon_points):
        """Check if a point is inside a polygon using ray casting algorithm"""
        if len(polygon_points) < 3:
            return False
        
        inside = False
        j = len(polygon_points) - 1
        
        for i in range(len(polygon_points)):
            xi, yi = polygon_points[i]
            xj, yj = polygon_points[j]
            
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        
        return inside
    
    def initialize_mandala_center(self):
        """Initialize the mandala center to the current canvas center in world coordinates"""
        if self.mandala_center_world_x is None or self.mandala_center_world_y is None:
            canvas_center_screen_x = self.width() / 2
            canvas_center_screen_y = self.height() / 2
            base_x, base_y = self.screen_to_world(canvas_center_screen_x, canvas_center_screen_y)
            self.mandala_center_world_x = base_x + self.center_offset_x
            self.mandala_center_world_y = base_y + self.center_offset_y
    
    def update_mandala_center(self):
        """Update the mandala center when offsets change"""
        if self.mandala_center_world_x is not None and self.mandala_center_world_y is not None:
            canvas_center_screen_x = self.width() / 2
            canvas_center_screen_y = self.height() / 2
            base_x, base_y = self.screen_to_world(canvas_center_screen_x, canvas_center_screen_y)
            self.mandala_center_world_x = base_x + self.center_offset_x
            self.mandala_center_world_y = base_y + self.center_offset_y
    
    def paintEvent(self, event):
        """Paint the canvas"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Initialize mandala center if not set
        self.initialize_mandala_center()
        
        # Fill canvas with white background
        painter.fillRect(self.rect(), QColor(255, 255, 255))
        
        # Apply zoom and pan transformation
        painter.translate(self.pan_offset_x, self.pan_offset_y)
        painter.scale(self.zoom_factor, self.zoom_factor)
        
        # Draw background image if available and enabled
        if self.background_image and not self.background_image.isNull() and self.show_image:
            # Draw image at original size with offset, transformations will handle zoom/pan
            painter.drawPixmap(int(self.image_offset_x), int(self.image_offset_y), self.background_image)
        
        # Reset transformation for UI elements
        painter.resetTransform()
        
        # Draw center cross and circle like polygons - will sync perfectly with zoom/pan
        # Use the fixed mandala center world coordinates
        if self.mandala_center_world_x is not None and self.mandala_center_world_y is not None:
            mandala_center_world_x = self.mandala_center_world_x
            mandala_center_world_y = self.mandala_center_world_y
            
            # Define cross size in world coordinates (like polygon points)
            cross_size_world = 20.0  # Cross arm length in world units
            circle_radius_world = 15.0  # Circle radius in world units
        
        # Create cross lines as world coordinates
        # Horizontal line points
        h_line_points = [
            (mandala_center_world_x - cross_size_world, mandala_center_world_y),
            (mandala_center_world_x + cross_size_world, mandala_center_world_y)
        ]
        
        # Vertical line points
        v_line_points = [
            (mandala_center_world_x, mandala_center_world_y - cross_size_world),
            (mandala_center_world_x, mandala_center_world_y + cross_size_world)
        ]
        
        # Draw cross lines using world-to-screen conversion (like polygons do)
        painter.setPen(QPen(QColor(255, 0, 0), 2))  # Red color, thicker line
        
        # Draw horizontal line
        screen_x1, screen_y1 = self.world_to_screen(h_line_points[0][0], h_line_points[0][1])
        screen_x2, screen_y2 = self.world_to_screen(h_line_points[1][0], h_line_points[1][1])
        painter.drawLine(int(screen_x1), int(screen_y1), int(screen_x2), int(screen_y2))
        
        # Draw vertical line
        screen_x1, screen_y1 = self.world_to_screen(v_line_points[0][0], v_line_points[0][1])
        screen_x2, screen_y2 = self.world_to_screen(v_line_points[1][0], v_line_points[1][1])
        painter.drawLine(int(screen_x1), int(screen_y1), int(screen_x2), int(screen_y2))
        
        # Draw circle using world coordinates
        screen_center_x, screen_center_y = self.world_to_screen(mandala_center_world_x, mandala_center_world_y)
        screen_radius = abs(circle_radius_world * self.zoom_factor)  # Scale radius with zoom
        painter.setPen(QPen(QColor(255, 0, 0), 1))  # Red color
        painter.setBrush(QBrush(Qt.NoBrush))  # No fill
        painter.drawEllipse(int(screen_center_x - screen_radius), int(screen_center_y - screen_radius), 
                          int(screen_radius * 2), int(screen_radius * 2))
        
        # Draw completed polygons (convert world coordinates to screen)
        for i, polygon_data in enumerate(self.polygons):
            points = polygon_data['points']
            color = polygon_data['color']
            
            if len(points) >= 3:
                # Convert world coordinates to screen coordinates
                screen_points = []
                for world_x, world_y in points:
                    screen_x, screen_y = self.world_to_screen(world_x, world_y)
                    screen_points.append(QPoint(int(screen_x), int(screen_y)))
                
                qpolygon = QPolygon(screen_points)
                
                # Highlight selected polygons (individual or group)
                if i in self.selected_polygon_indices:
                    # Draw thicker red border for selected polygons
                    painter.setPen(QPen(QColor(255, 0, 0), 3))  # Red thick border
                else:
                    # Draw normal thin black border
                    painter.setPen(QPen(QColor(0, 0, 0), 1))  # Thin black pen for border
                
                painter.setBrush(QBrush(color))
                painter.drawPolygon(qpolygon)
        
        # Draw control points for the primary selected polygon
        if self.selected_polygon_index >= 0:
            self.draw_control_points(painter)
        
        # Draw debug circle dots
        self.draw_debug_circle_dots(painter)
        
        # Draw user-defined circle if enabled (in front of array)
        if self.show_circle and self.mandala_center_world_x is not None and self.mandala_center_world_y is not None:
            mandala_center_world_x = self.mandala_center_world_x
            mandala_center_world_y = self.mandala_center_world_y
            screen_center_x, screen_center_y = self.world_to_screen(mandala_center_world_x, mandala_center_world_y)
            user_circle_radius_world = self.circle_diameter / 2.0
            user_circle_screen_radius = abs(user_circle_radius_world * self.zoom_factor)
            painter.setPen(QPen(QColor(0, 0, 255), 2))  # Blue color, thicker line
            painter.setBrush(QBrush(Qt.NoBrush))  # No fill
            painter.drawEllipse(int(screen_center_x - user_circle_screen_radius), 
                              int(screen_center_y - user_circle_screen_radius), 
                              int(user_circle_screen_radius * 2), 
                              int(user_circle_screen_radius * 2))
            
            # Draw drag handle on the circle
            handle_x, handle_y = self.get_circle_drag_handle_position()
            if handle_x is not None and handle_y is not None:
                # Draw handle background (white fill with blue border)
                painter.setPen(QPen(QColor(0, 0, 255), 2))  # Blue border
                painter.setBrush(QBrush(QColor(255, 255, 255)))  # White fill
                handle_radius = self.drag_handle_size // 2
                painter.drawEllipse(int(handle_x - handle_radius), 
                                  int(handle_y - handle_radius),
                                  self.drag_handle_size, 
                                  self.drag_handle_size)
        
        # Draw drag handle on the image (bottom-left corner)
        image_handle_x, image_handle_y = self.get_image_drag_handle_position()
        if image_handle_x is not None and image_handle_y is not None:
            # Draw handle background (white fill with green border)
            painter.setPen(QPen(QColor(0, 200, 0), 2))  # Green border
            painter.setBrush(QBrush(QColor(255, 255, 255)))  # White fill
            handle_radius = self.drag_handle_size // 2
            painter.drawEllipse(int(image_handle_x - handle_radius), 
                              int(image_handle_y - handle_radius),
                              self.drag_handle_size, 
                              self.drag_handle_size)
        
        # Draw polygon cursor and current points if in polygon mode
        if self.polygon_mode:
            # Get current mouse position relative to this widget
            cursor_pos = self.mapFromGlobal(QCursor.pos())
            if self.rect().contains(cursor_pos):
                # Draw square cursor
                painter.setPen(QPen(QColor(0, 255, 0), 2))  # Green square
                painter.setBrush(QBrush(Qt.NoBrush))  # No fill
                half_size = self.polygon_cursor_size // 2
                painter.drawRect(cursor_pos.x() - half_size, 
                               cursor_pos.y() - half_size,
                               self.polygon_cursor_size, 
                               self.polygon_cursor_size)
            
            # Draw current polygon points (convert world to screen coordinates)
            if self.polygon_points:
                painter.setPen(QPen(QColor(0, 255, 0), 3))  # Green points
                painter.setBrush(QBrush(QColor(0, 255, 0)))  # Green fill
                
                # Convert world coordinates to screen coordinates for display
                screen_points = []
                for world_x, world_y in self.polygon_points:
                    screen_x, screen_y = self.world_to_screen(world_x, world_y)
                    screen_points.append((screen_x, screen_y))
                
                # Draw points
                for i, (screen_x, screen_y) in enumerate(screen_points):
                    painter.drawEllipse(int(screen_x - 3), int(screen_y - 3), 6, 6)
                    
                    # Draw point number
                    painter.setPen(QPen(QColor(255, 255, 255), 1))
                    painter.setFont(QFont('Arial', 8, QFont.Bold))
                    painter.drawText(int(screen_x + 5), int(screen_y - 5), str(i + 1))
                    painter.setPen(QPen(QColor(0, 255, 0), 3))  # Reset pen for next point
                
                # Draw lines connecting the points
                if len(screen_points) > 1:
                    painter.setPen(QPen(QColor(0, 255, 0), 2))
                    for i in range(len(screen_points) - 1):
                        x1, y1 = screen_points[i]
                        x2, y2 = screen_points[i + 1]
                        painter.drawLine(int(x1), int(y1), int(x2), int(y2))
    
    def draw_control_points(self, painter):
        """Draw control points for the selected polygon(s)"""
        if self.selected_polygon_index < 0 or self.selected_polygon_index >= len(self.polygons):
            return
        
        # In mandala mode, draw control points for all selected polygons
        if self.mandala_mode and len(self.selected_polygon_indices) > 1:
            # Draw control points for all polygons in the group
            for idx in self.selected_polygon_indices:
                if idx < len(self.polygons):
                    polygon_data = self.polygons[idx]
                    points = polygon_data['points']
                    
                    # Primary polygon (the one we clicked on) gets yellow points
                    # Copies get red points
                    is_primary = (idx == self.selected_polygon_index)
                    
                    for i, (world_x, world_y) in enumerate(points):
                        # Convert world coordinates to screen coordinates
                        screen_x, screen_y = self.world_to_screen(world_x, world_y)
                        
                        if is_primary:
                            # Primary polygon: yellow points
                            if i == self.selected_control_point:
                                painter.setPen(QPen(QColor(255, 0, 0), 3))  # Red outline for selected
                                painter.setBrush(QBrush(QColor(255, 255, 0)))  # Yellow fill
                            else:
                                painter.setPen(QPen(QColor(0, 0, 255), 2))  # Blue outline
                                painter.setBrush(QBrush(QColor(255, 255, 0)))  # Yellow fill
                        else:
                            # Copy polygons: red points
                            painter.setPen(QPen(QColor(128, 0, 0), 2))  # Dark red outline
                            painter.setBrush(QBrush(QColor(255, 0, 0)))  # Red fill
                        
                        # Draw the control point circle
                        half_size = self.control_point_size // 2
                        painter.drawEllipse(int(screen_x - half_size), int(screen_y - half_size),
                                          self.control_point_size, self.control_point_size)
        else:
            # Single polygon mode or no group - draw yellow points as before
            polygon_data = self.polygons[self.selected_polygon_index]
            points = polygon_data['points']
            
            # Draw control points as yellow dots with blue outline
            for i, (world_x, world_y) in enumerate(points):
                # Convert world coordinates to screen coordinates
                screen_x, screen_y = self.world_to_screen(world_x, world_y)
                
                # Highlight selected control point
                if i == self.selected_control_point:
                    painter.setPen(QPen(QColor(255, 0, 0), 3))  # Red outline for selected
                    painter.setBrush(QBrush(QColor(255, 255, 0)))  # Yellow fill
                else:
                    painter.setPen(QPen(QColor(0, 0, 255), 2))  # Blue outline
                    painter.setBrush(QBrush(QColor(255, 255, 0)))  # Yellow fill
                
                # Draw the control point circle
                half_size = self.control_point_size // 2
                painter.drawEllipse(int(screen_x - half_size), int(screen_y - half_size),
                                  self.control_point_size, self.control_point_size)

    def draw_debug_circle_dots(self, painter):
        """Draw debug dots showing the circular positions"""
        if not hasattr(self, 'debug_circle_dots') or not self.debug_circle_dots:
            return
            
        # Draw bright green dots for the calculated circular positions
        painter.setPen(QPen(QColor(0, 255, 0), 3))  # Bright green outline
        painter.setBrush(QBrush(QColor(0, 255, 0)))  # Green fill
        
        for world_x, world_y in self.debug_circle_dots:
            # Convert world coordinates to screen coordinates
            screen_x, screen_y = self.world_to_screen(world_x, world_y)
            
            # Draw a larger dot so it's clearly visible
            dot_size = 10
            half_size = dot_size // 2
            painter.drawEllipse(int(screen_x - half_size), int(screen_y - half_size),
                              dot_size, dot_size)

    def update_corresponding_points_in_copies(self, new_world_x, new_world_y):
        """Update the corresponding control point in all copy polygons using correct circular logic"""
        import math
        
        # Get the correct mandala center
        center_x = self.mandala_center_world_x if self.mandala_center_world_x is not None else 0.0
        center_y = self.mandala_center_world_y if self.mandala_center_world_y is not None else 0.0
        
        # Calculate radius and the ACTUAL angle of the dragged point
        radius = math.sqrt((new_world_x - center_x)**2 + (new_world_y - center_y)**2)
        dragged_angle = math.atan2(new_world_y - center_y, new_world_x - center_x)
        
        # Check if we have valid selection data
        if (self.selected_polygon_index < 0 or 
            self.selected_control_point < 0 or 
            len(self.selected_polygon_indices) <= 1):
            return
            
        # Get the primary polygon data
        primary_polygon = self.polygons[self.selected_polygon_index]
        if 'group_id' not in primary_polygon:
            return
            
        # Get group info to find the number of copies
        group_info = self.get_polygon_group_by_id(primary_polygon['group_id'])
        if not group_info:
            return
            
        num_copies = group_info['parent_shape']['num_copies']
        
        # Calculate the target positions starting from the dragged point's angle
        angle_step = 2 * math.pi / num_copies
        target_positions = []
        
        for i in range(num_copies):
            # Start from the dragged point's angle and add increments
            angle = dragged_angle + (i * angle_step)
            target_x = center_x + radius * math.cos(angle)
            target_y = center_y + radius * math.sin(angle)
            target_positions.append((target_x, target_y))
        
        # Map each existing polygon to the closest target position
        # Get current positions
        current_positions = []
        for idx in self.selected_polygon_indices:
            if idx < len(self.polygons):
                polygon = self.polygons[idx]
                points = polygon['points']
                if self.selected_control_point < len(points):
                    current_pos = points[self.selected_control_point]
                    current_positions.append((idx, current_pos))
        
        used_targets = set()
        
        for poly_idx, current_pos in current_positions:
            if poly_idx == self.selected_polygon_index:
                # Primary polygon stays where user dragged it
                continue
                
            # Find the closest unused target position
            best_target_idx = None
            best_distance = float('inf')
            
            for target_idx, target_pos in enumerate(target_positions):
                if target_idx in used_targets:
                    continue
                    
                distance = math.sqrt((current_pos[0] - target_pos[0])**2 + (current_pos[1] - target_pos[1])**2)
                if distance < best_distance:
                    best_distance = distance
                    best_target_idx = target_idx
            
            if best_target_idx is not None:
                target_pos = target_positions[best_target_idx]
                used_targets.add(best_target_idx)
                
                # Update this polygon's control point
                self.polygons[poly_idx]['points'][self.selected_control_point] = target_pos
        
        # Clear debug dots since we're now actually moving the polygons
        self.debug_circle_dots = []
        
        # Force a redraw to show the updated positions
        self.update()
    
    def get_copy_rotation_angle(self, polygon_index, group_id):
        """Get the rotation angle for a specific polygon copy"""
        # Find which copy number this polygon is
        group_polygons = []
        for i, poly in enumerate(self.polygons):
            if 'group_id' in poly and poly['group_id'] == group_id:
                group_polygons.append(i)
        
        if polygon_index not in group_polygons:
            return None
            
        copy_number = group_polygons.index(polygon_index)
        
        # Get the number of copies from the group info
        group_info = self.get_polygon_group_by_id(group_id)
        if not group_info:
            return None
            
        num_copies = group_info['parent_shape']['num_copies']
        angle_step = 2 * 3.14159 / num_copies  # 2π / num_copies
        
        return copy_number * angle_step
    
    def find_control_point_at_screen_pos(self, screen_x, screen_y):
        """Find which control point is at the given screen position"""
        if self.selected_polygon_index < 0 or self.selected_polygon_index >= len(self.polygons):
            return -1
            
        polygon_data = self.polygons[self.selected_polygon_index]
        points = polygon_data['points']
        
        for i, (world_x, world_y) in enumerate(points):
            # Convert world coordinates to screen coordinates
            point_screen_x, point_screen_y = self.world_to_screen(world_x, world_y)
            
            # Check if click is within control point circle
            distance = ((screen_x - point_screen_x)**2 + (screen_y - point_screen_y)**2)**0.5
            if distance <= self.control_point_size:
                return i
                
        return -1


class SidePanel(QFrame):
    """Side panel widget"""
    
    def __init__(self, title, canvas=None):
        super().__init__()
        self.setFrameStyle(QFrame.StyledPanel)
        self.setMinimumWidth(200)
        self.setMaximumWidth(250)
        self.setStyleSheet("background-color: #f0f0f0;")
        self.canvas = canvas
        
        # Create layout for the panel
        layout = QVBoxLayout()
        
        # Add buttons for right panel
        if title == "Right Panel" and canvas:
            load_bg_button = QPushButton("Load Background")
            load_bg_button.clicked.connect(self.load_background)
            layout.addWidget(load_bg_button)
            
            # Add polygon checkbox
            self.polygon_checkbox = QCheckBox("Polygon")
            self.polygon_checkbox.toggled.connect(self.on_polygon_toggled)
            layout.addWidget(self.polygon_checkbox)
            
            # Add mandala checkbox
            self.mandala_checkbox = QCheckBox("Mandala")
            self.mandala_checkbox.setChecked(True)  # Checked by default
            self.mandala_checkbox.toggled.connect(self.on_mandala_toggled)
            layout.addWidget(self.mandala_checkbox)
            
            # Add eraser mode checkbox
            self.eraser_checkbox = QCheckBox("Eraser Mode")
            self.eraser_checkbox.toggled.connect(self.on_eraser_toggled)
            layout.addWidget(self.eraser_checkbox)
            
            # Add circle checkbox and diameter input
            self.circle_checkbox = QCheckBox("Circle")
            self.circle_checkbox.toggled.connect(self.on_circle_toggled)
            layout.addWidget(self.circle_checkbox)
            
            # Circle diameter input
            circle_label = QLabel("Diameter:")
            layout.addWidget(circle_label)
            self.circle_diameter_input = QLineEdit("1000")
            self.circle_diameter_input.textChanged.connect(self.on_circle_diameter_changed)
            layout.addWidget(self.circle_diameter_input)
            
            # Add show image checkbox
            self.show_image_checkbox = QCheckBox("Show Image")
            self.show_image_checkbox.setChecked(True)  # Checked by default
            self.show_image_checkbox.toggled.connect(self.on_show_image_toggled)
            layout.addWidget(self.show_image_checkbox)
            
            # Add save and load array buttons
            save_array_button = QPushButton("Save Array")
            save_array_button.clicked.connect(self.save_array)
            layout.addWidget(save_array_button)
            
            load_array_button = QPushButton("Load Array")
            load_array_button.clicked.connect(self.load_array)
            layout.addWidget(load_array_button)
            
            # Add number of copies control
            copies_label = QLabel("Radial Copies:")
            copies_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            layout.addWidget(copies_label)
            
            self.copies_input = QLineEdit()
            self.copies_input.setText("6")  # Default value
            self.copies_input.setPlaceholderText("Enter number (1-36)")
            self.copies_input.textChanged.connect(self.on_copies_changed)
            layout.addWidget(self.copies_input)
        
        # Add stretch to push content to top
        layout.addStretch()
        
        self.setLayout(layout)
    
    def load_background(self):
        """Load background image for canvas"""
        if not self.canvas:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Background Image",
            "",
            "Image files (*.png *.jpg *.jpeg *.bmp *.tiff *.gif);;All files (*.*)"
        )
        
        if file_path:
            # Ask for desired size of the longer side
            size, ok = QInputDialog.getInt(
                self,
                "Image Size",
                "Enter the desired length for the longer side (pixels):",
                value=1000,  # Default value
                min=100,     # Minimum value
                max=10000,   # Maximum value
                step=100     # Step size
            )
            
            if ok:
                self.canvas.set_background_image(file_path, desired_size=size)
            else:
                # User cancelled size dialog, load with original size
                self.canvas.set_background_image(file_path)
    
    def on_polygon_toggled(self, checked):
        """Handle polygon checkbox toggle"""
        if self.canvas:
            self.canvas.toggle_polygon_mode()
    
    def on_mandala_toggled(self, checked):
        """Handle mandala checkbox toggle"""
        if self.canvas:
            self.canvas.set_mandala_mode(checked)
    
    def on_eraser_toggled(self, checked):
        """Handle eraser mode checkbox toggle"""
        if self.canvas:
            self.canvas.set_eraser_mode(checked)
    
    def on_circle_toggled(self, checked):
        """Handle circle checkbox toggle"""
        if self.canvas:
            self.canvas.set_circle_visible(checked)
    
    def on_circle_diameter_changed(self, text):
        """Handle circle diameter input change"""
        if self.canvas:
            try:
                diameter = float(text) if text else 1000
                self.canvas.set_circle_diameter(diameter)
            except ValueError:
                # Invalid number, ignore or use default
                pass
    
    def on_show_image_toggled(self, checked):
        """Handle show image checkbox toggle"""
        if self.canvas:
            self.canvas.set_image_visible(checked)
    
    def on_copies_changed(self):
        """Handle copies input text changes"""
        if self.canvas:
            try:
                # Parse the input and validate range
                num_copies = int(self.copies_input.text())
                num_copies = max(1, min(36, num_copies))  # Clamp between 1 and 36
                self.canvas.set_num_copies(num_copies)
                
                # Update the input field if we clamped the value
                if str(num_copies) != self.copies_input.text():
                    self.copies_input.setText(str(num_copies))
                    
            except ValueError:
                # Invalid input, reset to default
                self.canvas.set_num_copies(6)
                if self.copies_input.text() == "":  # Don't reset while user is typing
                    self.copies_input.setText("6")
    
    def save_array(self):
        """Save polygons to CSV file compatible with mosaic_editor_pyqt"""
        if not self.canvas or not self.canvas.polygons:
            QMessageBox.warning(self, "Warning", "No polygons to save.")
            return
        
        # Open file dialog to choose save location
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Array as CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header with alpha channel support (compatible with mosaic_editor_pyqt)
                writer.writerow(['polygon_id', 'coordinates', 'color_r', 'color_g', 'color_b', 'color_a'])
                
                # Write each polygon
                for i, polygon_data in enumerate(self.canvas.polygons):
                    points = polygon_data['points']
                    color = polygon_data['color']
                    
                    # Convert points to JSON string format (same as mosaic_editor_pyqt)
                    coords_json = json.dumps([[float(x), float(y)] for x, y in points])
                    
                    # Extract RGBA values (convert from QColor to 0-1 range)
                    r = color.red() / 255.0
                    g = color.green() / 255.0
                    b = color.blue() / 255.0
                    a = color.alpha() / 255.0
                    
                    # Write row
                    writer.writerow([i, coords_json, r, g, b, a])
            
            QMessageBox.information(
                self, 
                "Success", 
                f"Saved {len(self.canvas.polygons)} polygons to {filename}"
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save array: {str(e)}")
    
    def load_array(self):
        """Load polygons from CSV file compatible with mosaic_editor_pyqt"""
        if not self.canvas:
            return
            
        # Open file dialog to choose file
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Array from CSV",
            "",
            "CSV Files (*.csv);;All Files (*)"
        )
        
        if not filename:
            return  # User cancelled
        
        try:
            polygons = []
            
            with open(filename, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                for row_num, row in enumerate(reader, 1):
                    try:
                        # Parse coordinates - handle JSON array format
                        coords_str = row['coordinates'] if 'coordinates' in row else row.get('polygon_coords', '')
                        
                        # Remove quotes and parse as JSON
                        coords_str = coords_str.strip('"\'')
                        
                        try:
                            coord_list = json.loads(coords_str)
                            points = [(float(point[0]), float(point[1])) for point in coord_list]
                        except:
                            # Fallback to ast parsing for backward compatibility
                            import ast
                            coord_list = ast.literal_eval(coords_str)
                            points = [(float(point[0]), float(point[1])) for point in coord_list]
                        
                        if len(points) < 3:
                            continue
                        
                        # Parse color - handle separate R,G,B columns
                        if 'color_r' in row and 'color_g' in row and 'color_b' in row:
                            r = float(row['color_r'])
                            g = float(row['color_g'])
                            b = float(row['color_b'])
                            
                            # Check for alpha channel
                            if 'color_a' in row:
                                a = float(row['color_a'])
                                a = int(a * 255) if a <= 1.0 else int(a)
                            else:
                                a = 255  # Default to fully opaque
                            
                            # Convert from 0-1 range to 0-255
                            r = int(r * 255) if r <= 1.0 else int(r)
                            g = int(g * 255) if g <= 1.0 else int(g)
                            b = int(b * 255) if b <= 1.0 else int(b)
                            
                            color = QColor(r, g, b, a)
                        else:
                            # Default color if no color data
                            color = QColor(100, 100, 100)
                        
                        # Create polygon data structure
                        polygon_data = {
                            'points': points,
                            'color': color
                        }
                        polygons.append(polygon_data)
                        
                    except Exception as e:
                        print(f"Error parsing row {row_num}: {e}")
                        continue
            
            if polygons:
                # Clear existing polygons and load new ones
                self.canvas.polygons = polygons
                self.canvas.update()
                
                QMessageBox.information(
                    self, 
                    "Success", 
                    f"Loaded {len(polygons)} polygons from {filename}"
                )
            else:
                QMessageBox.warning(self, "Warning", "No valid polygons found in the file.")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load array: {str(e)}")


class MandalaMosaicWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        self.initUI()
    
    def initUI(self):
        """Initialize the user interface"""
        self.setWindowTitle("Mandala Mosaic")
        self.setGeometry(100, 100, 1200, 800)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Create left panel
        left_panel = SidePanel("Left Panel")
        main_layout.addWidget(left_panel)
        
        # Create central canvas
        canvas = Canvas()
        main_layout.addWidget(canvas, 1)  # Give canvas stretch factor of 1
        
        # Create right panel (with reference to canvas for background loading)
        right_panel = SidePanel("Right Panel", canvas)
        main_layout.addWidget(right_panel)
        
        central_widget.setLayout(main_layout)


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    # Create and show the main window
    window = MandalaMosaicWindow()
    window.show()
    
    # Start the event loop
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
