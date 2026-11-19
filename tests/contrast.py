"""WCAG contrast calculation shared by palette and rendered-style tests."""


def contrast_ratio(foreground, background):
    """Return the unrounded ratio for two opaque sRGB triples (0..255)."""

    def luminance(rgb):
        channels = [channel / 255 for channel in rgb]
        linear = [
            value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
            for value in channels
        ]
        return sum(
            weight * value for weight, value in zip((0.2126, 0.7152, 0.0722), linear)
        )

    lighter, darker = sorted(
        (luminance(foreground), luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)
