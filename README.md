# RoadWatch CV

RoadWatch CV is an educational traffic-video analysis project for a Principles of Computer Vision laboratory. It detects vehicles with YOLO, associates detections with ByteTrack, maps their positions onto a calibrated road plane, estimates speed over a stable trajectory window, and records sustained overspeeding or wrong-way events.

## Install and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`. On the first analysis, Ultralytics downloads its small `yolo11n.pt` model weights. The first run therefore needs internet access; later runs use the local cached weights. Inference currently runs on CPU.

## Prepare and calibrate a video

Use a fixed-camera video with a clear road area. Select the video in the dashboard and mark the road corners in this order:

1. Far-left corner
2. Far-right corner
3. Near-right corner
4. Near-left corner

Review the four marked corners in the preview. Enter the known distance along the road between the far and near boundaries; this is the real-world scale reference used for speed. Road width is suggested as 3.5 m per lane from the lane-count selector and can be edited. The speed calculation uses longitudinal displacement, so lane changes do not add artificial speed. Choose whether the expected traffic travels from the far end toward the near end or in reverse.

The lane-width value is only a typical-width suggestion, not a measurement from the video. The app does not automatically recognize road boundaries; corner selection remains a user-reviewed step. Use a straight, approximately planar road and a reliable known longitudinal distance for the best result.

For the best lab demonstration, use a 10–30 second clip, keep the selected calibration area within one continuous stretch of road, and choose two physical dimensions that you can reasonably estimate from lane markings. Speed estimates depend on those measurements. Inspect annotated tracks before discussing any alert.

## What the system measures

- Vehicle classes: car, motorcycle, bus, and truck
- Persistent IDs from ByteTrack
- Road-plane positions from the four-point perspective transform
- Speed smoothed over approximately 0.8 seconds of track history
- Overspeed and wrong-way events after a stable observation period
- Annotated MP4 and downloadable CSV evidence, including a row per tracked vehicle even when no violations occur

## Limitations

- The camera should remain stationary, and the road should be approximately planar.
- Approximate longitudinal distance produces approximate speeds; the suggested width is not guaranteed to match the real road and results are not suitable for legal enforcement.
- Occlusion, dense traffic, unusual camera angles, or poor lighting can still break detections or tracks.
- Wrong-way checks assume the marked region is one-way in the selected direction.

## Academic and reuse note

This implementation was written independently. The project idea was informed by common traffic-analysis approaches and the public description of `ArcadiusOP/Machine-vision-project`; no source files were copied. Describe your own contribution accurately if you submit or publish this work.
