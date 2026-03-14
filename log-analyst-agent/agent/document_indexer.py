#!/usr/bin/env python3
"""
Document Indexer - Fetch from S3 and index to OpenSearch
Builds the knowledge base for RAG-enhanced log analysis
"""

import os
import sys
from pathlib import Path
from typing import List, Optional
import time
from colorama import init, Fore, Style

from s3_document_fetcher import S3DocumentFetcher
from rag_module import RAGManager

init()

class DocumentIndexer:
    """Index documents from S3 into OpenSearch for RAG"""
    
    def __init__(
        self,
        s3_bucket: str,
        s3_prefix: str,
        opensearch_endpoint: str,
        ollama_url: str = "http://localhost:11434",
        aws_region: str = "us-east-1"
    ):
        self.s3_fetcher = S3DocumentFetcher(s3_bucket, s3_prefix, aws_region)
        self.rag_manager = RAGManager(
            opensearch_endpoint=opensearch_endpoint,
            ollama_url=ollama_url,
            region=aws_region
        )
        
        print(f"{Fore.CYAN}📚 Document Indexer Initialized{Style.RESET_ALL}")
    
    def setup(self):
        """Setup embedding model and index"""
        print(f"\n{Fore.YELLOW}🔧 Setting up RAG system...{Style.RESET_ALL}")
        
        # Ensure embedding model is available
        self.rag_manager.ensure_embedding_model()
        
        # Create OpenSearch index with k-NN
        self.rag_manager.create_index()
        
        print(f"{Fore.GREEN}✓ RAG system ready{Style.RESET_ALL}")
    
    def index_all_documents(
        self,
        extensions: Optional[List[str]] = None,
        force_reindex: bool = False
    ) -> int:
        """
        Index all documents from S3
        
        Args:
            extensions: Filter by file extensions (e.g., ['.txt', '.md'])
            force_reindex: Reindex even if document exists
        
        Returns:
            Total number of chunks indexed
        """
        if extensions is None:
            extensions = ['.txt', '.md', '.json', '.yaml', '.yml']
        
        print(f"\n{Fore.CYAN}📄 Fetching documents from S3...{Style.RESET_ALL}")
        
        total_indexed = 0
        
        for ext in extensions:
            documents = self.s3_fetcher.list_documents(extension=ext)
            
            if not documents:
                continue
            
            print(f"\n{Fore.CYAN}Processing {len(documents)} {ext} files...{Style.RESET_ALL}")
            
            for doc in documents:
                try:
                    # Read document content
                    content = self.s3_fetcher.read_document(doc['key'])
                    
                    if not content:
                        print(f"{Fore.YELLOW}⚠ Skipping {doc['filename']} (empty or unreadable){Style.RESET_ALL}")
                        continue
                    
                    # Index the document
                    metadata = {
                        'size': doc['size'],
                        'last_modified': doc['last_modified'],
                        'extension': ext
                    }
                    
                    chunks_indexed = self.rag_manager.index_document(
                        text=content,
                        source=doc['key'],
                        metadata=metadata
                    )
                    
                    total_indexed += chunks_indexed
                    
                    # Small delay to avoid overwhelming the system
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"{Fore.RED}✗ Error processing {doc['filename']}: {e}{Style.RESET_ALL}")
                    continue
        
        print(f"\n{Fore.GREEN}✅ Indexing complete!{Style.RESET_ALL}")
        print(f"{Fore.GREEN}   Total chunks indexed: {total_indexed}{Style.RESET_ALL}")
        
        return total_indexed
    
    def index_single_document(self, s3_key: str) -> int:
        """Index a single document from S3"""
        print(f"\n{Fore.CYAN}📄 Indexing: {s3_key}{Style.RESET_ALL}")
        
        content = self.s3_fetcher.read_document(s3_key)
        
        if not content:
            print(f"{Fore.RED}✗ Failed to read document{Style.RESET_ALL}")
            return 0
        
        chunks = self.rag_manager.index_document(
            text=content,
            source=s3_key
        )
        
        print(f"{Fore.GREEN}✓ Indexed {chunks} chunks{Style.RESET_ALL}")
        return chunks
    
    def reindex_document(self, s3_key: str) -> int:
        """Delete and reindex a document"""
        print(f"\n{Fore.YELLOW}🔄 Reindexing: {s3_key}{Style.RESET_ALL}")
        
        # Delete existing chunks
        self.rag_manager.delete_document(s3_key)
        
        # Reindex
        return self.index_single_document(s3_key)
    
    def get_stats(self) -> dict:
        """Get indexing statistics"""
        total_chunks = self.rag_manager.get_document_count()
        
        return {
            'total_chunks': total_chunks,
            'index_name': self.rag_manager.index_name
        }
    
    def test_search(self, query: str, k: int = 3):
        """Test search functionality"""
        print(f"\n{Fore.CYAN}🔍 Testing search: '{query}'{Style.RESET_ALL}")
        
        results = self.rag_manager.search_similar(query, k=k)
        
        if not results:
            print(f"{Fore.YELLOW}⚠ No results found{Style.RESET_ALL}")
            return
        
        print(f"\n{Fore.GREEN}Found {len(results)} relevant chunks:{Style.RESET_ALL}\n")
        
        for i, result in enumerate(results, 1):
            source = Path(result['source']).name
            print(f"{i}. {Fore.CYAN}{source}{Style.RESET_ALL} (score: {result['score']:.3f})")
            print(f"   {result['text'][:200]}...")
            print()


def main():
    """Main entry point"""
    
    # Configuration
    s3_bucket = os.getenv('S3_BUCKET_NAME')
    s3_prefix = os.getenv('S3_PREFIX', 'knowledge-base/')
    opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT')
    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if not s3_bucket or not opensearch_endpoint:
        print(f"{Fore.RED}✗ Missing required configuration:{Style.RESET_ALL}")
        print(f"  S3_BUCKET_NAME: {'✓' if s3_bucket else '✗'}")
        print(f"  OPENSEARCH_ENDPOINT: {'✓' if opensearch_endpoint else '✗'}")
        sys.exit(1)
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}📚 Document Indexer for RAG{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    # Initialize indexer
    indexer = DocumentIndexer(
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        opensearch_endpoint=opensearch_endpoint,
        ollama_url=ollama_url,
        aws_region=aws_region
    )
    
    # Setup RAG system
    indexer.setup()
    
    # Check command line argument
    command = sys.argv[1] if len(sys.argv) > 1 else 'index_all'
    
    if command == 'index_all':
        # Index all documents
        indexer.index_all_documents()
        
    elif command == 'stats':
        # Show statistics
        stats = indexer.get_stats()
        print(f"\n{Fore.CYAN}Statistics:{Style.RESET_ALL}")
        print(f"  Index: {stats['index_name']}")
        print(f"  Total chunks: {stats['total_chunks']}")
        
    elif command == 'test':
        # Test search
        query = sys.argv[2] if len(sys.argv) > 2 else "database connection error"
        indexer.test_search(query)
        
    else:
        print(f"{Fore.RED}Unknown command: {command}{Style.RESET_ALL}")
        print("\nUsage:")
        print("  python document_indexer.py index_all  # Index all documents")
        print("  python document_indexer.py stats      # Show statistics")
        print("  python document_indexer.py test <query>  # Test search")
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Complete{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
