#!/usr/bin/env python3
"""
Log Analyst Agent - Intelligent log analysis using Ollama
"""

import os
import sys
import json
import time
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import ollama
from colorama import init, Fore, Style

# Initialize colorama
init()

class LogAnalystAgent:
    """Main agent class for analyzing logs using Ollama"""
    
    def __init__(
        self,
        ollama_url: str = "http://localhost:11434",
        model_name: str = "llama3.2:3b",
        output_dir: str = "/app/output"
    ):
        self.ollama_url = ollama_url
        self.model_name = model_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Ollama client
        self.client = ollama.Client(host=ollama_url)
        
        print(f"{Fore.CYAN}🤖 Log Analyst Agent Initialized{Style.RESET_ALL}")
        print(f"   Ollama URL: {ollama_url}")
        print(f"   Model: {model_name}")
        
    def ensure_model(self):
        """Ensure the model is pulled and ready"""
        try:
            print(f"{Fore.YELLOW}📥 Checking model availability...{Style.RESET_ALL}")
            self.client.list()
            
            # Try to pull the model if not available
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
    
    def read_log_file(self, log_path: Path, max_lines: int = 1000) -> str:
        """Read log file with size limits"""
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            if len(lines) > max_lines:
                print(f"{Fore.YELLOW}⚠ Log file has {len(lines)} lines, taking last {max_lines}{Style.RESET_ALL}")
                lines = lines[-max_lines:]
            
            return ''.join(lines)
        except Exception as e:
            print(f"{Fore.RED}❌ Error reading log file: {e}{Style.RESET_ALL}")
            return ""
    
    def extract_log_patterns(self, log_content: str) -> Dict:
        """Extract common patterns from logs"""
        patterns = {
            'errors': len(re.findall(r'ERROR|error|Error', log_content)),
            'warnings': len(re.findall(r'WARNING|warning|Warning|WARN', log_content)),
            'exceptions': len(re.findall(r'Exception|exception|Traceback', log_content)),
            'critical': len(re.findall(r'CRITICAL|critical|Critical|FATAL', log_content)),
            'status_codes': {
                '4xx': len(re.findall(r'\s4\d{2}\s', log_content)),
                '5xx': len(re.findall(r'\s5\d{2}\s', log_content))
            }
        }
        return patterns
    
    def analyze_logs(self, log_content: str, analysis_type: str = "general") -> Dict:
        """Analyze logs using Ollama"""
        
        patterns = self.extract_log_patterns(log_content)
        
        # Create context-aware prompt
        prompt = self._create_analysis_prompt(log_content, patterns, analysis_type)
        
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
                    'temperature': 0.3,  # Lower temperature for more focused analysis
                    'num_predict': 1000
                }
            )
            
            analysis = response['message']['content']
            
            return {
                'timestamp': datetime.now().isoformat(),
                'model': self.model_name,
                'analysis_type': analysis_type,
                'patterns': patterns,
                'analysis': analysis,
                'log_lines': len(log_content.split('\n'))
            }
            
        except Exception as e:
            print(f"{Fore.RED}❌ Analysis error: {e}{Style.RESET_ALL}")
            return {
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _create_analysis_prompt(self, log_content: str, patterns: Dict, analysis_type: str) -> str:
        """Create an optimized prompt for log analysis"""
        
        if analysis_type == "security":
            focus = "Focus on security incidents, unauthorized access attempts, suspicious patterns, and potential vulnerabilities."
        elif analysis_type == "performance":
            focus = "Focus on performance bottlenecks, slow queries, high latency, resource exhaustion, and optimization opportunities."
        elif analysis_type == "errors":
            focus = "Focus on errors, exceptions, failed operations, and their root causes."
        else:
            focus = "Provide a comprehensive overview including errors, warnings, patterns, and actionable recommendations."
        
        prompt = f"""Analyze the following application logs. {focus}

**Log Statistics:**
- Errors: {patterns['errors']}
- Warnings: {patterns['warnings']}
- Exceptions: {patterns['exceptions']}
- Critical: {patterns['critical']}
- HTTP 4xx: {patterns['status_codes']['4xx']}
- HTTP 5xx: {patterns['status_codes']['5xx']}

**Logs:**
```
{log_content[:8000]}  # Limit to avoid token overflow
```

Please provide:
1. **Summary**: Brief overview of log health
2. **Critical Issues**: Most urgent problems (if any)
3. **Patterns**: Notable trends or recurring issues
4. **Recommendations**: 2-3 actionable next steps

Be concise and prioritize actionable insights."""
        
        return prompt
    
    def save_analysis(self, analysis: Dict, log_filename: str):
        """Save analysis results to output directory"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = self.output_dir / f"analysis_{log_filename}_{timestamp}.json"
        
        with open(output_file, 'w') as f:
            json.dump(analysis, indent=2, fp=f)
        
        print(f"{Fore.GREEN}💾 Analysis saved: {output_file}{Style.RESET_ALL}")
        
        # Also save a human-readable version
        readable_file = self.output_dir / f"analysis_{log_filename}_{timestamp}.txt"
        with open(readable_file, 'w') as f:
            f.write(f"Log Analysis Report\n")
            f.write(f"={'='*60}\n\n")
            f.write(f"Generated: {analysis.get('timestamp', 'N/A')}\n")
            f.write(f"Model: {analysis.get('model', 'N/A')}\n")
            f.write(f"Analysis Type: {analysis.get('analysis_type', 'N/A')}\n")
            f.write(f"Log Lines Analyzed: {analysis.get('log_lines', 'N/A')}\n\n")
            
            if 'patterns' in analysis:
                f.write(f"Pattern Summary:\n")
                f.write(f"{'-'*60}\n")
                for key, value in analysis['patterns'].items():
                    f.write(f"  {key}: {value}\n")
                f.write(f"\n")
            
            f.write(f"Analysis:\n")
            f.write(f"{'-'*60}\n")
            f.write(analysis.get('analysis', 'No analysis available'))
        
        print(f"{Fore.GREEN}📄 Readable report: {readable_file}{Style.RESET_ALL}")
        
        return output_file, readable_file
    
    def analyze_directory(self, log_dir: Path, pattern: str = "*.log", analysis_type: str = "general"):
        """Analyze all log files in a directory"""
        log_files = list(log_dir.glob(pattern))
        
        if not log_files:
            print(f"{Fore.YELLOW}⚠ No log files found matching pattern: {pattern}{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}📁 Found {len(log_files)} log file(s){Style.RESET_ALL}")
        
        results = []
        for log_file in log_files:
            print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}📄 Analyzing: {log_file.name}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
            
            log_content = self.read_log_file(log_file)
            if log_content:
                analysis = self.analyze_logs(log_content, analysis_type)
                json_file, txt_file = self.save_analysis(analysis, log_file.stem)
                results.append({
                    'log_file': str(log_file),
                    'analysis_file': str(json_file),
                    'readable_file': str(txt_file)
                })
        
        # Create summary
        summary_file = self.output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump({
                'analyzed_at': datetime.now().isoformat(),
                'total_files': len(log_files),
                'results': results
            }, f, indent=2)
        
        print(f"\n{Fore.GREEN}✅ Analysis complete! Summary: {summary_file}{Style.RESET_ALL}")


def main():
    """Main entry point"""
    
    # Configuration from environment
    ollama_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
    model_name = os.getenv('MODEL_NAME', 'llama3.2:3b')
    log_dir = Path(os.getenv('LOG_DIR', '/app/logs'))
    output_dir = Path(os.getenv('OUTPUT_DIR', '/app/output'))
    analysis_type = os.getenv('ANALYSIS_TYPE', 'general')  # general, security, performance, errors
    watch_mode = os.getenv('WATCH_MODE', 'false').lower() == 'true'
    
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}🚀 Log Analyst Agent Starting{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
    
    # Initialize agent
    agent = LogAnalystAgent(
        ollama_url=ollama_url,
        model_name=model_name,
        output_dir=str(output_dir)
    )
    
    # Ensure model is available
    agent.ensure_model()
    
    # Check if log directory exists
    if not log_dir.exists():
        print(f"{Fore.YELLOW}⚠ Creating log directory: {log_dir}{Style.RESET_ALL}")
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # Run analysis
    if watch_mode:
        print(f"{Fore.CYAN}👁 Watch mode enabled - monitoring {log_dir}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Press Ctrl+C to stop{Style.RESET_ALL}\n")
        
        try:
            while True:
                agent.analyze_directory(log_dir, pattern="*.log", analysis_type=analysis_type)
                print(f"\n{Fore.CYAN}💤 Sleeping for 5 minutes...{Style.RESET_ALL}\n")
                time.sleep(300)  # Wait 5 minutes
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}👋 Stopping watch mode{Style.RESET_ALL}")
    else:
        agent.analyze_directory(log_dir, pattern="*.log", analysis_type=analysis_type)
    
    print(f"\n{Fore.GREEN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}✅ Log Analyst Agent Finished{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*60}{Style.RESET_ALL}\n")


if __name__ == "__main__":
    main()
