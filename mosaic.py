#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert an pixel image into a mosaic constructed by polygons
=======================================================================
Author: Johannes Beetz
Based on algorithm described in "Artificial Mosaics (2005)" by Di Blasi
"""

import time
import random
import tkinter as tk
from tkinter import filedialog, simpledialog
import matplotlib.pyplot as plt
from matplotlib import patches
import numpy as np
import csv
import json
from shapely.geometry import MultiPolygon
import edges, guides, tiles, convex, coloring, plotting

def save_polygons_to_csv(polygons, colors, filename=None):
    """Save polygons and their colors to a CSV file"""
    if filename is None:
        # Open file dialog to choose save location
        filename = filedialog.asksaveasfilename(
            title="Save polygons as CSV file",
            defaultextension=".csv",
            filetypes=[
                ("CSV files", "*.csv"),
                ("All files", "*.*")
            ],
            initialfile="mosaic_polygons.csv"
        )
        
        if not filename:  # User cancelled
            print("Save cancelled by user.")
            return False
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Write header
            writer.writerow(['polygon_id', 'coordinates', 'color_r', 'color_g', 'color_b'])
            
            # Write each polygon
            for i, (polygon, color) in enumerate(zip(polygons, colors)):
                # Extract coordinates as a list of [x, y] pairs
                coords = list(polygon.exterior.coords)
                # Convert to JSON string for storage
                coords_json = json.dumps([[float(x), float(y)] for x, y in coords])
                
                # Extract RGB values
                r, g, b = color[0], color[1], color[2]
                
                # Write row
                writer.writerow([i, coords_json, float(r), float(g), float(b)])
        
        print(f'Saved {len(polygons)} polygons to {filename}')
        return True
        
    except Exception as e:
        print(f'Error saving file: {e}')
        return False

# Hide the main tkinter window
root = tk.Tk()
root.withdraw()

# Select filename of input image
print("Please select an image file...")
fname = filedialog.askopenfilename(
    title="Select an image file",
    filetypes=[
        ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.tiff *.tif"),
        ("PNG files", "*.png"),
        ("JPEG files", "*.jpg *.jpeg"),
        ("All files", "*.*")
    ]
)

if not fname:
    print("No file selected. Using default test image.")
    fname = r''  # Empty string will use the default test image

# Ask user for desired size of the longer side using popup dialog
root = tk.Tk()
root.withdraw()  # Hide the main window

long_side_size = simpledialog.askinteger(
    "Image Size",
    "Enter the desired size for the longer side of the image:\n(100-5000 pixels)",
    initialvalue=1000,
    minvalue=100,
    maxvalue=5000
)

# If user cancels the dialog, use default value
if long_side_size is None:
    long_side_size = 1000

print(f"Image will be resized so its longer side is {long_side_size} pixels.")
 

# Parameters
half_tile =6 # 4...30 => half size of mosaic tile
GAUSS = 8 # 0...8 => blurs image before edge detection (check "edges" image for a good value)
EDGE_DETECTION = 'HED' # HED or DiBlasi
WITH_FRAME = True # default is True => control about guidelines along image borders
RAND_SIZE = 0.4 # portion of tile size which is added or removed randomly during construction
MAX_ANGLE = 70 # 30...75 => max construction angle for tiles along roundings
GAP_CHAIN_SPACING = 0.9 # 0.4 to 1.0 => spacing of gap filler chains
MAKE_CONVEX = True # default is True => break concave into more realistic polygons
COLOR_SCHEMA = ['nilotic',] # leave empty to plot all available or choose from 'wise_men',
                  #  'fish', 'cave_canem', 'nilotic', 'rooster', 'carpe_diem', 'Hyena'

# choose which image to plot
plot_list = [
    #'original',
    #'edges', # CAN BE HELPFUL FOR ADJUSTING GAUSS PARAMETER - REMOVED TO SKIP FIRST SCREEN
    #'distances',
    #'guidelines',
    #'gradient',
    #'angles_0to180',
    #'polygons_chains',
    #'used_up_space',
    #'distance_to_tile',
    #'filler_guidelines',
    #'polygons_filler',
    #'polygons_cut',
    'final', # <== MOST IMPORTANT
    #'final_recolored', # <== OR THIS
    #'statistics',
    ]


# Load image
t_start = time.time()
random.seed(0)
# Load image with user-specified long side size
img0 = edges.load_image(fname, width=None, long_side=long_side_size, plot=plot_list)
h,w = img0.shape[0],img0.shape[1]
A0 = (2*half_tile)**2 # area of tile when placed along straight guideline
print (f'Estimated number of tiles: {2*w*h/A0:.0f}') # factor 2 since tiles can be smaller than default size

# Find edges of image objects
if EDGE_DETECTION == 'HED':
    img_edges = edges.edges_hed(img0, gauss=GAUSS, plot=plot_list)
elif EDGE_DETECTION == 'DiBlasi':
    img_edges = edges.edges_diblasi(img0, gauss=GAUSS, details=4, plot=plot_list)
else:
    raise ValueError('Parameter for edge detection mode not understood.')


if WITH_FRAME: 
    img_edges[0,:]=1; img_edges[-1,:]=1; img_edges[:,0]=1; img_edges[:,-1]=1

# Interactive drawing stage - allow user to add guidelines
def interactive_drawing(img0, img_edges):
    """Allow user to draw additional guidelines on the image"""
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button
    
    print("Interactive drawing mode:")
    print("- Left click and drag to draw lines")
    print("- Press 'c' to clear all drawn lines") 
    print("- Press 'u' to undo last drawn line")
    print("- Press 'd' to toggle delete mode (click on lines to delete them)")
    print("- Press 'e' to toggle edge erase mode (drag to erase detected edges)")
    print("- Press 'Enter' or click 'Done' to finish")
    
    fig, ax1 = plt.subplots(1, 1, figsize=(12, 8))
    
    # Create a modifiable copy of the edges for erasing
    img_edges_modified = img_edges.copy().astype(float)
    
    # Show original image with edges overlaid
    ax1.imshow(img0)
    
    # Create custom colormap for edges - yellow with transparency
    import matplotlib.colors as mcolors
    colors = ['black', 'yellow']
    n_bins = 100
    cmap = mcolors.LinearSegmentedColormap.from_list('yellow_edges', colors, N=n_bins)
    
    # Draw edges thicker by dilating them
    from scipy import ndimage
    thick_edges = ndimage.binary_dilation(img_edges_modified, structure=np.ones((3,3)))
    edge_overlay = ax1.imshow(thick_edges, cmap=cmap, alpha=0.7, vmin=0, vmax=1)  # Store reference to update later
    ax1.set_title("Draw Additional Guidelines (Left Click & Drag)", fontsize=12)
    ax1.axis('on')
    
    # Store drawn lines
    drawn_lines = []
    current_line_coords = []
    current_line_plot = None
    is_drawing = False
    line_plots = []  # Store line plot objects for clearing
    delete_mode = False  # Toggle for delete mode
    delete_cursor = None  # Circle cursor for delete mode
    erase_mode = False  # Toggle for edge erase mode
    erase_cursor = None  # Circle cursor for erase mode
    is_erasing = False  # Currently erasing edges
    erase_mode = False  # Toggle for edge erase mode
    erase_cursor = None  # Circle cursor for erase mode
    is_erasing = False  # Currently erasing edges
    
    # Create a modifiable copy of the edges for erasing
    img_edges_modified = img_edges.copy().astype(float)
    
    def on_press(event):
        nonlocal is_drawing, current_line_coords, drawn_lines, line_plots, delete_mode, erase_mode, is_erasing, img_edges_modified, edge_overlay
        if event.inaxes == ax1 and event.button == 1:  # Left mouse button on left axis
            if erase_mode:
                # Edge erase mode - start erasing detected edges
                is_erasing = True
                erase_edges_at_point(event.xdata, event.ydata, img_edges_modified, edge_overlay)
                print("Started erasing edges")
            elif delete_mode:
                # Delete mode - find and remove clicked line
                click_x, click_y = event.xdata, event.ydata
                delete_threshold = 30  # pixels - even larger threshold
                
                print(f"Delete mode click at ({click_x:.0f}, {click_y:.0f}). Checking {len(drawn_lines)} lines...")
                
                # Check each drawn line for proximity to click
                deleted = False
                for i in range(len(drawn_lines) - 1, -1, -1):  # Go backwards to avoid index issues
                    line_coords = drawn_lines[i]
                    if len(line_coords) > 1:
                        # Check if click is near any point in the line
                        min_distance = float('inf')
                        for point in line_coords:
                            distance = abs(click_x - point[0]) + abs(click_y - point[1])  # Manhattan distance (simpler)
                            min_distance = min(min_distance, distance)
                        
                        print(f"  Line {i+1}: min_distance = {min_distance:.1f}")
                        
                        if min_distance <= delete_threshold:
                            # Remove this line
                            print(f"Deleting line {i+1}")
                            drawn_lines.pop(i)
                            line_plot = line_plots.pop(i)
                            line_plot.remove()
                            fig.canvas.draw_idle()
                            print(f"Deleted line. {len(drawn_lines)} lines remaining.")
                            deleted = True
                            break  # Exit after deleting first matching line
                
                if not deleted:
                    print(f"No line found near click point")
                return  # Don't process as drawing action
            else:
                # Drawing mode
                is_drawing = True
                current_line_coords = [(event.xdata, event.ydata)]
    
    def erase_edges_at_point(x, y, edges_array, overlay_obj):
        """Erase detected edges at the given point with a circular brush"""
        if x is None or y is None:
            return
        
        erase_radius = 15  # pixels
        center_x, center_y = int(x), int(y)
        
        # Create circular mask for erasing
        h, w = edges_array.shape
        y_grid, x_grid = np.ogrid[0:h, 0:w]
        mask = ((x_grid - center_x) ** 2 + (y_grid - center_y) ** 2) <= erase_radius ** 2
        
        # Erase edges (set to 0)
        edges_array[mask] = 0
        
        # Update the display
        thick_edges = ndimage.binary_dilation(edges_array, structure=np.ones((3,3)))
        overlay_obj.set_array(thick_edges)
        fig.canvas.draw_idle()
    
    def on_motion(event):
        nonlocal current_line_coords, current_line_plot, delete_cursor, delete_mode, erase_mode, erase_cursor, is_erasing, img_edges_modified, edge_overlay
        
        # Handle erase mode cursor and erasing
        if erase_mode and event.inaxes == ax1 and event.xdata is not None and event.ydata is not None:
            # Remove previous cursor
            if erase_cursor is not None:
                erase_cursor.remove()
            
            # Draw erase cursor (blue circle)
            erase_cursor = plt.Circle((event.xdata, event.ydata), 8, color='blue', fill=False, linewidth=2, alpha=0.7)
            ax1.add_patch(erase_cursor)
            
            # If currently erasing, continue erasing
            if is_erasing:
                erase_edges_at_point(event.xdata, event.ydata, img_edges_modified, edge_overlay)
            
            fig.canvas.draw_idle()
            
        # Handle delete mode cursor
        elif delete_mode and event.inaxes == ax1 and event.xdata is not None and event.ydata is not None:
            # Remove previous cursor
            if delete_cursor is not None:
                delete_cursor.remove()
            
            # Draw delete cursor (red circle)
            delete_cursor = plt.Circle((event.xdata, event.ydata), 8, color='red', fill=False, linewidth=2, alpha=0.7)
            ax1.add_patch(delete_cursor)
            fig.canvas.draw_idle()
            
        # Clean up cursors when not in their respective modes
        else:
            if not erase_mode and erase_cursor is not None:
                erase_cursor.remove()
                erase_cursor = None
            if not delete_mode and delete_cursor is not None:
                delete_cursor.remove()
                delete_cursor = None
            if erase_cursor is not None or delete_cursor is not None:
                fig.canvas.draw_idle()
        
        # Handle drawing
        if is_drawing and event.inaxes == ax1 and event.xdata is not None and event.ydata is not None and not delete_mode and not erase_mode:
            current_line_coords.append((event.xdata, event.ydata))
            
            # Remove previous temporary line
            if current_line_plot is not None:
                current_line_plot.remove()
            
            # Draw current line in progress
            if len(current_line_coords) > 1:
                xs, ys = zip(*current_line_coords)
                current_line_plot, = ax1.plot(xs, ys, 'yellow', linewidth=1, alpha=0.8)
                fig.canvas.draw_idle()
    
    def on_release(event):
        nonlocal is_drawing, current_line_coords, drawn_lines, current_line_plot, line_plots, delete_mode, is_erasing
        if is_erasing:
            is_erasing = False
            print("Stopped erasing edges")
        elif is_drawing and not delete_mode:  # Only process release for drawing mode
            is_drawing = False
            if len(current_line_coords) > 1:
                # Store the drawn line
                drawn_lines.append(current_line_coords.copy())
                
                # Draw final line
                xs, ys = zip(*current_line_coords)
                line_plot, = ax1.plot(xs, ys, 'yellow', linewidth=1, alpha=0.9)
                line_plots.append(line_plot)
                fig.canvas.draw_idle()
                print(f"Drew line {len(drawn_lines)} with {len(current_line_coords)} points. Total lines: {len(drawn_lines)}")
                print(f"Lists synchronized: drawn_lines={len(drawn_lines)}, line_plots={len(line_plots)}")
            else:
                print("Line too short, not adding")
                
            current_line_coords = []
            if current_line_plot is not None:
                current_line_plot.remove()
                current_line_plot = None
    
    def on_key(event):
        nonlocal drawn_lines, line_plots, delete_mode, delete_cursor, erase_mode, erase_cursor
        if event.key == 'enter':
            plt.close(fig)
        elif event.key == 'c':  # Clear all drawn lines
            print(f"Clear pressed. drawn_lines: {len(drawn_lines)}, line_plots: {len(line_plots)}")
            if drawn_lines or line_plots:
                drawn_lines.clear()
                for line_plot in line_plots:
                    try:
                        line_plot.remove()
                    except:
                        pass  # Ignore errors if line already removed
                line_plots.clear()
                fig.canvas.draw_idle()
                print(f"Cleared all lines.")
            else:
                print("No lines to clear.")
        elif event.key == 'u':  # Undo last drawn line
            print(f"Undo pressed. drawn_lines: {len(drawn_lines)}, line_plots: {len(line_plots)}")
            if drawn_lines and line_plots and len(drawn_lines) == len(line_plots):
                # Remove from data
                removed_line = drawn_lines.pop()  
                print(f"Removed line with {len(removed_line)} points")
                
                # Remove from plot
                last_plot = line_plots.pop()
                last_plot.remove()
                fig.canvas.draw_idle()
                print(f"Undid last line. {len(drawn_lines)} lines remaining.")
            elif len(drawn_lines) != len(line_plots):
                print(f"Error: Mismatch between drawn_lines ({len(drawn_lines)}) and line_plots ({len(line_plots)})")
                # Fix the mismatch
                while len(line_plots) > len(drawn_lines) and line_plots:
                    extra_plot = line_plots.pop()
                    extra_plot.remove()
                fig.canvas.draw_idle()
            else:
                print("No lines to undo.")
        elif event.key == 'd':  # Toggle delete mode
            delete_mode = not delete_mode
            if delete_mode:
                print(f"Delete mode ON - Click on lines to delete them. Currently have {len(drawn_lines)} lines.")
                ax1.set_title("DELETE MODE: Click on lines to delete them", fontsize=12, color='red')
                # Turn off other modes
                erase_mode = False
                if erase_cursor is not None:
                    erase_cursor.remove()
                    erase_cursor = None
            else:
                print("Delete mode OFF - Drawing mode restored")
                ax1.set_title("Draw Additional Guidelines (Left Click & Drag)", fontsize=12, color='black')
                # Remove delete cursor if it exists
                if delete_cursor is not None:
                    delete_cursor.remove()
                    delete_cursor = None
            fig.canvas.draw_idle()
        elif event.key == 'e':  # Toggle edge erase mode
            erase_mode = not erase_mode
            if erase_mode:
                print(f"Edge erase mode ON - Drag to erase detected edges")
                ax1.set_title("EDGE ERASE MODE: Drag to erase detected edges", fontsize=12, color='blue')
                # Turn off other modes
                delete_mode = False
                if delete_cursor is not None:
                    delete_cursor.remove()
                    delete_cursor = None
            else:
                print("Edge erase mode OFF - Drawing mode restored")
                ax1.set_title("Draw Additional Guidelines (Left Click & Drag)", fontsize=12, color='black')
                # Remove erase cursor if it exists
                if erase_cursor is not None:
                    erase_cursor.remove()
                    erase_cursor = None
            fig.canvas.draw_idle()
    
    def done_callback(event):
        plt.close(fig)
    
    # Add Done button
    ax_button = plt.axes([0.42, 0.01, 0.16, 0.05])
    button_done = Button(ax_button, 'Done')
    button_done.on_clicked(done_callback)
    
    # Connect events
    fig.canvas.mpl_connect('button_press_event', on_press)
    fig.canvas.mpl_connect('motion_notify_event', on_motion)
    fig.canvas.mpl_connect('button_release_event', on_release)
    fig.canvas.mpl_connect('key_press_event', on_key)
    
    plt.tight_layout()
    plt.show()
    
    # Convert drawn lines to edge pixels
    additional_edges = np.zeros_like(img_edges, dtype=bool)
    
    for line in drawn_lines:
        if len(line) > 1:
            # Rasterize each line segment
            for i in range(len(line) - 1):
                x1, y1 = int(np.clip(line[i][0], 0, img_edges.shape[1]-1)), int(np.clip(line[i][1], 0, img_edges.shape[0]-1))
                x2, y2 = int(np.clip(line[i+1][0], 0, img_edges.shape[1]-1)), int(np.clip(line[i+1][1], 0, img_edges.shape[0]-1))
                
                # Simple line drawing using numpy
                num_points = max(abs(x2-x1), abs(y2-y1), 1)
                xs = np.linspace(x1, x2, num_points).astype(int)
                ys = np.linspace(y1, y2, num_points).astype(int)
                
                # Set pixels along the line
                additional_edges[ys, xs] = True
    
    print(f"Added {len(drawn_lines)} manual guidelines")
    print(f"Modified edges: {np.sum(img_edges != img_edges_modified)} pixels erased")
    
    return additional_edges, img_edges_modified

# Call PyQt interactive drawing function
from interactive_guideline_editor import run_interactive_editor
manual_edges, img_edges_modified = run_interactive_editor(img0, img_edges)

# Combine original modified edges with manually drawn edges
img_edges = np.logical_or(img_edges_modified, manual_edges).astype(np.uint8)


# place tiles along chains
chains, angles_0to180 = guides.chains_and_angles(img_edges, half_tile=half_tile, plot=plot_list)
polygons_chains = tiles.place_tiles_along_chains(chains, angles_0to180, half_tile, RAND_SIZE, MAX_ANGLE, A0, plot=plot_list)

print(f'Placed {len(polygons_chains)} tiles along guidelines')
print('Continuing with full processing...')

# find gaps and put more tiles inside
filler_chains = guides.chains_into_gaps(polygons_chains, h, w, half_tile, GAP_CHAIN_SPACING, plot=plot_list)
polygons_all = tiles.place_tiles_into_gaps(polygons_chains, filler_chains, half_tile, A0, plot=plot_list)

# remove parts of tiles which reach outside of image frame
polygons_all = tiles.cut_tiles_outside_frame(polygons_all, half_tile, img0.shape[0],img0.shape[1], plot=plot_list)

# convert concave polygons to convex (i.e. more realistic) ones
polygons_convex = convex.make_convex(polygons_all, half_tile, A0) if MAKE_CONVEX else polygons_all

# make polygons smaller, remove or correct strange polygons, simplify and drop very small polygons
polygons_post = tiles.irregular_shrink(polygons_convex, half_tile)
polygons_post = tiles.repair_tiles(polygons_post) 
polygons_post = tiles.reduce_edge_count(polygons_post, half_tile)
polygons_post = tiles.drop_small_tiles(polygons_post, A0)

# O1: Show tiles after dropping small tiles, highlighting small ones
print('O1: Showing tiles after dropping small tiles (small tiles highlighted)...')
fig, ax = plt.subplots(1, 1, figsize=(12, 8))
ax.imshow(np.ones_like(img0) * 255)  # White background
small_tile_threshold = half_tile ** 2
small_tiles_count = 0
for i, poly in enumerate(polygons_post):
    if hasattr(poly, 'exterior'):
        is_small = False
        try:
            if poly.area < small_tile_threshold:
                is_small = True
        except Exception:
            pass  # Ignore invalid polygons for this check

        if is_small:
            small_tiles_count += 1
            fill_color = 'red'
            alpha = 0.5
        else:
            fill_color = 'lightgreen'
            alpha = 0.3
            
        coords = np.array(poly.exterior.coords)
        ax.plot(coords[:, 0], coords[:, 1], 'k-', linewidth=0.5)
        ax.fill(coords[:, 0], coords[:, 1], alpha=alpha, color=fill_color)

ax.set_title(f'Step O1: Tiles After Dropping Small Tiles - {len(polygons_post)} polygons ({small_tiles_count} small)')
ax.axis('off')
ax.set_xlim(0, img0.shape[1])
ax.set_ylim(img0.shape[0], 0)
plt.tight_layout()
plt.show()
print(f'O1 complete: {len(polygons_post)} tiles after dropping small tiles')


if 'final' in plot_list:
    # copy colors from original image
    colors_final = coloring.colors_from_original(polygons_post, img0, method='average')
    
    t0 = time.time()
    svg = plotting.draw_tiles(polygons_post, colors_final, h,w, background_brightness=0.2, return_svg=False, chains=None)
    if svg:
        with open("output.svg", "w") as fn:
            fn.write(svg)
    print ('Final plot / saving:', f'{time.time()-t0:.1f}s') 

if 'final_recolored' in plot_list:
    color_dict = coloring.load_colors()
    keys = color_dict.keys() if not COLOR_SCHEMA else COLOR_SCHEMA
    for key in keys:
        new_colors = coloring.modify_colors(colors_final, 'source', color_dict[key])
        title = key if not COLOR_SCHEMA else ''
        plotting.draw_tiles(polygons_post, new_colors, h, w, background_brightness=0.2,
                            return_svg=None, chains=None, title=title)

if 'statistics' in plot_list:
    plotting.statistics(polygons_post)

print (f'Total calculation time: {time.strftime("%M min %S s", time.gmtime((time.time()-t_start)))}')
print ('Final number of tiles:', len(polygons_post))

# Save final polygons to CSV file at the end
print('Saving final polygons to CSV file...')
save_polygons_to_csv(polygons_post, colors_final if 'final' in plot_list else coloring.colors_from_original(polygons_post, img0, method='average'))
























