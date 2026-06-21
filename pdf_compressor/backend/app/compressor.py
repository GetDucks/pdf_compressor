from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Result:
    path: Path
    reached: bool
    dpi: int
    jpeg_quality: int
    original: int
    compressed: int


# Profiles run from highest quality to lowest quality.
# Native-resolution profiles re-encode images without reducing resolution.
# Downsampled profiles are used only when stronger compression is needed.
COMPRESSION_PROFILES: list[tuple[int | None, int, bool]] = [
    # dpi, jpeg quality, downsample
    (None, 98, False),
    (None, 95, False),
    (None, 92, False),
    (None, 90, False),
    (None, 88, False),
    (None, 86, False),
    (None, 84, False),
    (None, 82, False),
    (None, 80, False),

    (600, 95, True),
    (500, 93, True),
    (450, 92, True),
    (400, 90, True),
    (350, 88, True),
    (325, 86, True),
    (300, 84, True),
    (275, 82, True),
    (250, 80, True),
    (225, 78, True),
    (200, 76, True),
    (180, 74, True),
    (165, 72, True),
    (150, 68, True),
    (135, 64, True),
    (120, 60, True),
    (108, 56, True),
    (96, 52, True),
    (84, 47, True),
    (72, 42, True),
    (60, 36, True),
    (55, 32, True),
    (45, 27, True),
    (40, 25, True),
]


def find_ghostscript() -> str:
    """
    Find the Ghostscript executable on Linux, macOS, or Windows.
    """

    for command in ("gs", "gswin64c", "gswin32c"):
        executable = shutil.which(command)

        if executable:
            return executable

    raise RuntimeError(
        "Ghostscript was not found. Make sure it is installed and available in PATH."
    )


def create_candidate(
    source_path: Path,
    output_path: Path,
    dpi: int | None,
    jpeg_quality: int,
    grayscale: bool,
    downsample: bool,
) -> None:
    """
    Create one compressed PDF candidate using a specific compression profile.
    """

    command = [
        find_ghostscript(),
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.5",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dSAFER",

        # General cleanup and font handling.
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dEmbedAllFonts=true",

        # Force color and grayscale images through JPEG encoding.
        "-dAutoFilterColorImages=false",
        "-dAutoFilterGrayImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dGrayImageFilter=/DCTEncode",

        # JPEG quality for this profile.
        f"-dJPEGQ={jpeg_quality}",
    ]

    if downsample and dpi is not None:
        command.extend(
            [
                "-dDownsampleColorImages=true",
                "-dDownsampleGrayImages=true",
                "-dDownsampleMonoImages=true",

                "-dColorImageDownsampleType=/Bicubic",
                "-dGrayImageDownsampleType=/Bicubic",
                "-dMonoImageDownsampleType=/Subsample",

                "-dColorImageDownsampleThreshold=1.0",
                "-dGrayImageDownsampleThreshold=1.0",
                "-dMonoImageDownsampleThreshold=1.0",

                f"-dColorImageResolution={dpi}",
                f"-dGrayImageResolution={dpi}",
                f"-dMonoImageResolution={max(dpi, 200)}",
            ]
        )
    else:
        command.extend(
            [
                "-dDownsampleColorImages=false",
                "-dDownsampleGrayImages=false",
                "-dDownsampleMonoImages=false",
            ]
        )

    if grayscale:
        command.extend(
            [
                "-sColorConversionStrategy=Gray",
                "-dProcessColorModel=/DeviceGray",
            ]
        )

    command.extend(
        [
            f"-sOutputFile={output_path}",
            str(source_path),
        ]
    )

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            completed.stderr.strip() or "Ghostscript compression failed."
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Ghostscript did not generate a valid output file.")


def compress(
    source_path: Path,
    output_path: Path,
    target: int,
    min_dpi: int,
    max_dpi: int = 600,
    gray: bool = False,
) -> Result:
    """
    Compress a PDF toward a maximum target size.

    The function generates several candidates and chooses the largest candidate
    that is still below the target. This avoids unnecessary quality loss.

    If no candidate reaches the target, the smallest generated candidate is
    returned and reached is set to False.
    """

    original_size = source_path.stat().st_size

    if target <= 0:
        raise ValueError("Target size must be greater than zero.")

    if original_size <= target:
        shutil.copy2(source_path, output_path)

        return Result(
            path=output_path,
            reached=True,
            dpi=max_dpi,
            jpeg_quality=100,
            original=original_size,
            compressed=original_size,
        )

    generated_candidates: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_path = Path(temporary_directory)

        for dpi, jpeg_quality, downsample in COMPRESSION_PROFILES:
            # Native-resolution profiles are always eligible.
            # Downsampled profiles must respect the selected DPI floor.
            if dpi is not None:
                if dpi < min_dpi:
                    continue

                if dpi > max_dpi:
                    continue

            profile_name = (
                f"native-q{jpeg_quality}"
                if dpi is None
                else f"{dpi}dpi-q{jpeg_quality}"
            )

            candidate_path = temporary_path / f"{profile_name}.pdf"

            create_candidate(
                source_path=source_path,
                output_path=candidate_path,
                dpi=dpi,
                jpeg_quality=jpeg_quality,
                grayscale=gray,
                downsample=downsample,
            )

            candidate_data = candidate_path.read_bytes()
            candidate_size = len(candidate_data)

            print(
                "Profile: "
                f"{'native resolution' if dpi is None else str(dpi) + ' DPI'} "
                f"/ quality {jpeg_quality} "
                f"-> {candidate_size / 1_000_000:.2f} MB"
            )

            generated_candidates.append(
                {
                    "dpi": dpi if dpi is not None else max_dpi,
                    "jpeg_quality": jpeg_quality,
                    "size": candidate_size,
                    "data": candidate_data,
                }
            )

    if not generated_candidates:
        raise RuntimeError("No valid compression profiles were available.")

    matching_candidates = [
        candidate
        for candidate in generated_candidates
        if int(candidate["size"]) <= target
    ]

    if matching_candidates:
        # Select the largest candidate below the target.
        # This normally preserves the most image data and visual quality.
        selected_candidate = max(
            matching_candidates,
            key=lambda candidate: int(candidate["size"]),
        )
        target_reached = True
    else:
        # Nothing reached the target. Return the smallest generated result.
        selected_candidate = min(
            generated_candidates,
            key=lambda candidate: int(candidate["size"]),
        )
        target_reached = False

    selected_data = selected_candidate["data"]

    if not isinstance(selected_data, bytes):
        raise RuntimeError("The selected candidate contains invalid data.")

    output_path.write_bytes(selected_data)

    return Result(
        path=output_path,
        reached=target_reached,
        dpi=int(selected_candidate["dpi"]),
        jpeg_quality=int(selected_candidate["jpeg_quality"]),
        original=original_size,
        compressed=int(selected_candidate["size"]),
    )
