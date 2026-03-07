---
name: image-generation
description: Create data visualizations, infographics, charts, and technical diagrams as PNG or JPG images. Use this skill when users need professional images for presentations, reports, documentation, or social media. Focuses on clarity, data accuracy, and visual communication rather than artistic expression.
license: Apache-2.0
---

# Image Generation

Create clear, professional images for data visualization, infographics, charts, diagrams, and technical illustrations. This skill focuses on practical visual communication - outputting PNG and JPG files optimized for presentations, reports, documentation, and digital media.

## When to Use This Skill

Use this skill when the user requests:
- **Data visualizations**: Bar charts, line graphs, pie charts, scatter plots, heatmaps
- **Infographics**: Visual representations of information, statistics, or processes
- **Technical diagrams**: Flowcharts, system architecture, network diagrams, org charts
- **Comparison images**: Before/after, feature comparisons, product matrices
- **Social media graphics**: Quote cards, statistics, announcement images
- **Reference images**: Quick visual guides, cheat sheets, visual summaries

**Do NOT use this skill for:**
- Artistic or abstract visual art (use `canvas-design` instead)
- Interactive or generative art (use `algorithmic-art` instead)
- Editing existing images (use `image-editing` instead)

## Output Requirements

Generate images in the following formats:
- **PNG**: For images with transparency, sharp text, diagrams, or screenshots
- **JPG/JPEG**: For photographs, complex images, or when smaller file size is needed

### Image Specifications

**Standard Dimensions:**
- Presentation slide: 1920x1080px (16:9) or 1280x720px
- Social media (Instagram square): 1080x1080px
- Social media (Instagram story): 1080x1920px (9:16)
- Social media (Twitter/X): 1200x675px
- Blog header: 1200x630px
- Print (300 DPI): Calculate based on physical size
- Custom: As requested by user

**Quality Guidelines:**
- Use high resolution (minimum 72 DPI for web, 300 DPI for print)
- Ensure text is crisp and readable at intended viewing size
- Optimize file size without sacrificing quality
- Include proper margins and padding

## Creation Methods

### Method 1: Python with Pillow (Recommended for most cases)

```python
from PIL import Image, ImageDraw, ImageFont

# Create canvas
img = Image.new('RGB', (1920, 1080), color='#FFFFFF')
draw = ImageDraw.Draw(img)

# Draw shapes
draw.rectangle([100, 100, 500, 400], fill='#2563EB', outline='#1E40AF', width=2)
draw.ellipse([600, 100, 900, 400], fill='#10B981')

# Add text (use default font or load a specific font)
try:
    font = ImageFont.truetype("arial.ttf", 36)
except:
    font = ImageFont.load_default()
draw.text((100, 50), "Title Text", fill='#1F2937', font=font)

# Save
img.save('output.png', 'PNG')
img.save('output.jpg', 'JPEG', quality=95)
```

### Method 2: HTML Canvas + Puppeteer/Playwright (For complex charts)

```html
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body>
    <canvas id="canvas" width="1920" height="1080"></canvas>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        // Draw visualization
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        // ... add chart/diagram code
    </script>
</body>
</html>
```

Then capture with a headless browser or use `html2image` Python library:

```python
from html2image import Html2Image
hti = Html2Image(size=(1920, 1080))
hti.screenshot(html_file='chart.html', save_as='chart.png')
```

### Method 3: Matplotlib/Seaborn (For data-heavy charts)

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
ax.bar(['Q1', 'Q2', 'Q3', 'Q4'], [45, 62, 58, 71], color='#2563EB')
ax.set_title('2024 Quarterly Sales', fontsize=24, fontweight='bold')
ax.set_ylabel('Sales ($K)', fontsize=14)
plt.tight_layout()
plt.savefig('chart.png', dpi=150, bbox_inches='tight')
plt.close()
```

## Chart Types and When to Use Them

| Chart Type | Best For |
|-----------|----------|
| Bar Chart | Comparing quantities across categories |
| Line Graph | Showing trends over time |
| Pie Chart | Proportions of a whole (max 5-7 slices) |
| Scatter Plot | Correlation between two variables |
| Heatmap | Intensity across two dimensions |
| Flowchart | Process steps and decision points |
| Org Chart | Hierarchical relationships |
| Timeline | Chronological events |
| Comparison Table | Side-by-side feature comparison |

## Design Best Practices

### Typography
- Use sans-serif fonts for clarity (Arial, Helvetica, Roboto)
- Font sizes: Title 32-48px, Headings 24-32px, Body 16-20px, Labels 12-16px
- Ensure adequate line spacing (1.4-1.6x font size)

### Color
- Limit palette to 2-5 colors plus neutrals
- Ensure sufficient contrast (WCAG AA: 4.5:1 for text)
- Consider colorblind accessibility (avoid red/green alone)
- Recommended palettes:
  - Professional: `#2563EB, #475569, #F1F5F9`
  - Warm: `#EA580C, #78350F, #FED7AA`
  - Vibrant: `#EF4444, #F59E0B, #10B981, #3B82F6`

### Layout
- Use consistent margins (minimum 40-60px from edges)
- Align elements to a grid
- Group related information together
- Use whitespace to separate sections

### Data Visualization Principles
- Always label axes and provide units
- Start Y-axis at zero for bar charts
- Order categories logically
- Highlight the key insight
- Keep it simple - remove unnecessary elements

## Accessibility Considerations

- Use sufficient color contrast
- Don't rely on color alone to convey meaning
- Include text labels and descriptions
- Use patterns or shapes in addition to colors when possible

## File Format Decision Guide

| Choose PNG when | Choose JPG when |
|----------------|-----------------|
| Sharp text/lines | Photographic content |
| Transparency needed | Smaller file size needed |
| Will be edited later | Final output only |
| Maximum quality | Many colors/gradients |

## Dependencies

```bash
pip install Pillow matplotlib
# Optional for HTML-based generation:
pip install html2image
```
