---
name: image-editing
description: Edit, transform, and manipulate existing images. Use this skill when users want to crop, resize, rotate, add watermarks, apply filters, adjust colors, composite images, convert formats, add text overlays, remove backgrounds, or perform any modification to existing image files (PNG, JPG, WEBP, BMP, TIFF, GIF).
license: Apache-2.0
---

# Image Editing

Edit and transform existing images using Python's Pillow (PIL) library. This skill handles all common image manipulation tasks including cropping, resizing, filtering, compositing, and format conversion.

## When to Use This Skill

Use this skill when the user wants to:
- **Resize/Scale**: Change image dimensions, create thumbnails
- **Crop**: Extract a portion of an image
- **Rotate/Flip**: Rotate by angle or flip horizontally/vertically
- **Watermark**: Add text or image watermarks
- **Filters**: Apply blur, sharpen, edge detection, emboss, etc.
- **Color adjustments**: Brightness, contrast, saturation, grayscale, sepia
- **Composite**: Overlay, merge, or blend multiple images
- **Format conversion**: Convert between PNG, JPG, WEBP, BMP, TIFF, GIF
- **Text overlay**: Add text, labels, or captions to images
- **Batch processing**: Apply the same edits to multiple images
- **Background**: Remove or replace backgrounds (simple cases)
- **Metadata**: Read or strip EXIF data

**Do NOT use this skill for:**
- Creating images from scratch (use `image-generation` instead)
- Creating artistic/design images (use `canvas-design` instead)
- Creating PowerPoint/PDF/Word documents (use `pptx`/`pdf`/`docx` instead)

## Core Operations

### Read and Save Images

```python
from PIL import Image

# Open image
img = Image.open('input.png')
print(f"Size: {img.size}, Mode: {img.mode}, Format: {img.format}")

# Save in different formats
img.save('output.png')                          # PNG
img.save('output.jpg', 'JPEG', quality=95)      # JPG with quality
img.save('output.webp', 'WEBP', quality=90)     # WebP
img.save('output.bmp')                          # BMP
img.save('output.tiff', compression='tiff_lzw') # TIFF compressed

# Convert color mode if needed
rgb_img = img.convert('RGB')   # For saving as JPG (no alpha)
rgba_img = img.convert('RGBA') # For transparency support
gray_img = img.convert('L')    # Grayscale
```

### Resize and Scale

```python
from PIL import Image

img = Image.open('input.png')

# Resize to exact dimensions
resized = img.resize((800, 600), Image.LANCZOS)

# Resize maintaining aspect ratio (fit within bounds)
img.thumbnail((800, 600), Image.LANCZOS)  # Modifies in-place

# Scale by percentage
width, height = img.size
scale = 0.5  # 50%
scaled = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)

# Resize to specific width, maintaining aspect ratio
new_width = 800
ratio = new_width / img.width
new_height = int(img.height * ratio)
resized = img.resize((new_width, new_height), Image.LANCZOS)
```

### Crop

```python
from PIL import Image

img = Image.open('input.png')

# Crop by coordinates (left, upper, right, lower)
cropped = img.crop((100, 100, 500, 400))

# Center crop to specific size
w, h = img.size
target_w, target_h = 800, 600
left = (w - target_w) // 2
top = (h - target_h) // 2
center_cropped = img.crop((left, top, left + target_w, top + target_h))

# Crop to aspect ratio (e.g., 16:9) from center
target_ratio = 16 / 9
current_ratio = w / h
if current_ratio > target_ratio:
    new_w = int(h * target_ratio)
    left = (w - new_w) // 2
    cropped = img.crop((left, 0, left + new_w, h))
else:
    new_h = int(w / target_ratio)
    top = (h - new_h) // 2
    cropped = img.crop((0, top, w, top + new_h))
```

### Rotate and Flip

```python
from PIL import Image

img = Image.open('input.png')

# Rotate (counterclockwise)
rotated_90 = img.rotate(90, expand=True)
rotated_45 = img.rotate(45, expand=True, fillcolor='white')

# Flip
flipped_h = img.transpose(Image.FLIP_LEFT_RIGHT)   # Horizontal mirror
flipped_v = img.transpose(Image.FLIP_TOP_BOTTOM)    # Vertical mirror
```

### Filters and Effects

```python
from PIL import Image, ImageFilter, ImageEnhance

img = Image.open('input.png')

# Built-in filters
blurred = img.filter(ImageFilter.GaussianBlur(radius=5))
sharpened = img.filter(ImageFilter.SHARPEN)
edges = img.filter(ImageFilter.FIND_EDGES)
embossed = img.filter(ImageFilter.EMBOSS)
contour = img.filter(ImageFilter.CONTOUR)
detail = img.filter(ImageFilter.DETAIL)
smooth = img.filter(ImageFilter.SMOOTH_MORE)

# Custom kernel filter
kernel = ImageFilter.Kernel(
    size=(3, 3),
    kernel=[0, -1, 0, -1, 5, -1, 0, -1, 0],  # Sharpen
    scale=1, offset=0
)
custom_filtered = img.filter(kernel)

# Enhancements
brightness = ImageEnhance.Brightness(img).enhance(1.3)   # 1.0 = original
contrast = ImageEnhance.Contrast(img).enhance(1.5)
saturation = ImageEnhance.Color(img).enhance(1.2)
sharpness = ImageEnhance.Sharpness(img).enhance(2.0)

# Grayscale
grayscale = img.convert('L')

# Sepia effect
grayscale = img.convert('L')
sepia = Image.merge('RGB', (
    grayscale.point(lambda x: min(255, int(x * 1.2))),
    grayscale.point(lambda x: min(255, int(x * 1.0))),
    grayscale.point(lambda x: min(255, int(x * 0.8))),
))

# Invert colors
from PIL import ImageOps
inverted = ImageOps.invert(img.convert('RGB'))
```

### Text Overlay

```python
from PIL import Image, ImageDraw, ImageFont

img = Image.open('input.png')
draw = ImageDraw.Draw(img)

# Load font (fallback to default)
try:
    font = ImageFont.truetype("arial.ttf", 48)
    small_font = ImageFont.truetype("arial.ttf", 24)
except:
    font = ImageFont.load_default()
    small_font = font

# Simple text
draw.text((50, 50), "Hello World", fill='white', font=font)

# Text with outline/stroke
draw.text((50, 50), "Hello World", fill='white', font=font,
          stroke_width=2, stroke_fill='black')

# Centered text
text = "Centered Title"
bbox = draw.textbbox((0, 0), text, font=font)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]
x = (img.width - text_w) // 2
y = (img.height - text_h) // 2
draw.text((x, y), text, fill='white', font=font)

# Text with background box
padding = 10
draw.rectangle([x - padding, y - padding, x + text_w + padding, y + text_h + padding],
               fill=(0, 0, 0, 180))  # Semi-transparent black (requires RGBA)
draw.text((x, y), text, fill='white', font=font)

img.save('output.png')
```

### Watermark

```python
from PIL import Image, ImageDraw, ImageFont, ImageEnhance

# Text watermark
def add_text_watermark(img_path, text, output_path, opacity=0.3):
    img = Image.open(img_path).convert('RGBA')
    watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    try:
        font = ImageFont.truetype("arial.ttf", 48)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = img.width - text_w - 20
    y = img.height - text_h - 20

    draw.text((x, y), text, fill=(255, 255, 255, int(255 * opacity)), font=font)
    result = Image.alpha_composite(img, watermark)
    result.convert('RGB').save(output_path)

# Image watermark (e.g., logo)
def add_image_watermark(img_path, logo_path, output_path, opacity=0.5, position='bottom-right'):
    img = Image.open(img_path).convert('RGBA')
    logo = Image.open(logo_path).convert('RGBA')

    # Scale logo to reasonable size (e.g., 1/5 of image width)
    logo_w = img.width // 5
    ratio = logo_w / logo.width
    logo_h = int(logo.height * ratio)
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # Adjust opacity
    alpha = logo.split()[3]
    alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
    logo.putalpha(alpha)

    # Position
    margin = 20
    positions = {
        'top-left': (margin, margin),
        'top-right': (img.width - logo_w - margin, margin),
        'bottom-left': (margin, img.height - logo_h - margin),
        'bottom-right': (img.width - logo_w - margin, img.height - logo_h - margin),
        'center': ((img.width - logo_w) // 2, (img.height - logo_h) // 2),
    }
    pos = positions.get(position, positions['bottom-right'])

    img.paste(logo, pos, logo)
    img.convert('RGB').save(output_path)

# Tiled/repeating watermark
def add_tiled_watermark(img_path, text, output_path, opacity=0.15, angle=-30):
    img = Image.open(img_path).convert('RGBA')
    watermark = Image.new('RGBA', img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(watermark)

    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        font = ImageFont.load_default()

    # Tile the text across the entire image
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0] + 100
    text_h = bbox[3] - bbox[1] + 80

    for y in range(-img.height, img.height * 2, text_h):
        for x in range(-img.width, img.width * 2, text_w):
            draw.text((x, y), text, fill=(128, 128, 128, int(255 * opacity)), font=font)

    watermark = watermark.rotate(angle, expand=False, center=(img.width // 2, img.height // 2))
    watermark = watermark.crop((0, 0, img.width, img.height))
    result = Image.alpha_composite(img, watermark)
    result.convert('RGB').save(output_path)
```

### Image Compositing

```python
from PIL import Image

# Overlay one image on another
background = Image.open('bg.png').convert('RGBA')
foreground = Image.open('fg.png').convert('RGBA')
background.paste(foreground, (x, y), foreground)  # 3rd arg = mask for transparency

# Blend two images (same size)
blended = Image.blend(img1, img2, alpha=0.5)  # 0.5 = equal mix

# Side by side
def side_by_side(img1_path, img2_path, output_path, gap=10):
    img1 = Image.open(img1_path)
    img2 = Image.open(img2_path)
    # Match heights
    h = max(img1.height, img2.height)
    img1 = img1.resize((int(img1.width * h / img1.height), h), Image.LANCZOS)
    img2 = img2.resize((int(img2.width * h / img2.height), h), Image.LANCZOS)
    result = Image.new('RGB', (img1.width + gap + img2.width, h), 'white')
    result.paste(img1, (0, 0))
    result.paste(img2, (img1.width + gap, 0))
    result.save(output_path)

# Create image grid/collage
def create_grid(image_paths, cols, output_path, cell_size=(300, 300), gap=5):
    rows_count = (len(image_paths) + cols - 1) // cols
    grid_w = cols * cell_size[0] + (cols - 1) * gap
    grid_h = rows_count * cell_size[1] + (rows_count - 1) * gap
    grid = Image.new('RGB', (grid_w, grid_h), 'white')

    for i, path in enumerate(image_paths):
        img = Image.open(path)
        img.thumbnail(cell_size, Image.LANCZOS)
        row, col = divmod(i, cols)
        x = col * (cell_size[0] + gap)
        y = row * (cell_size[1] + gap)
        # Center within cell
        offset_x = (cell_size[0] - img.width) // 2
        offset_y = (cell_size[1] - img.height) // 2
        grid.paste(img, (x + offset_x, y + offset_y))

    grid.save(output_path)
```

### Background Operations

```python
from PIL import Image

# Simple background removal (white/solid background)
def remove_solid_background(img_path, output_path, bg_color=(255, 255, 255), tolerance=30):
    img = Image.open(img_path).convert('RGBA')
    data = img.getdata()
    new_data = []
    for pixel in data:
        r, g, b, a = pixel
        if (abs(r - bg_color[0]) < tolerance and
            abs(g - bg_color[1]) < tolerance and
            abs(b - bg_color[2]) < tolerance):
            new_data.append((r, g, b, 0))  # Make transparent
        else:
            new_data.append(pixel)
    img.putdata(new_data)
    img.save(output_path, 'PNG')

# Replace background color
def replace_background(img_path, output_path, old_color=(255, 255, 255),
                       new_color=(0, 0, 255), tolerance=30):
    img = Image.open(img_path).convert('RGB')
    data = img.getdata()
    new_data = []
    for pixel in data:
        r, g, b = pixel
        if (abs(r - old_color[0]) < tolerance and
            abs(g - old_color[1]) < tolerance and
            abs(b - old_color[2]) < tolerance):
            new_data.append(new_color)
        else:
            new_data.append(pixel)
    img.putdata(new_data)
    img.save(output_path)
```

### Batch Processing

```python
from PIL import Image
import glob
import os

def batch_process(input_dir, output_dir, operations):
    """
    operations: list of tuples (function, kwargs)
    Example: [('resize', {'size': (800, 600)}), ('filter', {'name': 'SHARPEN'})]
    """
    os.makedirs(output_dir, exist_ok=True)
    files = glob.glob(os.path.join(input_dir, '*'))
    image_exts = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.gif'}

    for filepath in files:
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in image_exts:
            continue

        img = Image.open(filepath)
        filename = os.path.basename(filepath)

        for op, kwargs in operations:
            if op == 'resize':
                img = img.resize(kwargs['size'], Image.LANCZOS)
            elif op == 'thumbnail':
                img.thumbnail(kwargs['size'], Image.LANCZOS)
            elif op == 'rotate':
                img = img.rotate(kwargs.get('angle', 0), expand=True)
            elif op == 'convert':
                img = img.convert(kwargs.get('mode', 'RGB'))
            elif op == 'grayscale':
                img = img.convert('L')

        output_path = os.path.join(output_dir, filename)
        img.save(output_path)
        print(f"Processed: {filename}")

# Example usage:
# batch_process('./input', './output', [
#     ('thumbnail', {'size': (800, 800)}),
#     ('grayscale', {}),
# ])
```

### EXIF Metadata

```python
from PIL import Image
from PIL.ExifTags import TAGS

# Read EXIF data
img = Image.open('photo.jpg')
exif_data = img.getexif()
for tag_id, value in exif_data.items():
    tag = TAGS.get(tag_id, tag_id)
    print(f"{tag}: {value}")

# Strip all EXIF data (privacy)
def strip_exif(img_path, output_path):
    img = Image.open(img_path)
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    clean.save(output_path)
```

### Format Conversion Quick Reference

| From | To | Notes |
|------|----|-------|
| PNG → JPG | `img.convert('RGB').save('out.jpg', quality=95)` | Must convert RGBA→RGB |
| JPG → PNG | `img.save('out.png')` | Lossless |
| Any → WebP | `img.save('out.webp', quality=90)` | Good compression |
| Any → ICO | `img.save('out.ico', sizes=[(32,32),(64,64)])` | For favicons |
| GIF frames | `img.seek(n)` to access frame n | Iterate with `ImageSequence` |
| Any → PDF | `img.save('out.pdf')` | Single image to PDF |

## Advanced: rembg for AI Background Removal

For complex background removal (not just solid colors):

```bash
pip install rembg
```

```python
from rembg import remove
from PIL import Image

input_img = Image.open('input.png')
output_img = remove(input_img)
output_img.save('output.png')
```

## Dependencies

```bash
pip install Pillow
# Optional:
pip install rembg    # AI background removal
```
