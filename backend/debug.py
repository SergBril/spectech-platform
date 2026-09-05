"""Диагностика MinIO и таблицы uploaded_files."""

import sqlite3
import traceback

print("=" * 60)
print("=== Test 1: Check table uploaded_files exists ===")
print("=" * 60)
try:
    conn = sqlite3.connect("test.db")
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    conn.close()
    print("Tables in test.db:")
    for t in sorted(tables):
        print(f"  - {t}")
    print()
    if "uploaded_files" in tables:
        print("✅ uploaded_files table EXISTS")
    else:
        print("❌ uploaded_files table MISSING!")
        print("   Solution: alembic upgrade head")
except Exception as e:
    print(f"❌ ERROR: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("=== Test 2: Check MinIO connection ===")
print("=" * 60)
try:
    import boto3
    from botocore.exceptions import EndpointConnectionError

    s3 = boto3.client(
        "s3",
        endpoint_url="http://localhost:9000",
        aws_access_key_id="spectech",
        aws_secret_access_key="spectech123",
    )
    response = s3.list_buckets()
    buckets = [b["Name"] for b in response["Buckets"]]
    print(f"✅ MinIO connected. Buckets: {buckets}")
    if "spectech-files" in buckets:
        print("✅ Bucket 'spectech-files' EXISTS")
    else:
        print("❌ Bucket 'spectech-files' MISSING!")
        print("   Solution: create via http://localhost:9001")
except EndpointConnectionError:
    print("❌ ERROR: MinIO not running on localhost:9000")
    print("   Solution: docker compose up -d minio")
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
print("=== Test 3: Try storage_service.get_storage_stats() ===")
print("=" * 60)
try:
    from app.services import storage_service

    stats = storage_service.get_storage_stats()
    print(f"✅ Stats: {stats}")
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("=== Test 4: Try DB query on UploadedFile ===")
print("=" * 60)
try:
    from sqlalchemy import func

    from app.core.db import SessionLocal
    from app.models.telematics import UploadedFile

    db = SessionLocal()
    count = db.query(func.count(UploadedFile.id)).scalar() or 0
    print(f"✅ UploadedFile count: {count}")
    db.close()
except Exception as e:
    print(f"❌ ERROR: {type(e).__name__}: {e}")
    traceback.print_exc()

print()
print("=" * 60)
print("=== DONE ===")
print("=" * 60)
