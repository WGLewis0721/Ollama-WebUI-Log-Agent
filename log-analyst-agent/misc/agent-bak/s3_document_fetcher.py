#!/usr/bin/env python3
"""
S3 Document Fetcher - Load documents from S3 for RAG
"""

import os
import boto3
from pathlib import Path
from typing import List, Dict, Optional
import json

class S3DocumentFetcher:
    """Fetch and manage documents from S3 bucket"""
    
    def __init__(
        self,
        bucket_name: str,
        prefix: str = "knowledge-base/",
        region: str = "us-east-1"
    ):
        self.bucket_name = bucket_name
        self.prefix = prefix
        self.s3_client = boto3.client('s3', region_name=region)
        
        print(f"✓ S3 Document Fetcher initialized")
        print(f"   Bucket: {bucket_name}")
        print(f"   Prefix: {prefix}")
    
    def list_documents(self, extension: Optional[str] = None) -> List[Dict]:
        """
        List all documents in S3 bucket
        
        Args:
            extension: Filter by extension (e.g., '.txt', '.md', '.pdf')
        
        Returns:
            List of document metadata
        """
        documents = []
        
        try:
            paginator = self.s3_client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix)
            
            for page in pages:
                if 'Contents' not in page:
                    continue
                
                for obj in page['Contents']:
                    key = obj['Key']
                    
                    # Skip directories
                    if key.endswith('/'):
                        continue
                    
                    # Filter by extension if specified
                    if extension and not key.endswith(extension):
                        continue
                    
                    documents.append({
                        'key': key,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'].isoformat(),
                        'filename': Path(key).name,
                        'path': key
                    })
            
            print(f"✓ Found {len(documents)} documents in S3")
            return documents
            
        except Exception as e:
            print(f"✗ Error listing documents: {e}")
            return []
    
    def download_document(self, key: str, local_path: Optional[str] = None) -> Optional[str]:
        """
        Download a document from S3
        
        Args:
            key: S3 object key
            local_path: Local path to save (optional)
        
        Returns:
            Local file path or None if failed
        """
        try:
            if local_path is None:
                local_path = f"/tmp/{Path(key).name}"
            
            self.s3_client.download_file(self.bucket_name, key, local_path)
            print(f"✓ Downloaded: {key}")
            return local_path
            
        except Exception as e:
            print(f"✗ Error downloading {key}: {e}")
            return None
    
    def read_document(self, key: str) -> Optional[str]:
        """
        Read document content directly from S3
        
        Args:
            key: S3 object key
        
        Returns:
            Document content as string or None if failed
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            content = response['Body'].read()
            
            # Try to decode as text
            try:
                return content.decode('utf-8')
            except:
                return content.decode('latin-1')
                
        except Exception as e:
            print(f"✗ Error reading {key}: {e}")
            return None
    
    def upload_document(self, local_path: str, s3_key: Optional[str] = None) -> bool:
        """
        Upload a document to S3
        
        Args:
            local_path: Path to local file
            s3_key: S3 key (optional, defaults to filename in prefix)
        
        Returns:
            True if successful, False otherwise
        """
        try:
            if s3_key is None:
                s3_key = f"{self.prefix}{Path(local_path).name}"
            
            self.s3_client.upload_file(local_path, self.bucket_name, s3_key)
            print(f"✓ Uploaded: {s3_key}")
            return True
            
        except Exception as e:
            print(f"✗ Error uploading {local_path}: {e}")
            return False
    
    def get_document_metadata(self, key: str) -> Optional[Dict]:
        """Get metadata for a document"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'key': key,
                'size': response['ContentLength'],
                'last_modified': response['LastModified'].isoformat(),
                'content_type': response.get('ContentType', 'unknown'),
                'metadata': response.get('Metadata', {})
            }
        except Exception as e:
            print(f"✗ Error getting metadata for {key}: {e}")
            return None
    
    def sync_directory(self, local_dir: str, s3_prefix: Optional[str] = None) -> int:
        """
        Sync a local directory to S3
        
        Args:
            local_dir: Local directory path
            s3_prefix: S3 prefix (optional, uses default if None)
        
        Returns:
            Number of files uploaded
        """
        if s3_prefix is None:
            s3_prefix = self.prefix
        
        uploaded = 0
        local_path = Path(local_dir)
        
        for file_path in local_path.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(local_path)
                s3_key = f"{s3_prefix}{relative_path}"
                
                if self.upload_document(str(file_path), s3_key):
                    uploaded += 1
        
        print(f"✓ Synced {uploaded} files to S3")
        return uploaded


def test_s3_connection():
    """Test S3 connection"""
    bucket_name = os.getenv('S3_BUCKET_NAME', 'your-bucket-name')
    prefix = os.getenv('S3_PREFIX', 'knowledge-base/')
    
    try:
        fetcher = S3DocumentFetcher(bucket_name, prefix)
        documents = fetcher.list_documents()
        
        if documents:
            print(f"\n✓ Found {len(documents)} documents:")
            for doc in documents[:5]:  # Show first 5
                print(f"  - {doc['filename']} ({doc['size']} bytes)")
        else:
            print("\n⚠ No documents found in bucket")
            
    except Exception as e:
        print(f"\n✗ S3 connection failed: {e}")


if __name__ == "__main__":
    test_s3_connection()
