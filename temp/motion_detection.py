#!/usr/bin/env python3
"""
motion_detect.py

Simple local motion detector using OpenCV + NumPy.

Features:
- Uses a running average background model (cv2.accumulateWeighted).
- Per-frame difference + thresholding -> contours to find moving regions.
- Draws bounding boxes & motion mask on the live feed.
- Configurable sensitivity, minimum motion area, ROI, and background update speed.
- Can read from webcam (default) or a video file.

Dependencies:
  pip install opencv-python numpy

Usage:
  python motion_detect.py            # uses default webcam (0)
  python motion_detect.py --source 1 # use camera index 1
  python motion_detect.py --video file.mp4
  python motion_detect.py --min-area 1500 --alpha 0.01
"""

import cv2
import numpy as np
import argparse
import time

def parse_args():
    p = argparse.ArgumentParser(description="Simple local motion detector")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--video", "-v", help="Path to video file (optional)", default=None)
    group.add_argument("--source", "-s", help="Camera index (0,1,...)", type=int, default=0)
    p.add_argument("--min-area", type=int, default=1000,
                   help="Minimum contour area in pixels to consider motion (default 1000)")
    p.add_argument("--alpha", type=float, default=0.02,
                   help="Background update weight for running average (0-1). Lower = slower updates (default 0.02)")
    p.add_argument("--blur", type=int, default=21,
                   help="Gaussian blur kernel size (odd integer, default 21)")
    p.add_argument("--threshold", type=int, default=25,
                   help="Threshold for binarizing frame difference (default 25)")
    p.add_argument("--display-mask", action="store_true",
                   help="Show the binary motion mask in a separate window")
    p.add_argument("--no-display", action="store_true",
                   help="Run headless (no windows). Useful when redirecting output.")
    return p.parse_args()

def ensure_odd(x):
    return x if x % 2 == 1 else x + 1

def main():
    args = parse_args()
    blur_k = ensure_odd(args.blur)
    min_area = max(1, args.min_area)
    alpha = float(args.alpha)
    thr = int(args.threshold)

    # Open capture
    if args.video:
        cap = cv2.VideoCapture(args.video)
    else:
        cap = cv2.VideoCapture(args.source)

    if not cap.isOpened():
        print("ERROR: Unable to open video source.")
        return

    # Initialize background model
    ret, frame = cap.read()
    if not ret:
        print("ERROR: Unable to read from source.")
        cap.release()
        return

    # resize to reasonable width for speed (maintain aspect ratio)
    max_width = 800
    h0, w0 = frame.shape[:2]
    scale = 1.0
    if w0 > max_width:
        scale = max_width / float(w0)

    def resize_frame(f):
        if scale != 1.0:
            return cv2.resize(f, (int(f.shape[1]*scale), int(f.shape[0]*scale)))
        return f

    frame = resize_frame(frame)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (blur_k, blur_k), 0).astype("float32")

    background = gray.copy()  # float32 background model

    last_time = time.time()
    fps = 0.0

    print("Starting motion detection. Press 'q' in window or Ctrl+C in terminal to quit.")
    while True:
        ret, frame = cap.read()
        if not ret:
            # If video file ended, break cleanly.
            break

        frame = resize_frame(frame)
        frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_blur = cv2.GaussianBlur(frame_gray, (blur_k, blur_k), 0)

        # Update running average background (float32)
        cv2.accumulateWeighted(frame_blur.astype("float32"), background, alpha)

        # Compute absolute difference between background and current frame
        background_uint8 = cv2.convertScaleAbs(background)  # convert to uint8 for absdiff
        diff = cv2.absdiff(background_uint8, frame_blur)

        # Threshold to get motion regions
        _, motion_mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)

        # Morphological ops to reduce noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3,3))
        motion_mask = cv2.morphologyEx(motion_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        motion_mask = cv2.dilate(motion_mask, kernel, iterations=2)

        # Find contours on mask
        contours, _ = cv2.findContours(motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            motion_boxes.append((x, y, w, h))
            # draw bounding box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 180, 255), 2)

        # Overlay simple info
        now = time.time()
        fps = 0.9 * fps + 0.1 * (1.0 / (now - last_time)) if (now - last_time) > 0 else fps
        last_time = now
        text = f"FPS: {fps:.1f}  Motion boxes: {len(motion_boxes)}"
        cv2.putText(frame, text, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)

        # Optionally display mask
        if not args.no_display:
            cv2.imshow("Motion Detection", frame)
            if args.display_mask:
                # colorize mask for easier viewing
                mask_color = cv2.cvtColor(motion_mask, cv2.COLOR_GRAY2BGR)
                cv2.imshow("Motion Mask", mask_color)

        # user can press 'q' to quit
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Exited cleanly.")

if __name__ == "__main__":
    main()
