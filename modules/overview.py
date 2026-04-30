"""
Overview Tab Module - Dashboard summary and key metrics
Max lines: <600
"""

def get_overview_data():
    """
    Fetches overview dashboard data including security metrics
    """
    return {
        'total_repos': 0,
        'active_scans': 0,
        'critical_issues': 0,
        'high_issues': 0,
        'medium_issues': 0,
        'low_issues': 0,
        'compliance_score': 0,
        'last_scan': None,
        'scan_status': 'idle',
        'security_trends': {},
        'top_vulnerabilities': [],
        'recent_scans': []
    }


def calculate_security_score():
    """Calculate overall security score"""
    return 0


def get_security_status():
    """Determine overall security status"""
    return 'idle'
