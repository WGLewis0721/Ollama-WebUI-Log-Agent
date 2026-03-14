#!/usr/bin/env python3
"""
RAG Module - Document processing and vector storage in OpenSearch
Uses OpenSearch k-NN for cost-effective vector search
"""

import os
import json
from typing import List, Dict, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3
import ollama
from pathlib import Path
import hashlib

class RAGManager:
    """Manage RAG documents in OpenSearch with k-NN"""
    
    def __init__(
        self,
        opensearch_endpoint: str,
        ollama_url: str = "http://localhost:11434",
        embedding_model: str = "nomic-embed-text",
        region: str = "us-east-1",
        index_name: str = "knowledge-base"
    ):
        self.opensearch_endpoint = opensearch_endpoint
        self.ollama_url = ollama_url
        self.embedding_model = embedding_model
        self.index_name = index_name
        
        # Initialize OpenSearch client
        credentials = boto3.Session().get_credentials()
        awsauth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            region,
            'es',
            session_token=credentials.token
        )
        
        self.os_client = OpenSearch(
            hosts=[{'host': opensearch_endpoint, 'port': 443}],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
        
        # Initialize Ollama client
        self.ollama_client = ollama.Client(host=ollama_url)
        
        print(f"✓ RAG Manager initialized")
        print(f"   OpenSearch: {opensearch_endpoint}")
        print(f"   Embedding Model: {embedding_model}")
        print(f"   Index: {index_name}")
    
    def ensure_embedding_model(self):
        """Ensure embedding model is available"""
        try:
            # Check if model exists
            try:
                self.ollama_client.show(self.embedding_model)
                print(f"✓ Embedding model {self.embedding_model} is ready")
            except:
                print(f"📥 Pulling embedding model {self.embedding_model}...")
                self.ollama_client.pull(self.embedding_model)
                print(f"✓ Model pulled successfully")
        except Exception as e:
            print(f"✗ Error with embedding model: {e}")
            raise
    
    def create_index(self, dimension: int = 768):
        """
        Create OpenSearch index with k-NN mapping
        
        Args:
            dimension: Embedding dimension (768 for nomic-embed-text)
        """
        index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 100
                }
            },
            "mappings": {
                "properties": {
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": dimension,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24
                            }
                        }
                    },
                    "text": {"type": "text"},
                    "source": {"type": "keyword"},
                    "chunk_id": {"type": "keyword"},
                    "metadata": {"type": "object"},
                    "timestamp": {"type": "date"}
                }
            }
        }
        
        try:
            if not self.os_client.indices.exists(index=self.index_name):
                self.os_client.indices.create(index=self.index_name, body=index_body)
                print(f"✓ Created index: {self.index_name}")
            else:
                print(f"✓ Index already exists: {self.index_name}")
        except Exception as e:
            print(f"✗ Error creating index: {e}")
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split text into overlapping chunks
        
        Args:
            text: Input text
            chunk_size: Size of each chunk in characters
            overlap: Overlap between chunks
        
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.5:  # At least 50% into chunk
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return [c for c in chunks if c]  # Remove empty chunks
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Ollama
        
        Args:
            text: Input text
        
        Returns:
            Embedding vector
        """
        try:
            response = self.ollama_client.embeddings(
                model=self.embedding_model,
                prompt=text
            )
            return response['embedding']
        except Exception as e:
            print(f"✗ Error generating embedding: {e}")
            return []
    
    def index_document(
        self,
        text: str,
        source: str,
        metadata: Optional[Dict] = None,
        chunk_size: int = 500
    ) -> int:
        """
        Index a document with embeddings
        
        Args:
            text: Document text
            source: Source identifier (filename, URL, etc.)
            metadata: Additional metadata
            chunk_size: Size of text chunks
        
        Returns:
            Number of chunks indexed
        """
        chunks = self.chunk_text(text, chunk_size=chunk_size)
        indexed = 0
        
        print(f"📄 Indexing document: {source} ({len(chunks)} chunks)")
        
        for i, chunk in enumerate(chunks):
            # Generate unique ID for this chunk
            chunk_id = hashlib.md5(f"{source}_{i}".encode()).hexdigest()
            
            # Generate embedding
            embedding = self.generate_embedding(chunk)
            
            if not embedding:
                continue
            
            # Create document
            doc = {
                "text": chunk,
                "embedding": embedding,
                "source": source,
                "chunk_id": chunk_id,
                "chunk_index": i,
                "metadata": metadata or {},
                "timestamp": "now"
            }
            
            try:
                self.os_client.index(
                    index=self.index_name,
                    id=chunk_id,
                    body=doc,
                    refresh=True
                )
                indexed += 1
            except Exception as e:
                print(f"✗ Error indexing chunk {i}: {e}")
        
        print(f"✓ Indexed {indexed} chunks from {source}")
        return indexed
    
    def search_similar(
        self,
        query: str,
        k: int = 5,
        min_score: float = 0.5
    ) -> List[Dict]:
        """
        Search for similar documents using k-NN
        
        Args:
            query: Search query
            k: Number of results to return
            min_score: Minimum similarity score (0-1)
        
        Returns:
            List of matching documents with scores
        """
        # Generate query embedding
        query_embedding = self.generate_embedding(query)
        
        if not query_embedding:
            return []
        
        # k-NN search query
        search_query = {
            "size": k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": k
                    }
                }
            },
            "_source": ["text", "source", "metadata", "chunk_index"]
        }
        
        try:
            response = self.os_client.search(
                index=self.index_name,
                body=search_query
            )
            
            results = []
            for hit in response['hits']['hits']:
                score = hit['_score']
                
                # Filter by minimum score
                if score >= min_score:
                    results.append({
                        'text': hit['_source']['text'],
                        'source': hit['_source']['source'],
                        'metadata': hit['_source'].get('metadata', {}),
                        'chunk_index': hit['_source'].get('chunk_index', 0),
                        'score': score
                    })
            
            return results
            
        except Exception as e:
            print(f"✗ Error searching: {e}")
            return []
    
    def get_document_count(self) -> int:
        """Get total number of chunks in index"""
        try:
            response = self.os_client.count(index=self.index_name)
            return response['count']
        except:
            return 0
    
    def delete_document(self, source: str) -> int:
        """
        Delete all chunks for a document
        
        Args:
            source: Source identifier
        
        Returns:
            Number of chunks deleted
        """
        try:
            response = self.os_client.delete_by_query(
                index=self.index_name,
                body={
                    "query": {
                        "term": {"source": source}
                    }
                }
            )
            deleted = response['deleted']
            print(f"✓ Deleted {deleted} chunks from {source}")
            return deleted
        except Exception as e:
            print(f"✗ Error deleting document: {e}")
            return 0


class RAGEnhancedAnalyzer:
    """Enhanced log analyzer with RAG context"""
    
    def __init__(
        self,
        rag_manager: RAGManager,
        ollama_client: ollama.Client
    ):
        self.rag = rag_manager
        self.ollama = ollama_client
    
    def analyze_with_context(
        self,
        log_content: str,
        model: str = "llama3.1:8b",
        k: int = 3
    ) -> Dict:
        """
        Analyze logs with RAG context
        
        Args:
            log_content: Log text to analyze
            model: LLM model to use
            k: Number of context documents to retrieve
        
        Returns:
            Analysis result with context
        """
        # Extract key issues/errors for context search
        query = self._extract_search_query(log_content)
        
        # Search for relevant context
        context_docs = self.rag.search_similar(query, k=k)
        
        # Build context section
        context_text = self._build_context_section(context_docs)
        
        # Create enhanced prompt
        prompt = f"""Analyze the following application logs. Use the provided documentation and runbooks for context.

{context_text}

**Logs to Analyze:**
```
{log_content[:8000]}
```

Provide:
1. Summary with reference to relevant documentation
2. Critical issues with recommended actions from runbooks
3. Specific steps from your knowledge base
"""
        
        # Get analysis
        try:
            response = self.ollama.chat(
                model=model,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert log analyst with access to company documentation and runbooks.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            )
            
            return {
                'analysis': response['message']['content'],
                'context_used': len(context_docs),
                'context_sources': [doc['source'] for doc in context_docs]
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def _extract_search_query(self, log_content: str) -> str:
        """Extract key terms for context search"""
        # Simple extraction - could be enhanced
        lines = log_content.split('\n')
        error_lines = [l for l in lines if 'ERROR' in l or 'CRITICAL' in l]
        
        if error_lines:
            return ' '.join(error_lines[:3])
        else:
            return ' '.join(lines[:10])
    
    def _build_context_section(self, context_docs: List[Dict]) -> str:
        """Build context section from retrieved documents"""
        if not context_docs:
            return "**No relevant documentation found.**"
        
        context = "**Relevant Documentation:**\n\n"
        
        for i, doc in enumerate(context_docs, 1):
            source = Path(doc['source']).name
            context += f"{i}. From {source} (relevance: {doc['score']:.2f}):\n"
            context += f"   {doc['text'][:300]}...\n\n"
        
        return context


if __name__ == "__main__":
    # Test RAG setup
    endpoint = os.getenv('OPENSEARCH_ENDPOINT', 'your-domain.us-east-1.es.amazonaws.com')
    
    try:
        rag = RAGManager(endpoint)
        rag.ensure_embedding_model()
        rag.create_index()
        
        count = rag.get_document_count()
        print(f"\n✓ RAG system ready")
        print(f"   Documents indexed: {count}")
        
    except Exception as e:
        print(f"\n✗ RAG setup failed: {e}")
