import io, socket, struct, zipfile
from pathlib import Path
from .domain import Problem

class LocalStorage:
    def __init__(self, root): self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
    def path(self, key):
        import uuid
        uuid.UUID(key)
        return self.root / key
    def put(self, key, content): self.path(key).write_bytes(content)
    def get(self, key): return self.path(key).read_bytes()
    def delete(self, key): self.path(key).unlink(missing_ok=True)

class S3Storage:
    def __init__(self, settings):
        import boto3
        self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url, aws_access_key_id=settings.s3_access_key_id, aws_secret_access_key=settings.s3_secret_access_key)
        self.bucket = settings.s3_bucket
    def put(self, key, content): self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ServerSideEncryption="AES256")
    def get(self, key): return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
    def delete(self, key): self.client.delete_object(Bucket=self.bucket, Key=key)

def storage(settings):
    return S3Storage(settings) if settings.storage_provider == "s3" else LocalStorage(settings.storage_root)

MIMES = {".pdf": "application/pdf", ".txt": "text/plain", ".md": "text/markdown", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".mp4": "video/mp4"}
def validate_file(filename, declared, content):
    ext = Path(filename).suffix.lower()
    mime = MIMES.get(ext)
    if not mime or not content: raise Problem(422, "INVALID_FILE", "不支援的檔案格式或空檔案")
    if declared not in (mime, "application/octet-stream", "text/plain" if ext == ".md" else mime): raise Problem(422, "MIME_MISMATCH", "檔案類型不符")
    ok = False
    if ext in (".txt", ".md"):
        try: content.decode("utf-8"); ok = b"\0" not in content
        except UnicodeDecodeError: pass
    elif ext == ".pdf": ok = content.startswith(b"%PDF-")
    elif ext == ".png": ok = content.startswith(b"\x89PNG\r\n\x1a\n")
    elif ext in (".jpg", ".jpeg"): ok = content.startswith(b"\xff\xd8\xff")
    elif ext == ".mp4": ok = len(content) > 12 and content[4:8] == b"ftyp"
    else:
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                total = sum(i.file_size for i in z.infolist())
                ok = total <= 100 * 1024 * 1024 and "[Content_Types].xml" in z.namelist() and ("word/document.xml" if ext == ".docx" else "ppt/presentation.xml") in z.namelist()
        except zipfile.BadZipFile: pass
    if not ok: raise Problem(422, "MIME_MISMATCH", "檔案內容不符合格式")
    return mime

def scan(content, settings):
    with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=30) as conn:
        conn.sendall(b"zINSTREAM\0")
        for start in range(0, len(content), 65536):
            chunk = content[start:start+65536]; conn.sendall(struct.pack("!I", len(chunk)) + chunk)
        conn.sendall(struct.pack("!I", 0))
        result = b""
        while b"\0" not in result:
            chunk = conn.recv(4096)
            if not chunk: break
            result += chunk
        if not result.rstrip(b"\0").endswith(b": OK"):
            raise Problem(422, "FILE_REJECTED", "檔案未通過掃描")
