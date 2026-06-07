import os
import cloudinary
import cloudinary.uploader
import cloudinary.api

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True,
)

UPLOAD_PRESET = "storage_unsigned"


def ensure_upload_preset() -> None:
    """Crée le preset d'upload non signé s'il n'existe pas."""
    cfg = cloudinary.config()
    if not cfg.cloud_name or not cfg.api_key:
        return
    try:
        cloudinary.api.upload_preset(UPLOAD_PRESET)
    except Exception:
        try:
            cloudinary.api.create_upload_preset(
                name=UPLOAD_PRESET,
                unsigned=True,
                use_filename=False,
            )
        except Exception:
            pass


def _resource_type(mime_type: str) -> str:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("video/") or mime_type.startswith("audio/"):
        return "video"
    return "raw"


def upload_file(content: bytes, public_id: str, mime_type: str) -> str:
    """Upload bytes to Cloudinary. Returns secure_url."""
    cfg = cloudinary.config()
    if not cfg.cloud_name or not cfg.api_key:
        raise RuntimeError(
            "Cloudinary non configuré — ajoutez CLOUDINARY_CLOUD_NAME, "
            "CLOUDINARY_API_KEY et CLOUDINARY_API_SECRET dans les variables d'env Render."
        )
    result = cloudinary.uploader.upload(
        content,
        public_id=public_id,
        resource_type=_resource_type(mime_type),
        use_filename=False,
        overwrite=True,
    )
    return result["secure_url"]


def delete_file(public_id: str, mime_type: str) -> None:
    """Delete a file from Cloudinary (best-effort)."""
    try:
        cloudinary.uploader.destroy(public_id, resource_type=_resource_type(mime_type))
    except Exception:
        pass
