import io

import pikepdf
from PIL import Image

JPEG_QUALITY = 60
MAX_IMAGE_DIMENSION = 1600
MIN_IMAGE_DIMENSION_TO_PROCESS = 100


class CompressionError(Exception):
    """Raised when PDF compression cannot proceed (password-protected, invalid PDF, etc.)."""

    pass


def compress_pdf(input_stream) -> io.BytesIO:
    """
    Compress a PDF by recompressing embedded images and recompressing the PDF structure.

    Uses pikepdf (qpdf) + Pillow. Everything stays in memory.

    :param input_stream: file-like object opened for reading (e.g. Flask's file.stream)
    :return: BytesIO seeked to 0 containing the compressed PDF
    :raises CompressionError: for password-protected or invalid PDFs (user-facing message)
    """
    # Ensure stream is at start if possible
    try:
        input_stream.seek(0)
    except Exception:
        pass

    try:
        pdf = pikepdf.open(input_stream)
    except pikepdf.PasswordError:
        raise CompressionError("This PDF is password-protected. Remove the password before compressing.")
    except pikepdf.PdfError:
        raise CompressionError("This file doesn't look like a valid PDF and couldn't be opened.")
    except Exception as e:
        # Fallback: treat any open failure as invalid PDF if not password
        # but re-raise CompressionError for known messages; otherwise let it bubble?
        # Spec says catch PasswordError and PdfError only. We re-wrap PdfError-like.
        raise CompressionError("This file doesn't look like a valid PDF and couldn't be opened.") from e

    with pdf:
        for page in pdf.pages:
            # page.images is deprecated in favor of get_images, but spec mandates page.images.values()
            # Keep compatibility: try page.images, fallback to get_images()
            try:
                images = page.images
            except AttributeError:
                images = page.get_images()

            # images is a mapping of name -> Stream object
            # Use list() to avoid mutation issues while iterating
            for raw_image in list(images.values()):
                # Skip images with transparency (soft mask)
                if pikepdf.Name("/SMask") in raw_image:
                    continue

                # Wrap in PdfImage to inspect dimensions
                try:
                    pdf_image = pikepdf.PdfImage(raw_image)
                except Exception:
                    continue

                # Skip small icons/logos
                # Skip if longest side is smaller than threshold
                if max(pdf_image.width, pdf_image.height) < MIN_IMAGE_DIMENSION_TO_PROCESS:
                    continue

                # Decode via Pillow
                try:
                    pil_image = pdf_image.as_pil_image()
                except Exception:
                    continue

                # Downscale if larger than needed for on-screen viewing
                try:
                    if max(pil_image.size) > MAX_IMAGE_DIMENSION:
                        # Use thumbnail to preserve aspect ratio; LANCZOS for quality
                        pil_image.thumbnail(
                            (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION),
                            Image.LANCZOS,
                        )

                    # Handle transparency / modes: JPEG does not support alpha
                    if pil_image.mode in ("RGBA", "LA"):
                        background = Image.new("RGB", pil_image.size, (255, 255, 255))
                        # paste using alpha channel as mask
                        try:
                            alpha = pil_image.split()[-1]
                        except Exception:
                            alpha = None
                        if alpha is not None:
                            background.paste(pil_image, mask=alpha)
                        else:
                            background.paste(pil_image)
                        pil_image = background
                    elif pil_image.mode == "P":
                        # Palette images: convert via RGBA to handle transparency properly
                        if "transparency" in pil_image.info:
                            pil_image = pil_image.convert("RGBA")
                            background = Image.new("RGB", pil_image.size, (255, 255, 255))
                            background.paste(pil_image, mask=pil_image.split()[-1])
                            pil_image = background
                        else:
                            pil_image = pil_image.convert("RGB")
                    elif pil_image.mode not in ("RGB", "L"):
                        # Convert other modes (CMYK, etc.) to RGB for JPEG
                        # Keep L (grayscale) as RGB? JPEG supports L but we normalize to RGB for simplicity
                        # We'll convert everything not RGB to RGB; if L we could keep L but spec says update ColorSpace to DeviceRGB
                        pil_image = pil_image.convert("RGB")

                    # Ensure RGB for JPEG if not L – we convert L to RGB as well to match spec's ColorSpace update
                    if pil_image.mode == "L":
                        pil_image = pil_image.convert("RGB")

                    # Re-encode as JPEG
                    jpeg_buffer = io.BytesIO()
                    pil_image.save(
                        jpeg_buffer,
                        format="JPEG",
                        quality=JPEG_QUALITY,
                        optimize=True,
                    )
                    jpeg_bytes = jpeg_buffer.getvalue()
                except Exception:
                    # If Pillow fails, leave image untouched
                    try:
                        pil_image.close()
                    except Exception:
                        pass
                    continue
                finally:
                    # Close pil_image if it has close method and wasn't reassigned?
                    pass

                # Only replace if actually smaller
                try:
                    original_len = len(raw_image.read_raw_bytes())
                except Exception:
                    try:
                        original_len = len(raw_image.get_stream_buffer())
                    except Exception:
                        original_len = None

                if original_len is not None and len(jpeg_bytes) >= original_len:
                    continue

                # Replace image data
                try:
                    raw_image.write(jpeg_bytes, filter=pikepdf.Name("/DCTDecode"))
                except Exception:
                    continue

                # Update metadata to match new JPEG
                # Use pil_image.size which reflects thumbnail size
                new_width, new_height = pil_image.size
                raw_image[pikepdf.Name("/Width")] = new_width
                raw_image[pikepdf.Name("/Height")] = new_height
                raw_image[pikepdf.Name("/ColorSpace")] = pikepdf.Name("/DeviceRGB")
                raw_image[pikepdf.Name("/BitsPerComponent")] = 8

                # Remove DecodeParms which is not valid for DCTDecode
                if pikepdf.Name("/DecodeParms") in raw_image:
                    del raw_image[pikepdf.Name("/DecodeParms")]
                # Also remove Interpolate if present? Keep as is – not harmful

                # Ensure Filter is exactly /DCTDecode (write already sets it)
                # For images that had an array of filters, write will overwrite

                # Close pil_image to free memory
                try:
                    pil_image.close()
                except Exception:
                    pass

        output = io.BytesIO()
        pdf.save(
            output,
            compress_streams=True,
            stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
            object_stream_mode=pikepdf.ObjectStreamMode.generate,
        )
        output.seek(0)
        return output
