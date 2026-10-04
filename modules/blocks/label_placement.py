# label_placement.py
# -*- coding: utf-8 -*-
import numpy as np
import math
from .axis_utils import to_px

# Служебные функции
def label_size(label):
    """Размеры метки"""
    return (len(str(label)) * 6.5 + 10, 20)

def label_rect(cx, cy, w, h):
    """Прямоугольник метки"""
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

def rects_overlap(r1, r2, gap=3):
    """Проверка перекрытия"""
    return not (r1[2] < r2[0] + gap or r1[0] > r2[2] - gap or r1[3] < r2[1] + gap or r1[1] > r2[3] - gap)

def edge_dist(rect, px, py):
    """Расстояние до края"""
    x0, y0, x1, y1 = rect
    dx = min(px - x0, x1 - px)
    dy = min(py - y0, y1 - py)
    return 0 if dx < 0 or dy < 0 else math.sqrt(dx**2 + dy**2)

def get_quad(c, d, mean):
    """Определение квадранта"""
    return 'tr' if c >= mean and d > 0 else 'br' if c >= mean else 'tl' if d > 0 else 'bl'

def align_labels(corrs, diffs, labels, x_range, y_range, 
                plot_w=800, plot_h=500, point_size=10, label_gap=5):
    n = len(corrs)
    if n == 0:
        return []
    
    # Подготовка данных
    mean = np.mean(corrs)
    pts = [to_px(corrs[i], diffs[i], x_range, y_range, plot_w, plot_h) for i in range(n)]
    
    dirs = {
        'tr': [(0, -20), (20, -20), (20, 0), (20, 20), (0, 20)],
        'tl': [(0, -20), (-20, -20), (-20, 0), (-20, 20), (0, 20)],
        'br': [(0, 20), (20, 20), (20, 0), (20, -20), (0, -20)],
        'bl': [(0, 20), (-20, 20), (-20, 0), (-20, -20), (0, -20)]
    }
    
    placed = []
    offs = [None] * n
    order = sorted(range(n), key=lambda i: abs(diffs[i]), reverse=True)
    
    for idx in order:
        px, py = pts[idx]
        lbl = labels[idx]
        w, h = label_size(lbl)
        q = get_quad(corrs[idx], diffs[idx], mean)
        d = dirs[q]
        best, best_d = None, float('inf')
        
        # Первый проход
        for dx, dy in d:
            cx, cy = px + dx, py + dy
            r = label_rect(cx, cy, w, h)
            valid = True
            
            # Оптимизированная проверка валидности
            if all(not rects_overlap(r, pr, 4) for pr in placed):
                dist = edge_dist(r, px, py)
                if dist < best_d:
                    best_d, best = dist, (dx, dy)
        
        # Второй проход с увеличенными смещениями
        if not best:
            for dx,dy in d:
                dx2,dy2=int(dx*1.5),int(dy*1.5)
                cx,cy=px+dx2,py+dy2
                r=label_rect(cx,cy,w,h)
                valid=True
                
                for pr in placed:
                    if rects_overlap(r,pr,4):valid=False
                
                if valid:
                    dist=edge_dist(r,px,py)  # Используем новую функцию
                    if dist<best_d:best=(dx2,dy2)
        
        # Проверка типа best_offset
        if isinstance(best, tuple):
            offs[idx]=best
            if best:
                cx = px + best[0]
                cy = py + best[1]
                placed.append(label_rect(cx, cy, w, h))
        else:
            offs[idx] = d[0]  # Используем первое направление по умолчанию
    
    return offs  # Возврат смещений
