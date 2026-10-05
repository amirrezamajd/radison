import shutil
import zipfile
from pathlib import Path

from django.conf import settings


class TourUploadError(Exception):
    pass


def _is_within(base: Path, target: Path) -> bool:
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _find_index(root: Path) -> Path | None:
    direct = root / "index.html"
    if direct.is_file():
        return direct
    matches = sorted(p for p in root.rglob("index.html") if "__MACOSX" not in p.parts)
    return matches[0] if matches else None


def extract_tour_zip(uploaded_file, slug: str) -> str:
    """
    Extract a Pano2VR (or similar) ZIP into MEDIA_ROOT/virtual-tours/<slug>/.
    Returns storage_dir relative to virtual-tours/ (folder that contains index.html).
    """
    tours_root = Path(settings.MEDIA_ROOT) / "virtual-tours"
    tours_root.mkdir(parents=True, exist_ok=True)
    dest = tours_root / slug
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    temp_zip = dest / "_upload.zip"
    try:
        with temp_zip.open("wb") as out:
            for chunk in uploaded_file.chunks():
                out.write(chunk)

        if not zipfile.is_zipfile(temp_zip):
            raise TourUploadError("فایل باید ZIP معتبر باشد.")

        with zipfile.ZipFile(temp_zip, "r") as archive:
            for info in archive.infolist():
                name = info.filename.replace("\\", "/")
                if name.startswith("/") or ".." in Path(name).parts:
                    raise TourUploadError("ساختار ZIP ناامن است.")
                target = (dest / name).resolve()
                if not _is_within(dest, target):
                    raise TourUploadError("مسیر فایل از پوشه مقصد خارج است.")
            archive.extractall(dest)
    except TourUploadError:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    except zipfile.BadZipFile as exc:
        shutil.rmtree(dest, ignore_errors=True)
        raise TourUploadError("فایل ZIP خراب است.") from exc
    finally:
        if temp_zip.exists():
            temp_zip.unlink(missing_ok=True)

    # Drop macOS junk folders.
    junk = dest / "__MACOSX"
    if junk.exists():
        shutil.rmtree(junk, ignore_errors=True)

    # Unwrap single root folder (e.g. daya/index.html).
    top_items = [p for p in dest.iterdir() if p.name != "__MACOSX"]
    if len(top_items) == 1 and top_items[0].is_dir() and (top_items[0] / "index.html").is_file():
        nested = top_items[0]
        staging = dest.parent / f".{slug}-staging"
        if staging.exists():
            shutil.rmtree(staging)
        nested.rename(staging)
        shutil.rmtree(dest)
        staging.rename(dest)

    index_path = _find_index(dest)
    if index_path is None:
        shutil.rmtree(dest, ignore_errors=True)
        raise TourUploadError("داخل ZIP فایل index.html پیدا نشد.")

    content_root = index_path.parent
    return str(content_root.relative_to(tours_root)).replace("\\", "/")


def delete_tour_files(storage_dir: str) -> None:
    top = storage_dir.split("/")[0]
    if not top:
        return
    folder = Path(settings.MEDIA_ROOT) / "virtual-tours" / top
    if folder.exists() and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
