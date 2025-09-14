// Debug logging function
function debugLog(message) {
    var debugElement = document.getElementById('debugLog');
    var timestamp = new Date().toLocaleTimeString();
    debugElement.textContent += '[' + timestamp + '] ' + message + '\n';
    debugElement.scrollTop = debugElement.scrollHeight;
}

function clearDebug() {
    document.getElementById('debugLog').textContent = 'Debug log cleared...\n';
}

// CSV loading functions
function parseCSVRowJS(csvText) {
    var rows = [];
    var lines = csvText.split('\n');
    
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line) {
            var fields = [];
            var current = '';
            var inQuotes = false;
            
            for (var j = 0; j < line.length; j++) {
                var char = line[j];
                if (char === '"') {
                    inQuotes = !inQuotes;
                } else if (char === ',' && !inQuotes) {
                    fields.push(current.trim());
                    current = '';
                } else {
                    current += char;
                }
            }
            fields.push(current.trim());
            rows.push(fields);
        }
    }
    return rows;
}

function loadCSV(event) {
    var file = event.target.files[0];
    if (!file) return;
    
    debugLog('Loading CSV file: ' + file.name);
    var reader = new FileReader();
    
    reader.onload = function(e) {
        var csvText = e.target.result;
        debugLog('File loaded, size: ' + csvText.length + ' characters');
        
        try {
            var rows = parseCSVRowJS(csvText);
            debugLog('Parsed ' + rows.length + ' rows');
            
            var polygonsLoaded = 0;
            
            for (var i = 0; i < rows.length; i++) {
                if (rows[i].length >= 4) {
                    try {
                        var polygonStr = rows[i][0];
                        var r = parseInt(rows[i][1]) || 0;
                        var g = parseInt(rows[i][2]) || 0;
                        var b = parseInt(rows[i][3]) || 0;
                        
                        var coords = [];
                        var coordPairs = polygonStr.replace(/[()]/g, '').split(',');
                        
                        for (var k = 0; k < coordPairs.length; k += 2) {
                            if (k + 1 < coordPairs.length) {
                                var x = parseFloat(coordPairs[k].trim());
                                var y = parseFloat(coordPairs[k + 1].trim());
                                if (!isNaN(x) && !isNaN(y)) {
                                    coords.push([x, y]);
                                }
                            }
                        }
                        
                        if (coords.length >= 3 && window.paperFunctions) {
                            if (window.paperFunctions.createPolygon(coords, r, g, b)) {
                                polygonsLoaded++;
                            }
                        }
                    } catch (error) {
                        console.error('Error processing row', i, ':', error);
                        debugLog('Error processing row ' + i + ': ' + error.message);
                    }
                }
            }
            
            debugLog('Successfully loaded ' + polygonsLoaded + ' polygons');
        } catch (error) {
            console.error('Error parsing CSV:', error);
            debugLog('Error parsing CSV: ' + error.message);
        }
    };
    
    reader.readAsText(file);
}

function updateGrid() {
    var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
    if (window.paperFunctions && window.paperFunctions.drawGrid) {
        window.paperFunctions.drawGrid(tileSize);
    }
}

function addColumn() {
    if (window.paperFunctions && window.paperFunctions.addColumn) {
        window.paperFunctions.addColumn();
    }
}

function removeColumn() {
    if (window.paperFunctions && window.paperFunctions.removeColumn) {
        window.paperFunctions.removeColumn();
    }
}

function addRow() {
    if (window.paperFunctions && window.paperFunctions.addRow) {
        window.paperFunctions.addRow();
    }
}

function removeRow() {
    if (window.paperFunctions && window.paperFunctions.removeRow) {
        window.paperFunctions.removeRow();
    }
}

// Paper.js initialization and functions
function initializePaper() {
    // These variables will be in the Paper.js scope
    var polygonPaths = [];
    var showEdges = false;
    var bounds = null;
    var gridLines = [];
    var gridBackground = null;
    var gridColumns = 10;
    var gridRows = 7;
    var canvasWidth = 900;
    var canvasHeight = 600;

    // Set canvas background to white
    paper.project.view.element.style.backgroundColor = '#ffffff';

    // Create global functions accessible from regular JavaScript
    window.paperFunctions = {
        updatePolygonPositions: function() {
            // Get current tile size and grid dimensions
            var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
            var worldWidth = gridColumns * tileSize;
            var worldHeight = gridRows * tileSize;
            
            // Calculate scaling factors to fit canvas while maintaining aspect ratio
            var scaleX = canvasWidth / worldWidth;
            var scaleY = canvasHeight / worldHeight;
            var scale = Math.min(scaleX, scaleY);
            
            // Calculate display dimensions and offset for centering
            var displayWidth = worldWidth * scale;
            var displayHeight = worldHeight * scale;
            var offsetX = (canvasWidth - displayWidth) / 2;
            var offsetY = (canvasHeight - displayHeight) / 2;
            
            console.log('Updating', polygonPaths.length, 'polygons with new scale:', scale);
            
            // Update each polygon's position based on its original world coordinates
            for (var i = 0; i < polygonPaths.length; i++) {
                var path = polygonPaths[i];
                if (path.originalCoords) {
                    // Store the current visual properties before clearing segments
                    var fillColor = path.fillColor ? path.fillColor.clone() : null;
                    var strokeColor = path.strokeColor ? path.strokeColor.clone() : null;
                    var strokeWidth = path.strokeWidth;
                    var closed = path.closed;
                    
                    // Clear the path and recreate it with new coordinates
                    path.removeSegments();
                    
                    for (var j = 0; j < path.originalCoords.length; j++) {
                        var worldX = path.originalCoords[j][0];
                        var worldY = path.originalCoords[j][1];
                        var screenX = offsetX + (worldX * scale);
                        var screenY = offsetY + (worldY * scale);
                        path.add(new paper.Point(screenX, screenY));
                    }
                    
                    // Restore the visual properties
                    path.closed = closed;
                    if (fillColor) path.fillColor = fillColor;
                    if (strokeColor) path.strokeColor = strokeColor;
                    if (strokeWidth) path.strokeWidth = strokeWidth;
                    
                    // Ensure the polygon stays on top of the grid
                    path.bringToFront();
                }
            }
            
            // Redraw the view to ensure changes are visible
            paper.view.update();
        },
        
        clearPolygons: function() {
            console.log('Clearing', polygonPaths.length, 'polygons');
            // Only remove polygon paths, not grid elements
            for (var i = 0; i < polygonPaths.length; i++) {
                polygonPaths[i].remove();
            }
            polygonPaths = [];
            console.log('Polygons cleared, grid preserved');
        },
        
        createPolygon: function(coords, r, g, b) {
            try {
                // Get current tile size and grid dimensions
                var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
                var worldWidth = gridColumns * tileSize;
                var worldHeight = gridRows * tileSize;
                
                // Calculate scaling factors to fit canvas while maintaining aspect ratio
                var scaleX = canvasWidth / worldWidth;
                var scaleY = canvasHeight / worldHeight;
                var scale = Math.min(scaleX, scaleY);
                
                // Calculate display dimensions and offset for centering
                var displayWidth = worldWidth * scale;
                var displayHeight = worldHeight * scale;
                var offsetX = (canvasWidth - displayWidth) / 2;
                var offsetY = (canvasHeight - displayHeight) / 2;
                
                console.log('Creating polygon with scale:', scale, 'offset:', offsetX, offsetY);
                console.log('First coordinate:', coords[0], 'transformed to:', offsetX + (coords[0][0] * scale), offsetY + (coords[0][1] * scale));
                
                var path = new paper.Path();
                
                // Store original world coordinates for later updates
                path.originalCoords = coords.slice(); // Copy the coordinates array
                
                for (var j = 0; j < coords.length; j++) {
                    // Transform world coordinates to screen coordinates
                    var worldX = coords[j][0];
                    var worldY = coords[j][1];
                    var screenX = offsetX + (worldX * scale);
                    var screenY = offsetY + (worldY * scale);
                    path.add(new paper.Point(screenX, screenY));
                }
                path.closed = true;
                path.fillColor = new paper.Color(r/255, g/255, b/255);
                
                // Make sure the polygon is visible by adding a stroke for debugging
                path.strokeColor = new paper.Color(0, 0, 0, 0.5);
                path.strokeWidth = 1;
                
                // Ensure the polygon is on top of the grid
                path.bringToFront();
                
                polygonPaths.push(path);
                console.log('Polygon created with', coords.length, 'points, color:', r, g, b);
                return true;
            } catch (error) {
                console.error('Error creating polygon:', error);
                return false;
            }
        },
        
        drawGrid: function(tileSize) {
            // Clear existing grid elements
            for (var i = 0; i < gridLines.length; i++) {
                gridLines[i].remove();
            }
            gridLines = [];
            
            if (gridBackground) {
                gridBackground.remove();
                gridBackground = null;
            }
            
            // Calculate world dimensions (logical grid size)
            var worldWidth = gridColumns * tileSize;
            var worldHeight = gridRows * tileSize;
            
            // Calculate scaling factors to fit canvas while maintaining aspect ratio
            var scaleX = canvasWidth / worldWidth;
            var scaleY = canvasHeight / worldHeight;
            var scale = Math.min(scaleX, scaleY); // Use smaller scale to maintain aspect ratio
            
            // Calculate actual display dimensions (centered if needed)
            var displayWidth = worldWidth * scale;
            var displayHeight = worldHeight * scale;
            var offsetX = (canvasWidth - displayWidth) / 2;
            var offsetY = (canvasHeight - displayHeight) / 2;
            
            // Create gray background rectangle for the grid area
            gridBackground = new paper.Path.Rectangle({
                point: [offsetX, offsetY],
                size: [displayWidth, displayHeight],
                fillColor: '#404040'
            });
            
            // Send the background to the back so it doesn't cover polygons
            gridBackground.sendToBack();
            
            // Calculate visual tile size
            var visualTileWidth = displayWidth / gridColumns;
            var visualTileHeight = displayHeight / gridRows;
            
            // Draw vertical lines
            for (var col = 0; col <= gridColumns; col++) {
                var x = offsetX + (col * visualTileWidth);
                var line = new paper.Path.Line(new paper.Point(x, offsetY), new paper.Point(x, offsetY + displayHeight));
                line.strokeColor = new paper.Color(0.7, 0.7, 0.7, 0.8); // More visible grid
                line.strokeWidth = 1;
                gridLines.push(line);
            }
            
            // Draw horizontal lines
            for (var row = 0; row <= gridRows; row++) {
                var y = offsetY + (row * visualTileHeight);
                var line = new paper.Path.Line(new paper.Point(offsetX, y), new paper.Point(offsetX + displayWidth, y));
                line.strokeColor = new paper.Color(0.7, 0.7, 0.7, 0.8); // More visible grid
                line.strokeWidth = 1;
                gridLines.push(line);
            }
            
            // Redraw the view to ensure changes are visible
            paper.view.update();
        },
        
        addColumn: function() {
            gridColumns++;
            var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
            this.drawGrid(tileSize);
            this.updatePolygonPositions();
        },
        
        removeColumn: function() {
            if (gridColumns > 1) { // Prevent going below 1 column
                gridColumns--;
                var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
                this.drawGrid(tileSize);
                this.updatePolygonPositions();
            }
        },
        
        addRow: function() {
            gridRows++;
            var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
            this.drawGrid(tileSize);
            this.updatePolygonPositions();
        },
        
        removeRow: function() {
            if (gridRows > 1) { // Prevent going below 1 row
                gridRows--;
                var tileSize = parseInt(document.getElementById('tileSizeInput').value) || 300;
                this.drawGrid(tileSize);
                this.updatePolygonPositions();
            }
        }
    };

    // Mouse wheel zoom
    paper.view.onMouseWheel = function(event) {
        var oldZoom = paper.view.zoom;
        var newZoom = event.delta < 0 ? oldZoom * 1.05 : oldZoom * 0.95;
        newZoom = Math.max(0.05, Math.min(20, newZoom));
        
        var beta = oldZoom / newZoom;
        var mousePosition = paper.view.viewToProject(event.point);
        var viewCenter = paper.view.center;
        var offset = mousePosition.subtract(viewCenter);
        var newCenter = mousePosition.subtract(offset.multiply(beta));
        
        paper.view.zoom = newZoom;
        paper.view.center = newCenter;
    };

    // Mouse drag for panning
    paper.view.onMouseDrag = function(event) {
        paper.view.center = paper.view.center.subtract(event.delta);
    };

    // Set initial view with top-left corner at (0,0)
    paper.view.center = new paper.Point(paper.view.size.width / 2, paper.view.size.height / 2);
    paper.view.zoom = 1; // Original size, no scaling

    // Initialize with instruction text (light gray for dark background)
    var text = new paper.PointText({
        point: paper.view.center,
        content: 'Load a CSV file to view polygons',
        fontSize: 18,
        fillColor: '#cccccc',
        justification: 'center'
    });
    
    // Draw initial grid with default tile size
    window.paperFunctions.drawGrid(300);
}

// Initialize Paper.js when the page loads
window.addEventListener('load', function() {
    paper.setup('canvas');
    initializePaper();
});

// Regular JavaScript for UI interactions
function loadCSV(event) {
    debugLog('Starting CSV load process...');
    
    var file = event.target.files[0];
    if (!file) {
        debugLog('ERROR: No file selected');
        return;
    }

    debugLog('File selected: ' + file.name + ' (size: ' + file.size + ' bytes)');

    var reader = new FileReader();
    reader.onload = function(e) {
        debugLog('File read successfully, parsing CSV...');
        var csv = e.target.result;
        debugLog('CSV content length: ' + csv.length + ' characters');
        debugLog('First 200 chars: ' + csv.substring(0, 200) + '...');
        
        // Trigger the PaperScript parseCSV function
        try {
            // Don't clear existing polygons - just add new ones
            debugLog('Loading polygons without clearing existing ones');
            
            var lines = csv.trim().split('\n');
            debugLog('Split into ' + lines.length + ' lines');
            
            if (lines.length < 2) {
                debugLog('ERROR: Not enough lines in CSV (need header + data)');
                return;
            }

            var header = lines[0].split(',');
            debugLog('Header: ' + header.join(' | '));

            // Find column indices
            var coordsIndex = -1, colorRIndex = -1, colorGIndex = -1, colorBIndex = -1;
            
            for (var i = 0; i < header.length; i++) {
                var h = header[i].toLowerCase();
                if (h.includes('coordinates') || h.includes('polygon_coords')) coordsIndex = i;
                if (h.includes('color_r')) colorRIndex = i;
                if (h.includes('color_g')) colorGIndex = i;
                if (h.includes('color_b')) colorBIndex = i;
            }

            debugLog('Column indices - coords:' + coordsIndex + ', R:' + colorRIndex + ', G:' + colorGIndex + ', B:' + colorBIndex);

            if (coordsIndex === -1) {
                debugLog('ERROR: Could not find coordinates column');
                return;
            }

            var allCoords = [];
            var polygonCount = 0;
            var errorCount = 0;

            for (var i = 1; i < lines.length && i < 6; i++) { // Process first 5 rows for debugging
                debugLog('Processing row ' + i + ': ' + lines[i]);
                
                var row = parseCSVRowJS(lines[i]);
                debugLog('Parsed into ' + row.length + ' columns: [' + row.join('] [') + ']');
                
                if (row.length < header.length) {
                    debugLog('WARNING: Row ' + i + ' has fewer columns than header');
                    continue;
                }

                try {
                    // Parse coordinates
                    var coordsStr = row[coordsIndex] || '';
                    debugLog('Raw coordinates: ' + coordsStr);
                    
                    coordsStr = coordsStr.replace(/"/g, '').trim();
                    debugLog('Cleaned coordinates: ' + coordsStr);
                    
                    // Convert Python tuple format to JSON format
                    // Replace parentheses with square brackets for JSON parsing
                    var jsonCoordsStr = coordsStr.replace(/\(/g, '[').replace(/\)/g, ']');
                    debugLog('JSON format: ' + jsonCoordsStr);
                    
                    // Parse JSON coordinate array
                    var coords = JSON.parse(jsonCoordsStr);
                    debugLog('Parsed ' + coords.length + ' coordinate pairs');
                    
                    if (coords.length < 3) {
                        debugLog('WARNING: Polygon has less than 3 points, skipping');
                        continue;
                    }

                    // Parse colors
                    var r = parseFloat(row[colorRIndex] || 0);
                    var g = parseFloat(row[colorGIndex] || 0);
                    var b = parseFloat(row[colorBIndex] || 0);
                    debugLog('Raw colors: R=' + r + ', G=' + g + ', B=' + b);

                    // Convert 0-1 range to 0-255 if needed
                    if (r <= 1 && g <= 1 && b <= 1) {
                        r = Math.floor(r * 255);
                        g = Math.floor(g * 255);
                        b = Math.floor(b * 255);
                        debugLog('Converted colors to: R=' + r + ', G=' + g + ', B=' + b);
                    }

                    // If all colors are 0 (black/transparent), use white for visibility
                    if (r === 0 && g === 0 && b === 0) {
                        r = 255;
                        g = 255;
                        b = 255;
                        debugLog('Converted transparent polygon to white: R=' + r + ', G=' + g + ', B=' + b);
                    }

                    // Create Paper.js path using the exposed function
                    var success = window.paperFunctions.createPolygon(coords, r, g, b);
                    if (success) {
                        debugLog('Successfully created polygon ' + polygonCount);
                        polygonCount++;
                    } else {
                        debugLog('ERROR: Failed to create polygon');
                        errorCount++;
                    }
                    
                } catch (error) {
                    errorCount++;
                    debugLog('ERROR parsing row ' + i + ': ' + error.message);
                }
            }

            // Process remaining rows without detailed logging
            debugLog('Processing remaining ' + (lines.length - 6) + ' rows...');
            for (var i = 6; i < lines.length; i++) {
                var row = parseCSVRowJS(lines[i]);
                if (row.length < header.length || coordsIndex === -1) continue;

                try {
                    var coordsStr = row[coordsIndex] || '';
                    coordsStr = coordsStr.replace(/"/g, '').trim();
                    
                    // Convert Python tuple format to JSON format
                    var jsonCoordsStr = coordsStr.replace(/\(/g, '[').replace(/\)/g, ']');
                    var coords = JSON.parse(jsonCoordsStr);
                    if (coords.length < 3) continue;

                    var r = parseFloat(row[colorRIndex] || 0);
                    var g = parseFloat(row[colorGIndex] || 0);
                    var b = parseFloat(row[colorBIndex] || 0);

                    if (r <= 1 && g <= 1 && b <= 1) {
                        r = Math.floor(r * 255);
                        g = Math.floor(g * 255);
                        b = Math.floor(b * 255);
                    }

                    if (r === 0 && g === 0 && b === 0) {
                        r = 255;
                        g = 255;
                        b = 255;
                    }

                    var success = window.paperFunctions.createPolygon(coords, r, g, b);
                    if (success) {
                        polygonCount++;
                    } else {
                        errorCount++;
                    }
                    
                } catch (error) {
                    errorCount++;
                }
            }

            debugLog('Finished processing. Total polygons: ' + polygonCount + ', Errors: ' + errorCount);

            // No auto-fitting - polygons displayed at original size with top-left as (0,0)
            debugLog('Polygons displayed at original size, no auto-fitting applied');

            debugLog('SUCCESS: File loaded completely');
            
        } catch (error) {
            debugLog('FATAL ERROR: ' + error.message);
            debugLog('Stack trace: ' + error.stack);
        }
    };
    
    reader.onerror = function() {
        debugLog('ERROR: Failed to read file');
    };
    
    reader.readAsText(file);
}

function parseCSVRowJS(row) {
    var result = [];
    var current = '';
    var inQuotes = false;
    
    for (var i = 0; i < row.length; i++) {
        var char = row[i];
        if (char === '"') {
            inQuotes = !inQuotes;
        } else if (char === ',' && !inQuotes) {
            result.push(current);
            current = '';
        } else {
            current += char;
        }
    }
    result.push(current);
    return result;
}
