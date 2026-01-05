import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFrame, QMessageBox,
    QScrollArea, QSizePolicy, QLineEdit
)
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPixmap, QImage, QFont
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog, QPrintPreviewDialog


class ImagePreviewWidget(QWidget):
    """Widget for displaying and previewing the image with print boundaries"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image = None
        self.print_rect = QRectF(0, 0, 100, 100)  # Default print area
        self.scale_factor = 1.0
        self.show_print_area = True
        self.setMinimumSize(400, 300)

    def set_image(self, image_path):
        """Load and display an image"""
        self.image = QPixmap(image_path)
        if not self.image.isNull():
            self.update()
        else:
            QMessageBox.warning(self, "Error", "Failed to load image")

    def set_print_properties(self, paper_size, orientation, margins, scale):
        """Update print area based on properties"""
        # Convert paper size to pixels (assuming 300 DPI)
        dpi = 300
        if paper_size == "A4":
            if orientation == "Portrait":
                width = int(8.27 * dpi)  # A4 width in inches
                height = int(11.69 * dpi)  # A4 height in inches
            else:  # Landscape
                width = int(11.69 * dpi)
                height = int(8.27 * dpi)
        elif paper_size == "Letter":
            if orientation == "Portrait":
                width = int(8.5 * dpi)
                height = int(11 * dpi)
            else:
                width = int(11 * dpi)
                height = int(8.5 * dpi)
        elif paper_size == "A3":
            if orientation == "Portrait":
                width = int(11.69 * dpi)
                height = int(16.54 * dpi)
            else:
                width = int(16.54 * dpi)
                height = int(11.69 * dpi)

        # Apply margins
        margin_pixels = int(margins * dpi / 25.4)  # Convert mm to pixels
        print_width = width - 2 * margin_pixels
        print_height = height - 2 * margin_pixels

        self.print_rect = QRectF(margin_pixels, margin_pixels, print_width, print_height)
        self.scale_factor = scale / 100.0
        self.update()

    def paintEvent(self, event):
        """Draw the image and print boundaries"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.image and not self.image.isNull():
            # Calculate scaled image size
            scaled_width = self.image.width() * self.scale_factor
            scaled_height = self.image.height() * self.scale_factor

            # Center the image in the widget
            widget_width = self.width()
            widget_height = self.height()

            x = (widget_width - scaled_width) / 2
            y = (widget_height - scaled_height) / 2

            # Draw the scaled image
            painter.drawPixmap(int(x), int(y), self.image.scaled(
                int(scaled_width), int(scaled_height),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))

            # Draw print area boundary if enabled
            if self.show_print_area:
                painter.setPen(Qt.red)
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(self.print_rect.toRect())

                # Draw print area info
                painter.setPen(Qt.blue)
                font = painter.font()
                font.setPointSize(8)
                painter.setFont(font)
                info_text = f"Print Area: {self.print_rect.width():.0f} x {self.print_rect.height():.0f} pixels"
                painter.drawText(10, 20, info_text)


class PrintPropertiesWidget(QWidget):
    """Widget for setting print properties"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.image_preview = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface"""
        layout = QVBoxLayout()

        # Image loading section
        load_group = QGroupBox("Image")
        load_layout = QHBoxLayout()

        self.load_button = QPushButton("Load Image")
        self.load_button.clicked.connect(self.load_image)
        load_layout.addWidget(self.load_button)

        self.image_path_label = QLabel("No image loaded")
        load_layout.addWidget(self.image_path_label)

        load_group.setLayout(load_layout)
        layout.addWidget(load_group)

        # Print properties section
        properties_group = QGroupBox("Print Properties")
        properties_layout = QVBoxLayout()

        # Paper size
        paper_layout = QHBoxLayout()
        paper_layout.addWidget(QLabel("Paper Size:"))
        self.paper_size_combo = QComboBox()
        self.paper_size_combo.addItems(["A4", "A3", "Letter"])
        self.paper_size_combo.currentTextChanged.connect(self.update_preview)
        paper_layout.addWidget(self.paper_size_combo)
        properties_layout.addLayout(paper_layout)

        # Orientation
        orientation_layout = QHBoxLayout()
        orientation_layout.addWidget(QLabel("Orientation:"))
        self.orientation_combo = QComboBox()
        self.orientation_combo.addItems(["Portrait", "Landscape"])
        self.orientation_combo.currentTextChanged.connect(self.update_preview)
        orientation_layout.addWidget(self.orientation_combo)
        properties_layout.addLayout(orientation_layout)

        # Scale mode selection
        scale_mode_layout = QHBoxLayout()
        scale_mode_layout.addWidget(QLabel("Scale Mode:"))
        self.scale_mode_combo = QComboBox()
        self.scale_mode_combo.addItems(["Percentage", "Width (mm)"])
        self.scale_mode_combo.currentTextChanged.connect(self.on_scale_mode_changed)
        scale_mode_layout.addWidget(self.scale_mode_combo)
        properties_layout.addLayout(scale_mode_layout)

        # Scale percentage (shown when Percentage mode is selected)
        self.scale_percent_widget = QWidget()
        self.scale_percent_layout = QHBoxLayout(self.scale_percent_widget)
        self.scale_percent_layout.addWidget(QLabel("Scale (%):"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(10, 500)
        self.scale_spin.setValue(100)
        self.scale_spin.setSingleStep(5)
        self.scale_spin.valueChanged.connect(self.update_preview)
        self.scale_percent_layout.addWidget(self.scale_spin)
        properties_layout.addWidget(self.scale_percent_widget)

        # Printed width in mm (shown when Width mode is selected)
        self.scale_width_widget = QWidget()
        self.scale_width_layout = QHBoxLayout(self.scale_width_widget)
        self.scale_width_layout.addWidget(QLabel("Printed Width (mm):"))
        
        # Text input for width
        self.width_input = QLineEdit()
        self.width_input.setText("100")
        self.width_input.setPlaceholderText("Enter width in mm")
        self.width_input.setToolTip("Enter the desired printed width in millimeters (e.g., 250)")
        self.width_input.textChanged.connect(self.on_width_text_changed)
        self.scale_width_layout.addWidget(self.width_input)
        
        # Also keep spinbox for convenience (optional - can be removed)
        self.width_spin = QDoubleSpinBox()
        self.width_spin.setRange(10, 1000)
        self.width_spin.setValue(100)
        self.width_spin.setSingleStep(10)
        self.width_spin.valueChanged.connect(self.on_width_spin_changed)
        self.scale_width_layout.addWidget(self.width_spin)
        
        properties_layout.addWidget(self.scale_width_widget)

        # Margins
        margin_layout = QHBoxLayout()
        margin_layout.addWidget(QLabel("Margins (mm):"))
        self.margin_spin = QSpinBox()
        self.margin_spin.setRange(0, 50)
        self.margin_spin.setValue(10)
        self.margin_spin.valueChanged.connect(self.update_preview)
        margin_layout.addWidget(self.margin_spin)
        properties_layout.addLayout(margin_layout)

        # Print quality
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Quality:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Draft", "Normal", "High", "Photo"])
        quality_layout.addWidget(self.quality_combo)
        properties_layout.addLayout(quality_layout)

        # Color mode
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel("Color Mode:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Color", "Grayscale", "Monochrome"])
        color_layout.addWidget(self.color_combo)
        properties_layout.addLayout(color_layout)

        # Copies
        copies_layout = QHBoxLayout()
        copies_layout.addWidget(QLabel("Copies:"))
        self.copies_spin = QSpinBox()
        self.copies_spin.setRange(1, 99)
        self.copies_spin.setValue(1)
        copies_layout.addWidget(self.copies_spin)
        properties_layout.addLayout(copies_layout)

        properties_group.setLayout(properties_layout)
        layout.addWidget(properties_group)

        # Action buttons
        actions_layout = QHBoxLayout()

        self.preview_button = QPushButton("Print Preview")
        self.preview_button.clicked.connect(self.show_print_preview)
        self.preview_button.setEnabled(False)
        actions_layout.addWidget(self.preview_button)

        self.print_button = QPushButton("Print")
        self.print_button.clicked.connect(self.print_image)
        self.print_button.setEnabled(False)
        actions_layout.addWidget(self.print_button)

        layout.addLayout(actions_layout)

        # Show print area checkbox
        self.show_area_checkbox = QCheckBox("Show Print Area")
        self.show_area_checkbox.setChecked(True)
        self.show_area_checkbox.toggled.connect(self.toggle_print_area)
        layout.addWidget(self.show_area_checkbox)

        self.setLayout(layout)

        # Initially show percentage mode
        self.on_scale_mode_changed("Percentage")

    def on_scale_mode_changed(self, mode):
        """Handle scale mode changes"""
        if mode == "Percentage":
            self.scale_percent_widget.setVisible(True)
            self.scale_width_widget.setVisible(False)
        else:  # Width (mm)
            self.scale_percent_widget.setVisible(False)
            self.scale_width_widget.setVisible(True)
        self.update_preview()

    def on_width_text_changed(self, text):
        """Handle text input changes for width"""
        try:
            width = float(text)
            if 10 <= width <= 1000:
                # Update spinbox to match (without triggering its signal)
                self.width_spin.blockSignals(True)
                self.width_spin.setValue(width)
                self.width_spin.blockSignals(False)
                # Update preview
                self.update_preview()
        except ValueError:
            # Invalid input, ignore
            pass

    def on_width_spin_changed(self, value):
        """Handle spinbox changes for width"""
        # Update text input to match (without triggering its signal)
        self.width_input.blockSignals(True)
        self.width_input.setText(str(value))
        self.width_input.blockSignals(False)
        # Update preview
        self.update_preview()

    def calculate_scale_from_width(self, desired_width_mm):
        """Calculate scale percentage from desired width in mm"""
        if not self.image_preview or not self.image_preview.image:
            return 100.0
        
        # Get printer DPI (assume 300 DPI for calculation)
        dpi = 300
        
        # Convert desired width from mm to pixels
        desired_width_pixels = desired_width_mm * dpi / 25.4  # 25.4 mm per inch
        
        # Get original image width
        image_width = self.image_preview.image.width()
        
        # Calculate scale factor
        if image_width > 0:
            scale_factor = (desired_width_pixels / image_width) * 100.0
            return max(10, min(500, scale_factor))  # Clamp to valid range
        else:
            return 100.0

    def set_preview_widget(self, preview_widget):
        """Set the preview widget reference"""
        self.image_preview = preview_widget

    def load_image(self):
        """Load an image file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Image",
            "",
            "Image files (*.png *.jpg *.jpeg *.bmp *.tiff *.gif);;All files (*.*)"
        )

        if file_path:
            self.image_path_label.setText(os.path.basename(file_path))
            if self.image_preview:
                self.image_preview.set_image(file_path)
            self.preview_button.setEnabled(True)
            self.print_button.setEnabled(True)

    def update_preview(self):
        """Update the preview with current print properties"""
        if self.image_preview:
            paper_size = self.paper_size_combo.currentText()
            orientation = self.orientation_combo.currentText()
            margins = self.margin_spin.value()
            
            # Calculate scale based on mode
            if self.scale_mode_combo.currentText() == "Percentage":
                scale = self.scale_spin.value()
            else:  # Width (mm)
                # Get width from text input
                try:
                    width_mm = float(self.width_input.text())
                    scale = self.calculate_scale_from_width(width_mm)
                except ValueError:
                    # If invalid text, use spinbox value
                    scale = self.calculate_scale_from_width(self.width_spin.value())
            
            self.image_preview.set_print_properties(paper_size, orientation, margins, scale)

    def toggle_print_area(self, show):
        """Toggle display of print area boundary"""
        if self.image_preview:
            self.image_preview.show_print_area = show
            self.image_preview.update()

    def show_print_preview(self):
        """Show print preview dialog"""
        if not self.image_preview or not self.image_preview.image:
            return

        printer = QPrinter(QPrinter.HighResolution)
        self.setup_printer(printer)

        preview = QPrintPreviewDialog(printer, self)
        preview.paintRequested.connect(self.render_for_print)
        preview.exec_()

    def print_image(self):
        """Print the image with current settings"""
        if not self.image_preview or not self.image_preview.image:
            return

        printer = QPrinter(QPrinter.HighResolution)
        self.setup_printer(printer)

        dialog = QPrintDialog(printer, self)
        if dialog.exec_() == QPrintDialog.Accepted:
            self.render_for_print(printer)

    def setup_printer(self, printer):
        """Configure printer with current settings"""
        # Paper size
        paper_size = self.paper_size_combo.currentText()
        if paper_size == "A4":
            printer.setPageSize(QPrinter.A4)
        elif paper_size == "A3":
            printer.setPageSize(QPrinter.A3)
        elif paper_size == "Letter":
            printer.setPageSize(QPrinter.Letter)

        # Orientation
        if self.orientation_combo.currentText() == "Landscape":
            printer.setOrientation(QPrinter.Landscape)
        else:
            printer.setOrientation(QPrinter.Portrait)

        # Quality
        quality = self.quality_combo.currentText()
        if quality == "Draft":
            printer.setResolution(150)
        elif quality == "Normal":
            printer.setResolution(300)
        elif quality == "High":
            printer.setResolution(600)
        elif quality == "Photo":
            printer.setResolution(1200)

        # Color mode
        color_mode = self.color_combo.currentText()
        if color_mode == "Grayscale":
            printer.setColorMode(QPrinter.GrayScale)
        else:
            printer.setColorMode(QPrinter.Color)

        # Copies
        printer.setCopyCount(self.copies_spin.value())

        # Margins
        margins = self.margin_spin.value()
        printer.setPageMargins(margins, margins, margins, margins, QPrinter.Millimeter)

    def render_for_print(self, printer):
        """Render the image for printing"""
        if not self.image_preview or not self.image_preview.image:
            return

        painter = QPainter(printer)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # Get the print rectangle
        rect = printer.pageRect()

        # Calculate scaled image size
        if self.scale_mode_combo.currentText() == "Percentage":
            scale = self.scale_spin.value() / 100.0
        else:  # Width (mm)
            # Get width from text input
            try:
                width_mm = float(self.width_input.text())
                scale = self.calculate_scale_from_width(width_mm) / 100.0
            except ValueError:
                # If invalid text, use spinbox value
                scale = self.calculate_scale_from_width(self.width_spin.value()) / 100.0
        
        scaled_width = self.image_preview.image.width() * scale
        scaled_height = self.image_preview.image.height() * scale

        # Center the image on the page
        x = (rect.width() - scaled_width) / 2
        y = (rect.height() - scaled_height) / 2

        # Draw the scaled image
        painter.drawPixmap(int(x), int(y), self.image_preview.image.scaled(
            int(scaled_width), int(scaled_height),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        ))

        painter.end()


class PrinterMainWindow(QMainWindow):
    """Main window for the image printing editor"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Print Editor")
        self.setGeometry(100, 100, 1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Create main layout
        main_layout = QHBoxLayout(central_widget)

        # Create preview widget
        self.preview_widget = ImagePreviewWidget()
        main_layout.addWidget(self.preview_widget, 2)  # 2/3 of width

        # Create properties widget
        self.properties_widget = PrintPropertiesWidget()
        self.properties_widget.set_preview_widget(self.preview_widget)
        main_layout.addWidget(self.properties_widget, 1)  # 1/3 of width

        # Set size policies
        self.preview_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.properties_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.properties_widget.setFixedWidth(300)


def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Modern look

    window = PrinterMainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()