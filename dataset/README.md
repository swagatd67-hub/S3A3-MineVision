# PipeVision Inspection Dataset

YOLO object-detection layout:

```text
dataset/
├── data.yaml
├── images/{train,val,test}/
└── labels/{train,val,test}/
```

Each image must have a label file with the same filename stem.

YOLO label format:

```text
class_id center_x center_y width height
```

Coordinates are normalized to `[0, 1]`, with positive width and height.

Classes:
0 blockage
1 debris
2 crack
3 corrosion
4 sediment
5 structural_damage
