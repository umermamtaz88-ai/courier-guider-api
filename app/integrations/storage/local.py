import hashlib
import uuid
from pathlib import Path

from app.config import get_settings


class LocalStorage:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.root = Path(self.settings.object_storage_local_path)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, tenant_id: uuid.UUID, filename: str, content: bytes) -> tuple[str, str]:
        tenant_dir = self.root / str(tenant_id)
        tenant_dir.mkdir(parents=True, exist_ok=True)
        key = f"{tenant_id}/{uuid.uuid4().hex}_{filename}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key, hashlib.sha256(content).hexdigest()

    def read(self, storage_key: str) -> bytes:
        return (self.root / storage_key).read_bytes()
