#!/usr/bin/env python3
"""
Log Analyst Agent - Enhanced with OpenSearch Integration
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import ollama
from colorama import init, Fore, Style

# Import OpenSearch integration if available
try:
    from opensearch_integration import OpenSearchLogFetcher
    OPENSEARCH_AVAILABLE = True
except ImportError:
    OPENSEARCH_AVAILABLE = False
    print(f"{Fore.YELLOW}⚠ OpenSearch integration not available{Style.RESET_ALL}")

# Initialize colorama
init()

class LogAnalystAgent:
    """Main agent class for analyzing logs using Ollama"""
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model_name: str = "llama3.1:8b",
        output_dir: str = "/app/output",
        opensearch_endpoint: Optional[str] = None,
        aws_region: str = "us-east-1"
    ):
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Ollama client
        self.client = ollama.Client(host=ollama_url)
        
        # Initialize OpenSearch if configured
        self.opensearch = None
        if opensearch_endpoint and OPENSEARCH_AVAILABLE:
            try:
                self.opensearch = OpenSearchLogFetcher(opensearch_endpoint, aws_region)
                print(f"{Fore.GREEN}✓ OpenSearch integration enabled{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}✗ OpenSearch connection failed: {e}{Style.RESET_ALL}")
        
        print(f"{Fore.CYAN}🤖 Log Analyst Agent Initialized{Style.RESET_ALL}")
        print(f"   Ollama URL: {ollama_url}")
        print(f"   Model: {model_name}")
        print(f"   Data Source: {'OpenSearch' if self.opensearch else 'Local Files'}")
        
    def ensure_model(self):
        """Ensure the model is pulled and ready"""
        try:
            print(f"{Fore.YELLOW}📥 Checking model availability...{Style.RESET_ALL}")
            
            try:
                self.client.show(self.model_name)
                print(f"{Fore.GREEN}✓ Model {self.model_name} is ready{Style.RESET_ALL}")
            except:
                print(f"{Fore.YELLOW}📥 Pulling model {self.model_name}...{Style.RESET_ALL}")
                self.client.pull(self.model_name)
                print(f"{Fore.GREEN}✓ Model pulled successfully{Style.RESET_ALL}")
                
        except Exception as e:
            print(f"{Fore.RED}❌ Error with model: {e}{Style.RESET_ALL}")
            raise
    
    def fetch_logs_from_opensearch(
        self,
        index_pattern: str = "logs-*",
        time_range_minutes: int = 60,
        application: Optional[str] = None,
        errors_only: bool = False
    ) -> tuple[str, Dict]:
        """Fetch logs from OpenSearch"""
        
        if not self.opensearch:
            print(f"{Fore.RED}❌ OpenSearch not configured{Style.RESET_ALL}")
            return "", {}
        
        print(f"{Fore.CYAN}🔍 Fetching logs from OpenSearch...{Style.RESET_ALL}")
        print(f"   Index: {index_pattern}")
        print(f"   Time Range: Last {time_range_minutes} minutes")
        
        # Fetch logs based on parameters
        if application:
            logs = self.opensearch.fetch_logs_by_application(
                application, 
                time_range_minutes=time_range_minutes
            )
        elif errors_only:
            logs = self.opensearch.fetch_error_logs(
                index_pattern=index_pattern,
                time_range_minutes=time_range_minutes
            )
        else:
            logs = self.opensearch.fetch_logs(
                index_pattern=index_pattern,
                time_range_minutes=time_range_minutes
            )
        
        if not logs:
            print(f"{Fore.YELLOW}⚠ No logs found{Style.RESET_ALL}")
            return "", {}
        
        # Get statistics
        stats = self.opensearch.get_log_statistics(logs)
        
        # Format for analysis
        log_content = self.opensearch.format_logs_for_analysis(logs)
        
        print(f"{Fore.GREEN}✓ Fetched {len(logs)} logs{Style.RESET_ALL}")
        print(f"   Levels: {stats['by_level']}")
        
        return log_content, stats
    
    def analyze_logs(self, log_content: str, analysis_type: str = "general", metadata: Optional[Dict] = None) -> Dict:
        """Analyze logs using Ollama"""
        
        if not log_content:
            return {'error': 'No log content provided'}
        
        # Create context-aware prompt
        prompt = self._create_analysis_prompt(log_content, analysis_type, metadata)
        
        print(f"{Fore.CYAN}🔍 Analyzing logs with {self.model_name}...{Style.RESET_ALL}")
        
        try:
            response = self.client.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'system',
                        'content': 'You are an expert log analyst. Analyze logs concisely and identify critical issues, patterns, and actionable insights.'
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                options={
                    'temperature': 0.3,
                    'num_predict': 1500
                }
            )
            
            analysis = response['message']['content']
            
            return {
                'timestamp': datetime.now().isoformat(),
                'model': self.model_name,
                'analysis_type': analysis_type,
                'metadata': metadata or {},
                'analysis': analysis,
                'log_lines': len(log_content.split('\n'))
            }
            
        except Exception as e:
            print(f"{Fore.RED}❌ Analysis error: {e}{Style.RESET_ALL}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _create_analysis_prompt(self, log_content: str, analysis_type: str, metadata: Optional[Dict] = None) -> str:
        """Create an optimized prompt for log analysis"""
        
        if analysis_type == "security":
            focus = "Focus on security incidents, unauthorized access attempts, suspicious patterns, and potential vulnerabilities."
        elif analysis_type == "performance":
            focus = "Focus on performance bottlenecks, slow queries, high latency, resource exhaustion, and optimization opportunities."
        elif analysis_type == "errors":
            focus = "Focus on errors, exceptions, failed operations, and their root causes."
        else:
            focus = "Provide a comprehensive overview including errors, warnings, patterns, and actionable recommendations."
        
        stats_text = ""
        if metadata:
            stats_text = f"\n**Log Statistics:**\n"
            for key, value in metadata.items():
                stats_text += f"- {key}: {value}\n"
        
        prompt = f"""Analyze the following application logs from our production environment. {focus}
{stats_text}
**Logs:**
```
{log_content[:10000]}  # Limit to avoid token overflow
```

Please provide:
1. **Summary**: Brief overview of log health and system status
2. **Critical Issues**: Most urgent problems requiring immediate attention (if any)
3. **Patterns & Trends**: Notable trends or recurring issues
4. **Recommendations**: 2-3 specific, actionable next steps

Be concise and prioritize actionable insights. Focus on what the operations team needs to know right now."""
        
        return prompt
    
    def save_analysis(self, analysis: Dict, source_name: str = "opensearch"):
        """Save analysis results to output directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save JSON
        json_file = self.output_dir / f"analysis_{source_name}_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump(analysis, indent=2, fp=f)
        
        print(f"{Fore.GREEN}💾 Analysis saved: {json_file}{Style.RESET_ALL}")
        
        # Save human-readable version
        txt_file = self.output_dir / f"analysis_{source_name}_{timestamp}.txt"
        with open(txt_file, 'w') as f:
            f.write(f"Log Analysis Report\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Generated: {analysis.get('timestamp', 'N/A')}\n")
            f.write(f"Model: {analysis.get('model', 'N/A')}\n")
            f.write(f"Analysis Type: {analysis.get('analysis_type', 'N/A')}\n")
            f.write(f"Log Lines Analyzed: {analysis.get('log_lines', 'N/A')}\n\n")
            
            if 'metadata' in analysis and analysis['metadata']:
                f.write(f"Metadata:\n")
                f.write(f"{'-'*60}\n")
                for key, value in analysis['metadata'].items():
                    f.write(f"  {key}: {value}\n")
                f.write(f"\n")
            
            f.write(f"Analysis:\n")
            f.write(f"{'-'*60}\n")
            f.write(analysis.get('analysis', 'No analysis available'))
        
        print(f"{Fore.GREEN}📄 Readable report: {txt_file}{Style.RESET_ALL}")
        
        return json_file, txt_file


def main():
    """Main entry point"""
    
    # Configuration from environment
    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    model_name = os.getenv('MODEL_NAME', 'llama3.1:8b')
    output_dir = Path(os.getenv('OUTPUT_DIR', '/app/output'))
    analysis_type = os.getenv('ANALYSIS_TYPE', 'general')
    watch_mode = os.getenv('WATCH_MODE', 'false').lower() == 'true'
    
    # OpenSearch configuration
    opensearch_endpoint = os.getenv('OPENSEARCH_ENDPOINT')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    index_pattern = os.getenv('OPENSEARCH_INDEX', 'logs-*')
    time_range = int(os.getenv('TIME_RANGE_MINUTES', '60'))
    application = os.getenv('APPLICATION_NAME')
    errors_only = os.getenv('ERRORS_ONLY', 'false').lower() == 'true'
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🚀 Log Analyst Agent Starting{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    # Initialize agent
    agent = LogAnalystAgent(
        ollama_url=ollama_url,
        model_name=model_name,
        output_dir=str(output_dir),
        opensearch_endpoint=opensearch_endpoint,
        aws_region=aws_region
    )
    
    # Ensure model is available
    agent.ensure_model()
    
    # Run analysis
    if watch_mode:
        print(f"{Fore.CYAN}👁 Watch mode enabled{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Press Ctrl+C to stop{Style.RESET_ALL}\n")
        
        interval = int(os.getenv('WATCH_INTERVAL_MINUTES', '5'))
        
        try:
            while True:
                print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
                print(f"{Fore.CYAN}🔄 Running analysis cycle{Style.RESET_ALL}")
                print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
                
                if agent.opensearch:
                    log_content, stats = agent.fetch_logs_from_opensearch(
                        index_pattern=index_pattern,
                        time_range_minutes=time_range,
                        application=application,
                        errors_only=errors_only
                    )
                    
                    if log_content:
                        analysis = agent.analyze_logs(log_content, analysis_type, stats)
                        agent.save_analysis(analysis, source_name=application or "opensearch")
                
                print(f"\n{Fore.CYAN}💤 Sleeping for {interval} minutes...{Style.RESET_ALL}\n")
                time.sleep(interval * 60)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}👋 Stopping watch mode{Style.RESET_ALL}")
    else:
        # Single analysis run
        if agent.opensearch:
            log_content, stats = agent.fetch_logs_from_opensearch(
                index_pattern=index_pattern,
                time_range_minutes=time_range,
                application=application,
                errors_only=errors_only
            )
            
            if log_content:
                analysis = agent.analyze_logs(log_content, analysis_type, stats)
                agent.save_analysis(analysis, source_name=application or "opensearch")
        else:
            print(f"{Fore.YELLOW}⚠ OpenSearch not configured, use LOG_DIR for file-based analysis{Style.RESET_ALL}")
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Log Analyst Agent Finished{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
