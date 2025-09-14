#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import numpy as np
import skimage as sk
from skimage.io import imread
from skimage import filters
from skimage import transform
import plotting
from pathlib import Path


def load_image(fname, width=900, long_side=None, plot=[]):
    
    if fname:
        img0 = imread(fname)
    else:
        img0 = sk.data.coffee() # coffee (example image)
    
    # Convert RGBA to RGB if image has 4 channels (alpha channel)
    if len(img0.shape) == 3 and img0.shape[2] == 4:
        img0 = img0[:, :, :3]  # Remove alpha channel
        print("Converted RGBA image to RGB")
    
    # ensure image is rgb (for consistency)
    if len(img0.shape)<3:
        img0 = sk.color.gray2rgb(img0) 

    # resize image
    if long_side is not None:
        # Resize based on longer side while maintaining aspect ratio
        height, width_current = img0.shape[0], img0.shape[1]
        if width_current >= height:
            # Landscape: width is longer
            factor = long_side / width_current
        else:
            # Portrait: height is longer
            factor = long_side / height
        new_height = int(height * factor)
        new_width = int(width_current * factor)
        img0 = transform.resize(img0, (new_height, new_width), anti_aliasing=True)
        img0 = (img0*255).astype(int)  # transform.resize returns 0-1 range, convert to 0-255
    elif width is not None:
        # Original behavior: resize by width
        factor = width/img0.shape[1]
        img0 = transform.resize(img0, (int(img0.shape[0]*factor), int(img0.shape[1]*factor)), anti_aliasing=True)
        img0 = (img0*255).astype(int)  # transform.resize returns 0-1 range, convert to 0-255
    else:
        # No resizing - ensure image is in 0-255 range
        if img0.max() <= 1.0:
            img0 = (img0*255).astype(int)  # Convert 0-1 to 0-255
        else:
            img0 = img0.astype(int)  # Already 0-255, just ensure integer type
    if 'original' in plot: plotting.plot_image(img0)
    print (f'Size of input image: {img0.shape[0]}px * {img0.shape[1]}px')
    
    return img0



def edges_diblasi(img, gauss=5, details=1, plot=[]):

    # RGB to gray ("Luminance channel" in Di Blasi)
    img_gray = sk.color.rgb2gray(img)
    
    # equalize histogram
    img_eq = sk.exposure.equalize_hist(img_gray)
    
    # soften image
    img_gauss = filters.gaussian(img_eq, sigma=16, truncate=gauss/16)
    
    # segment bright areas to blobs
    variance = img_gauss.std()**2 #  evtl. direkt die std verwenden
    img_seg = np.ones((img.shape[0],img.shape[1]))        
    threshold = variance/4*2*details
    img_seg[abs(img_gauss-img_gauss.mean())>threshold] = 0
    
    ### 5. Kanten finden
    img_edge = filters.laplace(img_seg, ksize=3)
    img_edge[img_edge!=0]=1
    
    if 'edges' in plot: plotting.plot_image(img_edge, inverted=True, title='Di Blasi')
    
    return img_edge



def hed_edges(image):
    import cv2 as cv
    # based on https://github.com/opencv/opencv/blob/master/samples/dnn/edge_detection.py
    class CropLayer(object):
        def __init__(self, params, blobs):
            self.xstart = 0
            self.xend = 0
            self.ystart = 0
            self.yend = 0
        # Our layer receives two inputs. We need to crop the first input blob
        # to match a shape of the second one (keeping batch size and number of channels)
        def getMemoryShapes(self, inputs):
            inputShape, targetShape = inputs[0], inputs[1]
            batchSize, numChannels = inputShape[0], inputShape[1]
            height, width = targetShape[2], targetShape[3]
            self.ystart = int((inputShape[2] - targetShape[2]) / 2)
            self.xstart = int((inputShape[3] - targetShape[3]) / 2)
            self.yend = self.ystart + height
            self.xend = self.xstart + width
            return [[batchSize, numChannels, height, width]]
        def forward(self, inputs):
            return [inputs[0][:,:,self.ystart:self.yend,self.xstart:self.xend]]
    
    # Load the pretrained model (source: https://github.com/s9xie/hed)
    script_path = Path(__file__).parent.absolute()
    hed_path = Path.joinpath(script_path, 'HED')
    net = cv.dnn.readNetFromCaffe(str(hed_path / 'deploy.prototxt'),
                                  str(hed_path / 'hed_pretrained_bsds.caffemodel') )
    cv.dnn_registerLayer('Crop', CropLayer)

    image=cv.resize(image,(image.shape[1],image.shape[0]))
    # prepare image as input dataset (mean values from full image dataset)
    inp = cv.dnn.blobFromImage(image, scalefactor=1.0, size=(image.shape[1],image.shape[0]), #w,h
                               mean=(104.00698793, 116.66876762, 122.67891434),
                               swapRB=False, crop=False)
    net.setInput(inp)
    out = net.forward()
    cv.dnn_unregisterLayer('Crop') # get rid of issues when run in a loop
    out = out[0,0]
    return out


def edges_hed(img, gauss=None, plot=[]):

    if gauss:
        img = filters.gaussian(img, sigma=16, truncate=gauss/16)
    
    img = img/np.amax(img)*255
    img = img.astype(np.uint8)    
    
    hed_matrix = hed_edges(img)
    
    # gray to binary
    hed_seg = np.ones((hed_matrix.shape[0],hed_matrix.shape[1]))
    hed_seg[hed_matrix<0.5]=0
    
    # skeletonize to get inner lines
    img_edges = sk.morphology.skeletonize(hed_seg).astype(int)

    # option to make plot lines thicker:
    #from skimage.morphology import square,dilation
    #img_edges = dilation(img_edges, square(3))
    
    if 'edges' in plot: plotting.plot_image(img_edges, inverted=True, title='HED')
    
    return img_edges



if __name__ == '__main__':
    img = sk.data.coffee()
    #img_edges = edges_diblasi(img)
    img_edges = edges_hed(img, gauss=0)
    
    
    
    





