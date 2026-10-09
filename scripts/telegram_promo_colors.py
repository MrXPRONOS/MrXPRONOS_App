"""Telegram button palette chosen from the actual promotional image.

Telegram supports native styles: primary (blue), success (green), danger (red).
Neutral grays/whites and small overlaid elements are downweighted. No custom
RGB/HEX button colors are possible on Telegram.
"""
from pathlib import Path
from PIL import Image, ImageOps
import colorsys

def dominant_button_style(image_path, fallback="primary"):
    try:
        with Image.open(Path(image_path)) as original:
            image=ImageOps.exif_transpose(original).convert("RGBA")
            image.thumbnail((96,96))
            samples={"primary":0.0,"success":0.0,"danger":0.0}
            for red,green,blue,alpha in image.getdata():
                if alpha<160:continue
                hue,sat,val=colorsys.rgb_to_hsv(red/255,green/255,blue/255)
                if sat<0.23 or val<0.17 or val>0.98:continue
                weight=(sat**1.3)*(0.5+val/2)
                if hue<0.08 or hue>=0.93 or 0.08<=hue<0.17:
                    samples["danger"]+=weight
                elif 0.17<=hue<0.50:
                    samples["success"]+=weight
                else:
                    samples["primary"]+=weight
            if max(samples.values())<0.1:
                return fallback
            return max(samples,key=samples.get)
    except (OSError,ValueError):
        return fallback

def colorized_button(text,url,image_path, fallback="primary"):
    return {"text":text,"url":url,
            "style":dominant_button_style(image_path,fallback)}
