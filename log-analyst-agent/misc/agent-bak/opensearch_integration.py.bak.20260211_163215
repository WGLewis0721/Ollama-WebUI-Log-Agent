#!/usr/bin/env python3
"""
OpenSearch Integration Module
Connects to AWS OpenSearch to fetch logs for analysis
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

class OpenSearchLogFetcher:
    """Fetches logs from AWS OpenSearch for analysis"""
    
    def __init__(
        self,
        opensearch_endpoint: str,
        region: str = 'us-east-1',
        use_aws_auth: bool = True,
        username: Optional[str] = None,
        password: Optional[str] = None
    ):
        self.endpoint = opensearch_endpoint
        self.region = region
        
        if use_aws_auth:
            # Use AWS IAM authentication
            credentials = boto3.Session().get_credentials()
            awsauth = AWS4Auth(
                credentials.access_key,
                credentials.secret_key,
                region,
                'es',
                session_token=credentials.token
            )
            
            self.client = OpenSearch(
                hosts=[{'host': opensearch_endpoint, 'port': 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
        else:
            # Use basic authentication
            self.client = OpenSearch(
                hosts=[{'host': opensearch_endpoint, 'port': 443}],
                http_auth=(username, password),
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
        
        print(f"✓ Connected to OpenSearch: {opensearch_endpoint}")
    
    def fetch_logs(
        self,
        index_pattern: str = "logs-*",
        time_range_minutes: int = 60,
        max_logs: int = 1000,
        query: Optional[Dict] = None,
        log_level_filter: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Fetch logs from OpenSearch
        
        Args:
            index_pattern: Index pattern to search (e.g., "logs-*", "application-*")
            time_range_minutes: How far back to fetch logs
            max_logs: Maximum number of logs to retrieve
            query: Custom OpenSearch query (optional)
            log_level_filter: Filter by log levels (e.g., ["ERROR", "WARNING"])
        
        Returns:
            List of log documents
        """
        
        # Build time range query
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_range_minutes)
        
        if query is None:
            query = {
                "bool": {
                    "must": [
                        {
                            "range": {
                                "@timestamp": {
                                    "gte": start_time.isoformat(),
                                    "lte": end_time.isoformat()
                                }
                            }
                        }
                    ]
                }
            }
            
            # Add log level filter if specified
            if log_level_filter:
                query["bool"]["should"] = [
                    {"match": {"level": level}} for level in log_level_filter
                ]
                query["bool"]["minimum_should_match"] = 1
        
        try:
            response = self.client.search(
                index=index_pattern,
                body={
                    "query": query,
                    "size": max_logs,
                    "sort": [{"@timestamp": {"order": "desc"}}]
                }
            )
            
            hits = response['hits']['hits']
            logs = [hit['_source'] for hit in hits]
            
            print(f"✓ Fetched {len(logs)} logs from {index_pattern}")
            return logs
            
        except Exception as e:
            print(f"✗ Error fetching logs from OpenSearch: {e}")
            return []
    
    def fetch_logs_by_application(
        self,
        application_name: str,
        time_range_minutes: int = 60,
        max_logs: int = 1000
    ) -> List[Dict]:
        """Fetch logs for a specific application"""
        
        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": f"now-{time_range_minutes}m",
                                "lte": "now"
                            }
                        }
                    },
                    {
                        "match": {
                            "kubernetes.labels.app": application_name
                        }
                    }
                ]
            }
        }
        
        return self.fetch_logs(query=query, max_logs=max_logs)
    
    def fetch_error_logs(
        self,
        index_pattern: str = "logs-*",
        time_range_minutes: int = 60,
        max_logs: int = 500
    ) -> List[Dict]:
        """Fetch only ERROR and CRITICAL logs"""
        
        return self.fetch_logs(
            index_pattern=index_pattern,
            time_range_minutes=time_range_minutes,
            max_logs=max_logs,
            log_level_filter=["ERROR", "CRITICAL", "FATAL"]
        )
    
    def format_logs_for_analysis(self, logs: List[Dict]) -> str:
        """
        Convert OpenSearch logs to readable text format for LLM analysis
        """
        
        formatted_lines = []
        
        for log in logs:
            # Extract common fields
            timestamp = log.get('@timestamp', 'Unknown')
            level = log.get('level', log.get('log.level', 'INFO'))
            message = log.get('message', log.get('log', str(log)))
            
            # Optional fields
            service = log.get('service.name', log.get('kubernetes.labels.app', ''))
            host = log.get('host.name', '')
            
            # Format as readable log line
            parts = [timestamp, level.upper()]
            if service:
                parts.append(f"[{service}]")
            if host:
                parts.append(f"({host})")
            parts.append(message)
            
            formatted_lines.append(' '.join(parts))
        
        return '\n'.join(formatted_lines)
    
    def get_log_statistics(self, logs: List[Dict]) -> Dict:
        """Generate statistics from logs"""
        
        stats = {
            'total_logs': len(logs),
            'by_level': {},
            'by_service': {},
            'time_range': {
                'start': None,
                'end': None
            }
        }
        
        if not logs:
            return stats
        
        # Count by level
        for log in logs:
            level = log.get('level', log.get('log.level', 'UNKNOWN')).upper()
            stats['by_level'][level] = stats['by_level'].get(level, 0) + 1
            
            # Count by service
            service = log.get('service.name', log.get('kubernetes.labels.app', 'unknown'))
            stats['by_service'][service] = stats['by_service'].get(service, 0) + 1
        
        # Time range
        timestamps = [log.get('@timestamp') for log in logs if log.get('@timestamp')]
        if timestamps:
            stats['time_range']['start'] = min(timestamps)
            stats['time_range']['end'] = max(timestamps)
        
        return stats
    
    def search_by_pattern(
        self,
        pattern: str,
        index_pattern: str = "logs-*",
        time_range_minutes: int = 60,
        max_logs: int = 500
    ) -> List[Dict]:
        """Search logs by pattern (e.g., error messages, IPs, etc.)"""
        
        query = {
            "bool": {
                "must": [
                    {
                        "range": {
                            "@timestamp": {
                                "gte": f"now-{time_range_minutes}m",
                                "lte": "now"
                            }
                        }
                    },
                    {
                        "query_string": {
                            "query": pattern,
                            "default_field": "message"
                        }
                    }
                ]
            }
        }
        
        return self.fetch_logs(
            index_pattern=index_pattern,
            query=query,
            max_logs=max_logs
        )


def test_connection():
    """Test OpenSearch connection"""
    
    endpoint = os.getenv('OPENSEARCH_ENDPOINT', 'your-domain.us-east-1.es.amazonaws.com')
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    try:
        fetcher = OpenSearchLogFetcher(endpoint, region)
        logs = fetcher.fetch_logs(max_logs=10)
        
        if logs:
            print(f"✓ Successfully fetched {len(logs)} logs")
            print("\nSample log:")
            print(json.dumps(logs[0], indent=2))
        else:
            print("✗ No logs found")
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")


if __name__ == "__main__":
    test_connection()
