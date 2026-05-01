"""
History Tab Module - Scan history and audit logs
"""

import os
import json
from datetime import datetime
from pathlib import Path


def get_logs_directory():
    """Get the logs directory path"""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(module_dir)
    logs_dir = os.path.join(project_root, 'logs', 'tool-output')
    return logs_dir


def get_scan_history():
    """
    Fetch scanning history with detailed information from logs/tool-output
    """
    try:
        logs_dir = get_logs_directory()
        if not os.path.exists(logs_dir):
            return []
        
        history = []
        
        # Read each scan directory
        for scan_dir in os.listdir(logs_dir):
            scan_path = os.path.join(logs_dir, scan_dir)
            if not os.path.isdir(scan_path):
                continue
            
            # Try to read merged.json for summary data
            merged_file = os.path.join(scan_path, 'merged.json')
            opengrep_file = os.path.join(scan_path, 'opengrep.json')
            truffle_file = os.path.join(scan_path, 'truffle.json')
            trivy_file = os.path.join(scan_path, 'trivy.json')
            
            scan_data = {
                'scan_id': scan_dir,
                'timestamp': scan_dir,
                'repository': 'Unknown',
                'status': 'unknown',
                'total_findings': 0,
                'severity': {},
                'category': {},
                'multi_source': 0,
                'has_merged': os.path.exists(merged_file),
                'has_opengrep': os.path.exists(opengrep_file),
                'has_truffle': os.path.exists(truffle_file),
                'has_trivy': os.path.exists(trivy_file),
                'files': {
                    'merged': os.path.exists(merged_file),
                    'opengrep': os.path.exists(opengrep_file),
                    'truffle': os.path.exists(truffle_file),
                    'trivy': os.path.exists(trivy_file)
                }
            }
            
            # Try to read merged.json
            if os.path.exists(merged_file):
                try:
                    with open(merged_file, 'r') as f:
                        merged = json.load(f)
                        scan_data['timestamp'] = merged.get('timestamp', scan_dir)
                        repo_owner = merged.get('repo_owner', '')
                        repo_name = merged.get('repo_name', '')
                        scan_data['repository'] = f"{repo_owner}/{repo_name}" if repo_owner and repo_name else (repo_name or 'Unknown')
                        
                        summary = merged.get('summary', {})
                        scan_data['total_findings'] = summary.get('total_unique', 0)
                        scan_data['severity'] = summary.get('by_severity', {})
                        scan_data['category'] = summary.get('by_category', {})
                        scan_data['multi_source'] = summary.get('multi_source_findings', 0)
                        scan_data['tool_breakdown'] = summary.get('tool_breakdown', {})
                        
                        # Get first finding for preview
                        findings = merged.get('findings', [])
                        if findings:
                            scan_data['first_finding'] = {
                                'file': findings[0].get('file', ''),
                                'line': findings[0].get('line', ''),
                                'title': findings[0].get('title', ''),
                                'severity': findings[0].get('severity', ''),
                                'type': findings[0].get('type', '')
                            }
                except Exception as e:
                    pass
            
            # Try to read opengrep.json for repository name
            if os.path.exists(opengrep_file):
                try:
                    with open(opengrep_file, 'r') as f:
                        opengrep = json.load(f)
                        scan_data['repository'] = opengrep.get('repository', scan_data['repository'])
                        scan_data['timestamp'] = opengrep.get('timestamp', scan_data['timestamp'])
                except:
                    pass
            
            history.append(scan_data)
        
        # Sort by timestamp descending
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        return history
        
    except Exception as e:
        print(f"Error getting scan history: {e}")
        return []


def get_history_by_date(days=30):
    """Get scan history for the last N days"""
    history = get_scan_history()
    return sorted(history, key=lambda x: x['timestamp'], reverse=True)[:10]


def get_history_stats():
    """Get statistics from scan history"""
    history = get_scan_history()
    
    total_scans = len(history)
    total_findings = sum(h.get('total_findings', 0) for h in history)
    critical = sum(h.get('severity', {}).get('CRITICAL', 0) for h in history)
    medium = sum(h.get('severity', {}).get('MEDIUM', 0) for h in history)
    low = sum(h.get('severity', {}).get('LOW', 0) for h in history)
    
    return {
        'total_scans': total_scans,
        'total_findings': total_findings,
        'critical_issues': critical,
        'medium_issues': medium,
        'low_issues': low,
        'multi_source_findings': sum(h.get('multi_source', 0) for h in history)
    }


def get_scan_details(scan_id):
    """Get detailed scan information including merged findings"""
    try:
        logs_dir = get_logs_directory()
        scan_path = os.path.join(logs_dir, scan_id)
        
        if not os.path.exists(scan_path):
            return None
        
        # Read all JSON files
        result = {
            'scan_id': scan_id,
            'files': {}
        }
        
        for filename in ['merged.json', 'opengrep.json', 'truffle.json', 'trivy.json']:
            filepath = os.path.join(scan_path, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r') as f:
                        result['files'][filename.replace('.json', '')] = json.load(f)
                except:
                    pass
        
        return result
        
    except Exception as e:
        print(f"Error getting scan details: {e}")
        return None