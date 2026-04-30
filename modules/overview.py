"""
Overview Tab Module - Dashboard summary and key metrics
"""

import os
import json
from datetime import datetime

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'tool-output')

def get_overview_data():
    """
    Fetches overview dashboard data including security metrics from tool-output
    """
    recent_scans = get_recent_scans(10)
    
    total_critical = 0
    total_high = 0
    total_medium = 0
    total_low = 0
    
    for scan in recent_scans:
        severity = scan.get('severity', {})
        total_critical += severity.get('CRITICAL', 0)
        total_high += severity.get('HIGH', 0)
        total_medium += severity.get('MEDIUM', 0)
        total_low += severity.get('LOW', 0)
    
    return {
        'total_repos': 0,
        'active_scans': 0,
        'critical_issues': total_critical,
        'high_issues': total_high,
        'medium_issues': total_medium,
        'low_issues': total_low,
        'compliance_score': calculate_security_score(total_critical, total_high, total_medium, total_low),
        'last_scan': recent_scans[0]['timestamp'] if recent_scans else None,
        'scan_status': 'idle',
        'security_trends': {},
        'top_vulnerabilities': [],
        'recent_scans': recent_scans
    }


def get_recent_scans(limit=10):
    """
    Get recent scans from tool-output directory
    """
    scans = []
    
    if not os.path.exists(LOGS_DIR):
        return scans
    
    scan_dirs = sorted(os.listdir(LOGS_DIR), reverse=True)[:limit]
    
    for scan_id in scan_dirs:
        scan_path = os.path.join(LOGS_DIR, scan_id)
        if not os.path.isdir(scan_path):
            continue
            
        merged_file = os.path.join(scan_path, 'merged.json')
        if os.path.exists(merged_file):
            try:
                with open(merged_file, 'r') as f:
                    data = json.load(f)
                    
                    # Get severity from summary
                    severity = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
                    summary = data.get('summary', {})
                    by_severity = summary.get('by_severity', {})
                    
                    for sev, count in by_severity.items():
                        if sev in severity:
                            severity[sev] = count
                    
                    # Get timestamp and scan_id
                    timestamp = data.get('timestamp', '')
                    
                    # Get findings count
                    findings = data.get('findings', [])
                    total = summary.get('total_unique', len(findings))
                    
                    # Extract repo name from scan_id (or use "Unknown")
                    repo_name = scan_id[:8] + '...'
                    
                    scans.append({
                        'scan_id': scan_id,
                        'repository': repo_name,
                        'timestamp': timestamp,
                        'total_findings': total,
                        'severity': severity
                    })
            except Exception as e:
                print(f"Error reading {merged_file}: {e}")
    
    return scans


def calculate_security_score(critical, high, medium, low):
    """
    Calculate overall security score based on issues
    """
    total = critical + high + medium + low
    if total == 0:
        return 100
    
    penalty = (critical * 10) + (high * 5) + (medium * 2) + (low * 1)
    score = max(0, 100 - penalty)
    return score


def get_security_status():
    """Determine overall security status"""
    return 'idle'